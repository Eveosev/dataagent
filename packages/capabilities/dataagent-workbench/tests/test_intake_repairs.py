"""Regression tests for T50 D2/D3/D6/D7 and U1/U3/U5.

The scenarios mirror the evidence file: a rejected re-proposal used to drop
web corrections, a scanned-PDF combination never reused its verified mapping,
a mixed-page PDF could not associate a field with the document row, and save
rejections/summaries never named the affected objects.
"""
import json

import pytest

from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import SourceProfile, SourceSelection, WorkSpec
from dataagent_contracts.ontology import MappingSpec, ReviewDecision
from dataagent_ontology.identity import digest
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.document_fields import DocumentField, extract_fields
from dataagent_workbench.interfaces.mcp_server import handle
from dataagent_workbench.service_tools import invoke


class StubProbeClient:
    """Return prebuilt profiles; the acceptance data layer is not needed."""

    def __init__(self, profiles):
        self.profiles = profiles

    def probe(self, selection, ctx, workspace, *, previous=None, budget_seconds=None):
        return self.profiles[selection.source_id]


def csv_profile(source_id, records, fingerprint=None, kind='csv'):
    fields = list(dict.fromkeys(name for row in records for name in row))
    anchors = {}
    for index, row in enumerate(records):
        for field, value in row.items():
            if value is None:
                continue
            anchors[f'{index}.{field}'] = [SourceAnchor(
                source_ref=source_id, source_revision='sha256:fixture',
                selector={'kind': 'record_key', 'keys': {'row': index + 2},
                          'field': field})]
    return SourceProfile(source_id=source_id, source_revision='sha256:fixture', kind=kind,
                         records=records, fields=fields, anchors=anchors,
                         metadata={'structure_fingerprint': fingerprint or digest([source_id, 'structure'])},
                         total_partitions=1, completed_partitions=[1])


def pdf_profile(source_id, records, pages, spans, fingerprint):
    anchors = {}
    for index, row in enumerate(records):
        for field, value in row.items():
            if value is None:
                continue
            page, quote = spans[(index, field)]
            text = next(item['text'] for item in pages if item['page'] == page)
            start = text.index(quote)
            anchors[f'{index}.{field}'] = [SourceAnchor(
                source_ref=source_id, source_revision='sha256:fixture',
                selector={'kind': 'pdf_text_span', 'page': page,
                          'char_start': start, 'char_end': start + len(quote)})]
    return SourceProfile(source_id=source_id, source_revision='sha256:fixture', kind='pdf',
                         records=records, fields=list(records[0]) if records else [],
                         anchors=anchors,
                         metadata={'structure_fingerprint': fingerprint,
                                   'pages': pages, 'total_pages': len(pages)},
                         total_partitions=1, completed_partitions=[1])


def start(wb, sources, goal_id='g'):
    goal = WorkSpec(id=goal_id, goal='接入采购资料', acceptance_criteria=['来源可核对'],
                    authorization_ref=wb.authorization)
    return wb.sessions.start(sources, goal, wb.ctx)


def proposal_for(session, wb, source_id, bindings):
    source = next(item for item in wb.intake.inference_request(session.id, wb.ctx)['sources']
                  if item['source_id'] == source_id)
    return MappingSpec(id='candidate', revision='1', ontology_revision='procurement@1',
                       source_fingerprint=source['structure_fingerprint'], bindings=bindings)


def save_single(wb, session, mapping):
    preview = wb.intake.submit_proposal(session.id, mapping, session.revision, wb.ctx)
    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        current.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'
    return preview


def single_setup(tmp_path, records=None):
    wb = Workbench(tmp_path)
    profile = csv_profile('f', records or [{'number': 'INV-1', 'amount_minor': '126000',
                                           'currency': 'CNY'}])
    wb.layer_client = StubProbeClient({'f': profile})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='f', kind='file', locator_ref='invoice.csv')]).session_id, wb.ctx)
    assert session.phase == 'needs_input'
    return wb, session


