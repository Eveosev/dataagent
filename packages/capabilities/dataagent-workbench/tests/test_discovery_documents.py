"""Discovery evidence for document sources: sections, clauses and tables."""
import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from dataagent_contracts.core import SourceAnchor
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
    '400,东南区\n'
    '350,华西区\n'
    '300,华北区\n'
    '280,华中区\n'
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
        # 'text' is the G4 paragraphs record set field; allowing it is what
        # discloses section titles and clause text.
        'policy': ['城市等级', '职级', '费用类型', '限额', '币种', 'text'],
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
    # The table and its columns carry the record set's cell anchors, so the
    # identity key and the link below replay to a concrete position.  The
    # table anchor is the record set's top-left cell: a contract text_span.
    table_anchor = SourceAnchor.model_validate(standard['anchor'])
    assert table_anchor.selector.kind == 'text_span'
    assert table_anchor.selector.unit_ref == 'table:1/row:2/col:1'
    city = standard['columns']['城市等级']['anchor']['selector']
    assert (city['kind'], city['unit_ref']) == ('text_span', 'table:1/row:2/col:1')
    assert (city['char_start'], city['char_end']) == (0, 2)
    limit = standard['columns']['限额']['anchor']['selector']
    assert (limit['kind'], limit['unit_ref']) == ('text_span', 'table:1/row:2/col:4')
    assert (limit['char_start'], limit['char_end']) == (0, 3)
    detail = tables['明细']
    assert ['报销单号'] in detail['identity_keys']

    document, = data['catalog']['documents']
    assert document['source_id'] == 'policy' and document['kind'] == 'docx'
    title, = document['sections']
    assert title['level'] == 1 and title['title'] == '差旅报销标准'
    assert title['paragraph_range'] == [1, 7]
    assert title['ref'] == 'section:policy:1'
    assert title['anchor']['selector']['unit_ref'] == 'paragraph:1'
    assert [(section['title'], section['paragraph_range'])
            for section in title['sections']] == [('总则', [2, 4]), ('费用标准', [5, 5]),
                                                  ('附则', [6, 7])]
    assert [section['ref'] for section in title['sections']] == [
        'section:policy:2', 'section:policy:3', 'section:policy:4']
    assert [clause['number'] for clause in document['clauses']] == ['第一条', '第二条', '第三条']
    assert [clause['paragraph'] for clause in document['clauses']] == [3, 4, 7]
    assert [clause['ref'] for clause in document['clauses']] == [
        'clause:policy:1', 'clause:policy:2', 'clause:policy:3']
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
    # The link replays to a contract cell anchor of its document endpoint.
    assert tables[link['target_table']]['anchor']['selector']['unit_ref'].startswith('table:1/')

    draft = invoke(wb, 'ontology_discovery_propose', {
        'session_id': data['session_id'],
        'expected_revision': data['expected_revision'],
        'proposal': {
            'source_revision': data['source_revision'],
            'entities': [
                {'table': 'table:1', 'name': 'ExpenseStandard', 'grain': '每档费用标准一行',
                 'identity': ['城市等级', '职级', '费用类型'],
                 # The standard cites the section that carries its table and
                 # the clause that defines the city tiers.
                 'evidence_sections': ['section:policy:3', 'clause:policy:2']},
                {'table': '明细', 'name': 'ExpenseClaim', 'grain': '每笔报销一行',
                 'identity': ['报销单号'],
                 'properties': [{'column': '金额', 'name': 'amount'}]},
                {'table': 'departments', 'name': 'Department', 'grain': '每个部门一行',
                 'identity': ['部门名称']},
            ],
            'relationships': [{'evidence_id': link['id'], 'name': 'followsStandard'}],
        },
    }).data
    assert draft['state'] == 'pending'
    assert draft['unresolved_tables'] == []
    assert draft['unresolved_relationships'] == []
    assert draft['entities'][0]['evidence_sections'] == ['section:policy:3', 'clause:policy:2']


