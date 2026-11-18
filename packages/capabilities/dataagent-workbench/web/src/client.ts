import type {SourceProfile} from './generated/SourceProfile';
import type {IntakeSession} from './generated/IntakeSession';
import type {OntologyRevision} from './generated/OntologyRevision';
import type {MappingSpec,FieldBinding} from './generated/MappingSpec';
import type {MappingPreview} from './generated/MappingPreview';
import type {Discovery} from './pages/DiscoveryPage';
export type {SourceProfile,IntakeSession,OntologyRevision,MappingSpec,FieldBinding};
export type Preview=MappingPreview & {review_state:string; mapping_reused?:boolean; corrections?:unknown[]};
export type Draft={bindings?:Record<string,FieldBinding>;source_bindings?:Record<string,Record<string,FieldBinding>>;selected_field?:string;source_id?:string;record_index?:number};
// ontology_concept：任务固定映射目标的概念名（后端 _target 解析）；多概念本体
// 的页面一律按它取概念，legacy 单概念本体忽略它走旧字段。
export type View={session:IntakeSession;profiles:SourceProfile[];ontology:OntologyRevision;ontology_concept?:string;preview:Preview|null;draft:Draft;mapping_reused:boolean;discovery:Discovery|null;correction_views?:CorrectionView[];dispositions?:DispositionEntry[];disposition_options?:DispositionOption[];mappings?:Record<string,MappingSpec>};
export type Selector={kind:string;page?:number;char_start?:number;char_end?:number;bbox?:number[];pointer?:string;range?:string;sheet?:string;keys?:Record<string,unknown>;field?:string;unit_ref?:string;extensions?:Record<string,unknown>|null};
export type Evidence={source_id:string;selector:Selector};
export type WorkObject={id:string;entity_type:string;values:Record<string,unknown>;evidence:Record<string,Evidence[]>;unresolved:string[];extensions?:Record<string,unknown>|null;conflicts?:ConflictDetail[]};
export type Correction={decision_ref:string;entity_id:string;property:string;value:unknown;reason:string};
export type CorrectionView={decision_ref:string;entity_id:string;property:string;value:unknown;
 mapping_value:unknown;mapping_revision:string;mapping_changed:boolean};
export type Issue={code?:string;target?:string;row?:number;entity_id?:string;detail?:string;source_id?:string;object?:string};
// 冲突字段各来源原值（后端 conflict_details）：并排显示 + 一键采用的数据来源。
export type ConflictValue={source_id:string;source_name:string;locator_ref:string;kind:string;value:unknown;values:unknown[];locations:string[]};
export type ConflictDetail={entity_id:string;object?:string;field:string;reason?:string;values:ConflictValue[]};
// 来源处置（后端 disposition_options / dispositions）：被拦问题的出路。
// scope:'source' 是整源处置（本任务不使用该来源）——线上仍是 partition_not_applicable
// 不带分区（工具 schema 的 literal 没有第三个动作），审计记录由后端写成 ignore_source。
export type DispositionOption={action:'partition_not_applicable'|'exclude_record';scope?:'source';source_id:string;source_name:string;partition?:number|string|null;record?:number;gap?:string;reason_hint?:string};
export type DispositionEntry={action:string;source_id:string;reason:string;partition?:number|string;record?:number;record_values?:Record<string,unknown>;decision_ref?:string;recorded_at?:string};
export type ObjectView={session:IntakeSession;ontology:OntologyRevision;ontology_revision:string;ontology_concept?:string;ontology_draft:Record<string,unknown>|null;
 sources:(SourceProfile&{display_name:string})[];objects:WorkObject[];corrections:Correction[];correction_views:CorrectionView[];issues:Issue[];
 conflicts:ConflictDetail[];dispositions:DispositionEntry[];disposition_options:DispositionOption[];
 review_state:string|null;preview_ref?:string;mapping_revision:string|null;draft:Draft};
