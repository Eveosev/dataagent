"""D4 read-only queries over published ontology instances.

Every positive case goes through the real intake save path, so the queried
rows are exactly the instances a release published.  The negative cases cover
unpublished previews, partial saves, pinned revisions, retirement, unknown
properties and multi-concept concept naming.
"""
from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from dataagent_contracts.intake import SourceSelection
from dataagent_contracts.ontology import MappingSpec, ReviewDecision
from dataagent_ontology.identity import digest
from dataagent_runtime.ports.workbench_store import ChangeSet, Write
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.service_tools import invoke
from dataagent_workbench.tool_schema import MODELS, TOOLS
from test_intake_repairs import StubProbeClient, csv_profile, save_single, start
from test_partial_save import conflict_and_keyless_setup
from test_publish_gate import (
    client, full_completion, full_draft, prepare, publish, workbench as discovery_workbench,
)

BINDINGS = {'number': {'source_field': 'number'},
            'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'},
            'currency': {'source_field': 'currency'}}


def _selection(source_id='f', locator='f.csv'):
    return SourceSelection(source_id=source_id, kind='file', locator_ref=locator)


def _proposal(wb, session, source_id='f', bindings=None, revision='procurement@1'):
    request = wb.intake.inference_request(session.id, wb.ctx)
    source = next(item for item in request['sources'] if item['source_id'] == source_id)
    return MappingSpec(id='candidate', revision='1', ontology_revision=revision,
                       source_fingerprint=source['structure_fingerprint'],
                       bindings=bindings or BINDINGS)


def saved_rows(tmp_path, rows, *, source_id='f', allowed=None, bindings=None):
    wb = Workbench(tmp_path, allowed_model_fields=allowed)
    wb.layer_client = StubProbeClient({source_id: csv_profile(source_id, rows)})
    session = wb.intake.advance(start(wb, [_selection(source_id, source_id + '.csv')]).session_id,
                                wb.ctx)
    save_single(wb, session, _proposal(wb, session, source_id,
                                       bindings=bindings))
    return wb, session


def query(wb, **arguments):
    return wb.queries.query(arguments, wb.ctx)


def release_of(wb, session):
    return wb.sessions.get(session.id, wb.ctx).selected_versions['release']


def test_preview_is_invisible_and_published_rows_carry_values_and_provenance(tmp_path):
    wb, session = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
    ])
    assert release_of(wb, session).startswith('release:')

    # A second task stops at a preview; its objects never become query rows.
    wb.layer_client = StubProbeClient({'g': csv_profile('g', [
        {'number': 'INV-9', 'amount_minor': '90000', 'currency': 'CNY'},
    ])})
    preview_session = wb.intake.advance(start(wb, [_selection('g', 'g.csv')],
                                             'g-preview').session_id, wb.ctx)
    wb.intake.submit_proposal(preview_session.id,
                              _proposal(wb, preview_session, 'g'),
                              preview_session.revision, wb.ctx)

    page = query(wb, ontology_id='procurement')
    assert page['total'] == 1
    item, = page['items']
    assert item['ontology_id'] == 'procurement'
    assert item['ontology_revision'] == 'procurement@1'
    assert item['revision'] == '1'
    assert item['concept'] == 'PurchaseDocument'
    assert item['instance_id'].startswith('entity:')
    assert item['values'] == {'number': 'INV-1', 'amount': '100',
                              'currency': 'CNY'}
    assert item['release_ref'] == release_of(wb, session)
    assert item['session_id'] == session.id
    assert item['task'] == '接入采购资料'
    assert item['deactivated'] is False
    anchor = item['source_anchors']['number'][0]
    assert anchor['source_ref'] == 'f'
    assert anchor['selector']['kind'] == 'record_key'
    assert anchor['selector']['keys'] == {'row': 2}
    assert anchor['selector']['field'] == 'number'
    assert item['locations'][0]['property'] == 'number'
    assert item['locations'][0]['row'] == 2
    assert item['locations'][0]['source_ref'] == 'f'
    assert all(row['values'].get('number') != 'INV-9' for row in page['items'])


