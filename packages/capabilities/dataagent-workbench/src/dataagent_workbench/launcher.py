"""Start and open a workspace-bound loopback service without printing credentials."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser


def ensure_service(wb):
    descriptor = wb.root/'runtime/workbench.json'
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


def open_view(wb, session_id):
    data = ensure_service(wb)
    url = data['url']+'/#session='+session_id
    webbrowser.open(url+'&token='+wb.token)
    return {'session_id':session_id,'url':url,'opened':True}
