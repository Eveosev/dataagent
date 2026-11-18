import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// 三个用例都会发布/停用本体并移动默认指针，串行执行避免并行用例互相争用
// 默认本体；它们仍与其它测试文件并行。
test.describe.configure({mode:'serial'});

// V6：已发布本体发布新修订。初始本体走 MCP + HTTP 人工确认；修订任务以
// revise_ontology_id 发起，补全把已发布属性的值类型改掉（非破坏性），
// 然后走真实网页的发布按钮确认，最后到本体库核对修订历史与差异摘要。
// 破坏性修订的额外勾选由后端单元测试覆盖。
let workspace=process.env.DATAAGENT_TEST_WORKSPACE||'';
const python=process.env.DATAAGENT_TEST_PYTHON;
const SEED=path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql');

// verify_browser.py 只传 URL/token/解释器，不传工作区路径；上传一个探测文件后
// 到系统临时目录里找到同一个 locator_ref，确定性定位当前服务的工作区。
async function resolveWorkspace(page:Page){
 if(workspace)return workspace;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':'revision-probe.csv'},
  data:'book,doc_no\nPROBE,1\n',
 });
 expect(response.ok(),await response.text()).toBeTruthy();
 const {locator_ref}=await response.json() as {locator_ref?:string};
 const root=os.tmpdir();
 const dirs=fs.readdirSync(root).filter(name=>name.startsWith('dataagent-ui-'))
  .map(name=>path.join(root,name))
  .filter(dir=>fs.existsSync(path.join(dir,'.dataagent','db','workbench.sqlite3')));
 const found=dirs.find(dir=>{
  const file=path.resolve(dir,String(locator_ref||''));
  return file.startsWith(path.resolve(dir)+path.sep)&&fs.existsSync(file);
 });
 if(!found||!locator_ref)throw new Error(`cannot find the running workspace for ${locator_ref}`);
 fs.rmSync(path.resolve(found,locator_ref),{force:true});
 return found;
}

function callTool(name:string,args:Record<string,unknown>){
 const request={jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}};
 const line=execFileSync(python!,['-m','dataagent_workbench.interfaces.mcp_server'],{
  cwd:workspace,input:JSON.stringify(request)+'\n',encoding:'utf8',
  env:{...process.env,DATAAGENT_WORKSPACE:workspace},
 });
 const {result}=JSON.parse(line.trim().split('\n').filter(Boolean).pop()!);
 if(result.isError)throw new Error(`tool ${name} failed: ${result.content[0].text}`);
 const summary=JSON.parse(result.content[0].text);
 return JSON.parse(fs.readFileSync(path.join(workspace,summary.result_path),'utf8')).data;
}

