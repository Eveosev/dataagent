"""Discovery phase: ontology discovery over table-shaped sources.

It keeps the original SQLite acceptance and adds the D2a cases: two CSV files
linked by a customer number plus a JSON record set, one Excel workbook with two
table regions, an ambiguity with two equally matching targets, and the explicit
"wait for D2b" refusal for document sources.  All inputs are synthetic.
"""

import json
import shutil
import sqlite3

from .common import ROOT, call_workbench


INTAKE = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake'
EXCEL_REGIONS = INTAKE/'p1-files/samples/invoices-regions.xlsx'


def _write(project, name, content):
    (project/name).write_text(content, encoding='utf-8')


def _start(project, goal, sources):
    return call_workbench(project, 'intake_start', {
        'goal': goal, 'mode': 'ontology_discovery', 'sources': sources,
    })['session_id']


def _advance(project, session_id):
    args = {'session_id': session_id}
    return args, call_workbench(project, 'intake_advance', args)


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


def _document_refusal(project):
    shutil.copy2(INTAKE/'invoice.pdf', project/'policy.pdf')
    error = call_workbench(project, 'intake_start', {
        'goal': '从制度文件发现对象', 'mode': 'ontology_discovery',
        'sources': [{'source_id': 'policy', 'kind': 'file', 'locator_ref': 'policy.pdf'}],
    }, error=True)
    assert 'D2b' in error['detail'], error
    return {'code': error.get('error'), 'detail': error['detail']}


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
        'document_refusal': _document_refusal(project),
    }


def apply(report, project, args, context):
    report['discovery'] = verify(project)
    report['not_verified'] = ['model-generated ontology proposal'] + [
        item for item in report['not_verified'] if item != 'file processing']
