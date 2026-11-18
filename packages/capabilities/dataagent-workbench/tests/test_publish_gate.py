"""D1 publication gate: draft completion, human confirmation, publish, retire.

The positive flow is one synthetic SQLite source: discover three objects,
complete the draft into a multi-concept definition, let the agent prepare a
candidate, refuse an agent-side confirmation, publish through the local web
channel, then map a new task onto the published ontology.  The negative cases
pin every check the gate must enforce.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dataagent_contracts.core import CapabilityStatus
from dataagent_contracts.ontology import MappingSpec, OntologyRevision
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app
from dataagent_workbench.service_tools import invoke


CAPABILITIES = Path(__file__).resolve().parents[2]
DATA = CAPABILITIES / 'dataagent-data'
SEED = CAPABILITIES / 'dataagent-scenarios/fixtures/intake/sales-discovery.sql'


# --------------------------------------------------------------------- setup
def workbench(tmp_path, *, extra_sql=''):
    with sqlite3.connect(tmp_path / 'sales.db') as connection:
        connection.executescript(SEED.read_text())
        if extra_sql:
            connection.executescript(extra_sql)
    wb = Workbench(tmp_path, layer_client=LayerClient(DATA))
    session_id = invoke(wb, 'intake_start', {
        'goal': '从陌生数据库识别销售单据的业务对象',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'sales.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    return wb, session_id, request


def draft(wb, session_id, request, entities, relationships=()):
    return invoke(wb, 'ontology_discovery_propose', {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'proposal': {'source_revision': request['source_revision'],
                     'entities': entities,
                     'relationships': list(relationships)},
    }).data


def full_draft(wb, session_id, request):
    declared, = [link for link in request['catalog']['relationships']
                 if link['origin'] == 'declared']
    inferred, = [link for link in request['catalog']['relationships']
                 if link['origin'] == 'sample_supported']
    return draft(wb, session_id, request, [
        {'table': 'doc_hdr', 'name': 'SalesOrder', 'grain': '每个账簿内的一份销售单',
         'identity': ['book', 'doc_no']},
        {'table': 'doc_line', 'name': 'SalesOrderLine', 'grain': '销售单的一条明细',
         'identity': ['book', 'doc_no', 'seq'],
         'properties': [{'column': 'cents', 'name': 'amountInCents'}]},
        {'table': 'party', 'name': 'Customer', 'grain': '每个客户一行',
         'identity': ['party_no'],
         'properties': [{'column': 'nm', 'name': 'name'}]},
    ], [
        {'evidence_id': declared['id'], 'name': 'belongsToOrder'},
        {'evidence_id': inferred['id'], 'name': 'orderedBy'},
    ])


def customer_completion(wb, session_id, current_draft, *, identity=('party_no',),
                        properties=None):
    """A minimal completion for a draft whose only entity is Customer."""
    if properties is None:
        properties = {
            'party_no': {'column': 'party_no', 'value_type': 'string', 'required': True},
            'name': {'column': 'nm', 'value_type': 'string'},
        }
    return {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': current_draft['ref'],
        'ontology_id': 'customer-model',
        'concepts': [{'entity': 'Customer', 'properties': properties,
                      'identity_fields': list(identity)}],
        'dispositions': [],
    }


def full_completion(wb, session_id, current_draft):
    relations = {link['name']: link for link in current_draft['relationships']}
    return {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': current_draft['ref'],
        'ontology_id': 'sales-model',
        'title': '销售单据模型',
        'concepts': [
            {'entity': 'SalesOrder', 'properties': {
                'book': {'column': 'book', 'value_type': 'string', 'required': True},
                'doc_no': {'column': 'doc_no', 'value_type': 'integer', 'required': True},
            }, 'identity_fields': ['book', 'doc_no']},
            {'entity': 'SalesOrderLine', 'properties': {
                'book': {'column': 'book', 'value_type': 'string', 'required': True},
                'doc_no': {'column': 'doc_no', 'value_type': 'integer', 'required': True},
                'seq': {'column': 'seq', 'value_type': 'integer', 'required': True},
                'amountInCents': {'column': 'cents', 'value_type': 'decimal',
                                  'required': True},
            }, 'identity_fields': ['book', 'doc_no', 'seq']},
            {'entity': 'Customer', 'properties': {
                'party_no': {'column': 'party_no', 'value_type': 'string',
                             'required': True},
                'name': {'column': 'nm', 'value_type': 'string'},
            }, 'identity_fields': ['party_no']},
        ],
        'relations': [
            {'evidence_id': relations['belongsToOrder']['id'], 'name': 'belongsToOrder',
             'subject_concept': 'SalesOrderLine', 'object_concept': 'SalesOrder',
             'roles': ['line', 'order']},
            {'evidence_id': relations['orderedBy']['id'], 'name': 'orderedBy',
             'subject_concept': 'SalesOrder', 'object_concept': 'Customer',
             'roles': ['order', 'customer']},
        ],
        'dispositions': [],
    }


def prepare(wb, completion):
    return invoke(wb, 'ontology_publish_prepare', completion)


def client(wb):
    return TestClient(create_app(wb), headers={'x-dataagent-token': wb.token})


def confirmation(candidate, *, revision=None, **overrides):
    payload = {
        'candidate_ref': candidate['candidate_ref'],
        'draft_ref': candidate['draft_ref'],
        'source_snapshot': candidate['source_snapshot'],
        'definition_digest': candidate['definition_digest'],
        'expected_revision': revision or candidate['session_revision'],
        'confirmed': True,
        'reason': '展示给用户后的人工确认',
    }
    payload.update(overrides)
    return payload


def publish(wb, session_id, candidate):
    return client(wb).post(f'/api/sessions/{session_id}/publish/confirm',
                           json=confirmation(candidate))


def start_mapping(wb, sources, target=None, goal='接入销售数据'):
    arguments = {'goal': goal, 'sources': sources}
    if target is not None:
        arguments['target'] = target
    result = invoke(wb, 'intake_start', arguments)
    session_id = result.data['session_id']
    return session_id, invoke(wb, 'intake_advance', {'session_id': session_id}).data


# ------------------------------------------------------------------ positive
def test_discovery_publish_then_new_task_maps_to_the_new_ontology(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    candidate = prepare(wb, full_completion(wb, session_id, current)).data

    assert candidate['state'] == 'awaiting_human_confirmation'
    assert candidate['concept_names'] == ['SalesOrder', 'SalesOrderLine', 'Customer']
    assert candidate['default_concept'] == 'SalesOrder'
    assert set(candidate['relations']) == {'belongsToOrder', 'orderedBy'}
    assert candidate['definition_digest'] == candidate['definition_digest'].strip()

    # The agent-side tool can prepare, but never confirm.
    refusal = invoke(wb, 'ontology_publish_confirm',
                     {**confirmation(candidate), 'session_id': session_id})
    assert refusal.status == CapabilityStatus.needs_input
    assert refusal.issues[0].code == 'ontology.human_confirmation_required'
    assert wb.store.current('ontology', 'sales-model', scope=wb.scope) is None

    response = publish(wb, session_id, candidate)
    assert response.status_code == 200, response.json()
    published = response.json()
    assert published['ontology_id'] == 'sales-model'
    assert published['ontology_revision'] == '1'
    assert published['confirmed_by'] == wb.subject

    definition = OntologyRevision.model_validate(
        wb.store.current('ontology', 'sales-model', scope=wb.scope)['body'])
    assert definition.revision == '1'
    assert set(definition.concepts) == {'SalesOrder', 'SalesOrderLine', 'Customer'}
    assert definition.relations['belongsToOrder'].subject_concept == 'SalesOrderLine'
    assert definition.relations['belongsToOrder'].object_concept == 'SalesOrder'
    assert definition.relations['belongsToOrder'].roles == ['line', 'order']
    assert definition.relations['orderedBy'].subject_concept == 'SalesOrder'

    registry = client(wb).get('/api/ontologies').json()
    entries = {item['id']: item for item in registry['ontologies']}
    assert entries['sales-model']['origin'] == 'discovery'
    assert entries['sales-model']['state'] == 'active'
    assert entries['sales-model']['is_default'] is True
    assert registry['default_ontology'] == 'sales-model'
    assert {item['id'] for item in registry['ontologies']} == {'procurement', 'sales-model'}

    audit, = wb.store.query('ontology_publication', wb.scope)
    assert audit['body']['action'] == 'publish'
    assert audit['body']['draft_ref'] == current['ref']
    assert audit['body']['source_snapshot'] == candidate['source_snapshot']
    assert audit['body']['subject_ref'] == wb.subject

    # A new task without a target defaults to the published ontology's first
    # concept and can map a CSV onto it.
    (tmp_path / 'orders.csv').write_text('book,doc_no\nSALE,1001\nSALE,1002\n')
    new_session, inference = start_mapping(wb, [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
    ])
    assert inference['allowed_target']['ontology_id'] == 'sales-model'
    assert inference['allowed_target']['concept'] == 'SalesOrder'
    mapping = MappingSpec(id='orders', revision='1', ontology_revision='sales-model@1',
        concept='SalesOrder',
        source_fingerprint=inference['sources'][0]['structure_fingerprint'],
        bindings={'book': {'source_field': 'book'},
                  'doc_no': {'source_field': 'doc_no', 'transform': 'integer'}})
    preview = wb.intake.submit_proposal(new_session, mapping,
        wb.sessions.get(new_session, wb.ctx).revision, wb.ctx)
    assert [instance.entity_type for instance in preview.instances] == [
        'SalesOrder', 'SalesOrder']
    assert [dict(instance.values) for instance in preview.instances] == [
        {'book': 'SALE', 'doc_no': 1001}, {'book': 'SALE', 'doc_no': 1002}]
    assert preview.issues == []

    # intake_start may also name the published ontology explicitly.
    explicit, explicit_request = start_mapping(wb, [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
    ], target={'ontology_id': 'sales-model', 'concept': 'Customer'})
    assert explicit_request['allowed_target']['ontology_id'] == 'sales-model'
    assert explicit_request['allowed_target']['entity_type'] == 'Customer'
    assert explicit_request['allowed_target']['concept'] == 'Customer'


def test_identity_type_and_required_values_must_be_satisfiable(tmp_path):
    # A column with NULL/blank values cannot be an identity and cannot be a
    # required property; a text affinity cannot satisfy a date property.
    wb, session_id, request = workbench(tmp_path, extra_sql="""
        ALTER TABLE party ADD COLUMN region TEXT;
        UPDATE party SET region='East' WHERE party_no='P-1';
    """)
    current = draft(wb, session_id, request, [
        {'table': 'party', 'name': 'Customer', 'grain': '每个客户一行',
         'identity': ['party_no']},
    ])
    null_identity = customer_completion(wb, session_id, current,
        identity=('region',),
        properties={'region': {'column': 'region', 'value_type': 'string'}})
    with pytest.raises(ValueError, match='identity field'):
        prepare(wb, null_identity)

    required_blank = customer_completion(wb, session_id, current,
        properties={'party_no': {'column': 'party_no', 'value_type': 'string',
                                 'required': True},
                    'region': {'column': 'region', 'value_type': 'string',
                               'required': True}})
    with pytest.raises(ValueError, match='required property'):
        prepare(wb, required_blank)

    order = draft(wb, session_id, request, [
        {'table': 'doc_hdr', 'name': 'SalesOrder', 'grain': '每份销售单',
         'identity': ['book', 'doc_no']},
    ])
    wrong_type = {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': order['ref'], 'ontology_id': 'order-model',
        'concepts': [{'entity': 'SalesOrder', 'properties': {
            'book': {'column': 'book', 'value_type': 'string', 'required': True},
            'doc_no': {'column': 'doc_no', 'value_type': 'date'},
        }, 'identity_fields': ['book', 'doc_no']}],
        'dispositions': [],
    }
    with pytest.raises(ValueError, match='cannot be satisfied'):
        prepare(wb, wrong_type)


def test_identity_must_be_unique_in_the_observed_sample(tmp_path):
    wb, session_id, request = workbench(tmp_path, extra_sql="""
        INSERT INTO party VALUES ('P-3', 'Acme');
    """)
    current = draft(wb, session_id, request, [
        {'table': 'party', 'name': 'Customer', 'grain': '每个客户一行',
         'identity': ['party_no']},
    ])
    completion = customer_completion(wb, session_id, current,
        identity=('name',),
        properties={'name': {'column': 'nm', 'value_type': 'string',
                             'required': True}})
    with pytest.raises(ValueError, match='not unique'):
        prepare(wb, completion)


def test_identity_uniqueness_uses_bound_columns_not_property_names(tmp_path):
    """A property named seq may bind a non-unique cents column; reject it.

    Comparing property names (book, doc_no, seq) with observed key columns
    would accept this completion.  The extra row repeats cents=500, so the
    bound columns (book, doc_no, cents) are not unique.
    """
    wb, session_id, request = workbench(tmp_path, extra_sql="""
        INSERT INTO doc_line VALUES ('SALE', 1001, 3, 500);
    """)
    current = draft(wb, session_id, request, [
        {'table': 'doc_line', 'name': 'SalesOrderLine', 'grain': '销售单的一条明细',
         'identity': ['book', 'doc_no', 'seq']},
    ])
    completion = {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': current['ref'], 'ontology_id': 'line-model',
        'concepts': [{'entity': 'SalesOrderLine', 'properties': {
            'book': {'column': 'book', 'value_type': 'string', 'required': True},
            'doc_no': {'column': 'doc_no', 'value_type': 'integer', 'required': True},
            'seq': {'column': 'cents', 'value_type': 'integer', 'required': True},
        }, 'identity_fields': ['book', 'doc_no', 'seq']}],
        'dispositions': [],
    }
    with pytest.raises(ValueError, match='identity columns') as caught:
        prepare(wb, completion)
    assert 'cents' in str(caught.value)


def test_fabricated_entities_properties_and_relations_are_rejected(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    completion = full_completion(wb, session_id, current)

    fabricated_property = {**completion,
        'concepts': [dict(completion['concepts'][0],
            properties={**completion['concepts'][0]['properties'],
                        'secret': {'column': 'secret', 'value_type': 'string'}}),
            *completion['concepts'][1:]]}
    with pytest.raises(ValueError, match='unobserved column'):
        prepare(wb, fabricated_property)

    fabricated_entity = {**completion,
        'concepts': [*completion['concepts'][:1],
            {**completion['concepts'][1], 'entity': 'Invented'}]}
    with pytest.raises(ValueError, match='outside the draft'):
        prepare(wb, fabricated_entity)

    fabricated_relation = {**completion,
        'relations': [{**completion['relations'][0], 'evidence_id': 'invented'},
                      *completion['relations'][1:]]}
    with pytest.raises(ValueError, match='no selected evidence'):
        prepare(wb, fabricated_relation)

    reversed_relation = {**completion,
        'relations': [{**completion['relations'][0],
                       'subject_concept': 'SalesOrder',
                       'object_concept': 'SalesOrderLine'},
                      *completion['relations'][1:]]}
    with pytest.raises(ValueError, match='subject must be the evidence source'):
        prepare(wb, reversed_relation)


def test_sampled_coverage_must_be_accepted_before_publication(tmp_path):
    wb, _, _ = workbench(tmp_path)
    (tmp_path / 'large.csv').write_text(
        'id,value\n' + ''.join(f'{index},{index * 2}\n' for index in range(250)))
    session_id = invoke(wb, 'intake_start', {
        'goal': '发现采样来源', 'mode': 'ontology_discovery',
        'sources': [{'source_id': 'large', 'kind': 'file', 'locator_ref': 'large.csv'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    assert request['coverage'] == 'sampled'
    current = draft(wb, session_id, request, [
        {'table': 'large', 'name': 'Large', 'grain': '每行一条观测',
         'identity': ['id']},
    ])
    completion = {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': current['ref'], 'ontology_id': 'large-model',
        'concepts': [{'entity': 'Large', 'properties': {
            'id': {'column': 'id', 'value_type': 'string', 'required': True},
            'value': {'column': 'value', 'value_type': 'string'},
        }, 'identity_fields': ['id']}],
        'dispositions': [],
    }
    with pytest.raises(ValueError, match='coverage:sampled'):
        prepare(wb, completion)
    completion['dispositions'] = [{'kind': 'coverage', 'ref': 'sampled',
                                   'action': 'accept', 'reason': '抽样已够核对'}]
    assert prepare(wb, completion).data['state'] == 'awaiting_human_confirmation'


def test_unresolved_items_and_coverage_gaps_must_be_disposed(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    current = draft(wb, session_id, request, [
        {'table': 'party', 'name': 'Customer', 'grain': '每个客户一行',
         'identity': ['party_no']},
    ])
    assert current['unresolved_tables'] == ['doc_hdr', 'doc_line']
    assert current['unresolved_relationships']

    completion = customer_completion(wb, session_id, current)
    with pytest.raises(ValueError, match='must be excluded or accepted'):
        prepare(wb, completion)

    completion['dispositions'] = [
        {'kind': 'unresolved_table', 'ref': table, 'action': 'exclude',
         'reason': '本次不建模该表'} for table in current['unresolved_tables']]
    completion['dispositions'] += [
        {'kind': 'unresolved_relationship', 'ref': link['id'], 'action': 'exclude',
         'reason': '端点未建模'} for link in current['unresolved_relationships']]
    completion['dispositions'] += [
        {'kind': 'coverage_gap', 'ref': gap['ref'], 'action': 'accept',
         'reason': '采样缺口已核对'} for gap in current.get('gaps') or []]
    if current.get('coverage') != 'full':
        completion['dispositions'].append(
            {'kind': 'coverage', 'ref': current['coverage'], 'action': 'accept',
             'reason': '样本覆盖已接受'})
    result = prepare(wb, completion)
    assert result.data['state'] == 'awaiting_human_confirmation'


def test_stale_task_draft_and_source_confirmations_are_rejected(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    candidate = prepare(wb, full_completion(wb, session_id, current)).data

    # Change the draft and task revision, then try the old exact confirmation.
    replacement = full_draft(wb, session_id, request)
    stale = publish(wb, session_id, candidate)
    assert stale.status_code == 409

    newer = client(wb).post(f'/api/sessions/{session_id}/publish/confirm',
        json=confirmation(candidate,
            revision=wb.sessions.get(session_id, wb.ctx).revision))
    assert newer.status_code == 409

    # A source change after preparation is refused with a re-discover hint.
    candidate2 = prepare(wb, full_completion(wb, session_id, replacement)).data
    with sqlite3.connect(tmp_path / 'sales.db') as connection:
        connection.execute("INSERT INTO party VALUES ('P-3', 'Cedar')")
    source_changed = publish(wb, session_id, candidate2)
    assert source_changed.status_code == 422
    assert 'discover again' in source_changed.json()['detail']


def test_duplicate_confirmation_and_republishing_are_rejected(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    candidate = prepare(wb, full_completion(wb, session_id, current)).data
    assert publish(wb, session_id, candidate).status_code == 200

    duplicate = publish(wb, session_id, candidate)
    assert duplicate.status_code == 409
    assert 'already published' in duplicate.json()['detail']

    # M1 publishes once; modifying an existing definition is out of scope.
    with pytest.raises(ValueError, match='already registered'):
        prepare(wb, full_completion(wb, session_id, current))


def test_retirement_keeps_old_tasks_and_clears_the_new_task_default(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    candidate = prepare(wb, full_completion(wb, session_id, current)).data
    assert publish(wb, session_id, candidate).status_code == 200

    (tmp_path / 'orders.csv').write_text('book,doc_no\nSALE,1001\nSALE,1002\n')
    old_session, old_request = start_mapping(wb, [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
    ], target={'ontology_id': 'sales-model', 'concept': 'SalesOrder'})
    assert old_request['allowed_target']['ontology_id'] == 'sales-model'

    registry = client(wb).get('/api/ontologies').json()
    entry, = [item for item in registry['ontologies'] if item['id'] == 'sales-model']
    retired = client(wb).post('/api/ontologies/sales-model/retire', json={
        'reason': '并入新的销售模型修订', 'confirmed': True,
        'expected_revision': entry['registry_revision']})
    assert retired.status_code == 200, retired.json()
    assert retired.json()['state'] == 'retired'

    after = client(wb).get('/api/ontologies').json()
    entries = {item['id']: item for item in after['ontologies']}
    assert entries['sales-model']['state'] == 'retired'
    assert entries['sales-model']['retire_reason'] == '并入新的销售模型修订'
    assert after['default_ontology'] == 'procurement'

    # The old revision and the task pinned to it keep working.
    assert wb.store.get('ontology', 'sales-model', '1', scope=wb.scope) is not None
    mapping = MappingSpec(id='orders', revision='1', ontology_revision='sales-model@1',
        concept='SalesOrder',
        source_fingerprint=old_request['sources'][0]['structure_fingerprint'],
        bindings={'book': {'source_field': 'book'},
                  'doc_no': {'source_field': 'doc_no', 'transform': 'integer'}})
    preview = wb.intake.submit_proposal(old_session, mapping,
        wb.sessions.get(old_session, wb.ctx).revision, wb.ctx)
    assert len(preview.instances) == 2
    applied = invoke(wb, 'mapping_apply', {
        'session_id': old_session,
        'expected_revision': wb.sessions.get(old_session, wb.ctx).revision,
        'decision': {'preview_ref': preview.id + '@' + preview.revision,
                     'target_scope': 'mapping', 'decision': 'save'},
    })
    assert applied.status == CapabilityStatus.ok
    assert wb.store.query('release', wb.scope)

    # New tasks no longer default to the retired definition; the fallback
    # builtin revision is written into the task target, not resolved later.
    new_session, new_request = start_mapping(wb, [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
    ])
    assert new_request['allowed_target']['ontology_id'] == 'procurement'
    assert new_request['allowed_target']['concept'] == 'PurchaseDocument'
    pinned = wb.sessions.get(new_session, wb.ctx).extensions['dataagent.mapping_target']
    assert pinned == {'ontology_id': 'procurement', 'revision': '1',
                      'concept': 'PurchaseDocument'}

    # A retired definition stays readable for old tasks but cannot be chosen
    # explicitly by a new one.
    with pytest.raises(ValueError, match='retired for new tasks'):
        start_mapping(wb, [
            {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
        ], target={'ontology_id': 'sales-model', 'concept': 'SalesOrder'})

    # Retiring twice is refused, and the reason is mandatory.
    again = client(wb).post('/api/ontologies/sales-model/retire', json={
        'reason': '重复停用', 'confirmed': True})
    assert again.status_code == 422
    missing_reason = client(wb).post('/api/ontologies/procurement/retire', json={
        'reason': '', 'confirmed': True})
    assert missing_reason.status_code == 422


def test_sqlite_change_between_probe_and_prepare_is_rejected(tmp_path):
    """The source is pinned at probe time, not when a candidate is prepared."""
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    with sqlite3.connect(tmp_path / 'sales.db') as connection:
        connection.execute("INSERT INTO party VALUES ('P-3', 'Cedar')")
    with pytest.raises(ValueError, match='source changed since it was observed'):
        prepare(wb, full_completion(wb, session_id, current))


def wal_workbench(tmp_path):
    """Probe with a writer connection open so later writes stay in the WAL."""
    keeper = sqlite3.connect(tmp_path / 'sales.db')
    keeper.executescript(SEED.read_text())
    keeper.execute('PRAGMA journal_mode=WAL')
    keeper.execute('PRAGMA wal_autocheckpoint=0')
    keeper.commit()
    wb = Workbench(tmp_path, layer_client=LayerClient(DATA))
    session_id = invoke(wb, 'intake_start', {
        'goal': '从陌生数据库识别销售单据的业务对象',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'sales.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    return wb, session_id, request, keeper


def test_wal_only_change_between_probe_and_prepare_is_rejected(tmp_path):
    """A change parked in -wal is part of the observed source version."""
    wb, session_id, request, keeper = wal_workbench(tmp_path)
    try:
        current = full_draft(wb, session_id, request)
        database = tmp_path / 'sales.db'
        before = database.read_bytes()
        keeper.execute("INSERT INTO party VALUES ('P-3', 'Cedar')")
        keeper.commit()
        assert database.read_bytes() == before
        assert (tmp_path / 'sales.db-wal').stat().st_size > 0
        with pytest.raises(ValueError, match='source changed since it was observed'):
            prepare(wb, full_completion(wb, session_id, current))
    finally:
        keeper.close()


def empty_workbench(tmp_path):
    with sqlite3.connect(tmp_path / 'empty.db') as connection:
        connection.executescript(
            'CREATE TABLE empty_orders (order_no TEXT PRIMARY KEY, amount INTEGER);')
    wb = Workbench(tmp_path, layer_client=LayerClient(DATA))
    session_id = invoke(wb, 'intake_start', {
        'goal': '从一个空表发现业务对象',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'empty.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    return wb, session_id, request


def test_empty_table_concept_has_no_publishable_evidence(tmp_path):
    """An empty table still has columns and a declared key, but no sample."""
    wb, session_id, request = empty_workbench(tmp_path)
    current = draft(wb, session_id, request, [
        {'table': 'empty_orders', 'name': 'EmptyOrder', 'grain': '每行一份订单',
         'identity': ['order_no']},
    ])
    completion = {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': current['ref'], 'ontology_id': 'empty-model',
        'concepts': [{'entity': 'EmptyOrder', 'properties': {
            'order_no': {'column': 'order_no', 'value_type': 'string',
                         'required': True},
            'amount': {'column': 'amount', 'value_type': 'integer'},
        }, 'identity_fields': ['order_no']}],
        'dispositions': [],
    }
    with pytest.raises(ValueError, match='no observed sample rows'):
        prepare(wb, completion)


def test_property_with_no_observed_value_has_no_evidence(tmp_path):
    """A column that is null in every sampled row has no anchor to publish."""
    with sqlite3.connect(tmp_path / 'nullable.db') as connection:
        connection.executescript(
            'CREATE TABLE orders (order_no TEXT PRIMARY KEY, note TEXT);\n'
            "INSERT INTO orders VALUES ('O-1', NULL);")
    wb = Workbench(tmp_path, layer_client=LayerClient(DATA))
    session_id = invoke(wb, 'intake_start', {
        'goal': '从含空值的表发现业务对象',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'nullable.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    current = draft(wb, session_id, request, [
        {'table': 'orders', 'name': 'Order', 'grain': '每行一份订单',
         'identity': ['order_no']},
    ])
    completion = {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': current['ref'], 'ontology_id': 'nullable-model',
        'concepts': [{'entity': 'Order', 'properties': {
            'order_no': {'column': 'order_no', 'value_type': 'string',
                         'required': True},
            'note': {'column': 'note', 'value_type': 'string'},
        }, 'identity_fields': ['order_no']}],
        'dispositions': [],
    }
    with pytest.raises(ValueError, match='no observed value'):
        prepare(wb, completion)


def test_probe_source_version_survives_a_workbench_restart(tmp_path):
    """The pin lives in the workspace store, not in this process's memory."""
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    restarted = Workbench(tmp_path, layer_client=LayerClient(DATA))
    prepared = prepare(restarted, full_completion(restarted, session_id, current))
    assert prepared.data['state'] == 'awaiting_human_confirmation'


