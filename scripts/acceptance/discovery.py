"""Discovery phase: ontology discovery over table-shaped and document sources.

It keeps the original SQLite acceptance and adds the D2a cases: two CSV files
linked by a customer number plus a JSON record set, one Excel workbook with two
table regions, an ambiguity with two equally matching targets, a REST connection
probed end to end, composite-key inference with its search gap.  The D2b case
runs a synthetic 差旅报销标准 docx (headings, numbered clauses and a standard
table) against a 报销明细 Excel and a department CSV whose codes coincidentally
equal the table limits: the evidence must carry sections, clause candidates and
the table's composite candidate key, the detail must link to the standard table
through the three-column combination, and the coincidental codes must not link.
All inputs are synthetic.
"""

import io
import json
import os
import shutil
import sqlite3
import zipfile

from .common import ROOT, call_workbench, loopback


INTAKE = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake'
EXCEL_REGIONS = INTAKE/'p1-files/samples/invoices-regions.xlsx'


def _write(project, name, content):
    (project/name).write_text(content, encoding='utf-8')


def _start(project, goal, sources, env=None):
    return call_workbench(project, 'intake_start', {
        'goal': goal, 'mode': 'ontology_discovery', 'sources': sources,
    }, env=env)['session_id']


def _advance(project, session_id, env=None):
    args = {'session_id': session_id}
    return args, call_workbench(project, 'intake_advance', args, env=env)


def _link(links, source, source_column):
    matches = [link for link in links
               if link['source_table'] == source and link['source_columns'] == [source_column]]
    assert len(matches) == 1, matches
    return matches[0]


def _csv_and_json(project):
    _write(project, 'orders.csv',
           'order_no,customer_no,amount_minor,currency\n'
           'SO-1,C-1001,120000,CNY\n'
           'SO-2,C-1001,80000,CNY\n'
           'SO-3,C-1002,56000,CNY\n')
    _write(project, 'customers.csv',
           'customer_no,name,city\n'
           'C-1001,Acme,Shanghai\n'
           'C-1002,Blue,Beijing\n'
           'C-1003,Cedar,Shenzhen\n')
    _write(project, 'records.json', json.dumps([
        {'record_no': 'R-1', 'customer_no': 'C-1002', 'label': 'inspection'},
        {'record_no': 'R-2', 'customer_no': 'C-1003', 'label': 'delivery'},
        {'record_no': 'R-3', 'customer_no': 'C-1002', 'label': 'inspection'},
    ], ensure_ascii=False))
    session_id = _start(project, '从订单、客户和检查记录发现业务对象', [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
        {'source_id': 'customers', 'kind': 'file', 'locator_ref': 'customers.csv'},
        {'source_id': 'records', 'kind': 'file', 'locator_ref': 'records.json'},
    ])
    args, request = _advance(project, session_id)
    assert request['kind'] == 'ontology_discovery'
    assert request['coverage'] == 'full'
    assert sorted(request['source_ids']) == ['customers', 'orders', 'records']
    tables = {table['name']: table for table in request['catalog']['tables']}
    assert set(tables) == {'orders', 'customers', 'records'}
    assert {name: table['rows_observed'] for name, table in tables.items()} == {
        'orders': 3, 'customers': 3, 'records': 3}
    column = tables['orders']['columns']['customer_no']
    assert column['affinity'] == 'text'
    assert column['null_rows'] == 0 and column['null_rate'] == 0.0
    assert column['distinct_values'] == 2 and column['unique'] is False
    # No allowed_fields policy was configured: counts and type statistics only.
    assert column['samples'] == []
    assert ['order_no'] in tables['orders']['keys']
    assert ['customer_no'] not in tables['orders']['keys']
    assert ['customer_no'] in tables['customers']['identity_keys']

    links = request['catalog']['relationships']
    orders_link = _link(links, 'orders', 'customer_no')
    assert orders_link['target_table'] == 'customers'
    assert orders_link['origin'] == 'sample_supported'
    assert orders_link['matched_rows'] == 3 and orders_link['checked_rows'] == 3
    assert orders_link['matched_distinct_keys'] == 2
    assert orders_link['ambiguous'] is False
    records_link = _link(links, 'records', '/customer_no')
    assert records_link['target_table'] == 'customers'
    assert records_link['matched_rows'] == 3

    draft = call_workbench(project, 'ontology_discovery_propose', {
        **args, 'expected_revision': request['expected_revision'],
        'proposal': {
            'source_revision': request['source_revision'],
            'entities': [
                {'table': 'customers', 'name': 'Customer', 'grain': '每个客户一行',
                 'identity': ['customer_no'],
                 'properties': [{'column': 'name', 'name': 'name'}]},
                {'table': 'orders', 'name': 'SalesOrder', 'grain': '每个订单一行',
                 'identity': ['order_no'],
                 'properties': [{'column': 'amount_minor', 'name': 'amountMinor'}]},
                {'table': 'records', 'name': 'Inspection', 'grain': '每条检查记录一行',
                 'identity': ['/record_no'],
                 'properties': [{'column': '/label', 'name': 'label'}]},
            ],
            'relationships': [
                {'evidence_id': orders_link['id'], 'name': 'placedBy'},
                {'evidence_id': records_link['id'], 'name': 'inspectionFor'},
            ],
        },
    })
    assert draft['state'] == 'pending'
    assert draft['unresolved_tables'] == []
    return {
        'session_id': session_id,
        'tables': {name: {'rows_observed': table['rows_observed'],
                          'columns': sorted(table['columns']),
                          'identity_keys': table['identity_keys']}
                   for name, table in tables.items()},
        'relationships': [{'source': link['source_table'],
                           'source_columns': link['source_columns'],
                           'target': link['target_table'],
                           'matched_rows': link['matched_rows'],
                           'checked_rows': link['checked_rows']} for link in links],
        'draft_ref': draft['ref'],
    }