def test_partial_save_returns_only_the_saved_objects(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    result = wb.intake.apply(
        session_id,
        ReviewDecision(preview_ref=preview.id + '@' + preview.revision,
                       target_scope='mapping'),
        wb.sessions.get(session_id, wb.ctx).revision, wb.ctx,
        allow_partial=True, reason='只保存可确认的发票')
    assert result.extensions['intake.partial_save']['saved']
    page = query(wb, ontology_id='procurement')
    numbers = {item['values']['number'] for item in page['items']}
    assert numbers == {'INV-1', 'INV-3'}
    assert all(item['partial_release'] is True for item in page['items'])
    release_ref = result.extensions['intake.partial_save']['release_ref']
    assert {item['release_ref'] for item in page['items']} == {release_ref}

    # The summary counts the saved snapshot, not the suspended object.
    summary = wb.queries.summary({}, wb.ctx)
    procurement, = summary['ontologies']
    assert procurement['published_instances'] == 2
    assert procurement['last_published_at']
    concept, = procurement['concepts']
    assert concept['concept'] == 'PurchaseDocument'
    assert concept['published_instances'] == 2
    assert concept['last_published_at']


def test_partial_release_stays_frozen_after_a_later_republish(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    first = wb.intake.apply(
        session_id,
        ReviewDecision(preview_ref=preview.id + '@' + preview.revision,
                       target_scope='mapping'),
        wb.sessions.get(session_id, wb.ctx).revision, wb.ctx,
        allow_partial=True, reason='只保存可确认的发票')
    old_ref = first.extensions['intake.partial_save']['release_ref']
    old_page = query(wb, ontology_id='procurement')
    old_ids = {item['instance_id'] for item in old_page['items']}
    assert len(old_ids) == 2

    # The publisher can append another released revision to the same preview
    # (for example after a revalidation).  The old release's marker is then no
    # longer ``current``; its fixed manifest must still be found.
    saved = wb.store.get('preview', preview.id, '2', scope=wb.scope)
    assert saved['body']['release_ref'] == old_ref
    republished = dict(saved['body'])
    republished['issues'] = []
    republished['review_state'] = 'approved'
    republished['approved_preview_ref'] = preview.id + '@2'
    republished.pop('partial_save', None)
    republished.pop('suspended', None)
    content = {key: saved['body'].get(key)
               for key in ('ontology_revision', 'mapping', 'source_revisions')}
    content['instances'] = saved['body']['instances']
    content['issues'] = saved['body'].get('issues') or []
    if saved['body'].get('extensions'):
        content['extensions'] = saved['body']['extensions']
    republished['digest'] = digest(content)
    release, writes = wb.ontology.release_writes(
        republished, preview.id, '2', preview.id + '@2')
    wb.store.commit(ChangeSet(writes=writes))
    new_ref = release.id + '@' + release.revision
    assert new_ref != old_ref

    page = query(wb, ontology_id='procurement')
    by_release = {}
    for item in page['items']:
        by_release.setdefault(item['release_ref'], set()).add(item['instance_id'])
    assert by_release[old_ref] == old_ids
    assert by_release[new_ref]
    assert page['total'] == len(old_ids) + len(by_release[new_ref])


def test_old_release_keeps_session_and_task_after_same_task_republishes(tmp_path):
    wb, session = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
    ])
    current = wb.sessions.get(session.id, wb.ctx)
    old_ref = current.selected_versions['release']
    preview_id, preview_revision = current.selected_versions['preview'].rsplit('@', 1)
    old_page = query(wb, ontology_id='procurement')
    old_item, = old_page['items']
    assert old_item['release_ref'] == old_ref

    # A second release from the same task points at a newer preview revision.
    # The session's next revision selects it, so the first release disappears
    # from the current session row and has to be recovered from history.
    body = dict(wb.store.get('preview', preview_id, preview_revision,
                             scope=wb.scope)['body'])
    body['instances'] = [dict(item) for item in body.get('instances') or []]
    body['instances'][0]['values'] = {
        **body['instances'][0]['values'], 'currency': 'USD'}
    body.pop('release_ref', None)
    body.pop('partial_release_ref', None)
    body['review_state'] = 'approved'
    body['approved_preview_ref'] = preview_id + '@3'
    body['revision'] = '3'
    content = {key: body.get(key)
               for key in ('ontology_revision', 'mapping', 'source_revisions')}
    content['instances'] = body['instances']
    content['issues'] = body.get('issues') or []
    if body.get('extensions'):
        content['extensions'] = body['extensions']
    body['digest'] = digest(content)
    wb.store.commit(ChangeSet(writes=[Write(
        'preview', preview_id, wb.scope, body, preview_revision)]))
    release, writes = wb.ontology.release_writes(
        body, preview_id, '3', preview_id + '@3')
    wb.store.commit(ChangeSet(writes=writes))
    new_ref = release.id + '@' + release.revision
    assert new_ref != old_ref

    current = wb.sessions.get(session.id, wb.ctx)
    updated = current.model_dump(mode='json')
    updated['selected_versions'] = {
        **updated['selected_versions'], 'preview': preview_id + '@4',
        'release': new_ref}
    updated['revision'] = str(int(current.revision) + 1)
    updated['phase'] = 'saved'
    wb.store.commit(ChangeSet(writes=[Write(
        'session', session.id, wb.scope, updated, current.revision)]))

    page = query(wb, ontology_id='procurement')
    by_release = {}
    for item in page['items']:
        by_release.setdefault(item['release_ref'], []).append(item)
    assert {item['values']['currency'] for item in by_release[old_ref]} == {'CNY'}
    assert {item['values']['currency'] for item in by_release[new_ref]} == {'USD'}
    for item in by_release[old_ref] + by_release[new_ref]:
        assert item['session_id'] == session.id
        assert item['task'] == '接入采购资料'


