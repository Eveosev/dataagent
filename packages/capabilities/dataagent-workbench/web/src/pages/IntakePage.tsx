import {useEffect,useState} from 'react';
import {api,translateError,registryTitle} from '../client';
import type {Registry} from '../client';
type Source={source_id:string;kind:'file'|'sqlite'|'postgres'|'rest';locator_ref:string;options?:Record<string,string>};
type Connection={id:string;kind:'postgres'|'rest';label:string};
export function IntakePage({onStart,onError}:{onStart:(id:string)=>void;onError:(error:unknown)=>void}){
 const [goal,setGoal]=useState('');const [files,setFiles]=useState<File[]>([]);const [busy,setBusy]=useState(false);
 const [connections,setConnections]=useState<Connection[]>([]);
 const [selected,setSelected]=useState<string[]>([]);
 const [discover,setDiscover]=useState(false);
 // 目标本体：默认按注册表当前指针（is_default），多概念本体再选概念；
 // 已停用本体不出现在选项里。发现模式不固定映射目标。
 const [activeOntologies,setActiveOntologies]=useState<Registry['ontologies']>([]);
 const [targetOntology,setTargetOntology]=useState(''),[targetConcept,setTargetConcept]=useState('');
 useEffect(()=>{api<Registry>('/api/ontologies').then(data=>{
  const active=data.ontologies.filter(entry=>entry.state==='active');
  setActiveOntologies(active);
  const def=active.find(entry=>entry.is_default)||active[0];
  if(def){setTargetOntology(def.id);setTargetConcept(def.default_concept||def.concepts[0]||'');}
 }).catch(onError);},[]);
 useEffect(()=>{api<Connection[]>('/api/connections').then(setConnections).catch(onError);},[]);
 const selectedEntry=activeOntologies.find(entry=>entry.id===targetOntology);
 const canDiscover=files.length===1&&/\.(db|sqlite3?)$/i.test(files[0].name)&&selected.length===0;
 const mode=discover&&canDiscover?'ontology_discovery':'mapping';
 async function start(){
  setBusy(true);
  try{
   const sources:Source[]=connections.filter(connection=>selected.includes(connection.id)).map(connection=>({
    source_id:crypto.randomUUID(),kind:connection.kind,locator_ref:connection.id,
   }));
   for(const file of files){
    const response=await fetch('/api/files',{method:'POST',body:file,credentials:'same-origin',headers:{'x-file-name':encodeURIComponent(file.name)}});
    if(!response.ok){const detail=(await response.json()).detail;throw new Error(typeof detail==='string'?translateError(detail):'材料上传未完成');}
    sources.push(await response.json());
   }
   const result=await api<{session_id:string}>('/api/sessions','POST',{
    goal,sources,mode,
    ...(mode==='mapping'&&targetOntology?{target:{ontology_id:targetOntology,
     ...(targetConcept?{concept:targetConcept}:{})}}:{})});
   onStart(result.session_id);
  }catch(error){onError(error);}finally{setBusy(false);}
 }
 return <main className="intake-home"><div className="eyebrow">多源接入 · 本地工作区</div><h1>接入数据</h1><p className="muted">添加材料，查看探查结果并核对 Ontology 映射。</p>
  <section className="intake-card"><label className="label" htmlFor="goal">接入目标</label><textarea id="goal" value={goal} onChange={e=>setGoal(e.target.value)} placeholder="例如：接入采购发票，核对单据编号、金额和币种" rows={3}/>
  <div className="file-drop"><span className="upload-mark">＋</span><strong>添加本地材料</strong><p>PDF、Excel、Word、CSV、JSON、SQLite · 每份材料不超过 32 MB</p><input aria-label="选择材料" type="file" multiple accept=".pdf,.xlsx,.xlsm,.csv,.tsv,.json,.jsonl,.docx,.sqlite,.sqlite3,.db" onChange={e=>setFiles(Array.from(e.target.files||[]))}/></div>
  {files.length>0&&<ul className="file-list">{files.map((file,index)=><li key={index}><span>▤ {file.name}</span><span className="muted">{Math.max(1,Math.round(file.size/1024))} KB</span></li>)}</ul>}
  {connections.length>0&&<fieldset><legend>已配置连接</legend>{connections.map(connection=><div key={connection.id}>
   <label><input type="checkbox" checked={selected.includes(connection.id)} onChange={e=>{
    setSelected(previous=>e.target.checked?[...previous,connection.id]:previous.filter(id=>id!==connection.id));
   }}/> {connection.label} · {connection.kind==='postgres'?'PostgreSQL':'REST API'}</label>
  </div>)}</fieldset>}
  {canDiscover&&<fieldset className="intake-mode"><legend>接入方式</legend>
   <label><input type="radio" name="intake-mode" checked={!discover} onChange={()=>setDiscover(false)}/>映射到已有本体</label>
   <label><input type="radio" name="intake-mode" checked={discover} onChange={()=>setDiscover(true)}/>从数据库发现本体</label>
  </fieldset>}
  {mode==='mapping'&&<fieldset className="intake-mode"><legend>目标本体</legend>
   <label className="label" htmlFor="target-ontology">映射到的本体</label>
   <select id="target-ontology" value={targetOntology} onChange={e=>{
    setTargetOntology(e.target.value);
    const entry=activeOntologies.find(item=>item.id===e.target.value);
    setTargetConcept(entry?(entry.default_concept||entry.concepts[0]||''):'');
   }}>{activeOntologies.map(entry=><option key={entry.id} value={entry.id}>{registryTitle(entry)}{entry.is_default?'（默认）':''}</option>)}</select>
   {selectedEntry&&selectedEntry.concepts.length>1&&<>
    <label className="label" htmlFor="target-concept">目标概念</label>
    <select id="target-concept" value={targetConcept} onChange={e=>setTargetConcept(e.target.value)}>
     {selectedEntry.concepts.map(concept=><option key={concept} value={concept}>{concept}</option>)}
    </select></>}
  </fieldset>}
  {mode==='mapping'&&selectedEntry&&<div className="target-note"><span className="dot"/>目标本体 · {registryTitle(selectedEntry)}{selectedEntry.concepts.length>1&&targetConcept?` · ${targetConcept}`:''}</div>}
  <button className="primary" disabled={!goal.trim()||(!files.length&&!selected.length)||busy} onClick={start}>{busy?'正在添加材料…':'开始接入'}</button></section>
 </main>;
}
