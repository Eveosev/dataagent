"""Segmented probing: each call is bounded, resumable and lossless."""
from __future__ import annotations

from dataagent_contracts.intake import SourceSelection
from dataagent_data.observation.files import probe_file
from conftest import build_pdf_pages, build_xlsx
from fixtures.docx_policy import build_policy_docx


def selection(name: str, **options) -> SourceSelection:
    return SourceSelection(source_id='source', kind='file', locator_ref=name,
                           options=options)


def run_to_completion(workspace, ctx, name, **kwargs):
    first = probe_file(selection(name), ctx, workspace=workspace, **kwargs)
    profiles = [first]
    while profiles[-1].metadata.get('resume'):
        profiles.append(probe_file(selection(name), ctx, workspace=workspace,
                                   previous=profiles[-1], **kwargs))
        assert len(profiles) < 50
    return profiles


def test_csv_segments_resume_without_repeating_records(workspace, ctx):
    (workspace / 'rows.csv').write_text(
        'id,amount\n' + ''.join(f'{index},{index * 10}\n' for index in range(7)))
    profiles = run_to_completion(workspace, ctx, 'rows.csv', segment_rows=2)
    assert len(profiles) > 1
    for profile in profiles[:-1]:
        assert profile.coverage == 'partial'
        assert profile.completed_partitions == []
        assert [gap.code for gap in profile.gaps] == ['time_budget_exceeded']
        assert profile.metadata['resume']['next_row'] == len(profile.records)
    final = profiles[-1]
    assert final.coverage == 'full' and final.completed_partitions == [1]
    assert final.records == [{'id': str(index), 'amount': str(index * 10)}
                             for index in range(7)]
    assert 'resume' not in final.metadata
    # A completion has the same evidence as a single unbounded probe.
    one_shot = probe_file(selection('rows.csv'), ctx, workspace=workspace)
    assert final.records == one_shot.records
    assert final.anchors == one_shot.anchors


def test_jsonl_segments_resume_without_repeating_records(workspace, ctx):
    lines = [f'{{"id": {index}, "label": "row-{index}"}}' for index in range(5)]
    (workspace / 'rows.jsonl').write_text('\n'.join(lines) + '\n')
    profiles = run_to_completion(workspace, ctx, 'rows.jsonl', segment_rows=2)
    assert len(profiles) > 1
    final = profiles[-1]
    assert final.coverage == 'full'
    assert [row['/id'] for row in final.records] == [0, 1, 2, 3, 4]
    one_shot = probe_file(selection('rows.jsonl'), ctx, workspace=workspace)
    assert final.records == one_shot.records
    assert final.anchors == one_shot.anchors


def test_pdf_segments_by_page_and_keeps_earlier_pages(workspace, ctx):
    build_pdf_pages(workspace / 'pages.pdf', [
        ['invoice: A-1', 'amount: 100'],
        ['invoice: A-2', 'amount: 200'],
        ['invoice: A-3', 'amount: 300'],
    ])
    profiles = run_to_completion(workspace, ctx, 'pages.pdf', segment_pages=1)
    assert len(profiles) == 3
    assert [profile.completed_partitions for profile in profiles] == [[1], [1, 2], [1, 2, 3]]
    assert [profile.metadata['pages'][-1]['page'] for profile in profiles] == [1, 2, 3]
    final = profiles[-1]
    assert final.coverage == 'full'
    one_shot = probe_file(selection('pages.pdf'), ctx, workspace=workspace)
    assert final.records == one_shot.records
    assert final.anchors == one_shot.anchors
    assert final.metadata['pages'] == one_shot.metadata['pages']


def test_docx_segments_by_body_block_and_recomputes_structure(workspace, ctx):
    build_policy_docx(workspace / 'policy.docx')
    profiles = run_to_completion(workspace, ctx, 'policy.docx', segment_blocks=2)
    assert len(profiles) == 3
    assert [profile.metadata['paragraph_count'] for profile in profiles] == [2, 4, 4]
    assert [profile.metadata['table_count'] for profile in profiles] == [0, 0, 1]
    final = profiles[-1]
    assert final.coverage == 'full' and final.completed_partitions == [1, 2, 3, 4, 5]
    one_shot = probe_file(selection('policy.docx'), ctx, workspace=workspace)
    assert final.records == one_shot.records
    assert final.anchors == one_shot.anchors
    assert final.metadata['units'] == one_shot.metadata['units']
    assert final.metadata['structure_fingerprint'] == one_shot.metadata['structure_fingerprint']


