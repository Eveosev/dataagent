import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {lockDefaultPointer,slowTimeout,uniqueTag,unlockDefaultPointer} from './support';

let workspace=process.env.DATAAGENT_TEST_WORKSPACE||'';
const python=process.env.DATAAGENT_TEST_PYTHON;
const SEED=path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql');

// verify_browser.py 只把服务 URL/token/解释器传给 Playwright，不传工作区路径。
// 上传一个探针文件取得 locator_ref，再到系统临时目录里找到同一文件，从而定位
// 当前服务的工作区；测试自身仍走真实后端。
async function resolveWorkspace(page:Page){
 if(workspace)return;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':`publish-workspace-probe-${uniqueTag()}.csv`},
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

// 与网页共享同一个工作区：草案与补全走真实 MCP 工具，发布确认、停用与目标
// 选择只走网页人工通道。
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

// MCP 进程从工作区 .mint/packages/dataagent 找已安装数据层；验收工作区没有
// 装包，把同一 checkout 的 dataagent-data 链接进去，探查仍走公开子进程入口。
function ensureDataLayer(){
 const packages=path.join(workspace!,'.mint','packages','dataagent');
 fs.mkdirSync(packages,{recursive:true});
 const link=path.join(packages,'data-layer@local');
 if(!fs.existsSync(link))
  fs.symlinkSync(path.resolve('../../dataagent-data'),link,'dir');
}

function fullProposal(request:{expected_revision:string;source_revision:string;
 catalog:{relationships:{id:string;origin:string}[]}|null}){
 const declared=request.catalog!.relationships.find(link=>link.origin==='declared')!;
 const inferred=request.catalog!.relationships.find(link=>link.origin==='sample_supported')!;
 return {expected_revision:request.expected_revision,
  proposal:{source_revision:request.source_revision,entities:[
   {name:'SalesOrder',table:'doc_hdr',grain:'每个账簿内的一份销售单',identity:['book','doc_no']},
   {name:'SalesOrderLine',table:'doc_line',grain:'销售单的一条明细',identity:['book','doc_no','seq'],
    properties:[{name:'amountInCents',column:'cents'}]},
   {name:'Customer',table:'party',grain:'每个客户一行',identity:['party_no'],
    properties:[{name:'name',column:'nm'}]},
  ],relationships:[{name:'belongsToOrder',evidence_id:declared.id},
   {name:'orderedBy',evidence_id:inferred.id}]}};
}

// 与 test_publish_gate.full_completion 相同的补全；关系证据按各任务自己的目录取。
// requireName 为 true 时 Customer.name 必填，用来生成定义摘要不同的候选变体。
function fullCompletion(sid:string,draftRef:string,expectedRevision:string,
 catalog:{relationships:{id:string;origin:string}[]}|null,requireName=false,
 ontologyId='sales-model',title='销售单据模型'){
 const declared=catalog!.relationships.find(link=>link.origin==='declared')!;
 const inferred=catalog!.relationships.find(link=>link.origin==='sample_supported')!;
 return {
  session_id:sid,expected_revision:expectedRevision,draft_ref:draftRef,
  ontology_id:ontologyId,title,
  concepts:[
   {entity:'SalesOrder',properties:{
    book:{column:'book',value_type:'string',required:true},
    doc_no:{column:'doc_no',value_type:'integer',required:true},
   },identity_fields:['book','doc_no']},
   {entity:'SalesOrderLine',properties:{
    book:{column:'book',value_type:'string',required:true},
    doc_no:{column:'doc_no',value_type:'integer',required:true},
    seq:{column:'seq',value_type:'integer',required:true},
    amountInCents:{column:'cents',value_type:'decimal',required:true},
   },identity_fields:['book','doc_no','seq']},
   {entity:'Customer',properties:{
    party_no:{column:'party_no',value_type:'string',required:true},
    name:{column:'nm',value_type:'string',required:requireName},
   },identity_fields:['party_no']},
  ],
  relations:[
   {evidence_id:declared.id,name:'belongsToOrder',subject_concept:'SalesOrderLine',
    object_concept:'SalesOrder',roles:['line','order']},
   {evidence_id:inferred.id,name:'orderedBy',subject_concept:'SalesOrder',
    object_concept:'Customer',roles:['order','customer']},
  ],
  dispositions:[],
 };
}

async function startDiscovery(page:import('@playwright/test').Page,goal:string,database:string){
 await page.getByRole('button',{name:'新建接入'}).click();
 await page.getByLabel('接入目标').fill(goal);
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 return sessionId(page);
}

// 发布/停用本体移动注册表默认指针（共享状态），本文件的用例还要断言默认指针
// 的取值：与 browse.spec 的发布用例之间按工作区加文件锁串行，锁的释放挂在
// afterEach 上（用例失败也释放）。
let pointerLocked=false;
test.beforeEach(()=>{pointerLocked=false;});
test.afterEach(async({request},testInfo)=>{
 if(!pointerLocked)return;
 // 失败清理：发布成功后、停用前失败会让本体带着默认指针残留，破坏本用例的
 // 重试与并行用例；先在锁内尽力停用，再释放锁（已停用或未发布的忽略结果）。
 if(testInfo.status!=='passed'){
  for(const id of ['sales-model','pending-model','review-candidate-model']){
   await request.post(`/api/ontologies/${id}/retire`,
    {data:{reason:'用例失败后的清理停用，恢复默认指针',confirmed:true}}).catch(()=>{});
  }
 }
 unlockDefaultPointer(workspace);
 pointerLocked=false;
});

test('SQLite 发现 → 草案 → 补全 → 网页确认发布 → 新接入映射 → 停用',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(300000);
 await lockDefaultPointer(workspace);
 pointerLocked=true;
 // 共享工作区里的文件名带用例级唯一后缀：不删除也不覆盖其他并行用例的文件。
 const tag=uniqueTag();
 const database=path.join(workspace!,`publish-discovery-${tag}.db`);
 execFileSync('sqlite3',[database],{input:fs.readFileSync(SEED)});
 const orders=path.join(workspace!,`publish-orders-${tag}.csv`);
 fs.writeFileSync(orders,'book,doc_no\nSALE,1001\nSALE,1002\n');

 await page.goto('/');
 await page.getByLabel('接入目标').fill('从销售数据库发现本体并发布');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible({timeout:20000});
 // 等探查完成（来源证据出现）再取证据，catalog 才有表与关系。
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 const sid=sessionId(page);
 const request=callTool('intake_inference',{session_id:sid});

 // 反例：草案只建模一张表，通过审核后未处置项点名，确认发布被阻断。
 callTool('ontology_discovery_propose',{session_id:sid,expected_revision:request.expected_revision,
  proposal:{source_revision:request.source_revision,entities:[
   {name:'Customer',table:'party',grain:'每个客户一行',identity:['party_no'],
    properties:[{name:'name',column:'nm'}]},
  ],relationships:[]}});
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-card')).toBeVisible();
 await expect(page.getByTestId('publish-open-items')).toContainText('doc_hdr');
 await expect(page.getByTestId('publish-blocked')).toContainText('doc_hdr');
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 // 补全指令只用业务话术，不出现内部工具名（FDE2-12）。
 await expect(page.getByText(/intake_inference|ontology_discovery_propose|ontology_publish_prepare/)).toHaveCount(0);

 // FDE2-07：Agent 补全时对未决项自行下了处置，发布区逐项列出「Agent 处置，
 // 待你核对」并给出影响说明；逐项勾选同意前确认发布保持禁用。
 // intake_inference 的 draft 只是引用摘要；未决项在网页 view 的完整草案里。
 const partial=callTool('intake_inference',{session_id:sid});
 const partialView=await page.request.get(`/api/sessions/${sid}/view`);
 expect(partialView.ok(),await partialView.text()).toBeTruthy();
 const partialDraft=(await partialView.json() as {discovery:{draft:{
  ref:string;unresolved_tables:string[];unresolved_relationships:{id:string}[];
  gaps?:{ref?:string}[];coverage?:string}}}).discovery.draft;
 const partialDispositions=[
  ...partialDraft.unresolved_tables.map((name:string)=>({kind:'unresolved_table',ref:name,action:'exclude',reason:'不在本次登记范围'})),
  ...partialDraft.unresolved_relationships.map((link:{id:string})=>({kind:'unresolved_relationship',ref:link.id,action:'exclude',reason:'与本次登记无关'})),
  ...(partialDraft.gaps||[]).map((gap:{ref?:string})=>({kind:'coverage_gap',ref:String(gap.ref||''),action:'accept',reason:'接受该缺口'})),
  ...(partialDraft.coverage&&partialDraft.coverage!=='full'?[{kind:'coverage',ref:partialDraft.coverage,action:'accept',reason:'接受覆盖水平'}]:[]),
 ];
 callTool('ontology_publish_prepare',{
  session_id:sid,expected_revision:partial.expected_revision,draft_ref:partialDraft.ref,
  ontology_id:'partial-model',title:'部分登记模型',
  concepts:[{entity:'Customer',properties:{
   party_no:{column:'party_no',value_type:'string',required:true},
   name:{column:'nm',value_type:'string',required:false},
  },identity_fields:['party_no']}],
  relations:[],
  dispositions:partialDispositions,
 });
 await expect(page.getByTestId('publish-blocked')).toHaveCount(0,{timeout:20000});
 await expect(page.getByText('Agent 处置，待你核对').first()).toBeVisible();
 await expect(page.getByText('影响：').first()).toBeVisible();
 const dispositionBoxes=page.locator('.publish-disposition input');
 await expect(dispositionBoxes).toHaveCount(partialDispositions.length);
 // 勾选总核对后，未逐项同意 Agent 处置前确认发布仍禁用。
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 for(let index=0;index<partialDispositions.length;index++)await dispositionBoxes.nth(index).check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
 // 漏勾一项时重新禁用：逐项同意必须全部满足，不是任意一项。
 await dispositionBoxes.first().uncheck();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 await dispositionBoxes.first().check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
 // 退回让 Agent 重做的入口给业务话术指令，不出现内部工具名。
 await page.getByTestId('publish-return').locator('summary').click();
 await expect(page.getByTestId('publish-return')).not.toContainText('ontology_publish_prepare');

 // 完整链路换新任务：通过审核的发现任务已关闭，不能再次提案。
 const publishSid=await startDiscovery(page,'从销售数据库发现完整本体并发布',database);
 const full=callTool('intake_inference',{session_id:publishSid});
 callTool('ontology_discovery_propose',{session_id:publishSid,...fullProposal(full)});
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});

 // 补全生成候选；审核后草案引用会前进，补全必须引用通过审核后的草案修订。
 let fresh=callTool('intake_inference',{session_id:publishSid});
 callTool('ontology_publish_prepare',fullCompletion(publishSid,fresh.draft!.ref,fresh.expected_revision,fresh.catalog));
 await expect(page.getByText('候选定义摘要 · 销售单据模型')).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-concept-SalesOrder')).toContainText('book + doc_no');
 await expect(page.getByText('来源快照摘要')).toBeVisible();
 // FDE2-11：来源修订等内部哈希收进折叠「技术详情」，正文不铺哈希；值类型用中文。
 await expect(page.getByTestId('publish-tech-detail').getByText('来源修订')).toBeHidden();
 // 收进折叠后可见的快照摘要只剩本体标识；「来源修订」在折叠的第二个 dl 里。
 await expect(page.locator('.publish-snapshot').first()).not.toContainText('来源修订');
 await expect(page.getByTestId('publish-concept-SalesOrder')).toContainText('文本');
 await expect(page.getByText('发布后将成为新任务的默认目标本体')).toBeVisible();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();

 // 反例：核对过候选 A 后，Agent 用不同定义重新准备候选 B；页面换上 B 时人工
 // 核对勾选被重置，不能用对旧定义的确认发布新定义。
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 callTool('ontology_publish_prepare',fullCompletion(publishSid,fresh.draft!.ref,fresh.expected_revision,fresh.catalog,true));
 await expect(page.getByLabel('我已核对候选定义与来源摘要，确认发布')).not.toBeChecked({timeout:20000});
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();

 // 反例：任务修订越过后候选过期，确认被禁用并提示重新准备，不反复提交失效候选。
 // 说明：已审核发现任务的会话修订被后端冻结（sessions.update 拒绝 saved 阶段、
 // advance 原样返回），真实操作无法让候选的 session_revision 落后；这里只改写
 // view 响应里的修订号来验证网页门控，其余链路全部走真实后端。
 const viewRoute=`**/api/sessions/${publishSid}/view`;
 await page.route(viewRoute,async route=>{
  const response=await route.fetch();
  const body=await response.json();
  if(body.session)
   body.session={...body.session,revision:String(Number(body.session.revision)+1)};
  await route.fulfill({response,json:body});
 });
 await expect(page.getByTestId('publish-stale')).toContainText('候选已过期',{timeout:20000});
 await expect(page.getByTestId('publish-stale')).toContainText('重新生成发布候选');
 await expect(page.getByTestId('publish-stale')).not.toContainText('ontology_publish_prepare');
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 await expect(page.getByLabel('我已核对候选定义与来源摘要，确认发布')).toBeDisabled();
 await page.unroute(viewRoute);
 // 页面只接受不减的任务修订（MappingPage 的防回退守卫），改写过的修订已被缓存，
 // 恢复真实视图需刷新页面重新载入。
 await page.reload();
 await expect(page.getByText('候选定义摘要 · 销售单据模型')).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-stale')).toHaveCount(0);

 // 反例：页面尚未换上新候选时提交旧候选（Agent 已重新准备、页面更新前的窗口，
 // 这里按住候选接口复现），后端 409 拒绝；换到一致的新候选后发布流程恢复。
 const candidateRoute=`**/api/sessions/${publishSid}/publish/candidate`;
 const heldResponse=await page.request.get(`/api/sessions/${publishSid}/publish/candidate`);
 const held=await heldResponse.json();
 let holdCandidate=false;
 await page.route(candidateRoute,async route=>{
  await route.fulfill(holdCandidate?{json:held}:{response:await route.fetch()});
 });
 holdCandidate=true;
 callTool('ontology_publish_prepare',fullCompletion(publishSid,fresh.draft!.ref,fresh.expected_revision,fresh.catalog,true));
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-failure')).toContainText('候选已过期',{timeout:20000});
 await expect(page.getByTestId('publish-stale')).toContainText('候选已过期');
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 // 刷新取得与当前任务修订一致的新候选：过期标记清除、勾选重置，重新核对后可发布。
 holdCandidate=false;
 await page.getByRole('button',{name:'刷新候选'}).click();
 await expect(page.getByTestId('publish-stale')).toHaveCount(0,{timeout:20000});
 await expect(page.getByTestId('publish-failure')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
 await page.unroute(candidateRoute);

 // 反例：来源在观察后变化，确认被后端拒绝；已审核任务不能重探，只能新建发现任务。
 // 文件不恢复，后续发布由新任务在变更后的来源上完成。
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 // 直接取当前任务固定的来源文件：并行用例也会上传 SQLite，按 mtime 选会
 // 选到别人的文件，导致改错快照、发布反而成功。
 const sourceView=await page.request.get(`/api/sessions/${publishSid}/view`);
 expect(sourceView.ok(),await sourceView.text()).toBeTruthy();
 const sourceRef=(await sourceView.json() as {session:{sources:{locator_ref:string}[]}})
  .session.sources.find(source=>/\.(db|sqlite3?)$/.test(source.locator_ref))?.locator_ref;
 expect(sourceRef).toBeTruthy();
 const uploaded=path.resolve(workspace!,sourceRef!);
 execFileSync('sqlite3',[uploaded],{input:"INSERT INTO party VALUES ('P-9','Extra');\n"});
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-failure')).toContainText('来源');
 await expect(page.getByTestId('publish-failure')).toContainText('新建发现任务');
 await page.getByRole('button',{name:'用相同来源新建发现任务'}).click();
 // 旧任务页本身就有「本体发现」标题，等路由真正切到新任务再取会话号。
 await expect(page).not.toHaveURL(new RegExp(publishSid),{timeout:20000});
 const rediscoverySid=sessionId(page);
 expect(rediscoverySid).not.toBe(publishSid);
 // 新任务重新观察变更后的来源：party 表从 2 行变为 3 行。
 await expect(page.locator('.discovery-table summary',{hasText:'party'})).toContainText('3 行',{timeout:20000});

 // 变更后的来源上重新发现、补全并人工确认发布。
 const rediscovery=callTool('intake_inference',{session_id:rediscoverySid});
 callTool('ontology_discovery_propose',{session_id:rediscoverySid,...fullProposal(rediscovery)});
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});
 fresh=callTool('intake_inference',{session_id:rediscoverySid});
 callTool('ontology_publish_prepare',fullCompletion(rediscoverySid,fresh.draft!.ref,fresh.expected_revision,fresh.catalog));
 await expect(page.getByText('候选定义摘要 · 销售单据模型')).toBeVisible({timeout:20000});
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done')).toContainText('sales-model',{timeout:20000});

 // 本体库出现，新任务默认指向它。
 await page.getByRole('button',{name:'查看本体库'}).click();
 await expect(page.getByRole('heading',{name:'本体',exact:true})).toBeVisible();
 await expect(page.getByTestId('ontology-sales-model')).toContainText('销售单据模型');
 await expect(page.getByTestId('ontology-sales-model')).toContainText('发现发布');
 await expect(page.getByTestId('ontology-sales-model')).toContainText('新任务默认');
 await expect(page.getByTestId('ontology-procurement')).toBeVisible();
 // 内置本体不提供停用。
 await expect(page.getByTestId('ontology-procurement').getByRole('button',{name:'停用'})).toHaveCount(0);

 // 新建接入：目标本体默认为刚发布的本体，多概念需再选概念。
 await page.getByRole('button',{name:'新建接入'}).click();
 await page.getByLabel('接入目标').fill('接入销售订单到新本体');
 await page.getByLabel('选择材料').setInputFiles(orders);
 await expect(page.locator('#target-ontology')).toHaveValue('sales-model',{timeout:20000});
 await expect(page.getByLabel('目标概念')).toBeVisible();
 await page.getByLabel('目标概念').selectOption('SalesOrder');
 // 目标概念的中文名（FDE2-11）：选项与目标提示都显示「销售单」而非 SalesOrder。
 await expect(page.getByText('目标本体 · 销售单据模型 · 销售单')).toBeVisible();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'核对来源与本体映射'})).toBeVisible({timeout:20000});

 // 目标在任务创建时已固定；立即停用，缩短默认指针偏离内置的窗口，既有任务不受影响。
 // 停用按钮限定在 sales-model 自己的行：并行的修订用例可能短暂留有未停用的本体。
 await page.getByRole('button',{name:'本体库'}).click();
 await page.getByTestId('ontology-sales-model').getByRole('button',{name:'停用'}).click();
 await expect(page.getByRole('button',{name:'确认停用'})).toBeDisabled();
 await page.getByLabel('停用原因（必填，写入审计）').fill('并入新的销售模型修订');
 await page.getByLabel('我确认停用该本体，新任务将不再默认选用').check();
 await page.getByRole('button',{name:'确认停用'}).click();
 await expect(page.getByTestId('ontology-sales-model')).toContainText('已停用',{timeout:20000});
 await expect(page.getByTestId('ontology-sales-model')).toContainText('并入新的销售模型修订');

 // 回到已固定的映射任务：映射预览使用新本体的概念字段（多概念本体不再显示空属性）。
 await page.getByRole('button',{name:'返回任务'}).click();
 await expect(page.getByRole('button',{name:'book',exact:true})).toBeVisible({timeout:20000});
 await expect(page.getByRole('button',{name:'doc_no',exact:true})).toBeVisible();
 // 等探查完成（阶段提示）再编辑，避免草稿保存与探查更新撞修订。
 await expect(page.getByText('识别与探查已完成')).toBeVisible({timeout:20000});
 await page.getByLabel('doc_no 转换方式').selectOption('integer');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-doc_no')).toHaveText('1001',{timeout:20000});

 // 停用后新建接入：选项不再出现，也不再是默认。并行的修订用例不参与本用例的
 // 指针锁，可能短暂把默认指针移到它自己发布的本体上，「回到内置」只在无其他
 // 存活本体时成立，这里只断言已停用的 sales-model 不再被默认选中。
 await page.getByRole('button',{name:'新建接入'}).click();
 await expect(page.getByLabel('接入目标')).toBeVisible();
 await expect(page.getByRole('option',{name:/销售单据模型/})).toHaveCount(0);
 await expect(page.locator('#target-ontology')).not.toHaveValue('sales-model',{timeout:20000});
});

