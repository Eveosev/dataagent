"""Install actual local packages in a fresh project and verify their public CLI."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]


def run(command,cwd):
    result=subprocess.run([str(a) for a in command],cwd=cwd,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}):\n{result.stdout[-6000:]}\n{result.stderr[-6000:]}')
    return result.stdout


def call_workbench(project, operation, arguments, *, error=False, env=None):
    python, = (project/'.mint/packages/dataagent').glob('workbench@*/.venv/bin/python')
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': operation, 'arguments': arguments}}
    result = subprocess.run(
        [python, '-m', 'dataagent_workbench.interfaces.mcp_server'], cwd=project,
        input=json.dumps(request)+'\n', capture_output=True, text=True, check=True, env=env,
    )
    response = json.loads(result.stdout)['result']
    assert response['isError'] is error, response
    payload = json.loads(response['content'][0]['text'])
    if error:
        return payload
    result = json.loads((project/payload['result_path']).read_text())
    assert result['status'] != 'failed', result['issues']
    return result['data']


@contextmanager
def loopback(app):
    import uvicorn
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        url = f'http://127.0.0.1:{listener.getsockname()[1]}'
        server = uvicorn.Server(uvicorn.Config(app, log_level='critical', ws='none'))
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and time.monotonic() < deadline:
                time.sleep(.02)
            assert server.started
            yield url
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def verify_scan(project, ocr_root):
    fixture = ROOT/'packages/capabilities/dataagent-scenarios/fixtures/intake/scan.pdf'
    shutil.copy2(fixture, project/'scan.pdf')
    shutil.copytree(ocr_root, project/'.dataagent/ocr', symlinks=True)
    args = {'session_id': call_workbench(project, 'intake_start', {
        'goal': '核对扫描发票的编号、金额和币种',
        'sources': [{'source_id': 'scan', 'kind': 'file', 'locator_ref': 'scan.pdf'}],
    })['session_id']}
    observed = call_workbench(project, 'intake_advance', args)
    source, = observed['sources']
    page, = source['document_excerpts']
    assert source['coverage'] == 'full'
    fields = {'number': 'INV-003', 'amount': '1260.00', 'currency': 'CNY'}
    assert all(value in page['text'] for value in fields.values())
    derived = call_workbench(project, 'intake_extract', {
        **args, 'expected_revision': observed['expected_revision'], 'source_id': 'scan',
        'fields': [{'row': page['rows'][0], 'page': page['page'], 'name': name, 'quote': quote}
                   for name, quote in fields.items()],
    })
    proposal = {**derived['proposal_template'], 'bindings': {
        name: {'source_field': name, 'transform': 'decimal' if name == 'amount' else 'identity'}
        for name in fields
    }}
    preview = call_workbench(project, 'intake_propose', {
        **args, 'expected_revision': derived['expected_revision'], 'proposal': proposal,
    })
    assert preview['instance_count'] == 1 and preview['issues'] == []
    call_workbench(project, 'mapping_apply', {
        **args, 'expected_revision': preview['session_revision'],
        'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
    })
    status = call_workbench(project, 'intake_status', args)
    assert status['phase'] == 'saved' and status['selected_versions']['release']
    replay = call_workbench(project, 'intake_propose', {
        **args, 'expected_revision': status['revision'], 'proposal': proposal,
    }, error=True)
    assert 'saved intake is closed' in replay['detail']
    assert call_workbench(project, 'intake_status', args) == status
    return {'session': status, 'observed_text': page['text'], 'values': fields,
            'source_revision': source['source_revision'], 'late_proposal': replay}


def verify_sources(project, postgres_locator, postgres_user):
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


def verify_discovery(project):
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


def verify_api_workflow(project, *, mixed=False):
    sys.path.insert(0, str(ROOT/'packages/capabilities/dataagent-scenarios/src'))
    from dataagent_scenarios.business_system import create_app
    from dataagent_workbench.bootstrap import Workbench
    from fastapi.responses import JSONResponse

    root = '/api/expenses/records'
    query, create, submit, status = (f'expenses_{name}' for name in
                                    ('query_records', 'create_draft', 'submit_record', 'query_status'))
    lookup = {'lookup_operation': query, 'collection_pointer': '/items'}
    predicate = {'pointer': '/status', 'one_of': ['waiting_approval', 'approved', 'rejected']}
    goal = '提交合成报销并确认进入审批'
    workbench = Workbench(project)
    intake = call_workbench(project, 'intake_start', {'goal': goal, 'sources': [
        {'source_id': 'fixture', 'kind': 'file', 'locator_ref': 'invoice.csv'},
    ]})
    work = call_workbench(project, 'intake_status', {'session_id': intake['session_id']})['goal_ref']

    app = create_app(project/'fixture-business.sqlite3')
    outage = False

    @app.middleware('http')
    async def read_outage(request, call_next):
        if outage and request.url.path == root and request.method == 'GET' and 'business_key' in request.query_params:
            return JSONResponse({'detail': 'simulated scoped API lookup outage'}, status_code=503)
        return await call_next(request)

    with loopback(app) as url:
        config = project/'operations-config.json'
        settings = {
            'scope_ref': workbench.scope, 'authorization_ref': workbench.authorization,
            'environments': {'fixture': {
                'base_url': url, 'tenant': 'local-fixture', 'business_key_prefix': 'expense-',
                'operations': {
                    query: {'method': 'GET', 'path': root, 'business_key_parameter': 'business_key'},
                    create: {'method': 'POST', 'path': root, 'effect': {
                        **lookup, 'action': 'create-expense', 'business_key_field': 'business_key',
                        'applied': {'pointer': '/status', 'one_of': ['draft', *predicate['one_of']]},
                        'match_fields': {'/data': '/data'},
                    }},
                    submit: {'method': 'POST', 'path': root+'/{record_id}/submit', 'effect': {
                        **lookup, 'action': 'submit-expense', 'record_id_parameter': 'record_id',
                        'request_key_field': 'request_key', 'remote_idempotency': True,
                        'before': {'pointer': '/status', 'one_of': ['draft']}, 'applied': predicate,
                    }},
                    status: {'method': 'GET', 'path': root+'/{record_id}/status',
                             'record_lookup': query, 'collection_pointer': '/items', 'record_id_parameter': 'record_id'},
                },
            }},
        }
        if mixed:
            playwright = ROOT/'packages/capabilities/dataagent-workbench/web/node_modules/playwright'
            environment = settings['environments']['fixture']
            environment['browser'] = {
                'node': shutil.which('node'), 'playwright_module': str(playwright), 'channel': 'chrome',
                'pages': {'expenses_list': '/ui/expenses/records'},
                'lookups': {'expenses_list': {'key_parameter': 'business_key', 'row': 'tbody tr',
                                             'key': 'td:nth-child(1)', 'status': 'td:nth-child(2)'}},
            }
            environment['operations'][submit]['effect']['browser_lookup_page'] = 'expenses_list'
        config.write_text(json.dumps(settings))
        env = {**os.environ, 'DATAAGENT_OPERATIONS_CONFIG': str(config)}
        def call(operation, **arguments):
            return call_workbench(project, 'workflow_call', {'operation': operation, 'arguments': arguments}, env=env)

        snapshot = call('environment_discover', environment_id='fixture')
        assert snapshot['capabilities'][query]['verification'] == 'observed'
        assert json.load(urlopen(url+root, timeout=5))['total'] == 0
        draft = call('workflow_draft', work_spec_id=work, snapshot_id=snapshot['id'])
        assert draft['work_spec']['goal'] == goal
        spec = {
            'entry': 'create', 'input_schema': {'type': 'object', 'additionalProperties': False,
            'required': ['amount'], 'properties': {'amount': {'type': 'string'}}},
            'nodes': [
                {'id': 'create', 'kind': 'act', 'operation_id': create, 'next': 'submit', 'parameters': {
                    'body': {'data': {'employee': 'Synthetic Tester', 'amount': {'$ref': '/inputs/amount'},
                                      'currency': 'CNY', 'purpose': 'Local acceptance'}},
                }},
                {'id': 'submit', 'kind': 'act', 'operation_id': submit, 'next': 'verify'},
                {'id': 'verify', 'kind': 'verify', 'operation_id': status,
                 'condition': {'pointer': '/response/status', 'one_of': ['waiting_approval']}, 'criteria': [0]},
            ],
        }
        proposal = call('workflow_submit_proposal', draft_id=draft['id'], spec=spec)
        assert proposal['valid'], proposal['issues']
        run = call('workflow_start', proposal_id=proposal['id'], business_key='expense-local-1', inputs={'amount': '1260.00'})
        browser_observation = None
        if mixed:
            app.state.business_state.faults({'lose_next_submit_response': True, 'response_delay_seconds': 6})
            unknown = call('workflow_advance', run_id=run['id'])
            assert unknown['state'] == 'unknown' and unknown['unknown_action_ref']
            outage = True
            try:
                reconciled = call('workflow_advance', run_id=run['id'], max_steps=1)
            finally:
                outage = False
            assert 'submit' in reconciled['completed']
            action = next(action for action in call('workflow_actions', run_id=run['id']) if action['operation_id'] == submit)
            assert action['dispatch_count'] == 1 and action['receipt']['source'] == 'browser_reconciliation'
            browser_observation = call('environment_web_observation', observation_id=action['receipt']['observation_ref'])
            assert browser_observation['record_evidence'] == {'business_key': 'expense-local-1', 'status': 'waiting_approval'}
            screenshot = project/'.dataagent/db'/browser_observation['screenshot_ref']
            assert screenshot.read_bytes().startswith(b'\x89PNG')
        finished = call('workflow_advance', run_id=run['id'])
        assert finished['state'] == 'completed', finished
        assert call('workflow_status', run_id=run['id']) == finished
        receipts = call('workflow_actions', run_id=run['id'])
        items = json.load(urlopen(url+root+'?business_key=expense-local-1', timeout=5))['items']
        record, = items
        assert record['status'] == 'waiting_approval'
        assert finished['outputs']['verify']['id'] == record['id']
        assert len(finished['receipt_refs']) == 2
    return {'snapshot_id': snapshot['id'], 'proposal_id': proposal['id'], 'run': finished,
            'record': record, 'actions': receipts, 'browser_observation': browser_observation}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['bootstrap','files','sources','api-workflow','mixed-workflow','discovery'],default='bootstrap')
    parser.add_argument('--output',type=Path,default=ROOT/'.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance')
    parser.add_argument('--ocr-root',type=Path,help='verified local OCR directory to use for scanned PDF acceptance')
    parser.add_argument('--postgres-locator',help='local test database URL with a seeded invoice table')
    parser.add_argument('--postgres-user',default='dataagent_reader')
    args=parser.parse_args()
    if args.phase == 'files' and not args.ocr_root:
        parser.error('--phase files requires a verified local --ocr-root')
    if args.phase == 'sources' and not args.postgres_locator:
        parser.error('--phase sources requires --postgres-locator')
    mint=shutil.which('mint') or str(Path.home()/'.mint/bin/mint')
    project=Path(tempfile.mkdtemp(prefix='dataagent-intake-'))
    run([mint,'init','--no-preset','--offline','-y'],project)
    run([mint,'add','path:'+str(ROOT/'build/local/preset-intake'),'--offline','-y'],project)
    cli=list((project/'.mint/packages/dataagent').glob('cli@*/bin/dataagent'))
    assert len(cli)==1,'exactly one installed CLI required'
    run([cli[0],'setup'],project)
    doctor=run([cli[0],'doctor'],project)
    created=json.loads(run([cli[0],'workbench','intake','--goal','本地接入验收','--source','invoice.csv'],project))
    session=created['result']['data']['session_id']
    status=json.loads(run([cli[0],'workbench','status',session],project))
    assert status['result']['data']['job_ref']==created['result']['data']['job_ref']
    assert status['result']['data']['phase']=='queued'
    args.output.mkdir(parents=True,exist_ok=True)
    report={'phase':args.phase,'status':'passed','project':str(project),'session_id':session,
        'mint':run([mint,'--version'],project).strip(),'doctor':doctor,
        'manifest':json.loads((ROOT/'build/local/manifest.json').read_text()),
        'not_verified':['file processing','TUI session','GUI session']}
    if args.phase == 'discovery':
        report['discovery'] = verify_discovery(project)
        report['not_verified'] = ['model-generated ontology proposal', 'TUI session', 'GUI session']
    if args.phase == 'files':
        report['scan'] = verify_scan(project, args.ocr_root)
        report['not_verified'].remove('file processing')
    if args.phase == 'sources':
        report['sources'] = verify_sources(project, args.postgres_locator, args.postgres_user)
        report['not_verified'].remove('file processing')
    if args.phase in {'api-workflow','mixed-workflow'}:
        report['workflow'] = verify_api_workflow(project, mixed=args.phase == 'mixed-workflow')
    (args.output/f'{args.phase}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    summary = {'status': 'passed', 'project': str(project), 'report': str(args.output/f'{args.phase}.json')}
    if args.phase == 'discovery':
        summary['session_id'] = report['discovery']['session_id']
    print(json.dumps(summary, ensure_ascii=False))


if __name__=='__main__':main()
