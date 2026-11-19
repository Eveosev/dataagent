"""Audited source dispositions for FDE-3.

A preview previously blocked on a blank PDF page or a header row had no
outcome other than starting a new task.  These tests pin the two audited
actions: mark a partition not applicable and exclude one source record.
"""
import json

import pytest

from dataagent_contracts.intake import CoverageGap, SourceSelection
from dataagent_contracts.ontology import MappingSpec
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.mcp_server import handle
from dataagent_workbench.service_tools import invoke
from test_intake_repairs import StubProbeClient, csv_profile, pdf_profile, start


def bindings(source):
    fields = set(source['fields'])
    chosen = {}
    if 'number' in fields:
        chosen['number'] = {'source_field': 'number'}
    if 'amount_minor' in fields:
        chosen['amount'] = {'source_field': 'amount_minor', 'transform': 'minor_to_major'}
    elif 'amount' in fields:
        chosen['amount'] = {'source_field': 'amount'}
    if 'currency' in fields:
        chosen['currency'] = {'source_field': 'currency'}
    return chosen


def proposal_for_source(wb, session, source_id):
    source = next(item for item in wb.intake.inference_request(session.id, wb.ctx)['sources']
                  if item['source_id'] == source_id)
    return MappingSpec(id='candidate', revision='1', ontology_revision='procurement@1',
                       source_fingerprint=source['structure_fingerprint'],
                       bindings=bindings(source))


def blank_page_profile():
    pages = [{'page': 1, 'text': 'number: INV-1\namount: 1260.00\ncurrency: CNY'},
             {'page': 2, 'text': ''}]
    profile = pdf_profile('doc', [{'number': 'INV-1', 'amount': '1260.00', 'currency': 'CNY'}],
                          pages, {(0, 'number'): (1, 'INV-1'),
                                  (0, 'amount'): (1, '1260.00'),
                                  (0, 'currency'): (1, 'CNY')},
                          'sha256:blank-page-structure')
    return profile.model_copy(update={
        'total_partitions': 2, 'completed_partitions': [1],
        'gaps': [CoverageGap(partition=2, code='ocr_empty', detail='blank page')],
    })


def test_partition_not_applicable_clears_incomplete_source_and_is_audited(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'doc': blank_page_profile()})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='doc', kind='file', locator_ref='mixed.pdf')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, proposal_for_source(wb, session, 'doc'),
                                        session.revision, wb.ctx)
    assert any(issue['code'] == 'ontology.incomplete_source' for issue in preview.issues)

    result = invoke(wb, 'intake_dispose', {
        'session_id': session.id, 'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
        'action': 'partition_not_applicable', 'source_id': 'doc', 'partition': 2,
        'reason': '第 2 页为空白页，用户确认无需补录',
    }).data
    assert result['entry']['partition'] == 2
    assert result['entry']['reason'] == '第 2 页为空白页，用户确认无需补录'
    assert result['entry']['subject_ref'] == wb.subject
    assert result['entry']['recorded_at']
    assert result['disposition_ref'].startswith(session.id + '@')
    assert wb.sessions.get(session.id, wb.ctx).phase == 'needs_input'

    disposed = wb.sessions.get(session.id, wb.ctx)
    proposal = proposal_for_source(wb, disposed, 'doc')
    preview = wb.intake.submit_proposal(disposed.id, proposal, disposed.revision, wb.ctx)
    assert not any(issue['code'] == 'ontology.incomplete_source' for issue in preview.issues)
    stored = wb.store.get('preview', preview.id, preview.revision, scope=wb.scope)['body']
    assert stored['extensions']['intake.dispositions'][0]['action'] == 'partition_not_applicable'
    assert stored['extensions']['intake.dispositions'][0]['reason'].startswith('第 2 页')

    # The disposition is durable: the audited entry and its review record both
    # keep who/when/why, and a fresh preview still carries it.
    entry, = wb.store.query('disposition', wb.scope)[0]['body']['entries']
    assert entry['subject_ref'] == wb.subject and entry['recorded_at'] and entry['reason']
    reviews = [row for row in wb.store.query('review', wb.scope)
               if row['body'].get('decision', {}).get('changes', {}).get('disposition')]
    assert reviews and reviews[0]['body']['subject_ref'] == wb.subject

    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, _save_decision(preview), session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


def test_partition_numeric_string_is_accepted_as_integer(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'doc': blank_page_profile()})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='doc', kind='file', locator_ref='mixed.pdf')]).session_id, wb.ctx)
    wb.intake.submit_proposal(session.id, proposal_for_source(wb, session, 'doc'),
                              session.revision, wb.ctx)

    result = invoke(wb, 'intake_dispose', {
        'session_id': session.id,
        'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
        'action': 'partition_not_applicable', 'source_id': 'doc', 'partition': '2',
        'reason': '第 2 页为空白页，用户确认无需补录',
    }).data
    assert result['entry']['partition'] == 2
    disposed = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(
        disposed.id, proposal_for_source(wb, disposed, 'doc'),
        disposed.revision, wb.ctx)
    assert not any(issue['code'] == 'ontology.incomplete_source'
                   for issue in preview.issues)