test('Agent 补全时放弃草案关系 → 发布区逐项列出并需勾选同意',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(180000);
 const tag=uniqueTag();
 const database=path.join(workspace!,`publish-dropped-${tag}.db`);
 const ontologyId=`publish-dropped-${tag}`;
 execFileSync('sqlite3',[database],{input:fs.readFileSync(SEED)});

 await page.goto('/');
 await page.getByLabel('接入目标').fill('补全时放弃草案关系核对');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 const sid=sessionId(page);
 const request=callTool('intake_inference',{session_id:sid});
 callTool('ontology_discovery_propose',{session_id:sid,...fullProposal(request)});
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});

 // 补全时只带入一条草案关系；另一条已选关系被放弃。后端候选与草案的差异
 // 必须出现在发布确认区，而不是只留在候选的 dispositions 里。
 const fresh=callTool('intake_inference',{session_id:sid});
 const completion=fullCompletion(sid,fresh.draft!.ref,fresh.expected_revision,fresh.catalog,
  false,ontologyId,'补全放弃关系模型');
 const droppedRelation=completion.relations.find(item=>item.name==='orderedBy')!;
 completion.relations=completion.relations.filter(item=>item!==droppedRelation);
 callTool('ontology_publish_prepare',{...completion,
  dispositions:[{kind:'unresolved_relationship',ref:droppedRelation.evidence_id,
   action:'exclude',reason:'补全时未带入该关系'}]});
 await expect(page.getByText('候选定义摘要 · 补全放弃关系模型')).toBeVisible({timeout:20000});

 const dropped=page.getByTestId('publish-dropped-item');
 await expect(dropped).toHaveCount(1);
 await expect(dropped).toContainText('补全时放弃的草案关系');
 await expect(dropped).toContainText('orderedBy');
 await expect(dropped).toContainText('doc_hdr');
 await expect(dropped).toContainText('party');
 await expect(dropped).toContainText('补全候选未带入该草案项。');
 await expect(dropped).toContainText('影响：');
 await expect(page.getByTestId('publish-blocked')).toHaveCount(0);
 const candidate=await page.request.get(`/api/sessions/${sid}/publish/candidate`);
 const body=await candidate.json() as {dropped:{kind:string;ref:string}[]};
 expect(body.dropped.some(item=>item.kind==='relationship'
  &&item.ref===droppedRelation.evidence_id)).toBeTruthy();

 // 总核对勾选后仍禁用；逐项勾选这条被放弃的关系后才可确认发布。
 const checkbox=dropped.locator('input[type=checkbox]');
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 await checkbox.check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
 await checkbox.uncheck();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
});

