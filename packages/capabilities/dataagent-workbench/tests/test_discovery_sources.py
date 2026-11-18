"""Discovery evidence for table-shaped sources beyond one SQLite database."""
import json
import shutil
from pathlib import Path

import pytest

from dataagent_contracts.intake import SourceAnchor, SourceProfile
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.service_tools import invoke


PACKAGES = Path(__file__).resolve().parents[2]
FIXTURES = PACKAGES / 'dataagent-scenarios/fixtures/intake'
EXCEL_REGIONS = FIXTURES / 'p1-files/samples/invoices-regions.xlsx'


def workbench(tmp_path, allowed=None):
    return Workbench(tmp_path, layer_client=LayerClient(PACKAGES / 'dataagent-data'),
                     allowed_model_fields=allowed)


def start(wb, sources, goal='发现业务对象'):
    return invoke(wb, 'intake_start', {
        'goal': goal, 'mode': 'ontology_discovery', 'sources': sources,
    }).data['session_id']


def request(wb, session_id):
    invoke(wb, 'intake_advance', {'session_id': session_id})
    return invoke(wb, 'intake_inference', {'session_id': session_id}).data


def write(path, content):
    path.write_text(content, encoding='utf-8')


def csv_sources(tmp_path):
    write(tmp_path / 'orders.csv',
          'order_no,customer_no,amount_minor,currency\n'
          'SO-1,C-1001,120000,CNY\n'
          'SO-2,C-1001,80000,CNY\n'
          'SO-3,C-1002,56000,CNY\n')
    write(tmp_path / 'customers.csv',
          'customer_no,name,city\n'
          'C-1001,Acme,Shanghai\n'
          'C-1002,Blue,Beijing\n'
          'C-1003,Cedar,Shenzhen\n')
    write(tmp_path / 'records.json', json.dumps([
        {'record_no': 'R-1', 'customer_no': 'C-1002', 'label': 'inspection'},
        {'record_no': 'R-2', 'customer_no': 'C-1003', 'label': 'delivery'},
        {'record_no': 'R-3', 'customer_no': 'C-1002', 'label': 'inspection'},
    ], ensure_ascii=False))


def csv_workbench(tmp_path):
    return workbench(tmp_path, allowed={
        'orders': ['order_no', 'customer_no', 'amount_minor', 'currency'],
        'customers': ['customer_no', 'name', 'city'],
        'records': ['/record_no', '/customer_no', '/label'],
    })


def csv_sources_args():
    return [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
        {'source_id': 'customers', 'kind': 'file', 'locator_ref': 'customers.csv'},
        {'source_id': 'records', 'kind': 'file', 'locator_ref': 'records.json'},
    ]


