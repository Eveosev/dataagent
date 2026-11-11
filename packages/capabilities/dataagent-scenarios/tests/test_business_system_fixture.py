"""Real HTTP/SQLite acceptance tests for the mutable business fixture."""
import base64
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def system(tmp_path):
    from dataagent_scenarios.business_system import create_app, create_admin_app
    path = tmp_path / 'business.sqlite3'
    app = create_app(path)
    return TestClient(app), TestClient(create_admin_app(path, token='evaluator-secret')), path


def draft(client, key='expense-1', domain='expenses', **fields):
    data = {'employee': 'Lin', 'amount': '1260.00', 'currency': 'CNY', 'purpose': 'Travel'}
    data.update(fields)
    return client.post(f'/api/{domain}/records', json={'business_key': key, 'data': data})


def admin(client, path, body):
    return client.post(path, json=body, headers={'X-Admin-Token': 'evaluator-secret'})


def test_api_draft_is_visible_in_gui_and_persists(system):
    client, _, path = system
    response = draft(client)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record['status'] == 'draft'
    html = client.get(f"/ui/expenses/records/{record['id']}").text
    assert 'expense-1' in html and '1260.00' in html and 'Lin' in html
    from dataagent_scenarios.business_system import create_app
    restored = TestClient(create_app(path))
    assert restored.get('/api/expenses/records', params={'business_key': 'expense-1'}).json()['items'][0]['id'] == record['id']


def test_submit_is_idempotent_and_reconcilable_by_business_key(system):
    client, _, _ = system
    record = draft(client).json()
    route = f"/api/expenses/records/{record['id']}/submit"
    first = client.post(route, json={'request_key': 'submit-1'})
    assert first.status_code == 200
    assert first.json()['status'] == 'waiting_approval'
    assert client.post(route, json={'request_key': 'submit-1'}).json() == first.json()
    assert client.post(route, json={'request_key': 'submit-2'}).json()['id'] == record['id']
    assert draft(client).json()['id'] == record['id']
    found = client.get('/api/expenses/records', params={'business_key': 'expense-1'}).json()
    assert len(found['items']) == 1 and found['items'][0]['status'] == 'waiting_approval'
    events = client.get(f"/api/expenses/records/{record['id']}/events").json()['items']
    assert [e['status'] for e in events] == ['draft', 'submitted', 'waiting_approval']
    assert found['items'][0]['native_status'] == 'AWAITING_REVIEW'
    assert found['items'][0]['observed_at']


def test_conflicting_business_or_request_key_is_not_silent(system):
    client, _, _ = system
    record = draft(client).json()
    assert draft(client, amount='99').status_code == 409
    other = draft(client, key='expense-2').json()
    client.post(f"/api/expenses/records/{record['id']}/submit", json={'request_key': 'shared-key'})
    assert client.post(f"/api/expenses/records/{other['id']}/submit", json={'request_key': 'shared-key'}).status_code == 409


def test_attachment_bytes_are_persisted_and_required_on_configured_domain(system):
    client, manager, _ = system
    admin(manager, '/config', {'domain': 'expenses', 'require_attachment': True})
    record = draft(client).json()
    submit = f"/api/expenses/records/{record['id']}/submit"
    assert client.post(submit, json={'request_key': 'attach-submit'}).status_code == 422
    attached = client.post(f"/api/expenses/records/{record['id']}/attachments", json={
        'filename': 'invoice.txt', 'content_type': 'text/plain',
        'content_base64': base64.b64encode(b'Invoice 1260').decode(), 'request_key': 'upload-1'})
    assert attached.status_code == 201
    link = attached.json()['download_url']
    assert client.get(link).content == b'Invoice 1260'
    assert client.post(submit, json={'request_key': 'attach-submit'}).status_code == 200


