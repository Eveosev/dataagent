import {entityTypeLabel,locate,propertyLabel} from './client';
import type {OntologyRevision,Registry,RegistryEntry,Selector} from './client';

// D5c 已发布对象浏览：GET /api/ontologies 在 D4 里追加了实例计数，
// GET /api/ontologies/{id}/instances 返回一页冻结快照里的对象。这里的类型只描述
// 网页实际消费的字段，生成类型（OntologyRevision 等）保持不动。
export type BrowseRegistryEntry=RegistryEntry&{
 instance_counts?:Record<string,number>;
 published_instance_count?:number;
 current_revision_instance_counts?:Record<string,number>;
 deactivated?:boolean;
 last_published_at?:string|null;
};
export type BrowseRegistry={
 ontologies:BrowseRegistryEntry[];
 default_ontology:string|null;
 pointer:Registry['pointer'];
};

export type PropertyDefinitionView={value_type:string;required?:boolean;description?:string};
export type ConceptProperties={
 entity_type:string;
 properties:Record<string,PropertyDefinitionView>;
 identity_fields:string[];
};
export type SessionContext={
 sources:Record<string,string>;
 concepts:Record<string,ConceptProperties>;
 // 人工纠正按“对象:属性”记录原因，实例列表据此显示中文纠正来源；
 // 纠正是审核决定，不是文件里的 JSON 指针。
 corrections:Record<string,string>;
 revision:string;
};
export type InstanceAnchor={
 source_ref?:string;
 source_revision?:string;
 selector?:Selector;
 page?:number;
 paragraph?:number;
 line?:number;
 row?:number;
 sheet?:string;
 range?:string;
 unit_ref?:string;
 char_start?:number;
 char_end?:number;
};
export type InstanceLocation={
 property?:string;
 source_ref?:string;
 source_revision?:string;
 selector?:Selector;
 // 精简行的定位字段：kind/pointer/keys 只在需要还原 selector 时出现。
 kind?:string;
 pointer?:string;
 keys?:Record<string,unknown>;
 page?:number;
 paragraph?:number;
 line?:number;
 row?:number;
 sheet?:string;
 range?:string;
 unit_ref?:string;
 char_start?:number;
 char_end?:number;
};
// 精简行按来源分组：每组一份 source_ref，locations 按属性列一句话定位。
// 老形状的 source_anchors/locations 仍可读，便于与旧结果文件共存。
export type InstanceSource={
 source_ref?:string;
 source_revision?:string;
 locations:Record<string,InstanceLocation[]>;
};
export type PublishedInstance={
 ontology_id?:string;
 ontology_revision?:string;
 revision?:string;
 concept?:string;
 entity_type?:string;
 instance_id:string;
 entity_id?:string;
 id?:string;
 values:Record<string,unknown>;
 source?:InstanceSource[];
 source_refs?:string[];
 source_anchors?:Record<string,InstanceAnchor[]>;
 locations?:InstanceLocation[];
 release_ref:string;
 release_digest?:string;
 partial_release?:boolean;
 session_id:string;
 task:string;
 deactivated?:boolean;
 unresolved?:string[];
};
export type InstancePage={
 ontology_id:string;
 ontology_revision:string;
 revision:string;
 concept:string;
 entity_type:string;
 ontology_state?:string;
 deactivated?:boolean;
 items:PublishedInstance[];
 count:number;
 total:number;
 limit:number;
 has_more:boolean;
 next_cursor?:string|null;
 warnings?:{code?:string}[];
 // 当前修订无对象、旧修订有对象时的提示（FDE3-01）。
 hint?:{reason?:string;revision?:string;older_revision?:string;count?:number;concept?:string};
};

// 概念属性中文标签（FDE-11 的同一做法）：常见发现字段给中文，未收录的保留原名，
// 不猜不译。采购本体已有标签由 client.propertyLabel 负责，这里只补发现场景。
export const browsePropertyNames:Record<string,string>={
 book:'账簿',
 doc_no:'单据号',
 seq:'序号',
 amountInCents:'金额（分）',
 party_no:'客户编号',
 name:'名称',
 city:'城市',
 level:'职级',
 expense_type:'费用类型',
 limit_amount:'限额',
 note:'备注',
};
export function browsePropertyLabel(name:string):string{
 const known=propertyLabel(name);
 return known!==name?known:(browsePropertyNames[name]||name);
}
// 实体类型的中文说法统一收在 client.entityTypeNames（FDE2-11）；
// 这里只补本体库浏览特有的概念名，避免两处维护同一份字典。
export const browseConceptNames:Record<string,string>={};
export function browseConceptLabel(name:string):string{
 const known=entityTypeLabel(name);
 return known!==name?known:(browseConceptNames[name]||name);
}
// 筛选条件中文说法（FDE2-13）：比较条件只对 decimal/integer/date 属性开放。
export type FilterOp='eq'|'contains'|'gt'|'gte'|'lt'|'lte';
export const filterOpNames:Record<FilterOp,string>={
 eq:'等于',contains:'包含',gt:'大于',gte:'大于等于',lt:'小于',lte:'小于等于',
};
export const comparisonOps:FilterOp[]=['gt','gte','lt','lte'];
export const isComparisonOp=(op:FilterOp)=>comparisonOps.includes(op);
// 可比较的值类型：后端 gt/gte/lt/lte 只接受 decimal/integer/date。
export const comparableValueTypes=['decimal','integer','date'];