def basic_bindings():
    return {'number': {'source_field': 'number'},
            'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'},
            'currency': {'source_field': 'currency'}}


# --- D2: web corrections survive a new proposal -------------------------

def test_web_correction_survives_reproposal(tmp_path):
    wb, session = single_setup(tmp_path)
    preview = wb.intake.submit_proposal(
        session.id, proposal_for(session, wb, 'f', basic_bindings()), session.revision, wb.ctx)
    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@1', target_scope='instance',
        changes={'entity_id': preview.instances[0].id, 'property': 'amount',
                 'value': '1250', 'reason': '用户核对'}), session.revision, wb.ctx)

    session = wb.sessions.get(session.id, wb.ctx)
    again = wb.intake.submit_proposal(
        session.id, proposal_for(session, wb, 'f', basic_bindings()), session.revision, wb.ctx)
    view = wb.intake.view(session.id, wb.ctx)
    assert view['preview']['instances'][0]['values']['amount'] == '1250'
    assert [item['property'] for item in view['preview']['corrections']] == ['amount']
    assert view['preview']['issues'] == []
    assert again.instances[0].values['amount'] == 1250

    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=again.id + '@' + again.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'
    manual = [row for row in wb.store.query('assertion', wb.scope)
              if row['body']['extractor_version'] == 'user_correction']
    assert manual


def test_conflicting_carried_correction_is_reported_not_dropped(tmp_path):
    wb, session = single_setup(tmp_path)
    preview = wb.intake.submit_proposal(
        session.id, proposal_for(session, wb, 'f', basic_bindings()), session.revision, wb.ctx)
    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@1', target_scope='instance',
        changes={'entity_id': preview.instances[0].id, 'property': 'amount',
                 'value': '1250', 'reason': '用户核对'}), session.revision, wb.ctx)

    session = wb.sessions.get(session.id, wb.ctx)
    revised = proposal_for(session, wb, 'f', basic_bindings()).model_copy(
        update={'identity_strategy': 'declared_keys_v2'})
    wb.intake.submit_proposal(session.id, revised, session.revision, wb.ctx)
    view = wb.intake.view(session.id, wb.ctx)
    conflicts = [issue for issue in view['preview']['issues']
                 if issue['code'] == 'ontology.correction_conflict']
    assert conflicts and conflicts[0]['object'] == 'INV-1'
    assert 'amount' == conflicts[0]['target']

    session = wb.sessions.get(session.id, wb.ctx)
    with pytest.raises(ValueError) as blocked:
        wb.intake.apply(session.id, ReviewDecision(
            preview_ref=session.selected_versions['preview'], target_scope='mapping'),
            session.revision, wb.ctx)
    assert str(blocked.value) == 'preview contains unresolved issues'
    assert any(issue['object'] == 'INV-1' for issue in blocked.value.issues)


# --- D3: extracted fields do not change the structure fingerprint -------

def three_source_setup(tmp_path):
    wb = Workbench(tmp_path)
    invoice = csv_profile('invoice', [{'number': 'INV-001', 'amount_minor': '126000',
                                       'currency': 'CNY'}])
    pages = [{'page': 1, 'text': 'Invoice INV-003\nAmount: 1260.00CNY'}]
    scan = pdf_profile('scan', [{'Am0unt': '1260.00CNY'}], pages,
                       {(0, 'Am0unt'): (1, '1260.00CNY')},
                       digest(['scan', 'one scanned page']))
    xlsx = csv_profile('xlsx', [{'number': 'INV-004', 'amount_minor': '158000',
                                 'currency': 'CNY'}], kind='xlsx')
    wb.layer_client = StubProbeClient({'invoice': invoice, 'scan': scan, 'xlsx': xlsx})
    sources = [SourceSelection(source_id=source_id, kind='file', locator_ref=locator)
               for source_id, locator in [('invoice', 'invoice.pdf'), ('scan', 'scan.pdf'),
                                          ('xlsx', 'invoices.xlsx')]]
    return wb, sources


