from __future__ import annotations

from dataagent_contracts.intake import SourceSelection
from dataagent_data.observation.files import probe_file, select_record_set


HEADERS = ['number', 'amount', 'currency']
ROWS = [
    ['INV-301', '1260.00', 'CNY'],
    ['INV-302', '900.50', 'CNY'],
    ['INV-303', '3300.00', 'CNY'],
]


def build_invoice_docx(path):
    from docx import Document

    document = Document()
    document.add_heading('采购单', level=1)
    table = document.add_table(rows=len(ROWS) + 1, cols=len(HEADERS))
    table.style = 'Table Grid'
    for column, value in enumerate(HEADERS):
        table.cell(0, column).text = value
    for row_index, row in enumerate(ROWS, 1):
        for column, value in enumerate(row):
            table.cell(row_index, column).text = value
    document.add_paragraph('备注：发票登记表由财务复核。')
    document.save(str(path))


def selection(name='invoice.docx', **options):
    return SourceSelection(source_id='invoice', kind='file', locator_ref=name,
                           options=options)


def test_docx_header_is_labels_and_paragraphs_are_a_separate_record_set(workspace, ctx):
    build_invoice_docx(workspace / 'invoice.docx')
    profile = probe_file(selection(), ctx, workspace=workspace)

    assert profile.coverage == 'full'
    table = profile.metadata['tables'][0]
    assert table['header_detected'] is True
    assert table['header_row'] == 1
    assert table['header_record'] is None
    assert table['headers'] == HEADERS
    assert [cell['unit_ref'] for cell in table['header_cells']] == [
        'table:1/row:1/col:1', 'table:1/row:1/col:2', 'table:1/row:1/col:3']

    record_sets = profile.metadata['record_sets']
    assert profile.metadata['default_record_set'] == 'table:1'
    assert record_sets['table:1']['count'] == 3
    assert record_sets['paragraphs']['count'] == 2

    table_records = [profile.records[index]
                     for index in record_sets['table:1']['record_indices']]
    assert table_records == [dict(zip(HEADERS, row)) for row in ROWS]
    assert not any(row.get('number') == 'number' for row in profile.records)

    # Cell anchors use the T26 table coordinate, not a document character span.
    first = record_sets['table:1']['record_indices'][0]
    assert profile.anchors[f'{first}.amount'][0].selector.unit_ref == (
        'table:1/row:2/col:2')
    assert profile.anchors[f'{first}.currency'][0].selector.unit_ref == (
        'table:1/row:2/col:3')
    location = next(item for item in profile.metadata['record_locations']
                    if item['record'] == first)
    assert location['kind'] == 'table'
    assert location['row'] == 2
    assert location['label'] == '表 1 第 2 行'
    assert location['cells']['amount'] == {
        'table': 1, 'row': 2, 'col': 2, 'unit_ref': 'table:1/row:2/col:2'}
    assert profile.metadata['units']['table:1/row:1/col:1'] == 'number'

    # The default view is the data table; prose is opt-in.
    selected = select_record_set(profile)
    assert selected.metadata['selected_record_set'] == 'table:1'
    assert selected.records == table_records
    assert selected.fields == HEADERS
    assert selected.anchors['0.amount'][0].selector.unit_ref == 'table:1/row:2/col:2'

    paragraphs = select_record_set(profile, 'paragraphs')
    assert paragraphs.metadata['selected_record_set'] == 'paragraphs'
    assert [record['text'] for record in paragraphs.records] == [
        '采购单', '备注：发票登记表由财务复核。']
    assert paragraphs.fields == ['text']


def test_docx_record_set_option_selects_the_table(workspace, ctx):
    build_invoice_docx(workspace / 'invoice.docx')
    chosen = probe_file(selection(record_set='table:1'), ctx, workspace=workspace)

    assert chosen.metadata['selected_record_set'] == 'table:1'
    assert len(chosen.records) == 3
    assert chosen.fields == HEADERS
    assert chosen.metadata['source_record_sets']['paragraphs']['count'] == 2

    prose = probe_file(selection(record_set='paragraphs'), ctx, workspace=workspace)
    assert prose.metadata['selected_record_set'] == 'paragraphs'
    assert [record['text'] for record in prose.records] == [
        '采购单', '备注：发票登记表由财务复核。']


def test_docx_known_field_labels_mark_a_text_only_header(workspace, ctx):
    from docx import Document

    document = Document()
    table = document.add_table(rows=3, cols=2)
    for column, value in enumerate(['姓名', '部门']):
        table.cell(0, column).text = value
    for row_index, row in enumerate([['张三', '销售部'], ['李四', '技术部']], 1):
        for column, value in enumerate(row):
            table.cell(row_index, column).text = value
    document.save(str(workspace / 'people.docx'))

    profile = probe_file(selection('people.docx'), ctx, workspace=workspace)
    table = profile.metadata['tables'][0]
    assert table['header_detected'] is True
    assert table['headers'] == ['姓名', '部门']
    assert profile.metadata['record_sets']['table:1']['count'] == 2
    assert profile.records[profile.metadata['record_sets']['table:1']['record_indices'][0]] == {
        '姓名': '张三', '部门': '销售部'}