def test_revision_is_pinned_and_default_follows_the_registry(tmp_path):
    wb, first = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
    ])
    # A host registers the next immutable revision; new tasks default to it.
    revised = wb.definition.model_copy(update={'revision': '2'})
    wb.ontology.register(revised, wb.ctx)
    wb.layer_client = StubProbeClient({'g': csv_profile('g', [
        {'number': 'INV-2', 'amount_minor': '20000', 'currency': 'CNY'},
    ])})
    second = wb.intake.advance(start(wb, [_selection('g', 'g.csv')], 'g2').session_id,
                               wb.ctx)
    save_single(wb, second, _proposal(wb, second, 'g', revision='procurement@2'))

    default = query(wb, ontology_id='procurement')
    assert default['revision'] == '2'
    assert [item['values']['number'] for item in default['items']] == ['INV-2']

    old = query(wb, ontology_id='procurement', revision='1')
    assert old['ontology_revision'] == 'procurement@1'
    assert [item['values']['number'] for item in old['items']] == ['INV-1']
    old_by_ref = query(wb, ontology_id='procurement', revision='procurement@1')
    assert [item['values']['number'] for item in old_by_ref['items']] == ['INV-1']

    with pytest.raises(ValueError, match='another ontology'):
        query(wb, ontology_id='procurement', revision='other@1')
    with pytest.raises(KeyError):
        query(wb, ontology_id='procurement', revision='9')


def _published_model(tmp_path):
    wb, session_id, request = discovery_workbench(tmp_path)
    current = full_draft(wb, session_id, request)
    candidate = prepare(wb, full_completion(wb, session_id, current)).data
    assert publish(wb, session_id, candidate).status_code == 200
    return wb


