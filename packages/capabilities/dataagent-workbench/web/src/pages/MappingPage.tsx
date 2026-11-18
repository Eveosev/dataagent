import {useEffect,useRef,useState} from 'react';
import {api,display,transformNames} from '../client';
import type {View,Draft,FieldBinding,IntakeSession,MappingSpec,SourceProfile,CorrectionView} from '../client';
import {SourceViewer} from '../components/SourceViewer';
import {DiscoveryPage} from './DiscoveryPage';
import {MappingDetail} from '../components/MappingDetail';

function savedMappings(view:View){
 return (view.preview?.extensions?.['intake.source_mappings']||{}) as Record<string,MappingSpec>;
}

function defaultBindings(view:View,sourceId:string){
 const profile=view.profiles.find(p=>p.source_id===sourceId);
 return Object.fromEntries(Object.keys(view.ontology.properties).filter(k=>profile?.fields?.includes(k))
  .map(k=>[k,{source_field:k,transform:'identity' as const}]));
}

export function MappingPage({sessionId,onNew,onError,onOpenObjects}:{sessionId:string;onNew:()=>void;onError:(e:unknown)=>void;onOpenObjects?:()=>void}){
 const [view,setView]=useState<View|null>(null),[bindings,setBindings]=useState<Record<string,FieldBinding>>({});
 const [field,setField]=useState(''),[sourceId,setSourceId]=useState(''),[record,setRecord]=useState(0),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[onlyProblems,setOnlyProblems]=useState(false),[draftState,setDraftState]=useState('');
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
   setField(current=>current||data.draft.selected_field||Object.keys(data.ontology.properties)[0]||'');
   initialized.current=!!data.profiles.length;
  }else{
   const profile=data.profiles[0];const exact=defaultBindings(data,profile?.source_id||'');
   const chosen=local?.bindings||data.draft.bindings||data.preview?.mapping.bindings||exact;
   setBindings(chosen);bindingsRef.current=chosen;
   if(!initialized.current||reset){
    setField(local?.selected_field||data.draft.selected_field||Object.keys(data.ontology.properties)[0]||'');
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
   await api(base+'/revalidate','POST',{expected_revision:revision.current});await load();
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
 if(view.discovery)return <DiscoveryPage view={view} reload={load} onNew={onNew} onError={onError}/>;
 const phase=view.session.phase,done=phase==='saved',working=phase==='queued'||phase==='probing';
 const canRetry=view.session.next_actions?.includes('retry_probe');
 const instance=view.preview?.instances?.[record];const binding=bindings[field];
 const proof=instance?.source_anchors?.[field]?.filter(a=>a.source_ref===profile?.source_id)||[];
 const direct=Object.entries(profile?.anchors||{}).find(([key,anchors])=>
  key.endsWith('.'+binding?.source_field)&&anchors.some(anchor=>proof.some(candidate=>JSON.stringify(candidate)===JSON.stringify(anchor))));
 const sourceRow=instance?(direct?Number(direct[0].split('.',1)[0]):-1):record;
 const anchor=direct?.[1][0]||proof[0]||(!instance?profile?.anchors?.[`${sourceRow}.${binding?.source_field}`]?.[0]:undefined);
 const fields=Object.keys(view.ontology.properties).filter(k=>!onlyProblems||!bindings[k]||view.preview?.issues.some(i=>(i as Record<string,unknown>).target===k));
 const problemCount=(view.preview?.issues||view.session.issues||[]).length;
 return <main className="workspace"><div className="task-header"><div><div className="eyebrow">采购资料 / 接入任务</div><h1>{done?'接入已保存':'核对来源与 Ontology 映射'}</h1><p className="muted">{working?'正在识别材料并探查结构，已完成结果会持续保留。':canRetry?'部分来源待重试，已取得的证据可以查看。':'识别与探查已完成'}{view.mapping_reused?' · 已复用经过验证的映射':''}</p></div><div className="save-buttons">
  {canRetry&&<button className="primary" disabled={busy||working} onClick={async()=>{
   setBusy(true);try{await api(base+'/advance','POST',{});await load(true);}catch(error){onError(error);}finally{setBusy(false);}
  }}>继续探查</button>}
  <button className="secondary" onClick={onNew}>新建接入</button></div></div>
 <nav className="steps" aria-label="接入进度">{['已接收','识别与探查','映射与校验','查看对象','保存接入'].map((step,i)=><div key={step} className={done||i<(working?1:view.preview?4:2)?'step done':'step'}><span>{done||i<(working?1:2)?'✓':i+1}</span>{step}</div>)}</nav>
 <div className="work-grid"><section className="source-panel"><div className="panel-heading"><strong>来源</strong><span className="badge">{view.session.sources.length} 份材料</span></div>
  <div className="source-tabs">{view.session.sources.map(s=><button key={s.source_id} className={(profile?.source_id===s.source_id?'active ':'')+'source-tab'} onClick={()=>selectSource(s.source_id)}><span>▤</span><span>{String(s.options?.display_name||s.locator_ref.split('/').pop())}</span></button>)}</div>
  <SourceViewer sessionId={sessionId} profile={profile} anchor={anchor as never} recordIndex={sourceRow} sourceField={binding?.source_field}/>
 </section><section className="mapping-panel"><div className="panel-heading"><strong>目标映射</strong><span className="badge">{view.ontology.entity_type}</span></div>
 <div className="mapping-toolbar"><span><strong>{Object.keys(bindings).length}</strong> / {Object.keys(view.ontology.properties).length} 字段已绑定</span><label><input type="checkbox" checked={onlyProblems} onChange={e=>setOnlyProblems(e.target.checked)}/>只看待处理</label></div>
 <div className="mapping-table-scroll"><table className="mapping-table"><thead><tr><th>Ontology 属性</th><th>来源字段</th><th>转换方式</th><th>预览值</th></tr></thead><tbody>{fields.map(name=>{
  const b=bindings[name];const issue=view.preview?.issues.some(i=>(i as Record<string,unknown>).target===name);
  const correction=view.correction_views?.find(item=>item.entity_id===instance?.id&&item.property===name);return <tr key={name} className={field===name?'active-mapping':''} onClick={()=>setField(name)}>
  <td><button className="field-button" onClick={()=>setField(name)}>{name}</button>{view.ontology.properties[name].required&&<span className="required">必需</span>}<small className={issue||!b?'warn':'ok'}>{issue?'需核对':b?'已绑定':'未映射'}</small></td>
  <td><select disabled={done} aria-label={`${name} 来源字段`} value={b?.source_field||''} onChange={e=>change(name,{...(b||{}),source_field:e.target.value,transform:b?.transform||'identity'})}><option value="">选择来源字段</option>{profile?.fields?.map(f=><option key={f} value={f}>{f}</option>)}</select></td>
  <td><select disabled={done} aria-label={`${name} 转换方式`} value={b?.transform||'identity'} onChange={e=>change(name,{...(b||{source_field:''}),transform:e.target.value as FieldBinding['transform']})}>{Object.entries(transformNames).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></td>
  <td className="mapped-value">{dirty?'待更新':display(instance?.values?.[name])}{correction&&!dirty&&<small className="warn">纠正值生效 · 映射值 {display(correction.mapping_value)}</small>}</td></tr>;})}</tbody></table></div>
 <div className="mapping-actions"><span className="muted">{draftState||'原值与转换后的值均可核对'}</span><button className="primary" disabled={busy||working||done||!profile} onClick={preview}>{busy?'正在校验…':'生成映射预览'}</button></div>
 {problemCount>0&&<div className="notice amber"><strong>{problemCount} 项待核对</strong><ul>{(view.preview?.issues||view.session.issues||[]).slice(0,5).map((issue,i)=><li key={i}>{display((issue as Record<string,unknown>).target)} · {display((issue as Record<string,unknown>).code)}</li>)}</ul></div>}
 <div className="object-section"><div className="panel-heading"><strong>对象预览</strong><span className="badge">{view.preview?.instances?.length||0} 个对象</span>{onOpenObjects&&view.preview&&<button className="secondary" onClick={onOpenObjects}>打开对象页</button>}</div>{view.preview?<><div className="sample-controls"><button className="icon-button" disabled={record===0} onClick={()=>setRecord(record-1)}>←</button><span>对象 {record+1} / {view.preview.instances?.length||0}</span><button className="icon-button" disabled={record>=(view.preview.instances?.length||0)-1} onClick={()=>setRecord(record+1)}>→</button></div><dl className="object-values">{Object.keys(view.ontology.properties).map(k=><div key={k}><dt>{k}</dt><dd>{display(instance?.values?.[k])}</dd></div>)}</dl></>:<div className="empty">生成映射预览后，在这里查看真实对象。</div>}</div>
 {instance?.extensions&&<details className="extension-box"><summary>查看扩展字段</summary><pre>{JSON.stringify(instance.extensions,null,2)}</pre></details>}
 </section><MappingDetail readOnly={done} view={view} field={field} binding={binding} raw={profile?.records?.[sourceRow]?.[binding?.source_field||'']} dirty={dirty} recordIndex={record} onCorrect={correct} onAdopt={adopt} onSchema={async(name,reason)=>{try{await review('ontology',{property:name,value_type:'string',reason});}catch(error){onError(error);}}}/></div>
 <footer className="save-bar"><div><strong>{done?'已保存，可在后续接入中复用':dirty?'映射已修改，请生成新预览':problemCount?'补齐待核对项后保存':'核对后保存接入'}</strong><small>{view.preview?.review_state==='needs_revalidation'?'修改已留痕，需要重新校验。':'来源证据、映射修订和用户决定一起保存。'}</small></div><div className="save-buttons"><button className="secondary" onClick={()=>load(true).catch(onError)}>重新载入</button><button className="primary" disabled={busy||done||dirty||!view.preview||problemCount>0||view.preview.review_state!=='unreviewed'} onClick={save}>{done?'已保存':'保存接入'}</button></div></footer>
 </main>;
}