def test_two_csv_and_json_record_evidence_and_cross_source_links(tmp_path):
    csv_sources(tmp_path)
    wb = csv_workbench(tmp_path)
    data = request(wb, start(wb, csv_sources_args()))

    assert data['kind'] == 'ontology_discovery'
    assert data['coverage'] == 'full'
    assert sorted(data['source_ids']) == ['customers', 'orders', 'records']
    tables = {table['name']: table for table in data['catalog']['tables']}
    assert set(tables) == {'orders', 'customers', 'records'}
    assert {name: table['rows_observed'] for name, table in tables.items()} == {
        'orders': 3, 'customers': 3, 'records': 3,
    }
    sources = {source['source_id']: source for source in data['catalog']['sources']}
    assert {source['coverage'] for source in sources.values()} == {'full'}
    assert data['catalog']['gaps'] == []
    assert tables['orders']['rows_total'] == 3

    orders = tables['orders']
    customer_no = orders['columns']['customer_no']
    assert customer_no['affinity'] == 'text'
    assert customer_no['null_rows'] == 0 and customer_no['null_rate'] == 0.0
    assert customer_no['distinct_values'] == 2 and customer_no['unique'] is False
    assert customer_no['samples'] == ['C-1001', 'C-1002']
    assert ['order_no'] in orders['keys']
    assert ['customer_no'] not in orders['keys']
    assert ['customer_no'] in tables['customers']['identity_keys']
    assert tables['customers']['columns']['customer_no']['unique'] is True

    links = data['catalog']['relationships']
    by_slot = {(link['source_table'], tuple(link['source_columns']),
                link['target_table'], tuple(link['target_columns'])): link for link in links}
    orders_link = by_slot[('orders', ('customer_no',), 'customers', ('customer_no',))]
    assert orders_link['origin'] == 'sample_supported'
    assert orders_link['matched_rows'] == 3 and orders_link['checked_rows'] == 3
    assert orders_link['matched_distinct_keys'] == 2
    assert orders_link['ambiguous'] is False
    assert orders_link['cardinality'] == 'many_to_one'
    records_link = by_slot[('records', ('/customer_no',), 'customers', ('customer_no',))]
    assert records_link['matched_rows'] == 3
    assert records_link['matched_distinct_keys'] == 2

    proposal = {
        'source_revision': data['source_revision'],
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
    }
    draft = invoke(wb, 'ontology_discovery_propose', {
        'session_id': data['session_id'],
        'expected_revision': data['expected_revision'],
        'proposal': proposal,
    }).data
    assert draft['state'] == 'pending'
    assert draft['unresolved_tables'] == []
    assert draft['unresolved_relationships'] == []
    assert {entity['name'] for entity in draft['entities']} == {
        'Customer', 'SalesOrder', 'Inspection'}


@pytest.mark.parametrize(('change', 'message'), [
    (lambda p: p['entities'][0].update(table='fabricated'), 'unknown table'),
    (lambda p: p['entities'][1].update(identity=['customer_no']), 'observed key'),
    (lambda p: p['entities'][1]['properties'][0].update(column='secret'), 'unknown column'),
    (lambda p: p['relationships'][0].update(evidence_id='invented'), 'unknown relationship'),
])
def test_new_source_proposal_rejects_unanchored_input(tmp_path, change, message):
    csv_sources(tmp_path)
    wb = csv_workbench(tmp_path)
    data = request(wb, start(wb, csv_sources_args()))
    links = {(link['source_table'], link['target_table']): link
             for link in data['catalog']['relationships']}
    proposal = {
        'source_revision': data['source_revision'],
        'entities': [
            {'table': 'customers', 'name': 'Customer', 'grain': '每个客户一行',
             'identity': ['customer_no']},
            {'table': 'orders', 'name': 'SalesOrder', 'grain': '每个订单一行',
             'identity': ['order_no'],
             'properties': [{'column': 'amount_minor', 'name': 'amountMinor'}]},
            {'table': 'records', 'name': 'Inspection', 'grain': '每条检查记录一行',
             'identity': ['/record_no']},
        ],
        'relationships': [
            {'evidence_id': links[('orders', 'customers')]['id'], 'name': 'placedBy'},
            {'evidence_id': links[('records', 'customers')]['id'], 'name': 'inspectionFor'},
        ],
    }
    change(proposal)
    with pytest.raises(ValueError, match=message):
        invoke(wb, 'ontology_discovery_propose', {
            'session_id': data['session_id'],
            'expected_revision': data['expected_revision'],
            'proposal': proposal,
        })


def test_default_disclosure_returns_statistics_without_samples(tmp_path):
    csv_sources(tmp_path)
    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'customers', 'kind': 'file', 'locator_ref': 'customers.csv'},
    ]))
    table, = data['catalog']['tables']
    assert table['columns']['customer_no']['samples'] == []
    assert table['columns']['customer_no']['distinct_values'] == 3
    assert table['rows_observed'] == 3


