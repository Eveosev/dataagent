from pathlib import Path
import shutil

from conftest import start
from dataagent_operations.service import OperationsService


def test_unknown_api_submission_is_reconciled_by_read_only_browser(configured, business, workflow_spec, dispatch_fault):
    path, config = configured
    environment = config['environments']['test-orders']
    packages = Path(__file__).resolve().parents[2]
    environment['browser'] = {
        'node': shutil.which('node'),
        'playwright_module': str(packages/'dataagent-workbench/web/node_modules/playwright'),
        'channel': 'chrome',
        'pages': {'orders_list': '/ui/orders/records'},
        'lookups': {'orders_list': {'key_parameter':'business_key', 'row':'tbody tr',
                                    'key':'td:nth-child(1)', 'status':'td:nth-child(2)'}},
    }
    environment['operations']['orders_submit_record']['effect']['browser_lookup_page'] = 'orders_list'
    service = OperationsService(path, config, request_timeout=0.2)
    snapshot = service.discover('test-orders')
    proposal = service.submit_proposal(service.draft('purchase', snapshot.id).id, workflow_spec)
    assert proposal.valid, proposal.issues
    assert business[2].post('/faults', headers={'X-Admin-Token':'evaluation-only'}, json={
        'lose_next_submit_response': True, 'response_delay_seconds': 0.6,
    }).status_code == 200
    run = start(service, proposal)
    unknown = service.advance(run.id)
    assert unknown.state == 'unknown'
    dispatch_fault['lookup_unavailable'] = True
    try:
        resumed = OperationsService(path, config).advance(run.id, max_steps=1)
    finally:
        dispatch_fault['lookup_unavailable'] = False
    assert 'submit' in resumed.completed
    action = service.actions(run.id)[-1]
    assert action.dispatch_count == 1
    assert action.receipt.source == 'browser_reconciliation'
    observed = service.web_observation(action.receipt.observation_ref)
    assert observed.record_evidence == {'business_key':'po-work', 'status':'waiting_approval'}
    assert service.advance(run.id).state == 'waiting'
    record, = business[1].get('/api/orders/records').json()['records']
    assert record['status'] == 'waiting_approval'