def test_xlsx_segments_by_sheet_and_keeps_completed_sheets(workspace, ctx):
    build_xlsx(workspace / 'book.xlsx', {
        'First': [['id', 'amount'], ['A', 100], ['B', 200]],
        'Second': [['id', 'amount'], ['C', 300]],
        'Third': [['id', 'amount'], ['D', 400]],
    })
    profiles = run_to_completion(workspace, ctx, 'book.xlsx', segment_sheets=1)
    assert len(profiles) == 3
    assert [profile.completed_partitions for profile in profiles] == [[1], [1, 2], [1, 2, 3]]
    final = profiles[-1]
    assert final.coverage == 'full'
    one_shot = probe_file(selection('book.xlsx'), ctx, workspace=workspace)
    assert final.records == one_shot.records
    assert final.anchors == one_shot.anchors
    assert final.metadata['total_rows'] == one_shot.metadata['total_rows']


def test_resume_drops_a_recorded_probe_failure_and_keeps_completed_rows(workspace, ctx):
    from dataagent_contracts.intake import CoverageGap
    (workspace / 'rows.csv').write_text(
        'id,amount\n' + ''.join(f'{index},{index * 10}\n' for index in range(5)))
    first = probe_file(selection('rows.csv'), ctx, workspace=workspace, segment_rows=2)
    failed = first.model_copy(update={
        'gaps': [*first.gaps, CoverageGap(partition=3, code='probe_timeout')],
        'metadata': {**first.metadata, 'probe_error': {'code': 'probe_timeout'},
                     'probe_attempts': 1},
    })
    final = probe_file(selection('rows.csv'), ctx, workspace=workspace,
                       previous=failed, segment_rows=100)
    assert final.coverage == 'full'
    assert final.records == [{'id': str(index), 'amount': str(index * 10)}
                             for index in range(5)]
    assert final.gaps == []


def test_segmented_csv_stops_at_the_row_budget(workspace, ctx):
    (workspace / 'rows.csv').write_text(
        'id,amount\n' + ''.join(f'{index},{index * 10}\n' for index in range(7)))
    profiles = run_to_completion(workspace, ctx, 'rows.csv', segment_rows=2, budget_rows=5)
    final = profiles[-1]
    assert final.coverage == 'sampled' and final.sampled
    assert len(final.records) == 5
    assert final.completed_partitions == [1]
    assert final.gaps == []
    one_shot = probe_file(selection('rows.csv'), ctx, workspace=workspace, budget_rows=5)
    assert final.records == one_shot.records
    assert final.anchors == one_shot.anchors


def test_csv_segment_rows_is_the_actual_chunk_size(workspace, ctx):
    (workspace / 'rows.csv').write_text(
        'id,amount\n' + ''.join(f'{index},{index * 10}\n' for index in range(700)))
    first = probe_file(selection('rows.csv'), ctx, workspace=workspace,
                       segment_rows=500, budget_rows=1000)
    assert first.coverage == 'partial' and len(first.records) == 500
    assert first.metadata['resume']['next_row'] == 500
    final = probe_file(selection('rows.csv'), ctx, workspace=workspace, previous=first,
                       segment_rows=500, budget_rows=1000)
    assert len(final.records) == 700
    assert final.coverage == 'full'


def test_csv_continues_past_segment_rows_until_the_row_budget(workspace, ctx):
    (workspace / 'rows.csv').write_text(
        'id,amount\n' + ''.join(f'{index},{index * 10}\n' for index in range(700)))
    profiles = run_to_completion(workspace, ctx, 'rows.csv', segment_rows=250,
                                 budget_rows=1000)
    assert len(profiles) == 3
    assert [len(profile.records) for profile in profiles] == [250, 500, 700]
    assert profiles[-1].coverage == 'full'
    assert profiles[-1].metadata.get('resume') is None