// MCP 进程从工作区 .mint/packages/dataagent 找已安装数据层；验收用工作区没有
// 装包，把同一 checkout 的 dataagent-data 链接进去，探查仍走公开子进程入口。
function ensureDataLayer(){
 const packages=path.join(workspace,'.mint','packages','dataagent');
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

// docNoType 在修订任务里从 integer 改成 string；nameRequired 把 Customer.name
// 从可选改成必需。两者都不是破坏性变更，网页只勾主确认即可发布。
function fullCompletion(sid:string,draftRef:string,expectedRevision:string,
 catalog:{relationships:{id:string;origin:string}[]}|null,ontologyId:string,
 docNoType='integer',nameRequired=false,includeCustomerName=true){
 const declared=catalog!.relationships.find(link=>link.origin==='declared')!;
 const inferred=catalog!.relationships.find(link=>link.origin==='sample_supported')!;
 const customerProperties:Record<string,{column:string;value_type:string;required?:boolean}>={
  party_no:{column:'party_no',value_type:'string',required:true},
 };
 if(includeCustomerName)
  customerProperties.name={column:'nm',value_type:'string',required:nameRequired};
 return {
  session_id:sid,expected_revision:expectedRevision,draft_ref:draftRef,
  ontology_id:ontologyId,title:'销售单据修订模型',
  concepts:[
   {entity:'SalesOrder',properties:{
    book:{column:'book',value_type:'string',required:true},
    doc_no:{column:'doc_no',value_type:docNoType,required:true},
   },identity_fields:['book','doc_no']},
   {entity:'SalesOrderLine',properties:{
    book:{column:'book',value_type:'string',required:true},
    doc_no:{column:'doc_no',value_type:'integer',required:true},
    seq:{column:'seq',value_type:'integer',required:true},
    amountInCents:{column:'cents',value_type:'decimal',required:true},
   },identity_fields:['book','doc_no','seq']},
   {entity:'Customer',properties:customerProperties,identity_fields:['party_no']},
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

function startDiscovery(ontologyId:string,revise?:string){
 const database='revision-'+ontologyId+'.db';
 const absolute=path.join(workspace!,database);
 if(!fs.existsSync(absolute))
  execFileSync('sqlite3',[absolute],{input:fs.readFileSync(SEED)});
 const args:Record<string,unknown>={
  goal:'发布销售单据本体修订',
  mode:'ontology_discovery',
  sources:[{source_id:'db',kind:'sqlite',locator_ref:database}],
 };
 if(revise)args.revise_ontology_id=revise;
 const started=callTool('intake_start',args);
 const request=callTool('intake_advance',{session_id:started.session_id});
 return {sid:started.session_id as string,request};
}


function sessionId(page:Page){
 return new URL(page.url()).hash.match(/session=([0-9a-f]+)/)![1];
}

async function publishInitial(page:Page,ontologyId:string){
 const initial=startDiscovery(ontologyId);
 callTool('ontology_discovery_propose',{
  session_id:initial.sid,...fullProposal(initial.request)});
 const first=callTool('intake_inference',{session_id:initial.sid});
 const candidate=callTool('ontology_publish_prepare',
  fullCompletion(initial.sid,first.draft.ref,first.expected_revision,first.catalog,
   ontologyId,'integer'));
 const published=await page.request.post(
  `/api/sessions/${initial.sid}/publish/confirm`,{data:{
   candidate_ref:candidate.candidate_ref,draft_ref:candidate.draft_ref,
   source_snapshot:candidate.source_snapshot,
   definition_digest:candidate.definition_digest,
   expected_revision:candidate.session_revision,confirmed:true,
   reason:'e2e 初始本体确认',
  }});
 expect(published.ok(),await published.text()).toBeTruthy();
}

async function prepareRevision(ontologyId:string,
 options:{docNoType?:string;nameRequired?:boolean;includeCustomerName?:boolean}={}){
 const task=startDiscovery(ontologyId,ontologyId);
 callTool('ontology_discovery_propose',{
  session_id:task.sid,...fullProposal(task.request)});
 const inferred=callTool('intake_inference',{session_id:task.sid});
 const candidate=callTool('ontology_publish_prepare',
  fullCompletion(task.sid,inferred.draft.ref,inferred.expected_revision,
   inferred.catalog,ontologyId,options.docNoType||'integer',
   options.nameRequired||false,options.includeCustomerName!==false));
 return {sid:task.sid,candidate};
}

async function retire(page:Page,ontologyId:string){
 const retired=await page.request.post(`/api/ontologies/${ontologyId}/retire`,{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||''},
  data:{reason:'e2e 用例结束后停用，归还默认指针',confirmed:true}});
 expect(retired.ok(),await retired.text()).toBeTruthy();
}

test('非破坏性修订显示类型与必需性差异，网页一次确认发布修订 2',async({page})=>{
 test.skip(!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(300000);
 workspace=await resolveWorkspace(page);
 ensureDataLayer();
 const ontologyId=`sales-revision-${Date.now()}`;
 await publishInitial(page,ontologyId);

 // 修订任务：doc_no integer→string，Customer.name 可选→必需；两项都出现在
 // 发布区差异里，且不改身份、不删属性，所以只需主确认。
 const revision=await prepareRevision(ontologyId,
  {docNoType:'string',nameRequired:true});
 expect(revision.candidate.previous_revision).toBe('1');
 expect(revision.candidate.ontology_revision).toBe('2');
 expect(revision.candidate.destructive).toBe(false);
 expect(revision.candidate.revision_diff.summary)
  .toContain('SalesOrder.doc_no 值类型 integer → string');
 expect(revision.candidate.revision_diff.summary)
  .toContain('Customer.name 必需性 可选 → 必需');

 await page.goto('/#session='+revision.sid);
 await expect(page.getByTestId('revision-publish-notice')).toBeVisible({timeout:30000});
 await expect(page.getByTestId('revision-diff'))
  .toContainText('SalesOrder.doc_no 值类型 integer → string');
 await expect(page.getByTestId('revision-diff'))
  .toContainText('Customer.name 必需性 可选 → 必需');
 await expect(page.getByTestId('revision-destructive')).toHaveCount(0);
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done'))
  .toContainText('修订 1 → 2',{timeout:20000});

 await retire(page,ontologyId);
 await page.getByRole('button',{name:'本体库',exact:true}).click();
 const entry=page.getByTestId(`ontology-${ontologyId}`);
 await expect(entry).toContainText('销售单据修订模型');
 const history=page.getByTestId(`revision-history-${ontologyId}`);
 await history.locator('summary').click();
 await expect(page.getByTestId(`revision-${ontologyId}-1`)).toContainText('修订 1');
 await expect(page.getByTestId(`revision-${ontologyId}-1`)).toContainText('发布于');
 await expect(page.getByTestId(`revision-${ontologyId}-2`)).toContainText('修订 2');
 await expect(page.getByTestId(`revision-${ontologyId}-2`))
  .toContainText('SalesOrder.doc_no 值类型 integer → string');
 await expect(page.getByTestId(`revision-${ontologyId}-2`))
  .toContainText('Customer.name 必需性 可选 → 必需');
});

test('破坏性修订删除属性必须额外勾选旧数据不迁移',async({page})=>{
 test.skip(!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(300000);
 workspace=await resolveWorkspace(page);
 ensureDataLayer();
 const ontologyId=`sales-destructive-${Date.now()}`;
 await publishInitial(page,ontologyId);

 const revision=await prepareRevision(ontologyId,
  {includeCustomerName:false});
 expect(revision.candidate.destructive).toBe(true);
 expect(revision.candidate.requires_no_migration_ack).toBe(true);
 expect(revision.candidate.revision_diff.removed_properties)
  .toContainEqual({concept:'Customer',property:'name',value_type:'string'});

 await page.goto('/#session='+revision.sid);
 await expect(page.getByTestId('revision-publish-notice')).toBeVisible({timeout:30000});
 await expect(page.getByTestId('revision-destructive')).toBeVisible();
 await expect(page.getByTestId('revision-no-migration')).not.toBeChecked();
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeDisabled();
 await page.getByTestId('revision-no-migration').check();
 await expect(page.getByRole('button',{name:'确认发布'})).toBeEnabled();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done'))
  .toContainText('修订 1 → 2',{timeout:20000});

 await retire(page,ontologyId);
});

test('来源变更后新建发现任务保留修订目标',async({page})=>{
 test.skip(!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(300000);
 workspace=await resolveWorkspace(page);
 ensureDataLayer();
 const ontologyId=`sales-rediscover-${Date.now()}`;
 await publishInitial(page,ontologyId);

 const revision=await prepareRevision(ontologyId,{docNoType:'string'});
 // 观察后来源内容变化：确认必须被后端拒绝，网页给出用相同来源新建发现的出路。
 execFileSync('sqlite3',[path.join(workspace!,'revision-'+ontologyId+'.db')],{
  input:"INSERT INTO party VALUES ('P-9','Extra');\n"});

 await page.goto('/#session='+revision.sid);
 await expect(page.getByTestId('publish-card')).toBeVisible({timeout:30000});
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-failure'))
  .toContainText('新建发现任务',{timeout:20000});
 await page.getByRole('button',{name:'用相同来源新建发现任务'}).click();
 await expect(page).not.toHaveURL(new RegExp(revision.sid),{timeout:20000});

 const rediscoverySid=sessionId(page);
 expect(rediscoverySid).not.toBe(revision.sid);
 const created=await page.request.get(`/api/sessions/${rediscoverySid}`);
 expect(created.ok(),await created.text()).toBeTruthy();
 const session=(await created.json()) as {extensions?:Record<string,unknown>};
 const target=session.extensions?.['dataagent.revision_target'] as
  {ontology_id?:string;base_revision?:string}|undefined;
 expect(target).toMatchObject({ontology_id:ontologyId,base_revision:'1'});

 await retire(page,ontologyId);
});