def _excel_regions(project):
    shutil.copy2(EXCEL_REGIONS, project/'expenses.xlsx')
    session_id = _start(project, '从一个工作簿的两个表区发现对象', [
        {'source_id': 'expenses', 'kind': 'file', 'locator_ref': 'expenses.xlsx'},
    ])
    args, request = _advance(project, session_id)
    tables = request['catalog']['tables']
    assert len(tables) == 2
    assert {table['rows_observed'] for table in tables} == {3}
    assert {table['coverage'] for table in tables} == {'full'}
    assert len({table['name'] for table in tables}) == 2
    by_columns = {len(table['columns']): table for table in tables}
    assert set(by_columns) == {6, 4}
    detail, expenses = by_columns[6], by_columns[4]
    assert {'发票号', '币种'} <= detail['columns'].keys()
    assert {'报销单号', '费用类别', '报销金额（分）'} <= expenses['columns'].keys()
    assert ['发票号'] in detail['identity_keys']
    assert ['报销单号'] in expenses['identity_keys']

    draft = call_workbench(project, 'ontology_discovery_propose', {
        **args, 'expected_revision': request['expected_revision'],
        'proposal': {
            'source_revision': request['source_revision'],
            'entities': [
                {'table': detail['name'], 'name': 'Invoice', 'grain': '每张发票一行',
                 'identity': ['发票号']},
                {'table': expenses['name'], 'name': 'Expense', 'grain': '每张报销单一行',
                 'identity': ['报销单号']},
            ],
        },
    })
    assert draft['state'] == 'pending' and draft['unresolved_tables'] == []
    return {
        'session_id': session_id,
        'regions': [{'name': table['name'], 'rows_observed': table['rows_observed'],
                     'field_count': len(table['columns']),
                     'identity_keys': table['identity_keys']} for table in tables],
        'draft_ref': draft['ref'],
    }


def _ambiguous_targets(project):
    _write(project, 'ambiguous-orders.csv',
           'order_no,customer_no\nSO-1,C-1\nSO-2,C-1\nSO-3,C-2\n')
    for name in ('customers-a.csv', 'customers-b.csv'):
        _write(project, name, 'customer_no,name\nC-1,Alpha\nC-2,Beta\n')
    session_id = _start(project, '核对两条同样吻合的客户来源', [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'ambiguous-orders.csv'},
        {'source_id': 'customers_a', 'kind': 'file', 'locator_ref': 'customers-a.csv'},
        {'source_id': 'customers_b', 'kind': 'file', 'locator_ref': 'customers-b.csv'},
    ])
    _, request = _advance(project, session_id)
    links = request['catalog']['relationships']
    assert len(links) == 2
    assert {link['target_table'] for link in links} == {'customers_a', 'customers_b'}
    assert all(link['source_table'] == 'orders'
               and link['source_columns'] == ['customer_no']
               and link['matched_rows'] == 3
               and link['ambiguous'] is True for link in links)
    return {
        'session_id': session_id,
        'targets': sorted(link['target_table'] for link in links),
        'ambiguous': all(link['ambiguous'] for link in links),
    }


