import {useEffect,useRef,useState} from 'react';
import {api,ApiError,display,locate,findAnchorRow,isDecisionEvidence,decisionSourceName} from '../client';
import type {CorrectionView,ObjectView,SourceProfile} from '../client';
import {SourceViewer} from '../components/SourceViewer';

const ranges=[['instance','纠正当前对象的值'],['mapping','修改这类来源的映射'],['ontology','提出本体草案']] as const;
const scopeIds=['instance','mapping','ontology'];

export function ObjectPage({sessionId,onBack,onError}:{sessionId:string;onBack:()=>void;onError:(e:unknown)=>void}){
 const [view,setView]=useState<ObjectView|null>(null),[index,setIndex]=useState(0),[field,setField]=useState('');
 const [range,setRange]=useState('instance'),[value,setValue]=useState(''),[reason,setReason]=useState('');
 const [name,setName]=useState(''),[type,setType]=useState('string'),[busy,setBusy]=useState(false),[conflict,setConflict]=useState(false);
 const revision=useRef(''),base=useRef(''),editing=useRef(false),initialized=useRef(false),running=useRef(false);
 const objectRef=useRef(''),editObject=useRef(''),idxRef=useRef(0);
 const base_url=`/api/sessions/${sessionId}`;
 const localKey=`dataagent-object-draft:${sessionId}`;
 async function load(){
  const data=await api<ObjectView>(base_url+'/objects');
  revision.current=data.session.revision;
  if(!editing.current)base.current=data.session.revision;
  setView(data);
  if(!initialized.current){
   initialized.current=true;
   const properties=Object.keys(data.ontology.properties);
   if(properties.length)setField(properties[0]);
   const pending=sessionStorage.getItem(localKey);
   if(pending&&data.session.phase!=='saved'){
    try{
     const saved=JSON.parse(pending) as {object:string;range:string;property:string;value:string;reason:string;name:string;type:string};
     if(saved.value||saved.reason||saved.name){
      const pos=saved.object?data.objects.findIndex(o=>o.id===saved.object):-1;
      if(saved.object&&pos<0){sessionStorage.removeItem(localKey);}
      else{
       if(pos>=0)setIndex(pos);
       setValue(saved.value||'');setReason(saved.reason||'');
       if(saved.property&&properties.includes(saved.property))setField(saved.property);
       if(scopeIds.includes(saved.range))setRange(saved.range);
       if(saved.name)setName(saved.name);
       if(saved.type)setType(saved.type);
       editObject.current=saved.object||'';
       editing.current=true;
      }
     }
    }catch{sessionStorage.removeItem(localKey);}
   }
  }
 }
 useEffect(()=>{load().catch(onError);const timer=setInterval(()=>load().catch(onError),1500);return()=>clearInterval(timer);},[sessionId]);
 function touch(next:{property?:string;value?:string;reason?:string}={}){
  if(!editing.current){editing.current=true;base.current=revision.current;editObject.current=objectRef.current;}
  sessionStorage.setItem(localKey,JSON.stringify({object:editObject.current||objectRef.current,range,
   property:next.property??field,value:next.value??value,reason:next.reason??reason,
   name,type,revision:base.current}));
 }
 // A correction is bound to one object: switching objects starts a clean edit.
 function selectObject(i:number){
  if(i===idxRef.current)return;
  setIndex(i);setValue('');setReason('');setConflict(false);
  editing.current=false;editObject.current='';
  sessionStorage.removeItem(localKey);
 }
 async function confirmConflict(){
  setBusy(true);setConflict(false);editing.current=false;
  await load().catch(()=>{});
  editing.current=true;setBusy(false);
 }
 async function submit(){
  if(running.current)return;
  running.current=true;setBusy(true);try{
   const active=view;
   if(!active||!object||!active.preview_ref)throw new Error('请先生成映射预览');
   if(range==='instance'){
    if(!field||!value.trim()||!reason.trim())throw new Error('请填写纠正值与原因');
    if(editObject.current&&editObject.current!==object.id)throw new Error('纠正目标已切换，请核对当前对象后重新输入');
    await api(base_url+'/review','POST',{expected_revision:base.current,decision:{preview_ref:active.preview_ref,
     target_scope:'instance',changes:{entity_id:object.id,property:field,value,reason},decision:'save'}});
    editing.current=false;editObject.current='';
    await load();
    try{await api(base_url+'/revalidate','POST',{expected_revision:revision.current});}
    catch(error){onError(error);}
   }else{
    if(!name.trim()||!reason.trim())throw new Error('请填写属性名与原因');
    await api(base_url+'/review','POST',{expected_revision:base.current,decision:{preview_ref:active.preview_ref,
     target_scope:'ontology',changes:{property:name,value_type:type,reason},decision:'save'}});
    editing.current=false;editObject.current='';
   }
   setValue('');setReason('');setName('');setConflict(false);
   sessionStorage.removeItem(localKey);
   await load();
  }catch(error){
   onError(error);
   if(error instanceof ApiError&&error.status===409){
    // A stale decision stays blocked until the user explicitly re-checks; the
    // edit and its baseline revision are kept as they were.
    setConflict(true);
   }else{editing.current=false;await load().catch(()=>{});}
  }finally{running.current=false;setBusy(false);}
 }
 async function adopt(correction:CorrectionView){
  if(running.current)return;
  running.current=true;setBusy(true);try{
   const active=view;
   if(!active||!active.preview_ref)throw new Error('请先生成映射预览');
   await api(base_url+'/review','POST',{expected_revision:revision.current,decision:{preview_ref:active.preview_ref,
    target_scope:'instance',changes:{entity_id:correction.entity_id,property:correction.property,
     value:String(correction.mapping_value),reason:'撤销纠正，采用映射值'},decision:'save'}});
   // 采用映射值是一次新的用户决定：清掉本地草稿，以最新修订重新校验。
   editing.current=false;editObject.current='';setValue('');setReason('');setConflict(false);
   sessionStorage.removeItem(localKey);
   await load();
   try{await api(base_url+'/revalidate','POST',{expected_revision:revision.current});}
   catch(error){onError(error);}
   await load();
  }catch(error){
   onError(error);
   if(error instanceof ApiError&&error.status===409)setConflict(true);
  }finally{running.current=false;setBusy(false);}
 }
 const idx=Math.min(index,Math.max(0,(view?.objects.length||0)-1));
 idxRef.current=idx;
 if(!view)return <main className="loading">正在恢复任务…</main>;
 const properties=Object.keys(view.ontology.properties);
 const done=view.session.phase==='saved';
 const object=view.objects[idx];
 objectRef.current=object?.id||'';
 const proof=object&&field?object.evidence[field]||[]:[];
 // 原始来源证据优先；只有纠正证据时也传给来源视图显示决定定位，但不定位任何来源行。
 const sourceAnchor=proof.find(e=>!isDecisionEvidence(e))||proof[0];
 const isCorrectionOnly=sourceAnchor?isDecisionEvidence(sourceAnchor):false;
 const profile=(!isCorrectionOnly&&sourceAnchor?view.sources.find(s=>s.source_id===sourceAnchor.source_id):undefined)||view.sources[0];
 // selector 带页序号时按页定位对应来源记录；页码明确但不匹配时不回退，无页码时退回旧逻辑。
 const direct=profile&&sourceAnchor&&!isCorrectionOnly?findAnchorRow(profile,sourceAnchor):undefined;
 const sourceRow=direct?direct.row:(sourceAnchor?-1:0);
 const sourceField=direct?direct.field:field;
 const corrections=view.corrections.filter(c=>object&&c.entity_id===object.id);
 // 同一属性多次纠正时只展示最后一次决定；历史仍保存在预览，用作审计轨迹。
 const latestCorrections=corrections.filter((correction,i)=>!corrections.slice(i+1).some(c=>c.property===correction.property));
 // 来源名：SQLite 上传的显示名在 extensions 里，options 里没有时后端会回退到内部上传路径。
 const sourceName=(sourceId:string)=>{
  const selection=view.session.sources.find(s=>s.source_id===sourceId);
  const uploadName=selection?.extensions?.['dataagent.display_name'];
  if(typeof uploadName==='string'&&uploadName)return uploadName;
  return display((view.sources.find(s=>s.source_id===sourceId)||{}).display_name);
 };
 const submitButton=(label:string)=><button className="secondary" disabled={busy||!object}
  onClick={conflict?confirmConflict:submit}>{conflict?'已核对，重新提交':label}</button>;
 return <main className="workspace"><div className="task-header"><div><div className="eyebrow">采购资料 / 对象页</div><h1>核对业务对象</h1><p className="muted">每个值都带来源定位；三种修改范围分别生效。{done?'接入已保存，对象为只读。':''}</p></div><div className="save-buttons"><button className="secondary" onClick={onBack}>返回映射页</button></div></div>
 <div className="work-grid"><section className="source-panel"><div className="panel-heading"><strong>对象</strong><span className="badge">{view.objects.length} 个对象</span></div>
  <div className="source-tabs">{view.objects.map((entry,i)=><button key={entry.id} className={(i===idx?'active ':'')+'source-tab'} onClick={()=>selectObject(i)}>
   <span>▤</span><span>{String(entry.values[view.ontology.identity_fields?.[0]||'number']??entry.id)}</span>
   {entry.unresolved.length>0&&<span className="badge">{entry.unresolved.length} 项未解决</span>}</button>)}</div>
  {view.objects.length===0&&<div className="empty">生成映射预览后，在这里查看对象。</div>}
  <SourceViewer sessionId={sessionId} profile={profile as SourceProfile|undefined} anchor={sourceAnchor?{source_ref:sourceAnchor.source_id,selector:sourceAnchor.selector}:undefined} recordIndex={sourceRow} sourceField={sourceField}/>
 </section><section className="mapping-panel"><div className="panel-heading"><strong>对象详情</strong><span className="badge">{view.ontology.entity_type}</span></div>
  {object?<><div className="mapping-table-scroll"><table className="mapping-table"><thead><tr><th>Ontology 属性</th><th>当前值</th><th>来源定位</th><th>状态</th></tr></thead><tbody>{properties.map(prop=>{
   const anchors=object.evidence[prop]||[];const corrected=corrections.some(c=>c.property===prop);
   const issue=view.issues.some(i=>i.target===prop);
   const mappingChanged=view.correction_views.some(c=>c.entity_id===object.id&&c.property===prop);
   return <tr key={prop} className={field===prop?'active-mapping':''} onClick={()=>setField(prop)}>
    <td><button className="field-button" onClick={()=>setField(prop)}>{prop}</button>{view.ontology.properties[prop].required&&<span className="required">必需</span>}</td>
    <td data-testid={`object-${prop}`} className="mapped-value">{display(object.values[prop])}</td>
    <td className="object-evidence">{anchors.length?anchors.map((anchor,i)=><div key={i}>{isDecisionEvidence(anchor)?decisionSourceName(anchor.source_id):`${sourceName(anchor.source_id)} · ${locate(anchor.selector)}`}</div>):<span className="muted">无来源定位</span>}</td>
    <td><small className={object.unresolved.includes(prop)||issue||mappingChanged?'warn':'ok'}>{corrected?(mappingChanged?'已纠正 · 映射已变化':'已纠正'):object.unresolved.includes(prop)?'未解决':issue?'需核对':'已核对'}</small></td>
   </tr>;})}</tbody></table></div>
  {corrections.length>0&&<div className="notice"><strong>纠正记录</strong><ul>{latestCorrections.map((correction,i)=><li key={i}>{correction.property} → {display(correction.value)} · {correction.reason}</li>)}</ul>
   {view.correction_views.filter(c=>c.entity_id===object.id).map(c=><div key={c.property} className="correction-conflict" data-testid={`object-correction-${c.property}`}>
    <p><strong>{c.property}</strong>：映射已变化，纠正值仍生效；映射新算得的值为 {display(c.mapping_value)}。</p>
    <button className="secondary" disabled={busy||done} onClick={()=>adopt(c)}>采用新映射值</button></div>)}
  </div>}
  {view.issues.length>0&&<div className="notice amber"><strong>{view.issues.length} 项待核对</strong><ul>{view.issues.slice(0,5).map((issue,i)=><li key={i}>{display(issue.target)} · {display(issue.code)}</li>)}</ul></div>}
  {object.extensions&&<details className="extension-box"><summary>查看扩展字段</summary><pre>{JSON.stringify(object.extensions,null,2)}</pre></details>}</>
  :<div className="empty">选择左侧对象查看值与来源定位。</div>}
 </section><aside className="detail-panel"><div className="panel-heading"><span>修改范围</span><span className="badge">{view.review_state||'未预览'}</span></div><h2>{object?'三种修改范围':'选择一个对象'}</h2>
  <label className="label">修改范围</label><div className="range-options">{ranges.map(([id,label])=><label key={id}><input type="radio" name="object-range" value={id} checked={range===id} onChange={()=>setRange(id)} disabled={done}/>{label}</label>)}</div>
  {done?<p className="help">接入已保存。修订映射请在新建接入中进行。</p>:range==='instance'?<div className="edit-current">
   <label className="label" htmlFor="correction-property">纠正的属性</label>
   <select id="correction-property" value={field} onChange={e=>{setField(e.target.value);touch({property:e.target.value});}}>{properties.map(prop=><option key={prop} value={prop}>{prop}</option>)}</select>
   <label className="label" htmlFor="correction-value">纠正后的值</label><input id="correction-value" aria-label="纠正后的值" value={value} onChange={e=>{setValue(e.target.value);touch({value:e.target.value});}}/>
   <label className="label" htmlFor="correction-reason">修改原因</label><textarea id="correction-reason" rows={3} value={reason} onChange={e=>{setReason(e.target.value);touch({reason:e.target.value});}}/>
   <p className="help">{conflict?'任务已有更新，本编辑已保留。请核对最新值后确认重新提交，或重新载入页面。':'保留来源原值，将本次纠正作为用户证据保存并重新校验。并发修改时过期决定会被拒绝，编辑保留。'}</p>
   {submitButton('保存当前值并校验')}
  </div>:range==='mapping'?<div className="edit-current">
   <p className="help">映射修订作用于同类来源：修改绑定后生成新预览，经核对后保存为新映射修订，不影响已保存的其他对象。</p>
   <dl className="field-comparison"><div><dt>当前映射修订</dt><dd>{view.mapping_revision||'—'}</dd></div><div><dt>对象数</dt><dd>{view.objects.length}</dd></div></dl>
   <button className="secondary" onClick={onBack}>去映射页修订</button>
  </div>:<div className="edit-current">
   <label className="label" htmlFor="draft-property">建议新增的属性名</label><input id="draft-property" aria-label="建议新增的属性名" value={name} onChange={e=>{setName(e.target.value);touch();}}/>
   <label className="label" htmlFor="draft-type">值类型</label>
   <select id="draft-type" aria-label="值类型" value={type} onChange={e=>{setType(e.target.value);touch();}}>{['string','decimal','integer','boolean','date','datetime'].map(kind=><option key={kind} value={kind}>{kind}</option>)}</select>
   <label className="label" htmlFor="draft-reason">修改原因</label><textarea id="draft-reason" rows={3} value={reason} onChange={e=>{setReason(e.target.value);touch({reason:e.target.value});}}/>
   <p className="help">生成本体草案，未经审核不改正式本体（当前 {view.ontology_revision}）。</p>
   {submitButton('提交本体草案')}
  </div>}
  {view.ontology_draft&&<div className="notice"><strong>本体草案待审核</strong><ul>
   <li>{display(view.ontology_draft.property)} · {display(view.ontology_draft.value_type)}</li>
   <li>正式本体仍为 {view.ontology_revision}，草案未生效</li></ul></div>}
 </aside></div>
 </main>;
}