def test_excel_two_table_regions_are_separate_evidence(tmp_path):
    shutil.copy2(EXCEL_REGIONS, tmp_path / 'expenses.xlsx')
    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'expenses', 'kind': 'file', 'locator_ref': 'expenses.xlsx'},
    ]))

    tables = data['catalog']['tables']
    assert len(tables) == 2
    assert {table['rows_observed'] for table in tables} == {3}
    assert {table['coverage'] for table in tables} == {'full'}
    assert len({table['name'] for table in tables}) == 2
    by_columns = {len(table['columns']): table for table in tables}
    assert set(by_columns) == {6, 4}
    detail = by_columns[6]
    expenses = by_columns[4]
    assert {'发票号', '币种'} <= detail['columns'].keys()
    assert {'报销单号', '费用类别', '报销金额（分）'} <= expenses['columns'].keys()
    assert ['发票号'] in detail['identity_keys']
    assert ['报销单号'] in expenses['identity_keys']
    assert data['catalog']['relationships'] == []

    proposal = {
        'source_revision': data['source_revision'],
        'entities': [
            {'table': detail['name'], 'name': 'Invoice', 'grain': '每张发票一行',
             'identity': ['发票号']},
            {'table': expenses['name'], 'name': 'Expense', 'grain': '每张报销单一行',
             'identity': ['报销单号']},
        ],
    }
    draft = invoke(wb, 'ontology_discovery_propose', {
        'session_id': data['session_id'],
        'expected_revision': data['expected_revision'],
        'proposal': proposal,
    }).data
    assert draft['state'] == 'pending'
    assert draft['unresolved_tables'] == []


def test_two_equally_matching_targets_are_ambiguous(tmp_path):
    write(tmp_path / 'orders.csv',
          'order_no,customer_no\n'
          'SO-1,C-1\n'
          'SO-2,C-1\n'
          'SO-3,C-2\n')
    for name in ('customers_a.csv', 'customers_b.csv'):
        write(tmp_path / name,
              'customer_no,name\n'
              'C-1,Alpha\n'
              'C-2,Beta\n')
    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'orders', 'kind': 'file', 'locator_ref': 'orders.csv'},
        {'source_id': 'customers_a', 'kind': 'file', 'locator_ref': 'customers_a.csv'},
        {'source_id': 'customers_b', 'kind': 'file', 'locator_ref': 'customers_b.csv'},
    ]))

    links = data['catalog']['relationships']
    assert len(links) == 2
    assert {link['target_table'] for link in links} == {'customers_a', 'customers_b'}
    assert all(link['source_table'] == 'orders' for link in links)
    assert all(link['source_columns'] == ['customer_no'] for link in links)
    assert all(link['ambiguous'] is True for link in links)
    assert all(link['matched_rows'] == 3 for link in links)


def test_blank_observed_key_is_rejected_as_identity(tmp_path):
    write(tmp_path / 'customers.csv',
          'customer_no,name\n'
          'C-1,Alpha\n'
          'C-2,Beta\n'
          '   ,Gamma\n')
    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'customers', 'kind': 'file', 'locator_ref': 'customers.csv'},
    ]))
    table, = data['catalog']['tables']
    column = table['columns']['customer_no']
    assert column['null_rows'] == 0 and column['blank_rows'] == 1
    assert ['customer_no'] not in table['identity_keys']
    with pytest.raises(ValueError, match='observed key'):
        invoke(wb, 'ontology_discovery_propose', {
            'session_id': data['session_id'],
            'expected_revision': data['expected_revision'],
            'proposal': {
                'source_revision': data['source_revision'],
                'entities': [{'table': 'customers', 'name': 'Customer',
                              'grain': '每个客户一行', 'identity': ['customer_no']}],
            },
        })


@pytest.mark.parametrize('suffix', ['.pdf', '.docx'])
def test_document_sources_wait_for_d2b(tmp_path, suffix):
    locator = 'policy' + suffix
    if suffix == '.pdf':
        shutil.copy2(FIXTURES / 'invoice.pdf', tmp_path / locator)
    else:
        (tmp_path / locator).write_bytes(b'not a real document')
    wb = workbench(tmp_path)
    with pytest.raises(ValueError, match='D2b'):
        invoke(wb, 'intake_start', {
            'goal': '从制度文件发现对象', 'mode': 'ontology_discovery',
            'sources': [{'source_id': 'policy', 'kind': 'file', 'locator_ref': locator}],
        })