def test_required_field_drift_is_observable_and_blocks_submit(system):
    client, manager, _ = system
    record = draft(client).json()
    assert admin(manager, '/config', {'domain': 'expenses', 'required_field': {'name': 'organization', 'label': 'Cost organization', 'type': 'string'}}).status_code == 200
    submit = f"/api/expenses/records/{record['id']}/submit"
    response = client.post(submit, json={'request_key': 'drift-submit'})
    assert response.status_code == 422 and 'organization' in response.text
    schema = client.get('/openapi.json').json()
    assert 'organization' in str(schema) and 'Cost organization' in str(schema)
    assert 'Cost organization' in client.get(f"/ui/expenses/records/{record['id']}").text
    patched = client.patch(f"/api/expenses/records/{record['id']}", json={'data': {'organization': 'Research'}})
    assert patched.status_code == 200
    assert client.post(submit, json={'request_key': 'drift-submit'}).status_code == 200


def test_layout_and_pagination_drift_are_discoverable(system):
    client, manager, _ = system
    draft(client, key='one')
    draft(client, key='two')
    admin(manager, '/config', {'domain': 'expenses', 'layout': 'cards', 'submit_label': 'Send for review', 'pagination': 'cursor', 'page_size': 1, 'collection_field': 'results'})
    page = client.get('/api/expenses/records').json()
    assert len(page['results']) == 1 and page['next_cursor']
    next_page = client.get('/api/expenses/records', params={'cursor': page['next_cursor']}).json()
    assert next_page['results'][0]['business_key'] != page['results'][0]['business_key']
    html = client.get(f"/ui/expenses/records/{page['results'][0]['id']}").text
    assert 'Send for review' in html and 'data-layout="cards"' in html
    assert 'results' in str(client.get('/openapi.json').json())


def test_remote_success_without_response_can_be_reconciled(system):
    client, manager, _ = system
    record = draft(client).json()
    admin(manager, '/faults', {'lose_next_submit_response': True, 'response_delay_seconds': 0})
    with pytest.raises(ConnectionResetError):
        client.post(f"/api/expenses/records/{record['id']}/submit", json={'request_key': 'lost-response'})
    assert client.get('/api/expenses/records', params={'business_key': 'expense-1'}).json()['items'][0]['status'] == 'waiting_approval'
    assert client.post(f"/api/expenses/records/{record['id']}/submit", json={'request_key': 'lost-response'}).json()['status'] == 'waiting_approval'


def test_delayed_approval_survives_restart(system):
    client, manager, path = system
    admin(manager, '/config', {'domain': 'expenses', 'approval_delay_seconds': 0.08, 'approval_outcome': 'approved'})
    record = draft(client).json()
    route = f"/api/expenses/records/{record['id']}"
    assert client.post(route + '/submit', json={'request_key': 'delayed'}).json()['status'] == 'waiting_approval'
    from dataagent_scenarios.business_system import create_app
    restored = TestClient(create_app(path))
    time.sleep(0.12)
    observed = restored.get(route + '/status').json()
    assert observed['status'] == 'approved' and observed['native_status'] == 'APPROVED'
    events = restored.get(route + '/events').json()['items']
    assert events[-1]['status'] == 'approved'


def test_admin_app_is_separate_and_protected(system):
    client, manager, _ = system
    assert client.post('/config', json={}).status_code == 404
    assert 'faults' not in str(client.get('/openapi.json').json())
    assert 'Admin' not in str(client.get('/openapi.json').json())
    assert manager.post('/config', json={}).status_code == 403
    assert manager.get('/openapi.json').status_code == 404


def test_domains_are_configured_not_hardcoded(system):
    client, _, _ = system
    schema = client.get('/openapi.json').json()
    assert '/api/orders/records' in schema['paths']
    response = client.post('/api/orders/records', json={'business_key': 'po-1', 'data': {'supplier': 'Example Ltd', 'total': '80.50', 'currency': 'CNY'}})
    assert response.status_code == 201
    bad = client.post('/api/orders/records', json={'business_key': 'po-2', 'data': {'supplier': 'Example Ltd', 'total': 'not-money', 'currency': 'CNY'}})
    assert bad.status_code == 422


