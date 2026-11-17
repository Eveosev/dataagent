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
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
 const response=await fetch(path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 const data=await response.json();
 if(!response.ok)throw new ApiError(response.status,data.detail||data.error||'请求未完成');
 return data as T;
}
export const display=(value:unknown)=>value===null||value===undefined?'—':typeof value==='object'?JSON.stringify(value):String(value);
export const transformNames:Record<string,string>={identity:'保留原值',decimal:'十进制数',minor_to_major:'分 → 元（÷100）',integer:'整数',date:'日期',datetime:'带时区时间',enum:'枚举映射',combine:'组合字段',choose:'条件选择'};
export function locate(selector:Selector|undefined):string{
 if(!selector)return '—';
 if(selector.kind==='pdf_text_span'||selector.kind==='pdf_bbox')return `第 ${selector.page} 页`;
 if(selector.kind==='json_pointer')return selector.pointer||'';
 if(selector.kind==='excel_cell')return `${selector.sheet} · ${selector.range}`;
 if(selector.kind==='record_key'){
  const keys=selector.keys||{};
  return 'row' in keys?`来源行 ${String(keys.row)}`:Object.entries(keys).map(([k,v])=>`${k} = ${String(v)}`).join(' · ');
 }
 if(selector.kind==='text_span')return `字符 ${selector.char_start}–${selector.char_end}`;
 return selector.kind;
}
