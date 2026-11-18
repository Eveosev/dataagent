import type {SourceProfile} from './generated/SourceProfile';
import type {IntakeSession} from './generated/IntakeSession';
import type {OntologyRevision} from './generated/OntologyRevision';
import type {MappingSpec,FieldBinding} from './generated/MappingSpec';
import type {MappingPreview} from './generated/MappingPreview';
import type {Discovery} from './pages/DiscoveryPage';
export type {SourceProfile,IntakeSession,OntologyRevision,MappingSpec,FieldBinding};
export type Preview=MappingPreview & {review_state:string; mapping_reused?:boolean; corrections?:unknown[]};
export type Draft={bindings?:Record<string,FieldBinding>;source_bindings?:Record<string,Record<string,FieldBinding>>;selected_field?:string;source_id?:string;record_index?:number};
export type View={session:IntakeSession;profiles:SourceProfile[];ontology:OntologyRevision;preview:Preview|null;draft:Draft;mapping_reused:boolean;discovery:Discovery|null;correction_views?:CorrectionView[]};
export type Selector={kind:string;page?:number;char_start?:number;char_end?:number;bbox?:number[];pointer?:string;range?:string;sheet?:string;keys?:Record<string,unknown>;field?:string;extensions?:Record<string,unknown>|null};
export type Evidence={source_id:string;selector:Selector};
export type WorkObject={id:string;entity_type:string;values:Record<string,unknown>;evidence:Record<string,Evidence[]>;unresolved:string[];extensions?:Record<string,unknown>|null};
export type Correction={decision_ref:string;entity_id:string;property:string;value:unknown;reason:string};
export type CorrectionView={decision_ref:string;entity_id:string;property:string;value:unknown;
 mapping_value:unknown;mapping_revision:string;mapping_changed:boolean};
export type Issue={code?:string;target?:string;row?:number;entity_id?:string;detail?:string;source_id?:string;object?:string};
export type ObjectView={session:IntakeSession;ontology:OntologyRevision;ontology_revision:string;ontology_draft:Record<string,unknown>|null;
 sources:(SourceProfile&{display_name:string})[];objects:WorkObject[];corrections:Correction[];correction_views:CorrectionView[];issues:Issue[];
 review_state:string|null;preview_ref?:string;mapping_revision:string|null;draft:Draft};