class FlakySecondaryClient:
    """Fail the secondary source once, then delegate to the real data layer."""

    def __init__(self, client):
        self.client = client
        self.failed = False

    def probe(self, selection, *args, **kwargs):
        if selection.source_id == 'secondary' and not self.failed:
            self.failed = True
            raise ValueError('transient probe failure')
        return self.client.probe(selection, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.client, name)


class UnreadablePrimaryClient:
    """Make the primary file unreadable right after its probe returns."""

    def __init__(self, client, path):
        self.client = client
        self.path = Path(path)
        self.hidden = None
        self.secondary_failed = False

    def probe(self, selection, *args, **kwargs):
        if selection.source_id == 'secondary' and not self.secondary_failed:
            self.secondary_failed = True
            raise ValueError('transient probe failure')
        profile = self.client.probe(selection, *args, **kwargs)
        if selection.source_id == 'primary' and self.hidden is None:
            self.hidden = self.path.with_suffix('.hidden')
            self.path.rename(self.hidden)
        return profile

    def __getattr__(self, name):
        return getattr(self.client, name)


class WALMutatingSecondaryClient:
    """Edit the primary WAL on the secondary's first probe, then fail.

    This is the same-advance window: the primary probe has returned but the
    advance has not, so the secondary can still rewrite the primary.
    """

    def __init__(self, client, keeper):
        self.client = client
        self.keeper = keeper
        self.failed = False

    def probe(self, selection, *args, **kwargs):
        if selection.source_id == 'secondary' and not self.failed:
            self.failed = True
            self.keeper.execute("INSERT INTO party VALUES ('P-3', 'Cedar')")
            self.keeper.commit()
            raise ValueError('secondary failed after editing primary')
        return self.client.probe(selection, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.client, name)


