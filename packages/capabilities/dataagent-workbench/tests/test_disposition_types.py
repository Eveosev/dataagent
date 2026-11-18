"""Typed source dispositions for FDE2-05/FDE2-06.

A task may hold sources the pinned concept's mapping does not use (one
ontology, two concepts, two materials in one task).  The preview must name
each unused source once at source level instead of mapping every row, and the
audited way out is "this task does not use the source".  Row-level escapes
are typed by what the row is: only a record that reads like the header may be
excluded, a conversion failure on real data must be corrected or re-mapped,
and one row no longer counts the same failed column twice.
"""
import pytest
from fastapi.testclient import TestClient

from dataagent_contracts.intake import SourceSelection
from dataagent_contracts.ontology import FieldBinding, MappingSpec, ReviewDecision
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.intake_service import PreviewBlocked
from dataagent_workbench.interfaces.http_api import create_app
from dataagent_workbench.service_tools import invoke
from dataagent_workbench.view_service import ViewService
from test_intake_repairs import StubProbeClient, csv_profile, start
from test_clause_records import (clause_records, extract_records,
                                 setup as clause_setup, standard_proposal)


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


def proposal_for(wb, session, source_id):
    source = next(item for item in wb.intake.inference_request(session.id, wb.ctx)['sources']
                  if item['source_id'] == source_id)
    return MappingSpec(id='candidate', revision='1', ontology_revision='procurement@1',
                       source_fingerprint=source['structure_fingerprint'],
                       bindings=bindings(source))


class _Dispose:
    def __init__(self, action, *, partition=None, record=None, source_id='extra'):
        self.action, self.partition, self.record = action, partition, record
        self.source_id = source_id
        self.reason = '测试处置'


def _dispose(action, *, partition=None, record=None, source_id='extra'):
    return _Dispose(action, partition=partition, record=record, source_id=source_id)


def two_source_setup(tmp_path, extra_rows=None):
    """A mapped CSV plus a second material the pinned concept never maps."""
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'rows': csv_profile('rows', [{'number': 'INV-1', 'amount_minor': '126000',
                                      'currency': 'CNY'}]),
        'extra': csv_profile('extra', extra_rows or [
            {'number': f'X-{index}', 'amount_minor': '1000', 'currency': 'CNY'}
            for index in range(1, 6)]),
    })
    session = wb.intake.advance(start(wb, [
        SourceSelection(source_id='rows', kind='file', locator_ref='rows.csv'),
        SourceSelection(source_id='extra', kind='file', locator_ref='extra.csv')]).session_id, wb.ctx)
    return wb, session


def test_unmapped_source_is_one_source_level_issue_not_row_objects(tmp_path):
    wb, session = two_source_setup(tmp_path)
    # The agent proposes a single-source mapping; the other material stays out.
    preview = wb.intake.submit_proposal(session.id, proposal_for(wb, session, 'rows'),
                                        session.revision, wb.ctx)
    assert [(issue['code'], issue['source_id']) for issue in preview.issues
            if issue['code'] == 'ontology.source_unmapped'] == \
        [('ontology.source_unmapped', 'extra')]
    # Only the mapped source's rows become objects and row-level problems.
    assert [instance.values['number'] for instance in preview.instances] == ['INV-1']
    assert not any(issue['code'] in {'ontology.conversion_failed',
                                     'ontology.required_value_missing',
                                     'ontology.identity_unresolved'}
                   for issue in preview.issues)
    summary = wb.intake.view(session.id, wb.ctx)
    item = next(issue for issue in summary['preview']['issues']
                if issue['code'] == 'ontology.source_unmapped')
    assert item['object'] == '来源 extra.csv'
    assert item['reason'] == '该来源未用于当前映射'
    assert [option['reason_hint'] for option in item['actions']] == ['本任务不使用该来源']


