import {useEffect,useRef,useState} from 'react';
import {api,ApiError,display,transformNames,propertyLabel,sourceProblem,issueReasons,conceptOf,conceptLabel,builtinTitles,ontologyTitles} from '../client';
import type {View,Draft,FieldBinding,IntakeSession,MappingSpec,SourceProfile,CorrectionView,DispositionOption,Issue} from '../client';
import {SourceViewer} from '../components/SourceViewer';
import {DiscoveryPage} from './DiscoveryPage';
import {MappingDetail} from '../components/MappingDetail';

function savedMappings(view:View){
 return (view.preview?.extensions?.['intake.source_mappings']||{}) as Record<string,MappingSpec>;
}

// 默认绑定按任务固定概念的属性名与来源字段同名匹配（多概念本体不再读全局旧字段）。
// 来源把同一业务字段拆成最小单位（amount_minor/amount_cents）时，默认按
// minor_to_major 绑定；否则对象页会把它当成未映射字段，既没有金额值也没有
// 来源定位。同名精确列优先，不会被最小单位列覆盖。
function defaultBindings(view:View,sourceId:string):Record<string,FieldBinding>{
 const profile=view.profiles.find(p=>p.source_id===sourceId);
 const properties=conceptOf(view.ontology,view.ontology_concept).properties;
 const fields=profile?.fields||[];
 const bindings:Record<string,FieldBinding>={};
 for(const name of Object.keys(properties)){
  if(fields.includes(name))bindings[name]={source_field:name,transform:'identity'};
 }
 for(const name of Object.keys(properties)){
  if(bindings[name])continue;
  for(const suffix of ['_minor','_cents']){
   const field=`${name}${suffix}`;
   if(fields.includes(field)){bindings[name]={source_field:field,transform:'minor_to_major'};break;}
  }
 }
 return bindings;
}

// FDE2-05：已固定的映射来源范围（提案写进 selected_versions 的 mapping:<来源>）。
// 重新生成预览沿用这个范围，而不是把任务里所有来源都自动映射进去；被整源处置
// （本任务不使用该来源）的来源不再纳入。
function scopedSourceIds(view:View):Set<string>{
 const ignored=new Set((view.dispositions||[]).filter(entry=>entry.action==='ignore_source').map(entry=>entry.source_id));
 const scoped=new Set<string>();
 for(const key of Object.keys(view.session.selected_versions||{}))
  if(key.startsWith('mapping:'))scoped.add(key.slice('mapping:'.length));
 for(const id of ignored)scoped.delete(id);
 return scoped;
}

// 用户是否改过该来源的绑定（与同名默认绑定比较）：改过说明是有意纳入，
// 未改过的未映射来源保持「该来源未用于当前映射」。
function bindingsEdited(view:View,sourceId:string,sourceBindings:Record<string,Record<string,FieldBinding>>):boolean{
 const current=sourceBindings[sourceId];
 if(!current)return false;
 const defaults=defaultBindings(view,sourceId);
 const keys=new Set([...Object.keys(current),...Object.keys(defaults)]);
 if(keys.size!==Object.keys(current).length||keys.size!==Object.keys(defaults).length)return true;
 const same=(a:FieldBinding|undefined,b:FieldBinding|undefined)=>(!a&&!b)||(!!a&&!!b
  &&(a.source_field??'')===(b.source_field??'')&&(a.transform??'identity')===(b.transform??'identity'));
 for(const key of keys)if(!same(current[key],defaults[key]))return true;
 return false;
}

// 最新提案写入的来源范围签名。范围变化（例如代理缩窄）时，旧草稿里的绑定
// 不能再把来源加回来；只有本次页面里新做的绑定编辑才算显式纳入。
function mappingScopeKey(view:View):string{
 return Object.entries(view.session.selected_versions||{})
  .filter(([key])=>key.startsWith('mapping:'))
  .sort(([a],[b])=>a.localeCompare(b))
  .map(([key,value])=>`${key}=${value}`).join('|');
}