def two_source_wal_workbench(tmp_path, wrap_client=None):
    """Primary is observed; secondary must be retried once."""
    keeper = sqlite3.connect(tmp_path / 'sales.db')
    keeper.executescript(SEED.read_text())
    keeper.execute('PRAGMA journal_mode=WAL')
    keeper.execute('PRAGMA wal_autocheckpoint=0')
    keeper.commit()
    with sqlite3.connect(tmp_path / 'retry.db') as connection:
        connection.executescript(
            'CREATE TABLE retry_marker (code TEXT PRIMARY KEY, label TEXT);\n'
            "INSERT INTO retry_marker VALUES ('X-1', 'retry');")
    client = LayerClient(DATA)
    if wrap_client is None:
        client = FlakySecondaryClient(client)
    else:
        client = wrap_client(client, keeper)
    wb = Workbench(tmp_path, layer_client=client)
    session_id = invoke(wb, 'intake_start', {
        'goal': '两个来源中一个需要重试',
        'mode': 'ontology_discovery',
        'sources': [
            {'source_id': 'primary', 'kind': 'sqlite', 'locator_ref': 'sales.db'},
            {'source_id': 'secondary', 'kind': 'sqlite', 'locator_ref': 'retry.db'},
        ],
    }).data['session_id']
    first = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    return wb, session_id, first, keeper


