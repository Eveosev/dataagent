import {expect, test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import type {Discovery} from '../src/pages/DiscoveryPage';
import {awaitEvidenceProbed,slowTimeout,uniqueTag} from './support';

let workspace=process.env.DATAAGENT_TEST_WORKSPACE||'';
const python=process.env.DATAAGENT_TEST_PYTHON;

// verify_browser.py 只把服务 URL/token/解释器传给 Playwright，不传工作区路径。
// 上传一个探针文件取得 locator_ref，再到系统临时目录里找到同一文件，从而定位
// 当前服务的工作区；测试自身仍走真实后端。
async function resolveWorkspace(page:Page){
 if(workspace)return;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':`discovery-workspace-probe-${uniqueTag()}.csv`},
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
 // 共享工作区里的文件名带用例级唯一后缀：不删除也不覆盖其他并行用例的文件。
 const database=path.join(workspace!,`sales-discovery-${uniqueTag()}.db`);
 const sql=fs.readFileSync(path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql'));
 execFileSync('sqlite3',[database],{input:sql});
 await page.goto('/');
 await page.getByLabel('接入目标').fill('识别销售订单和订单明细');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从材料发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible();
 await awaitEvidenceProbed(page);
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
 // FDE2-13：390px 窄屏下发现页不横向溢出（草案表与证据表各自横向滚动）。
 await page.setViewportSize({width:390,height:844});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
 expect(overflow).toBeLessThanOrEqual(0);
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'discovery-narrow.png'),fullPage:true,
 });
 await page.setViewportSize({width:1280,height:720});
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
 slowTimeout(180000);
 const docxName=`两表制度-${uniqueTag()}.docx`;
 const docx=path.join(workspace!,docxName);
 buildTwoTableDocx(docx);
 const xlsx=path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.xlsx');
 await page.goto('/');
 await page.getByLabel('接入目标').fill('从制度文档与发票表发现本体');
 await page.getByLabel('选择材料').setInputFiles([docx,xlsx]);
 // 文件材料（docx + xlsx，多文件）也能勾选「本体发现」发起。
 await expect(page.getByRole('radio',{name:'从材料发现本体'})).toBeVisible();
 await page.getByRole('radio',{name:'从材料发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible({timeout:30000});
 await awaitEvidenceProbed(page,30000);
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
 await expect(notice).toContainText(`${docxName} · 第 2 张表`);
 await expect(notice).toContainText('invoices.xlsx · ');
 await expect(page.locator('main')).not.toContainText('::table:');
 // 草案来源表与证据区的显示名同口径。
 await expect(page.locator('.discovery-entity').first()).toContainText(`${docxName} · 第 1 张表`);
 await expect(page.locator('.discovery-table summary').filter({hasText:`${docxName} · 第 1 张表`})).toHaveCount(1);
});

