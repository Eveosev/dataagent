import json
import subprocess
import sys
from dataagent_contracts.core import CapabilityResult
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.mcp_server import handle


def test_mcp_pending_returns_real_job_and_no_credential(tmp_path):
    wb=Workbench(tmp_path)
    response=handle(wb,{'method':'tools/call','params':{'name':'intake_start','arguments':{
        'goal':'接入发票','sources':[{'source_id':'f','kind':'file','locator_ref':'in.csv'}]}}})
    payload=json.loads(response['content'][0]['text'])
    result=CapabilityResult.model_validate(payload['result'])
    job=wb.store.current('job',result.continuation.job_ref,scope=wb.scope)
    assert job['body']['state']=='queued'
    assert wb.token not in json.dumps(response)


def test_cli_and_mcp_share_session(tmp_path):
    result=subprocess.run([sys.executable,'-m','dataagent_workbench.interfaces.cli',
        '--workspace',str(tmp_path),'intake','--goal','接入','--source','in.csv'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)['result']['data']
    wb=Workbench(tmp_path)
    response=handle(wb,{'method':'tools/call','params':{'name':'intake_status','arguments':{'session_id':data['session_id']}}})
    status=json.loads(response['content'][0]['text'])['result']['data']
    assert status['sources'][0]['locator_ref']=='in.csv'


def test_stdio_initialization_and_error_do_not_break_next_request(tmp_path):
    requests=[{'jsonrpc':'2.0','id':1,'method':'initialize'},
        {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'intake_status','arguments':{'session_id':'missing'}}},
        {'jsonrpc':'2.0','id':3,'method':'tools/list'}]
    import os
    env={**os.environ,'DATAAGENT_WORKSPACE':str(tmp_path)}
    result=subprocess.run([sys.executable,'-m','dataagent_workbench.interfaces.mcp_server'],
        input='\n'.join(json.dumps(r) for r in requests),capture_output=True,text=True,env=env)
    assert result.returncode==0,result.stderr
    replies=[json.loads(x) for x in result.stdout.splitlines()]
    assert [r['id'] for r in replies]==[1,2,3]
    assert replies[1]['result']['isError']
    assert 'intake_start' in [t['name'] for t in replies[2]['result']['tools']]