def _save_sales_order(wb, tmp_path, name, number):
    (tmp_path / name).write_text('book,doc_no\nSALE,%d\n' % number)
    session_id = invoke(wb, 'intake_start', {
        'goal': '接入销售单', 'target': {'ontology_id': 'sales-model',
                                        'concept': 'SalesOrder'},
        'sources': [{'source_id': 'orders', 'kind': 'file',
                     'locator_ref': name}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    mapping = MappingSpec(id='orders', revision='1',
                          ontology_revision='sales-model@1', concept='SalesOrder',
                          source_fingerprint=request['sources'][0]['structure_fingerprint'],
                          bindings={'book': {'source_field': 'book'},
                                    'doc_no': {'source_field': 'doc_no',
                                               'transform': 'integer'}})
    preview = wb.intake.submit_proposal(session_id, mapping,
                                        wb.sessions.get(session_id, wb.ctx).revision,
                                        wb.ctx)
    wb.intake.apply(session_id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        wb.sessions.get(session_id, wb.ctx).revision, wb.ctx)
    return session_id


def _save_customer(wb, tmp_path, name, party_no):
    (tmp_path / name).write_text('party_no,name\n%s,Acme\n' % party_no)
    session_id = invoke(wb, 'intake_start', {
        'goal': '接入客户', 'target': {'ontology_id': 'sales-model',
                                      'concept': 'Customer'},
        'sources': [{'source_id': 'customers', 'kind': 'file',
                     'locator_ref': name}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    mapping = MappingSpec(id='customers', revision='1',
                          ontology_revision='sales-model@1', concept='Customer',
                          source_fingerprint=request['sources'][0]['structure_fingerprint'],
                          bindings={'party_no': {'source_field': 'party_no'},
                                    'name': {'source_field': 'name'}})
    preview = wb.intake.submit_proposal(session_id, mapping,
                                        wb.sessions.get(session_id, wb.ctx).revision,
                                        wb.ctx)
    wb.intake.apply(session_id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        wb.sessions.get(session_id, wb.ctx).revision, wb.ctx)
    return session_id


def test_multi_concept_requires_a_concept_and_each_endpoint_is_queryable(tmp_path):
    wb = _published_model(tmp_path)
    order_session = _save_sales_order(wb, tmp_path, 'orders.csv', 1001)
    customer_session = _save_customer(wb, tmp_path, 'customers.csv', 'P-1')

    with pytest.raises(ValueError, match='name one'):
        query(wb, ontology_id='sales-model')

    orders = query(wb, ontology_id='sales-model', concept='SalesOrder')
    assert orders['total'] == 1
    assert orders['items'][0]['concept'] == 'SalesOrder'
    assert orders['items'][0]['values'] == {'book': 'SALE', 'doc_no': 1001}
    assert orders['items'][0]['session_id'] == order_session

    customers = query(wb, ontology_id='sales-model', concept='Customer')
    assert customers['total'] == 1
    assert customers['items'][0]['concept'] == 'Customer'
    assert customers['items'][0]['values'] == {'party_no': 'P-1', 'name': 'Acme'}
    assert customers['items'][0]['session_id'] == customer_session

    # Both relation endpoints are independently addressable; no instance-level
    # relation rows are invented by the query.
    definition = wb.ontology.definition('sales-model@1', wb.ctx)
    endpoints = {name: (relation.subject_concept, relation.object_concept)
                 for name, relation in definition.relations.items()}
    assert endpoints['belongsToOrder'] == ('SalesOrderLine', 'SalesOrder')
    assert endpoints['orderedBy'] == ('SalesOrder', 'Customer')
    assert {item['concept'] for item in orders['items']} == {'SalesOrder'}
    assert {item['concept'] for item in customers['items']} == {'Customer'}
    with pytest.raises(ValueError, match='unknown concept'):
        query(wb, ontology_id='sales-model', concept='Invented')


def test_retired_ontology_stays_queryable_and_is_hidden_from_the_default_summary(tmp_path):
    wb = _published_model(tmp_path)
    _save_sales_order(wb, tmp_path, 'orders.csv', 1001)
    registry = client(wb).get('/api/ontologies').json()
    entry, = [item for item in registry['ontologies'] if item['id'] == 'sales-model']
    retired = client(wb).post('/api/ontologies/sales-model/retire', json={
        'reason': '并入下一版销售模型', 'confirmed': True,
        'expected_revision': entry['registry_revision']})
    assert retired.status_code == 200, retired.json()

    page = query(wb, ontology_id='sales-model', concept='SalesOrder')
    assert page['deactivated'] is True
    assert page['ontology_state'] == 'retired'
    assert page['total'] == 1
    assert page['items'][0]['deactivated'] is True

    service_default = wb.queries.ontologies(wb.ctx)
    assert 'sales-model' not in {item['id'] for item in service_default['ontologies']}
    service_all = wb.queries.ontologies(wb.ctx, include_deactivated=True)
    assert 'sales-model' in {item['id'] for item in service_all['ontologies']}

    default_summary = wb.queries.summary({}, wb.ctx)
    assert 'sales-model' not in {item['ontology_id'] for item in default_summary['ontologies']}
    explicit = wb.queries.summary({'ontology_id': 'sales-model'}, wb.ctx)
    assert explicit['ontologies'][0]['deactivated'] is True
    assert explicit['ontologies'][0]['published_instances'] == 1
    assert explicit['ontologies'][0]['last_published_at'] is None
    assert explicit['ontologies'][0]['last_published_at_source'] is None
    assert explicit['ontologies'][0]['last_published_at_note'] == '未知'
    assert explicit['ontologies'][0]['last_published_at_unknown'] is True
    concept = next(item for item in explicit['ontologies'][0]['concepts']
                   if item['concept'] == 'SalesOrder')
    assert concept['last_published_at'] is None
    assert concept['last_published_at_note'] == '未知'
    included = wb.queries.summary({'include_deactivated': True}, wb.ctx)
    assert 'sales-model' in {item['ontology_id'] for item in included['ontologies']}

    agent_registry = invoke(wb, 'ontology_registry', {}).data
    assert 'sales-model' not in {item['id'] for item in agent_registry['ontologies']}
    all_entries = invoke(wb, 'ontology_registry',
                         {'include_deactivated': True}).data
    assert 'sales-model' in {item['id'] for item in all_entries['ontologies']}


def test_undefined_property_is_an_error_not_an_empty_page(tmp_path):
    wb, _ = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
    ])
    with pytest.raises(ValueError, match='not defined'):
        query(wb, ontology_id='procurement',
              where=[{'property': 'secret', 'op': 'eq', 'value': 'x'}])
    with pytest.raises(ValidationError):
        query(wb, ontology_id='procurement', limit=201)
    with pytest.raises(ValidationError):
        query(wb, ontology_id='procurement',
              where=[{'property': 'number', 'op': 'regex', 'value': 'INV'}])


def test_pagination_filters_and_stable_cursor(tmp_path):
    wb, _ = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
        {'number': 'INV-2', 'amount_minor': '20000', 'currency': 'CNY'},
        {'number': 'INV-3', 'amount_minor': '30000', 'currency': 'USD'},
        {'number': 'INV-4', 'amount_minor': '40000', 'currency': 'USD'},
        {'number': 'INV-5', 'amount_minor': '50000', 'currency': 'CNY'},
    ])
    first = query(wb, ontology_id='procurement', limit=2)
    assert first['count'] == 2 and first['total'] == 5 and first['has_more'] is True
    seen = [item['instance_id'] for item in first['items']]
    cursor = first['next_cursor']
    assert cursor
    while cursor:
        page = query(wb, ontology_id='procurement', limit=2, cursor=cursor)
        seen += [item['instance_id'] for item in page['items']]
        cursor = page['next_cursor']
    assert len(seen) == 5 and len(set(seen)) == 5

    filtered = query(wb, ontology_id='procurement', limit=10,
                     where=[{'property': 'currency', 'op': 'in',
                             'value': ['USD']}])
    assert filtered['total'] == 2
    assert {item['values']['number'] for item in filtered['items']} == {'INV-3', 'INV-4'}

    contains = query(wb, ontology_id='procurement', limit=10,
                     where=[{'property': 'number', 'op': 'contains',
                             'value': 'INV-2'}])
    assert [item['values']['number'] for item in contains['items']] == ['INV-2']

    equal = query(wb, ontology_id='procurement', limit=10,
                  where=[{'property': 'amount', 'op': 'eq',
                          'value': '300'}])
    assert [item['values']['number'] for item in equal['items']] == ['INV-3']

    with pytest.raises(ValueError, match='invalid cursor'):
        query(wb, ontology_id='procurement', cursor='not-a-cursor')


def test_tool_and_summary_expose_published_instances_only(tmp_path):
    wb, _ = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
        {'number': 'INV-2', 'amount_minor': '20000', 'currency': 'CNY'},
    ])
    result = invoke(wb, 'ontology_query', {
        'ontology_id': 'procurement', 'limit': 1,
        'where': [{'property': 'number', 'op': 'eq', 'value': 'INV-2'}],
    })
    assert result.data['total'] == 1
    assert result.data['items'][0]['values']['number'] == 'INV-2'

    summary = invoke(wb, 'ontology_instances_summary', {})
    procurement, = summary.data['ontologies']
    assert procurement['ontology_id'] == 'procurement'
    assert procurement['published_instances'] == 2
    assert procurement['last_published_at'] is None
    assert procurement['last_published_at_note'] == '未知'
    concept, = procurement['concepts']
    assert concept['published_instances'] == 2
    assert concept['last_published_at'] is None
    assert concept['last_published_at_note'] == '未知'


