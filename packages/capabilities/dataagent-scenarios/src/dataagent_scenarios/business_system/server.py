"""Local OA/CRM fixture. Public and evaluator ASGI apps are never mounted together."""
import asyncio
from copy import deepcopy
import hmac
from html import escape
import json
from typing import Annotated, Literal

from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from .schemas import AttachmentRequest, DraftRequest, EventPage, PatchRequest, Record, SubmitRequest, data_model
from .state import BusinessState


def _page(title, content):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>' + escape(title) + '''</title><style>
body{font-family:system-ui;max-width:1000px;margin:32px auto;padding:0 20px;color:#17324d;background:#f4f7fa}nav,a{color:#145b91}main{padding:24px;background:white;border-radius:12px}label{display:block;margin:16px 0}input{display:block;padding:8px;min-width:260px}button{padding:10px 18px;margin:12px 8px 12px 0;cursor:pointer}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}[data-layout=cards] form{display:grid;grid-template-columns:1fr 1fr;gap:8px}pre{white-space:pre-wrap}#feedback{color:#934800}</style></head><body><nav><a href="/">Business system</a> · <a href="/docs">API documentation</a></nav><main>''' + content + '</main></body></html>'


def create_app(state_path, config=None) -> FastAPI:
    """Create the discoverable public app; config is installed only for a new DB."""
    state = BusinessState(state_path, config)
    app = FastAPI(title='Local Business System', version='1.0.0',
                  description='Mutable local OA/CRM. Discover domain schemas, draft records, attach evidence, submit idempotently, and reconcile by business_key. Approval is a separate lifecycle event.')
    app.state.business_state = state
    for seed in state.config().get('demo_records', []):
        state.create(seed['domain'], seed['business_key'], seed['data'])

    @app.get('/api/domains', operation_id='discover_domains')
    def domains():
        return {'domains': state.config()['domains']}

    @app.get('/api/attachments/{attachment_id}', operation_id='download_attachment')
    def download(attachment_id: str):
        attachment = state.attachment(attachment_id)
        return Response(attachment['body'], media_type=attachment['content_type'],
                        headers={'Content-Disposition': "attachment; filename*=UTF-8''" + __import__('urllib.parse', fromlist=['quote']).quote(attachment['filename'])})

    def register_domain(domain):
        root = f'/api/{domain}/records'

        @app.get(root, operation_id=f'{domain}_query_records', summary='Query records, including reconciliation by business key')
        def query_records(business_key: str | None = None, offset: Annotated[int, Query(ge=0)] = 0,
                          limit: Annotated[int | None, Query(ge=1, le=100)] = None,
                          cursor: str | None = None):
            try:
                start = int(cursor) if cursor is not None else offset
                if start < 0:
                    raise ValueError()
            except ValueError:
                raise HTTPException(422, 'Invalid cursor')
            return state.records(domain, business_key, start, limit)

        @app.post(root, status_code=201, response_model=Record, operation_id=f'{domain}_create_draft', summary='Create an idempotent draft using a unique business key')
        def create_draft(request: DraftRequest):
            return state.create(domain, request.business_key, request.data)

        @app.get(root + '/{record_id}', response_model=Record, operation_id=f'{domain}_get_record')
        def get_record(record_id: str):
            return state.get(domain, record_id)

        @app.patch(root + '/{record_id}', response_model=Record, operation_id=f'{domain}_update_draft')
        def update_draft(record_id: str, request: PatchRequest):
            return state.patch(domain, record_id, request.data)

        @app.post(root + '/{record_id}/attachments', status_code=201, operation_id=f'{domain}_attach_evidence')
        def attach(record_id: str, request: AttachmentRequest):
            return state.attach(domain, record_id, request.model_dump())

        @app.post(root + '/{record_id}/submit', response_model=Record, operation_id=f'{domain}_submit_record', summary='Submit a draft for approval; reconcile unknown results by business_key before retrying')
        async def submit(record_id: str, request: SubmitRequest):
            record, delay = state.submit(domain, record_id, request.request_key)
            if delay is not None:
                # Commit precedes the lost response. A short-timeout real client sees
                # an actual timeout; no successful submission receipt is delivered.
                await asyncio.sleep(delay)
                raise ConnectionResetError('Submission committed; response lost')
            return record

        @app.get(root + '/{record_id}/status', response_model=Record, operation_id=f'{domain}_query_status')
        def status(record_id: str):
            return state.get(domain, record_id)

        @app.get(root + '/{record_id}/events', response_model=EventPage, operation_id=f'{domain}_approval_events')
        def events(record_id: str, after: Annotated[int, Query(ge=0)] = 0):
            return state.events(domain, record_id, after)

    for domain in state.config()['domains']:
        register_domain(domain)

    def public_openapi():
        # Rebuild from persisted configuration so drift is observable immediately,
        # including when a separate evaluator process changed the same DB.
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        for name, domain in state.config()['domains'].items():
            root = f'/api/{name}/records'
            for method, path, partial in [('post', root, False), ('patch', root + '/{record_id}', True)]:
                fields = data_model(f'{name}Fields', domain, partial=partial).model_json_schema()
                request_schema = {'type': 'object', 'additionalProperties': False,
                                  'properties': {'data': fields}, 'required': ['data']}
                if method == 'post':
                    request_schema['properties']['business_key'] = {'type': 'string', 'minLength': 1}
                    request_schema['required'].append('business_key')
                schema['paths'][path][method]['requestBody']['content']['application/json']['schema'] = request_schema
            record_schema = deepcopy(schema['components']['schemas']['Record'])
            record_schema['properties']['data'] = data_model(f'{name}RecordFields', domain, partial=True).model_json_schema()
            schema['paths'][root]['get']['responses']['200']['content']['application/json']['schema'] = {
                'type': 'object', 'properties': {
                    domain['collection_field']: {'type': 'array', 'items': record_schema},
                    'total': {'type': 'integer'}, 'has_more': {'type': 'boolean'},
                    'next_cursor': {'type': ['string', 'null']}, 'next_offset': {'type': ['integer', 'null']},
                    'observed_at': {'type': 'string', 'format': 'date-time'}},
                'x-pagination': domain['pagination']}
        return schema

    app.openapi = public_openapi

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    def home():
        links = ''.join(f'<li><a href="/ui/{escape(name)}/records">{escape(domain["title"])}</a></li>' for name, domain in state.config()['domains'].items())
        return _page('Business system', '<h1>Business system</h1><p>Choose a business area to query records or create a draft.</p><ul>' + links + '</ul>')

    @app.get('/ui/{domain}/records', response_class=HTMLResponse, include_in_schema=False)
    def record_list(domain: str, business_key: str | None = None):
        conf = state.domain(domain)
        records = state.records(domain, business_key)[conf['collection_field']]
        rows = ''.join(f'<tr><td><a href="/ui/{escape(domain)}/records/{r["id"]}">{escape(r["business_key"])}</a></td><td>{escape(r["status"])}</td><td>{escape(str(r["data"]))}</td></tr>' for r in records)
        return _page(conf['title'], f'<h1>{escape(conf["title"])}</h1><a href="/ui/{escape(domain)}/records/new">Create draft</a><form><label>Business key<input name="business_key" value="{escape(business_key or "")}"></label><button>Search records</button></form><table><thead><tr><th>Business key</th><th>Status</th><th>Fields</th></tr></thead><tbody>{rows}</tbody></table>')

    @app.get('/ui/{domain}/records/{record_id}', response_class=HTMLResponse, include_in_schema=False)
    def record_view(domain: str, record_id: str):
        conf = state.domain(domain)
        new = record_id == 'new'
        record = {'id': None, 'business_key': '', 'data': {}, 'status': 'draft', 'native_status': 'DRAFT', 'attachments': []} if new else state.get(domain, record_id)
        controls = ''
        for field in conf['fields']:
            value = record['data'].get(field['name'], '')
            required = ' required' if field.get('required') else ''
            name = escape(field['name'], quote=True)
            controls += f'<label for="field-{name}">{escape(field["label"])}<input id="field-{name}" name="{name}" value="{escape(str(value), quote=True)}"{required}></label>'
        payload = json.dumps({'domain': domain, 'record': record}).replace('<', '\\u003c')
        attachments = ''.join(f'<li><a href="{escape(a["download_url"])}">{escape(a["filename"])}</a></li>' for a in record['attachments'])
        content = f'''<section data-layout="{escape(conf['layout'])}"><h1>{escape(conf['title'])} — {escape(record['business_key'] or 'New draft')}</h1>
<p role="status" id="business-status">Status: {record['status']} ({record['native_status']})</p>
<form id="draft-form"><label for="business-key">Business key<input id="business-key" name="business_key" value="{escape(record['business_key'], quote=True)}" required {'readonly' if not new else ''}></label>{controls}<button type="submit">Save draft</button></form>
<label for="attachment-file">Evidence attachment<input id="attachment-file" type="file"></label><button id="upload" type="button">Attach evidence</button><ul>{attachments}</ul>
<button id="submit-record" type="button">{escape(conf['submit_label'])}</button><button id="refresh-status" type="button">Refresh status</button><p id="feedback" role="alert"></p><h2>Approval events</h2><ol id="events"></ol></section>
<script type="application/json" id="page-data">{payload}</script><script>
const page=JSON.parse(document.getElementById('page-data').textContent);let record=page.record;
const root='/api/'+encodeURIComponent(page.domain)+'/records';
const feedback=document.getElementById('feedback');
async function call(url,method='GET',body){{const response=await fetch(url,{{method,headers:{{'Content-Type':'application/json'}},body:body===undefined?undefined:JSON.stringify(body)}});const value=await response.json();if(!response.ok)throw Error(JSON.stringify(value.detail||value));return value;}}
async function report(action){{try{{await action();}}catch(error){{feedback.textContent=error.message;}}}}
function saved(value){{record=value;document.getElementById('business-status').textContent='Status: '+record.status+' ('+record.native_status+')';feedback.textContent='Saved '+record.business_key;}}
document.getElementById('draft-form').addEventListener('submit',event=>{{event.preventDefault();report(async()=>{{const form=new FormData(event.target);const data={{}};for(const [key,value] of form)if(key!=='business_key')data[key]=value;const value=await call(record.id?root+'/'+record.id:root,record.id?'PATCH':'POST',record.id?{{data}}:{{business_key:form.get('business_key'),data}});saved(value);history.replaceState(null,'','/ui/'+page.domain+'/records/'+record.id);}});}});
document.getElementById('submit-record').onclick=()=>report(async()=>{{if(!record.id)throw Error('Save the draft first');saved(await call(root+'/'+record.id+'/submit','POST',{{request_key:'submit-'+record.id}}));await refresh();}});
async function refresh(){{if(!record.id)return;saved(await call(root+'/'+record.id+'/status'));const events=await call(root+'/'+record.id+'/events');const list=document.getElementById('events');list.replaceChildren();for(const event of events.items){{const li=document.createElement('li');li.textContent=event.status+' '+event.occurred_at;list.append(li);}}}}
document.getElementById('refresh-status').onclick=()=>report(refresh);
document.getElementById('upload').onclick=()=>report(async()=>{{if(!record.id)throw Error('Save the draft first');const file=document.getElementById('attachment-file').files[0];if(!file)throw Error('Choose an evidence attachment');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);await call(root+'/'+record.id+'/attachments','POST',{{filename:file.name,content_type:file.type||'application/octet-stream',content_base64:btoa(binary),request_key:'attach-'+record.id+'-'+file.name}});feedback.textContent='Attachment saved: '+file.name;}});
report(refresh);
</script>'''
        return _page(conf['title'], content)

    return app


class ApprovalRequest(BaseModel):
    domain: str
    record_id: str
    outcome: Literal['approved', 'rejected']


def create_admin_app(state_path, *, token: str) -> FastAPI:
    """Evaluator-only separate listener; never give its address or token to Agent."""
    if not token:
        raise ValueError('Evaluator token must not be empty')
    state = BusinessState(state_path)
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

    def authorize(value):
        if value is None or not hmac.compare_digest(value, token):
            raise HTTPException(403, 'Evaluator authorization required')

    @app.post('/config')
    def configure(change: dict = Body(...), x_admin_token: str | None = Header(None)):
        authorize(x_admin_token)
        return state.change_config(change)

    @app.post('/faults')
    def faults(change: dict = Body(...), x_admin_token: str | None = Header(None)):
        authorize(x_admin_token)
        return state.faults(change)

    @app.post('/approval')
    def approval(change: ApprovalRequest, x_admin_token: str | None = Header(None)):
        authorize(x_admin_token)
        return state.approve(change.domain, change.record_id, change.outcome)

    return app