def _composite_keys(project):
    """Three-column keys are candidates; a bounded search discloses its gap."""
    _write(project, 'matrix.csv',
           'a,b,c\n0,0,0\n0,0,1\n0,1,0\n1,0,0\n')
    _write(project, 'wide.csv',
           'a,b,c,d,e,f\n1,1,1,1,1,1\n1,1,1,1,1,1\n')
    _write(project, 'surrogate.csv',
           'row_id,tenant,invoice_no\n'
           '1,A,100\n2,A,101\n3,B,100\n4,B,101\n')
    session_id = _start(project, '从三个小表发现联合标识', [
        {'source_id': 'matrix', 'kind': 'file', 'locator_ref': 'matrix.csv'},
        {'source_id': 'wide', 'kind': 'file', 'locator_ref': 'wide.csv'},
        {'source_id': 'surrogate', 'kind': 'file', 'locator_ref': 'surrogate.csv'},
    ])
    args, request = _advance(project, session_id)
    tables = {table['name']: table for table in request['catalog']['tables']}
    assert tables['matrix']['keys'] == [['a', 'b', 'c']]
    assert tables['matrix']['identity_keys'] == [['a', 'b', 'c']]
    assert tables['matrix']['key_search']['truncated'] is False
    assert tables['wide']['keys'] == []
    assert tables['wide']['key_search']['truncated'] is True
    assert tables['surrogate']['keys'] == [['row_id'], ['tenant', 'invoice_no']]
    gap, = [gap for gap in request['catalog']['gaps']
            if gap['code'] == 'key_search_truncated']
    assert gap['source_id'] == 'wide' and gap['table'] == 'wide'
    draft = call_workbench(project, 'ontology_discovery_propose', {
        **args, 'expected_revision': request['expected_revision'],
        'proposal': {
            'source_revision': request['source_revision'],
            'entities': [
                {'table': 'matrix', 'name': 'Matrix', 'grain': '每行一条观测',
                 'identity': ['a', 'b', 'c']},
                {'table': 'wide', 'name': 'Wide', 'grain': '每行一条观测'},
                {'table': 'surrogate', 'name': 'Surrogate', 'grain': '每张发票一行',
                 'identity': ['tenant', 'invoice_no']},
            ],
        },
    })
    assert draft['state'] == 'pending' and draft['unresolved_tables'] == []
    return {
        'session_id': session_id,
        'matrix_keys': tables['matrix']['identity_keys'],
        'wide_truncated': tables['wide']['key_search']['truncated'],
        'surrogate_keys': tables['surrogate']['identity_keys'],
        'gap': {'source_id': gap['source_id'], 'table': gap['table'],
                'code': gap['code']},
        'draft_ref': draft['ref'],
    }


