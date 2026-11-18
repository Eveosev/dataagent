import {useEffect,useRef,useState} from 'react';
import {api,ApiError,display,locate,findAnchorRow,isDecisionEvidence,decisionSourceName,issueBlocksSave,issueObject,issueReasons,propertyLabel,entityTypeLabel,reviewStateNames} from '../client';
import type {CorrectionView,ObjectView,SourceProfile,Issue,WorkObject,ConflictValue,DispositionOption,Selector} from '../client';
import {SourceViewer} from '../components/SourceViewer';

const ranges=[['instance','纠正当前对象的值'],['mapping','修改这类来源的映射'],['ontology','提出本体草案']] as const;
const scopeIds=['instance','mapping','ontology'];

export function ObjectPage({sessionId,onBack,onError}:{sessionId:string;onBack:()=>void;onError:(e:unknown)=>void}){
 const [view,setView]=useState<ObjectView|null>(null),[index,setIndex]=useState(0),[field,setField]=useState('');
 const [range,setRange]=useState('instance'),[value,setValue]=useState(''),[reason,setReason]=useState('');
 const [name,setName]=useState(''),[type,setType]=useState('string'),[busy,setBusy]=useState(false),[conflict,setConflict]=useState(false);
 const [showAllIssues,setShowAllIssues]=useState(false);
 // FDE-12：纠正结果用绿色成功提示或琥珀色「其他对象挡住」说明，不再走红色错误条。
 const [notice,setNotice]=useState<{kind:'green'|'amber';text:string}|null>(null);
 // G2 处置：每个处置一条必填的原因，空白原因不能提交。
 const [disposalReasons,setDisposalReasons]=useState<Record<string,string>>({});
 const [partialReason,setPartialReason]=useState('');
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
  return data;
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
  setIndex(i);setValue('');setReason('');setConflict(false);setNotice(null);
  editing.current=false;editObject.current='';
  sessionStorage.removeItem(localKey);
 }
 async function confirmConflict(){
  setBusy(true);setConflict(false);editing.current=false;
  await load().catch(()=>{});
  editing.current=true;setBusy(false);
 }
 // 整批保存还被哪些对象挡住（FDE-12）：点名对象与属性，供纠正后的琥珀色说明。
 function blockedList(data:ObjectView):string{
  const identity=data.ontology.identity_fields?.[0]||'number';
  const required=Object.entries(data.ontology.properties).filter(([,definition])=>definition.required).map(([prop])=>prop);
  const parts:string[]=[];
  for(const entry of data.objects){
   const label=objectLabel(entry,data);
   const keyValue=entry.values[identity];
   if(keyValue===undefined||keyValue===null||keyValue===''){parts.push(`${label}（缺少单据号）`);continue;}
   for(const prop of required){
    const item=entry.values[prop];
    if(item===undefined||item===null||item==='')parts.push(`${label} · ${propertyLabel(prop)} 缺少必填值`);
   }
  }
  return parts.slice(0,5).join('；')+(parts.length>5?` 等 ${parts.length} 项`:'');
 }
 // 纠正提交后的共同收尾：刷新视图并重新校验；成功给绿色提示，
 // 重新校验被其他对象挡住时点名说明（FDE-12），不走红色错误条。
 async function afterCorrection(prop:string,corrected:unknown){
  const fresh=await load();
  try{
   await api(base_url+'/revalidate','POST',{expected_revision:revision.current});
   await load();
   setNotice({kind:'green',text:`纠正已保存：${propertyLabel(prop)} → ${display(corrected)}，已重新校验。`});
  }catch(error){
   if(error instanceof ApiError&&error.status===409){setConflict(true);onError(error);return;}
   const blocked=blockedList(fresh);
   setNotice({kind:'amber',text:blocked
    ?`纠正已保存：${propertyLabel(prop)} → ${display(corrected)}。整批保存仍被其他问题挡住：${blocked}。`
    :`纠正已保存，但重新校验未通过：${error instanceof Error?error.message:String(error)}`});
  }
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
    sessionStorage.removeItem(localKey);
    const submitted=value;
    setValue('');setReason('');setConflict(false);
    await afterCorrection(field,submitted);
   }else{
    if(!name.trim()||!reason.trim())throw new Error('请填写属性名与原因');
    await api(base_url+'/review','POST',{expected_revision:base.current,decision:{preview_ref:active.preview_ref,
     target_scope:'ontology',changes:{property:name,value_type:type,reason},decision:'save'}});
    editing.current=false;editObject.current='';
   }
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
 // FDE-5：冲突字段一键采用某个来源的原值，作为一次用户纠正保存并重新校验。
 async function adoptSourceValue(prop:string,entry:ConflictValue){
  if(running.current)return;
  running.current=true;setBusy(true);try{
   const active=view;
   if(!active||!object||!active.preview_ref)throw new Error('请先生成映射预览');
   await api(base_url+'/review','POST',{expected_revision:base.current,decision:{preview_ref:active.preview_ref,
    target_scope:'instance',changes:{entity_id:object.id,property:prop,value:entry.value,
     reason:`采用来源「${entry.source_name}」的原值`},decision:'save'}});
   editing.current=false;editObject.current='';
   sessionStorage.removeItem(localKey);
   setValue('');setReason('');setConflict(false);
   await afterCorrection(prop,entry.value);
  }catch(error){
   onError(error);
   if(error instanceof ApiError&&error.status===409)setConflict(true);
   else{editing.current=false;await load().catch(()=>{});}
  }finally{running.current=false;setBusy(false);}
 }
 async function adopt(correction:CorrectionView){
  if(running.current)return;
  running.current=true;setBusy(true);try{
   await api(base_url+'/corrections/adopt','POST',{expected_revision:revision.current,
    entity_id:correction.entity_id,property:correction.property});
   // 采用映射值是一次新的用户决定：清掉本地草稿，以最新修订重新校验。
   editing.current=false;editObject.current='';setValue('');setReason('');setConflict(false);
   sessionStorage.removeItem(localKey);
   await load();
  }catch(error){
   onError(error);
   if(error instanceof ApiError&&error.status===409)setConflict(true);
  }finally{running.current=false;setBusy(false);}
 }
 // G2 处置：被拦问题的出路。处置本身是可审计的决定，原因必填。
 const disposalKey=(option:DispositionOption)=>`${option.action}:${option.source_id}:${option.partition??''}:${option.record??''}`;
 async function submitDisposal(option:DispositionOption,why:string){
  if(running.current)return;
  running.current=true;setBusy(true);try{
   await api(base_url+'/dispositions','POST',{expected_revision:revision.current,
    action:option.action,source_id:option.source_id,
    ...(option.action==='partition_not_applicable'?{partition:option.partition}:{record:option.record}),
    reason:why});
   setDisposalReasons(previous=>({...previous,[disposalKey(option)]:''}));
   setNotice({kind:'green',text:'处置已记录。处置会重新生成预览，请返回映射页重新生成映射预览后核对。'});
   await load();
  }catch(error){onError(error);}finally{running.current=false;setBusy(false);}
 }
 // 只保存无问题对象（G2）：无对象级阻断的对象放行，其余挂起并逐条给出原因。
 async function savePartial(){
  if(running.current)return;
  running.current=true;setBusy(true);try{
   const active=view;
   if(!active||!active.preview_ref)throw new Error('请先生成映射预览');
   await api(base_url+'/review','POST',{expected_revision:revision.current,
    decision:{preview_ref:active.preview_ref,target_scope:'mapping',changes:{},decision:'save'},
    allow_partial:true,reason:partialReason});
   setPartialReason('');
   setNotice({kind:'green',text:'已按部分保存放行无阻断的对象，其余对象挂起并逐条给出原因。'});
   await load();
  }catch(error){
   if(error instanceof ApiError&&error.raw==='preview contains unresolved issues')
    setNotice({kind:'amber',text:'当前工作台服务暂不支持在网页上只保存无问题对象，请更新服务后再试；处置与对象页纠正仍可使用。'});
   else onError(error);
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
 // 待核对问题列出全部（不再截前 5 条）：阻断（对象页纠正解除不了，须修订映射或
 // 来源）排在可纠正前面，头部并列总数与阻断数；超过 10 条时折叠尾部。
 const sortedIssues=[...view.issues].sort((a,b)=>Number(issueBlocksSave(b))-Number(issueBlocksSave(a)));
 const blockingCount=sortedIssues.filter(issueBlocksSave).length;
 // 来源名：SQLite 上传的显示名在 extensions 里，options 里没有时后端会回退到内部上传路径。
 const sourceName=(sourceId:string,data:ObjectView=view)=>{
  const selection=data.session.sources.find(s=>s.source_id===sourceId);
  const uploadName=(selection as {extensions?:Record<string,unknown>}|undefined)?.extensions?.['dataagent.display_name'];
  if(typeof uploadName==='string'&&uploadName)return uploadName;
  return display((data.sources.find(s=>s.source_id===sourceId)||{}).display_name);
 };
 // 缺键对象不显示内部 candidate 哈希，改用来源描述点名（FDE-11）。
 const objectLabel=(entry:WorkObject,data:ObjectView=view)=>{
  const keyValue=entry.values[data.ontology.identity_fields?.[0]||'number'];
  if(keyValue!==undefined&&keyValue!==null&&keyValue!=='')return String(keyValue);
  for(const anchors of Object.values(entry.evidence||{})){
   for(const anchor of anchors){
    if(isDecisionEvidence(anchor))continue;
    return `${sourceName(anchor.source_id,data)} · ${locate(anchor.selector)}（无单号）`;
   }
  }
  return '未识别单据';
 };
 // 问题没有可点的对象时仍要可区分、可处理：行号定位不了的（只有行号、来源不明、
 // 该行在问题来源里没有锚点）一律显示行号与来源待定；无行号的来源级问题点出具体
 // 来源；纠正冲突沿用后端给的对象标签。
 const issueLocation=(issue:Issue)=>{
  if(issue.row!==undefined)return `第 ${issue.row+1} 行 · 来源待定`;
  if(issue.source_id)return sourceName(issue.source_id);
  return issue.object?display(issue.object):'映射层';
 };
 // G2：与该问题对应的来源处置（标记分区不适用 / 排除记录）。
 const issueDisposals=(issue:Issue)=>(view.disposition_options||[]).filter(option=>{
  if(issue.code==='ontology.incomplete_source')
   return option.action==='partition_not_applicable'&&option.source_id===issue.source_id;
  if(['ontology.identity_unresolved','ontology.required_value_missing','ontology.conversion_failed'].includes(issue.code||''))
   return option.action==='exclude_record'&&option.source_id===issue.source_id&&option.record===issue.row;
  return false;
 });
 // 处置记录的定位：与缺单号对象的标签用同一种编号——按该来源记录的锚点算出
 // 「来源行 N」（CSV 记录锚点的 keys.row 是含表头的原始行号），而不是另起一套
 // 「第 N 条记录」；找不到锚点时才退回记录序号。
 const recordLabel=(sourceId:string,record:number|undefined):string=>{
  if(record===undefined)return '该记录';
  const anchorsProfile=view.sources.find(s=>s.source_id===sourceId);
  for(const [key,anchors] of Object.entries(anchorsProfile?.anchors||{})){
   const dot=key.indexOf('.');
   if(dot<0||Number(key.slice(0,dot))!==record)continue;
   const anchor=anchors[0];
   if(anchor)return locate(anchor.selector as Selector);
  }
  return `第 ${record+1} 条记录`;
 };
 const disposalText=(option:DispositionOption)=>option.action==='partition_not_applicable'
  ?`标记「${option.source_name}」分区 ${option.partition} 不适用`
  :`排除「${option.source_name}」${recordLabel(option.source_id,option.record)}`;
 const submitButton=(label:string)=><button className="secondary" disabled={busy||!object}
  onClick={conflict?confirmConflict:submit}>{conflict?'已核对，重新提交':label}</button>;
 return <main className="workspace"><div className="task-header"><div><div className="eyebrow">采购资料 / 对象页</div><h1>核对业务对象</h1><p className="muted">每个值都带来源定位；三种修改范围分别生效。{done?'接入已保存，对象为只读。':''}</p></div><div className="save-buttons"><button className="secondary" onClick={onBack}>返回映射页</button></div></div>
 <div className="work-grid"><section className="source-panel"><div className="panel-heading"><strong>对象</strong><span className="badge">{view.objects.length} 个对象</span></div>
  <div className="source-tabs">{view.objects.map((entry,i)=><button key={entry.id} className={(i===idx?'active ':'')+'source-tab'} onClick={()=>selectObject(i)} title={objectLabel(entry)}>
   <span>▤</span><span>{objectLabel(entry)}</span>
   {entry.unresolved.length>0&&<span className="badge">{entry.unresolved.length} 项未解决</span>}</button>)}</div>
  {view.objects.length===0&&<div className="empty">生成映射预览后，在这里查看对象。</div>}
  <SourceViewer sessionId={sessionId} profile={profile as SourceProfile|undefined} anchor={sourceAnchor?{source_ref:sourceAnchor.source_id,selector:sourceAnchor.selector}:undefined} recordIndex={sourceRow} sourceField={sourceField}/>
 </section><section className="mapping-panel"><div className="panel-heading"><strong>对象详情</strong><span className="badge">{entityTypeLabel(view.ontology.entity_type)}</span></div>
  {object?<><div className="mapping-table-scroll"><table className="mapping-table"><thead><tr><th>本体属性</th><th>当前值</th><th>来源定位</th><th>状态</th></tr></thead><tbody>{properties.map(prop=>{
   const anchors=object.evidence[prop]||[];const corrected=corrections.some(c=>c.property===prop);
   const issue=view.issues.some(i=>i.target===prop);
   const mappingChanged=view.correction_views.some(c=>c.entity_id===object.id&&c.property===prop);
   return <tr key={prop} className={field===prop?'active-mapping':''} onClick={()=>setField(prop)}>
    <td><button className="field-button" title={prop} onClick={()=>setField(prop)}>{propertyLabel(prop)}</button>{view.ontology.properties[prop].required&&<span className="required">必需</span>}</td>
    <td data-testid={`object-${prop}`} className="mapped-value">{display(object.values[prop])}</td>
    <td className="object-evidence">{anchors.length?anchors.map((anchor,i)=><div key={i}>{isDecisionEvidence(anchor)?decisionSourceName(anchor.source_id):`${sourceName(anchor.source_id)} · ${locate(anchor.selector,propertyLabel(prop))}`}</div>):<span className="muted">无来源定位</span>}</td>
    <td><small className={object.unresolved.includes(prop)||issue||mappingChanged?'warn':'ok'}>{corrected?(mappingChanged?'已纠正 · 映射已变化':'已纠正'):object.unresolved.includes(prop)?'未解决':issue?'需核对':'已核对'}</small></td>
   </tr>;})}</tbody></table></div>
  {(object.conflicts||[]).length>0&&<div className="notice amber conflict-values" data-testid="object-conflicts"><strong>字段值冲突</strong>
   {/* 同一字段每个冲突来源各报一条问题，这里按字段归并后并排展示原值。 */}
   {(object.conflicts||[]).filter((conflict,i,all)=>all.findIndex(other=>other.field===conflict.field)===i).map(conflict=><div key={conflict.field} className="conflict-field" data-testid={`object-conflict-${conflict.field}`}>
    <span>{propertyLabel(conflict.field)} · {conflict.reason||issueReasons['ontology.conflicting_values']}</span>
    {conflict.values.map(entry=><div key={`${entry.source_id}:${display(entry.value)}`} className="conflict-source">
     <span>{entry.source_name}：<strong>{display(entry.value)}</strong>{entry.locations.length?`（${entry.locations.join('；')}）`:''}</span>
     <button className="secondary" disabled={busy||done} onClick={()=>adoptSourceValue(conflict.field,entry)}>采用此值</button>
    </div>)}
   </div>)}
   <p className="help">各来源原值并排显示；点「采用此值」把该来源的值作为用户纠正保存并重新校验。</p>
  </div>}
  {corrections.length>0&&<div className="notice"><strong>纠正记录</strong><ul>{latestCorrections.map((correction,i)=><li key={i}>{propertyLabel(correction.property)} → {display(correction.value)} · {correction.reason}</li>)}</ul>
   {view.correction_views.filter(c=>c.entity_id===object.id).map(c=><div key={c.property} className="correction-conflict" data-testid={`object-correction-${c.property}`}>
    <p><strong>{propertyLabel(c.property)}</strong>：映射已变化，纠正值仍生效；映射新算得的值为 {display(c.mapping_value)}。</p>
    <button className="secondary" disabled={busy||done} onClick={()=>adopt(c)}>采用新映射值</button></div>)}
  </div>}
  {object.extensions&&<details className="extension-box"><summary>查看扩展字段</summary><pre>{JSON.stringify(object.extensions,null,2)}</pre></details>}</>
  :<div className="empty">选择左侧对象查看值与来源定位。</div>}
  {notice&&<div className={notice.kind==='green'?'notice green':'notice amber'} data-testid={notice.kind==='green'?'correction-success':'correction-blocked'} role="status">{notice.text}</div>}
  {/* 待核对问题不依赖选中对象：预览没有实例时（如 no_records）仍要全部列出。 */}
  {view.issues.length>0&&<div className="notice amber" data-testid="pending-issues"><strong>{view.issues.length} 项待核对 · 阻断 {blockingCount} 项</strong>
   <ul>{sortedIssues.slice(0,showAllIssues?sortedIssues.length:10).map((issue,i)=>{
    const target=issueObject(issue,view);
    return <li key={i} data-testid="pending-issue"><small className={issueBlocksSave(issue)?'warn':'ok'}>{issueBlocksSave(issue)?'阻断':'可纠正'}</small>
     {' · '}{target?<button className="field-button" onClick={()=>selectObject(view.objects.indexOf(target))}>{objectLabel(target)}</button>:<span className="muted">{issueLocation(issue)}</span>}
     {issue.target?` · ${propertyLabel(issue.target)}`:''} · {issueReasons[issue.code||'']||display(issue.code)}{issue.detail?` · ${display(issue.detail)}`:''}
     {issueDisposals(issue).map(option=><div key={disposalKey(option)} className="disposal" data-testid="disposal-option">
      <span className="muted">{disposalText(option)} · {option.reason_hint}</span>
      <div className="disposal-controls">
       <input aria-label={`处置原因：${disposalText(option)}`} value={disposalReasons[disposalKey(option)]||''} onChange={e=>setDisposalReasons(previous=>({...previous,[disposalKey(option)]:e.target.value}))} placeholder="处置原因（必填，写入审计）"/>
       <button className="secondary" disabled={busy||done||!(disposalReasons[disposalKey(option)]||'').trim()} onClick={()=>submitDisposal(option,disposalReasons[disposalKey(option)])}>提交处置</button>
      </div>
     </div>)}
    </li>;})}</ul>
   {sortedIssues.length>10&&<button className="secondary" onClick={()=>setShowAllIssues(!showAllIssues)}>{showAllIssues?'收起其余问题':`展开其余 ${sortedIssues.length-10} 条`}</button>}
   {(view.dispositions||[]).length>0&&<p className="help">已记录处置：{(view.dispositions||[]).map(entry=>`${sourceName(entry.source_id)} · ${entry.action==='partition_not_applicable'?`分区 ${entry.partition} 标记不适用`:`排除${recordLabel(entry.source_id,entry.record)}`}（${entry.reason}）`).join('；')}</p>}
   {blockingCount>0&&!done&&<div className="disposal" data-testid="partial-save">
    <span className="muted">只保存无问题对象：无对象级阻断的对象先放行，其余对象挂起并逐条给出原因。</span>
    <div className="disposal-controls">
     <input aria-label="部分保存原因" value={partialReason} onChange={e=>setPartialReason(e.target.value)} placeholder="部分保存原因（必填，写入审计）"/>
     <button className="secondary" disabled={busy||!partialReason.trim()} onClick={savePartial}>只保存无问题对象</button>
    </div>
   </div>}
   <p className="help">阻断项不能在对象页解除，需修订映射或来源；可纠正项保存纠正值后自动解除，解除前整批保存同样被拦。</p></div>}
 </section><aside className="detail-panel"><div className="panel-heading"><span>修改范围</span><span className="badge">{reviewStateNames[view.review_state||'']||view.review_state||'未预览'}</span></div><h2>{object?'三种修改范围':'选择一个对象'}</h2>
  <label className="label">修改范围</label><div className="range-options">{ranges.map(([id,label])=><label key={id}><input type="radio" name="object-range" value={id} checked={range===id} onChange={()=>setRange(id)} disabled={done}/>{label}</label>)}</div>
  {done?<p className="help">接入已保存。修订映射请在新建接入中进行。</p>:range==='instance'?<div className="edit-current">
   <label className="label" htmlFor="correction-property">纠正的属性</label>
   <select id="correction-property" value={field} onChange={e=>{setField(e.target.value);touch({property:e.target.value});}}>{properties.map(prop=><option key={prop} value={prop}>{propertyLabel(prop)}</option>)}</select>
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