def test_source_proposal_subset_keeps_the_other_source_unmapped(tmp_path):
    wb, session = two_source_setup(tmp_path)
    preview = wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, session, 'rows')}, session.revision, wb.ctx)
    assert [issue['source_id'] for issue in preview.issues
            if issue['code'] == 'ontology.source_unmapped'] == ['extra']
    assert set(preview.source_revisions) == {'rows'}
    # A full set of proposals still maps every source and reports nothing.
    both = wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, session, 'rows'),
                     'extra': proposal_for(wb, session, 'extra')},
        wb.sessions.get(session.id, wb.ctx).revision, wb.ctx)
    assert both.issues == []
    assert len(both.instances) == 6
    # Narrowing through the multi-source endpoint (the web's rebuild path)
    # must drop the removed source's scope entry as well.
    current = wb.sessions.get(session.id, wb.ctx)
    narrowed = wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, current, 'rows')},
        current.revision, wb.ctx)
    assert set(narrowed.source_revisions) == {'rows'}
    assert 'mapping:extra' not in wb.sessions.get(session.id, wb.ctx).selected_versions
    with pytest.raises(ValueError, match='one mapping for each observed source'):
        wb.intake.submit_source_proposals(
            session.id, {'unknown': proposal_for(wb, session, 'rows')},
            wb.sessions.get(session.id, wb.ctx).revision, wb.ctx)


def test_ignore_source_disposition_is_audited_clears_the_issue_and_allows_save(tmp_path):
    wb, session = two_source_setup(tmp_path)
    wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, session, 'rows')}, session.revision, wb.ctx)
    # Without the disposition the source-level issue blocks the whole batch.
    blocked = wb.sessions.get(session.id, wb.ctx)
    with pytest.raises(PreviewBlocked) as rejection:
        wb.intake.apply(session.id, ReviewDecision(
            preview_ref=blocked.selected_versions['preview'], target_scope='mapping'),
            blocked.revision, wb.ctx)
    assert any(issue['code'] == 'ontology.source_unmapped'
               for issue in rejection.value.issues)

    wb.intake.dispose(session.id, _dispose('ignore_source'), blocked.revision, wb.ctx)
    entry, = wb.store.query('disposition', wb.scope)[0]['body']['entries']
    assert entry['action'] == 'ignore_source'
    assert entry['source_id'] == 'extra' and entry['reason'] == '测试处置'
    assert entry['subject_ref'] == wb.subject and entry['recorded_at']
    reviews = [row for row in wb.store.query('review', wb.scope)
               if row['body'].get('decision', {}).get('changes', {}).get('disposition')]
    assert reviews[0]['body']['subject_ref'] == wb.subject

    disposed = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_source_proposals(
        disposed.id, {'rows': proposal_for(wb, disposed, 'rows')}, disposed.revision, wb.ctx)
    assert preview.issues == []
    # The save no longer demands a mapping for the disposed source.
    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=current.selected_versions['preview'], target_scope='mapping'),
        current.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'
    with pytest.raises(ValueError, match='already recorded'):
        wb.intake.dispose(session.id, _dispose('ignore_source'),
                          wb.sessions.get(session.id, wb.ctx).revision, wb.ctx)


def test_narrowing_prunes_stale_draft_and_final_save_keeps_only_mapped_objects(tmp_path):
    wb, session = two_source_setup(tmp_path)
    stale = {
        source_id: {key: value.model_dump(mode='json')
                    for key, value in proposal_for(wb, session, source_id).bindings.items()}
        for source_id in ('rows', 'extra')
    }
    wb.intake.save_draft(session.id, {'source_bindings': stale}, session.revision, wb.ctx)

    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, current, 'rows')}, current.revision, wb.ctx)
    draft = wb.store.current('ui_draft', session.id, scope=wb.scope)
    # The narrowing proposal owns the scope: the old extra binding is gone
    # before the source disposition and final save.
    assert set(draft['body']['source_bindings']) == {'rows'}

    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.dispose(session.id, _dispose('ignore_source'), current.revision, wb.ctx)
    current = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, current, 'rows')}, current.revision, wb.ctx)
    assert preview.issues == []

    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=current.selected_versions['preview'], target_scope='mapping'),
        current.revision, wb.ctx)
    saved = wb.intake.view(session.id, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'
    assert [instance['values'].get('number') for instance in saved['preview']['instances']] == ['INV-1']


def test_ignore_source_over_the_wire_is_partition_not_applicable_without_partition(tmp_path):
    wb, session = two_source_setup(tmp_path)
    wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, session, 'rows')}, session.revision, wb.ctx)
    client = TestClient(create_app(wb))
    headers = {'x-dataagent-token': wb.token}
    posted = client.post(f'/api/sessions/{session.id}/dispositions', headers=headers, json={
        'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
        'action': 'partition_not_applicable', 'source_id': 'extra',
        'reason': '该材料属于另一个概念，本任务不使用',
    })
    assert posted.status_code == 200, posted.text
    # The audited entry says what it means, whatever the wire literal allows.
    entry = posted.json()['entry']
    assert entry['action'] == 'ignore_source'
    assert entry['source_id'] == 'extra'
    assert entry['reason'] == '该材料属于另一个概念，本任务不使用'
    assert 'partition' not in entry


