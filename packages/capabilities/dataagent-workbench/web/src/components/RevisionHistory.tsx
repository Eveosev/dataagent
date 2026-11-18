// 本体库的修订历史（V6）：每个本体显示修订号、发布时间（浏览器本地时区）与
// 相对上一修订的差异摘要。注册表条目本身保留当前修订；历史来自 revisions。
// 旧工作区的条目没有 revisions 时按当前修订合成一条，不隐藏已有本体。
export type RevisionDiff={
 previous_revision?:string;revision?:string;destructive?:boolean;
 summary?:string[];
 added_concepts?:string[];removed_concepts?:string[];
 added_properties?:{concept:string;property:string;value_type:string}[];
 removed_properties?:{concept:string;property:string;value_type:string}[];
 retyped_properties?:{concept:string;property:string;before:string;after:string}[];
 identity_changes?:{concept:string;before:string[];after:string[]}[];
 added_relations?:string[];removed_relations?:string[];changed_relations?:{relation:string}[];
};
export type RevisionRecord={
 revision:string;published_at?:string;published_by?:string;
 previous_revision?:string;destructive?:boolean;diff?:RevisionDiff;
};
export type RevisionEntry={
 id?:string;ontology_revision?:string;published_at?:string;published_by?:string;
 revisions?:RevisionRecord[];
};

// 发布时间统一按浏览器所在时区显示（FDE2-14：此前按 UTC 截取日期会差一天）。
export function localDateTime(value?:string|null):string{
 if(!value)return '';
 const moment=new Date(value);
 if(Number.isNaN(moment.getTime()))return value;
 const pad=(part:number)=>String(part).padStart(2,'0');
 return `${moment.getFullYear()}-${pad(moment.getMonth()+1)}-${pad(moment.getDate())} `
  +`${pad(moment.getHours())}:${pad(moment.getMinutes())}`;
}
export function localDate(value?:string|null):string{
 return localDateTime(value).slice(0,10);
}

export function revisionRecords(entry:RevisionEntry):RevisionRecord[]{
 if(entry.revisions&&entry.revisions.length)return entry.revisions;
 if(!entry.ontology_revision)return [];
 return [{revision:entry.ontology_revision,published_at:entry.published_at,
  published_by:entry.published_by}];
}

export function RevisionHistory({entry}:{entry:RevisionEntry}){
 const records=revisionRecords(entry);
 return <details className="revision-history" data-testid={`revision-history-${entry.id||''}`}>
  <summary>修订历史 · {records.length} 个修订</summary>
  <ol className="revision-list">
   {records.map(record=><li key={record.revision} data-testid={`revision-${entry.id||''}-${record.revision}`}>
    <div><strong>修订 {record.revision}</strong>
     {record.previous_revision&&<small className="muted"> · 由修订 {record.previous_revision} 发布</small>}
     {record.destructive&&<span className="badge">破坏性</span>}
    </div>
    <small className="muted">{record.published_at
     ?`发布于 ${localDateTime(record.published_at)}`
     :'发布时间未知'}{record.published_by?` · ${record.published_by}`:''}</small>
    <ul>{((record.diff&&record.diff.summary)||[]).length
     ?(record.diff!.summary||[]).map(line=><li key={line}>{line}</li>)
     :<li className="muted">{record.previous_revision?'结构未变化':'初始发布'}</li>}</ul>
   </li>)}
  </ol>
  <p className="help">旧修订与已发布实例不迁移、不删除；新任务默认使用当前修订。</p>
 </details>;
}
