"""Bounded REST discovery with per-response evidence and explicit pagination gaps."""
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.error import URLError
from dataagent_contracts.core.refs import SourceAnchor
from dataagent_contracts.intake import SourceProfile, CoverageGap
from ..adapters.sources.base import snapshot, digest, typed_key
from ..adapters.sources.rest import origin, approved, auth_headers, fetch


_MISSING=object()
RETRYABLE_GAPS = {'connection_failed', 'rate_limited', 'http_error'}
# JSON Pointers restart at ``/items/0`` on every page, so the pointer alone
# cannot tell two pages apart.  The 1-based response page rides in the
# selector's contract-provided ``extensions`` map; anchors written before
# this key existed remain valid and resolve through ``pointer`` unchanged.
PAGE_EXTENSION = 'dataagent.page'


def pointer(document, path):
    if not isinstance(path,str) or (path and not path.startswith('/')): raise ValueError('JSON pointer must be empty or begin with /')
    value=document
    try:
        for token in path.split('/')[1:]:
            token=token.replace('~1','/').replace('~0','~')
            value=value[int(token)] if isinstance(value,list) else value[token]
    except (KeyError,IndexError,ValueError,TypeError): return _MISSING
    return value


def flatten(record):
    fields={}
    def walk(value,path):
        if isinstance(value,dict) and value:
            for key,item in value.items(): walk(item,path+'/'+str(key).replace('~','~0').replace('/','~1'))
        else: fields[path or '']=value
    walk(record,'')
    return fields


def resume_rest(selection, previous, ctx, **kwargs):
    if (previous.source_id != selection.source_id or previous.kind != 'rest'
            or previous.coverage != 'partial' or previous.metadata.get('row_offset') != 0
            or previous.metadata.get('source_version') is None
            or not previous.metadata.get('cursor')
            or not all(gap.code in RETRYABLE_GAPS for gap in previous.gaps)):
        raise ValueError('no verifiable REST checkpoint; select the source in a new intake')
    return probe_rest(selection, ctx, previous=previous, **kwargs)


