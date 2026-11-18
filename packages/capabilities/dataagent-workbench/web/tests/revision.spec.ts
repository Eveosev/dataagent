import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

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

// docNoType 在修订任务里从 integer 改成 string，非破坏性，网页可直接确认。
function fullCompletion(sid:string,draftRef:string,expectedRevision:string,
 catalog:{relationships:{id:string;origin:string}[]}|null,ontologyId:string,
 docNoType='integer'){
 const declared=catalog!.relationships.find(link=>link.origin==='declared')!;
 const inferred=catalog!.relationships.find(link=>link.origin==='sample_supported')!;
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

test('已发布本体从网页确认修订 2 并在本体库显示修订历史',async({page})=>{
 test.skip(!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(300000);
 workspace=await resolveWorkspace(page);
 ensureDataLayer();
 const ontologyId=`sales-revision-${Date.now()}`;

 // 初始本体：MCP 提案与补全，HTTP 人工确认发布修订 1。
 const initial=startDiscovery(ontologyId);
 callTool('ontology_discovery_propose',{
  session_id:initial.sid,...fullProposal(initial.request)});
 const first=callTool('intake_inference',{session_id:initial.sid});
 const firstCandidate=callTool('ontology_publish_prepare',
  fullCompletion(initial.sid,first.draft.ref,first.expected_revision,first.catalog,
   ontologyId,'integer'));
 const firstPublished=await page.request.post(
  `/api/sessions/${initial.sid}/publish/confirm`,{data:{
   candidate_ref:firstCandidate.candidate_ref,draft_ref:firstCandidate.draft_ref,
   source_snapshot:firstCandidate.source_snapshot,
   definition_digest:firstCandidate.definition_digest,
   expected_revision:firstCandidate.session_revision,confirmed:true,
   reason:'e2e 初始本体确认',
  }});
 expect(firstPublished.ok()).toBeTruthy();

 // 修订任务：revise_ontology_id 指向刚发布的本体；把 doc_no 从 integer
 // 改成 string，差异应出现在候选与本体库历史中。
 const revision=startDiscovery(ontologyId,ontologyId);
 callTool('ontology_discovery_propose',{
  session_id:revision.sid,...fullProposal(revision.request)});
 const second=callTool('intake_inference',{session_id:revision.sid});
 const revisionCandidate=callTool('ontology_publish_prepare',
  fullCompletion(revision.sid,second.draft.ref,second.expected_revision,
   second.catalog,ontologyId,'string'));
 expect(revisionCandidate.previous_revision).toBe('1');
 expect(revisionCandidate.ontology_revision).toBe('2');
 expect(revisionCandidate.revision_diff.summary)
  .toContain('SalesOrder.doc_no 值类型 integer → string');

 await page.goto('/#session='+revision.sid);
 await expect(page.getByTestId('publish-card')).toBeVisible({timeout:30000});
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done')).toContainText('修订 2',{timeout:20000});

 // 立即归还默认指针，缩短与并行用例争用默认本体的窗口；修订历史保留。
 const retired=await page.request.post(`/api/ontologies/${ontologyId}/retire`,{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||''},
  data:{reason:'e2e 用例结束后停用，归还默认指针',confirmed:true}});
 expect(retired.ok(),await retired.text()).toBeTruthy();

 // 本体库显示修订历史：修订号、本地发布时间与差异摘要（停用后仍可查看）。
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
});
