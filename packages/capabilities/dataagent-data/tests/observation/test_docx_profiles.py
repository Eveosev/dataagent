from __future__ import annotations

import zipfile

import pytest

from conftest import file_ref
from fixtures.docx_policy import build_policy_docx
from dataagent_contracts.intake import SourceSelection
from dataagent_data.anchors import AnchorResolver
from dataagent_data.observation.files import probe_file


def selection(name: str) -> SourceSelection:
    return SourceSelection(source_id='policy', kind='file', locator_ref=name)


def probe(workspace, ctx, name='policy.docx'):
    return probe_file(selection(name), ctx, workspace=workspace)


def test_docx_extracts_paragraphs_headings_tables_and_merged_cells(workspace, ctx):
    build_policy_docx(workspace / 'policy.docx')
    profile = probe(workspace, ctx)

    assert profile.kind == 'docx'
    assert profile.coverage == 'full'
    assert profile.total_partitions == 5
    assert profile.completed_partitions == [1, 2, 3, 4, 5]
    assert profile.metadata['paragraph_count'] == 4
    assert profile.metadata['table_count'] == 1

    assert [row['text'] for row in profile.records if row.get('text')] == [
        '费用报销制度',
        '第一条 本制度适用于全体员工。',
        '审批权限',
        '金额超过 5000 元须经部门负责人审批。',
    ]
    assert [item['heading_level'] for item in profile.metadata['paragraphs']] == [1, None, 2, None]
    assert [item['style'] for item in profile.metadata['paragraphs']] == [
        'Heading 1', 'Normal', 'Heading 2', 'Normal']

    table = profile.metadata['tables'][0]
    assert table['row_count'] == 3 and table['column_count'] == 3
    assert table['merges'] == [{'row': 2, 'col': 3, 'row_span': 2, 'col_span': 1}]
    assert table['rows'] == [
        ['项目', '金额', '说明'],
        ['差旅费', '1200', '实报实销'],
        ['招待费', '800', '实报实销'],
    ]
    assert table['header_detected'] is True and table['header_row'] == 1
    assert table['header_record'] is None
    assert table['headers'] == ['项目', '金额', '说明']
    assert table['header_cells'][0]['unit_ref'] == 'table:1/row:1/col:1'
    assert all(row.get('项目') != '项目' for row in profile.records)

    record_sets = profile.metadata['record_sets']
    assert profile.metadata['default_record_set'] == 'table:1'
    assert record_sets['paragraphs']['count'] == 4
    table_indices = record_sets['table:1']['record_indices']
    assert len(table_indices) == 2
    assert profile.records[table_indices[0]]['项目'] == '差旅费'

    by_item = {row['项目']: index for index, row in enumerate(profile.records) if row.get('项目')}
    assert profile.records[by_item['差旅费']]['说明'] == '实报实销'
    assert profile.records[by_item['招待费']]['说明'] == '实报实销'

    paragraph_anchor = profile.anchors['1.text'][0]
    assert paragraph_anchor.selector.kind == 'text_span'
    assert paragraph_anchor.selector.unit_ref == 'paragraph:2'
    assert paragraph_anchor.source_revision == profile.source_revision

    travel_anchor = profile.anchors[f'{by_item["差旅费"]}.金额'][0]
    assert travel_anchor.selector.unit_ref == 'table:1/row:2/col:2'
    # The merged continuation value keeps the anchor of the cell that owns it.
    merged_anchor = profile.anchors[f'{by_item["招待费"]}.说明'][0]
    assert merged_anchor.selector.unit_ref == 'table:1/row:2/col:3'

    units = profile.metadata['units']
    assert units['paragraph:2'] == '第一条 本制度适用于全体员工。'
    assert units['table:1/row:2/col:3'] == '实报实销'

    resolver = AnchorResolver(units=units)
    for key, anchors in profile.anchors.items():
        row_index, field = key.split('.', 1)
        resolved = resolver.resolve(anchors[0])
        assert resolved.reason == '', (key, resolved.reason)
        assert resolved.text == str(profile.records[int(row_index)][field])

    # Headers and footers live outside w:body and must not enter the profile.
    dumped = repr(profile.metadata)
    assert '页眉' not in dumped and '页脚' not in dumped
    assert all('页眉' not in (row.get('text') or '') for row in profile.records)


def test_docx_horizontal_merge_is_expanded(workspace, ctx):
    from docx import Document
    from docx.oxml import OxmlElement

    document = Document()
    table = document.add_table(rows=2, cols=3)
    for column, value in enumerate(['项目', '金额', '说明']):
        table.cell(0, column).text = value
    # This all-text table is ambiguous by content, so mark the row explicitly
    # as a repeating Word header.
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    table.cell(1, 0).text = '合并值'
    table.cell(1, 0).merge(table.cell(1, 1))
    table.cell(1, 2).text = '独立值'
    document.save(str(workspace / 'merged.docx'))

    profile = probe(workspace, ctx, 'merged.docx')
    record = next(row for row in profile.records if row.get('项目') == '合并值')
    assert record['项目'] == '合并值'
    assert record['金额'] == '合并值'
    assert record['说明'] == '独立值'
    assert profile.metadata['tables'][0]['merges'] == [
        {'row': 2, 'col': 1, 'row_span': 1, 'col_span': 2}]
    index = profile.records.index(record)
    assert profile.anchors[f'{index}.项目'][0].selector.unit_ref == 'table:1/row:2/col:1'
    assert profile.anchors[f'{index}.金额'][0].selector.unit_ref == 'table:1/row:2/col:1'