def test_summary_uses_publish_audit_time_without_ontology_fallback(tmp_path):
    wb, session = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
    ])
    release_ref = wb.sessions.get(session.id, wb.ctx).selected_versions['release']
    recorded_at = '2026-11-18T10:00:00+00:00'
    wb.store.commit(ChangeSet(writes=[Write(
        'review', 'release-audit', wb.scope,
        {'release_ref': release_ref, 'recorded_at': recorded_at})]))
    summary = wb.queries.summary({}, wb.ctx)
    procurement, = summary['ontologies']
    assert procurement['last_published_at'] == recorded_at
    concept, = procurement['concepts']
    assert concept['last_published_at'] == recorded_at
    assert procurement['last_published_at_note'] is None
    assert procurement['last_published_at_unknown'] is False


def test_disallowed_property_values_and_anchors_are_not_disclosed(tmp_path):
    bindings = {**BINDINGS, 'issuer': {'source_field': 'issuer'}}
    wb, _ = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY',
         'issuer': 'Private Co'},
    ], allowed={'f': ['number', 'amount_minor', 'currency']}, bindings=bindings)
    item, = query(wb, ontology_id='procurement')['items']
    assert item['values'] == {'number': 'INV-1', 'amount': '100',
                              'currency': 'CNY'}
    assert 'issuer' not in item['source_anchors']
    assert 'Private Co' not in str(item)