test('修订候选放弃多项属性 → 每项分别勾选，迁移确认不能代勾',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(300000);
 const tag=uniqueTag();
 const ontologyId=`revision-dropped-${tag}`;
 const database=`revision-dropped-${tag}.db`;
 execFileSync('sqlite3',[path.join(workspace!,database)],{input:fs.readFileSync(SEED)});
 ensureDataLayer();
 await lockDefaultPointer(workspace!);
 pointerLocked=true;
 let published=false;
 try{
  // 先发布一个完整本体（两个属性都在），再用修订任务把两项属性一起删掉。
  const initial=callTool('intake_start',{goal:'发布多删除修订的初始本体',
   mode:'ontology_discovery',
   sources:[{source_id:'db',kind:'sqlite',locator_ref:database}]});
  const initialRequest=callTool('intake_advance',{session_id:initial.session_id});
  callTool('ontology_discovery_propose',{session_id:initial.session_id,
   ...fullProposal(initialRequest)});
  const first=callTool('intake_inference',{session_id:initial.session_id});
  const firstCandidate=callTool('ontology_publish_prepare',
   fullCompletion(initial.session_id,first.draft.ref,first.expected_revision,first.catalog,
    false,ontologyId,'多删除修订模型'));
  const confirmed=await page.request.post(
   `/api/sessions/${initial.session_id}/publish/confirm`,{data:{
    candidate_ref:firstCandidate.candidate_ref,draft_ref:firstCandidate.draft_ref,
    source_snapshot:firstCandidate.source_snapshot,
    definition_digest:firstCandidate.definition_digest,
    expected_revision:firstCandidate.session_revision,confirmed:true,
    reason:'e2e 多删除修订的初始本体',
   }});
  expect(confirmed.ok(),await confirmed.text()).toBeTruthy();
  published=true;

  const revision=callTool('intake_start',{goal:'修订里同时删除两个属性',
   mode:'ontology_discovery',
   sources:[{source_id:'db',kind:'sqlite',locator_ref:database}],
   revise_ontology_id:ontologyId});
  const revisionRequest=callTool('intake_advance',{session_id:revision.session_id});
  callTool('ontology_discovery_propose',{session_id:revision.session_id,
   ...fullProposal(revisionRequest)});
  const inferred=callTool('intake_inference',{session_id:revision.session_id});
  const completion=fullCompletion(revision.session_id,inferred.draft.ref,
   inferred.expected_revision,inferred.catalog,false,ontologyId,'多删除修订模型');
  const line=completion.concepts.find(item=>item.entity==='SalesOrderLine')!;
  const customer=completion.concepts.find(item=>item.entity==='Customer')!;
  delete (line.properties as Record<string,unknown>).amountInCents;
  delete (customer.properties as Record<string,unknown>).name;
  const candidate=callTool('ontology_publish_prepare',completion);
  expect(candidate.dropped).toHaveLength(2);
  expect(candidate.revision_diff.removed_properties).toHaveLength(2);

  await page.goto('/#session='+revision.session_id);
  await expect(page.getByTestId('revision-publish-notice')).toBeVisible({timeout:30000});
  const dropped=page.getByTestId('publish-dropped-item');
  await expect(dropped).toHaveCount(2);
  const amount=dropped.filter({hasText:'SalesOrderLine.amountInCents'});
  const name=dropped.filter({hasText:'Customer.name'});
  await expect(amount).toHaveCount(1);
  await expect(name).toHaveCount(1);

  // 迁移确认勾选后，两个被放弃属性仍各自未同意，确认发布保持禁用。
  await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
  await page.getByTestId('revision-no-migration').check();
  await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
  await amount.locator('input[type=checkbox]').check();
  await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
  await name.locator('input[type=checkbox]').check();
  await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
  await amount.locator('input[type=checkbox]').uncheck();
  await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 } finally {
  if(published)
   await page.request.post(`/api/ontologies/${ontologyId}/retire`,{
    data:{reason:'e2e 多删除修订用例结束停用',confirmed:true}}).catch(()=>{});
 }
});

