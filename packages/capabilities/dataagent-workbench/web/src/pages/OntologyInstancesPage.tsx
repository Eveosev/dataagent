import {useEffect,useMemo,useRef,useState} from 'react';
import {api,display,registryTitle,translateError} from '../client';
import type {RegistryEntry,View} from '../client';
import {
 anchorLocation,browseConceptLabel,browsePropertyLabel,conceptMap,filterOpNames,sourceDisplayName,
} from '../ontologyBrowse';
import type {
 BrowseRegistry,BrowseRegistryEntry,ConceptProperties,InstancePage,PublishedInstance,
 SessionContext,
} from '../ontologyBrowse';
import '../ontology-instances.css';

type Filter={property:string;op:'eq'|'contains';value:string};
type FilterDraft=Filter;

const NO_ITEMS:PublishedInstance[]=[];
const errorText=(error:unknown)=>error instanceof Error?translateError(error.message):String(error);

function contextOf(view:View):SessionContext{
 // 来源名优先取任务里保存的显示名；SQLite 上传把它放在 extensions，
 // 文件上传放在 options。都没有时退回来源定位（显示前已去掉本机路径与 UUID）。
 const names:Record<string,string>={};
 for(const source of view.session?.sources||[]){
  const raw=source.options?.['display_name']
   ??(source.extensions as Record<string,unknown>|null|undefined)?.['dataagent.display_name']
   ??source.locator_ref;
  names[source.source_id]=sourceDisplayName(raw);
 }
 return {
  sources:names,
  concepts:conceptMap(view.ontology),
  revision:String(view.ontology?.revision||''),
 };
}