def test_queries_do_not_write_to_the_workbench_store(tmp_path):
    wb, _ = saved_rows(tmp_path, [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
    ])
    with sqlite3.connect(wb.store.path) as db:
        before = db.execute('SELECT COUNT(*) FROM wb_records').fetchone()[0]
    query(wb, ontology_id='procurement')
    invoke(wb, 'ontology_query', {'ontology_id': 'procurement'})
    wb.queries.summary({}, wb.ctx)
    client(wb).get('/api/ontologies')
    client(wb).get('/api/ontologies/procurement/instances')
    with sqlite3.connect(wb.store.path) as db:
        after = db.execute('SELECT COUNT(*) FROM wb_records').fetchone()[0]
    assert after == before


def test_schema_and_mcp_registration_mark_query_tools_read_only(tmp_path):
    tools = {item['name']: item for item in TOOLS}
    assert tools['ontology_query']['annotations'] == {'readOnlyHint': True}
    assert tools['ontology_instances_summary']['annotations'] == {'readOnlyHint': True}
    assert 'where' in tools['ontology_query']['inputSchema']['properties']
    assert 'include_deactivated' in (
        tools['ontology_instances_summary']['inputSchema']['properties'])
    assert MODELS['ontology_query'].model_json_schema()['properties']['limit']['maximum'] == 200

    from dataagent_workbench.interfaces.mcp_server import handle
    listed = {item['name']: item for item in
              handle(Workbench(tmp_path), {'method': 'tools/list'})['tools']}
    assert listed['ontology_query']['annotations'] == {'readOnlyHint': True}
    assert listed['ontology_instances_summary']['annotations'] == {'readOnlyHint': True}


# ---------------------------------------------------------------- ordered queries
EXPENSE_DEFINITION = None


def _expense_definition():
    from dataagent_contracts.ontology import (
        ConceptDefinition, OntologyRevision, PropertyDefinition, RelationDefinition,
    )
    return OntologyRevision(id='expense-model', revision='1', concepts={
        'ExpenseLine': ConceptDefinition(entity_type='ExpenseLine', properties={
            'number': PropertyDefinition(value_type='string', required=True),
            'line': PropertyDefinition(value_type='integer', required=True),
            'spent_on': PropertyDefinition(value_type='date'),
            'category': PropertyDefinition(value_type='string', required=True),
            'amount': PropertyDefinition(value_type='decimal', required=True),
        }, identity_fields=['number', 'line']),
        'ExpenseStandard': ConceptDefinition(entity_type='ExpenseStandard', properties={
            'category': PropertyDefinition(value_type='string', required=True),
            'limit': PropertyDefinition(value_type='decimal', required=True),
        }, identity_fields=['category']),
    }, relations={'usesStandard': RelationDefinition(
        roles=['line', 'standard'], subject_concept='ExpenseLine',
        object_concept='ExpenseStandard')})


