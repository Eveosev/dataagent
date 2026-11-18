"""Discovery evidence for document sources: sections, clauses and tables."""
import io
import shutil
import zipfile
from pathlib import Path

import pytest

from dataagent_contracts.intake import SourceProfile
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.discovery_catalog import build_catalog
from dataagent_workbench.service_tools import invoke


PACKAGES = Path(__file__).resolve().parents[2]
FIXTURES = PACKAGES / 'dataagent-scenarios/fixtures/intake'

STANDARD_ROWS = [
    ['城市等级', '职级', '费用类型', '限额', '币种'],
    ['一线', 'P1', '住宿', '400', 'CNY'],
    ['一线', 'P1', '交通', '200', 'CNY'],
    ['一线', 'P2', '住宿', '350', 'CNY'],
    ['二线', 'P1', '住宿', '300', 'CNY'],
    ['二线', 'P2', '住宿', '280', 'CNY'],
    ['二线', 'P2', '交通', '150', 'CNY'],
]
DETAIL_ROWS = [
    ['报销单号', '日期', '城市等级', '职级', '费用类型', '金额', '币种'],
    ['BX-001', '2026-11-01', '一线', 'P1', '住宿', '380', 'CNY'],
    ['BX-002', '2026-11-02', '一线', 'P1', '交通', '180', 'CNY'],
    ['BX-003', '2026-11-03', '一线', 'P2', '住宿', '340', 'CNY'],
    ['BX-004', '2026-11-04', '二线', 'P1', '住宿', '290', 'CNY'],
]
DEPARTMENTS_CSV = (
    '部门编号,部门名称\n'
    '400,华东区\n'
    '200,华南区\n'
    '350,华西区\n'
    '300,华北区\n'
    '280,华中区\n'
    '150,东北区\n'
)


def workbench(tmp_path, allowed=None):
    return Workbench(tmp_path, layer_client=LayerClient(PACKAGES / 'dataagent-data'),
                     allowed_model_fields=allowed)


def start(wb, sources, goal='从制度文件和报销明细发现对象'):
    return invoke(wb, 'intake_start', {
        'goal': goal, 'mode': 'ontology_discovery', 'sources': sources,
    }).data['session_id']


def request(wb, session_id):
    invoke(wb, 'intake_advance', {'session_id': session_id})
    return invoke(wb, 'intake_inference', {'session_id': session_id}).data


def document_sources():
    return [
        {'source_id': 'policy', 'kind': 'file', 'locator_ref': 'policy.docx'},
        {'source_id': 'detail', 'kind': 'file', 'locator_ref': 'detail.xlsx'},
        {'source_id': 'departments', 'kind': 'file', 'locator_ref': 'departments.csv'},
    ]


def document_allowed():
    return {
        'policy': ['城市等级', '职级', '费用类型', '限额', '币种'],
        'detail': ['报销单号', '日期', '城市等级', '职级', '费用类型', '金额', '币种'],
        'departments': ['部门编号', '部门名称'],
    }


def _docx_part(name, body):
    return name, body


def _docx_zip(document):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'))
        archive.writestr('_rels/.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'))
        archive.writestr('word/document.xml', document)
    return buffer.getvalue()


def _paragraph(text, level=None):
    # An explicit outline level marks the heading without needing styles.xml.
    properties = (f'<w:pPr><w:outlineLvl w:val="{level - 1}"/></w:pPr>'
                  if level is not None else '')
    return f'<w:p>{properties}<w:r><w:t>{text}</w:t></w:r></w:p>'


def _table_row(cells):
    return ('<w:tr>' + ''.join(
        f'<w:tc><w:tcPr/><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>'
        for cell in cells) + '</w:tr>')


def write_policy_docx(path):
    table = ('<w:tbl><w:tblPr/><w:tblGrid>' + '<w:gridCol/>' * len(STANDARD_ROWS[0])
             + '</w:tblGrid>' + ''.join(_table_row(row) for row in STANDARD_ROWS)
             + '</w:tbl>')
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        + _paragraph('差旅报销标准', 1)
        + _paragraph('总则', 2)
        + _paragraph('第一条 本标准适用于全体员工出差费用报销。')
        + _paragraph('第二条 城市等级分为一线、二线两档。')
        + _paragraph('费用标准', 2)
        + table
        + _paragraph('附则', 2)
        + _paragraph('第三条 本标准自发布之日起执行。')
        + '<w:sectPr/></w:body></w:document>')
    path.write_bytes(_docx_zip(document))