def three_source_proposals(session, wb, request):
    bindings = {
        'invoice': {'number': {'source_field': 'number'},
                    'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'},
                    'currency': {'source_field': 'currency'}},
        'scan': {'number': {'source_field': 'number'},
                 'amount': {'source_field': 'amount', 'transform': 'decimal'},
                 'currency': {'source_field': 'currency'}},
        'xlsx': {'number': {'source_field': 'number'},
                 'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'},
                 'currency': {'source_field': 'currency'}},
    }
    return {source['source_id']: MappingSpec(
        id='candidate', revision='1', ontology_revision='procurement@1',
        source_fingerprint=source['structure_fingerprint'], bindings=bindings[source['source_id']])
        for source in request['sources']}


def test_scanned_combination_reuses_after_extraction(tmp_path):
    wb, sources = three_source_setup(tmp_path)
    session = wb.intake.advance(start(wb, sources).session_id, wb.ctx)
    request = wb.intake.inference_request(session.id, wb.ctx)
    before = request['sources'][1]['structure_fingerprint']
    extracted = invoke(wb, 'intake_extract', {
        'session_id': session.id, 'source_id': 'scan',
        'expected_revision': session.revision,
        'fields': [{'row': 0, 'name': name, 'page': 1, 'quote': quote}
                   for name, quote in [('number', 'INV-003'), ('amount', '1260.00'),
                                       ('currency', 'CNY')]],
    }).data
    after = next(item for item in extracted['sources']
                 if item['source_id'] == 'scan')['structure_fingerprint']
    assert before == after

    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_source_proposals(
        session.id, three_source_proposals(session, wb, extracted), session.revision, wb.ctx)
    assert preview.issues == []
    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'

    reused = wb.intake.advance(start(wb, sources, 'g2').session_id, wb.ctx)
    assert reused.phase == 'preview'
    view = wb.intake.view(reused.id, wb.ctx)
    assert view['mapping_reused']
    assert view['preview']['issues'] == []
    scan = next(item for item in view['profiles'] if item['source_id'] == 'scan')
    assert {'number', 'amount', 'currency'} <= set(scan['fields'])


# --- D6: a document row can receive a field from another page -----------

def mixed_profile():
    pages = [{'page': 1, 'text': 'number: INV-002\namount_minor: 90000'},
             {'page': 3, 'text': 'currency: CNY'}]
    return pdf_profile('mixed', [{'number': 'INV-002', 'amount_minor': '90000'},
                                 {'currency': 'CNY'}], pages,
                       {(0, 'number'): (1, 'INV-002'),
                        (0, 'amount_minor'): (1, '90000'),
                        (1, 'currency'): (3, 'CNY')},
                       digest(['mixed', 'three pages']))


def test_extract_associates_cross_page_field_and_keeps_its_page():
    updated = extract_fields(mixed_profile(), [DocumentField(
        row=0, name='currency', page=3, quote='CNY')], None)
    assert updated.records == [{'number': 'INV-002', 'amount_minor': '90000',
                                'currency': 'CNY'}]
    selector = updated.anchors['0.currency'][0].selector
    assert selector.page == 3
    text = updated.metadata['pages'][1]['text']
    assert text[selector.char_start:selector.char_end] == 'CNY'


def test_cross_page_extract_through_the_service_merges_the_orphan(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'mixed': mixed_profile()})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='mixed', kind='file', locator_ref='mixed.pdf')]).session_id, wb.ctx)
    result = invoke(wb, 'intake_extract', {
        'session_id': session.id, 'source_id': 'mixed',
        'expected_revision': session.revision,
        'fields': [{'row': 0, 'name': 'currency', 'page': 3, 'quote': 'CNY'}],
    }).data
    profile, = wb.intake.view(session.id, wb.ctx)['profiles']
    assert profile['records'] == [{'number': 'INV-002', 'amount_minor': '90000',
                                   'currency': 'CNY'}]
    assert profile['anchors']['0.currency'][0]['selector']['page'] == 3
    assert result['sources'][0]['structure_fingerprint'] == mixed_profile().metadata[
        'structure_fingerprint']


