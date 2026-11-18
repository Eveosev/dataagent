"""Start, inspect and stop a workspace-bound loopback service without printing credentials."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import webbrowser


def _descriptor(wb):
    return wb.root/'runtime/workbench.json'


def _service_record(wb):
    """The descriptor only when it belongs to this workspace."""

    try:
        data = json.loads(_descriptor(wb).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get('scope') != wb.scope:
        return None
    return data


def _alive(pid):
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_command(pid):
    try:
        result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='],
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _health_info(url):
    if not isinstance(url, str) or not url.startswith('http://127.0.0.1:'):
        return None
    try:
        with urllib.request.urlopen(url+'/health', timeout=.5) as response:
            payload = json.load(response)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _pid_listens_on(pid, url):
    """Whether ``pid`` owns the listening socket behind ``url`` (legacy help)."""

    try:
        port = urlsplit(url).port
    except ValueError:
        return False
    if not port:
        return False
    try:
        result = subprocess.run(
            ['lsof', '-nP', '-a', '-p', str(pid), f'-iTCP:{port}',
             '-sTCP:LISTEN', '-Fn'],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    return f'n127.0.0.1:{port}' in result.stdout or f'n[::1]:{port}' in result.stdout


def _is_workspace_service(pid, scope, url):
    """Signal only the process that serves this workspace's endpoint.

    ``ps`` only confirms that the pid is a workbench service; its output is a
    display string, not argv, and loses quoting around paths with spaces, so
    the workspace path is never parsed from it. The health response binds the
    serving pid to the descriptor's URL and scope instead. A legacy service
    without a pid is checked through its listening socket; if that binding is
    impossible, nothing is signalled.
    """

    command = _process_command(pid)
    if command is not None and 'dataagent_workbench.interfaces.cli' not in command:
        return False
    info = _health_info(url)
    if info is None or info.get('scope') != scope:
        return False
    reported = info.get('pid')
    if isinstance(reported, int) and not isinstance(reported, bool):
        return reported == pid
    return _pid_listens_on(pid, url)


def service_status(root):
    """Read a runtime descriptor and report it without trusting the pid."""

    root = Path(root)
    descriptor = root/'runtime/workbench.json'
    try:
        data = json.loads(descriptor.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    pid = data.get('pid')
    alive = _alive(pid) and _is_workspace_service(
        pid, data.get('scope'), data.get('url'))
    return {'pid': pid, 'url': data.get('url'), 'scope': data.get('scope'),
            'alive': alive}


def stop_service(wb):
    """Stop this workspace's workbench service; never signal another process."""

    descriptor = _descriptor(wb)
    data = _service_record(wb)
    if data is None:
        descriptor.unlink(missing_ok=True)
        return {'status': 'not_running', 'workspace': str(wb.workspace)}
    pid = data.get('pid')
    if not _alive(pid):
        descriptor.unlink(missing_ok=True)
        return {'status': 'not_running', 'workspace': str(wb.workspace),
                'detail': 'stale descriptor removed'}
    if pid == os.getpid():
        return {'status': 'failed', 'workspace': str(wb.workspace),
                'detail': 'refusing to stop the current process'}
    if not _is_workspace_service(pid, wb.scope, data.get('url')):
        return {'status': 'failed', 'workspace': str(wb.workspace),
                'detail': f'pid {pid} is not a workbench service for this workspace'}
    try:
        group = os.getpgid(pid)
    except OSError:
        group = None
    try:
        if group == pid:
            os.killpg(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        descriptor.unlink(missing_ok=True)
        return {'status': 'not_running', 'workspace': str(wb.workspace)}
    except OSError as exc:
        return {'status': 'failed', 'workspace': str(wb.workspace),
                'detail': f'could not signal pid {pid} ({type(exc).__name__})'}
    for _ in range(50):
        if not _alive(pid):
            break
        time.sleep(.1)
    if _alive(pid):
        try:
            if group == pid:
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            return {'status': 'failed', 'workspace': str(wb.workspace),
                    'detail': f'pid {pid} did not stop'}
    current = _service_record(wb)
    if current is not None and current.get('pid') == pid:
        descriptor.unlink(missing_ok=True)
    return {'status': 'stopped', 'workspace': str(wb.workspace), 'pid': pid,
            'url': data.get('url')}


def ensure_service(wb):
    descriptor = _descriptor(wb)
    def ready():
        try:
            data = json.loads(descriptor.read_text())
            if data['scope'] != wb.scope: return None
            url = data['url']
            if not url.startswith('http://127.0.0.1:'): return None
            with urllib.request.urlopen(url+'/health',timeout=.3) as r:
                if json.load(r).get('scope') == wb.scope: return data
        except (OSError, ValueError,KeyError): pass
        return None
    current = ready()
    if current: return current
    log = wb.root/'runtime/workbench.log'
    with log.open('ab') as output:
        process = subprocess.Popen([sys.executable,'-m','dataagent_workbench.interfaces.cli',
            '--workspace',str(wb.workspace),'serve'],cwd=wb.workspace,stdout=output,stderr=output,start_new_session=True)
    for _ in range(100):
        current = ready()
        if current: return current
        if process.poll() is not None: break
        time.sleep(.1)
    raise ValueError('workbench service did not become ready; inspect .dataagent/runtime/workbench.log')


def open_view(wb, session_id=None, *, run_id=None):
    data = ensure_service(wb)
    request=urllib.request.Request(data['url']+'/local/open',
        data=json.dumps({'session_id':session_id,'run_id':run_id}).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(request,timeout=10) as response:
        return json.load(response)


def home_url(wb):
    """Home page URL for a workspace with no task to open (FDE2-15).

    Starts the workspace service if needed, then returns the unauthenticated
    home page without calling ``/local/open``: the CLI prints a URL a human can
    open, and the page's own "打开本地工作台" button mints the one-time nonce
    link (60 s). No browser is launched here, so headless/SSH use is the same
    code path as a desktop run.
    """

    data = ensure_service(wb)
    return {'opened': False, 'url': data['url'].rstrip('/') + '/#'}
