"""`workbench list` and `workbench stop` (FDE-16, FDE-17)."""

import asyncio
import json
import os
import subprocess
import sys
import time

import pytest

from dataagent_workbench import launcher
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces import cli
from dataagent_workbench.interfaces.cli import list_sessions
from dataagent_workbench.launcher import stop_service
from dataagent_workbench.service_tools import invoke


def _descriptor(wb, pid, url='http://127.0.0.1:1'):
    path = wb.root / 'runtime/workbench.json'
    path.write_text(json.dumps({'url': url, 'scope': wb.scope, 'pid': pid}))
    return path


def test_list_sessions_reports_task_phase_and_release(tmp_path):
    wb = Workbench(tmp_path)
    started = invoke(wb, 'intake_start', {
        'goal': '三边对账，接口叫 accounting',
        'sources': [{'source_id': 'api', 'kind': 'rest', 'locator_ref': 'accounting'}],
    }).data
    session = wb.sessions.get(started['session_id'], wb.ctx)
    wb.sessions.update(session.id, session.revision, {
        'phase': 'saved', 'selected_versions': {'release': 'release:abc@1'},
    }, wb.ctx)

    rows = list_sessions(wb)

    row = next(item for item in rows if item['session_id'] == started['session_id'])
    assert row['task'] == '三边对账，接口叫 accounting'
    assert row['phase'] == 'saved'
    assert row['release_ref'] == 'release:abc@1'


def test_cli_list_prints_json_array(tmp_path, monkeypatch, capsys):
    wb = Workbench(tmp_path)
    invoke(wb, 'intake_start', {
        'goal': '列任务',
        'sources': [{'source_id': 'f', 'kind': 'file', 'locator_ref': 'invoices.csv'}],
    })
    monkeypatch.setattr(sys, 'argv', ['dataagent-workbench', '--workspace', str(tmp_path), 'list'])

    cli.main()

    rows = json.loads(capsys.readouterr().out)
    assert rows[0]['task'] == '列任务'
    assert rows[0]['phase'] == 'queued'
    assert rows[0]['release_ref'] is None


def test_stop_service_removes_stale_descriptor(tmp_path):
    wb = Workbench(tmp_path)
    descriptor = _descriptor(wb, 999999999)

    result = stop_service(wb)

    assert result['status'] == 'not_running'
    assert descriptor.exists() is False


def test_stop_service_refuses_the_current_process(tmp_path):
    wb = Workbench(tmp_path)
    descriptor = _descriptor(wb, os.getpid())

    result = stop_service(wb)

    assert result['status'] == 'failed'
    assert 'current process' in result['detail']
    assert descriptor.exists() is True


def test_stop_service_refuses_a_foreign_process(tmp_path):
    wb = Workbench(tmp_path)
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        _descriptor(wb, process.pid)
        result = stop_service(wb)
        assert result['status'] == 'failed'
        assert 'not a workbench service' in result['detail']
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)


HEALTH_SERVER = """
import json, os, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
scope, port_file = sys.argv[1], sys.argv[2]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'status': 'ready', 'scope': scope,
                           'pid': os.getpid()}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass
server = HTTPServer(('127.0.0.1', 0), Handler)
Path(port_file).write_text(str(server.server_port))
server.serve_forever()
"""


def test_stop_service_stops_this_workspace_service(tmp_path):
    wb = Workbench(tmp_path)
    port_file = tmp_path / 'port'
    process = subprocess.Popen([
        sys.executable, '-c', HEALTH_SERVER, wb.scope, str(port_file),
        'dataagent_workbench.interfaces.cli', '--workspace', str(wb.workspace),
    ])
    try:
        for _ in range(100):
            if port_file.is_file():
                break
            time.sleep(.05)
        port = port_file.read_text()
        descriptor = _descriptor(wb, process.pid, f'http://127.0.0.1:{port}')
        result = stop_service(wb)
        assert result['status'] == 'stopped'
        assert result['pid'] == process.pid
        assert process.wait(timeout=5) is not None
        assert descriptor.exists() is False
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def _start_health(wb, tmp_path, name):
    port_file = tmp_path / name
    process = subprocess.Popen([
        sys.executable, '-c', HEALTH_SERVER, wb.scope, str(port_file),
        'dataagent_workbench.interfaces.cli', '--workspace', str(wb.workspace),
    ])
    for _ in range(100):
        if port_file.is_file():
            break
        time.sleep(.05)
    return process, f'http://127.0.0.1:{port_file.read_text()}'


