"""Local workbench CLI. Credentials stay in the launch channel, outside stdout."""
import argparse
import json
import os
import socket
from pathlib import Path
from ..bootstrap import Workbench
from ..service_tools import invoke, result_summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',default=os.environ.get('DATAAGENT_WORKSPACE',os.getcwd()))
    commands=p.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve');serve.add_argument('--port',type=int,default=0)
    intake=commands.add_parser('intake');intake.add_argument('--goal',required=True);intake.add_argument('--source',action='append',required=True)
    for name in ['status','view']:
        commands.add_parser(name).add_argument('session_id')
    commands.add_parser('health')
    args=p.parse_args();wb=Workbench(args.workspace)
    if args.command=='serve':
        import uvicorn
        from .http_api import create_app
        sock=socket.socket();sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind(('127.0.0.1',args.port));sock.listen(128)
        data={'url':f'http://127.0.0.1:{sock.getsockname()[1]}','scope':wb.scope,'pid':os.getpid()}
        (wb.root/'runtime/workbench.json').write_text(json.dumps(data))
        uvicorn.Server(uvicorn.Config(create_app(wb),log_level='warning',access_log=False)).run(sockets=[sock])
        return
    if args.command=='health':
        print(json.dumps({'status':'ready','scope':wb.scope}));return
    try:
        if args.command=='intake':
            data={'goal':args.goal,'sources':[{'source_id':f'source-{i}','kind':'file','locator_ref':s} for i,s in enumerate(args.source)]}
            result=invoke(wb,'intake_start',data)
        else:
            result=invoke(wb,'workbench_view' if args.command=='view' else 'intake_status',{'session_id':args.session_id})
        print(json.dumps(result_summary(wb,result),ensure_ascii=False))
    except (ValueError,KeyError,PermissionError) as exc:
        print(json.dumps({'status':'failed','error':getattr(exc,'code','invalid_input'),'detail':str(exc)}))
        raise SystemExit(1)


if __name__=='__main__': main()
