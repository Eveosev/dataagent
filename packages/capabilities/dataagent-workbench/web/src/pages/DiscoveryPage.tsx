import {useState} from 'react';
import {api,display} from '../client';
import type {View} from '../client';

export type Relationship = {
 id:string; origin:'declared'|'sample_supported'; source_table:string; source_columns:string[];
 target_table:string; target_columns:string[]; matched_rows:number; checked_rows:number;
 sampled:boolean; ambiguous:boolean; cardinality:'one_to_one'|'many_to_one'; name?:string;
};
type Column = {
 name:string; type:string; nullable:boolean; null_rows:number; distinct_values:number;
};
export type Discovery = {
 source_revision?:string; coverage?:string;
 catalog:null|{
  tables:{name:string;rows_observed:number;sampled:boolean;columns:Record<string,Column>;keys:string[][];identity_keys:string[][]}[];
  relationships:Relationship[];gaps:{table?:string;code:string}[];
 };
 draft:null|{
  ref:string; state:'pending'|'approved'|'rejected'; reviewed_draft_ref?:string;
  entities:{name:string;table:string;grain:string;identity:string[];
            properties:{name:string;column:string}[];extension_columns:string[]}[];
  relationships:Relationship[]; unresolved_tables:string[]; unresolved_relationships:Relationship[];
 };
};

function RelationshipList({items}:{items:Relationship[]}){
 return items.length===0?<p className="muted">无关系</p>:<ul className="discovery-links">{items.map(link=>
  <li key={link.id}>
   <div><strong>{link.name}</strong>{link.name&&<span> · </span>}
    <code>{link.source_table}({link.source_columns.join(', ')})</code> → <code>{link.target_table}({link.target_columns.join(', ')})</code>
   </div>
   <small>{link.origin==='declared'?'数据库声明':'观测值匹配'} · {link.cardinality==='one_to_one'?'一对一':'多对一'} · {link.checked_rows
     ?`${link.sampled?'抽样':'观察'}同值 ${link.matched_rows}/${link.checked_rows}`
     :'无可比对值'}
    {link.ambiguous&&' · 多个候选'}
   </small>
  </li>)}</ul>;
}

const gapLabels:Record<string,string>={
 table_not_found:'请求的表不存在',
 declared_fk_target_outside_scope:'外键目标超出探查或披露范围',
 declared_fk_target_key_unverified:'外键目标键无法核对',
 candidate_budget_exceeded:'部分候选超出展示上限',
};