def test_retrying_secondary_does_not_refresh_the_primary_source_version(tmp_path):
    """Per-source pins: retrying B must not bless a WAL-only edit of A."""
    wb, session_id, first, keeper = two_source_wal_workbench(tmp_path)
    try:
        assert first['next_actions'] == ['retry_probe']
        session = wb.sessions.get(session_id, wb.ctx)
        primary_ref = session.selected_versions['profile:primary']
        secondary_ref = session.selected_versions['profile:secondary']
        record = wb.store.current('source_version', session_id, scope=wb.scope)
        primary_record = record['body']['sources']['primary']

        database = tmp_path / 'sales.db'
        before = database.read_bytes()
        keeper.execute("INSERT INTO party VALUES ('P-3', 'Cedar')")
        keeper.commit()
        assert database.read_bytes() == before
        assert (tmp_path / 'sales.db-wal').stat().st_size > 0

        request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
        session = wb.sessions.get(session_id, wb.ctx)
        # Only the retried source gets a new observation; A keeps its old pin.
        assert session.selected_versions['profile:primary'] == primary_ref
        assert session.selected_versions['profile:secondary'] != secondary_ref
        record = wb.store.current('source_version', session_id, scope=wb.scope)
        assert record['body']['sources']['primary'] == primary_record

        completion = two_source_completion(wb, session_id, request)
        with pytest.raises(ValueError, match='source changed since it was observed'):
            prepare(wb, completion)
    finally:
        keeper.close()