# --- D7: save rejection and summaries name objects and reasons ----------

def conflict_setup(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'a': csv_profile('a', [{'number': 'INV-1', 'amount_minor': '126000', 'currency': 'CNY'}]),
        'b': csv_profile('b', [{'number': 'INV-1', 'amount_minor': '125000', 'currency': 'CNY'}]),
    })
    sources = [SourceSelection(source_id='a', kind='file', locator_ref='a.csv'),
               SourceSelection(source_id='b', kind='file', locator_ref='b.csv')]
    session = wb.intake.advance(start(wb, sources).session_id, wb.ctx)
    request = wb.intake.inference_request(session.id, wb.ctx)
    proposals = {source['source_id']: MappingSpec(
        id='candidate', revision='1', ontology_revision='procurement@1',
        source_fingerprint=source['structure_fingerprint'], bindings={
            'number': {'source_field': 'number'},
            'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'},
            'currency': {'source_field': 'currency'}}) for source in request['sources']}
    preview = wb.intake.submit_source_proposals(
        session.id, proposals, session.revision, wb.ctx)
    return wb, session.id, preview


def test_preview_summary_names_conflicting_objects(tmp_path):
    wb, session_id, preview = conflict_setup(tmp_path)
    summary = invoke(wb, 'mapping_preview', {'session_id': session_id}).data
    assert summary['preview_ref'] == preview.id + '@1'
    assert summary['issue_count'] == len(summary['issues']) == 1
    issue, = summary['issues']
    assert issue['object'] == 'INV-1'
    assert issue['target'] == 'amount'
    assert issue['reason'] == '各来源的字段值不一致'


def test_save_rejection_lists_objects_through_mcp(tmp_path):
    wb, session_id, preview = conflict_setup(tmp_path)
    session = wb.sessions.get(session_id, wb.ctx)
    response = handle(wb, {'method': 'tools/call', 'params': {
        'name': 'mapping_apply', 'arguments': {
            'session_id': session_id, 'expected_revision': session.revision,
            'decision': {'preview_ref': preview.id + '@1', 'target_scope': 'mapping'}}}})
    payload = json.loads(response['content'][0]['text'])
    assert response['isError'] is True
    assert payload['detail'] == 'preview contains unresolved issues'
    assert any(issue['object'] == 'INV-1' and issue['target'] == 'amount'
               for issue in payload['issues'])
    assert wb.sessions.get(session_id, wb.ctx).phase == 'preview'


# --- U1/U3: readable candidate labels and an untruncated issue list -----

def candidate_setup(tmp_path, rows=6):
    wb = Workbench(tmp_path)
    records = [{'amount_minor': str(1000 + index), 'currency': 'CNY'}
               for index in range(rows)]
    wb.layer_client = StubProbeClient({'f': csv_profile('f', records)})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='f', kind='file', locator_ref='invoices.csv')]).session_id, wb.ctx)
    request = wb.intake.inference_request(session.id, wb.ctx)
    mapping = MappingSpec(id='candidate', revision='1', ontology_revision='procurement@1',
                          source_fingerprint=request['sources'][0]['structure_fingerprint'],
                          bindings={'number': {'source_field': 'number'},
                                    'amount': {'source_field': 'amount_minor',
                                               'transform': 'minor_to_major'},
                                    'currency': {'source_field': 'currency'}})
    preview = wb.intake.submit_proposal(session.id, mapping, session.revision, wb.ctx)
    return wb, session.id, preview


def test_candidate_objects_get_readable_labels_not_hashes(tmp_path):
    wb, session_id, preview = candidate_setup(tmp_path)
    view = wb.intake.view(session_id, wb.ctx)
    assert len(view['preview']['object_labels']) == len(preview.instances) == 6
    labels = list(view['preview']['object_labels'].values())
    assert all(label.startswith('未识别单据') for label in labels)
    assert all(not label.startswith('candidate:') for label in labels)


