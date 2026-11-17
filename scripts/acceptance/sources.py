"""Sources phase: file, SQLite, PostgreSQL and REST under one intake."""

import json
import os

from .common import call_workbench, loopback, remove_not_verified


def verify_sources(project, postgres_locator, postgres_user):
    import sqlite3

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    with sqlite3.connect(project/'invoice.db') as db:
        db.execute('CREATE TABLE invoice (number TEXT PRIMARY KEY, amount INTEGER, currency TEXT)')
        db.execute("INSERT INTO invoice VALUES ('INV-003', 1260, 'CNY')")
    (project/'invoice.csv').write_text('number,amount_minor,currency\nINV-003,126000,CNY\n')

    reads = {'first': 0, 'second': 0}

    @app.get('/invoices')
    def invoices():
        reads['first'] += 1
        return {'version': 'fixture-1', 'items': [{'code': 'INV-003', 'amount': '1260.00', 'currency': 'CNY'}],
                'next': '/invoices-more'}

    @app.get('/invoices-more')
    def invoices_more():
        reads['second'] += 1
        if reads['second'] == 1:
            return JSONResponse({}, status_code=429)
        return {'version': 'fixture-1', 'items': [], 'next': None}

    with loopback(app) as url:
        config = project/'source-connections.json'
        config.write_text(json.dumps({
            'ledger': {'kind': 'postgres', 'locator': postgres_locator, 'scope': {'tables': ['invoice']},
                       'credential_options': {'user': postgres_user}},
            'accounting': {'kind': 'rest', 'locator': url+'/invoices', 'allowed_origins': [url],
                           'options': {'records_path': '/items', 'keys': ['/code'], 'source_version_path': '/version',
                                       'pagination': {'next_path': '/next'}}},
        }))
        env = {**os.environ, 'DATAAGENT_SOURCE_CONNECTIONS': str(config)}
        inputs = [('file', 'invoice.csv'), ('sqlite', 'invoice.db'), ('postgres', 'ledger'), ('rest', 'accounting')]
        args = {'session_id': call_workbench(project, 'intake_start', {
            'goal': '从四种来源核对同一张合成发票',
            'sources': [{'source_id': kind, 'kind': kind, 'locator_ref': locator} for kind, locator in inputs],
        }, env=env)['session_id']}
        partial = call_workbench(project, 'intake_advance', args, env=env)
        rest = next(source for source in partial['sources'] if source['source_id'] == 'rest')
        assert rest['coverage'] == 'partial' and partial['next_actions'] == ['retry_probe']
        assert rest['gaps'] == [{'partition': 2, 'code': 'rate_limited'}]
        observed = call_workbench(project, 'intake_advance', args, env=env)
        assert reads == {'first': 1, 'second': 2}
        assert {source['source_id'] for source in observed['sources']} == {kind for kind, _ in inputs}
        assert all(source['coverage'] == 'full' for source in observed['sources'])
        assert next(source for source in observed['sources'] if source['source_id'] == 'postgres')['samples'][0]['posted_on'] == '2026-11-11'
        proposals = {}
        for source in observed['sources']:
            kind = source['source_id']
            proposals[kind] = {
                **observed['proposal_template'], 'source_fingerprint': source['structure_fingerprint'],
                'bindings': {
                    'number': {'source_field': '/code' if kind == 'rest' else 'number'},
                    'currency': {'source_field': '/currency' if kind == 'rest' else 'currency'},
                    'amount': {'source_field': 'amount_minor' if kind == 'file' else '/amount' if kind == 'rest' else 'amount',
                               'transform': 'minor_to_major' if kind == 'file' else 'decimal'},
                },
            }
        preview = call_workbench(project, 'intake_propose_sources', {
            **args, 'proposals': proposals, 'expected_revision': observed['expected_revision'],
        }, env=env)
        assert preview['instance_count'] == 1 and preview['issues'] == []
        call_workbench(project, 'mapping_apply', {
            **args, 'expected_revision': preview['session_revision'],
            'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
        }, env=env)
        status = call_workbench(project, 'intake_status', args, env=env)
        assert status['phase'] == 'saved'
    return {'session': status, 'sources': observed['sources'], 'instance_count': preview['instance_count'],
            'rest_partial': rest, 'rest_requests': reads}


def apply(report, project, args, context):
    report['sources'] = verify_sources(project, args.postgres_locator, args.postgres_user)
    remove_not_verified(report, 'file processing')
