import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {anchorRowLocation} from '../src/ontologyBrowse';
import {lockDefaultPointer,slowTimeout,uniqueTag,unlockDefaultPointer} from './support';

const python=process.env.DATAAGENT_TEST_PYTHON;
const SEED=path.resolve('../../dataagent-scenarios/fixtures/intake/sales-discovery.sql');
let workspace='';

// FDE2-13 余项：同一实例的多个属性来自同一来源行时（Word 表格一行拆成多个
// 单元格、Excel 一行拆成多个单元格），实例页只显示一行定位，属性标签负责列。
test('同一来源行的多个属性合并为一行定位',()=>{
 expect(anchorRowLocation({selector:{kind:'text_span',unit_ref:'table:1/row:9/col:1'}},
  '表 1 第 9 行 · 第 1 列')).toBe('表 1 第 9 行');
 expect(anchorRowLocation({selector:{kind:'text_span',unit_ref:'table:1/row:9/col:4'}},
  '表 1 第 9 行 · 第 4 列')).toBe('表 1 第 9 行');
 expect(anchorRowLocation({selector:{kind:'excel_cell',sheet:'明细',range:'A9'}},
  '明细 · A9')).toBe('明细 · 第 9 行');
 expect(anchorRowLocation({selector:{kind:'excel_cell',sheet:'明细',range:'B9'}},
  '明细 · B9')).toBe('明细 · 第 9 行');
 // 跨行区间与行级定位保留原说法。
 expect(anchorRowLocation({selector:{kind:'excel_cell',sheet:'明细',range:'A9:B10'}},
  '明细 · A9:B10')).toBe('明细 · A9:B10');
 expect(anchorRowLocation({selector:{kind:'record_key',keys:{row:2}}},
  '来源行 2')).toBe('来源行 2');
});