def test_demo_records_are_opt_in_and_not_hidden_evaluation_assets(tmp_path):
    from copy import deepcopy
    from dataagent_scenarios.business_system import DEFAULT_CONFIG, create_app
    config = deepcopy(DEFAULT_CONFIG)
    config['demo_records'] = [{'domain': 'expenses', 'business_key': 'demo-trip', 'data': {
        'employee': 'Example Employee', 'amount': '320.00', 'currency': 'CNY', 'purpose': 'Example trip'}}]
    demo = TestClient(create_app(tmp_path / 'demo.sqlite3', config=config))
    assert demo.get('/api/expenses/records').json()['items'][0]['business_key'] == 'demo-trip'
    blank = TestClient(create_app(tmp_path / 'blank.sqlite3'))
    assert blank.get('/api/expenses/records').json()['total'] == 0
    assert 'demo_records' not in str(demo.get('/openapi.json').json())
    assert 'demo_records' not in str(demo.get('/api/domains').json())


@pytest.fixture
def live_server(system):
    """Bind only loopback; real HTTP clients and browser share the fixture DB."""
    import socket
    import threading
    import uvicorn
    from dataagent_scenarios.business_system import create_app
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(system[2]), log_level='critical'))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.01)
    assert server.started, 'Loopback fixture did not start'
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive(), 'Loopback fixture did not stop'


def test_lost_response_is_a_real_http_timeout_after_commit(system, live_server):
    import httpx
    client, manager, _ = system
    record = draft(client).json()
    admin(manager, '/faults', {'lose_next_submit_response': True, 'response_delay_seconds': 0.25})
    with httpx.Client(base_url=live_server) as remote:
        with pytest.raises(httpx.ReadTimeout):
            remote.post(f"/api/expenses/records/{record['id']}/submit", json={'request_key': 'network-loss'}, timeout=0.03)
        assert remote.get('/api/expenses/records', params={'business_key': 'expense-1'}).json()['items'][0]['status'] == 'waiting_approval'


def test_browser_creates_attaches_and_submits_shared_record(system, live_server):
    import json
    import os
    from pathlib import Path
    import subprocess
    module = os.environ.get('DATAAGENT_PLAYWRIGHT_MODULE', str(Path(__file__).resolve().parents[2] / 'dataagent-workbench/web/node_modules/playwright'))
    # The browser is an explicit scenario prerequisite; absence is a setup gap.
    script = r'''
const {chromium}=require(process.argv[1]);
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.DATAAGENT_CHROMIUM_CHANNEL||undefined});
 try {
  const page=await browser.newPage();
  await page.goto(process.argv[2]+'/ui/expenses/records/new');
  await page.getByLabel('Business key',{exact:true}).fill('browser-created');
  await page.getByLabel('Employee',{exact:true}).fill('Browser Employee');
  await page.getByLabel('Amount',{exact:true}).fill('360.25');
  await page.getByLabel('Currency',{exact:true}).fill('CNY');
  await page.getByLabel('Purpose',{exact:true}).fill('Workshop');
  await page.getByRole('button',{name:'Save draft',exact:true}).click();
  await page.waitForURL(/records\/[a-f0-9]+$/);
  await page.getByLabel('Evidence attachment',{exact:true}).setInputFiles({name:'invoice.txt',mimeType:'text/plain',buffer:Buffer.from('Browser invoice')});
  await page.getByRole('button',{name:'Attach evidence',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Attachment saved'}).waitFor();
  await page.getByRole('button',{name:'Submit for approval',exact:true}).click();
  await page.getByRole('status').filter({hasText:'waiting_approval'}).waitFor();
  await page.reload();
  await page.getByRole('status').filter({hasText:'waiting_approval'}).waitFor();
  console.log(JSON.stringify({url:page.url(),status:await page.getByRole('status').textContent()}));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
'''
    result = subprocess.run(['node', '-e', script, module, live_server], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    observed = system[0].get('/api/expenses/records', params={'business_key': 'browser-created'}).json()['items']
    assert len(observed) == 1
    assert observed[0]['status'] == 'waiting_approval'
    assert observed[0]['data']['amount'] == '360.25'
    assert observed[0]['attachments'][0]['filename'] == 'invoice.txt'
    assert 'waiting_approval' in json.loads(result.stdout)['status']