export function DiscoveryPage({view,reload,onNew,onError}:{
 view:View;reload:()=>Promise<void>;onNew:()=>void;onError:(error:unknown)=>void;
}){
 const [busy,setBusy]=useState(false),[copied,setCopied]=useState(false);
 const {session,discovery}=view;
 if(!discovery)return null;
 const {catalog,draft}=discovery;
 const source=session.sources[0];
 const profile=view.profiles[0];
 const recordKeys=profile?.metadata?.record_keys as {table:string}[]|undefined;
 const binaryFields=profile?.metadata?.binary_fields as Record<string,string[]>|undefined;
 const displayName=String(source.extensions?.['dataagent.display_name']||source.locator_ref.split('/').pop());
 const prompt=`继续当前工作区的 SQLite 本体发现任务 ${session.id}。调用 intake_inference 获取当前证据，提出实体、粒度、标识、属性和关系，再用 ontology_discovery_propose 提交草案供我在工作台审核。`;
 const base=`/api/sessions/${session.id}`;
 async function review(decision:'approve'|'reject'){
  if(!draft)return;
  setBusy(true);
  try{
   await api(base+'/discovery/review','POST',{
    decision,draft_ref:draft.ref,expected_revision:session.revision,
   });
   await reload();
  }catch(error){onError(error);}finally{setBusy(false);}
 }
 async function retry(){
  setBusy(true);
  try{await api(base+'/advance','POST',{});await reload();}
  catch(error){onError(error);}finally{setBusy(false);}
 }
 const status=draft?.state==='approved'?'已通过审核':draft?.state==='rejected'?'已退回':
  draft?.state==='pending'?'待审核':catalog?.tables.length?'等待 Agent 提案':
  catalog?'未找到可探查的表':'正在探查';
 return <main className="workspace discovery-page">
  <header className="task-header">
   <div><div className="eyebrow">{displayName}</div><h1>SQLite 本体发现</h1><p className="muted">{status}</p></div>
   <button className="secondary" onClick={onNew}>新建接入</button>
  </header>
  {session.next_actions?.includes('retry_probe')&&<div className="notice amber">
   <p>{String((session.issues?.[0] as {detail?:string}|undefined)?.detail||'来源探查未完成')}</p>
   <button className="secondary" disabled={busy} onClick={retry}>重新探查</button>
  </div>}
  {!!catalog?.tables.length&&(!draft||draft.state==='rejected')&&<section className="discovery-card">
   <h2>生成本体草案</h2><p>在同一个 Mint 工作区发送这条指令。草案提交后会自动显示。</p>
   <div className="discovery-prompt"><code>{prompt}</code><button className="secondary" onClick={()=>
    navigator.clipboard.writeText(prompt).then(()=>setCopied(true)).catch(onError)}>{copied?'已复制':'复制指令'}</button></div>
  </section>}
  {draft&&catalog&&<section className="discovery-card">
   <div className="panel-heading"><h2>本体草案</h2><span className="badge">{status}</span></div>
   <div className="discovery-entities">{draft.entities.map(entity=>{
    const table=catalog.tables.find(item=>item.name===entity.table);
    return <article key={entity.table} className="discovery-entity">
     <h3>{entity.name}</h3><p>{entity.grain}</p>
     <dl><dt>来源表</dt><dd><code>{entity.table}</code></dd>
      <dt>标识</dt><dd>{entity.identity.length?entity.identity.join(' + '):'待确认'}</dd></dl>
     {entity.properties.length>0&&<table className="mapping-table">
      <thead><tr><th>属性</th><th>来源列</th><th>声明类型</th></tr></thead>
      <tbody>{entity.properties.map(prop=><tr key={prop.column}><td>{prop.name}</td>
       <td><code>{prop.column}</code></td><td>{table?.columns[prop.column]?.type||'—'}</td></tr>)}</tbody>
     </table>}
     {entity.extension_columns.length>0&&<p className="muted">保留为扩展字段 · {entity.extension_columns.join(', ')}</p>}
    </article>;
   })}</div>
   <h3>拟采用的关系</h3><RelationshipList items={draft.relationships}/>
   {(draft.unresolved_tables.length>0||draft.unresolved_relationships.length>0)&&<div className="notice amber">
    <strong>待核对</strong>
    {draft.unresolved_tables.length>0&&<p>未建模的表 · {draft.unresolved_tables.join(', ')}</p>}
    {draft.unresolved_relationships.length>0&&<RelationshipList items={draft.unresolved_relationships}/>}
   </div>}
   {draft.state==='pending'&&<div className="discovery-review">
    <button className="secondary" disabled={busy} onClick={()=>review('reject')}>退回草案</button>
    <button className="primary" disabled={busy} onClick={()=>review('approve')}>确认当前草案</button>
   </div>}
  </section>}
  {catalog&&<section className="discovery-card">
   <h2>来源证据</h2>
   <p className="muted">{catalog.tables.length} 张表 · 来源修订 <code title={discovery.source_revision}>{discovery.source_revision?.replace('sha256:','').slice(0,12)}</code></p>
   {catalog.tables.map(table=>{
    const rows=recordKeys?.flatMap((key,index)=>key.table===table.name?[{values:profile.records?.[index],binary:binaryFields?.[index]}]:[]).slice(0,3)||[];
    const fields=Object.values(table.columns);
    return <details key={table.name} className="discovery-table">
    <summary><code>{table.name}</code> <span className="muted">{table.rows_observed} 行{table.sampled?'抽样':'已观察'}</span></summary>
    <p>主键与唯一键 · {table.keys.map(key=>key.join(' + ')).join(' / ')||'未观察到'}</p>
    {table.identity_keys.length<table.keys.length&&<p className="muted">含已观察空值的键不可用作标识。</p>}
    <table className="mapping-table"><thead><tr><th>字段</th><th>声明类型</th><th>空值行</th><th>观测去重值</th>{rows.map((_,index)=><th key={index}>样本 {index+1}</th>)}</tr></thead>
     <tbody>{fields.map(column=><tr key={column.name}>
      <td><code>{column.name}</code></td><td>{column.type||'—'}</td><td>{column.null_rows}</td><td>{column.distinct_values}</td>
      {rows.map((row,index)=><td key={index}>{row.binary?.includes(column.name)?'二进制':display(row.values?.[column.name]).slice(0,160)}</td>)}
     </tr>)}</tbody></table>
   </details>;})}
   {!draft&&<><h3>关系证据</h3><RelationshipList items={catalog.relationships}/></>}
   {catalog.gaps.length>0&&<ul>{catalog.gaps.map((gap,i)=><li key={i}>{gap.table&&gap.table+' · '}{gapLabels[gap.code]||gap.code}</li>)}</ul>}
  </section>}
 </main>;
}
