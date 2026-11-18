import {useEffect,useState} from 'react';
import {api,translateError,originNames,ontologyStateNames,registryTitle} from '../client';
import type {Registry,RegistryEntry} from '../client';

// 本体库：工作区注册表（内置 / 发现发布 / 已停用）。停用只作用于新任务的默认
// 选择（原因必填、二次确认），内置本体是工作区兜底，不提供停用。
export function OntologiesPage({onNew,onBack,onError}:{onNew:()=>void;onBack?:()=>void;onError:(error:unknown)=>void}){
 const [registry,setRegistry]=useState<Registry|null>(null),[busy,setBusy]=useState(false);
 const [retiring,setRetiring]=useState<RegistryEntry|null>(null),[reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false);
 const [failure,setFailure]=useState<string|null>(null);
 async function load(){setRegistry(await api<Registry>('/api/ontologies'));}
 useEffect(()=>{load().catch(onError);},[]);
 async function retire(){
  const entry=retiring;
  if(!entry)return;
  setBusy(true);
  try{
   await api(`/api/ontologies/${entry.id}/retire`,'POST',{
    reason,confirmed:true,expected_revision:entry.registry_revision});
   setRetiring(null);setReason('');setConfirmed(false);setFailure(null);
   await load();
  }catch(error){
   setFailure(error instanceof Error?translateError(error.message):String(error));
  }finally{setBusy(false);}
 }
 const entries=registry?.ontologies||[];
 return <main className="workspace ontology-page">
  <header className="task-header">
   <div><div className="eyebrow">本体库 / 工作区注册表</div><h1>本体</h1>
    <p className="muted">新任务从这里选择映射目标；默认目标由最近一次发布或内置兜底决定。</p></div>
   <div className="save-buttons">
    {onBack&&<button className="secondary" onClick={onBack}>返回任务</button>}
    <button className="secondary" disabled={busy} onClick={()=>load().catch(onError)}>刷新</button>
    <button className="secondary" onClick={onNew}>新建接入</button>
   </div>
  </header>
  {retiring&&<div className="notice amber" data-testid="retire-form">
   <p><strong>停用 {registryTitle(retiring)}</strong>（{retiring.id} · 修订 {retiring.ontology_revision}）</p>
   <p className="help">停用后新任务不再默认选用该本体；既有任务、已发布修订与实例不删除。</p>
   {failure&&<p className="problem-text" data-testid="retire-failure">{failure}</p>}
   <label className="label" htmlFor="retire-reason">停用原因（必填，写入审计）</label>
   <textarea id="retire-reason" rows={2} value={reason} onChange={e=>setReason(e.target.value)} placeholder="例如：并入新的销售模型修订"/>
   <label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> 我确认停用该本体，新任务将不再默认选用</label>
   <div className="disposal-controls">
    <button className="secondary" disabled={busy} onClick={()=>{setRetiring(null);setReason('');setConfirmed(false);setFailure(null);}}>取消</button>
    <button className="primary" disabled={busy||!reason.trim()||!confirmed} onClick={retire}>确认停用</button>
   </div>
  </div>}
  <section className="discovery-card">
   {entries.length===0?<p className="muted">正在读取注册表…</p>:
   <div className="mapping-table-scroll"><table className="mapping-table" data-testid="ontology-entries">
    <thead><tr><th>名称</th><th>修订</th><th>来源</th><th>概念</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>{entries.map(entry=><tr key={entry.id} data-testid={`ontology-${entry.id}`}>
     <td><strong>{registryTitle(entry)}</strong><small><code>{entry.id}</code>{entry.published_at?` · 发布于 ${entry.published_at.slice(0,10)}`:''}</small></td>
     <td>{entry.ontology_revision}</td>
     <td><span className="badge">{originNames[entry.origin]||entry.origin}</span></td>
     <td>{entry.concepts.length>1?`${entry.concepts.length} 个概念 · ${entry.concepts.join('、')}`:entry.concepts[0]||'—'}</td>
     <td><span className="badge">{ontologyStateNames[entry.state]||entry.state}</span>
      {entry.is_default&&entry.state==='active'&&<small className="ok">新任务默认</small>}
      {entry.state==='retired'&&<small className="warn">{entry.retire_reason||''}</small>}</td>
     <td>{entry.origin==='discovery'&&entry.state==='active'
      ?<button className="secondary" disabled={busy||!!retiring} onClick={()=>{setRetiring(entry);setReason('');setConfirmed(false);setFailure(null);}}>停用</button>
      :<span className="muted">{entry.origin==='builtin'?'内置兜底':'—'}</span>}</td>
    </tr>)}</tbody>
   </table></div>}
   <p className="help">发现发布的本体在服务端经人工确认通道发布；停用是可审计的决定，保留全部已发布修订与实例。</p>
  </section>
 </main>;
}
