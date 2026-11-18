"""FDE2-15: `view` without a task opens the workbench home page.

The service is a local health stub, so the test proves the CLI returns the
home URL and never launches a browser (the page's own button mints the
one-time nonce link).
"""

import json
import subprocess
import sys
import time

from dataagent_workbench import launcher
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces import cli


HEALTH_SERVER = """
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
scope, port_file = sys.argv[1], sys.argv[2]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({'status': 'ready', 'scope': scope,
                           'pid': 424242}).encode()
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


def _start_health(wb, port_file):
    process = subprocess.Popen([sys.executable, '-c', HEALTH_SERVER,
                                wb.scope, str(port_file)])
    for _ in range(100):
        if port_file.is_file():
            break
        time.sleep(.05)
    return process, f'http://127.0.0.1:{port_file.read_text()}'


def _descriptor(wb, url, pid=424242):
    path = wb.root / 'runtime/workbench.json'
    path.write_text(json.dumps({'url': url, 'scope': wb.scope, 'pid': pid}))
    return path


def test_view_without_task_prints_home_url_and_opens_no_browser(
        tmp_path, monkeypatch, capsys):
    wb = Workbench(tmp_path)
    process, url = _start_health(wb, tmp_path / 'port')
    try:
        _descriptor(wb, url)

        def no_browser(*args, **kwargs):
            raise AssertionError('view must not launch a browser')

        monkeypatch.setattr(launcher.webbrowser, 'open', no_browser)
        monkeypatch.setattr(sys, 'argv', [
            'dataagent-workbench', '--workspace', str(tmp_path), 'view'])

        cli.main()

        payload = json.loads(capsys.readouterr().out)
        assert payload == {'opened': False, 'url': url + '/#'}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
