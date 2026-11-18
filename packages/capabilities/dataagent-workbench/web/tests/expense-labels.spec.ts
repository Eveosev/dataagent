import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {lockDefaultPointer,pinBuiltinOntology,slowTimeout,uniqueTag,unlockDefaultPointer} from './support';

// FDE2-11 第 2 轮返工的验收：差旅（费用）本体走英文实体名（ExpenseReport /
// ExpenseLine）时，网页可见位置一律显示中文标签；并覆盖「同一页签先打开过
// 任务（标题缓存已预热）→ 发布新本体 → 再建新任务」时面包屑能拿到新标题。
let workspace=process.env.DATAAGENT_TEST_WORKSPACE||'';
const python=process.env.DATAAGENT_TEST_PYTHON;

// 差旅报销库：报销单 + 费用明细，一对多外键。
const EXPENSE_SEED=`
CREATE TABLE expense_report (
    report_no TEXT PRIMARY KEY,
    employee TEXT NOT NULL,
    dept TEXT NOT NULL,
    report_date TEXT NOT NULL
);
CREATE TABLE expense_line (
    report_no TEXT NOT NULL,
    seq INTEGER NOT NULL,
    expense_type TEXT NOT NULL,
    cents INTEGER NOT NULL,
    city TEXT NOT NULL,
    PRIMARY KEY (report_no, seq),
    FOREIGN KEY (report_no) REFERENCES expense_report
);
INSERT INTO expense_report VALUES ('ER-001','王岚','市场部','2026-10-30'),('ER-002','李澄','交付部','2026-11-02');
INSERT INTO expense_line VALUES ('ER-001',1,'机票',72300,'上海'),('ER-001',2,'市内交通',4500,'上海'),('ER-002',1,'住宿',98000,'深圳');
`;

// 与 publish.spec 相同的工作区定位：上传探针文件找 locator_ref，再在系统
// 临时目录里找到持有它的运行中工作区；测试自身仍走真实后端。
async function resolveWorkspace(page:Page){
 if(workspace)return;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':`expense-workspace-probe-${uniqueTag()}.csv`},
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

// 草案与补全走真实 MCP 工具，发布确认只走网页人工通道。
function callTool(name:string,args:Record<string,unknown>){
 const request={jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}};
 const line=execFileSync(python!,['-m','dataagent_workbench.interfaces.mcp_server'],{
  cwd:workspace,input:JSON.stringify(request)+'\n',encoding:'utf8',
 });
 const {result}=JSON.parse(line);
 if(result.isError)throw new Error(`tool ${name} failed: ${result.content[0].text}`);
 const summary=JSON.parse(result.content[0].text);
 return JSON.parse(fs.readFileSync(path.join(workspace!,summary.result_path),'utf8')).data;
}

function sessionId(page:{url():string}){
 return new URL(page.url()).hash.match(/session=([0-9a-f]+)/)![1];
}

function declaredOf(request:{catalog:{relationships:{id:string;origin:string}[]}|null}){
 const declared=request.catalog!.relationships.find(link=>link.origin==='declared');
 if(!declared)throw new Error('expense seed must expose a declared foreign key');
 return declared;
}

// 发布/停用本体移动注册表默认指针（共享状态）：与 publish.spec、browse.spec
// 的发布用例之间按工作区加文件锁串行；收尾一律停用本用例发布的本体（未发布
// 时忽略失败）再释放锁——留着在用会让 publish.spec 的「停用」按钮匹配到多个。
let pointerLocked=false;
test.beforeEach(()=>{pointerLocked=false;});
test.afterEach(async({request})=>{
 if(!pointerLocked)return;
 await request.post('/api/ontologies/expense-model/retire',
  {data:{reason:'用例收尾停用，恢复默认指针',confirmed:true}}).catch(()=>{});
 unlockDefaultPointer(workspace);
 pointerLocked=false;
});