def write_detail_xlsx(path):
    sheet_rows = []
    for row_number, values in enumerate(DETAIL_ROWS, start=1):
        cells = ''.join(
            f'<c r="{chr(ord("A") + column)}{row_number}" t="inlineStr">'
            f'<is><t>{value}</t></is></c>'
            for column, value in enumerate(values))
        sheet_rows.append(f'<row r="{row_number}">{cells}</row>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as book:
        book.writestr('[Content_Types].xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'))
        book.writestr('_rels/.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'))
        book.writestr('xl/workbook.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="明细" sheetId="1" r:id="rId1"/></sheets></workbook>'))
        book.writestr('xl/_rels/workbook.xml.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'))
        book.writestr('xl/worksheets/sheet1.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'))


def document_workspace(tmp_path):
    write_policy_docx(tmp_path / 'policy.docx')
    write_detail_xlsx(tmp_path / 'detail.xlsx')
    (tmp_path / 'departments.csv').write_text(DEPARTMENTS_CSV, encoding='utf-8')


def test_document_sources_build_sections_clauses_and_table_evidence(tmp_path):
    document_workspace(tmp_path)
    wb = workbench(tmp_path, allowed=document_allowed())
    data = request(wb, start(wb, document_sources()))

    assert data['kind'] == 'ontology_discovery'
    tables = {table['name']: table for table in data['catalog']['tables']}
    assert set(tables) == {'table:1', '明细', 'departments'}

    standard = tables['table:1']
    assert standard['source_id'] == 'policy' and standard['kind'] == 'docx'
    assert standard['rows_observed'] == 6
    assert set(standard['columns']) == {'城市等级', '职级', '费用类型', '限额', '币种'}
    assert standard['columns']['限额']['affinity'] == 'text'
    assert standard['columns']['限额']['samples'] == ['400', '200', '350']
    assert ['限额'] in standard['keys']
    assert ['城市等级', '职级', '费用类型'] in standard['identity_keys']
    detail = tables['明细']
    assert ['报销单号'] in detail['identity_keys']

    document, = data['catalog']['documents']
    assert document['source_id'] == 'policy' and document['kind'] == 'docx'
    title, = document['sections']
    assert title['level'] == 1 and title['title'] == '差旅报销标准'
    assert title['paragraph_range'] == [1, 7]
    assert title['anchor']['selector']['unit_ref'] == 'paragraph:1'
    assert [(section['title'], section['paragraph_range'])
            for section in title['sections']] == [('总则', [2, 4]), ('费用标准', [5, 5]),
                                                  ('附则', [6, 7])]
    assert [clause['number'] for clause in document['clauses']] == ['第一条', '第二条', '第三条']
    assert [clause['paragraph'] for clause in document['clauses']] == [3, 4, 7]
    first = document['clauses'][0]
    assert first['anchor']['selector'] == {'kind': 'text_span', 'unit_ref': 'paragraph:3',
                                           'char_start': 0, 'char_end': 3}
    assert first['text'].startswith('第一条')
    assert document['record_sets'] == [
        {'name': 'paragraphs', 'kind': 'paragraph', 'count': 7},
        {'name': 'table:1', 'kind': 'table', 'count': 6},
    ]

    # The detail links to the standard table through the three-column composite
    # key; the department codes that coincidentally equal the limits do not.
    links = data['catalog']['relationships']
    assert [(link['source_table'], link['source_columns'], link['target_table'],
             link['target_columns']) for link in links] == [
        ('明细', ['城市等级', '职级', '费用类型'], 'table:1',
         ['城市等级', '职级', '费用类型'])]
    link, = links
    assert link['origin'] == 'sample_supported'
    assert link['ambiguous'] is False
    assert link['matched_rows'] == 4 and link['checked_rows'] == 4
    assert link['matched_distinct_keys'] == 4

    draft = invoke(wb, 'ontology_discovery_propose', {
        'session_id': data['session_id'],
        'expected_revision': data['expected_revision'],
        'proposal': {
            'source_revision': data['source_revision'],
            'entities': [
                {'table': 'table:1', 'name': 'ExpenseStandard', 'grain': '每档费用标准一行',
                 'identity': ['城市等级', '职级', '费用类型']},
                {'table': '明细', 'name': 'ExpenseClaim', 'grain': '每笔报销一行',
                 'identity': ['报销单号'],
                 'properties': [{'column': '金额', 'name': 'amount'}]},
                {'table': 'departments', 'name': 'Department', 'grain': '每个部门一行',
                 'identity': ['部门编号']},
            ],
            'relationships': [{'evidence_id': link['id'], 'name': 'followsStandard'}],
        },
    }).data
    assert draft['state'] == 'pending'
    assert draft['unresolved_tables'] == []
    assert draft['unresolved_relationships'] == []


