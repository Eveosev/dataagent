"""Discovery evidence for table-shaped sources beyond one SQLite database."""
import json
import shutil
from pathlib import Path

import pytest

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


def test_rest_records_share_the_table_evidence_and_link_rules(tmp_path):
    from dataagent_contracts.intake import SourceProfile
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

