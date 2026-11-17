"""Shared helpers for the verify_local acceptance phases."""

import json
from contextlib import contextmanager
from pathlib import Path
import socket
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


def run(command, cwd):
    result = subprocess.run([str(a) for a in command], cwd=cwd, capture_output=True, text=True)
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


def remove_not_verified(report, item):
    report['not_verified'].remove(item)