// 问题分级对应后端约定：整批保存被任何未解决问题拦下（dataagent-ontology
// service.py 的 prepare_review），其中这三个 code 能被对象页的实例纠正清除
//（dataagent_workbench intake_service 的 _RESOLVABLE_ISSUES），其余问题在修订
// 映射或来源前一直阻断。文案镜像 intake_service 的 _ISSUE_REASONS。
export const correctableIssueCodes=new Set(['ontology.conflicting_values','ontology.required_value_missing','ontology.conversion_failed']);
export const issueReasons:Record<string,string>={
 'ontology.conflicting_values':'各来源的字段值不一致',
 'ontology.required_value_missing':'缺少必填值',
 'ontology.required_binding_missing':'必填属性没有映射',
 'ontology.identity_unresolved':'缺少单据号，无法确定对象',
 'ontology.conversion_failed':'值无法按目标类型转换',
 'ontology.evidence_missing':'值没有来源定位',
 'ontology.incomplete_source':'来源未完整读取',
 'ontology.relation_unresolved':'关联字段不完整',
 'ontology.correction_conflict':'网页纠正无法沿用',
 'ontology.no_records':'没有可映射的记录',
};
export const issueBlocksSave=(issue:Issue)=>!correctableIssueCodes.has(issue.code||'');
// 问题点回对象：带 entity_id 的直接命中；只带行号的问题（row 是来源内 0 起的记录
// 序号，且可能不带 source_id）用对象证据锚点经来源 profile 解析回同一序号。行号
// 在各来源内独立计数，跨来源的同序号可能归并到不同对象——只有全部命中都指向同一
// 对象时才返回它，有歧义时返回 undefined，不给确定性的错误链接。
export function issueObject(issue:Issue,view:Pick<ObjectView,'objects'|'sources'>):WorkObject|undefined{
 if(issue.entity_id){
  const target=view.objects.find(o=>o.id===issue.entity_id);
  if(target)return target;
 }
 if(issue.row===undefined)return undefined;
 let matched:WorkObject|undefined;
 for(const object of view.objects){
  for(const anchors of Object.values(object.evidence||{})){
   for(const anchor of anchors){
    if(issue.source_id&&anchor.source_id!==issue.source_id)continue;
    const profile=view.sources.find(s=>s.source_id===anchor.source_id);
    const hit=profile?findAnchorRow(profile,anchor):undefined;
    if(hit&&hit.row===issue.row){
     if(matched&&matched.id!==object.id)return undefined;
     matched=object;
    }
   }
  }
 }
 return matched;
}
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
 let response:Response;
 try{
  response=await fetch(path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 }catch(error){
  // 断网等 fetch 直接失败的情况不走 HTTP 响应路径，同样翻成中文。
  throw new ApiError(0,translateError(error instanceof Error?error.message:'Failed to fetch'));
 }
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
  const page=pageNumber(selector);
  return page!==undefined?`第 ${page} 页 · ${pointer}`:pointer;
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
export function isDecisionSelector(selector:Selector|undefined):boolean{
 return selector?.kind==='json_pointer'&&selector.pointer==='/decision/changes/value';
}
export function isDecisionEvidence(evidence:Evidence):boolean{return isDecisionSelector(evidence.selector);}
export function decisionSourceName(sourceId:string):string{
 return `用户纠正 · 决定 ${sourceId.slice(0,12)}…`;
}
type AnchorLike={source_ref:string;selector:unknown};
// REST 分页的页号在 selector.extensions["dataagent.page"]（F1 起的形状，1 起的响应页号），
// 旧锚点没有 extensions；同时兼容更早把页号放在 selector.page 的写法。
export function pageNumber(selector:unknown):number|undefined{
 if(!selector||typeof selector!=='object')return undefined;
 const extensions=(selector as {extensions?:unknown}).extensions;
 if(extensions&&typeof extensions==='object'){
  const value=(extensions as Record<string,unknown>)['dataagent.page'];
  if(typeof value==='number')return value;
 }
 const page=(selector as {page?:unknown}).page;
 return typeof page==='number'?page:undefined;
}
const withoutPage=(selector:unknown)=>{
 if(!selector||typeof selector!=='object')return JSON.stringify(selector);
 const rest={...(selector as Record<string,unknown>)};
 delete rest.page;
 // extensions 的 null、空对象、缺失归一成同一形状（剥掉页号后为空视同没有），
 // 其他扩展字段保留：带页号的新证据才能回退匹配 extensions:null 的旧锚点。
 const extensions=rest.extensions;
 if(extensions===null)delete rest.extensions;
 else if(extensions&&typeof extensions==='object'){
  const copy={...(extensions as Record<string,unknown>)};
  delete copy['dataagent.page'];
  if(Object.keys(copy).length)rest.extensions=copy;else delete rest.extensions;
 }
 return JSON.stringify(rest);
};
// 来源行定位：selector 带页序号时按页取对应记录（REST 分页的 JSON Pointer 各页从 0 计，
// 会重复）。兼容回退只适用于无页码的旧锚点；双方页码都明确但不相等时（如锚点数据陈旧）
// 不回退到其他页的同名 pointer，宁可不定位来源行。
export function findAnchorRow(profile:{anchors?:Record<string,AnchorLike[]>}|undefined,evidence:Evidence):{row:number;field:string}|undefined{
 if(!profile)return undefined;
 const page=pageNumber(evidence.selector);
 const target=withoutPage(evidence.selector);
 let fallback:{row:number;field:string}|undefined;
 for(const [key,anchors] of Object.entries(profile.anchors||{})){
  const dot=key.indexOf('.');
  const row=dot>0?Number(key.slice(0,dot)):NaN;
  if(!Number.isFinite(row))continue;
  const field=key.slice(dot+1);
  for(const anchor of anchors){
   if(anchor.source_ref!==evidence.source_id||withoutPage(anchor.selector)!==target)continue;
   const anchorPage=pageNumber(anchor.selector);
   if(anchorPage===page)return {row,field};
   if(anchorPage===undefined){if(!fallback)fallback={row,field};if(page===undefined)return fallback;}
  }
 }
 return fallback;
}