test('修订候选只放弃一个属性 → 迁移确认不能代勾，仍须单独勾选',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(300000);
 const tag=uniqueTag();
 const ontologyId=`revision-dropped-single-${tag}`;
 const database=`revision-dropped-single-${tag}.db`;
 execFileSync('sqlite3',[path.join(workspace!,database)],{input:fs.readFileSync(SEED)});
 ensureDataLayer();
 await lockDefaultPointer(workspace!);
 pointerLocked=true;
 let published=false;
 try{
  // 先发布完整本体，再修订只删除一个属性：唯一被放弃项也不与「旧数据不迁移」同步。
  const initial=callTool('intake_start',{goal:'发布单删除修订的初始本体',
   mode:'ontology_discovery',
   sources:[{source_id:'db',kind:'sqlite',locator_ref:database}]});
  const initialRequest=callTool('intake_advance',{session_id:initial.session_id});
  callTool('ontology_discovery_propose',{session_id:initial.session_id,
   ...fullProposal(initialRequest)});
  const first=callTool('intake_inference',{session_id:initial.session_id});
  const firstCandidate=callTool('ontology_publish_prepare',
   fullCompletion(initial.session_id,first.draft.ref,first.expected_revision,first.catalog,
    false,ontologyId,'单删除修订模型'));
  const confirmed=await page.request.post(
   `/api/sessions/${initial.session_id}/publish/confirm`,{data:{
    candidate_ref:firstCandidate.candidate_ref,draft_ref:firstCandidate.draft_ref,
    source_snapshot:firstCandidate.source_snapshot,
    definition_digest:firstCandidate.definition_digest,
    expected_revision:firstCandidate.session_revision,confirmed:true,
    reason:'e2e 单删除修订的初始本体',
   }});
  expect(confirmed.ok(),await confirmed.text()).toBeTruthy();
  published=true;

  const revision=callTool('intake_start',{goal:'修订里删除一个属性',
   mode:'ontology_discovery',
   sources:[{source_id:'db',kind:'sqlite',locator_ref:database}],
   revise_ontology_id:ontologyId});
  const revisionRequest=callTool('intake_advance',{session_id:revision.session_id});
  callTool('ontology_discovery_propose',{session_id:revision.session_id,
   ...fullProposal(revisionRequest)});
  const inferred=callTool('intake_inference',{session_id:revision.session_id});
  const completion=fullCompletion(revision.session_id,inferred.draft.ref,
   inferred.expected_revision,inferred.catalog,false,ontologyId,'单删除修订模型');
  const line=completion.concepts.find(item=>item.entity==='SalesOrderLine')!;
  delete (line.properties as Record<string,unknown>).amountInCents;
  const candidate=callTool('ontology_publish_prepare',completion);
  expect(candidate.dropped).toHaveLength(1);
  expect(candidate.revision_diff.removed_properties).toHaveLength(1);

  await page.goto('/#session='+revision.session_id);
  await expect(page.getByTestId('revision-publish-notice')).toBeVisible({timeout:30000});
  const dropped=page.getByTestId('publish-dropped-item');
  await expect(dropped).toHaveCount(1);
  const amount=dropped.filter({hasText:'SalesOrderLine.amountInCents'});
  await expect(amount).toHaveCount(1);

  // 候选只有一个被放弃项：总确认与迁移确认都勾上也不放行，必须单独勾选该项。
  await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
  await page.getByTestId('revision-no-migration').check();
  await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
  await amount.locator('input[type=checkbox]').check();
  await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
  await amount.locator('input[type=checkbox]').uncheck();
  await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 } finally {
  if(published)
   await page.request.post(`/api/ontologies/${ontologyId}/retire`,{
    data:{reason:'e2e 单删除修订用例结束停用',confirmed:true}}).catch(()=>{});
 }
});