def test_ignore_source_rejects_a_mapped_source_and_blank_reason(tmp_path):
    wb, session = two_source_setup(tmp_path)
    wb.intake.submit_source_proposals(
        session.id, {'rows': proposal_for(wb, session, 'rows')}, session.revision, wb.ctx)
    current = wb.sessions.get(session.id, wb.ctx)
    with pytest.raises(ValueError, match='source is used by the current mapping'):
        wb.intake.dispose(session.id, _dispose('ignore_source', source_id='rows'),
                          current.revision, wb.ctx)
    blank = _dispose('ignore_source')
    blank.reason = ' \t '
    with pytest.raises(ValueError, match='处置原因不能为空'):
        wb.intake.dispose(session.id, blank, current.revision, wb.ctx)
    assert not wb.store.query('disposition', wb.scope)


def bad_rows_setup(tmp_path):
    """One header-like record and one real record with a bad amount."""
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'ledger': csv_profile('ledger', [
        # Row 0 repeats the column names: a header the probe kept as data.
        {'number': 'number', 'amount_minor': 'amount_minor', 'currency': 'currency'},
        # Row 1 is a real document whose amount cannot be converted.
        {'number': 'INV-9', 'amount_minor': 'not-a-number', 'currency': 'CNY'},
    ])})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='ledger', kind='file', locator_ref='ledger.csv')]).session_id, wb.ctx)
    return wb, session


def test_exclude_record_is_offered_only_for_header_like_rows(tmp_path):
    wb, session = bad_rows_setup(tmp_path)
    preview = wb.intake.submit_proposal(session.id, proposal_for(wb, session, 'ledger'),
                                        session.revision, wb.ctx)
    conversions = {issue['row'] for issue in preview.issues
                   if issue['code'] == 'ontology.conversion_failed'}
    assert conversions == {0, 1}
    options = wb.intake.disposition_options(session, wb.store.get(
        'preview', preview.id, preview.revision, scope=wb.scope)['body'])
    excludes = [option for option in options if option['action'] == 'exclude_record']
    # Only the header-like row gets the escape hatch; the real row must be
    # corrected or re-mapped instead of being excluded as "irrelevant".
    assert [option['record'] for option in excludes] == [0]


def unmapped_regeneration_setup(tmp_path):
    """A mapped ledger with one header-like row plus a material never mapped."""
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'ledger': csv_profile('ledger', [
            {'number': 'number', 'amount_minor': 'amount_minor', 'currency': 'currency'},
            {'number': 'INV-1', 'amount_minor': '126000', 'currency': 'CNY'},
            {'number': 'INV-2', 'amount_minor': '90000', 'currency': 'CNY'},
            {'number': 'INV-3', 'amount_minor': '75000', 'currency': 'CNY'},
        ]),
        # A different structure (extra note column) so the single-source
        # proposal cannot accidentally match both observations.
        'unused': csv_profile('unused', [
            {'number': f'X-{index}', 'amount_minor': '1000', 'currency': 'CNY',
             'note': f'另一份材料 {index}'}
            for index in range(1, 5)]),
    })
    session = wb.intake.advance(start(wb, [
        SourceSelection(source_id='ledger', kind='file', locator_ref='ledger.csv'),
        SourceSelection(source_id='unused', kind='file', locator_ref='unused.csv'),
    ]).session_id, wb.ctx)
    return wb, session


