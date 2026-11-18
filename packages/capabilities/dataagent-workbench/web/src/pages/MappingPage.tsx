import {useEffect,useRef,useState} from 'react';
import {api,ApiError,display,transformNames,propertyLabel,entityTypeLabel,sourceProblem,issueReasons,conceptOf} from '../client';
import type {View,Draft,FieldBinding,IntakeSession,MappingSpec,SourceProfile,CorrectionView} from '../client';
import {SourceViewer} from '../components/SourceViewer';
import {DiscoveryPage} from './DiscoveryPage';
import {MappingDetail} from '../components/MappingDetail';

function savedMappings(view:View){
 return (view.preview?.extensions?.['intake.source_mappings']||{}) as Record<string,MappingSpec>;
}

// 默认绑定按任务固定概念的属性名与来源字段同名匹配（多概念本体不再读全局旧字段）。
function defaultBindings(view:View,sourceId:string){
 const profile=view.profiles.find(p=>p.source_id===sourceId);
 const properties=conceptOf(view.ontology,view.ontology_concept).properties;
 return Object.fromEntries(Object.keys(properties).filter(k=>profile?.fields?.includes(k))
  .map(k=>[k,{source_field:k,transform:'identity' as const}]));
}

export function MappingPage({sessionId,onNew,onError,onOpenObjects,onOpenSession,onOpenOntologies}:{sessionId:string;onNew:()=>void;onError:(e:unknown)=>void;onOpenObjects?:()=>void;onOpenSession:(id:string)=>void;onOpenOntologies?:()=>void}){
 const [view,setView]=useState<View|null>(null),[bindings,setBindings]=useState<Record<string,FieldBinding>>({});
 const [field,setField]=useState(''),[sourceId,setSourceId]=useState(''),[record,setRecord]=useState(0),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[onlyProblems,setOnlyProblems]=useState(false),[draftState,setDraftState]=useState('');
 // FDE-12：字段详情里的纠正同样给绿色成功提示；被其他问题挡住时点名，不走红色错误条。
 const [correctionNotice,setCorrectionNotice]=useState<{kind:'green'|'amber';text:string}|null>(null);
 const revision=useRef(''),initialized=useRef(false),dirtyRef=useRef(false),queue=useRef(Promise.resolve()),draftError=useRef<unknown>(null),bindingsRef=useRef<Record<string,FieldBinding>>({});
 const sourceBindings=useRef<Record<string,Record<string,FieldBinding>>>({}),selectedSource=useRef('');
 const base=`/api/sessions/${sessionId}`;const localKey=`dataagent-draft:${sessionId}`;
 async function load(reset=false){
  const data=await api<View>(base+'/view');
  if(Number(data.session.revision)<Number(revision.current))return;
  setView(data);
  if(dirtyRef.current&&!reset)return;
  revision.current=data.session.revision;
  if(data.discovery)return;
  if(reset){
   sessionStorage.removeItem(localKey);setDirty(false);dirtyRef.current=false;draftError.current=null;setDraftState('');
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
    mappings[p.source_id]?.bindings||defaultBindings(data,p.source_id)]));
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
 const profile=sourceId?view?.profiles.find(p=>p.source_id===sourceId):view?.profiles[0];
 const multiple=(view?.session.sources.length||0)>1;
 function selectSource(id:string){
  selectedSource.current=id;setSourceId(id);setRecord(0);
  if(multiple){const next=sourceBindings.current[id]||{};setBindings(next);bindingsRef.current=next;}
 }
 function draft(next:Record<string,FieldBinding>,selected=field){
  setDraftState('正在保存草稿…');
  if(multiple)sourceBindings.current={...sourceBindings.current,[sourceId]:next};
  const draftData={...(multiple?{source_bindings:sourceBindings.current}:{bindings:next}),
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
 function change(target:string,binding:FieldBinding){const next={...bindingsRef.current,[target]:binding};if(!binding.source_field)delete next[target];bindingsRef.current=next;setBindings(next);setField(target);setDirty(true);dirtyRef.current=true;draft(next,target);}
 async function preview(){
  setBusy(true);try{
   await queue.current;if(draftError.current)throw draftError.current;
   if(!profile||!view)throw new Error('来源尚未探查');
   const loaded=view;
   function propose(source:SourceProfile,fields:Record<string,FieldBinding>,prior?:MappingSpec):MappingSpec{
    const used=new Set(Object.values(fields).map(b=>b.source_field));
    return {...prior,id:'candidate',revision:'1',ontology_revision:`${loaded.ontology.id}@${loaded.ontology.revision}`,
     // 多概念本体必须点名任务固定的概念，服务端会拒绝概念外的提案。
     concept:conceptOf(loaded.ontology,loaded.ontology_concept).name,
     source_fingerprint:String(source.metadata?.structure_fingerprint),bindings:fields,
     unmapped:Object.fromEntries((source.fields||[]).filter(f=>!used.has(f)).map(f=>[f,'extension']))};
   }
   if(multiple){
    const existing=savedMappings(view);
    const proposals=Object.fromEntries(view.profiles.map(source=>[source.source_id,
     propose(source,sourceBindings.current[source.source_id]||defaultBindings(view,source.source_id),existing[source.source_id])]));
    await api(base+'/source-proposals','POST',{proposals,expected_revision:revision.current});
   }else{
    const proposal=propose(profile,bindingsRef.current,view.preview?.mapping);
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
 const problemCount=(view.preview?.issues||view.session.issues||[]).length;
 // 预览问题已带对象标签与中文理由（issue_summary）；会话问题是探查失败，
 // 点出材料名而不是内部来源哈希。
 const issueItems=(view.preview?.issues||view.session.issues||[]) as {code?:string;target?:string;object?:string;reason?:string;source_id?:string}[];
 const issueText=(issue:{code?:string;target?:string;object?:string;reason?:string;source_id?:string})=>{
  if(issue.code==='intake.probe_failed'){
   const name=view.session.sources.find(s=>s.source_id===issue.source_id);
   return `${String((name as {options?:{display_name?:string}}|undefined)?.options?.display_name||'材料')} · 材料读取失败，请更换文件后重新接入`;
  }
  return `${issue.object||'全部对象'}${issue.target?` · ${propertyLabel(issue.target)}`:''} · ${issue.reason||issueReasons[issue.code||'']||display(issue.code)}`;
 };
 return <main className="workspace"><div className="task-header"><div><div className="eyebrow">采购资料 / 接入任务</div><h1>{done?'接入已保存':'核对来源与 Ontology 映射'}</h1><p className={failed?'muted problem-text':'muted'}>{working?'正在识别材料并探查结构，已完成结果会持续保留。':failed?'材料读取失败，请查看左侧来源的问题说明并更换材料。':canRetry?'部分来源待重试，已取得的证据可以查看。':'识别与探查已完成'}{view.mapping_reused?' · 已复用经过验证的映射':''}</p></div><div className="save-buttons">
  {canRetry&&<button className="primary" disabled={busy||working} onClick={async()=>{
   setBusy(true);try{await api(base+'/advance','POST',{});await load(true);}catch(error){onError(error);}finally{setBusy(false);}
  }}>继续探查</button>}
  <button className="secondary" onClick={onNew}>新建接入</button></div></div>
 <nav className="steps" aria-label="接入进度">{['已接收','识别与探查','映射与校验','查看对象','保存接入'].map((step,i)=><div key={step} className={i===1&&failed?'step failed':done||i<(working?1:view.preview?4:2)?'step done':'step'}><span>{i===1&&failed?'✗':done||i<(working?1:2)?'✓':i+1}</span>{step}</div>)}</nav>
 <div className="work-grid"><section className="source-panel"><div className="panel-heading"><strong>来源</strong><span className="badge">{view.session.sources.length} 份材料</span></div>
  <div className="source-tabs">{view.session.sources.map(s=><button key={s.source_id} className={(profile?.source_id===s.source_id?'active ':'')+'source-tab'} onClick={()=>selectSource(s.source_id)}><span>▤</span><span>{String(s.options?.display_name||s.locator_ref.split('/').pop())}</span></button>)}</div>
  <SourceViewer sessionId={sessionId} profile={profile} anchor={anchor as never} recordIndex={sourceRow} sourceField={binding?.source_field}/>
 </section><section className="mapping-panel"><div className="panel-heading"><strong>目标映射</strong><span className="badge">{entityTypeLabel(conceptOf(view.ontology,view.ontology_concept).entity_type)}</span></div>
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
 {problemCount>0&&<div className="notice amber"><strong>{problemCount} 项待核对</strong><ul data-testid="mapping-issues">{issueItems.slice(0,8).map((issue,i)=><li key={i}>{issueText(issue)}</li>)}</ul>{issueItems.length>8&&<p className="help">共 {issueItems.length} 项，打开对象页查看全部。</p>}</div>}
 <div className="object-section"><div className="panel-heading"><strong>对象预览</strong><span className="badge">{view.preview?.instances?.length||0} 个对象</span>{onOpenObjects&&view.preview&&<button className="secondary" onClick={onOpenObjects}>打开对象页</button>}</div>{view.preview?<><div className="sample-controls"><button className="icon-button" disabled={record===0} onClick={()=>setRecord(record-1)}>←</button><span>对象 {record+1} / {view.preview.instances?.length||0}</span><button className="icon-button" disabled={record>=(view.preview.instances?.length||0)-1} onClick={()=>setRecord(record+1)}>→</button></div><dl className="object-values">{Object.keys(conceptProperties).map(k=><div key={k}><dt>{k}</dt><dd>{display(instance?.values?.[k])}</dd></div>)}</dl></>:<div className="empty">生成映射预览后，在这里查看真实对象。</div>}</div>
 {instance?.extensions&&<details className="extension-box"><summary>查看扩展字段</summary><pre>{JSON.stringify(instance.extensions,null,2)}</pre></details>}
 </section><MappingDetail readOnly={done} view={view} field={field} binding={binding} raw={profile?.records?.[sourceRow]?.[binding?.source_field||'']} dirty={dirty} recordIndex={record} onCorrect={correct} onAdopt={adopt} onSchema={async(name,reason)=>{try{await review('ontology',{property:name,value_type:'string',reason});}catch(error){onError(error);}}}/></div>
 <footer className="save-bar"><div><strong>{done?'已保存，可在后续接入中复用':dirty?'映射已修改，请生成新预览':problemCount?'补齐待核对项后保存':'核对后保存接入'}</strong><small>{view.preview?.review_state==='needs_revalidation'?'修改已留痕，需要重新校验。':'来源证据、映射修订和用户决定一起保存。'}</small></div><div className="save-buttons"><button className="secondary" onClick={()=>load(true).catch(onError)}>重新载入</button><button className="primary" disabled={busy||done||dirty||!view.preview||problemCount>0||view.preview.review_state!=='unreviewed'} onClick={save}>{done?'已保存':'保存接入'}</button></div></footer>
 </main>;
}