test('差旅本体：英文实体名统一中文标签；发布后同页签面包屑拿到新标题',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(300000);
 await lockDefaultPointer(workspace);
 pointerLocked=true;
 const tag=uniqueTag();
 const database=path.join(workspace!,`expense-discovery-${tag}.db`);
 execFileSync('sqlite3',[database],{input:EXPENSE_SEED});
 const warmCsv=path.join(workspace!,`expense-warm-${tag}.csv`);
 fs.writeFileSync(warmCsv,'number,issuer,amount,currency\nBX-2026-0001,华东供应商,1200,人民币\n');
 const linesCsv=path.join(workspace!,`expense-lines-${tag}.csv`);
 fs.writeFileSync(linesCsv,'report_no,seq,expense_type,city,expense_date,cents\nER-001,1,机票,上海,2026-10-30,72300\n');

 // 1. 先开一个采购映射任务：页面拉取过本体标题缓存（此时还没有差旅本体），
 //    面包屑显示注册表里的内置习惯名。
 await page.goto('/');
 await page.getByLabel('接入目标').fill('预热标题缓存的采购接入');
 await page.getByLabel('选择材料').setInputFiles(warmCsv);
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'核对来源与本体映射'})).toBeVisible({timeout:20000});
 await expect(page.locator('.eyebrow').first()).toHaveText('采购资料 / 接入任务',{timeout:20000});

 // 2. 同页签（无整页刷新）发起差旅库的发现任务，Agent 用英文实体名提案。
 await page.getByRole('button',{name:'新建接入'}).click();
 await page.getByLabel('接入目标').fill('从差旅报销数据库发现本体并发布');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible({timeout:20000});
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 const sid=sessionId(page);
 const request=callTool('intake_inference',{session_id:sid});
 callTool('ontology_discovery_propose',{session_id:sid,expected_revision:request.expected_revision,
  proposal:{source_revision:request.source_revision,entities:[
   {name:'ExpenseReport',table:'expense_report',grain:'每份报销单一行',identity:['report_no']},
   {name:'ExpenseLine',table:'expense_line',grain:'报销单的一条费用明细',identity:['report_no','seq'],
    properties:[{name:'expenseType',column:'expense_type'},{name:'city',column:'city'}]},
  ],relationships:[{name:'belongsToReport',evidence_id:declaredOf(request).id}]}});
 // 草案：实体名显示中文标签，不出现英文原名。
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 await expect(page.getByRole('heading',{name:'费用报销单',exact:true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'费用明细',exact:true})).toBeVisible();
 await expect(page.getByText('ExpenseReport')).toHaveCount(0);
 await expect(page.getByText('ExpenseLine')).toHaveCount(0);

 // 3. 审核草案并补全发布候选：候选摘要同样只显示中文标签与中文实体类型。
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});
 const fresh=callTool('intake_inference',{session_id:sid});
 callTool('ontology_publish_prepare',{
  session_id:sid,expected_revision:fresh.expected_revision,draft_ref:fresh.draft!.ref,
  ontology_id:'expense-model',title:'差旅费用模型',
  concepts:[
   {entity:'ExpenseReport',properties:{
    report_no:{column:'report_no',value_type:'string',required:true},
   },identity_fields:['report_no']},
   {entity:'ExpenseLine',properties:{
    report_no:{column:'report_no',value_type:'string',required:true},
    seq:{column:'seq',value_type:'integer',required:true},
    expense_type:{column:'expense_type',value_type:'string',required:true},
    city:{column:'city',value_type:'string',required:true},
   },identity_fields:['report_no','seq']},
  ],
  relations:[{evidence_id:declaredOf(fresh).id,name:'belongsToReport',subject_concept:'ExpenseLine',
   object_concept:'ExpenseReport',roles:['line','report']}],
  dispositions:[],
 });
 await expect(page.getByText('候选定义摘要 · 差旅费用模型')).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-concept-ExpenseReport')).toContainText('费用报销单');
 await expect(page.getByTestId('publish-concept-ExpenseReport')).not.toContainText('ExpenseReport');
 await expect(page.getByTestId('publish-concept-ExpenseLine')).toContainText('费用明细');
 await expect(page.getByTestId('publish-concept-ExpenseLine')).not.toContainText('ExpenseLine');
 await expect(page.getByText('ExpenseLine')).toHaveCount(0);
 await expect(page.getByText('ExpenseReport')).toHaveCount(0);

 // 4. 人工确认发布；发布让注册表多出差旅本体。
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done')).toContainText('expense-model',{timeout:20000});

 // 5. 本体库：概念列与对象计数链接都显示中文概念名。
 await page.getByRole('button',{name:'查看本体库'}).click();
 await expect(page.getByRole('heading',{name:'本体',exact:true})).toBeVisible();
 const entry=page.getByTestId('ontology-expense-model');
 await expect(entry).toContainText('差旅费用模型');
 await expect(entry).toContainText('费用报销单');
 await expect(entry).toContainText('费用明细');
 await expect(entry).not.toContainText('ExpenseLine');
 await expect(page.getByTestId('concept-count-expense-model-ExpenseLine')).toContainText('费用明细');

 // 6. 同页签新建映射任务：目标概念选项与目标提示显示中文；面包屑拿到
 //    新本体的注册表标题（标题缓存在发布后已失效重取，而不是沿用第 1 步
 //    预热的旧结果退回概念名）。
 await page.getByRole('button',{name:'新建接入'}).click();
 await expect(page.locator('#target-ontology')).toHaveValue('expense-model',{timeout:20000});
 await expect(page.getByLabel('目标概念').locator('option[value="ExpenseLine"]')).toHaveText('费用明细');
 await page.getByLabel('目标概念').selectOption('ExpenseLine');
 await expect(page.getByText('目标本体 · 差旅费用模型 · 费用明细')).toBeVisible();
 await page.getByLabel('接入目标').fill('接入差旅报销明细到新本体');
 await page.getByLabel('选择材料').setInputFiles(linesCsv);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'核对来源与本体映射'})).toBeVisible({timeout:20000});
 await expect(page.locator('.eyebrow').first()).toHaveText('差旅费用模型 / 接入任务',{timeout:20000});
});
