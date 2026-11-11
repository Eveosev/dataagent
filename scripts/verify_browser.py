"""Exercise the real local web app; no test hooks are added to production."""
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
workspace=Path(tempfile.mkdtemp(prefix='dataagent-ui-'))
wb=Workbench(workspace,layer_client=LayerClient(ROOT/'packages/capabilities/dataagent-data'))
sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(128)
url=f'http://127.0.0.1:{sock.getsockname()[1]}'
server=uvicorn.Server(uvicorn.Config(create_app(wb),log_level='warning',access_log=False))
thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
try:
 for _ in range(100):
  try:
   urllib.request.urlopen(url+'/health',timeout=.2).close();break
  except OSError:time.sleep(.05)
 env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','LANG','TMPDIR','PLAYWRIGHT_BROWSERS_PATH'}}
 evidence=ROOT/'.superpowers/sdd/16-local-ingestion-workflow-build-plan/acceptance'
 evidence.mkdir(parents=True,exist_ok=True)
 env.update(DATAAGENT_TEST_URL=url,DATAAGENT_TEST_TOKEN=wb.token,DATAAGENT_SCREENSHOT=str(evidence/'mapping-live.png'),
            DATAAGENT_TEST_WORKSPACE=str(workspace),DATAAGENT_TEST_PYTHON=sys.executable)
 result=subprocess.run(['npm','run','test:e2e'],cwd=ROOT/'packages/capabilities/dataagent-workbench/web',env=env)
 raise SystemExit(result.returncode)
finally:
 server.should_exit=True;thread.join(timeout=5)