// D5c：按本体浏览已发布对象。数据只来自 release 指向的冻结快照（D4 接口）；
// 页面不显示实体/发布摘要等内部标识，也不读取本地文件。来源名、概念属性与
// 所属任务从发布该对象的接入任务读取（只读）。
export function OntologyInstancesPage({id,initialConcept,initialRevision,initialHistory,onBack,onNew,onOpenTask}:{
 id:string;initialConcept?:string;initialRevision?:string;initialHistory?:boolean;
 onBack:()=>void;onNew:()=>void;onOpenTask:(sessionId:string)=>void;
}){
 const [entry,setEntry]=useState<BrowseRegistryEntry|null>(null);
 const [registryError,setRegistryError]=useState('');
 const [concept,setConcept]=useState(initialConcept||'');
 const [revision,setRevision]=useState(initialRevision||'');
 const [revisionOther,setRevisionOther]=useState(false),[otherRevision,setOtherRevision]=useState('');
 const [historyOpen,setHistoryOpen]=useState(!!initialHistory);
 const [history,setHistory]=useState<{revision:string;total:number}[]>([]);
 const [historyLoading,setHistoryLoading]=useState(!!initialHistory);
 const [historyError,setHistoryError]=useState('');
 const historyAutoPicked=useRef(false);
 const [pageSize,setPageSize]=useState(10);
 const [cursors,setCursors]=useState<(string|undefined)[]>([undefined]);
 const [filter,setFilter]=useState<Filter|null>(null);
 const [draftFilter,setDraftFilter]=useState<FilterDraft>({property:'',op:'eq',value:''});
 const [page,setPage]=useState<InstancePage|null>(null);
 // 后端游标翻页的 total 是“游标后剩余数”，不是整个筛选结果的总数。
 // 首查（无 cursor）记下总数，后续页继续用它显示“共 N 条”。
 const [totalCount,setTotalCount]=useState<number|null>(null);
 const [contexts,setContexts]=useState<Record<string,SessionContext>>({});
 const [loading,setLoading]=useState(true),[failure,setFailure]=useState('');
 const [refreshToken,setRefreshToken]=useState(0);
 const cursor=cursors[cursors.length-1];

 useEffect(()=>{let cancelled=false;
  (async()=>{
   try{
    const data=await api<BrowseRegistry>('/api/ontologies');
    if(cancelled)return;
    const found=(data.ontologies||[]).find(item=>item.id===id);
    if(!found){setEntry(null);setRegistryError('本体不存在或未注册');return;}
    setRegistryError('');setEntry(found);
   }catch(error){if(!cancelled)setRegistryError(errorText(error));}
  })();
  return()=>{cancelled=true;};
 },[id,refreshToken]);

 // 注册表只给出当前修订；链接里带入的修订与已加载过的修订一并保留，
 // 没有列出的历史修订可在「其他修订」里指定。默认停在当前修订。
 useEffect(()=>{
  if(!entry)return;
  setConcept(current=>{
   if(current&&entry.concepts.includes(current))return current;
   if(initialConcept&&entry.concepts.includes(initialConcept))return initialConcept;
   if(entry.default_concept&&entry.concepts.includes(entry.default_concept))return entry.default_concept;
   return entry.concepts[0]||'';
  });
  setRevision(current=>current||entry.ontology_revision);
 },[entry,initialConcept]);

 useEffect(()=>{
  if(!entry||!concept||!revision){setLoading(false);return;}
  let cancelled=false;
  setLoading(true);setFailure('');
  const params=new URLSearchParams({concept,revision,limit:String(pageSize)});
  if(cursor)params.set('cursor',cursor);
  if(filter)params.set('where',JSON.stringify([{
   property:filter.property,op:filter.op,value:filter.value}]));
  api<InstancePage>(`/api/ontologies/${encodeURIComponent(id)}/instances?${params}`)
   .then(data=>{if(!cancelled){setPage(data);if(!cursor)setTotalCount(data.total);}})
   .catch(error=>{if(!cancelled){setPage(null);setFailure(errorText(error));}})
   .finally(()=>{if(!cancelled)setLoading(false);});
  return()=>{cancelled=true;};
 },[entry,concept,revision,cursor,pageSize,filter,refreshToken,id]);

 // 当前查询对应的页面：切换概念/修订时旧页不展示，避免把上一概念的属性
 // 或对象短暂套到新概念上。
 const visiblePage=page&&page.concept===concept&&page.revision===revision?page:null;
 const items=visiblePage?.items||NO_ITEMS;
 const total=totalCount??visiblePage?.total??0;
 const conceptTotal=entry?.instance_counts?.[concept]??0;
 const currentCounts=entry?.current_revision_instance_counts;
 const conceptCurrent=currentCounts?currentCounts[concept]??0:conceptTotal;
 const conceptHistory=Math.max(0,conceptTotal-conceptCurrent);

 // 来源名与概念属性来自发布对象的任务：任务保存后仍可只读打开。每个任务只读一次。
 useEffect(()=>{
  const pending=[...new Set(items.map(item=>item.session_id).filter(sid=>sid&&!contexts[sid]))];
  if(!pending.length)return;
  let cancelled=false;
  (async()=>{
   const loaded=await Promise.all(pending.map(async sid=>{
    try{return [sid,contextOf(await api<View>(`/api/sessions/${sid}/view`))] as const;}
    catch{return [sid,{sources:{},concepts:{},revision:''}] as const;}
   }));
   if(cancelled)return;
   setContexts(previous=>{
    const next={...previous};
    for(const [sid,context] of loaded)next[sid]=context;
    return next;
   });
  })();
  return()=>{cancelled=true;};
 },[items,contexts]);

 // HTTP 没有历史修订列表；只在需要看历史时，按当前修订号向前探测有实例的
 // 修订。找不到时仍可在“其他修订…”里手填，不把探测当成唯一入口。
 useEffect(()=>{
  if(!historyOpen||!entry||!concept||conceptHistory<=0){
   setHistory([]);setHistoryLoading(false);setHistoryError('');
   return;
  }
  const currentRevision=Number(entry.ontology_revision);
  if(!Number.isInteger(currentRevision)||currentRevision<=1||currentRevision>51){
   setHistory([]);setHistoryLoading(false);
   setHistoryError(currentRevision>51
    ?'修订号跨度过大，请在“其他修订…”中手动输入历史修订号。'
    :'当前修订号无法自动探测，请在“其他修订…”中手动输入历史修订号。');
   return;
  }
  let cancelled=false;
  setHistoryLoading(true);setHistoryError('');
  (async()=>{
   const found:{revision:string;total:number}[]=[];
   for(let value=1;value<currentRevision;value++){
    if(cancelled)return;
    try{
     const params=new URLSearchParams({concept,revision:String(value),limit:'1'});
     const data=await api<InstancePage>(`/api/ontologies/${encodeURIComponent(id)}/instances?${params}`);
     if(data.total>0)found.push({revision:String(value),total:data.total});
    }catch{
     // 该修订号不存在或没有读取权限：跳过，继续探测其他修订。
    }
   }
   if(cancelled)return;
   found.sort((left,right)=>Number(right.revision)-Number(left.revision));
   setHistory(found);setHistoryLoading(false);
   if(initialHistory&&!historyAutoPicked.current){
    historyAutoPicked.current=true;
    if(found.length){
     setRevision(found[0].revision);
     setFilter(null);setDraftFilter({property:'',op:'eq',value:''});
     setCursors([undefined]);setPage(null);
    }
   }
  })();
  return()=>{cancelled=true;};
 },[historyOpen,entry,concept,conceptHistory,id,initialHistory]);

 const conceptDef=useMemo(()=>{
  const selected=visiblePage?.revision;
  for(const context of Object.values(contexts)){
   if(selected&&context.revision&&context.revision!==selected)continue;
   const found=context.concepts[concept];
   if(found)return found as ConceptProperties;
  }
  return undefined;
 },[contexts,concept,visiblePage]);

 const propertyNames=useMemo(()=>{
  const names=Object.keys(conceptDef?.properties||{});
  // 定义可用时只列该概念已定义的属性；任务视图读不到时才退回已发布值，
  // 避免把不同修订/概念里多出来的字段混进列与筛选条件。
  if(!conceptDef)for(const item of items){
   for(const name of Object.keys(item.values||{})){
    if(!names.includes(name))names.push(name);
   }
  }
  return names;
 },[conceptDef,items]);

 const revisions=useMemo(()=>{
  const known=new Set<string>();
  if(entry?.ontology_revision)known.add(entry.ontology_revision);
  if(revision)known.add(revision);
  if(visiblePage?.revision)known.add(visiblePage.revision);
  for(const item of history)known.add(item.revision);
  return [...known].sort((left,right)=>{
   const a=Number(left),b=Number(right);
   return Number.isFinite(a)&&Number.isFinite(b)?b-a:left.localeCompare(right);
  });
 },[entry,revision,visiblePage,history]);

 // 概念切换后不保留上一个概念的筛选条件。
 useEffect(()=>{
  if(!propertyNames.length)return;
  if(draftFilter.property&&!propertyNames.includes(draftFilter.property))
   setDraftFilter({property:'',op:'eq',value:''});
  if(filter&&!propertyNames.includes(filter.property))setFilter(null);
 },[propertyNames,filter,draftFilter.property]);

 function chooseConcept(name:string){
  if(name===concept)return;
  setConcept(name);setCursors([undefined]);setFilter(null);
  setDraftFilter({property:'',op:'eq',value:''});setPage(null);
 }
 function chooseRevision(value:string){
  if(value==='__other__'){setRevisionOther(true);return;}
  setRevisionOther(false);
  if(value===revision)return;
  setRevision(value);setFilter(null);setDraftFilter({property:'',op:'eq',value:''});
  setCursors([undefined]);setPage(null);
 }
 function toggleHistory(){
  if(historyOpen){setHistoryOpen(false);return;}
  setHistoryLoading(true);setHistoryOpen(true);
 }
 function switchOtherRevision(){
  const next=otherRevision.trim();
  if(!next)return;
  setRevisionOther(false);setOtherRevision('');
  if(next===revision)return;
  setRevision(next);setFilter(null);setDraftFilter({property:'',op:'eq',value:''});
  setCursors([undefined]);setPage(null);
 }
 function applyFilter(){
  if(!draftFilter.property||!draftFilter.value.trim())return;
  setFilter({...draftFilter,value:draftFilter.value.trim()});
  setCursors([undefined]);setPage(null);
 }
 function clearFilter(){
  setFilter(null);setDraftFilter({property:'',op:'eq',value:''});
  setCursors([undefined]);setPage(null);
 }
 function changePageSize(value:number){
  setPageSize(value);setCursors([undefined]);setPage(null);
 }
 function refresh(){
  setCursors([undefined]);setPage(null);setRefreshToken(value=>value+1);
 }
 function nextPage(){
  const next=visiblePage?.next_cursor;
  if(!next)return;
  setCursors([...cursors,next]);
 }
 function previousPage(){if(cursors.length>1)setCursors(cursors.slice(0,-1));}

 const retired=entry?.state==='retired'||!!visiblePage?.deactivated;
 const taskName=(item:PublishedInstance)=>item.task||'查看接入任务';
 const sourceName=(item:PublishedInstance,ref?:string)=>{
  if(!ref)return '来源';
  return contexts[item.session_id]?.sources[ref]||'来源';
 };

 function sourceLines(item:PublishedInstance){
  // 同一来源位置的多个属性合并成一行（账簿、单据号 · 文件 · 来源行 N），
  // 避免同一对象重复展示同一段定位。
  const groups:{source:string;location:string;labels:string[]}[]=[];
  const anchorMap=item.source_anchors||{};
  const properties=[...new Set([...Object.keys(anchorMap),
   ...(item.locations||[]).map(location=>location.property)])];
  for(const property of properties){
   if(!propertyNames.includes(property))continue;
   const anchors=anchorMap[property]?.length
    ?anchorMap[property]
    :(item.locations||[]).filter(location=>location.property===property);
   for(const anchor of anchors){
    const located=anchorLocation(anchor);
    if(!located)continue;
    const source=sourceName(item,anchor.source_ref);
    const label=browsePropertyLabel(property);
    const group=groups.find(entry=>entry.source===source&&entry.location===located);
    if(group){if(!group.labels.includes(label))group.labels.push(label);}
    else groups.push({source,location:located,labels:[label]});
   }
  }
  return groups.length
   ?groups.map(group=><div key={`${group.source}:${group.location}`} className="instance-anchor">
    {group.labels.join('、')} · {group.source} · {group.location}</div>)
   :<span className="muted">无来源定位</span>;
 }

 function emptyState(){
  if(filter)return <div className="empty ontology-instance-empty" data-testid="instances-empty-filtered">
   <strong>没有符合筛选条件的实例</strong>
   <p>已发布实例仍在，清除筛选即可查看全部。</p>
   <button className="secondary" onClick={clearFilter}>清除筛选</button>
  </div>;
  return <div className="empty ontology-instance-empty" data-testid="instances-empty">
   <strong>{entry&&entry.concepts.length>1?`概念 ${concept} 还没有已发布实例`:'这个本体还没有已发布实例'}</strong>
   <p>发布后才会出现；未发布的预览不会显示在这里。</p>
   <button className="primary" onClick={onNew}>新建接入</button>
  </div>;
 }

 return <main className="workspace ontology-page ontology-instances-page">
  <header className="task-header">
   <div><div className="eyebrow">本体库 / 已发布对象</div>
    <h1>{entry?registryTitle(entry):'已发布对象'}</h1>
    <p className="muted">只读浏览已发布快照；来源定位、所属接入任务与发布修订随对象固定。</p></div>
   <div className="save-buttons">
    <button className="secondary" onClick={onBack}>返回本体库</button>
    <button className="secondary" disabled={loading} onClick={refresh}>刷新</button>
   </div>
  </header>
  {registryError&&<div className="notice red" data-testid="instances-failure" role="alert">{registryError}</div>}
  {!entry&&!registryError&&<div className="empty">正在读取本体…</div>}
  {entry&&<>
   {retired&&<div className="notice amber" data-testid="instances-retired">
    <strong>该本体已停用</strong>
    <p>停用只影响新任务的默认选择；已发布修订与实例保留，仍可只读浏览。
     {entry.retire_reason?`停用原因：${entry.retire_reason}`:''}</p>
   </div>}
   <nav className="instance-controls" aria-label="已发布对象浏览条件">
    {entry.concepts.length>1
     ?<div className="concept-tabs" role="group" aria-label="按概念切换">
      {entry.concepts.map(name=><button key={name} data-testid={`concept-tab-${name}`}
       className={name===concept?'concept-tab active':'concept-tab'}
       aria-pressed={name===concept} onClick={()=>chooseConcept(name)}>{name}</button>)}
     </div>
     :entry.concepts[0]&&<span className="badge">概念 {entry.concepts[0]}</span>}
    <div className="instance-control-row">
     <div className="instance-control">
      <label className="label" htmlFor="instance-revision">修订</label>
      <select id="instance-revision" value={revisionOther?'__other__':revision}
       onChange={event=>chooseRevision(event.target.value)}>
       {revisions.map(name=><option key={name} value={name}>
        修订 {name}{name===entry.ontology_revision?'（当前）':''}</option>)}
       <option value="__other__">其他修订…</option>
      </select>
     </div>
     {revisionOther&&<div className="instance-control revision-other">
      <label className="label" htmlFor="other-revision">历史版本号</label>
      <div className="revision-other-row">
       <input id="other-revision" value={otherRevision} placeholder="例如 2"
        onChange={event=>setOtherRevision(event.target.value)}
        onKeyDown={event=>{if(event.key==='Enter')switchOtherRevision();}}/>
       <button className="secondary" disabled={!otherRevision.trim()} onClick={switchOtherRevision}>切换</button>
      </div>
     </div>}
     {conceptHistory>0&&<div className="instance-control history-control">
      <span className="label">历史修订</span>
      <button className="secondary" data-testid="instance-history-toggle" onClick={toggleHistory}>
       {historyOpen?'收起历史修订':`查看历史（${conceptHistory} 个）`}</button>
     </div>}
     <div className="instance-control page-size">
      <label className="label" htmlFor="instance-page-size">每页条数</label>
      <select id="instance-page-size" value={pageSize}
       onChange={event=>changePageSize(Number(event.target.value))}>
       <option value={10}>10</option><option value={25}>25</option><option value={50}>50</option>
      </select>
     </div>
    </div>
    {historyOpen&&<div className="instance-history" data-testid="instance-history">
     <div className="instance-history-title"><strong>历史修订中的实例</strong>
      <span className="muted">当前修订 {entry.ontology_revision} 中该概念 {conceptCurrent} 个；历史累计 {conceptHistory} 个。</span></div>
     {historyLoading?<div className="muted">正在查找有实例的历史修订…</div>:
      history.length?<div className="history-options">
       {history.map(item=><button key={item.revision}
        className={item.revision===revision?'history-option active':'history-option'}
        onClick={()=>chooseRevision(item.revision)}>修订 {item.revision} · {item.total} 条</button>)}
      </div>:
      <div className="muted">{historyError||'没有找到有实例的历史修订；可在上方“其他修订…”中手动输入。'}</div>}
    </div>}
    {propertyNames.length>0&&<div className="instance-filter" data-testid="instance-filter">
     <div className="instance-control">
      <label className="label" htmlFor="filter-property">属性</label>
      <select id="filter-property" value={draftFilter.property}
       onChange={event=>setDraftFilter({...draftFilter,property:event.target.value})}>
       <option value="">选择属性</option>
       {propertyNames.map(name=><option key={name} value={name}>{browsePropertyLabel(name)}</option>)}
      </select>
     </div>
     <div className="instance-control">
      <label className="label" htmlFor="filter-op">条件</label>
      <select id="filter-op" value={draftFilter.op}
       onChange={event=>setDraftFilter({...draftFilter,op:event.target.value as 'eq'|'contains'})}>
       <option value="eq">等于</option><option value="contains">包含</option>
      </select>
     </div>
     <div className="instance-control filter-value">
      <label className="label" htmlFor="filter-value">值</label>
      <input id="filter-value" value={draftFilter.value} placeholder="输入要匹配的值"
       onChange={event=>setDraftFilter({...draftFilter,value:event.target.value})}
       onKeyDown={event=>{if(event.key==='Enter')applyFilter();}}/>
     </div>
     <div className="filter-actions">
      <button className="primary" disabled={!draftFilter.property||!draftFilter.value.trim()}
       onClick={applyFilter}>筛选</button>
      {filter&&<button className="secondary" onClick={clearFilter}>清除筛选</button>}
     </div>
    </div>}
    {filter&&<p className="help instance-filter-summary" data-testid="instance-filter-summary">
     当前筛选：{browsePropertyLabel(filter.property)} {filterOpNames[filter.op]} {filter.value}
    </p>}
   </nav>
   {failure&&<div className="notice red" data-testid="instances-failure" role="alert">{failure}</div>}
   {loading?<div className="empty" data-testid="instances-loading">正在读取已发布实例…</div>:
    !visiblePage?(!failure&&emptyState()):
    visiblePage.items.length===0?emptyState():
    <section className="discovery-card instance-card">
     <div className="panel-heading"><strong>{browseConceptLabel(concept)} 的已发布对象</strong>
      <span className="badge">{total} 条</span></div>
     <div className="mapping-table-scroll"><table className="mapping-table instance-table" data-testid="instance-table">
      <thead><tr>
       {propertyNames.map(name=><th key={name}>{browsePropertyLabel(name)}</th>)}
       <th>来源定位</th><th>所属接入任务</th><th>发布修订</th>
      </tr></thead>
      <tbody>{visiblePage.items.map((item,index)=><tr key={`${item.release_ref}:${index}`} data-testid="instance-row">
       {propertyNames.map(name=><td key={name} data-testid={`instance-value-${name}`}>{display(item.values?.[name])}</td>)}
       <td className="instance-source" data-testid="instance-source">{sourceLines(item)}</td>
       <td data-testid="instance-task">{item.session_id
        ?<button type="button" className="instance-task-link" title="打开该接入任务的对象页（只读）"
          onClick={()=>onOpenTask(item.session_id)}>{taskName(item)}</button>
        :<span className="muted">未知</span>}</td>
       <td data-testid="instance-revision"><span className="badge">修订 {item.revision}</span>
        {item.partial_release&&<small className="warn">部分发布</small>}</td>
      </tr>)}</tbody>
     </table></div>
     <div className="instance-pagination">
      <span className="muted">第 {cursors.length} 页 · 共 {total} 条</span>
      <div>
       <button className="secondary" disabled={cursors.length<=1} onClick={previousPage}>上一页</button>
       <button className="secondary" disabled={!visiblePage.has_more} onClick={nextPage}>下一页</button>
      </div>
     </div>
    </section>}
  </>}
 </main>;
}
