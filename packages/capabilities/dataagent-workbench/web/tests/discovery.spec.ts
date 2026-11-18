import {expect, test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import type {Discovery} from '../src/pages/DiscoveryPage';

let workspace=process.env.DATAAGENT_TEST_WORKSPACE||'';
const python=process.env.DATAAGENT_TEST_PYTHON;

// verify_browser.py 只把服务 URL/token/解释器传给 Playwright，不传工作区路径。
// 上传一个探针文件取得 locator_ref，再到系统临时目录里找到同一文件，从而定位
// 当前服务的工作区；测试自身仍走真实后端。
async function resolveWorkspace(page:Page){
 if(workspace)return;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':'discovery-workspace-probe.csv'},
  data:'probe\n',
 });
 expect(response.ok(),await response.text()).toBeTruthy();
 const {locator_ref}=await response.json() as {locator_ref?:string};
 const root=os.tmpdir();
 const found=fs.readdirSync(root).filter(name=>name.startsWith('dataagent-ui-'))
  .map(name=>path.join(root,name))
  .filter(dir=>fs.existsSync(path.join(dir,'.dataagent','db','workbench.sqlite3')))
  .find(dir=>{
   const file=path.resolve(dir,String(locator_ref||''));
   return file.startsWith(path.resolve(dir)+path.sep)&&fs.existsSync(file);
  });
 if(!found||!locator_ref)throw new Error(`cannot find the running workspace for ${locator_ref}`);
 fs.rmSync(path.resolve(found,locator_ref),{force:true});
 workspace=found;
}
test.beforeEach(async({page})=>{await resolveWorkspace(page);});

function callTool(name:string, args:Record<string,unknown>){
 const request={jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}};
 const line=execFileSync(python!,['-m','dataagent_workbench.interfaces.mcp_server'],{
  cwd:workspace,input:JSON.stringify(request)+'\n',encoding:'utf8',
 });
 const {result}=JSON.parse(line);
 expect(result.isError).toBe(false);
 const summary=JSON.parse(result.content[0].text);
 return JSON.parse(fs.readFileSync(path.join(workspace!,summary.result_path),'utf8')).data;
}

test('SQLite 上传、工具提交本体草案、工作台审核',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 const database=path.join(workspace!,'sales-discovery.db');
 fs.rmSync(database,{force:true});
 const sql=fs.readFileSync(path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql'));
 execFileSync('sqlite3',[database],{input:sql});
 await page.goto('/');
 await page.getByLabel('接入目标').fill('识别销售订单和订单明细');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible();
 await expect(page.getByText('观测值匹配',{exact:false})).toBeVisible();
 // 复制给用户转交 Agent 的指令只用业务话术，不出现内部工具名（FDE2-12）。
 await expect(page.getByText(/intake_inference|ontology_discovery_propose|ontology_publish_prepare/)).toHaveCount(0);
 const session_id=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session');
 const request=callTool('intake_inference',{session_id}) as Discovery & {
  expected_revision:string;source_revision:string;
 };
 const fk=request.catalog!.relationships.find(link=>link.origin==='declared');
 callTool('ontology_discovery_propose',{
  session_id,expected_revision:request.expected_revision,
  proposal:{
   source_revision:request.source_revision,
   entities:[
    {name:'销售单',table:'doc_hdr',grain:'每个账簿内的一份销售单',identity:['book','doc_no']},
    {name:'销售明细',table:'doc_line',grain:'每份销售单的一条明细',identity:['book','doc_no','seq'],
     properties:[{name:'金额（分）',column:'cents'}]},
   ],
   relationships:[{name:'所属订单',evidence_id:fk!.id}],
  },
 });
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible();
 await expect(page.getByText('每份销售单的一条明细')).toBeVisible();
 await expect(page.getByText('所属订单')).toBeVisible();
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible();
 await page.reload();
 await expect(page.getByText('已通过审核').first()).toBeVisible();
 await expect(page.getByText('待核对',{exact:true})).toBeVisible();
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'discovery-live.png'),fullPage:true,
 });
});

// 两张表的合成 Word 制度：发现页的表名显示「文件名 · 第 N 张表」，而不是
// 内部记录集 ID（table:2、<source>::table:1）。
function buildTwoTableDocx(target:string){
 const script=`
from docx import Document
import sys
document=Document()
document.add_heading('费用制度',level=1)
for rows in (
    (['项目','金额'],['A','1'],['B','2']),
    (['类型','限额'],['X','10'],['Y','20']),
):
    table=document.add_table(rows=len(rows),cols=2)
    for row_index,row in enumerate(rows):
        for column,value in enumerate(row):
            table.cell(row_index,column).text=value
document.save(sys.argv[1])
`;
 // python-docx 只在数据层依赖里：用 dataagent-data 的 venv 生成。
 const dataPython=path.resolve('../../dataagent-data/.venv/bin/python');
 execFileSync(dataPython,['-c',script,target]);
}

