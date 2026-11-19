"""Partial coverage reuses a verified mapping but still lists its gaps.

RU1 / T53 C-03-2: a REST source with one keyless record and a PDF source with
a blank OCR page make ``coverage=partial``.  That must not force a fresh
proposal every time: the structure fingerprint still matches the verified
mapping, and the preview can show the remaining gaps.  Saving stays blocked
until the user disposes of them (or explicitly chooses a partial save).
"""
import pytest

from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import CoverageGap, SourceProfile, SourceSelection
from dataagent_contracts.ontology import MappingSpec, ReviewDecision
from dataagent_ontology.identity import digest
from dataagent_workbench.adapters.layer_client import DataLayerProbeError
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.intake_service import PreviewBlocked
from dataagent_workbench.service_tools import invoke
from test_intake_repairs import (StubProbeClient, basic_bindings, pdf_profile,
                                proposal_for, single_setup, start)

REST = 'api'
REST_FINGERPRINT = digest(['api', 'rest invoice list'])


def rest_profile(records, *, key_gap=False, fields=None):
    """A REST observation; a missing /code is the expected keyless record."""
    revision = 'sha256:rest-fixture'
    anchors = {}
    for index, row in enumerate(records):
        for field, value in row.items():
            if value is None:
                continue
            anchors[f'{index}.{field}'] = [SourceAnchor(
                source_ref=REST, source_revision=revision,
                selector={'kind': 'json_pointer',
                          'pointer': f'/items/{index}{field}'})]
    gaps = []
    issues = []
    if key_gap:
        gaps.append(CoverageGap(partition=1, code='key_missing'))
        issues.extend({'code': 'key_missing', 'partition': 1,
                       'field': '/code', 'row': index}
                      for index, row in enumerate(records) if not row.get('/code'))
    return SourceProfile(
        source_id=REST, source_revision=revision, kind='rest',
        records=records, fields=fields or ['/code', '/amount', '/currency', '/issuer'],
        anchors=anchors,
        metadata={'structure_fingerprint': REST_FINGERPRINT},
        total_partitions=1, completed_partitions=[1], gaps=gaps, issues=issues)


REST_BINDINGS = {
    'number': {'source_field': '/code'},
    'amount': {'source_field': '/amount', 'transform': 'decimal'},
    'currency': {'source_field': '/currency'},
    'issuer': {'source_field': '/issuer'},
}
REST_ALTERNATE_ID = {
    **REST_BINDINGS,
    'number': {'source_field': '/invoice_no'},
}


def rest_proposal(wb, session, bindings=REST_BINDINGS):
    source = next(item for item in wb.intake.inference_request(
        session.id, wb.ctx)['sources'] if item['source_id'] == REST)
    return MappingSpec(id='candidate', revision='1', ontology_revision='procurement@1',
                       source_fingerprint=source['structure_fingerprint'],
                       bindings=bindings)


def rest_records(*, keyless):
    records = [{'/code': 'INV-1', '/amount': '100.00',
                '/currency': 'CNY', '/issuer': 'Alpha'}]
    if keyless:
        records.append({'/amount': '200.00', '/currency': 'CNY', '/issuer': 'Beta'})
    return records


