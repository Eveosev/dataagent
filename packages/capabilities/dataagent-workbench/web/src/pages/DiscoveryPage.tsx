import {useEffect,useRef,useState} from 'react';
import {api,ApiError,display,humanDetail,technicalDetail} from '../client';
import type {View,PublishCandidate,PublishDisposition} from '../client';
import type {IntakeSession} from '../generated/IntakeSession';
import {DiscoveryConcepts} from '../components/DiscoveryConcepts';
import {RevisionPublishNotice,isRevisionCandidate,revisionBlocksConfirm} from '../components/RevisionPublishNotice';
import type {RevisionCandidate} from '../components/RevisionPublishNotice';
import {conceptPending,gapLabels,sourceNameOf,tableLabel} from '../discoveryView';
import type {CatalogTable} from '../discoveryView';

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
 publish_candidate?:{ref:string;state?:string;ontology_id?:string;ontology_revision?:string;draft_ref?:string;previous_revision?:string;destructive?:boolean}|null;
 catalog:null|{
  tables:{name:string;source_id?:string;kind?:string;rows_observed:number;sampled:boolean;columns:Record<string,Column>;keys:string[][];identity_keys:string[][]}[];
  relationships:Relationship[];gaps:{table?:string;source_id?:string;code:string}[];
 };
 draft:null|{
  ref:string; state:'pending'|'approved'|'rejected'; reviewed_draft_ref?:string;
  entities:{name:string;table:string;grain:string;identity:string[];
            properties:{name:string;column:string}[];extension_columns:string[]}[];
  relationships:Relationship[]; unresolved_tables:string[]; unresolved_relationships:Relationship[];
  gaps?:{ref?:string;table?:string;code:string}[]; coverage?:string;
 };
};
type DiscoveryCatalog=NonNullable<Discovery['catalog']>;

function RelationshipList({items,tableName}:{items:Relationship[];tableName?:(name:string)=>string}){
 const label=tableName||((name:string)=>name);
 return items.length===0?<p className="muted">无关系</p>:<ul className="discovery-links">{items.map(link=>
  <li key={link.id}>
   <div><strong>{link.name}</strong>{link.name&&<span> · </span>}
    <code>{label(link.source_table)}({link.source_columns.join(', ')})</code> → <code>{label(link.target_table)}({link.target_columns.join(', ')})</code>
   </div>
   <small>{link.origin==='declared'?'数据库声明':'观测值匹配'} · {link.cardinality==='one_to_one'?'一对一':'多对一'} · {link.checked_rows
     ?`${link.sampled?'抽样':'观察'}同值 ${link.matched_rows}/${link.checked_rows}`
     :'无可比对值'}
    {link.ambiguous&&' · 多个候选'}
   </small>
  </li>)}</ul>;
}

const coverageNames:Record<string,string>={sampled:'抽样观察',partial:'部分读取',unknown:'覆盖未知'};
const dispositionKindNames:Record<string,string>={unresolved_table:'未建模的表',unresolved_relationship:'未采用的关系',coverage_gap:'覆盖缺口',coverage:'来源覆盖'};
// 候选与草案的差异（后端 candidate.dropped）：Agent 补全时没有带入候选的
// 草案已选关系、概念与属性。发布确认区必须逐项列出并让用户勾选同意。
type DroppedItem={kind:'relationship'|'concept'|'property';ref:string;name?:string;
 table?:string;concept?:string;column?:string;source_table?:string;source_columns?:string[];
 target_table?:string;target_columns?:string[];cardinality?:string};
type PublishCandidateView=PublishCandidate&{
 dropped?:DroppedItem[];
 revision_diff?:{destructive?:boolean;
  removed_properties?:{concept:string;property:string}[];
  removed_concepts?:string[]};
};
type OpenItem={kind:string;ref:string;label:string;dropped?:boolean;
 // 后端门禁要求 Agent 处置的项为 true；仅需用户确认的放弃项为 false。
 needsDisposition?:boolean;
 // 修订差异已经逐项列出并带「旧数据不迁移」确认的删除项，不再重复要求勾选。
 externalAck?:boolean};
