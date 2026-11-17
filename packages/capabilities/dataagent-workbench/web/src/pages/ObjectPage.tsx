import {useEffect,useRef,useState} from 'react';
import {api,display,locate} from '../client';
import type {ObjectView,SourceProfile} from '../client';
import {SourceViewer} from '../components/SourceViewer';

const ranges=[['instance','纠正当前对象的值'],['mapping','修改这类来源的映射'],['ontology','提出本体草案']] as const;

export function ObjectPage({sessionId,onBack,onError}:{sessionId:string;onBack:()=>void;onError:(e:unknown)=>void}){
 const [view,setView]=useState<ObjectView|null>(null),[index,setIndex]=useState(0),[field,setField]=useState('');
 const [range,setRange]=useState('instance'),[value,setValue]=useState(''),[reason,setReason]=useState('');
 const [name,setName]=useState(''),[type,setType]=useState('string'),[busy,setBusy]=useState(false);
 const revision=useRef(''),base=useRef(''),editing=useRef(false),initialized=useRef(false),running=useRef(false);
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
     const saved=JSON.parse(pending) as {property:string;value:string;reason:string};
     if(saved.value||saved.reason){
      setValue(saved.value);setReason(saved.reason);
      if(saved.property&&properties.includes(saved.property))setField(saved.property);
      editing.current=true;
     }
    }catch{sessionStorage.removeItem(localKey);}
   }
  }
 }
 useEffect(()=>{load().catch(onError);const timer=setInterval(()=>load().catch(onError),1500);return()=>clearInterval(timer);},[sessionId]);
 function touch(next:{property?:string;value?:string;reason?:string}={}){
  if(!editing.current){editing.current=true;base.current=revision.current;}
  sessionStorage.setItem(localKey,JSON.stringify({property:next.property??field,
   value:next.value??value,reason:next.reason??reason,revision:base.current}));
 }
 async function submit(){
  if(running.current)return;
  running.current=true;setBusy(true);try{
   const active=view;
   if(!active||!object||!active.preview_ref)throw new Error('请先生成映射预览');
   if(range==='instance'){
    if(!field||!value.trim()||!reason.trim())throw new Error('请填写纠正值与原因');
    await api(base_url+'/review','POST',{expected_revision:base.current,decision:{preview_ref:active.preview_ref,
     target_scope:'instance',changes:{entity_id:object.id,property:field,value,reason},decision:'save'}});
    editing.current=false;await load();
    await api(base_url+'/revalidate','POST',{expected_revision:revision.current});
   }else{
    if(!name.trim()||!reason.trim())throw new Error('请填写属性名与原因');
    await api(base_url+'/review','POST',{expected_revision:base.current,decision:{preview_ref:active.preview_ref,
     target_scope:'ontology',changes:{property:name,value_type:type,reason},decision:'save'}});
   }
   setValue('');setReason('');editing.current=false;
   sessionStorage.removeItem(localKey);
   await load();
  }catch(error){onError(error);editing.current=false;await load().catch(()=>{});}finally{running.current=false;setBusy(false);}
 }
 if(!view)return <main className="loading">正在恢复任务…</main>;
 const properties=Object.keys(view.ontology.properties);
 const done=view.session.phase==='saved';
 const idx=Math.min(index,Math.max(0,view.objects.length-1));
 const object=view.objects[idx];
 const proof=object&&field?object.evidence[field]||[]:[];
 const current=proof[0];
 const profile=(current?view.sources.find(s=>s.source_id===current.source_id):undefined)||view.sources[0];
 const direct=profile&&current?Object.entries(profile.anchors||{}).find(([key,anchors])=>
  anchors.some(anchor=>anchor.source_ref===current.source_id&&JSON.stringify(anchor.selector)===JSON.stringify(current.selector))):undefined;
 const sourceRow=direct?Number(direct[0].split('.',1)[0]):0;
 const sourceField=direct?direct[0].split('.').slice(1).join('.'):field;
 const corrections=view.corrections.filter(c=>object&&c.entity_id===object.id);
 return <main className="workspace"><div className="task-header"><div><div className="eyebrow">采购资料 / 对象页</div><h1>核对业务对象</h1><p className="muted">每个值都带来源定位；三种修改范围分别生效。{done?'接入已保存，对象为只读。':''}</p></div><div className="save-buttons"><button className="secondary" onClick={onBack}>返回映射页</button></div></div>
 <div className="work-grid"><section className="source-panel"><div className="panel-heading"><strong>对象</strong><span className="badge">{view.objects.length} 个对象</span></div>
  <div className="source-tabs">{view.objects.map((entry,i)=><button key={entry.id} className={(i===idx?'active ':'')+'source-tab'} onClick={()=>setIndex(i)}>
   <span>▤</span><span>{String(entry.values[view.ontology.identity_fields?.[0]||'number']??entry.id)}</span>
   {entry.unresolved.length>0&&<span className="badge">{entry.unresolved.length} 项未解决</span>}</button>)}</div>
  {view.objects.length===0&&<div className="empty">生成映射预览后，在这里查看对象。</div>}
  <SourceViewer sessionId={sessionId} profile={profile as SourceProfile|undefined} anchor={current?{source_ref:current.source_id,selector:current.selector}:undefined} recordIndex={sourceRow} sourceField={sourceField}/>
 </section><section className="mapping-panel"><div className="panel-heading"><strong>对象详情</strong><span className="badge">{view.ontology.entity_type}</span></div>
  {object?<><div className="mapping-table-scroll"><table className="mapping-table"><thead><tr><th>Ontology 属性</th><th>当前值</th><th>来源定位</th><th>状态</th></tr></thead><tbody>{properties.map(prop=>{
   const anchors=object.evidence[prop]||[];const corrected=corrections.some(c=>c.property===prop);
   const issue=view.issues.some(i=>i.target===prop);
   return <tr key={prop} className={field===prop?'active-mapping':''} onClick={()=>setField(prop)}>
    <td><button className="field-button" onClick={()=>setField(prop)}>{prop}</button>{view.ontology.properties[prop].required&&<span className="required">必需</span>}</td>
    <td data-testid={`object-${prop}`} className="mapped-value">{display(object.values[prop])}</td>
    <td className="object-evidence">{anchors.length?anchors.map((anchor,i)=><div key={i}>{display((view.sources.find(s=>s.source_id===anchor.source_id)||{}).display_name)} · {locate(anchor.selector)}</div>):<span className="muted">无来源定位</span>}</td>
    <td><small className={object.unresolved.includes(prop)||issue?'warn':'ok'}>{corrected?'已纠正':object.unresolved.includes(prop)?'未解决':issue?'需核对':'已核对'}</small></td>
   </tr>;})}</tbody></table></div>
  {corrections.length>0&&<div className="notice"><strong>纠正记录</strong><ul>{corrections.map((correction,i)=><li key={i}>{correction.property} → {display(correction.value)} · {correction.reason}</li>)}</ul></div>}
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
   <p className="help">保留来源原值，将本次纠正作为用户证据保存并重新校验。并发修改时过期决定会被拒绝，编辑保留；重新载入后可再提交。</p>
   <button className="secondary" disabled={busy||!object} onClick={submit}>保存当前值并校验</button>
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
   <button className="secondary" disabled={busy||!object} onClick={submit}>提交本体草案</button>
  </div>}
  {view.ontology_draft&&<div className="notice"><strong>本体草案待审核</strong><ul>
   <li>{display(view.ontology_draft.property)} · {display(view.ontology_draft.value_type)}</li>
   <li>正式本体仍为 {view.ontology_revision}，草案未生效</li></ul></div>}
 </aside></div>
 </main>;
}