def test_docx_grid_before_keeps_the_right_column_anchor(workspace, ctx):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = '左列'
    table.cell(0, 1).text = '右列'
    table.cell(1, 1).text = '应在右列'
    row = table.rows[1]._tr
    row.remove(row.tc_lst[0])  # the second row omits its leading cell
    grid_before = OxmlElement('w:gridBefore')
    grid_before.set(qn('w:val'), '1')
    row.get_or_add_trPr().append(grid_before)
    document.save(str(workspace / 'grid-before.docx'))

    profile = probe(workspace, ctx, 'grid-before.docx')
    table_meta = profile.metadata['tables'][0]
    assert table_meta['rows'] == [['左列', '右列'], [None, '应在右列']]
    assert table_meta['header_detected'] is False
    assert profile.records[1] == {'column_1': None, 'column_2': '应在右列'}
    assert profile.anchors['1.column_2'][0].selector.unit_ref == (
        'table:1/row:2/col:2')
    assert '1.column_1' not in profile.anchors


def test_docx_headerless_two_row_table_anchors_its_first_row(workspace, ctx):
    from docx import Document

    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = '张三'
    table.cell(0, 1).text = '销售部'
    table.cell(1, 0).text = '李四'
    table.cell(1, 1).text = '技术部'
    document.save(str(workspace / 'headerless.docx'))

    profile = probe(workspace, ctx, 'headerless.docx')
    table_meta = profile.metadata['tables'][0]
    assert table_meta['header_detected'] is False
    assert table_meta['header_row'] == 0
    assert table_meta['header_record'] is None
    assert profile.records == [
        {'column_1': '张三', 'column_2': '销售部'},
        {'column_1': '李四', 'column_2': '技术部'},
    ]
    assert profile.anchors['0.column_1'][0].selector.unit_ref == (
        'table:1/row:1/col:1')
    assert profile.anchors['0.column_2'][0].selector.unit_ref == (
        'table:1/row:1/col:2')
    assert profile.coverage == 'full'


def test_docx_one_row_table_keeps_its_text(workspace, ctx):
    from docx import Document

    document = Document()
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = '仅有一行的表格文本'
    document.save(str(workspace / 'one-row.docx'))

    profile = probe(workspace, ctx, 'one-row.docx')
    assert profile.records == [{'column_1': '仅有一行的表格文本'}]
    assert profile.metadata['tables'][0]['header_row'] == 0
    anchor = profile.anchors['0.column_1'][0]
    assert anchor.selector.unit_ref == 'table:1/row:1/col:1'
    assert profile.metadata['units']['table:1/row:1/col:1'] == '仅有一行的表格文本'


def test_docx_structure_fingerprint_ignores_text(workspace, ctx):
    build_policy_docx(workspace / 'a.docx', title_text='制度 A', body_text='正文 A')
    build_policy_docx(workspace / 'b.docx', title_text='制度 B', body_text='正文 B')
    first, second = probe(workspace, ctx, 'a.docx'), probe(workspace, ctx, 'b.docx')
    assert first.metadata['structure_fingerprint'] == second.metadata['structure_fingerprint']

    build_policy_docx(workspace / 'style.docx', title_style_level=2)
    build_policy_docx(workspace / 'shape.docx', table_rows=4)
    style = probe(workspace, ctx, 'style.docx')
    shape = probe(workspace, ctx, 'shape.docx')
    assert style.metadata['structure_fingerprint'] != first.metadata['structure_fingerprint']
    assert shape.metadata['structure_fingerprint'] != first.metadata['structure_fingerprint']
    assert len(first.metadata['structure_fingerprint']) == 64


def test_docx_non_zip_is_an_explicit_error(workspace, ctx):
    (workspace / 'broken.docx').write_bytes(b'not a zip')
    with pytest.raises(ValueError, match='docx'):
        probe(workspace, ctx, 'broken.docx')

    with zipfile.ZipFile(workspace / 'missing.docx', 'w') as archive:
        archive.writestr('not-word.txt', 'still not a Word package')
    with pytest.raises(ValueError, match='docx'):
        probe(workspace, ctx, 'missing.docx')


def test_docx_snapshot_is_content_addressed(workspace, ctx):
    build_policy_docx(workspace / 'policy.docx')
    profile = probe(workspace, ctx)
    reference = file_ref(workspace, 'policy.docx')
    assert profile.source_revision == reference.revision
    assert profile.metadata['snapshot_ref'] == f'.dataagent/content/{reference.revision[7:]}.docx'