// 已发布实例的来源名只显示可读名，不显示上传 UUID 或本机路径。
export function sourceDisplayName(value:unknown):string{
 const text=String(value??'').trim();
 if(!text)return '来源';
 if(/^[0-9a-f]{16,}$/i.test(text))return '来源';
 const clean=text.split(/[?#]/,1)[0];
 const name=clean.split(/[\\/]/).filter(Boolean).pop()||clean;
 if(/^[0-9a-f]{16,}(\.[a-z0-9]+)?$/i.test(name))return '来源';
 return name||'来源';
}

// 从任务定义取概念属性：多概念读 concepts，legacy 单概念按 entity_type 读旧字段。
export function conceptMap(ontology:OntologyRevision|null|undefined):Record<string,ConceptProperties>{
 if(!ontology)return {};
 if(ontology.concepts&&Object.keys(ontology.concepts).length){
  return Object.fromEntries(Object.entries(ontology.concepts).map(([name,value])=>[name,{
   entity_type:value.entity_type,
   properties:value.properties||{},
   identity_fields:value.identity_fields||[],
  }]));
 }
 const name=ontology.entity_type||'';
 if(!name)return {};
 return {[name]:{entity_type:name,properties:ontology.properties||{},
  identity_fields:ontology.identity_fields||[]}};
}

// 精简行把 selector 压成定位字段；需要中文说法或识别人工纠正时再还原成 selector。
export function locationSelector(location:InstanceLocation):Selector|undefined{
 if(location.selector)return location.selector;
 const kind=location.kind;
 if(kind==='json_pointer')return {kind:'json_pointer',pointer:location.pointer,page:location.page};
 if(kind==='record_key'&&location.keys)return {kind:'record_key',keys:location.keys};
 if(location.sheet!==undefined&&location.range!==undefined)
  return {kind:'excel_cell',sheet:location.sheet,range:location.range};
 if(location.row!==undefined)return {kind:'record_key',keys:{row:location.row}};
 if(location.line!==undefined)return {kind:'record_key',keys:{line:location.line}};
 if(location.unit_ref!==undefined)
  return {kind:'text_span',unit_ref:location.unit_ref,char_start:location.char_start,char_end:location.char_end};
 if(location.page!==undefined)return {kind:'pdf_text_span',page:location.page};
 return undefined;
}

// 兼容两种结果形状：后端精简行的 source，或旧结果的 source_anchors/locations。
export function instanceSources(item:PublishedInstance):InstanceSource[]{
 if(item.source?.length)return item.source;
 const locations:Record<string,InstanceLocation[]>={};
 for(const [property,anchors] of Object.entries(item.source_anchors||{})){
  for(const anchor of anchors){
   (locations[property]||=[]).push({property,...anchor});
  }
 }
 if(!Object.keys(locations).length){
  for(const location of item.locations||[]){
   if(location.property)(locations[location.property]||=[]).push(location);
  }
 }
 return Object.keys(locations).length?[{locations}]:[];
}

// 锚点中文描述：PDF 页、Word 段/表行、CSV/数据库行、Excel 单元格都走 client.locate，
// 和对象页使用同一套说法；selector 缺失时退回后端拍平的 page/paragraph/line。
// 不在这里拼属性名：调用方用属性列标签做前缀，避免 Word 表格列名重复出现。
export function anchorLocation(anchor:InstanceAnchor):string{
 if(anchor.selector){
  const text=locate(anchor.selector);
  if(text&&text!=='—'&&text!==anchor.selector.kind)return text;
 }
 if(anchor.page!==undefined)return `第 ${anchor.page} 页`;
 if(anchor.paragraph!==undefined)return `第 ${anchor.paragraph} 段`;
 if(anchor.line!==undefined)return `第 ${anchor.line} 行`;
 if(anchor.row!==undefined)return `来源行 ${anchor.row}`;
 if(anchor.sheet&&anchor.range)return `${anchor.sheet} · ${anchor.range}`;
 return '';
}

// FDE2-13 余项：同一来源行的多个属性合并成一行定位。Word 表格一行拆成多个
// 单元格锚点（unit_ref 的 col 不同），Excel 同一行的单元格 range 也不同；
// 属性标签已经说明是哪一列，定位只保留行，避免同一个对象把同一行重复展示
// 成「城市等级 · 表 1 第 9 行 · 第 1 列」「职级 · 表 1 第 9 行 · 第 2 列」。
export function anchorRowLocation(anchor:InstanceAnchor,located:string):string{
 if(anchor.selector?.kind==='text_span'){
  const match=String(anchor.selector.unit_ref||'').match(/^table:(\d+)\/row:(\d+)/);
  if(match)return `表 ${match[1]} 第 ${match[2]} 行`;
 }
 if(anchor.selector?.kind==='excel_cell'){
  const sheet=String(anchor.selector.sheet||'');
  const range=String(anchor.selector.range||'');
  const match=range.match(/^([A-Za-z]+)(\d+)(?::([A-Za-z]+)(\d+))?$/);
  // 只合并单行区间；跨行范围的定位保留原样，避免把两行内容并成一行。
  if(match&&(!match[4]||match[4]===match[2])){
   const row=Number(match[2]);
   return sheet?`${sheet} · 第 ${row} 行`:`第 ${row} 行`;
  }
 }
 return located;
}