def test_excel_parallel_regions_with_same_header_are_separate(tmp_path):
    from dataagent_workbench.discovery_catalog import build_catalog

    cells = [('A1', 'B1'), ('A2', 'B2'), ('D1', 'E1'), ('D2', 'E2')]
    records = [{'id': 'A-1', 'name': 'Alpha'}, {'id': 'A-2', 'name': 'Beta'},
               {'id': 'B-1', 'name': 'Gamma'}, {'id': 'B-2', 'name': 'Delta'}]
    anchors = {}
    for index, (first, second) in enumerate(cells):
        anchors[f'{index}.id'] = [SourceAnchor(
            source_ref='book', source_revision='sha256:book',
            selector={'kind': 'excel_cell', 'sheet': 'Sheet1', 'range': first})]
        anchors[f'{index}.name'] = [SourceAnchor(
            source_ref='book', source_revision='sha256:book',
            selector={'kind': 'excel_cell', 'sheet': 'Sheet1', 'range': second})]
    profile = SourceProfile(
        source_id='book', source_revision='sha256:book', kind='xlsx',
        records=records, fields=['id', 'name'], anchors=anchors,
        metadata={'structure_fingerprint': 'book', 'total_rows': 4})
    catalog = build_catalog([profile], {'book': {'id', 'name'}})
    tables = catalog['tables']
    assert len(tables) == 2
    assert {table['rows_observed'] for table in tables} == {2}
    assert sorted(table['name'] for table in tables) == ['Sheet1#1', 'Sheet1#2']
    assert all(['id'] in table['identity_keys'] for table in tables)
    assert all(table['partition'] == 'Sheet1' for table in tables)


def test_excel_side_by_side_same_header_workbook_keeps_two_regions(tmp_path):
    import zipfile

    rows = (['id', 'name', None, 'id', 'name'],
            ['A-1', 'Alpha', None, 'B-1', 'Gamma'],
            ['A-2', 'Beta', None, 'B-2', 'Delta'])
    sheet_rows = []
    for row_number, values in enumerate(rows, start=1):
        cells = ''.join(
            f'<c r="{chr(ord("A") + column)}{row_number}" t="inlineStr">'
            f'<is><t>{value}</t></is></c>'
            for column, value in enumerate(values) if value is not None)
        sheet_rows.append(f'<row r="{row_number}">{cells}</row>')
    path = tmp_path / 'parallel.xlsx'
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
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'))
        book.writestr('xl/_rels/workbook.xml.rels', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'))
        book.writestr('xl/worksheets/sheet1.xml', (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'))

    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'parallel', 'kind': 'file', 'locator_ref': 'parallel.xlsx'},
    ]))
    tables = data['catalog']['tables']
    assert len(tables) == 2, [(table['name'], table['rows_observed'],
                               sorted(table['columns'])) for table in tables]
    assert {table['rows_observed'] for table in tables} == {2}
    assert all(sorted(table['columns']) == ['id', 'name'] for table in tables)
    assert all(['id'] in table['identity_keys'] for table in tables)


def test_three_column_composite_key_is_observed_and_accepted(tmp_path):
    write(tmp_path / 'matrix.csv',
          'a,b,c\n'
          '0,0,0\n'
          '0,0,1\n'
          '0,1,0\n'
          '1,0,0\n')
    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'matrix', 'kind': 'file', 'locator_ref': 'matrix.csv'},
    ]))
    table, = data['catalog']['tables']
    assert table['keys'] == [['a', 'b', 'c']]
    assert table['identity_keys'] == [['a', 'b', 'c']]
    assert table['key_search'] == {
        'max_columns': 12, 'max_width': 5, 'max_combinations': 5000,
        'truncated': False,
    }
    assert not any(gap['code'] == 'key_search_truncated'
                   for gap in data['catalog']['gaps'])
    draft = invoke(wb, 'ontology_discovery_propose', {
        'session_id': data['session_id'],
        'expected_revision': data['expected_revision'],
        'proposal': {
            'source_revision': data['source_revision'],
            'entities': [{'table': 'matrix', 'name': 'Matrix', 'grain': '每行一条观测',
                          'identity': ['a', 'b', 'c']}],
        },
    }).data
    assert draft['state'] == 'pending' and draft['unresolved_tables'] == []


