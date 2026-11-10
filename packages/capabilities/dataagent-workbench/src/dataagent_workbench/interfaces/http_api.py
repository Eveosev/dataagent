"""Same-origin authenticated local UI. No credential is returned by public endpoints."""
import hmac
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dataagent_contracts.intake import SourceSelection, WorkSpec
from dataagent_runtime.ports.workbench_store import VersionConflict


def create_app(wb):
    app = FastAPI(docs_url=None,redoc_url=None,openapi_url=None)

    @app.middleware('http')
    async def local_access(request: Request, call_next):
        host = request.headers.get('host','').split(':')[0]
        if host not in {'127.0.0.1','localhost','testserver'}:
            return JSONResponse({'error':'invalid_host'},status_code=403)
        origin = request.headers.get('origin')
        expected = str(request.base_url).rstrip('/')
        if origin and origin != expected:
            return JSONResponse({'error':'untrusted_origin'},status_code=403)
        if request.url.path.startswith('/api/'):
            token = request.headers.get('x-dataagent-token','')
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

    return app
