import {useEffect,useRef,useState} from 'react';
import {api,ApiError,display,humanDetail,technicalDetail} from '../client';
import type {View,PublishCandidate,PublishDisposition} from '../client';
import type {IntakeSession} from '../generated/IntakeSession';

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
 publish_candidate?:{ref:string;state?:string;ontology_id?:string;ontology_revision?:string}|null;
 catalog:null|{
  tables:{name:string;source_id?:string;rows_observed:number;sampled:boolean;columns:Record<string,Column>;keys:string[][];identity_keys:string[][]}[];
  relationships:Relationship[];gaps:{table?:string;code:string}[];
 };
 draft:null|{
  ref:string; state:'pending'|'approved'|'rejected'; reviewed_draft_ref?:string;
  entities:{name:string;table:string;grain:string;identity:string[];
            properties:{name:string;column:string}[];extension_columns:string[]}[];
  relationships:Relationship[]; unresolved_tables:string[]; unresolved_relationships:Relationship[];
  gaps?:{ref?:string;table?:string;code:string}[]; coverage?:string;
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
const coverageNames:Record<string,string>={sampled:'抽样观察',partial:'部分读取',unknown:'覆盖未知'};
const dispositionKindNames:Record<string,string>={unresolved_table:'未建模的表',unresolved_relationship:'未采用的关系',coverage_gap:'覆盖缺口',coverage:'来源覆盖'};
type OpenItem={kind:string;ref:string;label:string};
// 草案里的未决项与覆盖缺口：发布前必须逐项排除或接受（D1 门禁在服务端复核，
// 这里先点名给用户核对）。
function openItems(draft:NonNullable<Discovery['draft']>):OpenItem[]{
 const items:OpenItem[]=[];
 for(const table of draft.unresolved_tables||[])
  items.push({kind:'unresolved_table',ref:String(table),label:`未建模的表 ${table}`});
 for(const link of draft.unresolved_relationships||[])
  items.push({kind:'unresolved_relationship',ref:String(link.id),
   label:`未采用的关系 ${link.name||`${link.source_table} → ${link.target_table}`}`});
 for(const gap of draft.gaps||[])
  items.push({kind:'coverage_gap',ref:String(gap.ref||''),label:`覆盖缺口 ${gap.table?gap.table+' · ':''}${gapLabels[gap.code]||gap.code}`});
 const coverage=draft.coverage||'unknown';
 if(coverage!=='full')
  items.push({kind:'coverage',ref:coverage,label:`来源覆盖 ${coverageNames[coverage]||coverage}`});
 return items;
}
const shortDigest=(value:string|undefined)=>value?value.replace('sha256:','').slice(0,12):'—';

// 草案通过审核后的发布区块：候选定义摘要、来源快照摘要、未决项处置状态；
// 未处置项点名并阻断，确认由人勾选后提交（网页是唯一确认通道）。
function PublishBlock({session,discovery,reload,onError,onOpenSession,onOpenOntologies}:{
 session:IntakeSession;discovery:Discovery;reload:()=>Promise<void>;
 onError:(error:unknown)=>void;onOpenSession:(id:string)=>void;onOpenOntologies?:()=>void;
}){
 const draft=discovery.draft!;
 const base=`/api/sessions/${session.id}`;
 const [candidate,setCandidate]=useState<PublishCandidate|null>(null),[checked,setChecked]=useState(false),[busy,setBusy]=useState(false);
 const [failure,setFailure]=useState<{text:string;action:'rediscover'|'refresh'}|null>(null),[copied,setCopied]=useState(false);
 const [staleHint,setStaleHint]=useState(false);
 // 记录被后端按过期拒绝的候选引用；只有换到不同且一致的候选才清除过期标记。
 const rejectedRef=useRef('');
 const summary=discovery.publish_candidate||null;
 const fetchCandidate=async()=>setCandidate(await api<PublishCandidate|null>(base+'/publish/candidate'));
 useEffect(()=>{let cancelled=false;
  (async()=>{try{const data=await api<PublishCandidate|null>(base+'/publish/candidate');if(!cancelled)setCandidate(data);}
   catch(error){if(!cancelled)onError(error);}})();
  return()=>{cancelled=true;};
 },[summary?.ref,summary?.state]);
 // 候选替换（引用或定义摘要变化）时重置人工核对勾选：核对必须绑定实际确认的候选，
 // 不能用对旧定义的确认发布新定义。
 useEffect(()=>{setChecked(false);},[candidate?.ref,candidate?.definition_digest]);
 // 刷新取得与被拒候选不同、且与当前任务修订一致的候选时清除过期标记，发布流程可恢复；
 // 候选仍过期时派生校验会继续禁用确认。
 useEffect(()=>{
  if(staleHint&&candidate&&candidate.ref!==rejectedRef.current
   &&candidate.draft_ref===draft.ref&&String(candidate.session_revision)===String(session.revision))
   setStaleHint(false);
 },[staleHint,candidate,session.revision,draft.ref]);
 const published=summary?.state==='published';
 // 候选必须锚定当前草案；草案更新后的旧候选不可确认。
 const current=candidate&&candidate.draft_ref===draft.ref?candidate:null;
 // 过期候选（D1 会拒绝）：任务修订已越过候选记录的修订时，确认被禁用并提示
 // 重新准备，避免反复提交同一失效候选。
 const expired=staleHint||(!!current&&String(current.session_revision)!==String(session.revision));
 const items=openItems(draft);
 const dispositionOf=(item:OpenItem)=>(current?.dispositions||[]).find((entry:PublishDisposition)=>entry.kind===item.kind&&entry.ref===item.ref);
 const undisposed=items.filter(item=>!dispositionOf(item));
 const completionPrompt=`继续当前工作区的本体发现任务 ${session.id}。草案 ${draft.ref} 已通过审核；调用 ontology_publish_prepare 补全每个概念的属性值类型、必需性与身份字段，对关系给出端点与角色，并对未决项与覆盖缺口逐项给出排除或接受的处置，生成发布候选供我在工作台确认。`;
 async function confirm(){
  if(!current||expired)return;
  setBusy(true);
  try{
   await api(base+'/publish/confirm','POST',{
    candidate_ref:current.ref,draft_ref:current.draft_ref,
    source_snapshot:current.source_snapshot,definition_digest:current.definition_digest,
    expected_revision:session.revision,confirmed:true,reason:'工作台人工确认发布',
   });
   setChecked(false);setFailure(null);
   await reload();await fetchCandidate();
  }catch(error){
   // 来源变更给新建发现任务入口；过期/重复确认给刷新候选入口，并标记候选
   // 已过期，避免「刷新候选」后反复提交同一失效候选。
   const raw=error instanceof ApiError?error.raw:'';
   if(/stale|task changed|draft changed|definition changed|does not name the prepared/.test(raw)){
    rejectedRef.current=current?.ref||'';setStaleHint(true);
   }
   setFailure({text:error instanceof Error?error.message:String(error),
    action:/discover again/.test(raw)?'rediscover':'refresh'});
  }finally{setBusy(false);}
 }
 // 来源变更后的出路：已审核的发现任务（phase saved）不能重新探查，后端也没有
 // 重开任务修订的接口；用相同来源新建发现任务，由新任务重新观察变更后的来源。
 async function startRediscovery(){
  setBusy(true);
  try{
   const sources=session.sources.map(source=>({
    source_id:crypto.randomUUID(),kind:source.kind,locator_ref:source.locator_ref,
    ...(source.options?{options:source.options}:{}),
    ...(source.extensions?{extensions:source.extensions}:{}),
   }));
   const result=await api<{session_id:string}>('/api/sessions','POST',{
    goal:`来源已变更，重新发现本体（原任务 ${session.id}）`,sources,mode:'ontology_discovery'});
   onOpenSession(result.session_id);
  }catch(error){onError(error);}finally{setBusy(false);}
 }
 async function refreshCandidate(){
  setBusy(true);
  try{await reload();await fetchCandidate();setFailure(null);}
  catch(error){onError(error);}finally{setBusy(false);}
 }
 if(published)
  return <section className="discovery-card" data-testid="publish-card"><div className="panel-heading"><h2>发布为本体</h2><span className="badge">已发布</span></div>
   <div className="notice green" data-testid="publish-done">草案已发布为正式本体 <code>{summary?.ontology_id}</code>（修订 {summary?.ontology_revision}），新任务将默认使用它。
    {onOpenOntologies&&<button className="secondary" onClick={onOpenOntologies}>查看本体库</button>}</div>
  </section>;
 return <section className="discovery-card" data-testid="publish-card"><div className="panel-heading"><h2>发布为本体</h2><span className="badge">{current?'待人工确认':'待补全'}</span></div>
  {failure&&<div className="notice amber" data-testid="publish-failure"><p>{failure.text}</p>
   {failure.action==='rediscover'?<>
    <p className="help">该发现任务的草案已审核，无法在原任务上重新探查来源；需用相同来源新建发现任务，由新任务重新观察变更后的来源。</p>
    <button className="secondary" disabled={busy} onClick={startRediscovery}>用相同来源新建发现任务</button>
   </>:<button className="secondary" disabled={busy} onClick={refreshCandidate}>刷新候选</button>}
  </div>}
  {expired&&current&&<div className="notice amber" data-testid="publish-stale">
   <p>候选已过期：任务修订已更新，后端会拒绝该候选。请让 Agent 重新调用 ontology_publish_prepare 生成新候选后再确认。</p>
  </div>}
  {current?<><h3>候选定义摘要 · {current.title||current.ontology_id}</h3>
   <div className="discovery-entities">{Object.entries(current.definition.concepts).map(([name,concept])=>
    <article key={name} className="discovery-entity" data-testid={`publish-concept-${name}`}>
     <h3>{name}</h3><dl><dt>实体类型</dt><dd><code>{concept.entity_type}</code></dd>
      <dt>身份字段</dt><dd>{concept.identity_fields.join(' + ')}</dd></dl>
     <table className="mapping-table"><thead><tr><th>属性</th><th>值类型</th><th>必需</th></tr></thead>
      <tbody>{Object.entries(concept.properties).map(([prop,definition])=><tr key={prop}>
       <td>{prop}</td><td>{definition.value_type}</td><td>{definition.required?'必需':'可选'}</td></tr>)}</tbody>
     </table>
    </article>)}</div>
   {Object.keys(current.definition.relations||{}).length>0&&<><h3>拟登记的关系</h3>
    <ul className="discovery-links">{Object.entries(current.definition.relations).map(([name,relation])=>{
     const roles=Array.isArray(relation)?relation:relation.roles;
     return <li key={name}><div><strong>{name}</strong> · <code>{Array.isArray(relation)?name:relation.subject_concept}</code>（{roles[0]}） → <code>{Array.isArray(relation)?name:relation.object_concept}</code>（{roles[1]}）</div></li>;
    })}</ul></>}
   <h3>来源快照摘要</h3>
   <dl className="publish-snapshot"><div><dt>来源修订</dt><dd><code title={current.source_revision}>{shortDigest(current.source_revision)}</code></dd></div>
    <div><dt>结构指纹</dt><dd><code title={current.structure_fingerprint}>{shortDigest(current.structure_fingerprint)}</code></dd></div>
    <div><dt>快照摘要</dt><dd><code title={current.source_snapshot}>{shortDigest(current.source_snapshot)}</code></dd></div>
    <div><dt>本体标识</dt><dd><code>{current.ontology_id}</code> · 修订 {current.ontology_revision}</dd></div></dl>
  </>:<div className="notice amber"><p>草案已通过审核。让 Agent 补全值类型、必需性与身份字段并生成发布候选后，在这里人工确认发布；Agent 工具不能代为确认。</p>
   <div className="discovery-prompt"><code>{completionPrompt}</code><button className="secondary" onClick={()=>
    navigator.clipboard.writeText(completionPrompt).then(()=>setCopied(true)).catch(onError)}>{copied?'已复制':'复制指令'}</button></div>
  </div>}
  <h3>未决项与覆盖缺口</h3>
  {items.length>0?<ul className="publish-items" data-testid="publish-open-items">{items.map(item=>{
   const disposition=dispositionOf(item);
   return <li key={`${item.kind}:${item.ref}`} data-testid="publish-open-item">
    {item.label} · {disposition
     ?<span className="ok">{disposition.action==='exclude'?'已排除':'已接受'}（{disposition.reason}）</span>
     :<span className="warn">未处置</span>}
   </li>;})}</ul>:<p className="muted">无未决项与覆盖缺口。</p>}
  {undisposed.length>0&&<div className="notice amber" data-testid="publish-blocked">
   <p>有 {undisposed.length} 项未处置，发布前必须逐项排除或接受：{undisposed.map(item=>item.label).join('；')}。请在补全指令中给出处置。</p>
  </div>}
  <p className="help">发布后将成为新任务的默认目标本体；既有任务与已发布实例不受影响。</p>
  <div className="discovery-review">
   <label><input type="checkbox" checked={checked} disabled={!current||undisposed.length>0||expired}
    onChange={e=>setChecked(e.target.checked)}/> 我已核对候选定义与来源摘要，确认发布</label>
   <button className="primary" disabled={!current||undisposed.length>0||expired||!checked||busy} onClick={confirm}>{busy?'正在发布…':'确认发布'}</button>
  </div>
 </section>;
}

export function DiscoveryPage({view,reload,onNew,onError,onOpenSession,onOpenOntologies}:{
 view:View;reload:()=>Promise<void>;onNew:()=>void;onError:(error:unknown)=>void;
 onOpenSession:(id:string)=>void;onOpenOntologies?:()=>void;
}){
 const [busy,setBusy]=useState(false),[copied,setCopied]=useState(false);
 const {session,discovery}=view;
 if(!discovery)return null;
 const {catalog,draft}=discovery;
 // 发现页对所有来源类型通用：显示名与样本行按表所属来源解析，不假设唯一来源。
 const profilesById=new Map(view.profiles.map(profile=>[profile.source_id,profile]));
 const sourceName=(sourceId:string|undefined)=>{
  const source=session.sources.find(item=>item.source_id===sourceId);
  if(!source)return '';
  return String(source.extensions?.['dataagent.display_name']||source.options?.display_name||source.locator_ref.split('/').pop());
 };
 const displayName=session.sources.map(source=>
  String(source.extensions?.['dataagent.display_name']||source.options?.display_name||source.locator_ref.split('/').pop())).join('、');
 const prompt=`继续当前工作区的本体发现任务 ${session.id}。调用 intake_inference 获取当前证据，提出实体、粒度、标识、属性和关系，再用 ontology_discovery_propose 提交草案供我在工作台审核。`;
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
 // 重新探查的原因统一中文化：已知原文进主文案，未知英文折叠为「详情」。
 const probe=humanDetail((session.issues?.[0] as {detail?:string}|undefined)?.detail||'来源探查未完成');
 return <main className="workspace discovery-page">
  <header className="task-header">
   <div><div className="eyebrow">{displayName}</div><h1>本体发现</h1><p className="muted">{status}</p></div>
   <button className="secondary" onClick={onNew}>新建接入</button>
  </header>
  {session.next_actions?.includes('retry_probe')&&<div className="notice amber">
   {/* 折叠详情不嵌在 <p> 内：details 与 pre 是块级元素，浏览器会拆开非法嵌套。 */}
   <p>{probe.summary||'来源探查未完成'}</p>
   {probe.detail&&<details className="tech-detail"><summary>详情</summary><pre>{technicalDetail(probe.detail)}</pre></details>}
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
  {draft&&draft.state==='approved'&&<PublishBlock session={session} discovery={discovery} reload={reload}
   onError={onError} onOpenSession={onOpenSession} onOpenOntologies={onOpenOntologies}/>}
  {catalog&&<section className="discovery-card">
   <h2>来源证据</h2>
   <p className="muted">{catalog.tables.length} 张表 · 来源修订 <code title={discovery.source_revision}>{shortDigest(discovery.source_revision)}</code></p>
   {catalog.tables.map(table=>{
    // 样本记录按表所属的来源取，多来源时不串表。
    const profile=table.source_id?profilesById.get(table.source_id):view.profiles[0];
    const recordKeys=profile?.metadata?.record_keys as {table:string}[]|undefined;
    const binaryFields=profile?.metadata?.binary_fields as Record<string,string[]>|undefined;
    const rows=recordKeys?.flatMap((key,index)=>key.table===table.name?[{values:profile?.records?.[index],binary:binaryFields?.[index]}]:[]).slice(0,3)||[];
    const fields=Object.values(table.columns);
    return <details key={table.name} className="discovery-table">
    <summary><code>{table.name}</code> <span className="muted">{table.rows_observed} 行{table.sampled?'抽样':'已观察'}{sourceName(table.source_id)?` · ${sourceName(table.source_id)}`:''}</span></summary>
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
