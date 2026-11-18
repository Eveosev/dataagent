import type {PublishCandidate} from '../client';
import type {RevisionDiff} from './RevisionHistory';

// 发现页发布区里的修订信息（V6）：修订目标生成的候选不是新本体，而是已发布
// 本体的下一修订。这里给出与当前修订的差异；删除属性或改身份字段是破坏性变更，
// 需要额外勾选「旧修订的数据不会自动迁移」。DiscoveryPage 只挂载这一块。
// FDE3-01：新修订登记时没有对象，当前修订的实例留在原修订；候选带出每个概念
// 在当前修订的实例数与需要重新接入的概念，确认前必须逐字看清并单独勾选。
export type RevisionCandidate=PublishCandidate&{
 previous_revision?:string;revision_diff?:RevisionDiff;destructive?:boolean;
 requires_no_migration_ack?:boolean;
 current_revision_instance_counts?:Record<string,number>;
 reintake_concepts?:string[];
};

export const isRevisionCandidate=(candidate:unknown):boolean=>
 !!candidate&&typeof candidate==='object'
 &&!!(candidate as {previous_revision?:string}).previous_revision;

export function revisionBlocksConfirm(candidate:PublishCandidate|null|undefined,
 acknowledged:boolean,reintakeAcknowledged=true):boolean{
 const revision=candidate as RevisionCandidate|null|undefined;
 if(!revision)return false;
 if(!!revision.destructive&&!acknowledged)return true;
 return (revision.reintake_concepts||[]).length>0&&!reintakeAcknowledged;
}

export function RevisionPublishNotice({candidate,acknowledged,onAcknowledge,
 reintakeAcknowledged,onReintakeAcknowledge,disabled}:{
 candidate:PublishCandidate|null;acknowledged:boolean;
 onAcknowledge:(value:boolean)=>void;
 reintakeAcknowledged:boolean;onReintakeAcknowledge:(value:boolean)=>void;
 disabled?:boolean;
}){
 if(!isRevisionCandidate(candidate))return null;
 const revision=candidate as RevisionCandidate;
 const diff=revision.revision_diff||{};
 const summary=diff.summary||[];
 const destructive=!!revision.destructive;
 const counts=revision.current_revision_instance_counts||{};
 const reintake=revision.reintake_concepts||[];
 return <section className="notice" data-testid="revision-publish-notice">
  <h3>发布新修订 · 修订 {revision.previous_revision} → {revision.ontology_revision}</h3>
  <p>这是已发布本体 <code>{revision.ontology_id}</code> 的新修订，不是新本体。
   确认后同一事务登记修订 {revision.ontology_revision}、更新注册表并把新任务默认指针移到它。</p>
  <h3>与当前修订的差异</h3>
  {summary.length
   ?<ul data-testid="revision-diff">{summary.map(line=><li key={line}>{line}</li>)}</ul>
   :<p className="muted">结构没有变化。</p>}
  {(diff.changed_relations||[]).length>0&&<div data-testid="revision-relation-changes">
   <h3>关系端点与角色变化</h3>
   {(diff.changed_relations||[]).map((change,index)=>{
    const before=change.before||{},after=change.after||{};
    const rows:[string,string,string,string][]=[
     ['subject','主体概念',before.subject_concept||'（无）',after.subject_concept||'（无）'],
     ['object','对象概念',before.object_concept||'（无）',after.object_concept||'（无）'],
     ['roles','角色',(before.roles||[]).join(' + ')||'（无）',
      (after.roles||[]).join(' + ')||'（无）'],
    ];
    return <div className="revision-relation" key={`${change.relation}-${index}`}
     data-testid={`revision-relation-${index}`}>
     <strong>{change.relation}</strong>
     <dl>{rows.map(([key,label,oldValue,newValue])=><div key={key}>
      <dt>{label}</dt>
      <dd data-testid={`revision-relation-${index}-${key}`}>
       <code>{oldValue}</code> → <code>{newValue}</code></dd>
     </div>)}</dl>
    </div>;
   })}
  </div>}
  {destructive
   ?<div className="notice amber" data-testid="revision-destructive">
     <p><strong>破坏性变更</strong>：本次修订删除属性、删除概念或修改身份字段。
      旧修订已发布的数据不会自动迁移到新修订，旧任务和旧实例仍留在原修订。</p>
     <label><input type="checkbox" checked={acknowledged} disabled={disabled}
      data-testid="revision-no-migration"
      onChange={event=>onAcknowledge(event.target.checked)}/>
      我知道旧修订的数据不会自动迁移</label>
    </div>
   :<p className="help">此修订不删除属性、不修改身份字段；旧修订的数据同样不自动迁移，
     旧任务和旧实例仍固定在原修订。</p>}
  {reintake.length>0
   ?<div className="notice amber" data-testid="revision-reintake">
     <p><strong>发布后新修订 {revision.ontology_revision} 下暂无对象</strong>，
      需要重新接入：{reintake.map(name=>`${name}（${counts[name]??0} 个对象）`).join('、')}；
      旧修订数据仍可按修订号查询。</p>
     <label><input type="checkbox" checked={reintakeAcknowledged} disabled={disabled}
      data-testid="revision-reintake-ack"
      onChange={event=>onReintakeAcknowledge(event.target.checked)}/>
      我知道发布后新修订下暂无对象，上述概念需要重新接入</label>
    </div>
   :<p className="help" data-testid="revision-reintake-empty">
     发布后新修订 {revision.ontology_revision} 下暂无对象；旧修订数据仍可按修订号查询。</p>}
 </section>;
}
