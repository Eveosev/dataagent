"""Small stdio JSON-RPC service; authority is supplied by local composition."""
import json
import os
import sys
from ..bootstrap import Workbench
from ..service_tools import invoke, result_summary
from ..tool_schema import TOOLS

def handle(wb, request):
    method = request.get('method')
    if method == 'initialize':
        return {'protocolVersion':request.get('params',{}).get('protocolVersion','2024-11-05'),
            'capabilities':{'tools':{}},'serverInfo':{'name':'dataagent-workbench','version':'0.1.0'}}
    if method == 'ping': return {}
    if method == 'tools/list': return {'tools':TOOLS}
    if method == 'tools/call':
        params = request['params']
        try:
            result = result_summary(wb,invoke(wb,params['name'],params.get('arguments',{})))
            return {'content':[{'type':'text','text':json.dumps(result,ensure_ascii=False)}],'isError':False}
        except (ValueError,KeyError,PermissionError) as exc:
            return {'content':[{'type':'text','text':json.dumps({'error':getattr(exc,'code','invalid_input'),'detail':str(exc)})}],'isError':True}
    raise ValueError('unsupported method')


def main():
    wb = Workbench(os.environ.get('DATAAGENT_WORKSPACE',os.getcwd()))
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if 'id' not in request: continue
            try:
                response = {'jsonrpc':'2.0','id':request['id'],'result':handle(wb,request)}
            except ValueError as exc:
                response = {'jsonrpc':'2.0','id':request['id'],'error':{'code':-32601,'message':str(exc)}}
        except (ValueError,TypeError):
            response = {'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'invalid JSON request'}}
        print(json.dumps(response,ensure_ascii=False),flush=True)


if __name__ == '__main__': main()