def test_row_disposition_regen_keeps_the_unmapped_source_out(tmp_path):
    """FDE2-05: disposing one row then regenerating must not pull in the other
    material (the regression read 40 -> 126 problems and 20 -> 31 objects)."""
    wb, session = unmapped_regeneration_setup(tmp_path)
    preview = wb.intake.submit_proposal(session.id, proposal_for(wb, session, 'ledger'),
                                        session.revision, wb.ctx)
    # Four ledger records become objects; the unused material contributes none.
    assert len(preview.instances) == 4
    assert {instance.values['number'] for instance in preview.instances} == \
        {'number', 'INV-1', 'INV-2', 'INV-3'}
    current = wb.sessions.get(session.id, wb.ctx)
    assert 'mapping:ledger' in current.selected_versions
    assert 'mapping:unused' not in current.selected_versions
    assert len(wb.intake.view(session.id, wb.ctx)['preview']['issues']) == 2

    # Drop the header-like row through an audited disposition.
    wb.intake.dispose(session.id, _dispose('exclude_record', record=0, source_id='ledger'),
                      current.revision, wb.ctx)
    disposed = wb.sessions.get(session.id, wb.ctx)
    # Regenerating the preview from the durable mapping scope maps only the
    # ledger: the unused material stays one source-level issue instead of
    # turning every one of its rows into objects and row problems.
    regenerated = wb.intake.submit_source_proposals(
        session.id, {'ledger': proposal_for(wb, disposed, 'ledger')},
        disposed.revision, wb.ctx)
    assert len(regenerated.instances) == 3
    assert {instance.values['number'] for instance in regenerated.instances} == \
        {'INV-1', 'INV-2', 'INV-3'}
    assert set(regenerated.source_revisions) == {'ledger'}
    assert [(issue['code'], issue['source_id']) for issue in regenerated.issues] == \
        [('ontology.source_unmapped', 'unused')]
    assert not any(issue.get('row') is not None and issue.get('source_id') == 'unused'
                   for issue in regenerated.issues)

    # The audited "this task does not use the source" decision clears the
    # source-level issue; the mapped rows still build three objects.
    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.dispose(session.id, _dispose('ignore_source', source_id='unused'),
                      current.revision, wb.ctx)
    disposed = wb.sessions.get(session.id, wb.ctx)
    cleared = wb.intake.submit_source_proposals(
        session.id, {'ledger': proposal_for(wb, disposed, 'ledger')},
        disposed.revision, wb.ctx)
    assert cleared.issues == []
    assert len(cleared.instances) == 3
    assert 'mapping:unused' not in wb.sessions.get(session.id, wb.ctx).selected_versions


def test_ignore_source_after_a_narrower_proposal_is_allowed(tmp_path):
    """A later narrower proposal leaves an already mapped source unused.

    The source-level issue names it once, so the audited disposition must be
    allowed; the narrower proposal also clears the stale mapping scope so the
    web cannot pull the source back in on the next rebuild.
    """
    wb, session = unmapped_regeneration_setup(tmp_path)
    mapped = {source_id: proposal_for(wb, session, source_id)
              for source_id in ('ledger', 'unused')}
    wb.intake.submit_source_proposals(session.id, mapped, session.revision, wb.ctx)
    assert 'mapping:unused' in wb.sessions.get(session.id, wb.ctx).selected_versions
    # A narrower proposal (single-source mapping revision) leaves the second
    # material unmapped in the preview and drops its old scope entry.
    narrowed = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(
        session.id, proposal_for(wb, narrowed, 'ledger'), narrowed.revision, wb.ctx)
    assert [issue['source_id'] for issue in preview.issues
            if issue['code'] == 'ontology.source_unmapped'] == ['unused']
    current = wb.sessions.get(session.id, wb.ctx)
    assert 'mapping:unused' not in current.selected_versions
    wb.intake.dispose(session.id, _dispose('ignore_source', source_id='unused'),
                      current.revision, wb.ctx)
    assert wb.store.query('disposition', wb.scope)[0]['body']['entries'][0]['action'] == \
        'ignore_source'