@pytest.mark.parametrize(('change', 'message'), [
    (lambda p: p['entities'][0].update(table='table:9'), 'unknown table'),
    (lambda p: p['entities'][0].update(
        properties=[{'column': '不存在的列', 'name': 'x'}]), 'unknown column'),
    (lambda p: p['entities'][0].update(identity=['城市等级']), 'observed key'),
    (lambda p: p['relationships'][0].update(evidence_id='invented'), 'unknown relationship'),
])
def test_document_proposals_reject_unanchored_input(tmp_path, change, message):
    document_workspace(tmp_path)
    wb = workbench(tmp_path, allowed=document_allowed())
    data = request(wb, start(wb, document_sources()))
    link, = data['catalog']['relationships']
    proposal = {
        'source_revision': data['source_revision'],
        'entities': [
            {'table': 'table:1', 'name': 'ExpenseStandard', 'grain': '每档费用标准一行',
             'identity': ['城市等级', '职级', '费用类型']},
            {'table': '明细', 'name': 'ExpenseClaim', 'grain': '每笔报销一行',
             'identity': ['报销单号']},
            {'table': 'departments', 'name': 'Department', 'grain': '每个部门一行',
             'identity': ['部门编号']},
        ],
        'relationships': [{'evidence_id': link['id'], 'name': 'followsStandard'}],
    }
    change(proposal)
    with pytest.raises(ValueError, match=message):
        invoke(wb, 'ontology_discovery_propose', {
            'session_id': data['session_id'],
            'expected_revision': data['expected_revision'],
            'proposal': proposal,
        })


def test_document_text_stays_hidden_without_a_disclosure_policy(tmp_path):
    document_workspace(tmp_path)
    wb = workbench(tmp_path)
    data = request(wb, start(wb, document_sources()))

    document, = data['catalog']['documents']
    title, = document['sections']
    assert title['title'] is None
    assert all(clause['text'] is None for clause in document['clauses'])
    standard = {table['name']: table for table in data['catalog']['tables']}['table:1']
    assert standard['columns']['限额']['samples'] == []
    assert standard['columns']['限额']['distinct_values'] == 6


def test_pdf_pages_become_sections_tables_and_clause_candidates(tmp_path):
    profile = SourceProfile(
        source_id='manual', source_revision='sha256:manual', kind='pdf',
        records=[], fields=[],
        metadata={
            'pages': [{'page': 1, 'text': '报销制度\n第一条 本制度适用。\n1. 住宿按标准执行。',
                       'method': 'text'}],
            'tables': [{'page': 1, 'rows': [['城市等级', '限额'], ['一线', '400'], ['二线', '300']],
                        'bbox': [0.0, 0.0, 100.0, 100.0]}],
            'structure_fingerprint': 'manual',
        })
    catalog = build_catalog([profile], {'manual': {'城市等级', '限额'}})
    document, = catalog['documents']
    assert document['kind'] == 'pdf'
    section, = document['sections']
    assert section['level'] == 1 and section['page'] == 1
    assert section['anchor']['selector']['kind'] == 'pdf_text_span'
    assert [clause['number'] for clause in document['clauses']] == ['第一条', '1.']
    table, = catalog['tables']
    assert table['name'] == 'page:1' and table['rows_observed'] == 2
    assert table['columns']['限额']['samples'] == ['400', '300']
    assert ['城市等级'] in table['keys']
    assert document['record_sets'] == [{'name': 'page:1', 'kind': 'table', 'count': 2}]


def test_pdf_source_starts_discovery_intake_end_to_end(tmp_path):
    shutil.copy2(FIXTURES / 'invoice.pdf', tmp_path / 'invoice.pdf')
    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'invoice', 'kind': 'file', 'locator_ref': 'invoice.pdf'},
    ], goal='从发票文档发现对象'))
    assert data['kind'] == 'ontology_discovery'
    documents = data['catalog']['documents']
    assert [document['source_id'] for document in documents] == ['invoice']
    assert documents[0]['kind'] == 'pdf'
    assert documents[0]['sections']