// 草案里的未决项与覆盖缺口：发布前必须逐项排除或接受（D1 门禁在服务端复核，
// 这里先点名给用户核对）。表名按来源文件转成可读标签，不显示内部记录集 ID。
function openItems(draft:NonNullable<Discovery['draft']>,catalog:DiscoveryCatalog|null,session:IntakeSession):OpenItem[]{
 const label=(table:string)=>tableLabel(table,catalog?.tables||[],session);
 const items:OpenItem[]=[];
 for(const table of draft.unresolved_tables||[])
  items.push({kind:'unresolved_table',ref:String(table),label:`未建模的表 ${label(table)}`});
 for(const link of draft.unresolved_relationships||[])
  items.push({kind:'unresolved_relationship',ref:String(link.id),
   label:`未采用的关系 ${link.name||`${label(link.source_table)} → ${label(link.target_table)}`}`});
 for(const gap of draft.gaps||[])
  items.push({kind:'coverage_gap',ref:String(gap.ref||''),label:`覆盖缺口 ${gap.table?label(gap.table)+' · ':''}${gapLabels[gap.code]||gap.code}`});
 const coverage=draft.coverage||'unknown';
 if(coverage!=='full')
  items.push({kind:'coverage',ref:coverage,label:`来源覆盖 ${coverageNames[coverage]||coverage}`});
 return items;
}
function droppedItems(dropped:DroppedItem[],label:(table:string)=>string,
 removed?:{properties:Set<string>;concepts:Set<string>}):OpenItem[]{
 return dropped.map(item=>{
  if(item.kind==='relationship'){
   const endpoints=`${label(item.source_table||'')} → ${label(item.target_table||'')}`;
   const detail=[item.name,endpoints].filter(Boolean).join(' · ');
   return {kind:'unresolved_relationship',ref:item.ref,dropped:true,
    needsDisposition:true,label:`补全时放弃的草案关系${detail?` ${detail}`:''}`};
  }
  // 防御分支：后端要求每个草案实体都补全，概念目前不会被放弃；关系与属性
  // 才是可到达、需要逐项确认的删除项。
  if(item.kind==='concept')
   return {kind:'dropped_concept',ref:item.ref,dropped:true,needsDisposition:false,
    externalAck:removed?.concepts.has(item.name||item.ref)===true,
    label:`补全时放弃的草案概念 ${item.name||item.ref}`};
  const name=[item.concept,item.name||item.column||item.ref].filter(Boolean).join('.');
  const column=item.column&&item.column!==item.name?`（来源列 ${item.column}）`:'';
  return {kind:'dropped_property',ref:item.ref,dropped:true,needsDisposition:false,
   externalAck:removed?.properties.has(`${item.concept}.${item.name}`)===true,
   label:`补全时放弃的草案属性 ${name}${column}`};
 });
}
// Agent 处置的影响说明（FDE2-07）：勾选核对前把每种处置的后果说清楚。
const dispositionImpacts:Record<string,Record<'exclude'|'accept',string>>={
 unresolved_table:{
  exclude:'这张表不会进入本体，发布后新任务按本体查询不到它的数据。',
  accept:'这张表保持未建模，处置随候选记录在案，不会生成对应概念。'},
 unresolved_relationship:{
  exclude:'这条关系不会登记进本体，两端概念之间没有这条关联。',
  accept:'这条关系保持未决，处置随候选记录在案，本体不登记它。'},
 coverage_gap:{
  exclude:'该缺口的证据不参与本次发布。',
  accept:'该缺口随候选发布，对应范围的证据不保证完整。'},
 coverage:{
  exclude:'本次发布不包含该来源覆盖范围。',
  accept:'本体按该覆盖水平发布，未观察到的数据形态不保证兼容。'},
};
const impactOf=(item:OpenItem,action:'exclude'|'accept')=>
 dispositionImpacts[item.kind]?.[action]||'该处置随候选记录在案。';