def test_narrowing_replaces_the_mapping_scope_for_web_rebuild(tmp_path):
    """FDE2-05: full mapping -> narrower proposal -> web rebuild must not grow.

    The web rebuilds from the ``mapping:<source>`` entries.  Replacing the
    whole scope on every proposal keeps it equal to the agent's latest choice;
    an old key would make the page map the removed material again.
    """
    wb, session = unmapped_regeneration_setup(tmp_path)
    full = wb.intake.submit_source_proposals(session.id, {
        'ledger': proposal_for(wb, session, 'ledger'),
        'unused': proposal_for(wb, session, 'unused'),
    }, session.revision, wb.ctx)
    assert {'mapping:ledger', 'mapping:unused'} <= set(
        wb.sessions.get(session.id, wb.ctx).selected_versions)
    assert len(full.instances) == 8
    # The agent narrows the mapping to the ledger only.
    current = wb.sessions.get(session.id, wb.ctx)
    narrow = wb.intake.submit_proposal(
        session.id, proposal_for(wb, current, 'ledger'), current.revision, wb.ctx)
    current = wb.sessions.get(session.id, wb.ctx)
    assert 'mapping:ledger' in current.selected_versions
    assert 'mapping:unused' not in current.selected_versions
    assert set(wb.intake.view(session.id, wb.ctx)['mappings']) == {'ledger'}
    assert len(narrow.instances) == 4
    # This is exactly what the web sends after reading the current scope: only
    # the ledger, with the same bindings.  Objects and row-level problems must
    # not expand back to the unused material.
    rebuilt = wb.intake.submit_source_proposals(
        session.id, {'ledger': proposal_for(wb, current, 'ledger')},
        current.revision, wb.ctx)
    assert set(rebuilt.source_revisions) == {'ledger'}
    assert len(rebuilt.instances) == 4
    assert 'mapping:unused' not in wb.sessions.get(session.id, wb.ctx).selected_versions
    assert [issue['source_id'] for issue in rebuilt.issues
            if issue['code'] == 'ontology.source_unmapped'] == ['unused']
    assert not any(issue.get('row') is not None and issue.get('source_id') == 'unused'
                   for issue in rebuilt.issues)


def test_partial_save_reason_is_chinese_and_raw_detail_is_separate(tmp_path):
    wb, session = bad_rows_setup(tmp_path)
    body = {
        'instances': [{'id': 'obj-1', 'values': {
            'number': 'INV-9', 'amount_minor': 'not-a-number', 'currency': 'CNY',
        }, 'source_anchors': {}, 'unresolved': []}],
        'issues': [
            {'code': 'ontology.conversion_failed', 'target': 'amount',
             'entity_id': 'obj-1', 'source_id': 'ledger', 'row': 1,
             'detail': "Invalid isoformat string: 'not-a-date'"},
            {'code': 'ontology.required_value_missing', 'target': 'currency',
             'entity_id': 'obj-1', 'source_id': 'ledger', 'row': 1},
        ],
    }
    plan = wb.intake.partial_plan(session, body)
    reasons = {item['field']: item for item in plan['suspended'][0]['reasons']}
    assert reasons['amount']['reason'] == '值无法按目标类型转换'
    assert reasons['amount']['detail'] == "Invalid isoformat string: 'not-a-date'"
    assert reasons['currency']['reason'] == '缺少必填值'
    assert 'detail' not in reasons['currency']
    assert all('Invalid' not in item['reason'] for item in reasons.values())


def test_failed_conversion_is_counted_once_per_row_and_column(tmp_path):
    wb, session = bad_rows_setup(tmp_path)
    preview = wb.intake.submit_proposal(session.id, proposal_for(wb, session, 'ledger'),
                                        session.revision, wb.ctx)
    # Two rows fail; each failed column must not also count as a missing
    # required value on the same row (FDE2-06: 20 rows read as 40 problems).
    # The stored preview itself carries the deduplicated list now, so every
    # outward count (preview, session status, page) reports the same number.
    assert len(preview.issues) == 2
    summary = wb.intake.view(session.id, wb.ctx)
    assert summary['issue_count'] == len(summary['preview']['issues']) == 2
    assert not any(issue['code'] == 'ontology.required_value_missing'
                   for issue in summary['preview']['issues'])
    status = invoke(wb, 'intake_status', {'session_id': session.id}).data
    assert status['issue_count'] == len(status['issues']) == 2
    page = ViewService(wb).object_page(session.id, wb.ctx)
    assert len(page['issues']) == 2
    assert [issue['code'] for issue in page['issues']] == \
        ['ontology.conversion_failed', 'ontology.conversion_failed']
    blocked = wb.sessions.get(session.id, wb.ctx)
    with pytest.raises(PreviewBlocked) as rejection:
        wb.intake.apply(session.id, ReviewDecision(
            preview_ref=blocked.selected_versions['preview'], target_scope='mapping'),
            blocked.revision, wb.ctx)
    # The save rejection keeps the deduplicated count as well.
    assert len(rejection.value.issues) == 2
    assert all(issue['reason'] == '值无法按目标类型转换'
               for issue in rejection.value.issues)