def probe_rest(selection, ctx, *, workspace, budget_rows=200, credentials=None, allowed_origins=None, previous=None):
    if selection.kind!='rest' or isinstance(budget_rows,bool) or not isinstance(budget_rows,int) or not 1<=budget_rows<=10000:
        raise ValueError('REST source and row budget 1..10000 required')
    if not allowed_origins: raise PermissionError('REST requires a host configured origin allowlist')
    allowed={origin(value) for value in allowed_origins};approved(selection.locator_ref,allowed)
    connection_revision = digest([selection.locator_ref, selection.options, selection.requested_scope, sorted(allowed)])
    if previous is not None and previous.metadata.get('connection_revision') != connection_revision:
        raise ValueError('configured source scope changed; select the source in a new intake')
    headers=auth_headers(credentials)
    options=selection.options;records_path=options.get('records_path','');pagination=options.get('pagination',{})
    if not isinstance(pagination,dict) or set(pagination)-{'next_path','cursor_path','cursor_param'}:
        raise ValueError('unsupported pagination; configure next_path or cursor_path/cursor_param')
    if 'next_path' in pagination and 'cursor_path' in pagination: raise ValueError('configure only one pagination mode')
    if 'cursor_path' in pagination and not isinstance(pagination.get('cursor_param'),str): raise ValueError('cursor_param is required')
    for path in [records_path,pagination.get('next_path',''),pagination.get('cursor_path',''),options.get('source_version_path','')]:
        pointer({},path)
    key_fields=options.get('keys',[])
    if not isinstance(key_fields,list) or any(not isinstance(key,str) for key in key_fields): raise ValueError('keys must be a list of fields')
    # Resume references may narrow a host-approved source, never grant a new origin.
    current=previous.metadata['cursor'] if previous else selection.requested_scope.get('cursor',selection.locator_ref)
    offset=previous.metadata['row_offset'] if previous else selection.requested_scope.get('row_offset',0)
    if isinstance(offset,bool) or not isinstance(offset,int) or offset<0: raise ValueError('row_offset must be nonnegative')
    approved(current,allowed)
    expected_version=previous.metadata['source_version'] if previous else selection.requested_scope.get('source_version')
    records=[];anchors={};pages=[];completed=[];issues=[];gaps=[];record_keys=[];seen=set();sampled=False;terminal=False;cursor=current;row_offset=offset
    if previous is not None:
        records=list(previous.records);anchors=dict(previous.anchors)
        pages=list(previous.metadata['pages']);completed=list(previous.completed_partitions)
        record_keys=list(previous.metadata['record_keys'])
        issues=[issue for issue in previous.issues if issue['code'] not in RETRYABLE_GAPS]
        seen={page['endpoint'] for page in pages}
    def issue(code,partition,**details):
        issues.append({'code':code,'partition':partition,**details});gaps.append(CoverageGap(partition=partition,code=code))
    for page_number in range(len(pages)+1,101):
        cursor=current
        try: approved(current,allowed)
        except (PermissionError,ValueError): issue('origin_not_allowed',page_number);break
        if current in seen: issue('pagination_cycle',page_number);break
        seen.add(current)
        try: status,payload,response_metadata=fetch(current,headers)
        except (OSError,URLError,TimeoutError): issue('connection_failed',page_number);break
        if 300<=status<400: issue('redirect_refused',page_number);break
        if status==429: issue('rate_limited',page_number,retry_after=response_metadata.get('retry_after'));break
        if status!=200: issue('http_error',page_number,status=status);break
        if 'error' in response_metadata: issue(response_metadata['error'],page_number);break
        version=pointer(payload,options['source_version_path']) if options.get('source_version_path') else response_metadata.get('source_version')
        if version is _MISSING: version=None;issue('source_version_missing',page_number)
        if (pages or expected_version is not None) and version != expected_version:
            issue('source_version_drift',page_number);break
        expected_version=version
        revision,ref=snapshot(workspace,payload)
        page={'number':page_number,'endpoint':current,'snapshot_ref':ref,'response_revision':revision,**response_metadata}
        pages.append(page)
        selected=pointer(payload,records_path)
        if selected is _MISSING or not isinstance(selected,(list,dict)):
            issue('records_path_invalid',page_number);break
        raw=selected if isinstance(selected,list) else [selected]
        if offset>len(raw): issue('resume_offset_invalid',page_number);break
        start=offset;offset=0;remaining=budget_rows-len(records);chosen=raw[start:start+remaining]
        for local_index,record in enumerate(chosen,start):
            if not isinstance(record,dict): issue('record_not_object',page_number,row=local_index);continue
            flat=flatten(record);index=len(records);records.append(flat)
            identity=[]
            for key in key_fields:
                value=pointer(record,key) if key.startswith('/') else record.get(key,_MISSING)
                if value is _MISSING or value is None: issue('key_missing',page_number,field=key,row=local_index)
                else: identity.append(typed_key(key,value))
            record_keys.append({'keys':identity,'page':page_number,'row':local_index})
            record_path=records_path+(f'/{local_index}' if isinstance(selected,list) else '')
            for field in flat:
                anchors[f'{index}.{field}']=[SourceAnchor(source_ref=selection.source_id,source_revision=revision,extraction_ref=ref,
                    selector={'kind':'json_pointer','pointer':record_path+field,
                        'extensions':{PAGE_EXTENSION:page_number}})]
        page['rows_observed']=len(chosen)
        if len(raw)-start>remaining:
            sampled=True;row_offset=start+remaining;break
        completed.append(page_number);row_offset=0
        if not pagination:
            terminal=True;cursor=None;break
        next_path=pagination.get('next_path',pagination.get('cursor_path'))
        if next_path is None: issue('pagination_incomplete',page_number);break
        next_value=pointer(payload,next_path)
        if next_value is _MISSING: issue('pagination_incomplete',page_number);break
        if next_value is None or next_value=='': terminal=True;cursor=None;break
        if 'next_path' in pagination:
            if not isinstance(next_value,str): issue('pagination_invalid',page_number);break
            current=urljoin(current,next_value)
        else:
            if not isinstance(next_value,(str,int)) or isinstance(next_value,bool): issue('pagination_invalid',page_number);break
            parsed=urlsplit(selection.locator_ref);param=pagination['cursor_param']
            query=[(key,value) for key,value in parse_qsl(parsed.query) if key!=param]+[(param,str(next_value))]
            current=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(query),''))
        cursor=current
        if len(records)>=budget_rows: sampled=True;break
    else: issue('page_budget_exceeded',101)
    # Missing global versions remain explicit: response hashes identify exactly the evidence read,
    # but do not promise a consistent snapshot across mutable remote pages.
    if len(pages)>1 and expected_version is None:
        issue('source_snapshot_unverified', 'pagination')
    revision='sha256:'+digest({'pages':[{k:v for k,v in page.items() if k in {'endpoint','response_revision'}} for page in pages],'scope':selection.requested_scope})
    fields=list(dict.fromkeys(k for row in records for k in row))
    shape={field:sorted({type(row[field]).__name__ for row in records if field in row and row[field] is not None}) for field in fields}
    return SourceProfile(source_id=selection.source_id,source_revision=revision,kind='rest',records=records,fields=fields,anchors=anchors,
        total_partitions=len(pages) if terminal else None,completed_partitions=completed,gaps=gaps,issues=issues,sampled=sampled,
        metadata={'pages':pages,'record_keys':record_keys,'records_path':records_path,'cursor':cursor,'row_offset':row_offset,'source_version':expected_version,
            'connection_revision':connection_revision,
            'completeness':'partial' if gaps else 'sampled' if sampled else 'full' if terminal else 'unknown',
            'structure_fingerprint':digest({'records_path':records_path,'fields':shape}),'statistics_scope':'observed_rows','extractor_version':'dataagent-rest-probe@1'})
