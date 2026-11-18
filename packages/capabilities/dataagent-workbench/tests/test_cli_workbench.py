"""`workbench list` and `workbench stop` (FDE-16, FDE-17)."""

import json
import os
import subprocess
import sys
import time

import pytest

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
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
scope, port_file = sys.argv[1], sys.argv[2]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'status': 'ready', 'scope': scope}).encode()
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
        'dataagent_workbench.interfaces.cli', str(wb.workspace),
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


def test_cli_stop_prints_failed_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    wb = Workbench(tmp_path)
    _descriptor(wb, os.getpid())
    monkeypatch.setattr(sys, 'argv', ['dataagent-workbench', '--workspace', str(tmp_path), 'stop'])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'failed'