def _rest_and_csv(project):
    """REST discovery traverses a host-configured connection end to end."""
    from fastapi import FastAPI

    app = FastAPI()
    reads = {'count': 0}

    @app.get('/invoices')
    def invoices():
        reads['count'] += 1
        return {
            'version': 'discovery-rest-1',
            'items': [
                {'invoice_no': 'INV-1', 'customer_no': 'C-1001', 'amount_minor': 120000},
                {'invoice_no': 'INV-2', 'customer_no': 'C-1002', 'amount_minor': 80000},
                {'invoice_no': 'INV-3', 'customer_no': 'C-1001', 'amount_minor': 56000},
            ],
            'next': None,
        }

    _write(project, 'rest-customers.csv',
           'customer_no,name\nC-1001,Acme\nC-1002,Blue\nC-1003,Cedar\n')
    with loopback(app) as url:
        config = project/'discovery-rest-connections.json'
        config.write_text(json.dumps({'billing': {
            'kind': 'rest', 'label': 'D2a billing API',
            'locator': url+'/invoices', 'allowed_origins': [url],
            'options': {'records_path': '/items', 'keys': ['/invoice_no'],
                        'source_version_path': '/version',
                        'pagination': {'next_path': '/next'}},
        }}))
        env = {**os.environ, 'DATAAGENT_SOURCE_CONNECTIONS': str(config)}
        session_id = _start(project, '从账单接口和客户表发现对象', [
            {'source_id': 'billing', 'kind': 'rest', 'locator_ref': 'billing'},
            {'source_id': 'rest_customers', 'kind': 'file', 'locator_ref': 'rest-customers.csv'},
        ], env=env)
        args, request = _advance(project, session_id, env=env)

        assert request['kind'] == 'ontology_discovery'
        assert request['coverage'] == 'full'
        tables = {table['name']: table for table in request['catalog']['tables']}
        assert set(tables) == {'billing', 'rest_customers'}
        billing = tables['billing']
        assert billing['rows_observed'] == 3
        assert billing['columns']['/customer_no']['affinity'] == 'text'
        assert billing['columns']['/customer_no']['samples'] == []
        assert ['/invoice_no'] in billing['identity_keys']
        link = _link(request['catalog']['relationships'], 'billing', '/customer_no')
        assert link['target_table'] == 'rest_customers'
        assert link['matched_rows'] == 3 and link['checked_rows'] == 3
        assert reads['count'] == 1, reads

        draft = call_workbench(project, 'ontology_discovery_propose', {
            **args, 'expected_revision': request['expected_revision'],
            'proposal': {
                'source_revision': request['source_revision'],
                'entities': [
                    {'table': 'billing', 'name': 'Invoice', 'grain': '每张账单一行',
                     'identity': ['/invoice_no'],
                     'properties': [{'column': '/amount_minor', 'name': 'amountMinor'}]},
                    {'table': 'rest_customers', 'name': 'Customer', 'grain': '每个客户一行',
                     'identity': ['customer_no']},
                ],
                'relationships': [{'evidence_id': link['id'], 'name': 'billedTo'}],
            },
        }, env=env)
        assert draft['state'] == 'pending' and draft['unresolved_tables'] == []
    return {
        'session_id': session_id,
        'tables': {name: {'rows_observed': table['rows_observed'],
                          'columns': sorted(table['columns']),
                          'identity_keys': table['identity_keys']}
                   for name, table in tables.items()},
        'relationship': {'source': link['source_table'],
                         'source_columns': link['source_columns'],
                         'target': link['target_table'],
                         'matched_rows': link['matched_rows']},
        'requests': reads['count'],
        'draft_ref': draft['ref'],
    }


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

_DOCX_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>')
_DOCX_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>')


def _docx_paragraph(text, level=None):
    # An explicit outline level marks the heading without needing styles.xml.
    properties = (f'<w:pPr><w:outlineLvl w:val="{level - 1}"/></w:pPr>'
                  if level is not None else '')
    return f'<w:p>{properties}<w:r><w:t>{text}</w:t></w:r></w:p>'


def _write_policy_docx(project):
    rows = ('<w:tr>' + ''.join(
        f'<w:tc><w:tcPr/><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>'
        for cell in row) + '</w:tr>' for row in STANDARD_ROWS)
    table = ('<w:tbl><w:tblPr/><w:tblGrid>' + '<w:gridCol/>' * len(STANDARD_ROWS[0])
             + '</w:tblGrid>' + ''.join(rows) + '</w:tbl>')
    document = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        + _docx_paragraph('差旅报销标准', 1)
        + _docx_paragraph('总则', 2)
        + _docx_paragraph('第一条 本标准适用于全体员工出差费用报销。')
        + _docx_paragraph('第二条 城市等级分为一线、二线两档。')
        + _docx_paragraph('费用标准', 2)
        + table
        + _docx_paragraph('附则', 2)
        + _docx_paragraph('第三条 本标准自发布之日起执行。')
        + '<w:sectPr/></w:body></w:document>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', _DOCX_TYPES)
        archive.writestr('_rels/.rels', _DOCX_RELS)
        archive.writestr('word/document.xml', document)
    (project/'policy.docx').write_bytes(buffer.getvalue())


