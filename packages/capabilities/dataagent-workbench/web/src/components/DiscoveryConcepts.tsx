import {useId,useState} from 'react';
import {CONCEPT_GROUP_THRESHOLD} from '../discoveryView';

// 概念分组（FDE2-08）：概念不多时保持平铺网格；概念多时按概念折叠分组，
// 默认只展开概要（概念名、身份、属性数、证据来源、待决数），顶部给概念
// 目录与「只看有待决项」筛选，逐个展开核对。
export type ConceptGroup={
 name:string;label?:string;identity:string;propertyCount:number;sourceLabel:string;pending:string[];
 content:React.ReactNode;
};

export function DiscoveryConcepts({concepts,testid}:{concepts:ConceptGroup[];testid?:(name:string)=>string}){
 const [onlyPending,setOnlyPending]=useState(false);
 // 草案和发布候选可能同时出现多组概念；目录锚点必须带实例前缀，避免
 // 两组都生成 concept-0 时点错折叠项。
 const prefix=useId().replace(/[^a-zA-Z0-9_-]/g,'');
 // 展示名（FDE2-11）：英文名给中文标签；testid 仍用原始名，测试按原名定位。
 const shown=(concept:ConceptGroup)=>concept.label||concept.name;
 if(concepts.length<=CONCEPT_GROUP_THRESHOLD)
  return <div className="discovery-entities">{concepts.map(concept=>
   <article key={concept.name} className="discovery-entity" data-testid={testid?.(concept.name)}>
    {concept.content}</article>)}</div>;
 const indexed=concepts.map((concept,index)=>({concept,index}));
 const visible=onlyPending?indexed.filter(({concept})=>concept.pending.length>0):indexed;
 // 目录是导航：点概念名直接展开该组，否则折叠状态下只能看到概要。
 const openGroup=(index:number)=>{
  const target=document.getElementById(`concept-${prefix}-${index}`);
  if(target instanceof HTMLDetailsElement){target.open=true;target.scrollIntoView({block:'start'});}
 };
 return <div className="concept-groups" data-testid="concept-groups">
  <div className="concept-toolbar">
   <nav className="concept-toc" aria-label="概念目录">{visible.map(({concept,index})=>
    <a key={concept.name} href={`#concept-${prefix}-${index}`} onClick={event=>{event.preventDefault();openGroup(index);}}>{shown(concept)}{concept.pending.length>0?`（待决 ${concept.pending.length}）`:''}</a>)}</nav>
   <label className="concept-filter"><input type="checkbox" checked={onlyPending}
    onChange={event=>setOnlyPending(event.target.checked)}/>只看有待决项</label>
  </div>
  {visible.map(({concept,index})=>
   <details key={concept.name} className="concept-group" id={`concept-${prefix}-${index}`}
    data-testid={testid?testid(concept.name):`concept-group-${concept.name}`}>
    <summary><strong>{shown(concept)}</strong>
     <span className="concept-meta">身份 {concept.identity||'待确认'} · {concept.propertyCount} 个属性 · 证据来源 {concept.sourceLabel} · 待决 {concept.pending.length} 项</span></summary>
    {concept.pending.length>0&&<p className="warn">待决：{concept.pending.join('；')}</p>}
    {concept.content}
   </details>)}
 </div>;
}