// verify_browser.py 只把 URL/token/解释器传给 Playwright，不传工作区路径。
// 用一次真实上传得到 locator_ref（相对工作区），再到系统临时目录里找到同一个
// 文件，从而确定性定位当前服务的工作区；测试自身也走真实后端。
async function resolveWorkspace(page:Page){
 if(process.env.DATAAGENT_TEST_WORKSPACE)return process.env.DATAAGENT_TEST_WORKSPACE;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':`browse-probe-${uniqueTag()}.csv`},
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
    party_no:{column:'party_no',value_type:'string',required:false},
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

// 发布/停用本体移动注册表默认指针：与 publish.spec 的发布用例之间按工作区加
// 文件锁串行，锁的释放挂在 afterEach 上（用例失败也释放）。
let pointerLocked=false;
test.beforeEach(()=>{pointerLocked=false;});
test.afterEach(async({request},testInfo)=>{
 if(!pointerLocked)return;
 // 失败清理：发布成功后、停用前失败会让本体带着默认指针残留，破坏本用例的
 // 重试与并行用例；先在锁内尽力停用，再释放锁（已停用或未发布的忽略结果）。
 if(testInfo.status!=='passed'){
  await request.post('/api/ontologies/browse-sales/retire',
   {data:{reason:'用例失败后的清理停用，恢复默认指针',confirmed:true}}).catch(()=>{});
 }
 unlockDefaultPointer(workspace);
 pointerLocked=false;
});

test('发布本体后按本体浏览已发布实例',async({page})=>{
 test.skip(!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(300000);
 workspace=await resolveWorkspace(page);
 await lockDefaultPointer(workspace);
 pointerLocked=true;
 // 共享工作区里的文件名带用例级唯一后缀：不删除也不覆盖其他并行用例的文件。
 const tag=uniqueTag();
 const database=path.join(workspace,`browse-discovery-${tag}.db`);
 execFileSync('sqlite3',[database],{input:fs.readFileSync(SEED)});
 const token=process.env.DATAAGENT_TEST_TOKEN||'';
 const auth={'x-dataagent-token':token};
 const ordersName=`browse-orders-${tag}.csv`;
 // 上传顺序故意打乱：实例列表默认按身份字段（book、doc_no）升序，
 // 不能按插入顺序展示（FDE2-13）。
 const csv='book,doc_no\n'
  +['SALE,1005','SALE,1001','SALE,1012','SALE,1003','SALE,1010','SALE,1002',
    'SALE,1007','SALE,1004','SALE,1009','SALE,1006','SALE,1011','SALE,1008'].join('\n')+'\n';
 const upload=await page.request.post('/api/files',{
  headers:{...auth,'x-file-name':ordersName},data:csv});
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

 // 2. 先用显式 target 创建映射任务，再停用本体。后端现在拒绝已停用本体
 // 作为新任务目标；先创建才能覆盖「停用后仍可只读浏览」，停用也会把工作区
 // 默认目标还给内置本体，避免长时间占用其它并行用例的默认指针。
 const created=await page.request.post('/api/sessions',{headers:auth,data:{
  goal:'接入浏览用的销售订单',sources:[orderSource],mode:'mapping',
  target:{ontology_id:'browse-sales',concept:'SalesOrder'}}});
 expect(created.ok(),await created.text()).toBeTruthy();
 const mappingSid=(await created.json()).session_id as string;
 const retired=await page.request.post('/api/ontologies/browse-sales/retire',{
  headers:auth,data:{reason:'浏览用例结束后停用，验证停用后仍可只读浏览',confirmed:true}});
 expect(retired.ok(),await retired.text()).toBeTruthy();
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
 await expect(page.getByRole('heading',{name:'核对来源与本体映射'})).toBeVisible({timeout:20000});
 await expect(page.getByText('识别与探查已完成')).toBeVisible({timeout:20000});
 // FDE2-11：面包屑跟随任务目标本体（browse-sales 的注册表标题），不再写死「采购资料」。
 await expect(page.locator('.eyebrow')).toContainText('浏览用销售模型 / 接入任务');

 // 4. 生成未保存的预览：预览对象存在，但已发布实例列表仍为空。
 await page.getByLabel('doc_no 转换方式').selectOption('integer');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-doc_no')).toHaveText('1005',{timeout:20000});
 await page.getByRole('button',{name:'本体库'}).click();
 await page.getByTestId('concept-count-browse-sales-SalesOrder').click();
 await expect(page.getByTestId('instances-empty')).toContainText('发布后才会出现');
 await expect(page.getByTestId('instance-table')).toHaveCount(0);
 await expect(page.getByText('1001')).toHaveCount(0);
 await page.getByRole('button',{name:'返回本体库'}).click();
 await page.getByRole('button',{name:'返回任务'}).click();
 await expect(page.getByTestId('preview-doc_no')).toHaveText('1005',{timeout:20000});

 // 4b. 在对象页人工纠正一个非标识字段，再保存发布；实例列表必须显示纠正后的值，
 // 来源必须是中文的“人工纠正 · 对象页 · 原因”，不能露出决定 ID 或 JSON 指针。
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible({timeout:20000});
 await page.getByLabel('纠正的属性').selectOption('party_no');
 await page.getByLabel('纠正后的值').fill('加急');
 await page.getByLabel('修改原因').fill('客户电话确认加急');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByText(/纠正已保存/)).toBeVisible({timeout:20000});
 await page.getByRole('button',{name:'返回映射页'}).click();
 await expect(page.getByTestId('preview-doc_no')).toHaveText('1005',{timeout:20000});

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
 // 上传顺序打乱时默认仍按身份字段升序展示（FDE2-13）。
 const firstPageNumbers=firstPageDocNos.map(Number);
 expect(firstPageNumbers).toEqual([...firstPageNumbers].sort((a,b)=>a-b));
 await expect(page.getByTestId('instance-source').first()).toContainText(ordersName);
 await expect(page.getByTestId('instance-source').first()).toContainText('来源行');
 await expect(page.getByTestId('instance-task').first()).toContainText('接入浏览用的销售订单');
 await expect(page.getByTestId('instance-revision').first()).toContainText('修订 1');
 await expect(page.getByTestId('instance-table')).not.toContainText('/Users/');
 await expect(page.getByTestId('instance-table')).not.toContainText('sha256:');
 await expect(page.getByRole('columnheader',{name:'客户编号'})).toBeVisible();
 const correctionFilter=page.getByTestId('instance-filter');
 await correctionFilter.getByLabel('属性').selectOption('party_no');
 await correctionFilter.getByLabel('条件').selectOption('eq');
 await correctionFilter.getByLabel('值').fill('加急');
 await page.getByRole('button',{name:'筛选',exact:true}).click();
 await expect(page.getByTestId('instance-row')).toHaveCount(1);
 const correctedRow=page.getByTestId('instance-row').first();
 await expect(correctedRow.getByTestId('instance-value-party_no')).toHaveText('加急');
 const correctedSource=correctedRow.getByTestId('instance-source');
 await expect(correctedSource).toContainText('人工纠正');
 await expect(correctedSource).toContainText('对象页');
 await expect(correctedSource).toContainText('客户电话确认加急');
 await expect(correctedSource).not.toContainText('/decision');
 await expect(correctedSource).not.toContainText('decision:');
 await page.getByRole('button',{name:'清除筛选'}).click();
 await expect(page.getByTestId('instance-row')).toHaveCount(10);
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

 // 6. 分页。后端游标的 total 是剩余数；页面必须继续显示首查总数 12。
 const secondResponse=page.waitForResponse(response=>{
  const url=new URL(response.url());
  return url.pathname.endsWith('/instances')&&url.searchParams.get('cursor')!==null;
 });
 await page.getByRole('button',{name:'下一页'}).click();
 const secondPayload=await (await secondResponse).json() as {count:number;total:number};
 expect(secondPayload.count).toBe(2);
 // HEAD 的查询把游标后的剩余数放进 total（第二页实测为 2）；页面必须仍用首查的 12。
 expect(secondPayload.total).toBe(2);
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

 // 7b. 数值属性的比较筛选（FDE2-13）：doc_no 是 integer，大于 1008 命中 4 条；
 // 字符串属性（book）不提供比较条件。
 const compareFilter=page.getByTestId('instance-filter');
 await compareFilter.getByLabel('属性').selectOption('doc_no');
 await expect(compareFilter.getByLabel('条件').locator('option[value="gt"]')).toHaveCount(1);
 await expect(compareFilter.getByLabel('条件').locator('option[value="lte"]')).toHaveCount(1);
 await compareFilter.getByLabel('条件').selectOption('gt');
 await compareFilter.getByLabel('值').fill('1008');
 await page.getByRole('button',{name:'筛选',exact:true}).click();
 await expect(page.getByTestId('instance-row')).toHaveCount(4);
 await expect(page.getByTestId('instance-filter-summary')).toContainText('单据号 大于 1008');
 await expect(page.getByTestId('instance-value-doc_no').first()).toHaveText('1009');
 await page.getByRole('button',{name:'清除筛选'}).click();
 await expect(page.getByTestId('instance-row')).toHaveCount(10);
 await compareFilter.getByLabel('属性').selectOption('book');
 await expect(compareFilter.getByLabel('条件').locator('option[value="gt"]')).toHaveCount(0);

 // 7c. 点列头切换排序方向，恢复按钮回到身份字段升序（FDE2-13）。
 await page.getByTestId('instance-sort-doc_no').click();
 await page.getByTestId('instance-sort-doc_no').click();
 const descDocNos=(await page.getByTestId('instance-value-doc_no').allTextContents()).map(Number);
 expect(descDocNos).toEqual([...descDocNos].sort((a,b)=>b-a));
 await page.getByTestId('instance-sort-reset').click();
 const ascDocNos=(await page.getByTestId('instance-value-doc_no').allTextContents()).map(Number);
 expect(ascDocNos).toEqual([...ascDocNos].sort((a,b)=>a-b));

 // 7d. 390px 窄屏下实例表横向滚动，身份列（账簿、单据号）粘性固定可见（FDE2-13）。
 await page.setViewportSize({width:390,height:844});
 await expect(page.getByTestId('instance-table')).toBeVisible();
 for(const cell of [page.getByTestId('instance-value-book').first(),
  page.getByTestId('instance-value-doc_no').first()]){
  await expect(cell).toBeVisible();
  const box=await cell.boundingBox();
  expect(box).toBeTruthy();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x+box!.width).toBeLessThanOrEqual(390);
 }
 const horizontallyScrollable=await page.locator('.instance-card .mapping-table-scroll')
  .evaluate(el=>el.scrollWidth>el.clientWidth);
 expect(horizontallyScrollable).toBe(true);
 // 滚到最右后，粘性身份列仍固定在视口内（不是只在初始位置可见）。
 const scroller=page.locator('.instance-card .mapping-table-scroll');
 await scroller.evaluate(el=>{el.scrollLeft=el.scrollWidth;});
 expect(await scroller.evaluate(el=>el.scrollLeft>0)).toBe(true);
 await expect.poll(async()=>{
  const box=await page.getByTestId('instance-value-book').first().boundingBox();
  return box?box.x>=0&&box.x+box.width<=390:false;
 }).toBe(true);
 const docNoBox=await page.getByTestId('instance-value-doc_no').first().boundingBox();
 expect(docNoBox).toBeTruthy();
 expect(docNoBox!.x).toBeGreaterThanOrEqual(0);
 expect(docNoBox!.x+docNoBox!.width).toBeLessThanOrEqual(390);
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'browse-narrow.png')});
 await page.setViewportSize({width:1280,height:720});

 await page.getByTestId('concept-tab-Customer').click();
 await expect(page.getByTestId('instances-empty')).toContainText('发布后才会出现');
 await expect(page.getByTestId('instance-table')).toHaveCount(0);
 await page.getByTestId('concept-tab-SalesOrder').click();
 await expect(page.getByTestId('instance-row')).toHaveCount(10);

 // 8. 所属任务可点到只读对象页，并选中刚点的对象（FDE2-10）：跳转带 instance
 // 参数。后端实例页返回的行集合在并行用例间不稳定，动态点一行非默认对象
 // （默认第一个对象是 1005），再断言对象页高亮的正是刚点的那一行。
 const docNos=await page.getByTestId('instance-value-doc_no').allTextContents();
 const pickIndex=docNos.findIndex(doc=>doc&&doc!=='1005');
 expect(pickIndex).toBeGreaterThan(-1);
 await page.getByTestId('instance-row').nth(pickIndex).getByTestId('instance-task').getByRole('button').click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible({timeout:20000});
 await expect(page.getByText('接入已保存，对象为只读')).toBeVisible();
 await expect(page.locator('.source-tab.active')).toContainText(`SALE · ${docNos[pickIndex]}`);

 // 9. M1 只允许发布一次；浏览器只模拟“注册表已切到尚无实例的修订 2”，
 // 历史修订 1 的实例查询仍走真实后端。这样不写共享 SQLite，也不会在并行
 // 用例探查时制造数据库锁；计数与历史入口的对应关系仍由真实页面验证。
 const registryResponse=await page.request.get('/api/ontologies',{headers:auth});
 expect(registryResponse.ok(),await registryResponse.text()).toBeTruthy();
 const registry=await registryResponse.json() as {
  ontologies:Array<Record<string,unknown>&{id:string;concepts:string[];instance_counts?:Record<string,number>;
   current_revision_instance_counts?:Record<string,number>;registry_revision?:number}>;
  [key:string]:unknown;
 };
 const revised=registry.ontologies.find(item=>item.id==='browse-sales');
 expect(revised).toBeTruthy();
 const revisedEntry={
  ...revised,
  ontology_revision:'2',
  registry_revision:Number(revised!.registry_revision||1)+1,
  state:'retired',
  retired_at:new Date().toISOString(),
  retired_by:'local-owner:test',
  retire_reason:'浏览用例模拟历史修订，验证计数与入口',
  current_revision_instance_counts:Object.fromEntries((revised!.concepts||[]).map(name=>[name,0])),
 };
 await page.route(/\/api\/ontologies$/,async route=>{
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
   ...registry,ontologies:registry.ontologies.map(item=>item.id==='browse-sales'?revisedEntry:item)})});
 });
 await page.route(/\/api\/ontologies\/browse-sales\/instances\?/,async route=>{
  const url=new URL(route.request().url());
  if(url.searchParams.get('revision')!=='2'){await route.continue();return;}
  const concept=url.searchParams.get('concept')||'SalesOrder';
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
   ontology_id:'browse-sales',ontology_revision:'browse-sales@2',revision:'2',
   concept,entity_type:concept,ontology_state:'retired',deactivated:true,items:[],
   count:0,total:0,has_more:false,next_cursor:null})});
 });
 await page.getByRole('button',{name:'本体库'}).click();
 const revisedRow=page.getByTestId('ontology-browse-sales');
 await expect(revisedRow).toContainText('当前修订 0 个 · 历史累计 12 个',{timeout:20000});
 const currentCount=page.getByTestId('concept-count-browse-sales-SalesOrder');
 const historyCount=page.getByTestId('concept-history-browse-sales-SalesOrder');
 await expect(currentCount).toContainText('0 个对象');
 await expect(historyCount).toContainText('历史累计 12 个');
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'ontologies-history.png'),fullPage:true});

 await currentCount.click();
 await expect(page.getByTestId('instances-empty')).toContainText('发布后才会出现');
 await expect(page.getByTestId('instance-table')).toHaveCount(0);
 await page.getByRole('button',{name:'返回本体库'}).click();
 await historyCount.click();
 await expect(page.locator('#instance-revision')).toHaveValue('1',{timeout:20000});
 await expect(page.getByTestId('instance-history')).toContainText('修订 1');
 await expect(page.getByTestId('instance-row')).toHaveCount(10);
 await expect(page.getByText('第 1 页 · 共 12 条')).toBeVisible();
 if(process.env.DATAAGENT_SCREENSHOT)await page.screenshot({
  path:path.join(path.dirname(process.env.DATAAGENT_SCREENSHOT),'browse-history.png'),fullPage:true});
});