def _write_detail_xlsx(project):
    sheet_rows = []
    for row_number, values in enumerate(DETAIL_ROWS, start=1):
        cells = ''.join(
            f'<c r="{chr(ord("A") + column)}{row_number}" t="inlineStr">'
            f'<is><t>{value}</t></is></c>'
            for column, value in enumerate(values))
        sheet_rows.append(f'<row r="{row_number}">{cells}</row>')
    with zipfile.ZipFile(project/'detail.xlsx', 'w', zipfile.ZIP_DEFLATED) as book:
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


def _document_sources(project):
    """A policy docx, a claim workbook and a CSV with coincidentally equal codes."""
    _write_policy_docx(project)
    _write_detail_xlsx(project)
    (project/'departments.csv').write_text(DEPARTMENTS_CSV, encoding='utf-8')
    session_id = _start(project, '从差旅报销标准和报销明细发现对象', [
        {'source_id': 'policy', 'kind': 'file', 'locator_ref': 'policy.docx'},
        {'source_id': 'detail', 'kind': 'file', 'locator_ref': 'detail.xlsx'},
        {'source_id': 'departments', 'kind': 'file', 'locator_ref': 'departments.csv'},
    ])
    args, request = _advance(project, session_id)
    assert request['kind'] == 'ontology_discovery'
    tables = {table['name']: table for table in request['catalog']['tables']}
    assert set(tables) == {'table:1', '明细', 'departments'}
    standard = tables['table:1']
    assert standard['kind'] == 'docx' and standard['rows_observed'] == 6
    assert set(standard['columns']) == {'城市等级', '职级', '费用类型', '限额', '币种'}
    assert ['城市等级', '职级', '费用类型'] in standard['identity_keys']
    # The table and its columns carry the record set's cell anchors, so the
    # key and the link below replay to a concrete table position.  The table
    # anchor is the record set's top-left cell and validates as a contract
    # text_span anchor.
    from dataagent_contracts.core import SourceAnchor
    table_anchor = SourceAnchor.model_validate(standard['anchor'])
    assert table_anchor.selector.kind == 'text_span'
    assert table_anchor.selector.unit_ref == 'table:1/row:2/col:1'
    city = standard['columns']['城市等级']['anchor']['selector']
    assert (city['kind'], city['unit_ref']) == ('text_span', 'table:1/row:2/col:1')

    document, = request['catalog']['documents']
    assert document['source_id'] == 'policy' and document['kind'] == 'docx'
    title, = document['sections']
    # No field-disclosure policy is configured in acceptance, so the evidence
    # carries the heading structure and anchors without the titles themselves.
    assert title['level'] == 1 and title['title'] is None
    assert title['paragraph_range'] == [1, 7]
    assert title['ref'] == 'section:policy:1'
    assert title['anchor']['selector']['unit_ref'] == 'paragraph:1'
    assert [(section['level'], section['paragraph_range'])
            for section in title['sections']] == [(2, [2, 4]), (2, [5, 5]), (2, [6, 7])]
    assert [section['ref'] for section in title['sections']] == [
        'section:policy:2', 'section:policy:3', 'section:policy:4']
    assert [clause['number'] for clause in document['clauses']] == ['第一条', '第二条', '第三条']
    assert [clause['ref'] for clause in document['clauses']] == [
        'clause:policy:1', 'clause:policy:2', 'clause:policy:3']
    assert all(clause['text'] is None and clause['anchor'] for clause in document['clauses'])
    assert document['record_sets'] == [
        {'name': 'paragraphs', 'kind': 'paragraph', 'count': 7},
        {'name': 'table:1', 'kind': 'table', 'count': 6},
    ]

    # The detail links through the three-column composite key; the department
    # codes that coincidentally equal the limits must not become a link.
    links = request['catalog']['relationships']
    assert [(link['source_table'], link['source_columns'], link['target_table'],
             link['target_columns']) for link in links] == [
        ('明细', ['城市等级', '职级', '费用类型'], 'table:1',
         ['城市等级', '职级', '费用类型'])]
    link, = links
    assert link['origin'] == 'sample_supported' and link['ambiguous'] is False
    assert link['matched_rows'] == 4 and link['checked_rows'] == 4
    assert link['matched_distinct_keys'] == 4
    # The link's document endpoint replays to a contract cell anchor of its table.
    assert tables[link['target_table']]['anchor']['selector']['unit_ref'].startswith('table:1/')

    draft = call_workbench(project, 'ontology_discovery_propose', {
        **args, 'expected_revision': request['expected_revision'],
        'proposal': {
            'source_revision': request['source_revision'],
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
    })
    assert draft['state'] == 'pending' and draft['unresolved_tables'] == []
    standard_entity, = [entity for entity in draft['entities'] if entity['table'] == 'table:1']
    assert standard_entity['evidence_sections'] == ['section:policy:3', 'clause:policy:2']
    return {
        'session_id': session_id,
        'sections': [{'level': section['level'],
                      'paragraph_range': section['paragraph_range']}
                     for section in title['sections']],
        'clauses': [clause['number'] for clause in document['clauses']],
        'evidence_sections': standard_entity['evidence_sections'],
        'standard': {'name': standard['name'], 'rows_observed': standard['rows_observed'],
                     'columns': sorted(standard['columns']),
                     'identity_keys': standard['identity_keys']},
        'relationship': {'source': link['source_table'],
                         'source_columns': link['source_columns'],
                         'target': link['target_table'],
                         'target_columns': link['target_columns'],
                         'matched_rows': link['matched_rows'],
                         'matched_distinct_keys': link['matched_distinct_keys']},
        'draft_ref': draft['ref'],
    }


def verify(project):
    seed = INTAKE/'sales-discovery.sql'
    with sqlite3.connect(project/'sales-discovery.db') as db:
        db.executescript(seed.read_text())
    started = call_workbench(project, 'intake_start', {
        'goal': '从陌生数据库识别销售订单、明细和客户',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'sales', 'kind': 'sqlite', 'locator_ref': 'sales-discovery.db'}],
    })
    args = {'session_id': started['session_id']}
    request = call_workbench(project, 'intake_advance', args)
    assert request['kind'] == 'ontology_discovery' and request['coverage'] == 'full'
    assert 'allowed_target' not in request
    tables = {table['name']: table for table in request['catalog']['tables']}
    assert {name: table['rows_observed'] for name, table in tables.items()} == {
        'party': 2, 'doc_hdr': 2, 'doc_line': 3,
    }
    fk, = [link for link in request['catalog']['relationships'] if link['origin'] == 'declared']
    inferred, = [link for link in request['catalog']['relationships'] if link['origin'] == 'sample_supported']
    assert fk['target_columns'] == ['book', 'doc_no'] and fk['matched_rows'] == 3
    assert inferred['target_table'] == 'party' and inferred['matched_rows'] == 2
    draft = call_workbench(project, 'ontology_discovery_propose', {
        **args, 'expected_revision': request['expected_revision'], 'proposal': {
            'source_revision': request['source_revision'],
            'entities': [
                {'table': 'party', 'name': 'Customer', 'grain': '每个客户一行',
                 'identity': ['party_no'], 'properties': [{'column': 'nm', 'name': 'name'}]},
                {'table': 'doc_hdr', 'name': 'SalesOrder', 'grain': '每个账簿内的一份销售单',
                 'identity': ['book', 'doc_no']},
                {'table': 'doc_line', 'name': 'SalesOrderLine', 'grain': '销售单的一条明细',
                 'identity': ['book', 'doc_no', 'seq'],
                 'properties': [{'column': 'cents', 'name': 'amountInCents'}]},
            ],
            'relationships': [
                {'evidence_id': fk['id'], 'name': 'belongsToOrder'},
                {'evidence_id': inferred['id'], 'name': 'orderedBy'},
            ],
        },
    })
    assert draft['state'] == 'pending'
    reloaded = call_workbench(project, 'intake_inference', args)
    assert reloaded['draft'] == {'ref': draft['ref'], 'state': 'pending'}
    return {
        **args, 'source_revision': request['source_revision'], 'draft': draft,
        'table_sources': _csv_and_json(project),
        'excel_regions': _excel_regions(project),
        'ambiguous_targets': _ambiguous_targets(project),
        'rest_sources': _rest_and_csv(project),
        'composite_keys': _composite_keys(project),
        'document_sources': _document_sources(project),
    }


def apply(report, project, args, context):
    report['discovery'] = verify(project)
    report['not_verified'] = ['model-generated ontology proposal'] + [
        item for item in report['not_verified'] if item != 'file processing']