@pytest.mark.parametrize(('change', 'message'), [
    (lambda p: p['entities'][0].update(table='table:9'), 'unknown table'),
    (lambda p: p['entities'][0].update(
        properties=[{'column': '不存在的列', 'name': 'x'}]), 'unknown column'),
    (lambda p: p['entities'][0].update(identity=['城市等级']), 'observed key'),
    (lambda p: p['entities'][0].update(
        evidence_sections=['section:policy:9']), 'unknown evidence section'),
    (lambda p: p['entities'][0].update(
        evidence_sections=['clause:policy:9']), 'unknown evidence section'),
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
             'identity': ['部门名称']},
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


@pytest.mark.parametrize('policy_fields', [
    None,  # no disclosure policy at all
    [],  # an empty policy for the source
    ['城市等级', '职级', '费用类型', '限额', '币种'],  # table columns only
])
def test_document_text_stays_hidden_without_paragraph_text_disclosure(tmp_path, policy_fields):
    document_workspace(tmp_path)
    allowed = None if policy_fields is None else {'policy': policy_fields}
    wb = workbench(tmp_path, allowed=allowed)
    data = request(wb, start(wb, document_sources()))

    document, = data['catalog']['documents']
    title, = document['sections']
    assert title['title'] is None
    assert all(clause['text'] is None for clause in document['clauses'])
    # The heading structure and anchors are still evidence.
    assert title['level'] == 1 and title['paragraph_range'] == [1, 7]
    assert document['clauses'][0]['anchor']['selector']['unit_ref'] == 'paragraph:3'


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


def test_disclosed_document_text_is_truncated_like_a_table_sample(tmp_path):
    clause = '第一条 ' + '本' * 200
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        + _paragraph('报销制度', 1)
        + _paragraph(clause)
        + '<w:sectPr/></w:body></w:document>')
    (tmp_path / 'policy.docx').write_bytes(_docx_zip(document))
    wb = workbench(tmp_path, allowed={'policy': ['text']})
    data = request(wb, start(wb, [
        {'source_id': 'policy', 'kind': 'file', 'locator_ref': 'policy.docx'},
    ], goal='从制度文件发现对象'))
    document, = data['catalog']['documents']
    title, = document['sections']
    assert title['title'] == '报销制度'
    entry, = document['clauses']
    assert entry['text'] == clause[:160]
    assert len(entry['text']) == 160


def test_pdf_headings_become_real_sections_tables_and_clause_candidates():
    """A page with two chapter headings yields two sections, not one page section."""
    page1 = ('第一章 总则\n'
             '第一条 本制度适用于全体员工。\n'
             '第二章 标准\n'
             '一、这一行虽然以「一、」开头，但是一条很长的正文句子，结尾还有句号，因此不是标题。\n'
             '第二条 住宿按标准执行。')
    profile = SourceProfile(
        source_id='manual', source_revision='sha256:manual', kind='pdf',
        records=[], fields=[],
        metadata={
            'pages': [{'page': 1, 'text': page1, 'method': 'text'}],
            'tables': [
                {'page': 1, 'rows': [['城市等级', '限额'], ['一线', '400'], ['二线', '300']],
                 'bbox': [0.0, 0.0, 100.0, 100.0]},
                {'page': 1, 'rows': [['单号', '金额'], ['A-1', '10'], ['A-2', '20']],
                 'anchor': {'source_ref': 'manual', 'source_revision': 'sha256:manual',
                            'selector': {'kind': 'pdf_bbox', 'page': 1,
                                         'bbox': [1.0, 2.0, 3.0, 4.0]}}},
            ],
            'structure_fingerprint': 'manual',
        })
    catalog = build_catalog([profile], {'manual': {'城市等级', '限额', '单号', '金额', 'text'}})
    document, = catalog['documents']
    assert document['kind'] == 'pdf'
    chapters = document['sections']
    assert [(section['title'], section['level'], section['page']) for section in chapters] == [
        ('第一章 总则', 1, 1), ('第二章 标准', 1, 1)]
    assert [section['ref'] for section in chapters] == ['section:manual:1', 'section:manual:2']
    assert [section['line_range'] for section in chapters] == [[1, 2], [3, 5]]
    # The anchor replays to the heading line inside its page.
    second = chapters[1]
    assert second['anchor']['selector'] == {
        'kind': 'pdf_text_span', 'page': 1,
        'char_start': page1.index('第二章 标准'),
        'char_end': page1.index('第二章 标准') + len('第二章 标准')}
    assert [clause['number'] for clause in document['clauses']] == ['第一条', '第二条']
    assert [clause['ref'] for clause in document['clauses']] == ['clause:manual:1', 'clause:manual:2']
    assert document['clauses'][0]['text'] == '第一条 本制度适用于全体员工。'

    tables = {table['name']: table for table in catalog['tables']}
    assert set(tables) == {'page:1#1', 'page:1#2'}
    first = tables['page:1#1']
    assert first['rows_observed'] == 2
    assert first['columns']['限额']['samples'] == ['400', '300']
    assert ['城市等级'] in first['keys']
    # A PDF table carries the upstream bbox anchor of its detection.
    assert first['anchor']['selector'] == {'kind': 'pdf_bbox', 'page': 1,
                                           'bbox': [0.0, 0.0, 100.0, 100.0]}
    assert tables['page:1#2']['anchor']['selector']['bbox'] == [1.0, 2.0, 3.0, 4.0]
    assert document['record_sets'] == [
        {'name': 'page:1#1', 'kind': 'table', 'count': 2},
        {'name': 'page:1#2', 'kind': 'table', 'count': 2},
    ]