function sourceInScope(view:View,sourceId:string,sourceBindings:Record<string,Record<string,FieldBinding>>,
 editedSources:Set<string>,includedSources:Set<string>):boolean{
 if((view.dispositions||[]).some(entry=>entry.action==='ignore_source'&&entry.source_id===sourceId))return false;
 const scoped=scopedSourceIds(view);
 if(!scoped.size)return true; // 尚无任何提案固定范围：保持全部来源一起提案。
 // 用户点过「纳入映射」就是显式选择：即使绑定仍是同名默认值也要提案，
 // 否则默认绑定正确的来源永远无法回到映射范围（FDE2-05）。
 return scoped.has(sourceId)||includedSources.has(sourceId)
  ||(editedSources.has(sourceId)&&bindingsEdited(view,sourceId,sourceBindings));
}

export function MappingPage({sessionId,onNew,onError,onOpenObjects,onOpenSession,onOpenOntologies}:{sessionId:string;onNew:()=>void;onError:(e:unknown)=>void;onOpenObjects?:()=>void;onOpenSession:(id:string)=>void;onOpenOntologies?:()=>void}){
 const [view,setView]=useState<View|null>(null),[bindings,setBindings]=useState<Record<string,FieldBinding>>({});
 const editedSources=useRef<Set<string>>(new Set()),scopeKey=useRef('');
 const [field,setField]=useState(''),[sourceId,setSourceId]=useState(''),[record,setRecord]=useState(0),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[onlyProblems,setOnlyProblems]=useState(false),[draftState,setDraftState]=useState('');
 // FDE-12：字段详情里的纠正同样给绿色成功提示；被其他问题挡住时点名，不走红色错误条。
 const [correctionNotice,setCorrectionNotice]=useState<{kind:'green'|'amber';text:string}|null>(null);
 // 面包屑用的本体名：任务目标本体的注册表标题（FDE2-11）。
 const [ontologyName,setOntologyName]=useState('');
 // FDE2-05：未映射来源的整源处置（本任务不使用该来源），原因必填、写入审计。
 const [disposalReasons,setDisposalReasons]=useState<Record<string,string>>({});
 // 用户显式勾选的来源范围（「纳入映射」）：与绑定是否被改过无关，沿用默认
 // 绑定也能重新提案；提案范围变化后清空，由最新提案重新固定范围。
 const [includedSources,setIncludedSources]=useState<Set<string>>(()=>new Set());
 const includedSourcesRef=useRef<Set<string>>(new Set());
 const revision=useRef(''),initialized=useRef(false),dirtyRef=useRef(false),queue=useRef(Promise.resolve()),draftError=useRef<unknown>(null),bindingsRef=useRef<Record<string,FieldBinding>>({});
 const sourceBindings=useRef<Record<string,Record<string,FieldBinding>>>({}),selectedSource=useRef(''),viewRef=useRef<View|null>(null);
 const base=`/api/sessions/${sessionId}`;const localKey=`dataagent-draft:${sessionId}`;
 async function load(reset=false){
  const data=await api<View>(base+'/view');
  if(Number(data.session.revision)<Number(revision.current))return;
  setView(data);viewRef.current=data;
  const nextScope=mappingScopeKey(data);
  if(nextScope!==scopeKey.current){
   scopeKey.current=nextScope;editedSources.current.clear();
   // 新提案重新固定来源范围；旧的「纳入映射」点击不能把被缩窄掉的来源
   // 又加回来（与 editedSources 同一处理）。
   includedSourcesRef.current=new Set();setIncludedSources(new Set());
  }
  if(dirtyRef.current&&!reset)return;
  revision.current=data.session.revision;
  if(data.discovery)return;
  if(reset){
   sessionStorage.removeItem(localKey);setDirty(false);dirtyRef.current=false;draftError.current=null;setDraftState('');
   editedSources.current.clear();
  }
  let local:Draft|undefined;
  const pending=sessionStorage.getItem(localKey);
  if(!initialized.current&&pending&&data.session.phase!=='saved'){
   try{
    const saved=JSON.parse(pending) as {revision:string;draft:Draft};
    local=saved.draft;
    if(local){
     dirtyRef.current=true;setDirty(true);setDraftState('本地编辑已恢复');
     if(saved.revision!==data.session.revision){
      draftError.current=new Error('任务已有更新，请重新载入并核对本地编辑。');
      setDraftState('编辑已保留，任务有更新');
     }
    }
   }catch{sessionStorage.removeItem(localKey);}
  }
  const multiple=data.session.sources.length>1;
  if(multiple){
   const mappings=savedMappings(data);
   sourceBindings.current=Object.fromEntries(data.profiles.map(p=>[p.source_id,
    local?.source_bindings?.[p.source_id]||data.draft.source_bindings?.[p.source_id]||
    mappings[p.source_id]?.bindings||data.mappings?.[p.source_id]?.bindings||
    defaultBindings(data,p.source_id)]));
   const id=selectedSource.current||local?.source_id||data.draft.source_id||data.profiles[0]?.source_id||'';
   const chosen=sourceBindings.current[id]||{};
   selectedSource.current=id;setSourceId(id);setBindings(chosen);bindingsRef.current=chosen;
   setField(current=>current||data.draft.selected_field||Object.keys(conceptOf(data.ontology,data.ontology_concept).properties)[0]||'');
   initialized.current=!!data.profiles.length;
  }else{
   const profile=data.profiles[0];const exact=defaultBindings(data,profile?.source_id||'');
   const chosen=local?.bindings||data.draft.bindings||data.preview?.mapping.bindings||exact;
   setBindings(chosen);bindingsRef.current=chosen;
   if(!initialized.current||reset){
    setField(local?.selected_field||data.draft.selected_field||Object.keys(conceptOf(data.ontology,data.ontology_concept).properties)[0]||'');
    setSourceId(data.draft.source_id||profile?.source_id||'');setRecord(data.draft.record_index||0);initialized.current=!!profile;
   }
  }
 }
 useEffect(()=>{load().catch(onError);const timer=setInterval(()=>load().catch(onError),1500);return()=>clearInterval(timer);},[sessionId]);
 // 面包屑用任务目标本体的注册表标题（FDE2-11），一次拉取后缓存复用。
 const targetOntologyId=view?.ontology.id;
 useEffect(()=>{
  let cancelled=false;
  if(targetOntologyId)ontologyTitles().then(titles=>{if(!cancelled)setOntologyName(titles[targetOntologyId]||'');});
  return()=>{cancelled=true;};
 },[targetOntologyId]);
 const profile=sourceId?view?.profiles.find(p=>p.source_id===sourceId):view?.profiles[0];
 const multiple=(view?.session.sources.length||0)>1;
 function selectSource(id:string){
  selectedSource.current=id;setSourceId(id);setRecord(0);
  if(multiple){const next=sourceBindings.current[id]||{};setBindings(next);bindingsRef.current=next;}
 }
 // 未映射来源的中文名：优先用户选择的显示名，退回文件名，最后才是内部来源 ID。
 function sourceLabel(id:string){
  const selection=view?.session.sources.find(source=>source.source_id===id) as
   {options?:{display_name?:string};locator_ref?:string}|undefined;
  return String(selection?.options?.display_name
   ||selection?.locator_ref?.split('/').pop()||id);
 }
 // 显式纳入一个未映射来源：沿用当前（未改过的默认）绑定，下一次「生成映射预览」
 // 会把它一起提交；不再要求用户先改一个字段才能证明想用这份材料。
 function includeSource(id:string){
  const next=new Set(includedSourcesRef.current);next.add(id);
  includedSourcesRef.current=next;setIncludedSources(next);
  setCorrectionNotice({kind:'amber',
   text:`已将「${sourceLabel(id)}」纳入映射范围，沿用当前绑定（默认同名绑定可直接使用）；请点击「生成映射预览」重新提案。`});
 }
 function draft(next:Record<string,FieldBinding>,selected=field){
  setDraftState('正在保存草稿…');
  if(multiple)sourceBindings.current={...sourceBindings.current,[sourceId]:next};
  // 草稿只保存范围内来源的绑定：范围外的来源保持未映射，保存时的草稿比对
  // 也不会把它们当作待提交的映射（FDE2-05）。
  const inScope=(id:string)=>!viewRef.current||!multiple||sourceInScope(viewRef.current,id,sourceBindings.current,editedSources.current,includedSourcesRef.current);
  const draftData={...(multiple?{source_bindings:Object.fromEntries(Object.entries(sourceBindings.current).filter(([id])=>inScope(id)))}:{bindings:next}),
   selected_field:selected,source_id:sourceId,record_index:record};
  const pending=JSON.stringify({revision:revision.current,draft:draftData});
  sessionStorage.setItem(localKey,pending);
  queue.current=queue.current.then(async()=>{
   if(draftError.current)throw draftError.current;
   const session=await api<IntakeSession>(base+'/draft','PUT',{expected_revision:revision.current,draft:draftData});
   revision.current=session.revision;setView(v=>v?{...v,session}:v);setDraftState('草稿已保存');
   if(sessionStorage.getItem(localKey)===pending)sessionStorage.removeItem(localKey);
  }).catch(error=>{draftError.current=error;setDraftState('编辑已保留，任务有更新');onError(error);});
 }
 function change(target:string,binding:FieldBinding){const next={...bindingsRef.current,[target]:binding};if(!binding.source_field)delete next[target];bindingsRef.current=next;setBindings(next);setField(target);setDirty(true);dirtyRef.current=true;if(multiple)editedSources.current.add(sourceId);draft(next,target);}
 async function preview(){
  setBusy(true);try{
   await queue.current;if(draftError.current)throw draftError.current;
   if(!profile||!view)throw new Error('来源尚未探查');
   const loaded=viewRef.current||view;
   function propose(source:SourceProfile,fields:Record<string,FieldBinding>,prior?:MappingSpec):MappingSpec{
    const used=new Set(Object.values(fields).map(b=>b.source_field));
    return {...prior,id:'candidate',revision:'1',ontology_revision:`${loaded.ontology.id}@${loaded.ontology.revision}`,
     // 多概念本体必须点名任务固定的概念，服务端会拒绝概念外的提案。
     concept:conceptOf(loaded.ontology,loaded.ontology_concept).name,
     source_fingerprint:String(source.metadata?.structure_fingerprint),bindings:fields,
     unmapped:Object.fromEntries((source.fields||[]).filter(f=>!used.has(f)).map(f=>[f,'extension']))};
   }
   if(multiple){
    // FDE2-05：只提交范围内的来源（Agent 已映射的 + 用户改过绑定的），
    // 未映射来源保持来源级问题，而不是自动映射后逐行报错。
    const existing=savedMappings(loaded);
    const proposals=Object.fromEntries(loaded.profiles
     .filter(source=>sourceInScope(loaded,source.source_id,sourceBindings.current,editedSources.current,includedSourcesRef.current))
     .map(source=>[source.source_id,
      propose(source,sourceBindings.current[source.source_id]||defaultBindings(loaded,source.source_id),existing[source.source_id])]));
    if(!Object.keys(proposals).length)throw new Error('没有可映射的来源，请先绑定至少一个来源');
    await api(base+'/source-proposals','POST',{proposals,expected_revision:revision.current});
   }else{
    const proposal=propose(profile,bindingsRef.current,loaded.preview?.mapping);
    await api(base+'/proposal','POST',{proposal,expected_revision:revision.current});
   }
   setDirty(false);dirtyRef.current=false;sessionStorage.removeItem(localKey);await load();
  }catch(error){onError(error);}finally{setBusy(false);}
 }
 async function review(target_scope:string,changes:Record<string,unknown>={}){
  await queue.current;if(draftError.current)throw draftError.current;if(!view?.preview)throw new Error('请先生成映射预览');
  await api(base+'/review','POST',{expected_revision:revision.current,decision:{preview_ref:`${view.preview.id}@${view.preview.revision}`,target_scope,changes,decision:'save'}});
  await load();
 }
 async function save(){setBusy(true);try{await review('mapping');}catch(error){onError(error);}finally{setBusy(false);}}
 async function correct(value:string,reason:string){
  try{
   const instance=view?.preview?.instances?.[record];if(!instance)throw new Error('请选择对象');
   await review('instance',{entity_id:instance.id,property:field,value,reason});
   try{
    await api(base+'/revalidate','POST',{expected_revision:revision.current});await load();
    setCorrectionNotice({kind:'green',text:`纠正已保存：${propertyLabel(field)} → ${value}，已重新校验。`});
   }catch(error){
    if(error instanceof ApiError&&error.status===409)throw error;
    // 重新校验被其他对象挡住：点名到待核对清单，不用红色错误条（FDE-12）。
    await load().catch(()=>{});
    setCorrectionNotice({kind:'amber',text:`纠正已保存：${propertyLabel(field)} → ${value}。整批保存仍被其他问题挡住，见下方待核对清单。`});
   }
  }catch(error){onError(error);}
 }
 async function adopt(correction:CorrectionView){
  try{
   await api(base+'/corrections/adopt','POST',{expected_revision:revision.current,
    entity_id:correction.entity_id,property:correction.property});
   await load();
  }catch(error){onError(error);}
 }
 // FDE2-05：整源处置（本任务不使用该来源）走真实后端，原因必填、写入审计。
 async function submitDisposal(option:DispositionOption,why:string){
  // Keep the regenerate button disabled until the new revision is loaded;
  // otherwise a quick click can send the pre-disposition revision and 409.
  setBusy(true);
  try{
   await api(base+'/dispositions','POST',{expected_revision:revision.current,
    action:option.action,source_id:option.source_id,
    ...(option.scope==='source'?{}:option.action==='partition_not_applicable'
     ?{partition:option.partition}:{record:option.record}),
    reason:why});
   setDisposalReasons(previous=>({...previous,[`${option.action}:${option.source_id}`]:''}));
   setCorrectionNotice({kind:'green',text:'处置已记录。请重新生成映射预览后核对。'});
   await load();
  }catch(error){onError(error);}
  finally{setBusy(false);}
 }
 if(!view)return <main className="loading">正在恢复任务…</main>;
 if(view.discovery)return <DiscoveryPage view={view} reload={load} onNew={onNew} onError={onError} onOpenSession={onOpenSession} onOpenOntologies={onOpenOntologies}/>;
 const phase=view.session.phase,done=phase==='saved',working=phase==='queued'||phase==='probing';
 const canRetry=view.session.next_actions?.includes('retry_probe');
 // FDE-10：任一来源探查失败时进度标红，副标题不再宣称「识别与探查已完成」。
 const failed=(view.profiles||[]).some(p=>!!sourceProblem(p))
  ||(view.session.issues||[]).some(i=>String((i as Record<string,unknown>).code)==='intake.probe_failed');
 const instance=view.preview?.instances?.[record];const binding=bindings[field];
 const proof=instance?.source_anchors?.[field]?.filter(a=>a.source_ref===profile?.source_id)||[];
 const direct=Object.entries(profile?.anchors||{}).find(([key,anchors])=>
  key.endsWith('.'+binding?.source_field)&&anchors.some(anchor=>proof.some(candidate=>JSON.stringify(candidate)===JSON.stringify(anchor))));
 const sourceRow=instance?(direct?Number(direct[0].split('.',1)[0]):-1):record;
 const anchor=direct?.[1][0]||proof[0]||(!instance?profile?.anchors?.[`${sourceRow}.${binding?.source_field}`]?.[0]:undefined);
 const conceptProperties=conceptOf(view.ontology,view.ontology_concept).properties;
 const fields=Object.keys(conceptProperties).filter(k=>!onlyProblems||!bindings[k]||view.preview?.issues.some(i=>(i as Record<string,unknown>).target===k));
 // 计数按根因：同一列跨多行的转换失败只算 1 项，受影响行数单列（FDE2-06）。
 // issues 仍逐行保留，供逐行定位与纠正。
 const issueItems=(view.preview?.issues||view.session.issues||[]) as Issue[];
 const problemCount=view.preview?.issue_count??issueItems.length;
 const issueRowCount=view.preview?.issue_row_count
  ??new Set(issueItems.filter(issue=>issue.row!==undefined).map(issue=>`${issue.source_id??''}|${issue.row}`)).size;
 // 来源级问题（未映射来源、来源与概念不符、来源不完整）及操作永远排在最前，
 // 不参与只显示前 8 条的截断；否则前面的行级问题一多，「纳入映射」入口就不可达。
 const sourceLevelIssue=(issue:Issue)=>issue.code==='ontology.source_unmapped'
  ||issue.code==='ontology.incomplete_source'
  ||issue.code==='ontology.source_concept_mismatch';
 const sourceIssues=issueItems.filter(sourceLevelIssue);
 const rowIssues=issueItems.filter(issue=>!sourceLevelIssue(issue));
 const visibleIssues=[...sourceIssues,...rowIssues.slice(0,8)];
 // 整源处置不能只挂在「未映射/不符」问题上：结构上能绑定、但业务上明显
 // 是另一张表（例如限额表被错绑成金额/币种）时，来源页签里也要能带原因
 // 选择不使用。已有来源级问题行时由问题行提供入口，避免重复控件。
 const sourceLevelIssueIds=new Set(issueItems
  .filter(issue=>issue.code==='ontology.source_unmapped'||issue.code==='ontology.source_concept_mismatch')
  .map(issue=>issue.source_id).filter((id):id is string=>!!id));
 const hasAnySourceIssue=sourceLevelIssueIds.size>0;
 const sourceDisposals=(view.disposition_options||[]).filter(option=>option.scope==='source'
  && !sourceLevelIssueIds.has(option.source_id));
 const issueText=(issue:{code?:string;target?:string;object?:string;reason?:string;source_id?:string})=>{
  if(issue.code==='intake.probe_failed'){
   const name=view.session.sources.find(s=>s.source_id===issue.source_id);
   return `${String((name as {options?:{display_name?:string}}|undefined)?.options?.display_name||'材料')} · 材料读取失败，请更换文件后重新接入`;
  }
  // FDE2-11：已知 code 用前端的通用中文说法（不再用采购口径的「单据号」），
  // 前端未收录的 code 才退回后端给的 reason。
  return `${issue.object||'全部对象'}${issue.target?` · ${propertyLabel(issue.target)}`:''} · ${issueReasons[issue.code||'']||issue.reason||display(issue.code)}`;
 };
 // 面包屑与标题跟随任务目标本体（FDE2-11）：不再写死「采购资料 / Ontology」。
 const crumb=ontologyName||builtinTitles[view.ontology.id]||conceptLabel(conceptOf(view.ontology,view.ontology_concept));
 return <main className="workspace"><div className="task-header"><div><div className="eyebrow">{crumb} / 接入任务</div><h1>{done?'接入已保存':'核对来源与本体映射'}</h1><p className={failed?'muted problem-text':'muted'}>{working?'正在识别材料并探查结构，已完成结果会持续保留。':failed?'材料读取失败，请查看左侧来源的问题说明并更换材料。':canRetry?'部分来源待重试，已取得的证据可以查看。':'识别与探查已完成'}{view.mapping_reused?' · 已复用经过验证的映射':''}</p></div><div className="save-buttons">
  {canRetry&&<button className="primary" disabled={busy||working} onClick={async()=>{
   setBusy(true);try{await api(base+'/advance','POST',{});await load(true);}catch(error){onError(error);}finally{setBusy(false);}
  }}>继续探查</button>}
  <button className="secondary" onClick={onNew}>新建接入</button></div></div>
 <nav className="steps" aria-label="接入进度">{['已接收','识别与探查','映射与校验','查看对象','保存接入'].map((step,i)=><div key={step} className={i===1&&failed?'step failed':done||i<(working?1:view.preview?4:2)?'step done':'step'}><span>{i===1&&failed?'✗':done||i<(working?1:2)?'✓':i+1}</span>{step}</div>)}</nav>
 <div className="work-grid"><section className="source-panel"><div className="panel-heading"><strong>来源</strong><span className="badge">{view.session.sources.length} 份材料</span></div>
  <div className="source-tabs">{view.session.sources.map(s=><button key={s.source_id} className={(profile?.source_id===s.source_id?'active ':'')+'source-tab'} onClick={()=>selectSource(s.source_id)}><span>▤</span><span>{String(s.options?.display_name||s.locator_ref.split('/').pop())}</span></button>)}</div>
  <SourceViewer sessionId={sessionId} profile={profile} anchor={anchor as never} recordIndex={sourceRow} sourceField={binding?.source_field}/>
  {!done&&sourceDisposals.length>0&&<div className="source-disposals">
   {sourceDisposals.map(option=>{
    const key=`${option.action}:${option.source_id}`;
    return <div key={key} className="disposal source-disposal" data-testid="source-disposal">
     <div data-testid={hasAnySourceIssue?'source-disposal-option':'disposal-option'}>
      <span className="muted">本任务不使用「{option.source_name}」 · {option.reason_hint}</span>
      <div className="disposal-controls">
       <input aria-label={`处置原因：本任务不使用「${option.source_name}」`} value={disposalReasons[key]||''} onChange={e=>setDisposalReasons(previous=>({...previous,[key]:e.target.value}))} placeholder="处置原因（必填，写入审计）"/>
       <button className="secondary" disabled={busy||done||!(disposalReasons[key]||'').trim()} onClick={()=>submitDisposal(option,disposalReasons[key])}>提交处置</button>
      </div>
     </div>
    </div>;})}
  </div>}
 </section><section className="mapping-panel"><div className="panel-heading"><strong>目标映射</strong><span className="badge">{conceptLabel(conceptOf(view.ontology,view.ontology_concept))}</span></div>
 <div className="mapping-toolbar"><span><strong>{Object.keys(bindings).length}</strong> / {Object.keys(conceptProperties).length} 字段已绑定</span><label><input type="checkbox" checked={onlyProblems} onChange={e=>setOnlyProblems(e.target.checked)}/>只看待处理</label></div>
 <div className="mapping-table-scroll"><table className="mapping-table"><thead><tr><th>本体属性</th><th>来源字段</th><th>转换方式</th><th>预览值</th></tr></thead><tbody>{fields.map(name=>{
  const b=bindings[name];const issue=view.preview?.issues.some(i=>(i as Record<string,unknown>).target===name);
  const correction=view.correction_views?.find(item=>item.entity_id===instance?.id&&item.property===name);return <tr key={name} className={field===name?'active-mapping':''} onClick={()=>setField(name)}>
  <td><button className="field-button" title={name} onClick={()=>setField(name)}>{propertyLabel(name)}</button>{conceptProperties[name]&&conceptProperties[name].required&&<span className="required">必需</span>}<small className={issue||!b?'warn':'ok'}>{issue?'需核对':b?'已绑定':'未映射'}</small></td>
  <td><select disabled={done} aria-label={`${propertyLabel(name)} 来源字段`} value={b?.source_field||''} onChange={e=>change(name,{...(b||{}),source_field:e.target.value,transform:b?.transform||'identity'})}><option value="">选择来源字段</option>{profile?.fields?.map(f=><option key={f} value={f}>{f}</option>)}</select></td>
  <td><select disabled={done} aria-label={`${propertyLabel(name)} 转换方式`} value={b?.transform||'identity'} onChange={e=>change(name,{...(b||{source_field:''}),transform:e.target.value as FieldBinding['transform']})}>{Object.entries(transformNames).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></td>
  <td className="mapped-value">{dirty?'待更新':display(instance?.values?.[name])}{correction&&!dirty&&<small className="warn">纠正值生效 · 映射值 {display(correction.mapping_value)}</small>}</td></tr>;})}</tbody></table></div>
 <div className="mapping-actions"><span className="muted">{draftState||'原值与转换后的值均可核对'}</span><button className="primary" disabled={busy||working||done||!profile} onClick={preview}>{busy?'正在校验…':'生成映射预览'}</button></div>
 {correctionNotice&&<div className={correctionNotice.kind==='green'?'notice green':'notice amber'} data-testid="mapping-correction-notice" role="status">{correctionNotice.text}</div>}
 {problemCount>0&&<div className="notice amber"><strong>{problemCount} 项根因{issueRowCount?` · 影响 ${issueRowCount} 行`:''}</strong><ul data-testid="mapping-issues">{visibleIssues.map((issue,i)=><li key={i}>{issueText(issue)}
   {/* 未映射来源的第一条出路：显式纳入映射。点一次即记录来源范围选择，
       沿用当前绑定（未改过时就是默认同名绑定）重新提案，不要求先改绑定。 */}
   {issue.code==='ontology.source_unmapped'&&issue.source_id&&(()=>{
    const id=issue.source_id as string,included=includedSources.has(id);
    return <div className="disposal" data-testid="include-mapping-option">
     <span className="muted">{included
      ?`已纳入「${sourceLabel(id)}」：沿用当前绑定，请点击「生成映射预览」重新提案。`
      :`把「${sourceLabel(id)}」纳入映射：沿用当前绑定（默认同名绑定可直接使用）重新提案。`}</span>
     <div className="disposal-controls">
      <button className="secondary" disabled={busy||done||included} onClick={()=>includeSource(id)}>{included?'已纳入，待生成预览':'纳入映射'}</button>
     </div>
    </div>;})()}
   {/* 未映射/与概念不符来源的整源处置：写审计、必填原因，处置后重新生成预览即可。 */}
   {(issue.code==='ontology.source_unmapped'||issue.code==='ontology.source_concept_mismatch')&&(view.disposition_options||[]).filter(option=>option.scope==='source'&&option.source_id===issue.source_id).map(option=>{
    const key=`${option.action}:${option.source_id}`;
    return <div key={key} className="disposal" data-testid="disposal-option">
     <span className="muted">本任务不使用「{option.source_name}」 · {option.reason_hint}</span>
     <div className="disposal-controls">
      <input aria-label={`处置原因：本任务不使用「${option.source_name}」`} value={disposalReasons[key]||''} onChange={e=>setDisposalReasons(previous=>({...previous,[key]:e.target.value}))} placeholder="处置原因（必填，写入审计）"/>
      <button className="secondary" disabled={busy||done||!(disposalReasons[key]||'').trim()} onClick={()=>submitDisposal(option,disposalReasons[key])}>提交处置</button>
     </div>
    </div>;})}
  </li>)}</ul>{issueItems.length>visibleIssues.length&&<p className="help">共 {problemCount} 项根因，打开对象页查看全部逐行问题。</p>}</div>}
 <div className="object-section"><div className="panel-heading"><strong>对象预览</strong><span className="badge">{view.preview?.instances?.length||0} 个对象</span>{onOpenObjects&&view.preview&&<button className="secondary" onClick={onOpenObjects}>打开对象页</button>}</div>{view.preview?<><div className="sample-controls"><button className="icon-button" disabled={record===0} onClick={()=>setRecord(record-1)}>←</button><span>对象 {record+1} / {view.preview.instances?.length||0}</span><button className="icon-button" disabled={record>=(view.preview.instances?.length||0)-1} onClick={()=>setRecord(record+1)}>→</button></div><dl className="object-values">{Object.keys(conceptProperties).map(k=><div key={k}><dt title={k}>{propertyLabel(k)}</dt><dd>{display(instance?.values?.[k])}</dd></div>)}</dl></>:<div className="empty">生成映射预览后，在这里查看真实对象。</div>}</div>
 {instance?.extensions&&<details className="extension-box"><summary>查看扩展字段</summary><pre>{JSON.stringify(instance.extensions,null,2)}</pre></details>}
 </section><MappingDetail readOnly={done} view={view} field={field} binding={binding} raw={profile?.records?.[sourceRow]?.[binding?.source_field||'']} dirty={dirty} recordIndex={record} onCorrect={correct} onAdopt={adopt} onSchema={async(name,reason)=>{try{await review('ontology',{property:name,value_type:'string',reason});}catch(error){onError(error);}}}/></div>
 <footer className="save-bar"><div><strong>{done?'已保存，可在后续接入中复用':dirty?'映射已修改，请生成新预览':problemCount?'补齐待核对项后保存':'核对后保存接入'}</strong><small>{view.preview?.review_state==='needs_revalidation'?'修改已留痕，需要重新校验。':'来源证据、映射修订和用户决定一起保存。'}</small></div><div className="save-buttons"><button className="secondary" onClick={()=>load(true).catch(onError)}>重新载入</button><button className="primary" disabled={busy||done||dirty||!view.preview||problemCount>0||view.preview.review_state!=='unreviewed'} onClick={save}>{done?'已保存':'保存接入'}</button></div></footer>
 </main>;
}
