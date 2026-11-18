import type {IntakeSession} from './generated/IntakeSession';
import type {Discovery} from './pages/DiscoveryPage';

// 概念分组阈值：草案/候选的概念数超过它时按概念折叠分组（FDE2-08，
// 真实制度 24 个概念一页 8000px），不超过时保持平铺网格。
export const CONCEPT_GROUP_THRESHOLD=6;

export const gapLabels:Record<string,string>={
 table_not_found:'请求的表不存在',
 declared_fk_target_outside_scope:'外键目标超出探查或披露范围',
 declared_fk_target_key_unverified:'外键目标键无法核对',
 candidate_budget_exceeded:'部分候选超出展示上限',
};

export type CatalogTable=NonNullable<Discovery['catalog']>['tables'][number];

export function sourceNameOf(session:IntakeSession,sourceId:string|undefined):string{
 const source=session.sources.find(item=>item.source_id===sourceId);
 if(!source)return '';
 return String(source.extensions?.['dataagent.display_name']||source.options?.display_name||source.locator_ref.split('/').pop());
}

// 表名 → 用户可读（FDE2-08）：文件来源的证据表显示「文件名 · 第 N 张表 /
// 第 N 页的表 / 工作表名」，不显示内部记录集 ID（table:1、<source>::table:1、
// 无表名来源的 source uuid）。数据库表名本身可读，多来源时补文件名前缀。
export function tableLabel(name:string,tables:CatalogTable[],session:IntakeSession):string{
 const table=tables.find(item=>item.name===name);
 if(!table)return name;
 const prefix=`${table.source_id}::`;
 const base=table.name.startsWith(prefix)?table.name.slice(prefix.length):table.name;
 const source=sourceNameOf(session,table.source_id);
 const docx=base.match(/^table:(\d+)$/);
 if(docx)return source?`${source} · 第 ${docx[1]} 张表`:base;
 const pdf=base.match(/^page:(\d+)(?:#(\d+))?$/);
 if(pdf)return source?`${source} · 第 ${pdf[1]} 页的表${pdf[2]?`（第 ${pdf[2]} 个）`:''}`:base;
 if(base===table.source_id)return source||base;
 // Excel 的表名是工作表标题，本身可读；仍补文件来源，符合「文件名 + 标题」。
 const locator=session.sources.find(item=>item.source_id===table.source_id)?.locator_ref||'';
 if(/\.(xlsx|xlsm)$/i.test(locator)&&source)return `${source} · ${base}`;
 const multiSource=new Set(tables.map(item=>item.source_id)).size>1;
 return multiSource&&source?`${source} · ${base}`:base;
}

// 单个概念的待决项（FDE2-08 概览里的待决数）：涉及该概念来源表的未采用
// 关系与落在该表上的覆盖缺口；全局项（来源覆盖）不属于任何概念。
export function conceptPending(table:string,draft:NonNullable<Discovery['draft']>,
 label:(name:string)=>string=(name)=>name):string[]{
 const items:string[]=[];
 for(const link of draft.unresolved_relationships||[])
  if(link.source_table===table||link.target_table===table)
   items.push(`未采用的关系 ${link.name||`${label(link.source_table)} → ${label(link.target_table)}`}`);
 for(const gap of draft.gaps||[])
  if(gap.table===table)items.push(`覆盖缺口 ${gapLabels[gap.code]||gap.code}`);
 return items;
}
