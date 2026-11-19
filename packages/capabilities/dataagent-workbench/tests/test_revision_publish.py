"""Publishing revision 2..n of an already published discovery ontology.

One positive chain publishes revision 1 from a discovery draft, opens a second
discovery task whose revision target is that ontology, completes the same
concepts with one property's value type changed, prepares the revision
candidate, confirms it through the local web channel and then proves that a
new task maps onto revision 2 while a task pinned before the revision still
maps onto revision 1.

The negative cases pin every gate the revision path must keep: the builtin
cannot be revised, a retired ontology cannot be revised, the completion must
name the revision target, a stale base revision loses against a concurrent
revision, the agent tool cannot confirm, and a destructive revision needs the
extra no-migration acknowledgement.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from dataagent_contracts.core import CapabilityStatus
from dataagent_contracts.intake import SourceSelection, WorkSpec
from dataagent_contracts.ontology import (MappingSpec, OntologyRevision,
                                          RelationDefinition)
from dataagent_ontology.revisions import definition_diff
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app
from dataagent_workbench.service_tools import invoke
from dataagent_workbench.tool_schema import Start
from test_intake_repairs import StubProbeClient, csv_profile, save_single


CAPABILITIES = Path(__file__).resolve().parents[2]
DATA = CAPABILITIES / 'dataagent-data'
SEED = CAPABILITIES / 'dataagent-scenarios/fixtures/intake/sales-discovery.sql'


# --------------------------------------------------------------------- setup
def workbench(tmp_path, *, revise_ontology_id=None):
    if not (tmp_path / 'sales.db').exists():
        with sqlite3.connect(tmp_path / 'sales.db') as connection:
            connection.executescript(SEED.read_text())
    wb = Workbench(tmp_path, layer_client=LayerClient(DATA))
    arguments = {
        'goal': '从陌生数据库识别销售单据的业务对象',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'sales.db'}],
    }
    if revise_ontology_id is not None:
        arguments['revise_ontology_id'] = revise_ontology_id
    session_id = invoke(wb, 'intake_start', arguments).data['session_id']
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


FULL_ENTITIES = [
    {'table': 'doc_hdr', 'name': 'SalesOrder', 'grain': '每个账簿内的一份销售单',
     'identity': ['book', 'doc_no']},
    {'table': 'doc_line', 'name': 'SalesOrderLine', 'grain': '销售单的一条明细',
     'identity': ['book', 'doc_no', 'seq'],
     'properties': [{'column': 'cents', 'name': 'amountInCents'}]},
    {'table': 'party', 'name': 'Customer', 'grain': '每个客户一行',
     'identity': ['party_no'],
     'properties': [{'column': 'nm', 'name': 'name'}]},
]


def full_draft(wb, session_id, request):
    declared, = [link for link in request['catalog']['relationships']
                 if link['origin'] == 'declared']
    inferred, = [link for link in request['catalog']['relationships']
                 if link['origin'] == 'sample_supported']
    return draft(wb, session_id, request, FULL_ENTITIES, [
        {'evidence_id': declared['id'], 'name': 'belongsToOrder'},
        {'evidence_id': inferred['id'], 'name': 'orderedBy'},
    ])


def completion(wb, session_id, current_draft, ontology_id='sales-model', *,
               doc_no_type='integer', include_customer_name=True,
               title='销售单据模型', day_type=None):
    relations = {link['name']: link for link in current_draft['relationships']}
    order_properties = {
        'book': {'column': 'book', 'value_type': 'string', 'required': True},
        'doc_no': {'column': 'doc_no', 'value_type': doc_no_type,
                   'required': True},
    }
    if day_type is not None:
        order_properties['day'] = {'column': 'day', 'value_type': day_type}
    customer_properties = {
        'party_no': {'column': 'party_no', 'value_type': 'string', 'required': True},
    }
    if include_customer_name:
        customer_properties['name'] = {'column': 'nm', 'value_type': 'string'}
    return {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'draft_ref': current_draft['ref'],
        'ontology_id': ontology_id,
        'title': title,
        'concepts': [
            {'entity': 'SalesOrder', 'properties': order_properties,
             'identity_fields': ['book', 'doc_no']},
            {'entity': 'SalesOrderLine', 'properties': {
                'book': {'column': 'book', 'value_type': 'string', 'required': True},
                'doc_no': {'column': 'doc_no', 'value_type': 'integer',
                           'required': True},
                'seq': {'column': 'seq', 'value_type': 'integer', 'required': True},
                'amountInCents': {'column': 'cents', 'value_type': 'decimal',
                                  'required': True},
            }, 'identity_fields': ['book', 'doc_no', 'seq']},
            {'entity': 'Customer', 'properties': customer_properties,
             'identity_fields': ['party_no']},
        ],
        'relations': [
            {'evidence_id': relations['belongsToOrder']['id'],
             'name': 'belongsToOrder', 'subject_concept': 'SalesOrderLine',
             'object_concept': 'SalesOrder', 'roles': ['line', 'order']},
            {'evidence_id': relations['orderedBy']['id'], 'name': 'orderedBy',
             'subject_concept': 'SalesOrder', 'object_concept': 'Customer',
             'roles': ['order', 'customer']},
        ],
        'dispositions': [],
    }


def client(wb):
    return TestClient(create_app(wb), headers={'x-dataagent-token': wb.token})


def confirmation(candidate, **overrides):
    payload = {
        'candidate_ref': candidate['candidate_ref'],
        'draft_ref': candidate['draft_ref'],
        'source_snapshot': candidate['source_snapshot'],
        'definition_digest': candidate['definition_digest'],
        'expected_revision': candidate['session_revision'],
        'confirmed': True,
        'reason': '展示给用户后的人工确认',
    }
    payload.update(overrides)
    return payload


def publish(wb, session_id, candidate, **overrides):
    return client(wb).post(f'/api/sessions/{session_id}/publish/confirm',
                           json=confirmation(candidate, **overrides))


def publish_initial(wb, session_id, request):
    current = full_draft(wb, session_id, request)
    candidate = invoke(wb, 'ontology_publish_prepare',
                       completion(wb, session_id, current)).data
    response = publish(wb, session_id, candidate)
    assert response.status_code == 200, response.json()
    return current, candidate, response.json()


def revision_candidate(wb, session_id, request, **kwargs):
    current = full_draft(wb, session_id, request)
    payload = completion(wb, session_id, current,
                         ontology_id='sales-model', **kwargs)
    candidate = invoke(wb, 'ontology_publish_prepare', payload).data
    return current, candidate


def csv_source(tmp_path):
    (tmp_path / 'orders.csv').write_text('book,doc_no\nSALE,1001\nSALE,1002\n')
    return [{'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'}]


def start_mapping(wb, sources, target=None):
    arguments = {'goal': '接入销售数据', 'sources': sources}
    if target is not None:
        arguments['target'] = target
    session_id = invoke(wb, 'intake_start', arguments).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    return session_id, request


def registry_entry(wb, ontology_id='sales-model'):
    registry = client(wb).get('/api/ontologies').json()
    return next(item for item in registry['ontologies']
                if item['id'] == ontology_id)


def save_sales_orders(wb, tmp_path, rows=None):
    """Release SalesOrder objects into revision 1 through a pinned task."""
    rows = rows or [{'book': 'SALE', 'doc_no': '1001'},
                    {'book': 'SALE', 'doc_no': '1002'}]
    (tmp_path / 'orders.csv').write_text(
        'book,doc_no\n' + '\n'.join(
            f"{row['book']},{row['doc_no']}" for row in rows) + '\n')
    wb.layer_client = StubProbeClient({'orders': csv_profile('orders', rows)})
    goal = WorkSpec(id='map', goal='接入销售数据',
                    acceptance_criteria=['来源可核对'],
                    authorization_ref=wb.authorization)
    started = wb.sessions.start(
        [SourceSelection(source_id='orders', kind='file',
                         locator_ref='orders.csv')], goal, wb.ctx,
        target={'ontology_id': 'sales-model', 'concept': 'SalesOrder'})
    mapping_session = wb.intake.advance(started.session_id, wb.ctx)
    mapping_source, = wb.intake.inference_request(
        mapping_session.id, wb.ctx)['sources']
    save_single(wb, mapping_session, MappingSpec(
        id='orders', revision='1', ontology_revision='sales-model@1',
        concept='SalesOrder',
        source_fingerprint=mapping_source['structure_fingerprint'],
        bindings={'book': {'source_field': 'book'},
                  'doc_no': {'source_field': 'doc_no',
                             'transform': 'integer'}}))
    wb.layer_client = LayerClient(DATA)


# ------------------------------------------------------------------ positive
def test_revision_publish_keeps_old_tasks_and_defaults_new_tasks_to_rev2(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    publish_initial(wb, session_id, request)

    # A task pinned to revision 1 before the revision must keep working.
    old_session, old_request = start_mapping(wb, csv_source(tmp_path),
        target={'ontology_id': 'sales-model', 'concept': 'SalesOrder'})
    assert old_request['allowed_target']['ontology_revision'] == 'sales-model@1'
    assert old_request['allowed_target']['properties']['doc_no']['value_type'] \
        == 'integer'

    revision_wb, revision_session, revision_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    current, candidate = revision_candidate(
        revision_wb, revision_session, revision_request, doc_no_type='string',
        title='销售单据模型·修订二')

    assert candidate['ontology_id'] == 'sales-model'
    assert candidate['title'] == '销售单据模型·修订二'
    assert candidate['previous_revision'] == '1'
    assert candidate['ontology_revision'] == '2'
    assert candidate['destructive'] is False
    assert candidate['requires_no_migration_ack'] is False
    diff = candidate['revision_diff']
    assert diff['previous_revision'] == '1'
    assert diff['revision'] == '2'
    assert diff['retyped_properties'] == [
        {'concept': 'SalesOrder', 'property': 'doc_no',
         'before': 'integer', 'after': 'string'}]
    assert diff['removed_properties'] == []
    assert any('SalesOrder.doc_no 值类型 integer → string' in line
               for line in diff['summary'])

    # The agent-side tool still only reports that a human must confirm.
    refusal = invoke(revision_wb, 'ontology_publish_confirm',
                     {**confirmation(candidate), 'session_id': revision_session})
    assert refusal.status == CapabilityStatus.needs_input
    assert refusal.issues[0].code == 'ontology.human_confirmation_required'
    assert wb.store.current('ontology', 'sales-model',
                            scope=wb.scope)['body']['revision'] == '1'

    response = publish(revision_wb, revision_session, candidate)
    assert response.status_code == 200, response.json()
    published = response.json()
    assert published['state'] == 'published'
    assert published['ontology_revision'] == '2'
    assert published['previous_revision'] == '1'
    assert published['revision_diff']['retyped_properties']

    # Both revisions stay registered; the registry names the new one and
    # carries the visible history; the pointer moved to it.
    definitions = {
        revision: wb.store.get('ontology', 'sales-model', revision,
                               scope=wb.scope)
        for revision in ('1', '2')}
    assert definitions['1'] is not None and definitions['2'] is not None
    assert OntologyRevision.model_validate(
        definitions['1']['body']).concepts['SalesOrder'].properties[
            'doc_no'].value_type == 'integer'
    second = OntologyRevision.model_validate(definitions['2']['body'])
    assert second.revision == '2'
    assert second.concepts['SalesOrder'].properties['doc_no'].value_type == 'string'

    entry = registry_entry(wb)
    assert entry['ontology_revision'] == '2'
    assert entry['title'] == candidate['title']
    assert [item['revision'] for item in entry['revisions']] == ['1', '2']
    assert entry['revisions'][1]['previous_revision'] == '1'
    assert entry['revisions'][1]['published_at']
    assert entry['revisions'][1]['diff']['retyped_properties']
    assert entry['is_default'] is True
    pointer = client(wb).get('/api/ontologies').json()['pointer']
    assert pointer['ontology_id'] == 'sales-model'

    # The publication audit names the previous revision and the exact diff.
    publications = [row['body'] for row in wb.store.query(
        'ontology_publication', wb.scope)]
    revision_audit, = [item for item in publications
                       if item['previous_revision'] == '1']
    assert revision_audit['ontology_revision'] == '2'
    assert revision_audit['diff']['retyped_properties'][0]['property'] == 'doc_no'
    audit, = [row['body'] for row in wb.store.query('review', wb.scope)
              if row['body'].get('decision') == 'publish'
              and row['body'].get('previous_revision') == '1']
    assert audit['revision_diff']['revision'] == '2'

    # ontology_query defaults to the current revision and can name the old one.
    default_query = invoke(wb, 'ontology_query',
                           {'ontology_id': 'sales-model',
                            'concept': 'SalesOrder'}).data
    assert default_query['ontology_revision'] == 'sales-model@2'
    old_query = invoke(wb, 'ontology_query',
                       {'ontology_id': 'sales-model', 'revision': '1',
                        'concept': 'SalesOrder'}).data
    assert old_query['ontology_revision'] == 'sales-model@1'

    # The old task still maps with the revision-1 property type.
    old_mapping = MappingSpec(id='orders', revision='1',
        ontology_revision='sales-model@1', concept='SalesOrder',
        source_fingerprint=old_request['sources'][0]['structure_fingerprint'],
        bindings={'book': {'source_field': 'book'},
                  'doc_no': {'source_field': 'doc_no', 'transform': 'integer'}})
    old_preview = wb.intake.submit_proposal(old_session, old_mapping,
        wb.sessions.get(old_session, wb.ctx).revision, wb.ctx)
    assert [dict(instance.values) for instance in old_preview.instances] == [
        {'book': 'SALE', 'doc_no': 1001}, {'book': 'SALE', 'doc_no': 1002}]
    assert old_preview.issues == []

    # A new task defaults to revision 2 and maps with the new value type.
    new_session, new_request = start_mapping(wb, csv_source(tmp_path))
    assert new_request['allowed_target']['ontology_revision'] == 'sales-model@2'
    assert new_request['allowed_target']['properties']['doc_no']['value_type'] \
        == 'string'
    new_mapping = MappingSpec(id='orders', revision='1',
        ontology_revision='sales-model@2', concept='SalesOrder',
        source_fingerprint=new_request['sources'][0]['structure_fingerprint'],
        bindings={'book': {'source_field': 'book'},
                  'doc_no': {'source_field': 'doc_no'}})
    new_preview = wb.intake.submit_proposal(new_session, new_mapping,
        wb.sessions.get(new_session, wb.ctx).revision, wb.ctx)
    assert [dict(instance.values) for instance in new_preview.instances] == [
        {'book': 'SALE', 'doc_no': '1001'}, {'book': 'SALE', 'doc_no': '1002'}]
    assert new_preview.issues == []


def test_rev1_released_instances_stay_queryable_after_rev2(tmp_path):
    """Publishing revision 2 must not rewrite what revision 1 already released."""
    wb, session_id, request = workbench(tmp_path)
    publish_initial(wb, session_id, request)
    (tmp_path / 'orders.csv').write_text(
        'book,doc_no\nSALE,1001\nSALE,1002\n')
    wb.layer_client = StubProbeClient({'orders': csv_profile('orders', [
        {'book': 'SALE', 'doc_no': '1001'},
        {'book': 'SALE', 'doc_no': '1002'},
    ])})
    goal = WorkSpec(id='map', goal='接入销售数据',
                    acceptance_criteria=['来源可核对'],
                    authorization_ref=wb.authorization)
    started = wb.sessions.start(
        [SourceSelection(source_id='orders', kind='file',
                         locator_ref='orders.csv')], goal, wb.ctx,
        target={'ontology_id': 'sales-model', 'concept': 'SalesOrder'})
    mapping_session = wb.intake.advance(started.session_id, wb.ctx)
    mapping_source, = wb.intake.inference_request(
        mapping_session.id, wb.ctx)['sources']
    save_single(wb, mapping_session, MappingSpec(
        id='orders', revision='1', ontology_revision='sales-model@1',
        concept='SalesOrder',
        source_fingerprint=mapping_source['structure_fingerprint'],
        bindings={'book': {'source_field': 'book'},
                  'doc_no': {'source_field': 'doc_no',
                             'transform': 'integer'}}))

    before = invoke(wb, 'ontology_query', {
        'ontology_id': 'sales-model', 'revision': '1',
        'concept': 'SalesOrder'}).data
    assert before['total'] == 2
    assert sorted(item['values']['doc_no'] for item in before['items']) == [1001, 1002]
    assert {item['revision'] for item in before['items']} == {'1'}

    # Publish revision 2 through the real discovery/revision path.
    wb.layer_client = LayerClient(DATA)
    revision_session = invoke(wb, 'intake_start', {
        'goal': '发布销售单据修订',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite',
                     'locator_ref': 'sales.db'}],
        'revise_ontology_id': 'sales-model',
    }).data['session_id']
    revision_request = invoke(wb, 'intake_advance',
                              {'session_id': revision_session}).data
    current = full_draft(wb, revision_session, revision_request)
    candidate = invoke(wb, 'ontology_publish_prepare', completion(
        wb, revision_session, current, doc_no_type='string')).data
    published = publish(wb, revision_session, candidate)
    assert published.status_code == 200, published.json()
    assert published.json()['ontology_revision'] == '2'

    after = invoke(wb, 'ontology_query', {
        'ontology_id': 'sales-model', 'revision': '1',
        'concept': 'SalesOrder'}).data
    assert after == before
    current_page = invoke(wb, 'ontology_query', {
        'ontology_id': 'sales-model', 'concept': 'SalesOrder'}).data
    assert current_page['ontology_revision'] == 'sales-model@2'
    assert current_page['total'] == 0  # rev1 data is not silently migrated



def test_revision_candidate_names_current_revision_counts_and_reintake(tmp_path):
    """FDE3-01: the candidate summary tells the confirmation page what the
    new revision means for published data.

    Per concept it counts the objects on the revision being replaced, and it
    names the concepts that need taking in again: the new revision is
    registered empty, so every released object stays invisible to queries
    that default to it.  A first publication has neither a current revision
    to count nor stranded objects.
    """
    wb, session_id, request = workbench(tmp_path)
    _, first_candidate, _ = publish_initial(wb, session_id, request)
    assert first_candidate['current_revision_instance_counts'] == {}
    assert first_candidate['reintake_concepts'] == []

    # Publish two SalesOrder objects on revision 1.
    save_sales_orders(wb, tmp_path)

    _, revision_session, revision_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    _, candidate = revision_candidate(
        wb, revision_session, revision_request, doc_no_type='string')
    assert candidate['previous_revision'] == '1'
    # Both revisions' concepts carry a count from the current revision;
    # only SalesOrder has objects, so only it needs taking in again.
    assert candidate['current_revision_instance_counts'] == {
        'SalesOrder': 2, 'SalesOrderLine': 0, 'Customer': 0}
    assert candidate['reintake_concepts'] == ['SalesOrder']

    # The web candidate view serves the same fields the summary reports.
    view = client(wb).get(
        f'/api/sessions/{revision_session}/publish/candidate').json()
    assert view['current_revision_instance_counts']['SalesOrder'] == 2
    assert view['reintake_concepts'] == ['SalesOrder']


def test_revision_confirm_rejects_a_candidate_after_old_revision_releases(tmp_path):
    """FDE3-01 review: the re-intake outlook is rechecked at confirmation.

    Preparing a revision while revision 1 is empty tells the user no concept
    needs re-intake.  A release into revision 1 made after that point makes
    the statement false; confirming the stale candidate would publish a
    revision whose objects the user was told are unaffected, so the server
    refuses and demands a fresh candidate.
    """
    wb, session_id, request = workbench(tmp_path)
    publish_initial(wb, session_id, request)

    revision_wb, revision_session, revision_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    current, candidate = revision_candidate(
        revision_wb, revision_session, revision_request, doc_no_type='string')
    assert candidate['current_revision_instance_counts'] == {
        'SalesOrder': 0, 'SalesOrderLine': 0, 'Customer': 0}
    assert candidate['reintake_concepts'] == []

    # Another task releases objects into revision 1 after prepare.
    save_sales_orders(revision_wb, tmp_path)
    stale = publish(revision_wb, revision_session, candidate)
    assert stale.status_code == 409, stale.json()
    assert 'published instances changed' in stale.json()['detail']
    assert revision_wb.store.current(
        'ontology', 'sales-model',
        scope=revision_wb.scope)['body']['revision'] == '1'

    # A fresh candidate carries the new outlook; confirming it publishes.
    refreshed = invoke(revision_wb, 'ontology_publish_prepare',
                       completion(revision_wb, revision_session, current)).data
    assert refreshed['candidate_ref'] != candidate['candidate_ref']
    assert refreshed['current_revision_instance_counts']['SalesOrder'] == 2
    assert refreshed['reintake_concepts'] == ['SalesOrder']
    published = publish(revision_wb, revision_session, refreshed)
    assert published.status_code == 200, published.json()
    assert published.json()['ontology_revision'] == '2'


def test_revision_date_to_string_formats_a_default_mapping(tmp_path):
    """FDE3-09: date→string revision keeps date formatting for default mappings.

    The source is an xlsx date column whose cells the sheet reader serializes
    as midnight ISO text.  The revision records the retype, so a mapping that
    omits ``transform`` (the default identity binding) still stores
    ``YYYY-MM-DD``.  A plain string property is not touched.
    """
    with sqlite3.connect(tmp_path / 'sales.db') as connection:
        connection.executescript(SEED.read_text())
        connection.execute('ALTER TABLE doc_hdr ADD COLUMN day TEXT')
        connection.execute(
            "UPDATE doc_hdr SET day=CASE doc_no "
            "WHEN 1001 THEN '2026-04-08' ELSE '2026-04-09' END")
    wb, session_id, request = workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    first = invoke(wb, 'ontology_publish_prepare',
                   completion(wb, session_id, current, day_type='date')).data
    assert publish(wb, session_id, first).status_code == 200

    revision_wb, revision_session, revision_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    current, candidate = revision_candidate(
        revision_wb, revision_session, revision_request, day_type='string')
    assert candidate['definition']['extensions']['dataagent.date_text'] == [
        'SalesOrder.day']
    assert publish(revision_wb, revision_session, candidate).status_code == 200

    rows = [{'book': 'SALE', 'doc_no': '1001', 'day': '2026-04-08T00:00:00'},
            {'book': 'SALE', 'doc_no': '1002', 'day': '2026-04-09T00:00:00'}]
    (tmp_path / 'orders.csv').write_text(
        'book,doc_no,day\n' + '\n'.join(
            f"{row['book']},{row['doc_no']},{row['day']}" for row in rows) + '\n')
    revision_wb.layer_client = StubProbeClient({
        'orders': csv_profile('orders', rows).model_copy(update={'kind': 'xlsx'})})
    goal = WorkSpec(id='map', goal='接入销售数据',
                    acceptance_criteria=['来源可核对'],
                    authorization_ref=revision_wb.authorization)
    started = revision_wb.sessions.start(
        [SourceSelection(source_id='orders', kind='file',
                         locator_ref='orders.csv')], goal, revision_wb.ctx,
        target={'ontology_id': 'sales-model', 'concept': 'SalesOrder'})
    mapping_session = revision_wb.intake.advance(started.session_id, revision_wb.ctx)
    mapping_source, = revision_wb.intake.inference_request(
        mapping_session.id, revision_wb.ctx)['sources']
    preview = save_single(revision_wb, mapping_session, MappingSpec(
        id='orders', revision='1', ontology_revision='sales-model@2',
        concept='SalesOrder',
        source_fingerprint=mapping_source['structure_fingerprint'],
        bindings={'book': {'source_field': 'book'},
                  'doc_no': {'source_field': 'doc_no', 'transform': 'integer'},
                  'day': {'source_field': 'day'}}))
    assert {instance.values['day'] for instance in preview.instances} == {
        '2026-04-08', '2026-04-09'}
    revision_wb.layer_client = LayerClient(DATA)


def test_revision_field_does_not_change_existing_target_validation():
    source = {'source_id': 'f', 'kind': 'file', 'locator_ref': 'orders.csv'}
    plain = Start.model_validate({
        'goal': '接入销售数据', 'sources': [source],
        'target': {'ontology_id': 'procurement',
                   'concept': 'PurchaseDocument'}})
    assert plain.target.ontology_id == 'procurement'
    assert plain.target.concept == 'PurchaseDocument'
    assert plain.revise_ontology_id is None
    assert Start.model_validate(
        {'goal': '接入销售数据', 'sources': [source]}).target is None

    with pytest.raises(ValidationError):
        Start.model_validate({'goal': '接入销售数据', 'sources': [source],
                              'target': {'concept': 'PurchaseDocument'}})
    with pytest.raises(ValidationError, match='either'):
        Start.model_validate({'goal': '接入销售数据', 'sources': [source],
                              'mode': 'ontology_discovery',
                              'target': {'ontology_id': 'sales-model'},
                              'revise_ontology_id': 'sales-model'})
    with pytest.raises(ValidationError, match='ontology_discovery'):
        Start.model_validate({'goal': '接入销售数据', 'sources': [source],
                              'revise_ontology_id': 'sales-model'})


def test_definition_diff_lists_properties_of_added_and_removed_concepts():
    before = OntologyRevision(id='m', revision='1', concepts={
        'A': {'entity_type': 'A', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'}}},
        'Old': {'entity_type': 'Old', 'identity_fields': ['id'],
                'properties': {'id': {'value_type': 'string'},
                               'label': {'value_type': 'string'}}},
    })
    after = OntologyRevision(id='m', revision='2', concepts={
        'A': {'entity_type': 'A', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'}}},
        'New': {'entity_type': 'New', 'identity_fields': ['id'],
                'properties': {'id': {'value_type': 'string'},
                               'title': {'value_type': 'string'}}},
    })
    diff = definition_diff(before, after)
    assert diff['added_concepts'] == ['New']
    assert diff['removed_concepts'] == ['Old']
    assert diff['added_properties'] == [
        {'concept': 'New', 'property': 'id', 'value_type': 'string'},
        {'concept': 'New', 'property': 'title', 'value_type': 'string'}]
    assert diff['removed_properties'] == [
        {'concept': 'Old', 'property': 'id', 'value_type': 'string'},
        {'concept': 'Old', 'property': 'label', 'value_type': 'string'}]
    assert 'New.id 新增属性（string）' in diff['summary']
    assert 'Old.label 删除属性（string）' in diff['summary']



def test_definition_diff_reports_relation_endpoint_and_role_changes():
    concepts = {
        'A': {'entity_type': 'A', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'}}},
        'B': {'entity_type': 'B', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'}}},
        'C': {'entity_type': 'C', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'}}},
    }
    before = OntologyRevision(id='m', revision='1', concepts=concepts, relations={
        'link': RelationDefinition(roles=['line', 'order'],
            subject_concept='A', object_concept='B')})
    after = OntologyRevision(id='m', revision='2', concepts=concepts, relations={
        'link': RelationDefinition(roles=['line', 'customer'],
            subject_concept='A', object_concept='C')})
    diff = definition_diff(before, after)
    assert diff['changed_relations'] == [{
        'relation': 'link',
        'before': {'roles': ['line', 'order'],
                   'subject_concept': 'A', 'object_concept': 'B'},
        'after': {'roles': ['line', 'customer'],
                  'subject_concept': 'A', 'object_concept': 'C'},
    }]
    assert any('关系 link 端点或角色调整' in line for line in diff['summary'])


def test_builtin_upgrade_appends_the_new_revision_to_history(tmp_path):
    wb = Workbench(tmp_path)
    row = wb.store.current('ontology_registry', 'procurement', scope=wb.scope)
    before = row['body']
    assert [item['revision'] for item in before['revisions']] == ['1']

    wb.ontology.register(wb.definition.model_copy(update={'revision': '2'}),
                         wb.ctx)
    row = wb.store.current('ontology_registry', 'procurement', scope=wb.scope)
    after = row['body']
    assert after['ontology_revision'] == '2'
    assert [item['revision'] for item in after['revisions']] == ['1', '2']
    assert after['revisions'][1]['previous_revision'] == '1'
    assert after['revisions'][1]['published_at']
    assert after['revisions'][1]['diff']['summary'] == []


def test_definition_diff_treats_identity_change_as_destructive():
    before = OntologyRevision(id='m', revision='1', concepts={
        'A': {'entity_type': 'A', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'},
                             'note': {'value_type': 'string'}}},
    })
    after = OntologyRevision(id='m', revision='2', concepts={
        'A': {'entity_type': 'A', 'identity_fields': ['code', 'note'],
              'properties': {'code': {'value_type': 'string'},
                             'note': {'value_type': 'string'}}},
    })
    diff = definition_diff(before, after)
    assert diff['destructive'] is True
    assert diff['identity_changes'] == [
        {'concept': 'A', 'before': ['code'], 'after': ['code', 'note']}]
    assert any('身份字段' in line for line in diff['summary'])


def test_definition_diff_reports_requiredness_change():
    before = OntologyRevision(id='m', revision='1', concepts={
        'A': {'entity_type': 'A', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'},
                             'note': {'value_type': 'string',
                                      'required': False}}},
    })
    after = OntologyRevision(id='m', revision='2', concepts={
        'A': {'entity_type': 'A', 'identity_fields': ['code'],
              'properties': {'code': {'value_type': 'string'},
                             'note': {'value_type': 'string',
                                      'required': True}}},
    })
    diff = definition_diff(before, after)
    assert diff['destructive'] is False
    assert diff['required_changes'] == [
        {'concept': 'A', 'property': 'note',
         'before': False, 'after': True}]
    assert 'A.note 必需性 可选 → 必需' in diff['summary']


# ----------------------------------------------------------------- negatives
def test_builtin_ontology_cannot_be_a_revision_target(tmp_path):
    with pytest.raises(ValueError, match='builtin ontology cannot be revised'):
        workbench(tmp_path, revise_ontology_id='procurement')


def test_retired_ontology_cannot_be_a_revision_target(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    publish_initial(wb, session_id, request)
    entry = registry_entry(wb)
    retired = client(wb).post('/api/ontologies/sales-model/retire', json={
        'reason': '并入新的销售模型', 'confirmed': True,
        'expected_revision': entry['registry_revision']})
    assert retired.status_code == 200, retired.json()

    with pytest.raises(ValueError, match='retired for new tasks'):
        workbench(tmp_path, revise_ontology_id='sales-model')


def test_revision_completion_must_name_the_revision_target(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    publish_initial(wb, session_id, request)
    _, revision_session, revision_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    current = full_draft(wb, revision_session, revision_request)
    wrong = completion(wb, revision_session, current, ontology_id='customer-model')
    with pytest.raises(ValueError, match='must equal revise_ontology_id'):
        invoke(wb, 'ontology_publish_prepare', wrong)


def test_two_revisions_from_the_same_base_only_one_publishes(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    publish_initial(wb, session_id, request)

    _, first_session, first_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    _, first_candidate = revision_candidate(
        wb, first_session, first_request, doc_no_type='string')
    _, second_session, second_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    _, second_candidate = revision_candidate(
        wb, second_session, second_request, include_customer_name=False)

    first = publish(wb, first_session, first_candidate)
    assert first.status_code == 200, first.json()
    # The second candidate was built against revision 1 as well; the registry
    # and pointer expected revisions are now stale, so it cannot overwrite it.
    second = publish(wb, second_session, second_candidate,
                     acknowledge_no_migration=True)
    assert second.status_code in {409, 422}, second.json()
    assert 'ontology revision changed' in second.json()['detail']
    entry = registry_entry(wb)
    assert entry['ontology_revision'] == '2'
    assert [item['revision'] for item in entry['revisions']] == ['1', '2']
    assert wb.store.get('ontology', 'sales-model', '3', scope=wb.scope) is None


def test_destructive_revision_needs_the_no_migration_acknowledgement(tmp_path):
    wb, session_id, request = workbench(tmp_path)
    publish_initial(wb, session_id, request)
    _, revision_session, revision_request = workbench(
        tmp_path, revise_ontology_id='sales-model')
    # Dropping Customer.name deletes a published property: old objects stay on
    # revision 1 and are not migrated.
    _, candidate = revision_candidate(wb, revision_session, revision_request,
                                      include_customer_name=False)
    assert candidate['destructive'] is True
    assert candidate['requires_no_migration_ack'] is True
    assert candidate['revision_diff']['removed_properties'] == [
        {'concept': 'Customer', 'property': 'name', 'value_type': 'string'}]

    refused = publish(wb, revision_session, candidate)
    assert refused.status_code == 422
    assert 'acknowledging that old data will not be migrated' \
        in refused.json()['detail']
    assert wb.store.current('ontology', 'sales-model',
                            scope=wb.scope)['body']['revision'] == '1'

    accepted = publish(wb, revision_session, candidate,
                       acknowledge_no_migration=True)
    assert accepted.status_code == 200, accepted.json()
    assert accepted.json()['ontology_revision'] == '2'
    assert 'name' not in OntologyRevision.model_validate(
        wb.store.get('ontology', 'sales-model', '2',
                     scope=wb.scope)['body']).concepts['Customer'].properties
    # Revision 1 still carries the property old data was published with.
    assert 'name' in OntologyRevision.model_validate(
        wb.store.get('ontology', 'sales-model', '1',
                     scope=wb.scope)['body']).concepts['Customer'].properties


def test_mcp_tool_list_exposes_the_revision_target():
    """The MCP surface advertises the composition-added revision field."""
    from dataagent_workbench.tool_schema import TOOLS
    tool, = [item for item in TOOLS if item['name'] == 'intake_start']
    assert 'revise_ontology_id' in tool['inputSchema']['properties']