def test_stop_service_binds_the_pid_to_the_endpoint(tmp_path):
    first = Workbench(tmp_path / 'first')
    second = Workbench(tmp_path / 'second')
    service_a, url_a = _start_health(first, tmp_path, 'a.port')
    service_b, url_b = _start_health(second, tmp_path, 'b.port')
    try:
        # Descriptor in A names B's pid but A's endpoint: neither identity
        # check may let the signal through.
        _descriptor(first, service_b.pid, url_a)
        result = stop_service(first)
        assert result['status'] == 'failed'
        assert service_b.poll() is None

        _descriptor(second, service_a.pid, url_b)
        result = stop_service(second)
        assert result['status'] == 'failed'
        assert service_a.poll() is None
    finally:
        for process in (service_a, service_b):
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def test_stop_service_accepts_a_workspace_path_with_spaces(tmp_path, monkeypatch):
    wb = Workbench(tmp_path / 'Mint Project')
    service, url = _start_health(wb, tmp_path, 'space.port')
    # ``ps`` prints this display string without keeping the argv boundary, so
    # the path appears unquoted even though it contains a space.
    monkeypatch.setattr(
        launcher, '_process_command',
        lambda pid: (f'{sys.executable} -m dataagent_workbench.interfaces.cli '
                     f'--workspace {wb.workspace} serve'),
    )
    try:
        descriptor = _descriptor(wb, service.pid, url)
        result = stop_service(wb)
        assert result['status'] == 'stopped', result
        assert service.wait(timeout=5) is not None
        assert descriptor.exists() is False
    finally:
        if service.poll() is None:
            service.kill()
            service.wait(timeout=5)


def test_service_health_reports_the_serving_pid(tmp_path):
    wb = Workbench(tmp_path)
    sent = []

    async def receive():
        return {'type': 'http.request'}

    async def send(message):
        sent.append(message)

    asyncio.run(cli._service_app(wb)({'type': 'http', 'path': '/health'},
                                     receive, send))

    body = json.loads(sent[1]['body'])
    assert body == {'status': 'ready', 'service': 'dataagent-workbench',
                    'scope': wb.scope, 'pid': os.getpid()}


def test_cli_binds_workspace_for_connection_lookup(tmp_path, monkeypatch):
    from dataagent_workbench.adapters.source_connections import bind_workspace

    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'source-connections.json').write_text(json.dumps({
        'accounting': {'kind': 'rest', 'label': 'A',
                       'locator': 'http://127.0.0.1:1/invoices'},
    }))
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    seen = {}

    def during(wb, args):
        seen['env'] = os.environ.get('DATAAGENT_WORKSPACE')
        result = invoke(wb, 'source_connections', {})
        seen['connections'] = [item['id'] for item in result.data['connections']]

    previous = os.environ.pop('DATAAGENT_WORKSPACE', None)
    bind_workspace(None)
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(cli, '_run', during)
    monkeypatch.setattr(sys, 'argv', [
        'dataagent-workbench', '--workspace', str(workspace), 'health'])
    try:
        cli.main()
        assert seen['env'] == str(workspace.resolve())
        assert seen['connections'] == ['accounting']
        assert 'DATAAGENT_WORKSPACE' not in os.environ
        assert cli.bound_workspace() is None
    finally:
        bind_workspace(None)
        if previous is None:
            os.environ.pop('DATAAGENT_WORKSPACE', None)
        else:
            os.environ['DATAAGENT_WORKSPACE'] = previous


def test_cli_stop_prints_failed_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    wb = Workbench(tmp_path)
    _descriptor(wb, os.getpid())
    monkeypatch.setattr(sys, 'argv', ['dataagent-workbench', '--workspace', str(tmp_path), 'stop'])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'failed'