def same_structure_setup(tmp_path):
    """Two materials whose structure fingerprint is identical on purpose."""
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'left': csv_profile('left', [
            {'number': 'L-1', 'amount_minor': '126000', 'currency': 'CNY'}],
            fingerprint='shared-structure'),
        'right': csv_profile('right', [
            {'number': 'R-1', 'amount_minor': '90000', 'currency': 'CNY'}],
            fingerprint='shared-structure'),
    })
    session = wb.intake.advance(start(wb, [
        SourceSelection(source_id='left', kind='file', locator_ref='left.csv'),
        SourceSelection(source_id='right', kind='file', locator_ref='right.csv')]).session_id, wb.ctx)
    return wb, session


def test_single_proposal_names_one_of_two_same_structure_sources(tmp_path):
    wb, session = same_structure_setup(tmp_path)
    # A fingerprint alone cannot choose between the two observations.  Do not
    # map both: ask for the explicit source id instead.
    with pytest.raises(ValueError, match='multiple sources'):
        wb.intake.submit_proposal(session.id, proposal_for(wb, session, 'left'),
                                  session.revision, wb.ctx)
    named = proposal_for(wb, session, 'left').model_copy(
        update={'extensions': {'intake.source_id': 'left'}})
    preview = wb.intake.submit_proposal(session.id, named, session.revision, wb.ctx)
    assert set(preview.source_revisions) == {'left'}
    assert [instance.values['number'] for instance in preview.instances] == ['L-1']
    assert [(issue['code'], issue['source_id']) for issue in preview.issues
            if issue['code'] == 'ontology.source_unmapped'] == \
        [('ontology.source_unmapped', 'right')]


def test_disposed_source_cannot_be_reintroduced_by_a_proposal(tmp_path):
    wb, session = unmapped_regeneration_setup(tmp_path)
    wb.intake.submit_source_proposals(
        session.id, {'ledger': proposal_for(wb, session, 'ledger')}, session.revision, wb.ctx)
    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.dispose(session.id, _dispose('ignore_source', source_id='unused'),
                      current.revision, wb.ctx)
    current = wb.sessions.get(session.id, wb.ctx)
    # Re-proposing the disposed material, alone or with the mapped one, must
    # be rejected instead of materializing its rows again.
    with pytest.raises(ValueError, match='disposed'):
        wb.intake.submit_source_proposals(session.id, {
            'ledger': proposal_for(wb, current, 'ledger'),
            'unused': proposal_for(wb, current, 'unused'),
        }, current.revision, wb.ctx)
    with pytest.raises(ValueError, match='disposed'):
        wb.intake.submit_proposal(session.id, proposal_for(wb, current, 'unused'),
                                  current.revision, wb.ctx)
    unused = proposal_for(wb, current, 'unused').model_copy(
        update={'extensions': {'intake.source_id': 'unused'}})
    with pytest.raises(ValueError, match='disposed'):
        wb.intake.submit_proposal(session.id, unused, current.revision, wb.ctx)
    # The allowed scope still regenerates: no object or row issue from the
    # disposed source, and no source-level "unmapped" prompt for it either.
    regenerated = wb.intake.submit_source_proposals(
        session.id, {'ledger': proposal_for(wb, current, 'ledger')},
        current.revision, wb.ctx)
    assert {instance.values['number'] for instance in regenerated.instances} == \
        {'number', 'INV-1', 'INV-2', 'INV-3'}
    assert not any(issue.get('source_id') == 'unused' for issue in regenerated.issues)


def test_issue_summary_uses_chinese_reason_for_unknown_code(tmp_path):
    wb, session = bad_rows_setup(tmp_path)
    preview = wb.intake.submit_proposal(session.id, proposal_for(wb, session, 'ledger'),
                                        session.revision, wb.ctx)
    body = wb.store.get('preview', preview.id, preview.revision, scope=wb.scope)['body']
    raw = "Invalid isoformat string: 'not-a-date'"
    body = {**body, 'issues': [
        {'code': 'ontology.future_failure', 'target': 'amount', 'detail': raw}]}
    item = wb.intake.issue_summary(session, body)[0]
    assert item['reason'] == '该项未通过核对'
    assert 'Invalid' not in item['reason']
    assert item['detail'] == raw