// 本体注册表（GET /api/ontologies）：内置 / 发现发布 / 已停用；default_ontology 为
// 注册表当前指针（指针被停用清空时后端回退到内置）。
export type RegistryEntry={id:string;ontology_revision:string;origin:'builtin'|'discovery';state:'active'|'retired';title:string;concepts:string[];default_concept:string;source_snapshot:string;published_at:string;published_by:string;retired_at:string|null;retired_by:string|null;retire_reason:string|null;registry_revision:string;is_default:boolean};
export type Registry={ontologies:RegistryEntry[];default_ontology:string|null;pointer:{ontology_id:string|null;concept:string;updated_at?:string;updated_by?:string}|null};
export const originNames:Record<string,string>={builtin:'内置',discovery:'发现发布'};
export const ontologyStateNames:Record<string,string>={active:'在用',retired:'已停用'};
// 标题展示：内置 procurement 沿用中文习惯名，其余用注册表标题（缺省回 ID）。
export const builtinTitles:Record<string,string>={procurement:'采购资料'};
export const registryTitle=(entry:Pick<RegistryEntry,'id'|'title'>)=>builtinTitles[entry.id]||entry.title||entry.id;
// 面包屑用的本体名（FDE2-11）：任务页不再写死「采购资料」，按任务目标本体
// 显示注册表标题；注册表拉取失败时由调用方退回内置习惯名或概念名。
let ontologyTitleCache:Promise<Record<string,string>>|null=null;
// 发布会往注册表里写入新本体：确认发布后清掉缓存，面包屑下次进入任务页
// 重新拉取，同页签新建的任务也能拿到新标题。
export function invalidateOntologyTitles(){ontologyTitleCache=null;}
export function ontologyTitles():Promise<Record<string,string>>{
 if(!ontologyTitleCache)ontologyTitleCache=api<Registry>('/api/ontologies')
  .then(data=>Object.fromEntries((data.ontologies||[]).map(entry=>[entry.id,registryTitle(entry)])))
  // 失败不缓存，下一次调用重试，避免一次网络故障把空结果钉死到页签关闭。
  .catch(()=>{ontologyTitleCache=null;return {};});
 return ontologyTitleCache;
}
// 发布候选（GET /api/sessions/{sid}/publish/candidate）：人在网页确认的精确对象，
// 携带完整定义、来源摘要与全部处置记录。
export type PublishDisposition={kind:string;ref:string;action:'exclude'|'accept';reason:string};
export type PublishCandidate={
 ref:string;session_id:string;draft_ref:string;state:'candidate'|'published';
 ontology_id:string;ontology_revision:string;title:string;
 definition:{id:string;revision:string;concepts:Record<string,{entity_type:string;identity_fields:string[];properties:Record<string,{value_type:string;required?:boolean;description?:string}>}>;relations:Record<string,{roles:string[];subject_concept?:string;object_concept?:string}|string[]>};
 definition_digest:string;source_revision:string;source_snapshot:string;structure_fingerprint:string;session_revision:string;
 dispositions:PublishDisposition[];candidate_revision?:string;publication_ref?:string;
};
// 问题分级对应后端约定：整批保存被任何未解决问题拦下（dataagent-ontology
// service.py 的 prepare_review），其中这三个 code 能被对象页的实例纠正清除
//（dataagent_workbench intake_service 的 _RESOLVABLE_ISSUES），其余问题在修订
// 映射或来源前一直阻断。文案镜像 intake_service 的 _ISSUE_REASONS。
export const correctableIssueCodes=new Set(['ontology.conflicting_values','ontology.required_value_missing','ontology.conversion_failed']);
export const issueReasons:Record<string,string>={
 'ontology.conflicting_values':'各来源的字段值不一致',
 'ontology.required_value_missing':'缺少必填值',
 'ontology.required_binding_missing':'必填属性没有映射',
 // FDE2-11：不再用采购口径的「单据号」，通用说法指向身份字段值。
 'ontology.identity_unresolved':'缺少身份字段值，无法确定对象',
 'ontology.conversion_failed':'值无法按目标类型转换',
 'ontology.evidence_missing':'值没有来源定位',
 'ontology.incomplete_source':'来源未完整读取',
 'ontology.source_unmapped':'该来源未用于当前映射',
 'ontology.relation_unresolved':'关联字段不完整',
 'ontology.correction_conflict':'网页纠正无法沿用',
 'ontology.no_records':'没有可映射的记录',
 'record_attribution_unverified':'该记录的引文归属未核实',
};
export const issueBlocksSave=(issue:Issue)=>!correctableIssueCodes.has(issue.code||'');
// 按行重复的问题 code（FDE2-06）：同一列同一类问题跨多行时按根因合并成一条。
export const rowLevelIssueCodes=new Set(['ontology.conversion_failed','ontology.required_value_missing','ontology.identity_unresolved','ontology.evidence_missing','record_attribution_unverified']);
// 同一行同一列：转换失败的记录不再重复报「缺少必填值」（后端同款去重，
// 页面在这里再做一遍，路由改写注入的原始问题也能按同一口径计数）。
export function dedupeIssues(issues:Issue[]):Issue[]{
 const failed=new Set(issues.filter(issue=>issue.code==='ontology.conversion_failed'&&issue.row!==undefined)
  .map(issue=>`${issue.source_id??''}|${issue.row}|${issue.target??''}`));
 return issues.filter(issue=>!(issue.code==='ontology.required_value_missing'
  &&failed.has(`${issue.source_id??''}|${issue.row??''}|${issue.target??''}`)));
}
// 问题点回对象（不误链优先）：只有能唯一确定对象时才给入口——带 entity_id 的直接
// 命中，或行号与来源都明确且该行在问题来源里有锚点。只有行号、来源不明、或该行在
// 问题来源里没有锚点时不给入口，绝不链接到另一来源同序号的对象（问题归属标识待后端
// D0 卡补充后再放宽）。
export function issueObject(issue:Issue,view:Pick<ObjectView,'objects'|'sources'>):WorkObject|undefined{
 if(issue.entity_id){
  const target=view.objects.find(o=>o.id===issue.entity_id);
  if(target)return target;
 }
 if(issue.row===undefined||!issue.source_id)return undefined;
 const profile=view.sources.find(s=>s.source_id===issue.source_id);
 if(!profile)return undefined;
 for(const object of view.objects){
  for(const anchors of Object.values(object.evidence||{})){
   for(const anchor of anchors){
    if(anchor.source_id!==issue.source_id)continue;
    const hit=findAnchorRow(profile,anchor);
    if(hit&&hit.row===issue.row)return object;
   }
  }
 }
 return undefined;
}
export class ApiError extends Error {constructor(public status:number,message:string,public raw:string=message){super(message);}}
// 后端原始报错按原文透出会给用户看不懂的英文；已知文案在这里换成中文说法。
const errorTexts:Record<string,string>={
 'required property remains unresolved':'必填属性仍未解决，请先在对象页核对后再保存',
 'identity remains unresolved':'对象标识仍未解决，请先核对单据编号',
 'no instance correction to revalidate':'没有需要重新校验的纠正',
 'correction entity no longer exists':'纠正的对象已不存在，请重新载入',
 'null corrections require an explicit unresolved decision':'纠正为空值需要先明确标记为未解决',
 'identity correction would merge objects; resolve the mapping explicitly':'标识纠正会使多个对象合并，请先调整映射',
 'preview contains unresolved issues':'预览仍有未解决的问题，请逐项核对后再保存',
 'preview does not need correction validation':'当前预览不需要重新校验，请刷新页面后重试',
 'source is used by the current mapping; dispose a partition or a record instead':'该来源正被当前映射使用，请改为处置分区或记录',
 'partition is not part of the source observation':'该分区不在来源观察范围内',
 'unsupported file type':'暂不支持该文件类型',
 'file exceeds 32 MiB limit':'文件超过 32 MB 限制',
 'Failed to fetch':'网络连接失败，请稍后重试',
 'Not Found':'当前服务不支持该操作，请更新工作台服务后再试',
 // 发布与停用（D1 门禁）：拒绝原文统一换成中文说法，页面再按原文分类给
 // 「重新探查」或「刷新候选」入口。
 'candidate is stale; prepare it again':'发布候选已过期，请让 Agent 重新生成候选后再确认',
 'candidate was already published':'该候选已发布过，请刷新后查看本体库',
 'discovery draft changed; prepare the candidate again':'草案已更新，请让 Agent 重新生成候选',
 'discovery draft changed; complete the latest draft':'草案已更新，请补全最新草案',
 'task changed; prepare the candidate again':'任务已有更新，请让 Agent 重新生成候选',
 'discovery session changed; reload inputs':'发现任务已有更新，请重新载入',
 'source changed since it was observed; discover again':'来源在观察后发生了变化，请重新探查',
 'source snapshot changed; discover again':'来源快照已变化，请重新探查',
 'source snapshot reference is missing; discover again':'来源快照缺失，请重新探查',
 'source structure changed; discover again':'来源结构已变化，请重新探查',
 'source observation changed; discover again':'来源观察已变化，请重新探查',
 'source file is no longer readable; discover again':'来源文件已不可读，请重新探查',
 'rejected discovery drafts cannot be published':'已退回的草案不能发布',
 'retiring an ontology requires explicit confirmation':'停用本体需要明确确认',
 'retiring an ontology needs a reason':'停用本体必须填写原因',
 'the builtin ontology is the workspace fallback and cannot be retired':'内置本体是工作区兜底，不能停用',
 'ontology is already retired':'该本体已停用',
 'ontology not registered':'本体不存在或未注册',
 'registry changed; reload before retiring':'本体注册表已有更新，请刷新后重试',
};
export function translateError(message:string):string{return errorTexts[message.trim()]||message;}
// 用户可见的后端原文（问题 detail、报错 message）统一在这里中文化：已知原文
// 映射成中文说法进主文案；未识别的英文原文不直接铺在主文案里，只作为折叠
// 「详情」的原始证据保留（沿用 technicalDetail 的路径脱敏）。中文原文直接展示。
const detailTexts:Record<string,string>={
 'nonfinite number':'数值超出可表示范围',
 'non-integral value':'不是整数',
 'timezone required for naive datetime':'时间缺少时区，无法转换',
 'unknown enum value':'不在枚举范围内',
 'boolean must be true or false':'布尔值只认 true / false',
 'nested value needs an explicit scalar mapping':'嵌套值需要显式的标量映射',
 'relation role has no value':'关联字段没有值',
 'probe returned the same checkpoint without progress':'探查没有新进展，已暂停',
 'segment limit reached in one advance':'单次探查分段数达到上限',
 "[<class 'decimal.ConversionSyntax'>]":'不是有效的数字',
};
// 前缀匹配：后端在固定原文后拼接具体项（如不再可解析的字段名），中文说法
// 保留拼接部分，字段名原样透出。
const detailPrefixes:[string,string][]=[
 ['recorded fields no longer resolve in the source','来源字段在当前来源中已不再可解析'],
];
// 原始异常（可能带无效来源值）只给中文摘要；完整原文保留在折叠「详情」里。
const exceptionPrefixes:[string,string][]=[
 ['Invalid isoformat string','日期时间格式无法解析'],
];
export type HumanDetail={summary:string;detail?:string};
export function humanDetail(raw:unknown):HumanDetail{
 const text=String(raw??'').trim();
 if(!text)return {summary:''};
 if(detailTexts[text])return {summary:detailTexts[text]};
 for(const [prefix,summary] of exceptionPrefixes){
  if(text.startsWith(prefix))return {summary,detail:text};
 }
 for(const [prefix,summary] of detailPrefixes){
  if(text.startsWith(prefix)){
   const rest=text.slice(prefix.length).replace(/^[\s:：]+/,'');
   return {summary:rest?`${summary}：${rest}`:summary};
  }
 }
 // 中文原文按原文进主文案；未识别的英文或混合原文只进折叠详情。判定不数
 // 字符多少：只要含拉丁字母就整段进详情——夹着 NaN 之类短英文片段的中文
 // 原文同样不算「映射后的中文」，不能凭中文占多数直通主文案。
 if(!/[A-Za-z]/.test(text)&&/[\u4e00-\u9fff]/.test(text))return {summary:text};
 return {summary:'',detail:text};
}
// 探查缺口（FDE-10）：分区级缺口用中文直说，不显示内部代码。
export const gapNames:Record<string,string>={
 ocr_engine_missing:'需要 OCR 引擎',ocr_empty:'该页没有可读文本（可能是空白页）',
 key_missing:'缺少身份字段值',time_budget_exceeded:'读取时间用尽，可继续探查',
 malformed_row:'行列数不齐',invalid_input:'文件内容无法读取',probe_failed:'材料读取失败',
};
export type SourceProblem={title:string;detail?:string;next:string};
// 坏输入直说（FDE-10）：探查失败或零数据行时给出中文原因与下一步；
// 原始报错只作为 detail 保留，由页面收进折叠的「技术详情」，不直接展示。
export function sourceProblem(profile:{kind?:string;records?:Record<string,unknown>[];metadata?:Record<string,unknown>}|undefined):SourceProblem|undefined{
 if(!profile)return undefined;
 const error=profile.metadata?.['probe_error'] as {code?:string;detail?:string}|undefined;
 if(error){
  const text=String(error.detail||'');
  if(/no rows/i.test(text))return {title:'文件是空的，没有可读取的内容',detail:text,next:'请更换文件后新建接入'};
  if(/not a zip file/i.test(text))return {title:profile.kind==='docx'?'不是有效的 Word 文件':'不是有效的 Excel 文件',detail:text,next:'请更换文件后新建接入'};
  return {title:'材料读取失败',detail:text,next:'请更换文件后新建接入'};
 }
 if((profile.records||[]).length===0&&profile.metadata?.['total_rows']===0)
  return {title:'只有表头，没有数据行',next:'请补全数据行或更换文件后新建接入'};
 return undefined;
}
// 技术详情（折叠展示）：原始报错里的绝对路径只保留文件名，避免泄露本机目录。
export function technicalDetail(text:unknown):string{
 return String(text||'').replace(/[^\s:：,，;；)）]*\/[^\s:：,，;；)）]+/g,part=>part.split('/').pop()||part).trim();
}
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
 let response:Response;
 try{
  response=await fetch(path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 }catch(error){
  // 断网等 fetch 直接失败的情况不走 HTTP 响应路径，同样翻成中文。
  throw new ApiError(0,translateError(error instanceof Error?error.message:'Failed to fetch'));
 }
 const data=await response.json();
 if(!response.ok)throw new ApiError(response.status,translateError(String(data.detail||data.error||'请求未完成')),String(data.detail||data.error||'请求未完成'));
 return data as T;
}
export const display=(value:unknown)=>value===null||value===undefined?'—':typeof value==='object'?JSON.stringify(value):String(value);
// D0 起本体可携带多概念，legacy 单概念字段（entity_type / properties）在生成类型里
// 变为可选；运行时单概念任务仍按原样序列化这些字段。页面统一从这里取任务固定
// 概念：多概念本体走 concepts[任务固定的 concept]，旧字段兜底。
export const legacyProperties=(ontology:{properties?:Record<string,{required?:boolean}>}|null|undefined):Record<string,{required?:boolean}>=>ontology?.properties||{};
export const legacyEntityType=(ontology:{entity_type?:string}|null|undefined):string=>ontology?.entity_type||'';
export type ConceptView={name:string;entity_type:string;properties:Record<string,{required?:boolean}>;identity_fields:string[]};
// 任务固定概念：ontology_concept 命中 concepts 时用它；多概念但未给名字时退到
// 第一个概念（后端 _target 总会解析出名字，这里只是兜底）；无 concepts 的 legacy
// 定义按 entity_type 单概念读旧字段。
export function conceptOf(ontology:OntologyRevision|null|undefined,concept?:string|null):ConceptView{
 const concepts=ontology?.concepts;
 if(concepts&&Object.keys(concepts).length){
  const name=concept&&concepts[concept]?concept:Object.keys(concepts)[0];
  const found=concepts[name];
  return {name,entity_type:found.entity_type,properties:found.properties||{},identity_fields:found.identity_fields||[]};
 }
 return {name:legacyEntityType(ontology),entity_type:legacyEntityType(ontology),
  properties:legacyProperties(ontology),identity_fields:ontology?.identity_fields||[]};
}
export const transformNames:Record<string,string>={identity:'保留原值',decimal:'十进制数',minor_to_major:'分 → 元（÷100）',integer:'整数',date:'日期',datetime:'带时区时间',enum:'枚举映射',combine:'组合字段',choose:'条件选择'};
// 中英对照标签（FDE-11）：本体属性、实体类型与审核状态都有中文说法；
// 没有对应中文时保留原名，不猜不译。
export const propertyNames:Record<string,string>={number:'单据编号',amount:'金额',currency:'币种',issuer:'开票方'};
export const propertyLabel=(name:string)=>propertyNames[name]||name;
// 实体类型中文标签（FDE2-11）：发现任务的常见英文实体名给中文说法；
// 未收录的保留原名，不猜不译。
export const entityTypeNames:Record<string,string>={
 PurchaseDocument:'采购单据',SalesOrder:'销售单',SalesOrderLine:'销售明细',Customer:'客户',
 ExpenseLine:'费用明细',ExpenseReport:'费用报销单',TravelRequest:'差旅申请',
 TravelItinerary:'行程',Reimbursement:'报销单',ExpenseCategory:'费用类别',
 TravelPolicy:'差旅标准',Employee:'员工',Department:'部门',City:'城市',
 CostCenter:'成本中心',Invoice:'发票',
};
export const entityTypeLabel=(name:string)=>entityTypeNames[name]||name;
// 草案实体 / 概念名（FDE2-11）：Agent 起的中文名保留原名，英文名查实体
// 类型字典；都没有时保留原名。
export function draftEntityLabel(name:string):string{
 if(/[\u4e00-\u9fff]/.test(name))return name;
 return entityTypeLabel(name);
}
// 概念徽标（FDE2-11）：本体定义里概念名本身是中文时直接用（发现任务的
// Agent 常用中文命名），否则查实体类型字典，都没有时保留原名。
export function conceptLabel(concept:{name:string;entity_type:string}):string{
 if(/[\u4e00-\u9fff]/.test(concept.name))return concept.name;
 return entityTypeLabel(concept.entity_type);
}
// 值类型中文标签（FDE2-11）：本体值类型（string/decimal…）与来源声明类型
// （SQLite 的 text/numeric/date…）两套英文名统一成中文说法；未收录的保留原名。
export const valueTypeNames:Record<string,string>={
 string:'文本',decimal:'数字',integer:'整数',boolean:'布尔',date:'日期',datetime:'日期时间',reference:'引用',
 text:'文本',numeric:'数字',real:'数字',float:'数字',blob:'二进制',int:'整数',
};
export const valueTypeLabel=(name:string|undefined|null)=>name?valueTypeNames[name]||name:'—';
export const reviewStateNames:Record<string,string>={unreviewed:'未核对',needs_revalidation:'需重新校验',approved:'已通过',rejected:'已退回'};
export function locate(selector:Selector|undefined,field?:string):string{
 if(!selector)return '—';
 if(selector.kind==='pdf_text_span'||selector.kind==='pdf_bbox')return `第 ${selector.page} 页`;
 if(selector.kind==='json_pointer'){
  const pointer=selector.pointer||'';
  const page=pageNumber(selector);
  return page!==undefined?`第 ${page} 页 · ${pointer}`:pointer;
 }
 if(selector.kind==='excel_cell')return `${selector.sheet} · ${selector.range}`;
 if(selector.kind==='record_key')return locateRecordKey(selector);
 if(selector.kind==='text_span'){
  // Word 表格单元格与段落：unit_ref 已指到表/行/列（或第几段），
  // 比字符偏移可读；列名优先用调用方给出的字段名。
  const unit=selector.unit_ref||'';
  const table=unit.match(/^table:(\d+)\/row:(\d+)(?:\/col:(\d+))?$/);
  if(table)return `表 ${table[1]} 第 ${table[2]} 行`+(field?` · ${field}`:table[3]?` · 第 ${table[3]} 列`:'');
  const paragraph=unit.match(/^paragraph:(\d+)$/);
  if(paragraph)return `第 ${paragraph[1]} 段`;
  return `字符 ${selector.char_start}–${selector.char_end}`;
 }
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