test('pending 草案 + 候选 → 网页一次确认发布 → 草案 approved',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(300000);
 await lockDefaultPointer(workspace);
 pointerLocked=true;
 const database=path.join(workspace!,`publish-pending-${uniqueTag()}.db`);
 execFileSync('sqlite3',[database],{input:fs.readFileSync(SEED)});

 await page.goto('/');
 await page.getByLabel('接入目标').fill('pending 草案一次确认发布');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible({timeout:20000});
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 const sid=sessionId(page);

 const request=callTool('intake_inference',{session_id:sid});
 callTool('ontology_discovery_propose',{session_id:sid,...fullProposal(request)});
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 await expect(page.getByText('待审核').first()).toBeVisible();
 // 不点「确认当前草案」：草案保持 pending，补全候选后应在发布区直接出现。
 await expect(page.getByRole('button',{name:'确认当前草案'})).toBeVisible();

 const fresh=callTool('intake_inference',{session_id:sid});
 callTool('ontology_publish_prepare',fullCompletion(sid,fresh.draft!.ref,
  fresh.expected_revision,fresh.catalog,false,'pending-model','待审核一次确认模型'));
 await expect(page.getByTestId('publish-card')).toBeVisible({timeout:20000});
 await expect(page.getByText('候选定义摘要 · 待审核一次确认模型')).toBeVisible({timeout:20000});
 // FDE2-12：发布区存在时「确认当前草案」收进「只审核草案，不发布」，不与
 // 「确认发布」并列造成要点两次的误解；发布区写明确认即一并审核。
 await expect(page.getByRole('button',{name:'确认当前草案'})).not.toBeVisible();
 await expect(page.getByTestId('publish-pending-note')).toContainText('一并审核');
 await expect(page.getByTestId('draft-only-review')).toBeVisible();
 await expect(page.getByTestId('draft-only-review')).not.toHaveAttribute('open');
 await page.getByTestId('draft-only-review').locator('summary').click();
 await expect(page.getByRole('button',{name:'确认当前草案'})).toBeVisible();
 // 展开后不用它：一次确认即审核并发布。
 await page.getByTestId('draft-only-review').locator('summary').click();
 await expect(page.getByRole('button',{name:'确认当前草案'})).not.toBeVisible();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done')).toContainText('pending-model',{timeout:20000});
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});

 const view=await page.request.get(`/api/sessions/${sid}/view`);
 expect((await view.json()).discovery.draft.state).toBe('approved');
 // 不把测试发布的本体留成默认目标，避免影响并行用例与本用例的重试。
 const retired=await page.request.post('/api/ontologies/pending-model/retire',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||''},
  data:{reason:'用例结束停用',confirmed:true}});
 expect(retired.ok(),await retired.text()).toBeTruthy();
});