def test_rest_key_missing_partial_save_is_reused_with_the_gap_listed(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({REST: rest_profile(
        rest_records(keyless=True), key_gap=True)})
    first = wb.intake.advance(start(wb, [SourceSelection(
        source_id=REST, kind='rest', locator_ref='invoice-api')]).session_id, wb.ctx)
    assert first.phase == 'needs_input'
    preview = wb.intake.submit_proposal(first.id, rest_proposal(wb, first),
                                        first.revision, wb.ctx)
    assert any(issue['code'] == 'ontology.identity_unresolved'
               and issue['source_id'] == REST for issue in preview.issues)
    current = wb.sessions.get(first.id, wb.ctx)
    saved = invoke(wb, 'mapping_apply', {
        'session_id': first.id, 'expected_revision': current.revision,
        'decision': {'preview_ref': preview.id + '@' + preview.revision,
                     'target_scope': 'mapping'},
        'allow_partial': True, 'reason': '缺键记录挂起，先保存可核对对象',
    }).data
    assert saved['partial'] is True
    assert saved['unidentified_records']
    assert wb.sessions.get(first.id, wb.ctx).phase == 'saved'

    # A structurally identical second intake must reuse the verified mapping.
    second = wb.intake.advance(start(wb, [SourceSelection(
        source_id=REST, kind='rest', locator_ref='invoice-api')], 'g2').session_id, wb.ctx)
    assert second.phase == 'preview'
    view = wb.intake.view(second.id, wb.ctx)
    assert view['mapping_reused'] is True
    assert view['mapping_reuse_reason'] is None
    keyless, = [issue for issue in view['preview']['issues']
                if issue['code'] == 'ontology.identity_unresolved']
    assert keyless['source_id'] == REST
    assert keyless['gaps'] == [{'code': 'key_missing', 'partition': 1}]
    assert keyless['gap'] == {'code': 'key_missing', 'partitions': [1]}
    assert keyless['gap_records'][0]['field'] == '/code'

    # Reuse never auto-saves: the keyless record still blocks a whole save.
    with pytest.raises(PreviewBlocked) as blocked:
        wb.intake.apply(second.id, ReviewDecision(
            preview_ref=view['preview']['id'] + '@' + view['preview']['revision'],
            target_scope='mapping'), wb.sessions.get(second.id, wb.ctx).revision, wb.ctx)
    assert str(blocked.value) == 'preview contains unresolved issues'
    assert wb.sessions.get(second.id, wb.ctx).phase == 'preview'
    assert 'release' not in wb.sessions.get(second.id, wb.ctx).selected_versions


def test_probe_key_missing_with_complete_mapped_identity_still_blocks_save(tmp_path):
    """A mapped identity from another column must not erase the probe-key gap."""
    fields = ['/code', '/invoice_no', '/amount', '/currency', '/issuer']
    records = [
        {'/code': 'INV-1', '/invoice_no': 'EXT-1', '/amount': '100.00',
         '/currency': 'CNY', '/issuer': 'Alpha'},
        {'/code': 'INV-2', '/invoice_no': 'EXT-2', '/amount': '200.00',
         '/currency': 'CNY', '/issuer': 'Beta'},
    ]
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({REST: rest_profile(records, fields=fields)})
    first = wb.intake.advance(start(wb, [SourceSelection(
        source_id=REST, kind='rest', locator_ref='invoice-api')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(
        first.id, rest_proposal(wb, first, REST_ALTERNATE_ID), first.revision, wb.ctx)
    assert preview.issues == []
    session = wb.sessions.get(first.id, wb.ctx)
    wb.intake.apply(first.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(first.id, wb.ctx).phase == 'saved'

    # The second probe reports the configured /code key missing, but the
    # mapping still resolves the object through /invoice_no.  No identity issue
    # is produced; the gap itself must remain visible and blocking.
    keyless = [records[0], {key: value for key, value in records[1].items()
                            if key != '/code'}]
    wb.layer_client = StubProbeClient({REST: rest_profile(
        keyless, key_gap=True, fields=fields)})
    second = wb.intake.advance(start(wb, [SourceSelection(
        source_id=REST, kind='rest', locator_ref='invoice-api')], 'g2').session_id, wb.ctx)
    assert second.phase == 'preview'
    view = wb.intake.view(second.id, wb.ctx)
    assert view['mapping_reused'] is True
    assert not [issue for issue in view['preview']['issues']
                if issue['code'] == 'ontology.identity_unresolved']
    gap, = [issue for issue in view['preview']['issues']
            if issue['code'] == 'ontology.incomplete_source'
            and issue.get('source_id') == REST]
    assert gap['coverage'] == 'partial'
    assert gap['partitions'] == [1]
    assert gap['row'] == 1
    assert gap['target'] == '/code'
    assert gap['gap'] == {'code': 'key_missing', 'partitions': [1]}
    assert gap['gap_records'] == [{'code': 'key_missing', 'partition': 1,
                                   'field': '/code', 'row': 1}]
    options = wb.intake.disposition_options(
        wb.sessions.get(second.id, wb.ctx), view['preview'])
    option, = [item for item in options
               if item['action'] == 'partition_not_applicable'
               and item.get('source_id') == REST
               and item.get('gap') == 'key_missing']
    assert option['partition'] == 1
    assert '仍可识别' in option['reason_hint']

    current = wb.sessions.get(second.id, wb.ctx)
    with pytest.raises(PreviewBlocked) as blocked:
        wb.intake.apply(second.id, ReviewDecision(
            preview_ref=view['preview']['id'] + '@' + view['preview']['revision'],
            target_scope='mapping'), current.revision, wb.ctx)
    assert str(blocked.value) == 'preview contains unresolved issues'
    # A source-level key gap is not silently bypassed by a partial save either.
    with pytest.raises(PreviewBlocked):
        wb.intake.apply(second.id, ReviewDecision(
            preview_ref=view['preview']['id'] + '@' + view['preview']['revision'],
            target_scope='mapping'), current.revision, wb.ctx, allow_partial=True)
    assert wb.sessions.get(second.id, wb.ctx).phase == 'preview'
    assert 'release' not in wb.sessions.get(second.id, wb.ctx).selected_versions

    # The user can acknowledge the source key gap explicitly; only then does
    # the batch save become available.
    invoke(wb, 'intake_dispose', {
        'session_id': second.id,
        'expected_revision': current.revision,
        'action': 'partition_not_applicable', 'source_id': REST, 'partition': 1,
        'reason': '该页缺 /code，但映射用 /invoice_no 完整识别对象',
    })
    session = wb.sessions.get(second.id, wb.ctx)
    clean = wb.intake.submit_proposal(
        second.id, rest_proposal(wb, session, REST_ALTERNATE_ID),
        session.revision, wb.ctx)
    assert clean.issues == []
    session = wb.sessions.get(second.id, wb.ctx)
    wb.intake.apply(second.id, ReviewDecision(
        preview_ref=clean.id + '@' + clean.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(second.id, wb.ctx).phase == 'saved'


def test_excluding_the_only_keyless_record_clears_the_rest_key_gap(tmp_path):
    """Excluding the keyless row is a record-level disposition of its gap."""
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({REST: rest_profile(
        rest_records(keyless=True), key_gap=True)})
    first = wb.intake.advance(start(wb, [SourceSelection(
        source_id=REST, kind='rest', locator_ref='invoice-api')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(first.id, rest_proposal(wb, first),
                                        first.revision, wb.ctx)
    assert any(issue['code'] == 'ontology.identity_unresolved'
               and issue['source_id'] == REST and issue['row'] == 1
               for issue in preview.issues)
    invoke(wb, 'intake_dispose', {
        'session_id': first.id,
        'expected_revision': wb.sessions.get(first.id, wb.ctx).revision,
        'action': 'exclude_record', 'source_id': REST, 'record': 1,
        'reason': '该行缺少 /code，不进入本次对象',
    })
    session = wb.sessions.get(first.id, wb.ctx)
    clean = wb.intake.submit_proposal(first.id, rest_proposal(wb, first),
                                      session.revision, wb.ctx)
    assert clean.issues == []
    wb.intake.apply(first.id, ReviewDecision(
        preview_ref=clean.id + '@' + clean.revision, target_scope='mapping'),
        wb.sessions.get(first.id, wb.ctx).revision, wb.ctx)
    assert wb.sessions.get(first.id, wb.ctx).phase == 'saved'


def test_excluding_one_keyless_record_keeps_another_gap_on_the_same_page(tmp_path):
    """A page-level gap must not hide a second, unexcluded keyless row."""
    fields = ['/code', '/invoice_no', '/amount', '/currency', '/issuer']
    records = [
        {'/code': 'INV-1', '/invoice_no': 'EXT-1', '/amount': '100.00',
         '/currency': 'CNY', '/issuer': 'Alpha'},
        {'/invoice_no': 'EXT-2', '/amount': '200.00',
         '/currency': 'CNY', '/issuer': 'Beta'},
        {'/invoice_no': 'EXT-3', '/amount': '300.00',
         '/currency': 'CNY', '/issuer': 'Gamma'},
    ]
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({REST: rest_profile(
        records, key_gap=True, fields=fields)})
    first = wb.intake.advance(start(wb, [SourceSelection(
        source_id=REST, kind='rest', locator_ref='invoice-api')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(
        first.id, rest_proposal(wb, first, REST_ALTERNATE_ID), first.revision, wb.ctx)
    assert not [issue for issue in preview.issues
                if issue['code'] == 'ontology.identity_unresolved']
    assert sorted(issue['row'] for issue in preview.issues
                  if issue['code'] == 'ontology.incomplete_source') == [1, 2]

    invoke(wb, 'intake_dispose', {
        'session_id': first.id,
        'expected_revision': wb.sessions.get(first.id, wb.ctx).revision,
        'action': 'exclude_record', 'source_id': REST, 'record': 1,
        'reason': '只排除第一条缺键行',
    })
    session = wb.sessions.get(first.id, wb.ctx)
    blocked = wb.intake.submit_proposal(
        first.id, rest_proposal(wb, first, REST_ALTERNATE_ID),
        session.revision, wb.ctx)
    remaining = [issue for issue in blocked.issues
                 if issue['code'] == 'ontology.incomplete_source'
                 and issue.get('source_id') == REST]
    assert [issue['row'] for issue in remaining] == [2]
    assert remaining[0]['gap'] == {'code': 'key_missing', 'partitions': [1]}
    with pytest.raises(PreviewBlocked):
        wb.intake.apply(first.id, ReviewDecision(
            preview_ref=blocked.id + '@' + blocked.revision,
            target_scope='mapping'), wb.sessions.get(first.id, wb.ctx).revision, wb.ctx)

    invoke(wb, 'intake_dispose', {
        'session_id': first.id,
        'expected_revision': wb.sessions.get(first.id, wb.ctx).revision,
        'action': 'exclude_record', 'source_id': REST, 'record': 2,
        'reason': '第二条缺键行也不进入本次对象',
    })
    session = wb.sessions.get(first.id, wb.ctx)
    clean = wb.intake.submit_proposal(
        first.id, rest_proposal(wb, first, REST_ALTERNATE_ID),
        session.revision, wb.ctx)
    assert clean.issues == []
    wb.intake.apply(first.id, ReviewDecision(
        preview_ref=clean.id + '@' + clean.revision, target_scope='mapping'),
        wb.sessions.get(first.id, wb.ctx).revision, wb.ctx)
    assert wb.sessions.get(first.id, wb.ctx).phase == 'saved'


def blank_page(fingerprint):
    pages = [{'page': 1, 'text': 'number: INV-1\namount: 1260.00\ncurrency: CNY'},
             {'page': 2, 'text': ''}]
    profile = pdf_profile('doc', [{'number': 'INV-1', 'amount': '1260.00',
                                   'currency': 'CNY'}], pages,
                          {(0, 'number'): (1, 'INV-1'),
                           (0, 'amount'): (1, '1260.00'),
                           (0, 'currency'): (1, 'CNY')}, fingerprint)
    return profile.model_copy(update={
        'total_partitions': 2, 'completed_partitions': [1],
        'gaps': [CoverageGap(partition=2, code='ocr_empty', detail='blank page')],
    })


def pdf_proposal(wb, session):
    source = next(item for item in wb.intake.inference_request(
        session.id, wb.ctx)['sources'] if item['source_id'] == 'doc')
    return MappingSpec(id='candidate', revision='1', ontology_revision='procurement@1',
                       source_fingerprint=source['structure_fingerprint'],
                       bindings={'number': {'source_field': 'number'},
                                 'amount': {'source_field': 'amount'},
                                 'currency': {'source_field': 'currency'}})


def test_ocr_empty_partial_reuses_mapping_and_suggests_disposition(tmp_path):
    fingerprint = digest(['doc', 'blank second page'])
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'doc': blank_page(fingerprint)})
    first = wb.intake.advance(start(wb, [SourceSelection(
        source_id='doc', kind='file', locator_ref='mixed.pdf')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(first.id, pdf_proposal(wb, first),
                                        first.revision, wb.ctx)
    assert any(issue['code'] == 'ontology.incomplete_source' for issue in preview.issues)
    disposed = invoke(wb, 'intake_dispose', {
        'session_id': first.id,
        'expected_revision': wb.sessions.get(first.id, wb.ctx).revision,
        'action': 'partition_not_applicable', 'source_id': 'doc', 'partition': 2,
        'reason': '第 2 页为空白页，确认无需补录',
    }).data
    assert disposed['entry']['partition'] == 2
    session = wb.sessions.get(first.id, wb.ctx)
    clean = wb.intake.submit_proposal(first.id, pdf_proposal(wb, session),
                                      session.revision, wb.ctx)
    assert clean.issues == []
    session = wb.sessions.get(first.id, wb.ctx)
    wb.intake.apply(first.id, ReviewDecision(
        preview_ref=clean.id + '@' + clean.revision, target_scope='mapping'),
        session.revision, wb.ctx)
    assert wb.sessions.get(first.id, wb.ctx).phase == 'saved'

    second = wb.intake.advance(start(wb, [SourceSelection(
        source_id='doc', kind='file', locator_ref='mixed.pdf')], 'g2').session_id, wb.ctx)
    assert second.phase == 'preview'
    view = wb.intake.view(second.id, wb.ctx)
    assert view['mapping_reused'] is True
    gap, = [issue for issue in view['preview']['issues']
            if issue['code'] == 'ontology.incomplete_source']
    assert gap['partitions'] == [2]
    assert gap['coverage'] == 'partial'
    hint = view['inheritance']
    assert hint['count'] == 1
    assert hint['operations'] == ['intake_dispose']
    assert hint['disposition_count'] == 1
    assert hint['dispositions'][0]['action'] == 'partition_not_applicable'
    assert hint['dispositions'][0]['partition'] == 2
    assert '可继承' in hint['disposition_message']

    with pytest.raises(PreviewBlocked):
        wb.intake.apply(second.id, ReviewDecision(
            preview_ref=view['preview']['id'] + '@' + view['preview']['revision'],
            target_scope='mapping'), wb.sessions.get(second.id, wb.ctx).revision, wb.ctx)
    assert wb.sessions.get(second.id, wb.ctx).phase == 'preview'


class FailingProbeClient:
    def probe(self, selection, ctx, workspace, *, previous=None, budget_seconds=None):
        raise DataLayerProbeError('source_unreadable', 'source file is no longer readable')


def test_unreadable_source_is_not_reused(tmp_path):
    wb, session = single_setup(tmp_path)
    preview = wb.intake.submit_proposal(
        session.id, proposal_for(session, wb, 'f', basic_bindings()),
        session.revision, wb.ctx)
    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        current.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'

    wb.layer_client = FailingProbeClient()
    broken = wb.intake.advance(start(wb, [SourceSelection(
        source_id='f', kind='file', locator_ref='invoice.csv')], 'g2').session_id, wb.ctx)
    assert broken.phase == 'needs_input'
    assert broken.next_actions == ['repair_source']
    view = wb.intake.view(broken.id, wb.ctx)
    assert view['mapping_reused'] is False
    assert view['preview'] is None
    issue, = [item for item in broken.issues if item['code'] == 'intake.probe_failed']
    assert issue['error_code'] == 'source_unreadable'


def test_exclude_record_hint_survives_same_source_revision(tmp_path):
    from test_intake_repairs import csv_profile

    profile = csv_profile('ledger', [
        {'number': 'number', 'amount_minor': 'amount_minor', 'currency': 'currency'},
        {'number': 'INV-9', 'amount_minor': '90000', 'currency': 'CNY'},
    ])
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'ledger': profile})
    first = wb.intake.advance(start(wb, [SourceSelection(
        source_id='ledger', kind='file', locator_ref='ledger.csv')]).session_id, wb.ctx)
    wb.intake.submit_proposal(first.id, proposal_for(first, wb, 'ledger', basic_bindings()),
                              first.revision, wb.ctx)
    invoke(wb, 'intake_dispose', {
        'session_id': first.id,
        'expected_revision': wb.sessions.get(first.id, wb.ctx).revision,
        'action': 'exclude_record', 'source_id': 'ledger', 'record': 0,
        'reason': '第 2 行是表头，不是单据',
    })
    session = wb.sessions.get(first.id, wb.ctx)
    clean = wb.intake.submit_proposal(
        first.id, proposal_for(session, wb, 'ledger', basic_bindings()),
        session.revision, wb.ctx)
    assert clean.issues == []
    session = wb.sessions.get(first.id, wb.ctx)
    wb.intake.apply(first.id, ReviewDecision(
        preview_ref=clean.id + '@' + clean.revision, target_scope='mapping'),
        session.revision, wb.ctx)

    second = wb.intake.advance(start(wb, [SourceSelection(
        source_id='ledger', kind='file', locator_ref='ledger.csv')], 'g2').session_id, wb.ctx)
    view = wb.intake.view(second.id, wb.ctx)
    assert view['mapping_reused'] is True
    hint = view['inheritance']
    assert hint['count'] == 1
    assert hint['disposition_count'] == 1
    assert hint['dispositions'][0]['action'] == 'exclude_record'
    assert hint['dispositions'][0]['record'] == 0
    assert '可继承' in hint['disposition_message']
