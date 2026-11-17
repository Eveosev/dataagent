"""API workflow phase: discover, submit and verify a synthetic expense workflow."""

import json
import os
import shutil
import sys
from urllib.request import urlopen

from .common import ROOT, call_workbench, loopback


def verify(project, *, mixed=False):
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


def apply(report, project, args, context):
    report['workflow'] = verify(project, mixed=False)
