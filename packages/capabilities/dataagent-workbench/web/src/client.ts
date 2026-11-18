import type {SourceProfile} from './generated/SourceProfile';
import type {IntakeSession} from './generated/IntakeSession';
import type {OntologyRevision} from './generated/OntologyRevision';
import type {MappingSpec,FieldBinding} from './generated/MappingSpec';
import type {MappingPreview} from './generated/MappingPreview';
import type {Discovery} from './pages/DiscoveryPage';
export type {SourceProfile,IntakeSession,OntologyRevision,MappingSpec,FieldBinding};
export type Preview=MappingPreview & {review_state:string; mapping_reused?:boolean; corrections?:unknown[]};
export type Draft={bindings?:Record<string,FieldBinding>;source_bindings?:Record<string,Record<string,FieldBinding>>;selected_field?:string;source_id?:string;record_index?:number};
export type View={session:IntakeSession;profiles:SourceProfile[];ontology:OntologyRevision;preview:Preview|null;draft:Draft;mapping_reused:boolean;discovery:Discovery|null};
export type Selector={kind:string;page?:number;char_start?:number;char_end?:number;bbox?:number[];pointer?:string;range?:string;sheet?:string;keys?:Record<string,unknown>;field?:string};
export type Evidence={source_id:string;selector:Selector};
export type WorkObject={id:string;entity_type:string;values:Record<string,unknown>;evidence:Record<string,Evidence[]>;unresolved:string[];extensions?:Record<string,unknown>|null};
export type Correction={decision_ref:string;entity_id:string;property:string;value:unknown;reason:string};
export type Issue={code?:string;target?:string;row?:number;entity_id?:string;detail?:string;source_id?:string};
export type ObjectView={session:IntakeSession;ontology:OntologyRevision;ontology_revision:string;ontology_draft:Record<string,unknown>|null;
 sources:(SourceProfile&{display_name:string})[];objects:WorkObject[];corrections:Correction[];issues:Issue[];
 review_state:string|null;preview_ref?:string;mapping_revision:string|null;draft:Draft};
export class ApiError extends Error {constructor(public status:number,message:string){super(message);}}
// 后端原始报错按原文透出会给用户看不懂的英文；已知文案在这里换成中文说法。
const errorTexts:Record<string,string>={
 'required property remains unresolved':'必填属性仍未解决，请先在对象页核对后再保存',
 'identity remains unresolved':'对象标识仍未解决，请先核对单据编号',
 'no instance correction to revalidate':'没有需要重新校验的纠正',
 'correction entity no longer exists':'纠正的对象已不存在，请重新载入',
 'null corrections require an explicit unresolved decision':'纠正为空值需要先明确标记为未解决',
 'identity correction would merge objects; resolve the mapping explicitly':'标识纠正会使多个对象合并，请先调整映射',
 'preview contains unresolved issues':'预览仍有未解决的问题，请逐项核对后再保存',
 'unsupported file type':'暂不支持该文件类型',
 'file exceeds 32 MiB limit':'文件超过 32 MiB 限制',
 'Failed to fetch':'网络连接失败，请稍后重试',
};
export function translateError(message:string):string{return errorTexts[message.trim()]||message;}
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
 const response=await fetch(path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 const data=await response.json();
 if(!response.ok)throw new ApiError(response.status,translateError(String(data.detail||data.error||'请求未完成')));
 return data as T;
}
export const display=(value:unknown)=>value===null||value===undefined?'—':typeof value==='object'?JSON.stringify(value):String(value);
export const transformNames:Record<string,string>={identity:'保留原值',decimal:'十进制数',minor_to_major:'分 → 元（÷100）',integer:'整数',date:'日期',datetime:'带时区时间',enum:'枚举映射',combine:'组合字段',choose:'条件选择'};
export function locate(selector:Selector|undefined):string{
 if(!selector)return '—';
 if(selector.kind==='pdf_text_span'||selector.kind==='pdf_bbox')return `第 ${selector.page} 页`;
 if(selector.kind==='json_pointer'){
  const pointer=selector.pointer||'';
  return typeof selector.page==='number'?`第 ${selector.page} 页 · ${pointer}`:pointer;
 }
 if(selector.kind==='excel_cell')return `${selector.sheet} · ${selector.range}`;
 if(selector.kind==='record_key')return locateRecordKey(selector);
 if(selector.kind==='text_span')return `字符 ${selector.char_start}–${selector.char_end}`;
 return selector.kind;
}
// 数据库定位：表 / 主键（或无主键时的快照行），主键是“列 = 值”而不是内部对象。
function locateRecordKey(selector:Selector):string{
 const keys=selector.keys||{};
 if('row' in keys)return `来源行 ${display(keys.row)}`;
 if('line' in keys)return `第 ${display(keys.line)} 行`;
 if('table' in keys||'primary_key' in keys||'snapshot_row' in keys){
  const parts:string[]=[];
  const table=[keys.schema,keys.table].filter(value=>value!==undefined&&value!==null&&value!=='')
   .map(value=>display(value)).join('.');
  if(table)parts.push(`表 ${table}`);
  if(keys.primary_key&&typeof keys.primary_key==='object')
   parts.push(`主键 ${Object.entries(keys.primary_key as Record<string,unknown>).map(([column,value])=>`${column} = ${display(value)}`).join(' · ')}`);
  else if('snapshot_row' in keys){
   const ordinal=Number(keys.snapshot_row);
   parts.push(`快照第 ${Number.isFinite(ordinal)?ordinal+1:display(keys.snapshot_row)} 行`);
  }
  return parts.join(' · ');
 }
 return Object.entries(keys).map(([k,v])=>`${k} = ${display(v)}`).join(' · ');
}
// 用户纠正作为证据保存时，来源是审核决定本身，不是内部 JSON 路径。
export function isDecisionEvidence(evidence:Evidence):boolean{
 return evidence.selector?.kind==='json_pointer'&&evidence.selector.pointer==='/decision/changes/value';
}
export function decisionSourceName(evidence:Evidence):string{
 return `用户纠正 · 决定 ${evidence.source_id.slice(0,12)}…`;
}
type AnchorLike={source_ref:string;selector:unknown};
const withoutPage=(selector:unknown)=>{
 if(!selector||typeof selector!=='object')return JSON.stringify(selector);
 const {page:_,...rest}=selector as Record<string,unknown>;
 return JSON.stringify(rest);
};
// 来源行定位：selector 带页序号时按页取对应记录（REST 分页的 JSON Pointer 各页从 0 计，
// 会重复）；没有页序号时退回只比对 selector 的旧逻辑，命中第一条。
export function findAnchorRow(profile:{anchors?:Record<string,AnchorLike[]>}|undefined,evidence:Evidence):{row:number;field:string}|undefined{
 if(!profile)return undefined;
 const page=typeof evidence.selector?.page==='number'?evidence.selector.page:undefined;
 const target=withoutPage(evidence.selector);
 let fallback:{row:number;field:string}|undefined;
 for(const [key,anchors] of Object.entries(profile.anchors||{})){
  const dot=key.indexOf('.');
  const row=dot>0?Number(key.slice(0,dot)):NaN;
  if(!Number.isFinite(row))continue;
  const field=key.slice(dot+1);
  for(const anchor of anchors){
   if(anchor.source_ref!==evidence.source_id||withoutPage(anchor.selector)!==target)continue;
   const anchorPage=typeof (anchor.selector as {page?:unknown}|null)?.page==='number'?(anchor.selector as {page:number}).page:undefined;
   if(page===undefined||anchorPage===page)return {row,field};
   if(!fallback)fallback={row,field};
  }
 }
 return fallback;
}