def _save_concept(wb, concept, rows, bindings, relation_bindings=None):
    from dataagent_contracts.intake import WorkSpec
    source_id = 'src-' + concept
    wb.layer_client = StubProbeClient({source_id: csv_profile(source_id, rows)})
    goal = WorkSpec(id='goal-' + concept, goal='按本体接入', acceptance_criteria=['来源可核对'],
                    authorization_ref=wb.authorization)
    handle = wb.sessions.start(
        [SourceSelection(source_id=source_id, kind='file',
                         locator_ref=source_id + '.csv')],
        goal, wb.ctx, mode='mapping',
        target={'ontology_id': 'expense-model', 'concept': concept})
    wb.intake.advance(handle.session_id, wb.ctx)
    session = wb.sessions.get(handle.session_id, wb.ctx)
    request = wb.intake.inference_request(handle.session_id, wb.ctx)
    source = request['sources'][0]
    mapping = MappingSpec(id='candidate', revision='1',
                          ontology_revision='expense-model@1', concept=concept,
                          source_fingerprint=source['structure_fingerprint'],
                          bindings=bindings,
                          relation_bindings=relation_bindings or {})
    preview = wb.intake.submit_proposal(handle.session_id, mapping,
                                        session.revision, wb.ctx)
    session = wb.sessions.get(handle.session_id, wb.ctx)
    wb.intake.apply(handle.session_id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision,
        target_scope='mapping'), session.revision, wb.ctx)
    assert wb.sessions.get(handle.session_id, wb.ctx).phase == 'saved'
    return handle.session_id


def expense_model(tmp_path):
    """Standards and lines published by separate tasks of one revision."""
    wb = Workbench(tmp_path)
    wb.ontology.register(_expense_definition(), wb.ctx)
    _save_concept(wb, 'ExpenseStandard', [
        {'category': '住宿', 'limit': '500'},
        {'category': '伙食', 'limit': '80'},
    ], {'category': {'source_field': 'category'},
        'limit': {'source_field': 'limit', 'transform': 'decimal'}})
    _save_concept(wb, 'ExpenseLine', [
        {'number': 'BX-1', 'line': '1', 'spent_on': '2026-03-01',
         'category': '住宿', 'amount': '600'},
        {'number': 'BX-1', 'line': '2', 'spent_on': '2026-03-02',
         'category': '住宿', 'amount': '450'},
        {'number': 'BX-2', 'line': '1', 'spent_on': '2026-03-03',
         'category': '伙食', 'amount': '90'},
        {'number': 'BX-2', 'line': '2', 'spent_on': '2026-03-04',
         'category': '交通', 'amount': '30'},
    ], {'number': {'source_field': 'number'},
        'line': {'source_field': 'line', 'transform': 'integer'},
        'spent_on': {'source_field': 'spent_on', 'transform': 'date'},
        'category': {'source_field': 'category'},
        'amount': {'source_field': 'amount', 'transform': 'decimal'}},
        {'usesStandard': {
            'line': {'source_field': '$entity'},
            'standard': {'source_field': 'category'},
        }})
    return wb


def _amounts(page):
    return sorted(str(item['values']['amount']) for item in page['items'])


def test_ordered_conditions_compare_numbers_and_dates(tmp_path):
    wb = expense_model(tmp_path)
    over = query(wb, ontology_id='expense-model', concept='ExpenseLine',
                 where=[{'property': 'amount', 'op': 'gt', 'value': '500'}], limit=200)
    assert over['total'] == 1 and _amounts(over) == ['600']

    at_least = query(wb, ontology_id='expense-model', concept='ExpenseLine',
                     where=[{'property': 'amount', 'op': 'gte', 'value': 450}], limit=200)
    assert at_least['total'] == 2

    under = query(wb, ontology_id='expense-model', concept='ExpenseLine',
                  where=[{'property': 'amount', 'op': 'lt', 'value': '90'}], limit=200)
    assert under['total'] == 1 and _amounts(under) == ['30']

    dated = query(wb, ontology_id='expense-model', concept='ExpenseLine',
                  where=[{'property': 'spent_on', 'op': 'gte', 'value': '2026-03-02'}],
                  limit=200)
    assert dated['total'] == 3
    before = query(wb, ontology_id='expense-model', concept='ExpenseLine',
                   where=[{'property': 'spent_on', 'op': 'lt', 'value': '2026-03-02'}],
                   limit=200)
    assert before['total'] == 1

    combined = query(wb, ontology_id='expense-model', concept='ExpenseLine',
                     where=[{'property': 'amount', 'op': 'lte', 'value': '450'},
                            {'property': 'category', 'op': 'eq', 'value': '住宿'}],
                     limit=200)
    assert combined['total'] == 1