def test_pdf_sections_nest_across_pages_and_skip_non_headings():
    profile = SourceProfile(
        source_id='manual', source_revision='sha256:manual', kind='pdf',
        records=[], fields=[],
        metadata={
            'pages': [
                {'page': 1, 'method': 'text', 'text': (
                    '差旅报销标准\n'
                    '第一章 总则\n'
                    '备注：无\n'
                    '正文句子一行，不是标题。')},
                {'page': 2, 'method': 'text', 'text': (
                    '第一节 适用范围\n'
                    '1. 覆盖全部流程。')},
            ],
            'structure_fingerprint': 'manual',
        })
    catalog = build_catalog([profile], None)
    document, = catalog['documents']
    # '差旅报销标准' qualifies as the document's leading title line; '备注：无'
    # is a label and the sentence line is body text.
    title, chapter = document['sections']
    assert title['level'] == 1 and title['line_range'] == [1, 1]
    assert title['page_range'] == [1, 1]
    assert chapter['level'] == 1 and chapter['line_range'] == [2, 6]
    assert chapter['page_range'] == [1, 2]
    subsection, = chapter['sections']
    assert subsection['level'] == 2 and subsection['page'] == 2
    assert subsection['line_range'] == [5, 6]
    # No title without a disclosure: structure and anchors only.
    assert title['title'] is None and subsection['title'] is None
    assert [clause['number'] for clause in document['clauses']] == ['1.']
    assert document['clauses'][0]['text'] is None


def test_pdf_ordinary_short_prose_is_not_a_section():
    """Review counterexample: punctuation-free prose stays chapter body."""
    page = '第一章 总则\n本规定适用于员工\n第二章 标准'
    profile = SourceProfile(
        source_id='manual', source_revision='sha256:manual', kind='pdf',
        records=[], fields=[],
        metadata={
            'pages': [{'page': 1, 'text': page, 'method': 'text'}],
            'tables': [],
            'structure_fingerprint': 'manual',
        })
    catalog = build_catalog([profile], {'manual': {'text'}})
    document, = catalog['documents']
    chapters = document['sections']
    assert [section['title'] for section in chapters] == ['第一章 总则', '第二章 标准']
    # The prose line belongs to the first chapter instead of truncating it.
    assert chapters[0]['line_range'] == [1, 2]
    assert chapters[1]['line_range'] == [3, 3]


