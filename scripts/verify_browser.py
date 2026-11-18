"""Exercise the real local web app; no test hooks are added to production.

The run has two stages against one workspace: the first starts the service and
runs the browser suite (which also prepares a task with a saved draft and an
unresolved item); the service is then restarted on the same workspace and a
recovery spec verifies materials, drafts and unresolved items survive.

Retries are enabled (playwright.config.ts): a test that passes after a retry is
flaky, not failed, but it is always listed here so it cannot be silently
swallowed.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uvicorn
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.interfaces.http_api import create_app

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'packages/capabilities/dataagent-data'
WEB=ROOT/'packages/capabilities/dataagent-workbench/web'


def start_service(workspace):
    wb=Workbench(workspace,layer_client=LayerClient(DATA))
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
    url=f'http://127.0.0.1:{sock.getsockname()[1]}'
    server=uvicorn.Server(uvicorn.Config(create_app(wb),log_level='warning',access_log=False))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(url+'/health',timeout=.2).close();return wb,server,thread,url
        except OSError:time.sleep(.05)
    raise SystemExit('service did not become ready')


def flaky_tests(report):
    """Titles of tests that passed only after a retry (from the JSON report)."""
    if not report.is_file():return []
    try:data=json.loads(report.read_text())
    except ValueError:return []
    found=[]
    def walk(suites):
        for suite in suites or []:
            for spec in suite.get('specs') or []:
                for case in spec.get('tests') or []:
                    if case.get('status')=='flaky':
                        location=spec.get('location') or {}
                        found.append(f"{spec.get('file','?')}:{location.get('line',spec.get('line','?'))} › {spec.get('title','')}")
            walk(suite.get('suites'))
    walk(data.get('suites'))
    return found


def run_e2e(url,token,extra,grep=None):
    env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','LANG','TMPDIR','PLAYWRIGHT_BROWSERS_PATH'}}
    # Forward outer DATAAGENT_* overrides (workers, retries, timeout scaling);
    # the values this script sets itself are applied afterwards and win.
    env.update({k:v for k,v in os.environ.items() if k.startswith('DATAAGENT_')})
    # The screenshot evidence goes to a per-run temp directory, never into the
    # repository; the run only reports its path.
    evidence=Path(tempfile.mkdtemp(prefix='dataagent-ui-evidence-'))
    report=evidence/'report.json'
    env.update(DATAAGENT_TEST_URL=url,DATAAGENT_TEST_TOKEN=token,
        DATAAGENT_SCREENSHOT=str(evidence/'mapping-live.png'),
        DATAAGENT_TEST_PYTHON=sys.executable,PLAYWRIGHT_JSON_OUTPUT_NAME=str(report),**extra)
    command=['npm','run','test:e2e','--']+(['--grep',grep] if grep else [])+['--reporter=line,json']
    code=subprocess.run(command,cwd=WEB,env=env).returncode
    shot=evidence/'mapping-live.png'
    if shot.is_file():print('evidence:',shot)
    # Flaky tests do not fail the run (retries are enabled), but they must be listed.
    flaky=flaky_tests(report)
    if flaky:
        print(f'flaky（重试后通过，不计失败，共 {len(flaky)} 条）:')
        for item in flaky:print('  -',item)
    return code


def main():
    workspace=Path(tempfile.mkdtemp(prefix='dataagent-ui-'))
    state=Path(tempfile.mkdtemp(prefix='dataagent-ui-state-'))/'state.json'
    wb,server,thread,url=start_service(workspace)
    try:
        code=run_e2e(url,wb.token,{'DATAAGENT_TEST_STATE_FILE':str(state)})
    finally:
        server.should_exit=True;thread.join(timeout=5)
    if code!=0:raise SystemExit(code)
    if not state.is_file():raise SystemExit('restart preparation state missing')
    # Restart the service on the same workspace, then verify recovery in the browser.
    restarted,server2,thread2,url2=start_service(workspace)
    try:
        code=run_e2e(url2,restarted.token,
            {'DATAAGENT_TEST_STAGE':'recovery','DATAAGENT_TEST_STATE_FILE':str(state)},grep='重启')
    finally:
        server2.should_exit=True;thread2.join(timeout=5)
    raise SystemExit(code)


if __name__=='__main__':
    main()
