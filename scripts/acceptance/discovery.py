"""Discovery phase: ontology discovery over an unfamiliar SQLite database."""

import sqlite3

from .common import ROOT, call_workbench


def verify(project):
    seed = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake/sales-discovery.sql'
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
    return {**args, 'source_revision': request['source_revision'], 'draft': draft}


def apply(report, project, args, context):
    report['discovery'] = verify(project)
    report['not_verified'] = ['model-generated ontology proposal', 'TUI session', 'GUI session']
