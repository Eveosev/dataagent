import {useEffect,useState} from 'react';
import {api,translateError} from '../client';
type Source={source_id:string;kind:'file'|'sqlite'|'postgres'|'rest';locator_ref:string;options?:Record<string,string>};
type Connection={id:string;kind:'postgres'|'rest';label:string};
export function IntakePage({onStart,onError}:{onStart:(id:string)=>void;onError:(error:unknown)=>void}){
 const [goal,setGoal]=useState('');const [files,setFiles]=useState<File[]>([]);const [busy,setBusy]=useState(false);
 const [connections,setConnections]=useState<Connection[]>([]);
 const [selected,setSelected]=useState<string[]>([]);
 const [discover,setDiscover]=useState(false);
 const canDiscover=files.length===1&&/\.(db|sqlite3?)$/i.test(files[0].name)&&selected.length===0;
 const mode=discover&&canDiscover?'ontology_discovery':'mapping';
 useEffect(()=>{api<Connection[]>('/api/connections').then(setConnections).catch(onError);},[]);
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
   const result=await api<{session_id:string}>('/api/sessions','POST',{goal,sources,mode});onStart(result.session_id);
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
   <label><input type="radio" name="intake-mode" checked={!discover} onChange={()=>setDiscover(false)}/>映射到采购资料</label>
   <label><input type="radio" name="intake-mode" checked={discover} onChange={()=>setDiscover(true)}/>从数据库发现本体</label>
  </fieldset>}
  {mode==='mapping'&&<div className="target-note"><span className="dot"/>目标本体 · 采购资料</div>}
  <button className="primary" disabled={!goal.trim()||(!files.length&&!selected.length)||busy} onClick={start}>{busy?'正在添加材料…':'开始接入'}</button></section>
 </main>;
}