def test_issue_list_is_not_truncated_and_reports_the_total(tmp_path):
    wb, session_id, _ = candidate_setup(tmp_path)
    summary = invoke(wb, 'mapping_preview', {'session_id': session_id}).data
    assert summary['issue_count'] == len(summary['issues']) == 12
    assert summary['issue_count'] > 5
    assert {issue['object'] for issue in summary['issues']} == {
        f'第 {row + 1} 行' for row in range(6)}


# --- U5: read-only connection listing ----------------------------------

def test_source_connections_tool_lists_names_and_kinds_only(tmp_path, monkeypatch):
    sentinel = 'T50-SENTINEL-6a1f0c4d8e2b'
    monkeypatch.setenv('T50_REST_TOKEN', sentinel)
    config = tmp_path / 'connections.json'
    config.write_text(json.dumps({'accounting': {
        'kind': 'rest', 'label': '发票 API', 'locator': 'http://127.0.0.1:9999/invoices',
        'allowed_origins': ['http://127.0.0.1:9999'],
        'options': {'records_path': '/items'},
        'credential_options': {'auth': 'bearer'},
        'credential_refs': {'token': 'env:T50_REST_TOKEN'},
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(config))
    wb = Workbench(tmp_path)
    result = invoke(wb, 'source_connections', {})
    assert result.data == {'connections': [
        {'id': 'accounting', 'kind': 'rest', 'label': '发票 API'}]}
    assert sentinel not in json.dumps(result.data)


def test_cross_page_move_rejects_fields_from_another_document():
    pages = [{'page': 1, 'text': 'number: INV-A\namount_minor: 100'},
             {'page': 2, 'text': 'number: INV-B\ncurrency: CNY'}]
    profile = pdf_profile('two-docs', [
        {'number': 'INV-A', 'amount_minor': '100'},
        {'number': 'INV-B', 'currency': 'CNY'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (0, 'amount_minor'): (1, '100'),
               (1, 'number'): (2, 'INV-B'), (1, 'currency'): (2, 'CNY')},
        digest(['two-documents', 'one-pdf']))
    with pytest.raises(ValueError, match='different documents'):
        extract_fields(profile, [DocumentField(row=0, name='currency', page=2, quote='CNY')],
                       None, identity_fields=('number',))


def test_cross_page_move_allows_the_same_document_number():
    pages = [{'page': 1, 'text': 'number: INV-A\namount_minor: 100'},
             {'page': 2, 'text': 'number: INV-A\ncurrency: CNY'}]
    profile = pdf_profile('same-doc', [
        {'number': 'INV-A', 'amount_minor': '100'},
        {'number': 'INV-A', 'currency': 'CNY'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (0, 'amount_minor'): (1, '100'),
               (1, 'number'): (2, 'INV-A'), (1, 'currency'): (2, 'CNY')},
        digest(['same-document', 'one-pdf']))
    updated = extract_fields(profile, [DocumentField(
        row=0, name='currency', page=2, quote='CNY')], None, identity_fields=('number',))
    assert updated.records[0] == {'number': 'INV-A', 'amount_minor': '100', 'currency': 'CNY'}
    assert updated.anchors['0.currency'][0].selector.page == 2


def two_source_setup(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'a': csv_profile('a', [{'number': 'INV-A', 'amount_minor': '100000', 'currency': 'CNY'}]),
        'b': csv_profile('b', [{'number': 'INV-B', 'amount_minor': '200000', 'currency': 'CNY'}]),
    })
    sources = [SourceSelection(source_id='a', kind='file', locator_ref='a.csv'),
               SourceSelection(source_id='b', kind='file', locator_ref='b.csv')]
    session = wb.intake.advance(start(wb, sources).session_id, wb.ctx)
    request = wb.intake.inference_request(session.id, wb.ctx)
    proposals = {source['source_id']: MappingSpec(
        id='candidate', revision='1', ontology_revision='procurement@1',
        source_fingerprint=source['structure_fingerprint'],
        bindings=basic_bindings()) for source in request['sources']}
    preview = wb.intake.submit_source_proposals(
        session.id, proposals, session.revision, wb.ctx)
    return wb, session.id, preview


def correct_amount(wb, session_id, preview, number, value):
    instances = preview.instances if hasattr(preview, 'instances') else preview['instances']
    def number_of(instance):
        values = instance.get('values', {}) if isinstance(instance, dict) else instance.values
        return values.get('number')
    entity = next(instance for instance in instances if number_of(instance) == number)
    entity_id = entity.get('id') if isinstance(entity, dict) else entity.id
    session = wb.sessions.get(session_id, wb.ctx)
    return wb.intake.apply(session_id, ReviewDecision(
        preview_ref=session.selected_versions['preview'], target_scope='instance',
        changes={'entity_id': entity_id, 'property': 'amount', 'value': value,
                 'reason': '用户核对'}), session.revision, wb.ctx)


def test_pending_correction_conflicts_survive_repeated_proposals(tmp_path):
    wb, session_id, preview = two_source_setup(tmp_path)
    correct_amount(wb, session_id, preview, 'INV-A', '1000')
    correct_amount(wb, session_id, wb.intake.view(session_id, wb.ctx)['preview'],
                   'INV-B', '2000')
    assert {item['value'] for item in
            wb.intake.view(session_id, wb.ctx)['preview']['corrections']} == {'1000', '2000'}

    # Re-propose with only source a: INV-B disappears, but its correction must
    # remain visible instead of being discarded with the replaced preview.
    for _ in range(2):
        session = wb.sessions.get(session_id, wb.ctx)
        mapping = proposal_for(session, wb, 'a', basic_bindings())
        wb.intake.submit_proposal(session_id, mapping, session.revision, wb.ctx)
        view = wb.intake.view(session_id, wb.ctx)
        conflicts = [issue for issue in view['preview']['issues']
                     if issue['code'] == 'ontology.correction_conflict']
        assert any(issue['object'] == 'INV-B' for issue in conflicts), view['preview']['issues']
        assert all(issue['target'] == 'amount' for issue in conflicts)

    # Bringing source b back resolves the pending correction instead of
    # reporting it forever.
    session = wb.sessions.get(session_id, wb.ctx)
    request = wb.intake.inference_request(session_id, wb.ctx)
    proposals = {source['source_id']: MappingSpec(
        id='candidate', revision='1', ontology_revision='procurement@1',
        source_fingerprint=source['structure_fingerprint'], bindings=basic_bindings())
        for source in request['sources']}
    preview = wb.intake.submit_source_proposals(
        session_id, proposals, session.revision, wb.ctx)
    assert preview.issues == []
    view = wb.intake.view(session_id, wb.ctx)
    assert {item['value'] for item in view['preview']['corrections']} == {'1000', '2000'}
    session = wb.sessions.get(session_id, wb.ctx)
    wb.intake.apply(session_id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(session_id, wb.ctx).phase == 'saved'


def test_cross_page_alias_rejects_fields_from_another_document():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'number: INV-B\nIssuer: Seller-B'}]
    profile = pdf_profile('alias-docs', [
        {'number': 'INV-A'},
        {'number': 'INV-B', 'Issuer': 'Seller-B'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'number'): (2, 'INV-B'),
               (1, 'Issuer'): (2, 'Seller-B')}, digest(['alias', 'two-documents']))
    with pytest.raises(ValueError, match='different documents'):
        extract_fields(profile, [DocumentField(
            row=0, name='issuer', page=2, quote='Seller-B')], None,
            identity_fields=('number',))


def test_cross_page_alias_allows_the_same_document():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'number: INV-A\nIssuer: Seller-A'}]
    profile = pdf_profile('alias-same-doc', [
        {'number': 'INV-A'},
        {'number': 'INV-A', 'Issuer': 'Seller-A'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'number'): (2, 'INV-A'),
               (1, 'Issuer'): (2, 'Seller-A')}, digest(['alias', 'same-document']))
    updated = extract_fields(profile, [DocumentField(
        row=0, name='issuer', page=2, quote='Seller-A')], None,
        identity_fields=('number',))
    assert updated.records[0]['issuer'] == 'Seller-A'
    assert updated.anchors['0.issuer'][0].selector.page == 2


def test_cross_page_without_an_exact_anchor_checks_the_page_owner():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'number: INV-B\nIssuer: Seller-B'}]
    profile = pdf_profile('alias-no-anchor', [
        {'number': 'INV-A'},
        {'number': 'INV-B', 'Issuer': 'Seller-B'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'number'): (2, 'INV-B'),
               (1, 'Issuer'): (2, 'Seller-B')}, digest(['alias', 'no-anchor']))
    profile.anchors.pop('1.Issuer')
    with pytest.raises(ValueError, match='different documents'):
        extract_fields(profile, [DocumentField(
            row=0, name='issuer', page=2, quote='Seller-B')], None,
            identity_fields=('number',))


