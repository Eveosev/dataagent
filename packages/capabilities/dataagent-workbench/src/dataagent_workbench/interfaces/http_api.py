"""Same-origin authenticated local UI. No credential is returned by public endpoints."""
import hmac
import hashlib
import json
import secrets
import time
import webbrowser
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlencode
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from dataagent_contracts.intake import SourceSelection, WorkSpec
from dataagent_contracts.ontology import MappingSpec,ReviewDecision
from dataagent_runtime.ports.workbench_store import VersionConflict


def create_app(wb):
    app = FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    launch_nonces={}

    @app.middleware('http')
    async def local_access(request: Request, call_next):
        host = request.headers.get('host','').split(':')[0]
        if host not in {'127.0.0.1','localhost','testserver'}:
            return JSONResponse({'error':'invalid_host'},status_code=403)
        origin = request.headers.get('origin')
        expected = str(request.base_url).rstrip('/')
        if origin and origin != expected:
            return JSONResponse({'error':'untrusted_origin'},status_code=403)
        if request.url.path.startswith('/api/') and request.url.path!='/api/auth':
            token = request.headers.get('x-dataagent-token','') or request.cookies.get('dataagent_workbench','')
            if not hmac.compare_digest(token,wb.token):
                return JSONResponse({'error':'authentication_required'},status_code=401)
        response = await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.exception_handler(VersionConflict)
    async def conflict(_, exc):
        return JSONResponse({'error':'version_conflict','detail':str(exc)},status_code=409)

    @app.exception_handler(KeyError)
    async def missing(_, exc):
        return JSONResponse({'error':'not_found'},status_code=404)

    @app.exception_handler(PermissionError)
    async def forbidden(_, exc):
        return JSONResponse({'error':'access_denied'},status_code=403)

    @app.exception_handler(ValueError)
    async def invalid(_, exc):
        return JSONResponse({'error':'invalid_input','detail':str(exc)},status_code=422)

    @app.get('/health')
    def health():
        return {'status':'ready','service':'dataagent-workbench','scope':wb.scope}

    @app.post('/local/open')
    async def open_browser(request:Request):
        data=await request.json()
        sid=data.get('session_id')
        run_id=data.get('run_id')
        if sid:wb.sessions.get(sid,wb.ctx)
        if run_id:
            workflow(run_id)
        for nonce,created in list(launch_nonces.items()):
            if time.monotonic()-created>60:launch_nonces.pop(nonce,None)
        if len(launch_nonces)>100:raise ValueError('too many pending browser launches')
        nonce=secrets.token_urlsafe(32);launch_nonces[nonce]=time.monotonic()
        route = {'workflow':run_id} if run_id else {'session':sid} if sid else {}
        base = str(request.base_url).rstrip('/')+'/#'
        webbrowser.open(base+urlencode({**route,'nonce':nonce}))
        return {'opened':True,'session_id':sid,'url':base+urlencode(route)}

    @app.post('/api/auth')
    async def exchange(request:Request):
        data=await request.json();created=launch_nonces.pop(data.get('nonce',''),None)
        if created is None or time.monotonic()-created>60:
            return JSONResponse({'error':'launch_expired'},status_code=401)
        response=JSONResponse({'authenticated':True})
        response.set_cookie('dataagent_workbench',wb.token,httponly=True,samesite='strict',path='/api')
        return response

    @app.get('/api/identity')
    def identity():return {'scope':wb.scope,'mode':'local-owner'}

    @app.get('/api/connections')
    def connections():
        from ..adapters.source_connections import SourceConnections
        return SourceConnections().list()

    @app.get('/api/workflows/{run_id}')
    def workflow(run_id: str):
        from ..adapters.operations_client import call_operations
        result = call_operations(wb, 'workflow_status', {'run_id': run_id})
        if result.status.value == 'failed':
            raise ValueError(result.issues[0].message)
        return result.data

    @app.post('/api/workflows/{run_id}/control')
    async def control_workflow(run_id: str, request: Request):
        from ..adapters.operations_client import call_operations
        data = await request.json()
        operation = 'workflow_advance' if data.get('command') == 'advance' else 'workflow_control'
        arguments = {'run_id': run_id}
        if operation == 'workflow_control':
            arguments.update(command=data.get('command'), values=data.get('values'))
        result = call_operations(wb, operation, arguments)
        if result.status.value == 'failed':
            raise ValueError(result.issues[0].message)
        return result.data

    @app.post('/api/sessions')
    async def start(request: Request):
        data = await request.json()
        goal = WorkSpec(id='goal',goal=data['goal'],acceptance_criteria=data.get('acceptance_criteria',['来源可核对']),
            authorization_ref=wb.authorization,domain_config_ref=data.get('domain_config_ref'))
        return wb.sessions.start([SourceSelection.model_validate(s) for s in data['sources']],goal,wb.ctx)

    @app.get('/api/sessions/{sid}')
    def status(sid: str):
        return wb.sessions.get(sid,wb.ctx)

    @app.get('/api/sessions/{sid}/events')
    def events(sid: str, after: int=0):
        return wb.sessions.events(sid,after,wb.ctx)

    @app.post('/api/files')
    async def upload(request: Request):
        name=Path(request.headers.get('x-file-name','input')).name
        suffix=Path(name).suffix.lower()
        if suffix not in {'.pdf','.csv','.tsv','.xlsx','.xlsm','.json','.jsonl','.sqlite','.sqlite3','.db'}:
            raise ValueError('unsupported file type')
        sid=uuid4().hex
        path=wb.root/'uploads'/(sid+suffix);path.parent.mkdir(exist_ok=True)
        size=0
        try:
            with path.open('wb') as f:
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>32*1024*1024:raise ValueError('file exceeds 32 MiB limit')
                    f.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True);raise
        if suffix in {'.sqlite','.sqlite3','.db'}:
            return SourceSelection(source_id=sid,kind='sqlite',locator_ref=str(path.relative_to(wb.workspace)))
        return SourceSelection(source_id=sid,kind='file',locator_ref=str(path.relative_to(wb.workspace)),options={'display_name':name})

    @app.get('/api/sessions/{sid}/view')
    def view(sid:str):return wb.intake.view(sid,wb.ctx)

    @app.post('/api/sessions/{sid}/advance')
    def advance(sid:str):return wb.intake.advance(sid,wb.ctx)

    @app.put('/api/sessions/{sid}/draft')
    async def draft(sid:str,request:Request):
        data=await request.json()
        return wb.intake.save_draft(sid,data['draft'],data['expected_revision'],wb.ctx)

    @app.post('/api/sessions/{sid}/proposal')
    async def propose(sid:str,request:Request):
        data=await request.json()
        return wb.intake.submit_proposal(sid,MappingSpec.model_validate(data['proposal']),data['expected_revision'],wb.ctx)

    @app.post('/api/sessions/{sid}/source-proposals')
    async def propose_sources(sid: str, request: Request):
        data = await request.json()
        proposals = {key: MappingSpec.model_validate(value) for key, value in data['proposals'].items()}
        return wb.intake.submit_source_proposals(sid, proposals, data['expected_revision'], wb.ctx)

    @app.post('/api/sessions/{sid}/review')
    async def review(sid:str,request:Request):
        data=await request.json()
        return wb.intake.apply(sid,ReviewDecision.model_validate(data['decision']),data['expected_revision'],wb.ctx)

    @app.post('/api/sessions/{sid}/revalidate')
    async def revalidate(sid:str,request:Request):
        data=await request.json()
        return wb.intake.revalidate(sid,data['expected_revision'],wb.ctx)

    @app.get('/api/sessions/{sid}/sources/{source_id}/raw')
    def original(sid:str,source_id:str):
        s=wb.sessions.get(sid,wb.ctx)
        sources=[p for p in wb.intake._profiles(s) if p.source_id==source_id]
        if len(sources)!=1:raise KeyError('source not in task')
        profile=sources[0]
        path=(wb.workspace/profile.metadata['snapshot_ref']).resolve()
        if not path.is_relative_to((wb.root/'content').resolve()):raise PermissionError('invalid snapshot')
        if 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()!=profile.source_revision:
            raise ValueError('source snapshot changed')
        media={'pdf':'application/pdf','json':'application/json','csv':'text/csv'}.get(profile.kind,'application/octet-stream')
        return FileResponse(path,media_type=media)

    @app.get('/api/sessions/{sid}/sources/{source_id}/pages/{page}')
    def page_preview(sid:str,source_id:str,page:int):
        from ..adapters.layer_client import LayerClient,installed_data_package
        s=wb.sessions.get(sid,wb.ctx)
        profiles=[p for p in wb.intake._profiles(s) if p.source_id==source_id and p.kind=='pdf']
        if len(profiles)!=1:raise KeyError('PDF source not in task')
        client=wb.layer_client or LayerClient(installed_data_package(wb.workspace))
        return FileResponse(client.render_page(profiles[0],page,wb.ctx,wb.workspace),media_type='image/png')

    static=Path(__file__).parents[1]/'static'
    if static.is_dir():app.mount('/',StaticFiles(directory=static,html=True),name='workbench')

    return app
