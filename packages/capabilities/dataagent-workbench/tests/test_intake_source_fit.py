"""A source that cannot carry the task's concept is intercepted, not mapped.

FDE3-04: two materials in one mapping task, the target concept fixed on the
expense line; the limit-table document used to be mapped anyway, flooding the
preview with unidentified objects and per-row missing values.  The proposal
stage now holds such a source out with one source-level issue, offers the
audited "this task does not use the source" way out, and never offers the
"include in mapping" escape a matching-but-unmapped source gets.  FDE2-06 余项:
a column whose required value is missing on every row counts as one root
cause with an affected-row count, not one problem per row.
"""
import pytest

from dataagent_contracts.intake import SourceSelection
from dataagent_contracts.ontology import ReviewDecision
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.intake_service import PreviewBlocked
from dataagent_workbench.service_tools import invoke
from test_intake_repairs import StubProbeClient, csv_profile, start


def mismatch_setup(tmp_path):
    """A matching ledger plus a limit table that is not an expense line."""
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'ledger': csv_profile('ledger', [
            {'number': 'INV-1', 'amount_minor': '126000', 'currency': 'CNY'},
            {'number': 'INV-2', 'amount_minor': '90000', 'currency': 'CNY'},
        ]),
        'limits': csv_profile('limits', [
            {'费用类别': '市内交通费', '限额': '80'},
            {'费用类别': '住宿费', '限额': '400'},
        ], kind='docx'),
    })
    session = wb.intake.advance(start(wb, [
        SourceSelection(source_id='ledger', kind='file', locator_ref='ledger.csv'),
        SourceSelection(source_id='limits', kind='file', locator_ref='limits.docx')]).session_id, wb.ctx)
    return wb, session


def proposals_for(wb, session, source_ids):
    """Same-name-plus-分转元 bindings over the source's observed fields."""
    from dataagent_contracts.ontology import MappingSpec
    proposals = {}
    for source_id in source_ids:
        source = next(item for item in wb.intake.inference_request(session.id, wb.ctx)['sources']
                      if item['source_id'] == source_id)
        bindings = {}
        fields = set(source['fields'])
        if 'number' in fields:
            bindings['number'] = {'source_field': 'number'}
        if 'amount_minor' in fields:
            bindings['amount'] = {'source_field': 'amount_minor', 'transform': 'minor_to_major'}
        elif 'amount' in fields:
            bindings['amount'] = {'source_field': 'amount'}
        if 'currency' in fields:
            bindings['currency'] = {'source_field': 'currency'}
        if '限额' in fields:
            # The agent maps the limit table onto the concept as best it can
            # (FDE3-04): the identity column simply does not exist there.
            bindings['amount'] = {'source_field': '限额', 'transform': 'decimal'}
        proposals[source_id] = MappingSpec(
            id='candidate', revision='1', ontology_revision='procurement@1',
            source_fingerprint=source['structure_fingerprint'],
            bindings=bindings)
    return proposals


def test_mismatched_source_is_held_out_with_one_source_level_issue(tmp_path):
    wb, session = mismatch_setup(tmp_path)
    # The agent proposes mappings for both materials, the limit table included.
    preview = wb.intake.submit_source_proposals(
        session.id, proposals_for(wb, session, ('ledger', 'limits')),
        session.revision, wb.ctx)
    assert [(issue['code'], issue['source_id']) for issue in preview.issues] == \
        [('ontology.source_concept_mismatch', 'limits')]
    assert set(preview.source_revisions) == {'ledger'}
    # The limit table's rows never became objects or per-row problems.
    assert [instance.values['number'] for instance in preview.instances] == \
        ['INV-1', 'INV-2']
    assert not any(issue.get('row') is not None for issue in preview.issues)
    # The page names the source and offers the audited way out.
    summary = wb.intake.view(session.id, wb.ctx)
    item = next(issue for issue in summary['preview']['issues']
                if issue['code'] == 'ontology.source_concept_mismatch')
    assert item['object'] == '来源 limits.docx'
    assert item['reason'] == '该来源与目标概念不符'
    assert [option['reason_hint'] for option in item['actions']] == ['本任务不使用该来源']
    # A matching-but-unmapped source keeps the include escape; a mismatched
    # one never gets it (the web gates the button on the issue code).
    options = wb.intake.disposition_options(
        wb.sessions.get(session.id, wb.ctx),
        wb.store.get('preview', preview.id, preview.revision, scope=wb.scope)['body'])
    assert [option['scope'] for option in options
            if option['source_id'] == 'limits'] == ['source']


def test_unmapped_mismatching_source_is_named_as_a_mismatch_not_unmapped(tmp_path):
    wb, session = mismatch_setup(tmp_path)
    preview = wb.intake.submit_source_proposals(
        session.id, proposals_for(wb, session, ('ledger',)), session.revision, wb.ctx)
    assert [(issue['code'], issue['source_id']) for issue in preview.issues] == \
        [('ontology.source_concept_mismatch', 'limits')]
    # A source that matches the concept by name keeps the plain unmapped issue.
    wb2 = Workbench(tmp_path / 'second')
    wb2.layer_client = StubProbeClient({
        'rows': csv_profile('rows', [{'number': 'R-1', 'amount_minor': '500',
                                      'currency': 'CNY'}]),
        'extra': csv_profile('extra', [{'number': 'X-1', 'amount_minor': '100',
                                        'currency': 'CNY'}]),
    })
    session2 = wb2.intake.advance(start(wb2, [
        SourceSelection(source_id='rows', kind='file', locator_ref='rows.csv'),
        SourceSelection(source_id='extra', kind='file', locator_ref='extra.csv')]).session_id, wb2.ctx)
    narrow = wb2.intake.submit_source_proposals(
        session2.id, proposals_for(wb2, session2, ('rows',)), session2.revision, wb2.ctx)
    assert [(issue['code'], issue['source_id']) for issue in narrow.issues] == \
        [('ontology.source_unmapped', 'extra')]