def test_cross_page_alias_rejects_an_orphan_row_from_another_document():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'number: INV-B\nIssuer: Seller-B'}]
    profile = pdf_profile('alias-orphan', [
        {'number': 'INV-A'},
        {'Issuer': 'Seller-B'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'Issuer'): (2, 'Seller-B')},
        digest(['alias', 'orphan-source']))
    with pytest.raises(ValueError, match='different documents'):
        extract_fields(profile, [DocumentField(
            row=0, name='issuer', page=2, quote='Seller-B')], None,
            identity_fields=('number',))


def test_cross_page_number_alias_rejects_another_document():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'invoice_no: INV-B\nIssuer: Seller-B'}]
    profile = pdf_profile('number-alias-docs', [
        {'number': 'INV-A'},
        {'invoice_no': 'INV-B', 'Issuer': 'Seller-B'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'invoice_no'): (2, 'INV-B'),
               (1, 'Issuer'): (2, 'Seller-B')}, digest(['number-alias', 'different']))
    with pytest.raises(ValueError, match='different documents'):
        extract_fields(profile, [DocumentField(
            row=0, name='issuer', page=2, quote='Seller-B')], None,
            identity_fields=('number',))


def test_cross_page_number_alias_allows_the_same_document():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'invoice_no: INV-A\nIssuer: Seller-A'}]
    profile = pdf_profile('number-alias-same', [
        {'number': 'INV-A'},
        {'invoice_no': 'INV-A', 'Issuer': 'Seller-A'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'invoice_no'): (2, 'INV-A'),
               (1, 'Issuer'): (2, 'Seller-A')}, digest(['number-alias', 'same']))
    updated = extract_fields(profile, [DocumentField(
        row=0, name='issuer', page=2, quote='Seller-A')], None,
        identity_fields=('number',))
    assert updated.records[0]['issuer'] == 'Seller-A'