def test_pdf_unnumbered_heading_needs_title_position_or_larger_font():
    text = '总则\n正文一段。\n费用说明\n正文二段。'
    # '总则' is the document's leading line; '费用说明' is mid-page and only
    # qualifies when its block is taller than the page's body text.
    blocks = [
        {'text': '总则', 'bbox': [72.0, 90.0, 120.0, 102.0], 'char_start': 0, 'char_end': 2},
        {'text': '正文一段。', 'bbox': [72.0, 120.0, 300.0, 130.0], 'char_start': 3, 'char_end': 8},
        {'text': '费用说明', 'bbox': [72.0, 150.0, 200.0, 168.0], 'char_start': 9, 'char_end': 13},
        {'text': '正文二段。', 'bbox': [72.0, 180.0, 300.0, 190.0], 'char_start': 14, 'char_end': 19},
    ]
    profile = SourceProfile(
        source_id='manual', source_revision='sha256:manual', kind='pdf',
        records=[], fields=[],
        metadata={
            'pages': [{'page': 1, 'text': text, 'method': 'text', 'blocks': blocks}],
            'tables': [],
            'structure_fingerprint': 'manual',
        })
    catalog = build_catalog([profile], {'manual': {'text'}})
    document, = catalog['documents']
    assert [section['title'] for section in document['sections']] == ['总则', '费用说明']

    # Without block evidence the mid-page line has no layout support: body text.
    pages = [dict(page, blocks=[]) for page in profile.metadata['pages']]
    profile = profile.model_copy(
        update={'metadata': {**profile.metadata, 'pages': pages}})
    catalog = build_catalog([profile], {'manual': {'text'}})
    document, = catalog['documents']
    assert [section['title'] for section in document['sections']] == ['总则']


def test_docx_table_anchor_resolves_through_the_anchor_contract(tmp_path):
    """The table anchor is a contract cell anchor the replay engine resolves.

    The replay runs in the data layer's own interpreter, like the probe itself:
    the workbench process must not import ``dataagent_data``.
    """
    units = {
        'table:1/row:2/col:1': '一线',
        'table:1/row:2/col:4': '400',
    }

    def cell(row, col, text):
        return {'source_ref': 'manual', 'source_revision': 'sha256:manual',
                'selector': {'kind': 'text_span',
                             'unit_ref': f'table:1/row:{row}/col:{col}',
                             'char_start': 0, 'char_end': len(text)},
                'extensions': None}

    profile = SourceProfile(
        source_id='manual', source_revision='sha256:manual', kind='docx',
        records=[], fields=[],
        metadata={
            'paragraphs': [],
            'units': units,
            'record_sets': {
                'table:1': {
                    'name': 'table:1', 'kind': 'table', 'table': 1, 'count': 1,
                    'fields': ['城市等级', '限额'],
                    'records': [{'城市等级': '一线', '限额': '400'}],
                    'anchors': {'0.城市等级': [cell(2, 1, '一线')],
                                '0.限额': [cell(2, 4, '400')]},
                },
            },
            'structure_fingerprint': 'manual',
        })
    catalog = build_catalog([profile], {'manual': {'城市等级', '限额'}})
    table, = catalog['tables']

    # Contract validation: the anchor is a real SourceAnchor, selector and all.
    anchor = SourceAnchor.model_validate(table['anchor'])
    assert anchor.selector.kind == 'text_span'
    assert anchor.selector.unit_ref == 'table:1/row:2/col:1'

    script = tmp_path / 'replay_anchor.py'
    script.write_text(
        'import json, sys\n'
        'from dataagent_contracts.core import SourceAnchor\n'
        'from dataagent_data.anchors import AnchorResolver\n'
        'payload = json.load(open(sys.argv[1], encoding="utf-8"))\n'
        'resolved = AnchorResolver(units=payload["units"]).resolve(\n'
        '    SourceAnchor.model_validate(payload["anchor"]))\n'
        'print(json.dumps({"text": resolved.text, "reason": resolved.reason},\n'
        '                 ensure_ascii=False))\n', encoding='utf-8')

    def replay(anchor_dict):
        payload = tmp_path / 'anchor.json'
        payload.write_text(json.dumps({'anchor': anchor_dict, 'units': units}),
                           encoding='utf-8')
        result = subprocess.run(
            [str(PACKAGES / 'dataagent-data/.venv/bin/python'), str(script), str(payload)],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    # Replay through the data layer's resolver: table and column anchors
    # resolve to the cells they point at.
    assert replay(table['anchor']) == {'text': '一线', 'reason': ''}
    assert replay(table['columns']['限额']['anchor']) == {'text': '400', 'reason': ''}


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
    # The invoice is label:value lines with no heading, clause or table
    # structure, so no page is promoted to a section.
    assert documents[0]['sections'] == [] and documents[0]['clauses'] == []