def test_mismatched_source_can_be_ignored_and_the_task_saves(tmp_path):
    wb, session = mismatch_setup(tmp_path)
    wb.intake.submit_source_proposals(
        session.id, proposals_for(wb, session, ('ledger', 'limits')),
        session.revision, wb.ctx)
    # Without the disposition the mismatch blocks the whole-batch save.
    blocked = wb.sessions.get(session.id, wb.ctx)
    with pytest.raises(PreviewBlocked) as rejection:
        wb.intake.apply(session.id, ReviewDecision(
            preview_ref=blocked.selected_versions['preview'], target_scope='mapping'),
            blocked.revision, wb.ctx)
    assert any(issue['code'] == 'ontology.source_concept_mismatch'
               for issue in rejection.value.issues)
    # The wrongly mapped source is disposed as a whole even though a proposal
    # named it: the wrong mapping must not pin it into the task (FDE3-04).
    from test_disposition_types import _dispose
    wb.intake.dispose(session.id, _dispose('ignore_source', source_id='limits'),
                      blocked.revision, wb.ctx)
    entry, = wb.store.query('disposition', wb.scope)[0]['body']['entries']
    assert entry['action'] == 'ignore_source' and entry['source_id'] == 'limits'
    # Regenerating maps only the ledger; the save no longer needs the disposed
    # material and keeps the ledger's two objects.
    disposed = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_source_proposals(
        disposed.id, proposals_for(wb, disposed, ('ledger',)), disposed.revision, wb.ctx)
    assert preview.issues == []
    assert len(preview.instances) == 2
    current = wb.sessions.get(session.id, wb.ctx)
    wb.intake.apply(session.id, ReviewDecision(
        preview_ref=current.selected_versions['preview'], target_scope='mapping'),
        current.revision, wb.ctx)
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'
    assert [instance['values']['number'] for instance in
            wb.intake.view(session.id, wb.ctx)['preview']['instances']] == ['INV-1', 'INV-2']


def test_single_source_mismatch_keeps_one_issue_and_no_objects(tmp_path):
    """The single-source endpoint holds the mismatch out the same way."""
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'limits': csv_profile('limits', [
            {'费用类别': '市内交通费', '限额': '80'},
            {'费用类别': '住宿费', '限额': '400'}], kind='docx')})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='limits', kind='file', locator_ref='limits.docx')]).session_id, wb.ctx)
    from dataagent_contracts.ontology import MappingSpec
    source = wb.intake.inference_request(session.id, wb.ctx)['sources'][0]
    proposal = MappingSpec(id='candidate', revision='1', ontology_revision='procurement@1',
                           source_fingerprint=source['structure_fingerprint'],
                           bindings={'amount': {'source_field': '限额', 'transform': 'decimal'}})
    preview = wb.intake.submit_proposal(session.id, proposal, session.revision, wb.ctx)
    assert not preview.instances
    assert {issue['code'] for issue in preview.issues} == \
        {'ontology.source_concept_mismatch', 'ontology.no_records'}


def test_identity_column_keeps_a_sparse_source_materialized(tmp_path):
    """The mismatch rule is conservative: identity bound, or half the required.

    A ledger that carries the identity column but misses one required column
    is a real (incomplete) mapping, not a concept mismatch: its rows stay
    objects and the missing column collapses to one root cause (FDE2-06).
    """
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'gaps': csv_profile('gaps', [
            {'number': 'INV-1', 'amount_minor': '1000'},
            {'number': 'INV-2', 'amount_minor': '2000'},
            {'number': 'INV-3', 'amount_minor': '3000'}])})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='gaps', kind='file', locator_ref='gaps.csv')]).session_id, wb.ctx)
    preview = wb.intake.submit_source_proposals(
        session.id, proposals_for(wb, session, ('gaps',)), session.revision, wb.ctx)
    assert len(preview.instances) == 3
    assert [issue['code'] for issue in preview.issues] == \
        ['ontology.required_binding_missing'] + ['ontology.required_value_missing'] * 3
    # Two root causes (the unbound currency column, and the same column's
    # missing value collapsed across rows), three affected rows; the stored
    # per-row list still names every row for locating and correcting.
    status = invoke(wb, 'intake_status', {'session_id': session.id}).data
    assert status['issue_count'] == len(status['issues']) == 2
    assert {issue['code'] for issue in status['issues']} == \
        {'ontology.required_value_missing', 'ontology.required_binding_missing'}
    assert status['issue_row_count'] == 3
    summary = wb.intake.view(session.id, wb.ctx)
    assert summary['issue_count'] == 2
    assert summary['preview']['issue_row_count'] == 3
    assert summary['preview']['issue_item_count'] == \
        len(summary['preview']['issues']) == 4
