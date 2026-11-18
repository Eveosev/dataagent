"""Local workbench CLI. Credentials stay in the launch channel, outside stdout."""
import argparse
import json
import os
import socket
from pathlib import Path
from ..adapters.source_connections import bind_workspace, bound_workspace
from ..bootstrap import Workbench
from ..launcher import stop_service
from ..service_tools import invoke, result_summary


def _bind_workspace(wb):
    """Make every connection lookup in this process use ``wb.workspace``."""

    bind_workspace(wb.workspace)
    os.environ['DATAAGENT_WORKSPACE'] = str(wb.workspace)


def _service_app(wb):
    """The HTTP app with a pid-stamped health endpoint.

    ``stop_service`` compares this pid with the descriptor's pid, so a stale
    or copied descriptor cannot point one workspace's pid at another
    workspace's URL.
    """

    from .http_api import create_app

    app = create_app(wb)

    async def with_identity(scope, receive, send):
        if scope.get('type') == 'http' and scope.get('path') == '/health':
            body = json.dumps({'status': 'ready', 'service': 'dataagent-workbench',
                               'scope': wb.scope, 'pid': os.getpid()}).encode()
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', b'application/json'),
                                    (b'content-length', str(len(body)).encode())]})
            await send({'type': 'http.response.body', 'body': body})
            return
        await app(scope, receive, send)

    return with_identity


def list_sessions(wb):
    """Tasks in this workspace with their phase and published release."""

    rows = wb.store.query('session', wb.scope, limit=1000)
    sessions = []
    for row in rows:
        body = row.get('body') or {}
        task = None
        goal_ref = str(body.get('goal_ref') or '')
        if '@' in goal_ref:
            goal_id, revision = goal_ref.rsplit('@', 1)
            goal = wb.store.get('goal', goal_id, revision, scope=wb.scope)
            if goal:
                task = (goal.get('body') or {}).get('goal')
        sessions.append({
            'session_id': row.get('id'),
            'task': task,
            'phase': body.get('phase'),
            'release_ref': (body.get('selected_versions') or {}).get('release'),
        })
    return sessions


def _run(wb, args):
    if args.command=='serve':
        import uvicorn
        sock=socket.socket();sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind(('127.0.0.1',args.port));sock.listen(128)
        data={'url':f'http://127.0.0.1:{sock.getsockname()[1]}','scope':wb.scope,'pid':os.getpid()}
        descriptor=wb.root/'runtime/workbench.json'
        descriptor.write_text(json.dumps(data))
        try:
            uvicorn.Server(uvicorn.Config(_service_app(wb),log_level='warning',access_log=False)).run(sockets=[sock])
        finally:
            # A clean shutdown must not leave a descriptor pointing at a dead pid.
            try:
                current=json.loads(descriptor.read_text())
            except (OSError,ValueError):
                current=None
            if isinstance(current,dict) and current.get('pid')==os.getpid():
                descriptor.unlink(missing_ok=True)
        return
    if args.command=='health':
        print(json.dumps({'status':'ready','service':'dataagent-workbench','scope':wb.scope,'pid':os.getpid()}));return
    try:
        if args.command=='intake':
            data={'goal':args.goal,'sources':[{'source_id':f'source-{i}','kind':'file','locator_ref':s} for i,s in enumerate(args.source)]}
            result=invoke(wb,'intake_start',data)
        elif args.command=='list':
            print(json.dumps(list_sessions(wb),ensure_ascii=False));return
        elif args.command=='stop':
            stopped=stop_service(wb)
            print(json.dumps(stopped,ensure_ascii=False))
            if stopped.get('status')=='failed':
                raise SystemExit(1)
            return
        else:
            result=invoke(wb,'workbench_view' if args.command=='view' else 'intake_status',{'session_id':args.session_id})
        print(json.dumps(result_summary(wb,result),ensure_ascii=False))
    except (ValueError,KeyError,PermissionError) as exc:
        print(json.dumps({'status':'failed','error':getattr(exc,'code','invalid_input'),'detail':str(exc)}))
        raise SystemExit(1)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',default=os.environ.get('DATAAGENT_WORKSPACE',os.getcwd()))
    commands=p.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve');serve.add_argument('--port',type=int,default=0)
    intake=commands.add_parser('intake');intake.add_argument('--goal',required=True);intake.add_argument('--source',action='append',required=True)
    for name in ['status','view']:
        commands.add_parser(name).add_argument('session_id')
    commands.add_parser('list')
    commands.add_parser('stop')
    commands.add_parser('health')
    args=p.parse_args();wb=Workbench(args.workspace)
    previous_bind=bound_workspace()
    previous_env=os.environ.get('DATAAGENT_WORKSPACE')
    _bind_workspace(wb)
    try:
        _run(wb,args)
    finally:
        # A CLI call must not leak its workspace into an embedding process.
        # ``serve`` remains bound for the lifetime of the server.
        bind_workspace(previous_bind)
        if previous_env is None:
            os.environ.pop('DATAAGENT_WORKSPACE',None)
        else:
            os.environ['DATAAGENT_WORKSPACE']=previous_env


if __name__=='__main__': main()