def test_exclude_record_drops_header_row_and_keeps_the_rest(tmp_path):
    wb = Workbench(tmp_path)
    profile = csv_profile('ledger', [
        {'number': 'number', 'amount_minor': 'amount_minor', 'currency': 'currency'},
        {'number': 'INV-9', 'amount_minor': '90000', 'currency': 'CNY'},
    ])
    wb.layer_client = StubProbeClient({'ledger': profile})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='ledger', kind='file', locator_ref='ledger.csv')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, proposal_for_source(wb, session, 'ledger'),
                                        session.revision, wb.ctx)
    assert preview.issues

    result = invoke(wb, 'intake_dispose', {
        'session_id': session.id, 'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
        'action': 'exclude_record', 'source_id': 'ledger', 'record': 0,
        'reason': '第 2 行是表头，不是单据',
    }).data
    assert result['entry']['record'] == 0
    assert result['entry']['record_values']['number'] == 'number'

    disposed = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(disposed.id,
                                        proposal_for_source(wb, disposed, 'ledger'),
                                        disposed.revision, wb.ctx)
    assert preview.issues == []
    assert [instance.values['number'] for instance in preview.instances] == ['INV-9']
    stored = wb.store.get('preview', preview.id, preview.revision, scope=wb.scope)['body']
    assert stored['extensions']['intake.dispositions'][0]['record'] == 0

    session = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, _save_decision(preview), session.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


def test_disposition_rejects_blank_reason_before_writing(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'ledger': csv_profile(
        'ledger', [{'number': 'INV-9', 'amount_minor': '90000', 'currency': 'CNY'}])})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='ledger', kind='file', locator_ref='ledger.csv')]).session_id, wb.ctx)

    response = handle(wb, {
        'method': 'tools/call',
        'params': {'name': 'intake_dispose', 'arguments': {
            'session_id': session.id, 'expected_revision': session.revision,
            'action': 'partition_not_applicable', 'source_id': 'ledger',
            'partition': 1, 'reason': ' \t ',
        }},
    })
    assert response['isError'] is True
    error = json.loads(response['content'][0]['text'])
    assert error['error'] == 'invalid_input'
    assert '处置原因不能为空' in error['detail']
    assert not wb.store.query('disposition', wb.scope)

    blank = _dispose('partition_not_applicable', partition=1)
    blank.reason = ' \t '
    with pytest.raises(ValueError, match='处置原因不能为空'):
        wb.intake.dispose(session.id, blank, session.revision, wb.ctx)
    assert not wb.store.query('disposition', wb.scope)


def test_disposition_rejects_unknown_partition_record_and_duplicate(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'ledger': csv_profile(
        'ledger', [{'number': 'INV-9', 'amount_minor': '90000', 'currency': 'CNY'}])})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='ledger', kind='file', locator_ref='ledger.csv')]).session_id, wb.ctx)
    wb.intake.submit_proposal(session.id, proposal_for_source(wb, session, 'ledger'),
                              session.revision, wb.ctx)

    with pytest.raises(ValueError, match='partition is not part'):
        invoke(wb, 'intake_dispose', {
            'session_id': session.id, 'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
            'action': 'partition_not_applicable', 'source_id': 'ledger', 'partition': 99,
            'reason': '不存在的分区'})
    with pytest.raises(ValueError, match='record index is outside'):
        invoke(wb, 'intake_dispose', {
            'session_id': session.id, 'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
            'action': 'exclude_record', 'source_id': 'ledger', 'record': 9,
            'reason': '不存在的记录'})
    wb.intake.dispose(session.id, _dispose('exclude_record', record=0),
                      wb.sessions.get(session.id, wb.ctx).revision, wb.ctx)
    with pytest.raises(ValueError, match='already recorded'):
        wb.intake.dispose(session.id, _dispose('exclude_record', record=0),
                          wb.sessions.get(session.id, wb.ctx).revision, wb.ctx)


class _Dispose:
    def __init__(self, action, *, partition=None, record=None, source_id='ledger'):
        self.action, self.partition, self.record = action, partition, record
        self.source_id = source_id
        self.reason = '测试处置'


def _dispose(action, *, partition=None, record=None, source_id='ledger'):
    return _Dispose(action, partition=partition, record=record, source_id=source_id)


def _save_decision(preview):
    from dataagent_contracts.ontology import ReviewDecision
    return ReviewDecision(preview_ref=preview.id + '@' + preview.revision,
                          target_scope='mapping')