test('prepare → 网页审核草案 → 发布区仍显示候选 → 确认发布成功',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(300000);
 await lockDefaultPointer(workspace);
 pointerLocked=true;
 const database=path.join(workspace!,`publish-review-candidate-${uniqueTag()}.db`);
 execFileSync('sqlite3',[database],{input:fs.readFileSync(SEED)});

 await page.goto('/');
 await page.getByLabel('接入目标').fill('审核草案后继续确认发布');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 const sid=sessionId(page);
 const request=callTool('intake_inference',{session_id:sid});
 callTool('ontology_discovery_propose',{session_id:sid,...fullProposal(request)});
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 await expect(page.getByText('待审核').first()).toBeVisible();

 const fresh=callTool('intake_inference',{session_id:sid});
 callTool('ontology_publish_prepare',fullCompletion(sid,fresh.draft!.ref,
  fresh.expected_revision,fresh.catalog,false,'review-candidate-model','审核草案后继续发布模型'));
 await expect(page.getByTestId('publish-card')).toBeVisible({timeout:20000});
 await expect(page.getByText('候选定义摘要 · 审核草案后继续发布模型')).toBeVisible({timeout:20000});

 // 发布区存在时先单独审核草案。旧实现 review() 只 reload，候选 effect 的
 // 依赖不包含 draft.ref/session.revision，审核后发布区退回「待补全」。
 await page.getByTestId('draft-only-review').locator('summary').click();
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-card')).toBeVisible();
 await expect(page.getByText('候选定义摘要 · 审核草案后继续发布模型')).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-card')).not.toContainText('让 Agent 补全');

 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done')).toContainText('review-candidate-model',{timeout:20000});
 const view=await page.request.get(`/api/sessions/${sid}/view`);
 expect((await view.json()).discovery.draft.state).toBe('approved');
 // 不把测试发布的本体留成默认目标，避免影响并行用例。
 const retired=await page.request.post('/api/ontologies/review-candidate-model/retire',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||''},
  data:{reason:'用例结束停用',confirmed:true}});
 expect(retired.ok(),await retired.text()).toBeTruthy();
});