def two_source_completion(wb, session_id, request):
    declared, = [link for link in request['catalog']['relationships']
                 if link['origin'] == 'declared']
    inferred, = [link for link in request['catalog']['relationships']
                 if link['origin'] == 'sample_supported']
    current = draft(wb, session_id, request, [
        {'table': 'doc_hdr', 'name': 'SalesOrder', 'grain': '每个账簿内的一份销售单',
         'identity': ['book', 'doc_no']},
        {'table': 'doc_line', 'name': 'SalesOrderLine', 'grain': '销售单的一条明细',
         'identity': ['book', 'doc_no', 'seq'],
         'properties': [{'column': 'cents', 'name': 'amountInCents'}]},
        {'table': 'party', 'name': 'Customer', 'grain': '每个客户一行',
         'identity': ['party_no'],
         'properties': [{'column': 'nm', 'name': 'name'}]},
        {'table': 'retry_marker', 'name': 'RetryMarker', 'grain': '每行一条重试标记',
         'identity': ['code']},
    ], [
        {'evidence_id': declared['id'], 'name': 'belongsToOrder'},
        {'evidence_id': inferred['id'], 'name': 'orderedBy'},
    ])
    completion = full_completion(wb, session_id, current)
    completion['concepts'].append({
        'entity': 'RetryMarker', 'properties': {
            'code': {'column': 'code', 'value_type': 'string', 'required': True},
            'label': {'column': 'label', 'value_type': 'string'},
        }, 'identity_fields': ['code'],
    })
    return completion