// 补全时被放弃的草案概念/属性没有 Agent 处置可核对；仍要说明不进入候选的影响。
const droppedImpacts:Record<string,string>={
 dropped_concept:'这个草案概念不会进入本体，发布后新任务按本体查询不到对应范围的数据。',
 dropped_property:'这个草案属性不会进入本体，该字段的数据不在本体中提供。',
};
const shortDigest=(value:string|undefined)=>value?value.replace('sha256:','').slice(0,12):'—';

// 发布区块：候选定义摘要、来源快照摘要、未决项与补全放弃项的处置状态。草案
// pending 但已有有效候选时也直接显示，用户核对后一次确认即发布；Agent 已下的
// 处置与补全时放弃的草案项逐项列出并要求逐项勾选同意（FDE2-07），未处置项点名
// 并阻断，确认由人勾选后提交（网页是唯一确认通道）。
function PublishBlock({session,discovery,reload,onError,onOpenSession,onOpenOntologies}:{
 session:IntakeSession;discovery:Discovery;reload:()=>Promise<void>;
 onError:(error:unknown)=>void;onOpenSession:(id:string)=>void;onOpenOntologies?:()=>void;
}){
 const draft=discovery.draft!;
 const catalog=discovery.catalog as DiscoveryCatalog|null;
 const tables:CatalogTable[]=catalog?.tables||[];
 const label=(table:string)=>tableLabel(table,tables,session);
 const base=`/api/sessions/${session.id}`;
 const [candidate,setCandidate]=useState<PublishCandidateView|null>(null),[checked,setChecked]=useState(false),[busy,setBusy]=useState(false);
 const [agreed,setAgreed]=useState<Record<string,boolean>>({});
 const [migrationAck,setMigrationAck]=useState(false);
 const [failure,setFailure]=useState<{text:string;action:'rediscover'|'refresh'}|null>(null),[copied,setCopied]=useState(false),[copiedReturn,setCopiedReturn]=useState(false);
 const [staleHint,setStaleHint]=useState(false);
 // 记录被后端按过期拒绝的候选引用；只有换到不同且一致的候选才清除过期标记。
 const rejectedRef=useRef('');
 const summary=discovery.publish_candidate||null;
 const fetchCandidate=async()=>setCandidate(await api<PublishCandidateView|null>(base+'/publish/candidate'));
 useEffect(()=>{let cancelled=false;
  (async()=>{try{const data=await api<PublishCandidateView|null>(base+'/publish/candidate');if(!cancelled)setCandidate(data);}
   catch(error){if(!cancelled)onError(error);}})();
  return()=>{cancelled=true;};
 },[summary?.ref,summary?.state,draft.ref,session.revision]);
 // 候选替换（引用或定义摘要变化）时重置人工核对勾选：核对必须绑定实际确认的候选，
 // 不能用对旧定义的确认发布新定义；Agent 处置的逐项同意也一并重置。
 useEffect(()=>{setChecked(false);setAgreed({});setMigrationAck(false);},[candidate?.ref,candidate?.definition_digest]);
 // 刷新取得与被拒候选不同、且与当前任务修订一致的候选时清除过期标记，发布流程可恢复；
 // 候选仍过期时派生校验会继续禁用确认。
 useEffect(()=>{
  if(staleHint&&candidate&&candidate.ref!==rejectedRef.current
   &&candidate.draft_ref===draft.ref&&String(candidate.session_revision)===String(session.revision))
   setStaleHint(false);
 },[staleHint,candidate,session.revision,draft.ref]);
 const published=summary?.state==='published';
 const publishedRevision=isRevisionCandidate(candidate)?candidate as RevisionCandidate:null;
 // 候选必须锚定当前草案；草案更新后的旧候选不可确认。
 const current=candidate&&candidate.draft_ref===draft.ref?candidate:null;
 const revision=isRevisionCandidate(current)?current as RevisionCandidate:null;
 const revisionId=(session.extensions?.['dataagent.revision_target'] as {ontology_id?:string}|undefined)?.ontology_id;
 // 过期候选（D1 会拒绝）：任务修订已越过候选记录的修订时，确认被禁用并提示
 // 重新准备，避免反复提交同一失效候选。
 const expired=staleHint||(!!current&&String(current.session_revision)!==String(session.revision));
 const dispositionOf=(item:OpenItem)=>(current?.dispositions||[]).find((entry:PublishDisposition)=>entry.kind===item.kind&&entry.ref===item.ref);
 // 发布区覆盖候选里的全部处置：草案未决项之外，还要列出 Agent 补全时
 // 放弃（未带入候选）的草案关系/概念/属性——数据取自后端候选与草案的
 // 差异（candidate.dropped），不能只看草案自己声明的未决项。
 const draftItems=openItems(draft,catalog,session);
 const removedProperties=new Set((current?.revision_diff?.removed_properties||[])
  .map(item=>`${item.concept}.${item.property}`));
 const removedConcepts=new Set(current?.revision_diff?.removed_concepts||[]);
 const dropped=droppedItems(current?.dropped||[],label,
  {properties:removedProperties,concepts:removedConcepts});
 const items=[...draftItems,...dropped.filter(candidateItem=>
  !draftItems.some(existing=>existing.kind===candidateItem.kind&&existing.ref===candidateItem.ref))];
 // 防御性兜底：后端若有发布区还没命名的处置，也逐项列出而不是静默漏掉。
 const orphanDispositions=(current?.dispositions||[]).filter(entry=>
  !items.some(item=>item.kind===entry.kind&&item.ref===entry.ref));
 const allItems:OpenItem[]=[...items,...orphanDispositions.map(entry=>({kind:entry.kind,ref:entry.ref,
  label:`${dispositionKindNames[entry.kind]||entry.kind} ${entry.ref}`}))];
 // 未处置只阻断后端门禁要求 Agent 表态的项；补全时放弃的概念/属性只需用户确认。
 const undisposed=allItems.filter(item=>item.needsDisposition!==false&&!dispositionOf(item));
 // Agent 处置与被放弃项的逐项同意：每一项都要用户勾选核对，全部同意前确认发布禁用。
 // 修订差异里的删除项同样逐项记录同意状态；「旧数据不迁移」迁移确认始终
 // 独立，不论单项还是多项删除都不代勾任何被放弃项。
 const agreements=allItems.filter(item=>item.needsDisposition===false||!!dispositionOf(item));
 const dispositionsAgreed=agreements.every(item=>agreed[`${item.kind}:${item.ref}`]===true);
 const copyPrompt=(text:string,done:()=>void)=>navigator.clipboard.writeText(text).then(done).catch(onError);
 // 复制给用户转交 Agent 的指令只用业务话术，不出现内部工具名（FDE2-12）。
 const completionPrompt=`继续当前工作区的本体发现任务 ${session.id}。草案 ${draft.ref} ${draft.state==='pending'?'仍待审核':'已通过审核'}；请补全每个概念的属性值类型、必需性与身份字段，对关系给出端点与角色，对未决项与覆盖缺口逐项给出排除或接受的处置并说明影响，生成发布候选供我在工作台确认。`;
 const returnPrompt=`继续当前工作区的本体发现任务 ${session.id}。草案 ${draft.ref} 的发布候选里，对未决项与覆盖缺口的处置我不认可，请逐项重新给出排除或接受的处置、说明理由与影响，生成新的发布候选供我在工作台确认。`;
 async function confirm(){
  if(!current||expired||revisionBlocksConfirm(current,migrationAck))return;
  setBusy(true);
  try{
   await api(base+'/publish/confirm','POST',{
    candidate_ref:current.ref,draft_ref:current.draft_ref,
    source_snapshot:current.source_snapshot,definition_digest:current.definition_digest,
    expected_revision:session.revision,confirmed:true,reason:'工作台人工确认发布',
    ...(revision?{acknowledge_no_migration:migrationAck}:{}),
   });
   setChecked(false);setMigrationAck(false);setFailure(null);
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
    goal:`来源已变更，重新发现本体（原任务 ${session.id}）`,sources,mode:'ontology_discovery',
    // HTTP 入口把发现页的修订目标放在既有 target 通道；服务端据此重新钉住
    // 同一本体，不会把新任务退化成“新建本体”。
    ...(revisionId?{target:{ontology_id:revisionId}}:{}),
   });
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
   <div className="notice green" data-testid="publish-done">{publishedRevision
    ?<>修订 {publishedRevision.previous_revision} → {publishedRevision.ontology_revision} 已发布到本体 <code>{publishedRevision.ontology_id}</code>，旧修订与实例保留，新任务将默认使用新修订。</>
    :<>草案已发布为正式本体 <code>{summary?.ontology_id}</code>（修订 {summary?.ontology_revision}），新任务将默认使用它。</>}
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
   <p>候选已过期：任务修订已更新，后端会拒绝该候选。请让 Agent 重新生成发布候选后再确认。</p>
  </div>}
  {current?<><RevisionPublishNotice candidate={current} acknowledged={migrationAck}
    onAcknowledge={setMigrationAck} disabled={expired}/>
   <h3>候选定义摘要 · {current.title||current.ontology_id}</h3>
   <DiscoveryConcepts testid={name=>`publish-concept-${name}`} concepts={Object.entries(current.definition.concepts).map(([name,concept])=>{
    const entity=draft.entities.find(item=>item.name===name);
    return {name,identity:concept.identity_fields.join(' + '),
     propertyCount:Object.keys(concept.properties).length,
     sourceLabel:entity?tableLabel(entity.table,tables,session):'—',
     pending:entity?conceptPending(entity.table,draft,label):[],
     content:<>
      <h3>{name}</h3><dl><dt>实体类型</dt><dd><code>{concept.entity_type}</code></dd>
       <dt>身份字段</dt><dd>{concept.identity_fields.join(' + ')}</dd></dl>
      <table className="mapping-table"><thead><tr><th>属性</th><th>值类型</th><th>必需</th></tr></thead>
       <tbody>{Object.entries(concept.properties).map(([prop,definition])=><tr key={prop}>
        <td>{prop}</td><td>{definition.value_type}</td><td>{definition.required?'必需':'可选'}</td></tr>)}</tbody>
      </table>
     </>};
   })}/>
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
  </>:<div className="notice amber"><p>草案{draft.state==='pending'?'待审核':'已通过审核'}。让 Agent 补全值类型、必需性与身份字段并生成发布候选后，在这里人工确认发布；Agent 工具不能代为确认。</p>
   <div className="discovery-prompt"><code>{completionPrompt}</code><button className="secondary" onClick={()=>copyPrompt(completionPrompt,()=>setCopied(true))}>{copied?'已复制':'复制指令'}</button></div>
  </div>}
  <h3>未决项、补全放弃项与覆盖缺口</h3>
  {allItems.length>0?<ul className="publish-items" data-testid="publish-open-items">{allItems.map(item=>{
   const disposition=dispositionOf(item);
   const key=`${item.kind}:${item.ref}`;
   const dropped=item.dropped===true;
   return <li key={key} data-testid={dropped?'publish-dropped-item':'publish-open-item'}
    data-dropped={dropped?'true':undefined}>
    {disposition?<>
     <label className="publish-disposition">
      <input type="checkbox" checked={agreed[key]===true} disabled={!current||expired}
       onChange={event=>setAgreed(previous=>({...previous,[key]:event.target.checked}))}/>
      <span>{item.label} · <span className="ok">Agent 处置，待你核对</span></span>
     </label>
     <p className="help">{dropped&&'补全候选未带入该草案项。'}{disposition.action==='exclude'?'Agent 已排除':'Agent 已接受'}（{disposition.reason}）。影响：{impactOf(item,disposition.action)}</p>
    </>:item.externalAck?<>
     <label className="publish-disposition">
      <input type="checkbox" checked={agreed[key]===true} disabled={!current||expired}
       onChange={event=>setAgreed(previous=>({...previous,[key]:event.target.checked}))}/>
      <span>{item.label} · <span className="warn">待你核对同意</span></span>
     </label>
      <p className="help">补全候选未带入该草案项。影响：{droppedImpacts[item.kind]||'该草案项不会进入本体。'}该删除项已在上方修订差异中列出，仍须单独勾选同意；「旧数据不迁移」迁移确认不能代替逐项同意。</p>
    </>:item.needsDisposition===false?<>
     <label className="publish-disposition">
      <input type="checkbox" checked={agreed[key]===true} disabled={!current||expired}
       onChange={event=>setAgreed(previous=>({...previous,[key]:event.target.checked}))}/>
      <span>{item.label} · <span className="warn">未带入候选，待你核对同意</span></span>
     </label>
     <p className="help">补全候选未带入该草案项。影响：{droppedImpacts[item.kind]||'该草案项不会进入本体。'}</p>
    </>:<>{item.label} · <span className="warn">未处置</span></>}
   </li>;})}</ul>:<p className="muted">无未决项、补全放弃项与覆盖缺口。</p>}
  {undisposed.length>0&&<div className="notice amber" data-testid="publish-blocked">
   <p>有 {undisposed.length} 项未处置，发布前必须逐项排除或接受：{undisposed.map(item=>item.label).join('；')}。请在补全指令中给出处置。</p>
  </div>}
  {allItems.some(item=>dispositionOf(item))&&<details className="publish-return" data-testid="publish-return">
   <summary>不同意某项处置？退回让 Agent 重做</summary>
   <p className="help">把这条指令发给 Agent：它会重新给出每项处置并生成新候选，新候选出现后再在这里核对；当前候选不会被它覆盖。</p>
   <div className="discovery-prompt"><code>{returnPrompt}</code><button className="secondary" onClick={()=>copyPrompt(returnPrompt,()=>setCopiedReturn(true))}>{copiedReturn?'已复制':'复制指令'}</button></div>
  </details>}
  <p className="help">发布后将成为新任务的默认目标本体；既有任务与已发布实例不受影响。</p>
  {draft.state==='pending'&&current&&<p className="help" data-testid="publish-pending-note">当前草案待审核：点「确认发布」会一并审核该草案并发布为正式本体，不需要先单独确认草案。</p>}
  <div className="discovery-review">
   <label><input type="checkbox" checked={checked} disabled={!current||undisposed.length>0||expired}
    onChange={e=>setChecked(e.target.checked)}/> 我已核对候选定义与来源摘要，确认发布</label>
   <button className="primary" disabled={!current||undisposed.length>0||expired||!checked||!dispositionsAgreed||revisionBlocksConfirm(current,migrationAck)||busy} onClick={confirm}>{busy?'正在发布…':'确认发布'}</button>
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
 const tables:CatalogTable[]=catalog?.tables||[];
 const label=(name:string)=>tableLabel(name,tables,session);
 // pending 草案只在候选仍锚定当前草案时开放发布区；rejected 永不显示。
 const candidateSummary=discovery.publish_candidate;
 const pendingCandidate=!!draft&&draft.state==='pending'
  &&candidateSummary?.state==='candidate'
  &&candidateSummary.draft_ref===draft.ref;
 // 复制给用户转交 Agent 的指令只用业务话术，不出现内部工具名（FDE2-12）。
 const prompt=`继续当前工作区的本体发现任务 ${session.id}。请基于当前证据提出实体、粒度、标识、属性和关系，提交本体草案供我在工作台审核。`;
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
   <div><div className="eyebrow">{session.sources.map(source=>sourceNameOf(session,source.source_id)).join('、')}</div><h1>本体发现</h1><p className="muted">{status}</p></div>
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
   <DiscoveryConcepts concepts={draft.entities.map(entity=>({name:entity.name,
    identity:entity.identity.join(' + '),propertyCount:entity.properties.length,
    sourceLabel:label(entity.table),pending:conceptPending(entity.table,draft,label),
    content:<>
     <h3>{entity.name}</h3><p>{entity.grain}</p>
     <dl><dt>来源表</dt><dd><code>{label(entity.table)}</code></dd>
      <dt>标识</dt><dd>{entity.identity.length?entity.identity.join(' + '):'待确认'}</dd></dl>
     {entity.properties.length>0&&<table className="mapping-table">
      <thead><tr><th>属性</th><th>来源列</th><th>声明类型</th></tr></thead>
      <tbody>{entity.properties.map(prop=><tr key={prop.column}><td>{prop.name}</td>
       <td><code>{prop.column}</code></td><td>{tables.find(item=>item.name===entity.table)?.columns[prop.column]?.type||'—'}</td></tr>)}</tbody>
     </table>}
     {entity.extension_columns.length>0&&<p className="muted">保留为扩展字段 · {entity.extension_columns.join(', ')}</p>}
    </>}))}/>
   <h3>拟采用的关系</h3><RelationshipList items={draft.relationships} tableName={label}/>
   {(draft.unresolved_tables.length>0||draft.unresolved_relationships.length>0)&&<div className="notice amber">
    <strong>待核对</strong>
    {draft.unresolved_tables.length>0&&<p>未建模的表 · {draft.unresolved_tables.map(label).join('、')}</p>}
    {draft.unresolved_relationships.length>0&&<RelationshipList items={draft.unresolved_relationships} tableName={label}/>}
   </div>}
   {draft.state==='pending'&&(pendingCandidate
    // 发布区已存在时草案确认收进次要操作（FDE2-12）：「确认发布」会一并
    // 审核当前草案，主按钮并列会造成「要点两次」的误解。
    ?<details className="draft-only-review" data-testid="draft-only-review">
      <summary>只审核草案，不发布</summary>
      <p className="help">发布区的「确认发布」会一并审核当前草案并发布为正式本体；只有不准备发布时才在这里单独审核。</p>
      <div className="discovery-review">
       <button className="secondary" disabled={busy} onClick={()=>review('reject')}>退回草案</button>
       <button className="secondary" disabled={busy} onClick={()=>review('approve')}>确认当前草案</button>
      </div>
     </details>
    :<div className="discovery-review">
      <button className="secondary" disabled={busy} onClick={()=>review('reject')}>退回草案</button>
      <button className="primary" disabled={busy} onClick={()=>review('approve')}>确认当前草案</button>
     </div>)}
  </section>}
  {draft&&(draft.state==='approved'||pendingCandidate)&&<PublishBlock session={session} discovery={discovery} reload={reload}
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
    <summary><code>{label(table.name)}</code> <span className="muted">{table.rows_observed} 行{table.sampled?'抽样':'已观察'}{sourceNameOf(session,table.source_id)?` · ${sourceNameOf(session,table.source_id)}`:''}</span></summary>
    <p>主键与唯一键 · {table.keys.map(key=>key.join(' + ')).join(' / ')||'未观察到'}</p>
    {table.identity_keys.length<table.keys.length&&<p className="muted">含已观察空值的键不可用作标识。</p>}
    <table className="mapping-table"><thead><tr><th>字段</th><th>声明类型</th><th>空值行</th><th>观测去重值</th>{rows.map((_,index)=><th key={index}>样本 {index+1}</th>)}</tr></thead>
     <tbody>{fields.map(column=><tr key={column.name}>
      <td><code>{column.name}</code></td><td>{column.type||'—'}</td><td>{column.null_rows}</td><td>{column.distinct_values}</td>
      {rows.map((row,index)=><td key={index}>{row.binary?.includes(column.name)?'二进制':display(row.values?.[column.name]).slice(0,160)}</td>)}
     </tr>)}</tbody></table>
   </details>;})}
   {!draft&&<><h3>关系证据</h3><RelationshipList items={catalog.relationships} tableName={label}/></>}
   {catalog.gaps.length>0&&<ul>{catalog.gaps.map((gap,i)=><li key={i}>{gap.table?label(gap.table)+' · ':''}{gapLabels[gap.code]||gap.code}</li>)}</ul>}
  </section>}
 </main>;
}