def test_ordered_conditions_reject_unsupported_types_and_values(tmp_path):
    wb = expense_model(tmp_path)
    with pytest.raises(ValueError, match='only supported on decimal/integer/date'):
        query(wb, ontology_id='expense-model', concept='ExpenseLine',
              where=[{'property': 'category', 'op': 'gt', 'value': '住宿'}])
    with pytest.raises(ValueError, match='single value'):
        query(wb, ontology_id='expense-model', concept='ExpenseLine',
              where=[{'property': 'amount', 'op': 'gt', 'value': ['500']}])
    with pytest.raises(ValueError, match='does not match ordered decimal'):
        query(wb, ontology_id='expense-model', concept='ExpenseLine',
              where=[{'property': 'amount', 'op': 'gt', 'value': 'not-a-number'}])


def test_include_related_fetches_the_standard_limit_for_each_line(tmp_path):
    wb = expense_model(tmp_path)
    page = query(wb, ontology_id='expense-model', concept='ExpenseLine',
                 include_related={'relation': 'usesStandard', 'fields': ['limit']},
                 limit=200)
    assert page['total'] == 4
    by_id = {item['values']['number'] + '-' + str(item['values']['line']): item
             for item in page['items']}
    assert by_id['BX-1-1']['related'] == {
        'relation': 'usesStandard',
        'target_instance_id': by_id['BX-1-1']['related']['target_instance_id'],
        'fields': {'limit': '500'},
    }
    assert by_id['BX-1-2']['related']['fields'] == {'limit': '500'}
    assert by_id['BX-2-1']['related']['fields'] == {'limit': '80'}
    assert by_id['BX-2-2']['related'] is None
    assert page['related_missing_count'] == 1
    assert page['related_missing'] == [{
        'release_ref': page['related_missing'][0]['release_ref'],
        'instance_id': page['related_missing'][0]['instance_id'],
        'values': by_id['BX-2-2']['values'],
    }]
    assert page['related_stats'] == {
        'relation': 'usesStandard', 'matched': 3, 'missing': 1, 'ambiguous': 0,
    }
    assert page['include_related']['target_concept'] == 'ExpenseStandard'
    assert page['include_related']['direction'] == 'subject_to_object'

    # The two-step business answer: fetch the amounts and the related limits,
    # then compare in the agent.  Exactly the over-limit rows survive.
    flagged = [(item['values']['number'], item['values']['line'])
               for item in page['items']
               if item['related'] is not None
               and float(item['values']['amount']) > float(item['related']['fields']['limit'])]
    assert sorted(flagged) == [('BX-1', 1), ('BX-2', 1)]


def test_include_related_can_traverse_in_reverse_and_defaults_to_identity(tmp_path):
    wb = expense_model(tmp_path)
    page = query(wb, ontology_id='expense-model', concept='ExpenseStandard',
                 include_related={'relation': 'usesStandard'}, limit=200)
    assert page['include_related']['target_concept'] == 'ExpenseLine'
    assert page['include_related']['direction'] == 'object_to_subject'
    assert page['include_related']['fields'] == ['number', 'line']
    related = [item['related'] for item in page['items'] if item['related']]
    assert len(related) == 2
    assert all(set(item['fields']) == {'number', 'line'} for item in related)

    with pytest.raises(ValueError, match='unknown relation'):
        query(wb, ontology_id='expense-model', concept='ExpenseLine',
              include_related={'relation': 'missing', 'fields': ['limit']})
    with pytest.raises(ValueError, match='not defined on related concept'):
        query(wb, ontology_id='expense-model', concept='ExpenseLine',
              include_related={'relation': 'usesStandard', 'fields': ['secret']})
