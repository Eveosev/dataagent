import {expect,test} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const workspace=process.env.DATAAGENT_TEST_WORKSPACE;
const python=process.env.DATAAGENT_TEST_PYTHON;
const SEED=path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql');

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
function fullCompletion(sid:string,draftRef:string,expectedRevision:string,
 catalog:{relationships:{id:string;origin:string}[]}|null){
 const declared=catalog!.relationships.find(link=>link.origin==='declared')!;
 const inferred=catalog!.relationships.find(link=>link.origin==='sample_supported')!;
 return {
  session_id:sid,expected_revision:expectedRevision,draft_ref:draftRef,
  ontology_id:'sales-model',title:'销售单据模型',
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
    name:{column:'nm',value_type:'string'},
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

test('SQLite 发现 → 草案 → 补全 → 网页确认发布 → 新接入映射 → 停用',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(300000);
 const database=path.join(workspace!,'publish-discovery.db');
 fs.rmSync(database,{force:true});
 execFileSync('sqlite3',[database],{input:fs.readFileSync(SEED)});
 const orders=path.join(workspace!,'publish-orders.csv');
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
 await expect(page.getByText('发布后将成为新任务的默认目标本体')).toBeVisible();
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
 await expect(page.getByTestId('publish-stale')).toContainText('ontology_publish_prepare');
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 await expect(page.getByLabel('我已核对候选定义与来源摘要，确认发布')).toBeDisabled();
 await page.unroute(viewRoute);
 // 页面只接受不减的任务修订（MappingPage 的防回退守卫），改写过的修订已被缓存，
 // 恢复真实视图需刷新页面重新载入。
 await page.reload();
 await expect(page.getByText('候选定义摘要 · 销售单据模型')).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-stale')).toHaveCount(0);

 // 反例：来源在观察后变化，确认被后端拒绝；已审核任务不能重探，只能新建发现任务。
 // 文件不恢复，后续发布由新任务在变更后的来源上完成。
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 const uploadsDir=path.join(workspace!,'.dataagent','uploads');
 const uploaded=fs.readdirSync(uploadsDir).filter(name=>/\.(db|sqlite3?)$/.test(name))
  .map(name=>path.join(uploadsDir,name))
  .sort((a,b)=>fs.statSync(b).mtimeMs-fs.statSync(a).mtimeMs)[0];
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
 await expect(page.getByText('目标本体 · 销售单据模型 · SalesOrder')).toBeVisible();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'核对来源与 Ontology 映射'})).toBeVisible({timeout:20000});

 // 目标在任务创建时已固定；立即停用，缩短默认指针偏离内置的窗口，既有任务不受影响。
 await page.getByRole('button',{name:'本体库'}).click();
 await page.getByRole('button',{name:'停用'}).click();
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

 // 停用后新建接入：选项不再出现，默认回到内置。
 await page.getByRole('button',{name:'新建接入'}).click();
 await expect(page.getByLabel('接入目标')).toBeVisible();
 await expect(page.getByRole('option',{name:/销售单据模型/})).toHaveCount(0);
 await expect(page.locator('#target-ontology')).toHaveValue('procurement',{timeout:20000});
});