def test_wal_edit_during_secondary_probe_does_not_refresh_primary_version(tmp_path):
    """The primary pin must be captured before the next source probes."""
    wb, session_id, first, keeper = two_source_wal_workbench(
        tmp_path, wrap_client=WALMutatingSecondaryClient)
    try:
        assert first['next_actions'] == ['retry_probe']
        session = wb.sessions.get(session_id, wb.ctx)
        primary_ref = session.selected_versions['profile:primary']
        record = wb.store.current('source_version', session_id, scope=wb.scope)
        primary_record = record['body']['sources']['primary']
        # The capture is the WAL as it was when primary's probe returned; the
        # secondary edited it afterwards while the advance was still running.
        current_wal = 'sha256:' + hashlib.sha256(
            (tmp_path / 'sales.db-wal').read_bytes()).hexdigest()
        assert primary_record['state']['files']['wal'] != current_wal

        request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
        session = wb.sessions.get(session_id, wb.ctx)
        assert session.selected_versions['profile:primary'] == primary_ref
        record = wb.store.current('source_version', session_id, scope=wb.scope)
        assert record['body']['sources']['primary'] == primary_record
        with pytest.raises(ValueError, match='source changed since it was observed'):
            prepare(wb, two_source_completion(wb, session_id, request))
    finally:
        keeper.close()


def test_unreadable_primary_stays_blocked_after_unrelated_retry(tmp_path):
    """An unreadable pin must not be re-fixed just because another source retries."""
    holder = {}

    def wrap(client, keeper):
        holder['client'] = UnreadablePrimaryClient(client, tmp_path / 'sales.db')
        return holder['client']

    wb, session_id, first, keeper = two_source_wal_workbench(
        tmp_path, wrap_client=wrap)
    try:
        assert first['next_actions'] == ['retry_probe']
        record = wb.store.current('source_version', session_id, scope=wb.scope)
        assert record['body']['sources']['primary']['state'].get('unreadable')

        # The source becomes readable again, but it has not been re-probed.
        holder['client'].hidden.rename(holder['client'].path)
        request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
        record = wb.store.current('source_version', session_id, scope=wb.scope)
        assert record['body']['sources']['primary']['state'].get('unreadable')
        with pytest.raises(ValueError, match='source observation version is missing'):
            prepare(wb, two_source_completion(wb, session_id, request))
    finally:
        keeper.close()
