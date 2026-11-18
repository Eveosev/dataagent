import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const python=process.env.DATAAGENT_TEST_PYTHON;
const SEED=path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql');
let workspace='';

// verify_browser.py 只把 URL/token/解释器传给 Playwright，不传工作区路径。
// 用一次真实上传得到 locator_ref（相对工作区），再到系统临时目录里找到同一个
// 文件，从而确定性定位当前服务的工作区；测试自身也走真实后端。
async function resolveWorkspace(page:Page){
 if(process.env.DATAAGENT_TEST_WORKSPACE)return process.env.DATAAGENT_TEST_WORKSPACE;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':'browse-probe.csv'},
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

function sessionId(page:Page){
 return new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session')||'';
}

type Catalog={relationships:{id:string;origin:string}[]};
function proposal(request:{expected_revision:string;source_revision:string;catalog:Catalog}){
 const declared=request.catalog.relationships.find(link=>link.origin==='declared')!;
 const inferred=request.catalog.relationships.find(link=>link.origin==='sample_supported')!;
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

function completion(sid:string,draftRef:string,expectedRevision:string,catalog:Catalog){
 const declared=catalog.relationships.find(link=>link.origin==='declared')!;
 const inferred=catalog.relationships.find(link=>link.origin==='sample_supported')!;
 return {session_id:sid,expected_revision:expectedRevision,draft_ref:draftRef,
  ontology_id:'browse-sales',title:'浏览用销售模型',
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
    name:{column:'nm',value_type:'string',required:false},
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

test('发布本体后按本体浏览已发布实例',async({page})=>{
 test.skip(!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 test.setTimeout(300000);
 workspace=await resolveWorkspace(page);
 const database=path.join(workspace,'browse-discovery.db');
 fs.rmSync(database,{force:true});
 execFileSync('sqlite3',[database],{input:fs.readFileSync(SEED)});
 const token=process.env.DATAAGENT_TEST_TOKEN||'';
 const auth={'x-dataagent-token':token};
 const csv='book,doc_no\n'+Array.from({length:12},(_,i)=>`SALE,${1001+i}`).join('\n')+'\n';
 const upload=await page.request.post('/api/files',{
  headers:{...auth,'x-file-name':'browse-orders.csv'},data:csv});
 expect(upload.ok(),await upload.text()).toBeTruthy();
 const orderSource=await upload.json();

 // 1. 从数据库发现并发布一个多概念本体（人工确认只走网页通道）。
 await page.goto('/');
 await page.getByLabel('接入目标').fill('发现销售单据本体用于浏览');
 await page.getByLabel('选择材料').setInputFiles(database);
 await page.getByRole('radio',{name:'从数据库发现本体'}).check();
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('heading',{name:'本体发现'})).toBeVisible({timeout:20000});
 await expect(page.getByRole('heading',{name:'来源证据'})).toBeVisible({timeout:20000});
 const discoverySid=sessionId(page);
 const request=callTool('intake_inference',{session_id:discoverySid}) as {
  expected_revision:string;source_revision:string;catalog:Catalog};
 callTool('ontology_discovery_propose',{session_id:discoverySid,...proposal(request)});
 await expect(page.getByRole('heading',{name:'本体草案',exact:true})).toBeVisible({timeout:20000});
 await page.getByRole('button',{name:'确认当前草案'}).click();
 await expect(page.getByText('已通过审核').first()).toBeVisible({timeout:20000});

 const fresh=callTool('intake_inference',{session_id:discoverySid}) as {
  expected_revision:string;draft:{ref:string};catalog:Catalog};
 callTool('ontology_publish_prepare',
  completion(discoverySid,fresh.draft.ref,fresh.expected_revision,fresh.catalog));
 await expect(page.getByText('候选定义摘要 · 浏览用销售模型')).toBeVisible({timeout:20000});
 await expect(page.getByTestId('publish-blocked')).toHaveCount(0);
 await page.getByLabel('我已核对候选定义与来源摘要，确认发布').check();
 await page.getByRole('button',{name:'确认发布'}).click();
 await expect(page.getByTestId('publish-done')).toContainText('browse-sales',{timeout:20000});

 // 2. 立刻停用本体，把工作区默认目标还给内置本体。停用只影响新任务的默认选择；
 // 本用例随后通过真实接口显式指定 target 创建映射任务（与任务固定目标同一机制），
 // 避免长时间占用其它并行用例的默认指针。
 const retired=await page.request.post('/api/ontologies/browse-sales/retire',{
  headers:auth,data:{reason:'浏览用例结束后停用，验证停用后仍可只读浏览',confirmed:true}});
 expect(retired.ok(),await retired.text()).toBeTruthy();
 const created=await page.request.post('/api/sessions',{headers:auth,data:{
  goal:'接入浏览用的销售订单',sources:[orderSource],mode:'mapping',
  target:{ontology_id:'browse-sales',concept:'SalesOrder'}}});
 expect(created.ok(),await created.text()).toBeTruthy();
 const mappingSid=(await created.json()).session_id as string;
 const advanced=await page.request.post(`/api/sessions/${mappingSid}/advance`,{headers:auth});
 expect(advanced.ok(),await advanced.text()).toBeTruthy();

 // 3. 本体库显示每个概念的已发布实例数；没有实例时点进去是「发布后才会出现」，
 // 已停用本体仍可只读浏览。
 await page.getByRole('button',{name:'查看本体库'}).click();
 await expect(page.getByRole('heading',{name:'本体',exact:true})).toBeVisible();
 const ontologyRow=page.getByTestId('ontology-browse-sales');
 await expect(ontologyRow).toContainText('已停用');
 await expect(page.getByTestId('concept-count-browse-sales-SalesOrder')).toContainText('0');
 await page.getByTestId('concept-count-browse-sales-SalesOrder').click();
 await expect(page.getByTestId('instances-retired')).toContainText('已停用');
 await expect(page.getByTestId('instances-empty')).toContainText('发布后才会出现');
 await expect(page.getByRole('button',{name:'新建接入'})).toBeVisible();

 await page.goto('/#session='+mappingSid);
 await page.reload();
 await expect(page.getByRole('heading',{name:'核对来源与 Ontology 映射'})).toBeVisible({timeout:20000});
 await expect(page.getByText('识别与探查已完成')).toBeVisible({timeout:20000});

 // 4. 生成未保存的预览：预览对象存在，但已发布实例列表仍为空。
 await page.getByLabel('doc_no 转换方式').selectOption('integer');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-doc_no')).toHaveText('1001',{timeout:20000});
 await page.getByRole('button',{name:'本体库'}).click();
 await page.getByTestId('concept-count-browse-sales-SalesOrder').click();
 await expect(page.getByTestId('instances-empty')).toContainText('发布后才会出现');
 await expect(page.getByTestId('instance-table')).toHaveCount(0);
 await expect(page.getByText('1001')).toHaveCount(0);
 await page.getByRole('button',{name:'返回本体库'}).click();
 await page.getByRole('button',{name:'返回任务'}).click();
 await expect(page.getByTestId('preview-doc_no')).toHaveText('1001',{timeout:20000});

 // 5. 保存后实例数出现，按概念列对象并显示来源定位、所属任务与修订。
 const save=page.getByRole('button',{name:'保存接入'});
 await expect(save).toBeEnabled({timeout:20000});
 await save.click();
 await expect(page.getByText('接入已保存')).toBeVisible({timeout:20000});
 await page.getByRole('button',{name:'本体库'}).click();
 await expect(page.getByTestId('concept-count-browse-sales-SalesOrder')).toContainText('12',{timeout:20000});
 await expect(page.getByTestId('ontology-counts-browse-sales')).toContainText('共 12 个已发布对象');
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'ontologies-live.png'),fullPage:true});
 await page.getByTestId('concept-count-browse-sales-SalesOrder').click();
 await expect(page.getByTestId('instances-retired')).toContainText('已停用');
 await expect(page.getByTestId('instance-table')).toBeVisible({timeout:20000});
 await expect(page.getByTestId('instance-row')).toHaveCount(10);
 await expect(page.getByText('第 1 页 · 共 12 条')).toBeVisible();
 await expect(page.getByRole('columnheader',{name:'账簿'})).toBeVisible();
 await expect(page.getByRole('columnheader',{name:'单据号'})).toBeVisible();
 await expect(page.getByTestId('instance-value-book').first()).toHaveText('SALE');
 const firstPageDocNos=await page.getByTestId('instance-value-doc_no').allTextContents();
 expect(firstPageDocNos).toHaveLength(10);
 await expect(page.getByTestId('instance-source').first()).toContainText('browse-orders.csv');
 await expect(page.getByTestId('instance-source').first()).toContainText('来源行');
 await expect(page.getByTestId('instance-task').first()).toContainText('接入浏览用的销售订单');
 await expect(page.getByTestId('instance-revision').first()).toContainText('修订 1');
 await expect(page.getByTestId('instance-table')).not.toContainText('/Users/');
 await expect(page.getByTestId('instance-table')).not.toContainText('sha256:');
 const revisionSelect=page.locator('#instance-revision');
 await expect(revisionSelect).toHaveValue('1');
 await expect(revisionSelect.locator('option').first()).toContainText('（当前）');
 await revisionSelect.selectOption('__other__');
 await page.locator('#other-revision').fill('1');
 await page.getByRole('button',{name:'切换',exact:true}).click();
 await expect(revisionSelect).toHaveValue('1');
 await expect(page.getByTestId('instance-row')).toHaveCount(10);
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'browse-live.png'),fullPage:true});

 // 6. 分页。
 await page.getByRole('button',{name:'下一页'}).click();
 await expect(page.getByText('第 2 页 · 共 12 条')).toBeVisible();
 await expect(page.getByTestId('instance-row')).toHaveCount(2);
 const secondPageDocNos=await page.getByTestId('instance-value-doc_no').allTextContents();
 expect([...firstPageDocNos,...secondPageDocNos].sort())
  .toEqual(Array.from({length:12},(_,i)=>String(1001+i)).sort());
 await page.getByRole('button',{name:'上一页'}).click();
 await expect(page.getByText('第 1 页 · 共 12 条')).toBeVisible();

 // 7. 按已定义属性筛选：等于、包含，切换概念。
 const filter=page.getByTestId('instance-filter');
 await filter.getByLabel('属性').selectOption('doc_no');
 await filter.getByLabel('条件').selectOption('eq');
 await filter.getByLabel('值').fill('1002');
 await page.getByRole('button',{name:'筛选',exact:true}).click();
 await expect(page.getByTestId('instance-row')).toHaveCount(1);
 await expect(page.getByTestId('instance-value-doc_no')).toHaveText('1002');
 await expect(page.getByTestId('instance-filter-summary')).toContainText('单据号');
 await filter.getByLabel('属性').selectOption('book');
 await filter.getByLabel('条件').selectOption('contains');
 await filter.getByLabel('值').fill('AL');
 await page.getByRole('button',{name:'筛选',exact:true}).click();
 await expect(page.getByTestId('instance-row')).toHaveCount(10);
 await page.getByRole('button',{name:'清除筛选'}).click();
 await expect(page.getByTestId('instance-row')).toHaveCount(10);

 await page.getByTestId('concept-tab-Customer').click();
 await expect(page.getByTestId('instances-empty')).toContainText('发布后才会出现');
 await expect(page.getByTestId('instance-table')).toHaveCount(0);
 await page.getByTestId('concept-tab-SalesOrder').click();
 await expect(page.getByTestId('instance-row')).toHaveCount(10);

 // 8. 所属任务可点到只读对象页。
 await page.getByTestId('instance-task').first().getByRole('button').click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible({timeout:20000});
 await expect(page.getByText('接入已保存，对象为只读')).toBeVisible();
});