test('docx 与 xlsx 可在网页勾选本体发现发起，表名不显示内部 ID（FDE2-08）',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(180000);
 const docx=path.join(workspace!,'两表制度.docx');
 buildTwoTableDocx(docx);
 const xlsx=path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.xlsx');
 await page.goto('/');
 await page.getByLabel('接入目标').fill('从制度文档与发票表发现本体');
 await page.getByLabel('选择材料').setInputFiles([docx,xlsx]);
 // 文件材料（docx + xlsx，多文件）也能勾选「本体发现」发起。
 await expect(page.getByRole('radio',{name:'从数据库发现本体'})).toBeVisible();
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible({timeout:30000});
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:30000});
 const session_id=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session');
 const request=callTool('intake_inference',{session_id}) as Discovery & {
  expected_revision:string;source_revision:string;
 };
 const docxTable=request.catalog!.tables.find(table=>/(^|::)table:1$/.test(table.name))!;
 const columns=Object.keys(docxTable.columns);
 callTool('ontology_discovery_propose',{
  session_id,expected_revision:request.expected_revision,
  proposal:{
   source_revision:request.source_revision,
   entities:[{name:'费用项目',table:docxTable.name,grain:'每条费用项目一行',
    identity:[columns[0]],properties:[{name:'金额',column:columns[1]}]}],
   relationships:[],
  },
 });
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 // 未建模的表显示来源文件名 + 表序号（或表名），不显示内部 ID。
 const notice=page.locator('.notice.amber').filter({hasText:'待核对'});
 await expect(notice).toContainText('两表制度.docx · 第 2 张表');
 await expect(notice).toContainText('invoices.xlsx · ');
 await expect(page.locator('main')).not.toContainText('::table:');
 // 草案来源表与证据区的显示名同口径。
 await expect(page.locator('.discovery-entity').first()).toContainText('两表制度.docx · 第 1 张表');
 await expect(page.locator('.discovery-table summary').filter({hasText:'两表制度.docx · 第 1 张表'})).toHaveCount(1);
});

test('概念多时草案按概念折叠分组并支持待决筛选（FDE2-08）',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(120000);
 const database=path.join(workspace!,'grouping-discovery.db');
 fs.rmSync(database,{force:true});
 const sql=fs.readFileSync(path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql'));
 execFileSync('sqlite3',[database],{input:sql});
 await page.goto('/');
 await page.getByLabel('接入目标').fill('多概念分组核对');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session');
 const request=callTool('intake_inference',{session_id:sid}) as Discovery & {
  expected_revision:string;source_revision:string;
 };
 const fk=request.catalog!.relationships.find(link=>link.origin==='declared');
 callTool('ontology_discovery_propose',{
  session_id:sid,expected_revision:request.expected_revision,
   proposal:{source_revision:request.source_revision,entities:[
   {name:'销售单',table:'doc_hdr',grain:'每个账簿内的一份销售单',identity:['book','doc_no'],
    properties:[{name:'客户',column:'party_no'}]},
   {name:'销售明细',table:'doc_line',grain:'销售单的一条明细',identity:['book','doc_no','seq']},
  ],relationships:[{name:'所属订单',evidence_id:fk!.id}]},
 });
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 // 概念不多时保持平铺。
 await expect(page.getByTestId('concept-groups')).toHaveCount(0);
 // 路由改写把草案扩成 8 个概念（真实制度 24 个概念的形态），并留一条未采用
 // 关系：只有被它触及的概念有待决项。
 const viewRoute=`**/api/sessions/${sid}/view`;
 await page.route(viewRoute,async route=>{
  const response=await route.fetch();
  const body=await response.json();
  const draft=body.discovery.draft;
  if(draft){
   draft.entities=[...draft.entities,...Array.from({length:6},(_,index)=>({
    name:`备选概念${index+1}`,table:'party',grain:'每个备选概念一行',identity:['party_no'],
    properties:[{name:'名称',column:'nm'}],extension_columns:[],
   }))];
   draft.unresolved_relationships=[{id:'injected',origin:'sample_supported',
    source_table:'party',source_columns:['party_no'],target_table:'doc_hdr',target_columns:['book'],
    matched_rows:2,checked_rows:2,sampled:false,ambiguous:false,cardinality:'many_to_one',name:'备选关联'}];
  }
  await route.fulfill({response,json:body});
 });
 // 分组折叠：概要（概念名、身份、属性数、证据来源、待决数）可见，正文收起。
 const groups=page.getByTestId('concept-groups');
 await expect(groups).toBeVisible({timeout:20000});
 const summary=page.getByTestId('concept-group-销售单').locator('summary');
 await expect(summary).toContainText('身份 book + doc_no');
 await expect(summary).toContainText('1 个属性');
 await expect(summary).toContainText('证据来源 doc_hdr');
 await expect(summary).toContainText('待决 1 项');
 await expect(page.getByText('每个账簿内的一份销售单')).toBeHidden();
 // 顶部概念目录列出全部概念。
 await expect(groups.locator('.concept-toc')).toContainText('销售明细');
 await expect(groups.locator('.concept-toc')).toContainText('备选概念6');
 // 逐个展开后才显示正文。
 await summary.click();
 await expect(page.getByText('每个账簿内的一份销售单')).toBeVisible();
 // 只看有待决项：没有待决的概念不显示。
 await page.getByLabel('只看有待决项').check();
 await expect(page.getByTestId('concept-group-销售单')).toBeVisible();
 await expect(page.getByTestId('concept-group-销售明细')).toHaveCount(0);
 await expect(page.getByTestId('concept-group-备选概念1')).toBeVisible();
 await page.unroute(viewRoute);
});