test('概念多时草案按概念折叠分组并支持待决筛选（FDE2-08）',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(180000);
 // 真实后端生成多概念草案：8 张表的 SQLite 只建模 7 张，并保留一条未采用的
 // 声明关系（order_line → product），让这两个概念带待决项，其余概念没有。
 // 不再改写 /view 路由：分组、目录与筛选都针对后端返回的真实草案。
 const database=path.join(workspace!,`grouping-discovery-${uniqueTag()}.db`);
 execFileSync('sqlite3',[database],{input:`
CREATE TABLE category (id TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE product (id TEXT PRIMARY KEY, category_id TEXT NOT NULL, label TEXT NOT NULL,
  FOREIGN KEY (category_id) REFERENCES category(id));
CREATE TABLE customer (id TEXT PRIMARY KEY, full_name TEXT NOT NULL);
CREATE TABLE sales_order (id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
  FOREIGN KEY (customer_id) REFERENCES customer(id));
CREATE TABLE order_line (id TEXT PRIMARY KEY, order_id TEXT NOT NULL, product_id TEXT NOT NULL,
  qty INTEGER NOT NULL,
  FOREIGN KEY (order_id) REFERENCES sales_order(id),
  FOREIGN KEY (product_id) REFERENCES product(id));
CREATE TABLE supplier (id TEXT PRIMARY KEY, vendor TEXT NOT NULL);
CREATE TABLE shipment (id TEXT PRIMARY KEY, supplier_id TEXT NOT NULL,
  FOREIGN KEY (supplier_id) REFERENCES supplier(id));
CREATE TABLE warehouse (id TEXT PRIMARY KEY, site TEXT NOT NULL);
INSERT INTO category VALUES ('CAT-1','食品'),('CAT-2','用品');
INSERT INTO product VALUES ('PRD-1','CAT-1','饼干'),('PRD-2','CAT-2','纸巾');
INSERT INTO customer VALUES ('CUS-1','甲方'),('CUS-2','乙方');
INSERT INTO sales_order VALUES ('SO-1','CUS-1'),('SO-2','CUS-2');
INSERT INTO order_line VALUES ('OL-1','SO-1','PRD-1',2),('OL-2','SO-2','PRD-2',3);
INSERT INTO supplier VALUES ('SUP-1','供应商甲'),('SUP-2','供应商乙');
INSERT INTO shipment VALUES ('SHP-1','SUP-1'),('SHP-2','SUP-2');
INSERT INTO warehouse VALUES ('WH-1','一号仓'),('WH-2','二号仓');
`});
 await page.goto('/');
 await page.getByLabel('接入目标').fill('多概念分组核对');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从材料发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitEvidenceProbed(page,20000);
 const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session');
 const request=callTool('intake_inference',{session_id:sid}) as Discovery & {
  expected_revision:string;source_revision:string;
 };
 const selected=request.catalog!.relationships.filter(link=>
  !(link.source_table==='order_line'&&link.target_table==='product'));
 expect(selected.length).toBe(request.catalog!.relationships.length-1);
 callTool('ontology_discovery_propose',{
  session_id:sid,expected_revision:request.expected_revision,
  proposal:{source_revision:request.source_revision,entities:[
   {name:'category',table:'category',grain:'每个商品分类一行',identity:['id'],
    properties:[{name:'label',column:'label'}]},
   {name:'product',table:'product',grain:'商品主数据',identity:['id'],
    properties:[{name:'label',column:'label'}]},
   {name:'customer',table:'customer',grain:'每个客户一行',identity:['id'],
    properties:[{name:'full_name',column:'full_name'}]},
   {name:'sales_order',table:'sales_order',grain:'每张销售订单一行',identity:['id']},
   {name:'order_line',table:'order_line',grain:'订单里的一条明细',identity:['id'],
    properties:[{name:'qty',column:'qty'}]},
   {name:'supplier',table:'supplier',grain:'每个供应商一行',identity:['id'],
    properties:[{name:'vendor',column:'vendor'}]},
   {name:'shipment',table:'shipment',grain:'每次发货一行',identity:['id']},
  ],relationships:selected.map(link=>({name:`关系_${link.source_table}_${link.target_table}`,
   evidence_id:link.id}))}},
 );
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 // 7 个概念超过阈值，按概念折叠分组：概要可见，正文默认收起。
 const groups=page.getByTestId('concept-groups');
 await expect(groups).toBeVisible({timeout:20000});
 const product=page.getByTestId('concept-group-product');
 const summary=product.locator('summary');
 await expect(summary).toContainText('身份 id');
 await expect(summary).toContainText('1 个属性');
 await expect(summary).toContainText('证据来源 product');
 await expect(summary).toContainText('待决 1 项');
 await expect(page.getByText('商品主数据')).toBeHidden();
 // 顶部概念目录列出全部 7 个概念，并标出待决数。
 for(const name of ['category','product','customer','sales_order','order_line','supplier','shipment'])
  await expect(groups.locator('.concept-toc')).toContainText(name);
 await expect(groups.locator('.concept-toc')).toContainText('product（待决 1）');
 // 目录是导航：点没有待决的 category 也会展开该组。
 await groups.locator('.concept-toc').getByRole('link',{name:'category'}).click();
 await expect(page.getByText('每个商品分类一行')).toBeVisible();
 // 逐个展开后才显示正文。
 await summary.click();
 await expect(page.getByText('商品主数据')).toBeVisible();
 // 只看有待决项：只留下 order_line 与 product，没有待决的概念不显示。
 await page.getByLabel('只看有待决项').check();
 await expect(product).toBeVisible();
 await expect(page.getByTestId('concept-group-order_line')).toBeVisible();
 await expect(page.getByTestId('concept-group-category')).toHaveCount(0);
 await expect(page.getByTestId('concept-group-customer')).toHaveCount(0);
 await expect(groups.locator('.concept-toc')).not.toContainText('customer');
});