def test_key_search_limit_is_disclosed(tmp_path):
    write(tmp_path / 'wide.csv',
          'a,b,c,d,e,f\n'
          '1,1,1,1,1,1\n'
          '1,1,1,1,1,1\n')
    wb = workbench(tmp_path)
    data = request(wb, start(wb, [
        {'source_id': 'wide', 'kind': 'file', 'locator_ref': 'wide.csv'},
    ]))
    table, = data['catalog']['tables']
    assert table['keys'] == []
    assert table['key_search']['truncated'] is True
    assert table['key_search']['max_width'] == 5
    gap, = [gap for gap in data['catalog']['gaps']
            if gap['code'] == 'key_search_truncated']
    assert gap['source_id'] == 'wide' and gap['table'] == 'wide'


def test_discovery_probe_strips_the_sampling_hint_only_for_rest(tmp_path):
    from dataagent_contracts.intake import SourceSelection

    seen = []

    class Client:
        def probe(self, selection, *args, **kwargs):
            seen.append(selection)

    wb = Workbench(tmp_path, layer_client=Client())
    rest = SourceSelection(source_id='api', kind='rest', locator_ref='api',
                           options={'sample_strategy': 'per_table'})
    wb.layer_client.probe(rest, None, None)
    sqlite = SourceSelection(source_id='db', kind='sqlite', locator_ref='db',
                             options={'sample_strategy': 'per_table'})
    wb.layer_client.probe(sqlite, None, None)
    assert seen[0].options == {}
    assert seen[1].options == {'sample_strategy': 'per_table'}


def test_rest_records_share_the_table_evidence_and_link_rules(tmp_path):
    from dataagent_workbench.discovery_catalog import build_catalog

    rest = SourceProfile(
        source_id='invoices', source_revision='sha256:rest', kind='rest',
        records=[{'/invoice_no': 'R-1', '/customer_no': 'C-1'},
                 {'/invoice_no': 'R-2', '/customer_no': 'C-2'},
                 {'/invoice_no': 'R-3', '/customer_no': 'C-1'}],
        fields=['/invoice_no', '/customer_no'],
        metadata={'structure_fingerprint': 'rest-fingerprint', 'total_rows': 3})
    customers = SourceProfile(
        source_id='customers', source_revision='sha256:csv', kind='csv',
        records=[{'customer_no': 'C-1', 'name': 'Alpha'},
                 {'customer_no': 'C-2', 'name': 'Beta'},
                 {'customer_no': 'C-3', 'name': 'Gamma'}],
        fields=['customer_no', 'name'],
        metadata={'structure_fingerprint': 'csv-fingerprint', 'total_rows': 3})
    catalog = build_catalog([rest, customers], {
        'invoices': {'/invoice_no', '/customer_no'},
        'customers': {'customer_no', 'name'},
    })
    tables = {table['name']: table for table in catalog['tables']}
    assert tables['invoices']['columns']['/customer_no']['samples'] == ['C-1', 'C-2']
    link, = catalog['relationships']
    assert link['source_table'] == 'invoices'
    assert link['source_columns'] == ['/customer_no']
    assert link['target_table'] == 'customers'
    assert link['matched_rows'] == 3

    # The discovery start gate accepts REST; probing still depends on a
    # host-configured connection.
    wb = workbench(tmp_path)
    assert start(wb, [{'source_id': 'api', 'kind': 'rest', 'locator_ref': 'invoices'}])