def test_cross_page_continuation_rejects_an_unlabeled_other_document_number():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'Invoice INV-B\ncurrency: CNY'}]
    profile = pdf_profile('unlabeled-other-doc', [
        {'number': 'INV-A'},
        {'currency': 'CNY'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'currency'): (2, 'CNY')},
        digest(['unlabeled', 'other-document']))
    with pytest.raises(ValueError, match='different documents'):
        extract_fields(profile, [DocumentField(
            row=0, name='currency', page=2, quote='CNY')], None,
            identity_fields=('number',))


def test_cross_page_continuation_allows_the_same_unlabeled_document_number():
    pages = [{'page': 1, 'text': 'number: INV-A'},
             {'page': 2, 'text': 'Invoice INV-A\ncurrency: CNY'}]
    profile = pdf_profile('unlabeled-same-doc', [
        {'number': 'INV-A'},
        {'currency': 'CNY'},
    ], pages, {(0, 'number'): (1, 'INV-A'), (1, 'currency'): (2, 'CNY')},
        digest(['unlabeled', 'same-document']))
    updated = extract_fields(profile, [DocumentField(
        row=0, name='currency', page=2, quote='CNY')], None,
        identity_fields=('number',))
    assert updated.records == [{'number': 'INV-A', 'currency': 'CNY'}]
