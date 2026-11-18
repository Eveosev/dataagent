"""Real local sources: bounded reading, provenance and failure preservation."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sqlite3
import threading
from pathlib import Path
import pytest
from dataagent_contracts.intake import SourceSelection


def db_selection(**kwargs):
    return SourceSelection(source_id='db', kind='sqlite', locator_ref=kwargs.pop('locator', 'data.sqlite'), **kwargs)


@pytest.fixture
def database(tmp_path):
    with sqlite3.connect(tmp_path/'data.sqlite') as conn:
        conn.executescript('''CREATE TABLE entries (tenant TEXT, n INTEGER, label TEXT, effective DATE, PRIMARY KEY(tenant,n));
        INSERT INTO entries VALUES ('a',1,'same','2026-01-01'),('b',1,'same',NULL),('a',2,NULL,'2026-02-01');
        CREATE TABLE other (n INTEGER PRIMARY KEY, label TEXT);
        INSERT INTO other VALUES (1,'same');''')
    return tmp_path


def test_sqlite_composite_keys_nulls_and_exact_anchors(database):
    from dataagent_data.observation.database import probe_database
    result=probe_database(db_selection(requested_scope={'tables':['entries']}), None, workspace=database)
    assert len(result.records)==3
    assert result.coverage=='full'
    assert result.metadata['tables'][0]['primary_key']==['tenant','n']
    assert result.metadata['record_keys'][0]=={'table':'entries','keys':[{'field':'tenant','type':'str','value':'a'},{'field':'n','type':'int','value':1}]}
    assert any(row['effective'] is None for row in result.records)
    selector=result.anchors['0.label'][0].selector
    assert selector.keys=={'table':'entries','primary_key':{'tenant':'a','n':1}}
    assert selector.field=='label'
    assert result.anchors['0.label'][0].source_revision==result.source_revision
    assert (database/result.metadata['snapshot_ref']).is_file()


def test_database_key_named_table_cannot_replace_source_table(tmp_path):
    from dataagent_data.observation.database import probe_database
    with sqlite3.connect(tmp_path/'data.sqlite') as conn:
        conn.executescript('CREATE TABLE items ("table" TEXT PRIMARY KEY, amount INTEGER);'
                           "INSERT INTO items VALUES ('item-1', 42);")
    profile=probe_database(db_selection(),None,workspace=tmp_path)
    assert profile.anchors['0.amount'][0].selector.keys == {
        'table':'items', 'primary_key':{'table':'item-1'},
    }


def test_sqlite_budget_and_schema_fingerprint(database):
    from dataagent_data.observation.database import probe_database
    selection=db_selection(requested_scope={'tables':['entries']})
    result=probe_database(selection,None,workspace=database,budget_rows=2)
    assert result.sampled and result.coverage=='sampled'
    assert len(result.records)==2
    assert result.metadata['tables'][0]['uniqueness_scope']=='sample'
    with sqlite3.connect(database/'data.sqlite') as conn: conn.execute('ALTER TABLE entries ADD COLUMN extra REAL')
    changed=probe_database(selection,None,workspace=database,budget_rows=2)
    assert result.metadata['structure_fingerprint']!=changed.metadata['structure_fingerprint']


@pytest.mark.parametrize('locator',['../outside.sqlite','/tmp/outside.sqlite','file:data.sqlite?mode=rw'])
def test_sqlite_refuses_uncontrolled_paths(database, locator):
    from dataagent_data.observation.database import probe_database
    with pytest.raises((PermissionError,ValueError)):
        probe_database(db_selection(locator=locator),None,workspace=database)


def test_sqlite_refuses_symlink_and_user_sql(database,tmp_path):
    from dataagent_data.observation.database import probe_database
    (database/'alias.sqlite').symlink_to(database/'data.sqlite')
    with pytest.raises(PermissionError): probe_database(db_selection(locator='alias.sqlite'),None,workspace=database)
    with pytest.raises(ValueError): probe_database(db_selection(options={'query':'DELETE FROM entries'}),None,workspace=database)
    with sqlite3.connect(database/'data.sqlite') as conn: assert conn.execute('SELECT count(*) FROM entries').fetchone()[0]==3


def test_source_port_describes_reads_and_explicitly_rejects_changes(database):
    from dataagent_data.adapters.sources.sqlite import SQLiteSource
    from dataagent_data.ports.source import SourcePort
    adapter=SQLiteSource(db_selection(requested_scope={'tables':['other']}),workspace=database)
    assert isinstance(adapter, SourcePort)
    assert adapter.describe(None).metadata['tables'][0]['name']=='other'
    assert adapter.read(None,budget_rows=1).records==[{'n':1,'label':'same'}]
    assert adapter.changes(None).metadata['status']=='unsupported'


@pytest.fixture
def http_source():
    routes={}; requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path,dict(self.headers)))
            status,payload,headers=routes.get(self.path,(404,{},{}))
            body=json.dumps(payload).encode()
            self.send_response(status)
            for key,value in headers.items(): self.send_header(key,value)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    yield origin,routes,requests
    server.shutdown();server.server_close();thread.join()


def rest_selection(origin,path='/items',**kwargs):
    options={'records_path':'/items','pagination':{'next_path':'/next'},'keys':['id']}
    options.update(kwargs.pop('options',{}))
    return SourceSelection(source_id='api',kind='rest',locator_ref=origin+path,options=options,**kwargs)


def test_rest_probe_segments_by_page_and_resumes(tmp_path,http_source):
    from dataagent_data.observation.cli import probe
    origin,routes,requests=http_source
    routes['/items']=(200,{'items':[{'id':1}],'next':'/more'},{'X-Source-Version':'r1'})
    routes['/more']=(200,{'items':[{'id':2}],'next':None},{'X-Source-Version':'r1'})
    selection=rest_selection(origin)
    first=probe(selection,None,tmp_path,{'allowed_origins':[origin],'segment_pages':1})
    assert first.coverage=='partial'
    assert first.completed_partitions==[1]
    assert first.records==[{'/id':1}]
    assert [(gap.partition,gap.code) for gap in first.gaps]==[(2,'time_budget_exceeded')]
    assert first.metadata['resume']=={'kind':'rest','next_page':2}
    assert [path for path,_ in requests]==['/items']
    second=probe(selection,None,tmp_path,{'allowed_origins':[origin],
        'previous':first.model_dump(mode='json')})
    assert second.coverage=='full' and second.completed_partitions==[1,2]
    assert second.records==[{'/id':1},{'/id':2}]
    assert [path for path,_ in requests]==['/items','/more']


def test_rest_follows_pages_preserves_nesting_and_response_anchors(tmp_path,http_source):
    from dataagent_data.observation.http import probe_rest
    origin,routes,requests=http_source
    routes['/items']=(200,{'items':[{'id':1,'nested':{'label':'same'},'lines':[{'x':2}]}],'next':'/items?p=2'},{'X-Source-Version':'r1'})
    routes['/items?p=2']=(200,{'items':[{'id':2,'nested':{'label':None},'lines':[]}],'next':None},{'X-Source-Version':'r1'})
    profile=probe_rest(rest_selection(origin),None,workspace=tmp_path,allowed_origins=[origin])
    assert profile.coverage=='full' and profile.completed_partitions==[1,2]
    assert profile.records[0]['/lines']==[{'x':2}]
    anchor=profile.anchors['1./nested/label'][0]
    assert anchor.selector.pointer=='/items/0/nested/label'
    assert anchor.extraction_ref==profile.metadata['pages'][1]['snapshot_ref']
    assert profile.metadata['cursor'] is None
    assert profile.metadata['record_keys'][0]['keys']==[{'field':'id','type':'int','value':1}]


@pytest.mark.parametrize('status,code',[(429,'rate_limited'),(500,'http_error')])
def test_rest_retains_successful_page_when_later_request_fails(tmp_path,http_source,status,code):
    from dataagent_data.observation.http import probe_rest
    origin,routes,_=http_source
    routes['/items']=(200,{'items':[{'id':1}],'next':'/more'},{})
    routes['/more']=(status,{}, {'Retry-After':'4'})
    profile=probe_rest(rest_selection(origin),None,workspace=tmp_path,allowed_origins=[origin])
    assert profile.records==[{'/id':1}] and profile.coverage=='partial'
    assert profile.completed_partitions==[1]
    assert code in [issue['code'] for issue in profile.issues]
    assert profile.metadata['cursor']==origin+'/more'


@pytest.mark.parametrize('version', ['r1', 'r2', None])
def test_rest_resumes_only_a_matching_snapshot_and_retains_first_page(tmp_path,http_source,version):
    from dataagent_data.observation.http import probe_rest, resume_rest
    origin,routes,requests=http_source
    selection=rest_selection(origin)
    routes['/items']=(200,{'items':[{'id':1}],'next':'/more'},{'X-Source-Version':'r1'})
    routes['/more']=(429,{}, {'Retry-After':'1'})
    initial=probe_rest(selection,None,workspace=tmp_path,allowed_origins=[origin])
    routes['/more']=(200,{'items':[{'id':2}],'next':None},{'X-Source-Version':version} if version else {})
    resumed=resume_rest(selection,initial,None,workspace=tmp_path,allowed_origins=[origin])
    assert [path for path,_ in requests] == ['/items','/more','/more']
    assert resumed.anchors['0./id'] == initial.anchors['0./id']
    if version == 'r1':
        assert resumed.coverage == 'full' and resumed.completed_partitions == [1,2]
        assert resumed.records == [{'/id':1},{'/id':2}]
        assert resumed.metadata['record_keys'][1]['page'] == 2
    else:
        assert resumed.coverage == 'partial'
        assert resumed.records == initial.records
        assert 'source_version_drift' in {gap.code for gap in resumed.gaps}


def test_rest_resumes_at_checkpoint_offset_instead_of_initial_offset(tmp_path,http_source):
    from dataagent_data.observation.http import probe_rest, resume_rest
    origin,routes,_=http_source
    selection=rest_selection(origin,requested_scope={'row_offset':1})
    headers={'X-Source-Version':'r1'}
    routes['/items']=(200,{'items':[{'id':1},{'id':2}],'next':'/more'},headers)
    routes['/more']=(429,{}, {})
    first=probe_rest(selection,None,workspace=tmp_path,allowed_origins=[origin])
    routes['/more']=(200,{'items':[{'id':3},{'id':4}],'next':None},headers)
    resumed=resume_rest(selection,first,None,workspace=tmp_path,allowed_origins=[origin])
    assert resumed.coverage=='full'
    assert resumed.records==[{'/id':2},{'/id':3},{'/id':4}]


@pytest.mark.parametrize('next_value,code',[('/items','pagination_cycle'),('http://localhost:1/private','origin_not_allowed')])
def test_rest_refuses_cycles_and_unapproved_next_pages(tmp_path,http_source,next_value,code):
    from dataagent_data.observation.http import probe_rest
    origin,routes,requests=http_source
    routes['/items']=(200,{'items':[{'id':1}],'next':next_value},{})
    profile=probe_rest(rest_selection(origin),None,workspace=tmp_path,allowed_origins=[origin])
    assert len(requests)==1 and profile.coverage=='partial'
    assert code in [issue['code'] for issue in profile.issues]


def test_rest_refuses_cross_origin_redirect(tmp_path,http_source):
    from dataagent_data.observation.http import probe_rest
    origin,routes,requests=http_source
    routes['/items']=(302,{}, {'Location':'http://localhost:1/private'})
    profile=probe_rest(rest_selection(origin),None,workspace=tmp_path,allowed_origins=[origin])
    assert profile.coverage=='partial' and len(requests)==1
    assert 'redirect_refused' in [i['code'] for i in profile.issues]


@pytest.mark.parametrize('versions', [('r1','r2'), (None,'r1'), ('r1',None)])
def test_rest_stops_before_mixing_source_versions(tmp_path,http_source,versions):
    from dataagent_data.observation.http import probe_rest
    origin,routes,_=http_source
    routes['/items']=(200,{'items':[{'id':1}],'next':'/more'},{'X-Source-Version':versions[0]} if versions[0] else {})
    routes['/more']=(200,{'items':[{'id':2}],'next':None},{'X-Source-Version':versions[1]} if versions[1] else {})
    result=probe_rest(rest_selection(origin),None,workspace=tmp_path,allowed_origins=[origin])
    assert result.records==[{'/id':1}] and result.coverage=='partial'
    assert result.completed_partitions==[1]
    assert 'source_version_drift' in {i['code'] for i in result.issues}


def test_rest_budget_cursor_and_host_credentials_are_not_persisted(tmp_path,http_source):
    from dataagent_data.observation.http import probe_rest
    origin,routes,requests=http_source
    routes['/items']=(200,{'items':[{'id':1},{'id':2}],'next':'/more'},{})
    result=probe_rest(rest_selection(origin),None,workspace=tmp_path,budget_rows=1,allowed_origins=[origin],credentials={'auth':'bearer','token':'host-secret'})
    assert result.coverage=='sampled' and len(result.records)==1
    assert result.metadata['cursor']==origin+'/items'
    assert result.metadata['row_offset']==1
    assert requests[0][1]['Authorization']=='Bearer host-secret'
    assert 'host-secret' not in result.model_dump_json()
    assert all(b'host-secret' not in file.read_bytes() for file in (tmp_path/'.dataagent/content').iterdir())


@pytest.mark.parametrize('version', [None, 'r1'])
def test_rest_cursor_pagination(tmp_path,http_source,version):
    from dataagent_data.observation.http import probe_rest
    origin,routes,_=http_source
    headers={'X-Source-Version':version} if version else {}
    routes['/items']=(200,{'items':[{'id':1}],'cursor':'abc'},headers)
    routes['/items?after=abc']=(200,{'items':[{'id':2}],'cursor':None},headers)
    result=probe_rest(rest_selection(origin,options={'pagination':{'cursor_path':'/cursor','cursor_param':'after'}}),None,workspace=tmp_path,allowed_origins=[origin])
    assert len(result.records)==2
    assert result.coverage==('full' if version else 'partial')
    if not version:assert 'source_snapshot_unverified' in {i['code'] for i in result.issues}


@pytest.mark.parametrize('change',[{'locator_ref':'http://user:secret@127.0.0.1/items'},{'credentials':{'auth':'oauth-magic','token':'secret'}},{'allowed_origins':None}])
def test_rest_refuses_unsafe_connection_before_request(tmp_path,http_source,change):
    from dataagent_data.observation.http import probe_rest
    origin,_,requests=http_source
    selection=rest_selection(origin)
    kwargs={'workspace':tmp_path,'allowed_origins':[origin]}
    if 'locator_ref' in change: selection=selection.model_copy(update=change)
    else: kwargs.update(change)
    with pytest.raises((PermissionError,ValueError)): probe_rest(selection,None,**kwargs)
    assert not requests


def test_postgres_refuses_inline_secrets_and_sql_before_connect(tmp_path):
    from dataagent_data.observation.database import probe_database
    for locator,options in [('postgresql://user:secret@localhost/test',{}),('postgresql://localhost/test',{'query':'DELETE FROM entries'})]:
        with pytest.raises(ValueError): probe_database(SourceSelection(source_id='pg',kind='postgres',locator_ref=locator,options=options),None,workspace=tmp_path)


def test_rest_versionless_segment_resume_does_not_reread_first_page(tmp_path, http_source):
    from dataagent_data.observation.cli import probe
    origin, routes, requests = http_source
    routes['/items'] = (200, {'items': [{'id': 1}], 'next': '/more'}, {})
    routes['/more'] = (200, {'items': [{'id': 2}], 'next': None}, {})
    selection = rest_selection(origin)
    first = probe(selection, None, tmp_path, {'allowed_origins': [origin],
                                              'segment_pages': 1})
    assert first.coverage == 'partial'
    assert first.completed_partitions == [1]
    assert first.records == [{'/id': 1}]
    assert first.metadata['resume'] == {'kind': 'rest', 'next_page': 2}
    assert [path for path, _ in requests] == ['/items']
    second = probe(selection, None, tmp_path, {'allowed_origins': [origin],
                                               'segment_pages': 1,
                                               'previous': first.model_dump(mode='json')})
    assert [path for path, _ in requests] == ['/items', '/more']
    assert second.records == [{'/id': 1}, {'/id': 2}]
    assert second.completed_partitions == [1, 2]
    assert second.total_partitions == 2
    assert second.metadata.get('resume') is None
    codes = {gap.code for gap in second.gaps}
    assert 'source_snapshot_unverified' in codes
    assert 'source_snapshot_unverified' in {issue['code'] for issue in second.issues}