def clause_conversion_setup(tmp_path):
    wb = Workbench(tmp_path)
    profile = csv_profile('clause', [
        {'number': 'CL-1', 'amount_minor': 'not-a-number', 'currency': 'CNY'},
    ], kind='clause')
    profile.metadata['selected_record_set'] = 'clause_records:费用标准'
    wb.layer_client = StubProbeClient({'clause': profile})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='clause', kind='file', locator_ref='clause.pdf')]).session_id, wb.ctx)
    return wb, session


def test_clause_record_never_gets_exclude_record_option(tmp_path):
    wb, session = clause_conversion_setup(tmp_path)
    # 条款记录没有表头/无关行：转换失败、必填缺失、引文归属未核实都不提供
    # 「排除记录」，只能纠正值或重新提取条款记录。
    for code in ('ontology.conversion_failed', 'ontology.required_value_missing',
                 'record_attribution_unverified'):
        options = wb.intake.disposition_options(session, {'issues': [{
            'code': code, 'source_id': 'clause', 'row': 0}]})
        assert not [option for option in options
                    if option['action'] == 'exclude_record'], code


def test_clause_conversion_with_required_gap_stays_one_issue(tmp_path):
    wb, session = clause_setup(tmp_path)
    records = clause_records()
    # Same clause record: the limit is bound to a text field so its conversion
    # fails, and because the limit is required the engine also sees a missing
    # value on that row/column.  The real preview keeps one root cause and
    # offers no row-level escape for it.
    records[0]['values'] = [item for item in records[0]['values']
                             if item['property'] != '币种']
    extract_records(wb, session, records)
    session = wb.sessions.get(session.id, wb.ctx)
    mapping = standard_proposal(wb, session)
    mapping.bindings['限额'] = FieldBinding(source_field='城市等级', transform='decimal')
    preview = wb.intake.submit_proposal(
        session.id, mapping, session.revision, wb.ctx)
    # The failed 限额 conversion also leaves the required 限额 missing on the
    # same row/column; the stored preview keeps one root cause per record and
    # does not repeat the missing value.
    assert {issue['code'] for issue in preview.issues} == \
        {'ontology.conversion_failed'}
    assert len(preview.issues) == 4
    body = wb.intake.view(session.id, wb.ctx)['preview']
    # Those real clause records must not get an exclude action.
    assert not [action for issue in body['issues']
                for action in issue.get('actions', [])
                if action['action'] == 'exclude_record']
    options = wb.intake.disposition_options(
        wb.sessions.get(session.id, wb.ctx), body)
    assert not [option for option in options
                if option['action'] == 'exclude_record' and option['record'] == 0]


def test_real_clause_required_gap_has_no_exclude_record_option(tmp_path):
    """Review round 8: a real clause row missing a required value is not filler.

    The record has identity values but never states the required limit.  The
    preview's required_value_missing is a real gap to correct or re-extract,
    so neither the issue nor the disposition list may offer the table-row
    escape hatch.
    """
    wb, session = clause_setup(tmp_path)
    records = clause_records()
    records[0]['values'] = [item for item in records[0]['values']
                             if item['property'] != '限额']
    extract_records(wb, session, records)
    session = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(
        session.id, standard_proposal(wb, session), session.revision, wb.ctx)
    missing = [issue for issue in preview.issues
               if issue['code'] == 'ontology.required_value_missing']
    assert missing and missing[0]['row'] == 0 and missing[0]['target'] == '限额'
    assert not [issue for issue in preview.issues
                if issue['code'] == 'ontology.conversion_failed']
    body = wb.intake.view(session.id, wb.ctx)['preview']
    assert not [action for issue in body['issues']
                for action in issue.get('actions', [])
                if action['action'] == 'exclude_record']
    options = wb.intake.disposition_options(
        wb.sessions.get(session.id, wb.ctx), body)
    assert not [option for option in options
                if option['action'] == 'exclude_record']
    # The audited endpoint enforces the same rule; re-extraction (or a value
    # correction) is the way out, not dropping the verified clause record.
    current = wb.sessions.get(session.id, wb.ctx)
    with pytest.raises(ValueError, match='条款记录不能按无关行排除'):
        wb.intake.dispose(session.id,
                          _dispose('exclude_record', source_id='policy', record=0),
                          current.revision, wb.ctx)
