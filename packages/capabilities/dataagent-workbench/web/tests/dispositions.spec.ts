import {test,expect} from '@playwright/test';
import {pinBuiltinOntology,slowTimeout} from './support';

// G2 处置入口 + FDE-11 可读性：被拦的问题旁给出可用的处置（标记分区不适用、
// 排除记录、只保存无问题对象），原因必填；缺键对象显示来源描述而不是内部哈希。
//
// 处置提交走真实后端路由 POST /api/sessions/<id>/dispositions 与 /review 的
// allow_partial（B1 已挂出）：请求与响应契约从真实网络交互里核对，不拦截；
// 视图刷新（处置使预览失效、部分保存使接入落盘）用页面状态断言。
const disposalUrl=/\/api\/sessions\/[^/]+\/dispositions$/;
const reviewUrl=/\/api\/sessions\/[^/]+\/review$/;
async function postResponse(page:import('@playwright/test').Page,url:RegExp){
 return page.waitForResponse(response=>response.request().method()==='POST'&&url.test(response.url()));
}
const missingNumberCsv=Buffer.from('number,amount,currency,issuer\nINV-001,1260,CNY,华信办公\n,900,CNY,北明科技\n');

async function openObjectPage(page:import('@playwright/test').Page,files:Parameters<import('@playwright/test').Page['setInputFiles']>[1]){
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入缺键记录并核对处置入口');
 await page.getByLabel('选择材料').setInputFiles(files);
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 // 预览问题用中文说明并点名对象，不再显示内部代码。
 await expect(page.getByTestId('mapping-issues')).toContainText('缺少单据号，无法确定对象');
 await expect(page.getByTestId('mapping-issues')).not.toContainText('ontology.');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
}

test('缺键对象显示来源描述，处置需要填写原因',async({page})=>{
 slowTimeout(40000);
 await openObjectPage(page,{name:'发票.csv',mimeType:'text/csv',buffer:missingNumberCsv});
 // FDE-11：缺键对象不显示 candidate:<哈希>，改用来源描述点名（第 3 行是文件里的原始行号）。
 await expect(page.locator('.source-tab').filter({hasText:'来源行 3'})).toContainText('发票.csv · 来源行 3（无单号）');
 await expect(page.getByText(/candidate:/)).toHaveCount(0);
 // FDE-11：徽标与列名是中文。
 await expect(page.locator('.mapping-panel .panel-heading .badge')).toContainText('采购单据');
 await expect(page.locator('.detail-panel .panel-heading .badge')).toContainText('未核对');
 await expect(page.locator('.mapping-table thead th').first()).toHaveText('本体属性');
 // 缺键记录的阻断问题旁给出排除记录的处置；行号与对象标签统一用「来源行 N」
 //（record 是 0 起的记录序号 1，锚点定位到文件里的原始行号 3）。
 const issue=page.getByTestId('pending-issue').filter({hasText:'缺少单据号'});
 await expect(issue).toContainText('阻断');
 const disposal=issue.getByTestId('disposal-option');
 await expect(disposal).toContainText('排除「发票.csv」来源行 3');
 // 原因空白时不可提交。
 const reason=disposal.getByLabel(/处置原因/);
 await expect(disposal.getByRole('button',{name:'提交处置'})).toBeDisabled();
 await reason.fill('表头行混入数据，排除该行');
 await expect(disposal.getByRole('button',{name:'提交处置'})).toBeEnabled();
});

test('排除记录处置走真实后端并刷新视图',async({page})=>{
 slowTimeout(40000);
 await openObjectPage(page,{name:'发票.csv',mimeType:'text/csv',buffer:missingNumberCsv});
 const issue=page.getByTestId('pending-issue').filter({hasText:'缺少单据号'});
 const disposal=issue.getByTestId('disposal-option');
 await disposal.getByLabel(/处置原因/).fill('表头行混入数据，排除该行');
 const [response]=await Promise.all([
  postResponse(page,disposalUrl),
  disposal.getByRole('button',{name:'提交处置'}).click(),
 ]);
 expect(response.status()).toBe(200);
 const request=response.request().postDataJSON() as Record<string,unknown>;
 const body=await response.json();
 // 提交的是可审计的处置契约：动作、来源、记录与原因齐全，修订带校验。
 expect(request).toMatchObject({action:'exclude_record',source_id:expect.any(String),
  record:1,reason:'表头行混入数据，排除该行'});
 expect(String(request.expected_revision)).toMatch(/^[0-9]+$/);
 // 真实后端记录了处置审计并使预览失效。
 expect(body.entry).toMatchObject({action:'exclude_record',record:1,
  reason:'表头行混入数据，排除该行',source_id:expect.any(String)});
 expect(String(body.session_revision)).toMatch(/^[0-9]+$/);
 await expect(page.getByTestId('correction-success')).toContainText('处置已记录');
 // 视图刷新：预览失效后对象区回到空态，阻断问题不再挂着。
 await expect(page.getByText('生成映射预览后，在这里查看对象。')).toBeVisible();
 await expect(page.getByTestId('pending-issues')).toHaveCount(0);
});

test('只保存无问题对象需要填写原因并走真实后端 allow_partial',async({page})=>{
 slowTimeout(40000);
 await openObjectPage(page,{name:'发票.csv',mimeType:'text/csv',buffer:missingNumberCsv});
 const partial=page.getByTestId('partial-save');
 await expect(partial).toBeVisible();
 await expect(partial).toContainText('只保存无问题对象');
 const reason=partial.getByLabel('部分保存原因');
 await expect(partial.getByRole('button',{name:'只保存无问题对象'})).toBeDisabled();
 await reason.fill('先保存有单号的对象，缺键记录单独处理');
 await expect(partial.getByRole('button',{name:'只保存无问题对象'})).toBeEnabled();
 const [response]=await Promise.all([
  postResponse(page,reviewUrl),
  partial.getByRole('button',{name:'只保存无问题对象'}).click(),
 ]);
 expect(response.status()).toBe(200);
 const request=response.request().postDataJSON() as Record<string,unknown>;
 const body=await response.json();
 // 提交契约：allow_partial 与原因走顶层，决定范围是整批映射。
 expect(request).toMatchObject({allow_partial:true,reason:'先保存有单号的对象，缺键记录单独处理',
  decision:{target_scope:'mapping',decision:'save'}});
 // 真实后端按计划放行：INV-001 保存，缺键记录挂起为未识别，无对象被挡。
 expect(body.partial).toBe(true);
 expect(body.saved).toHaveLength(1);
 expect((body.saved[0] as {values:{number?:string}}).values.number).toBe('INV-001');
 expect(body.suspended).toHaveLength(0);
 expect(body.unidentified_records).toHaveLength(1);
 await expect(page.getByTestId('correction-success')).toContainText('已按部分保存放行无阻断的对象');
 // 成功后视图刷新：接入进入已保存，对象只读。
 await expect(page.getByText('接入已保存，对象为只读。')).toBeVisible();
});

test('空白页来源可标记分区不适用',async({page})=>{
 slowTimeout(40000);
 // mixed.pdf 第 2 页是空白页：来源未完整读取（阻断）旁给出标记分区不适用的处置。
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入混排发票并核对空白页处置');
 await page.getByLabel('选择材料').setInputFiles({name:'mixed.pdf',mimeType:'application/pdf',
  buffer:await import('node:fs').then(fs=>fs.readFileSync('../../dataagent-scenarios/fixtures/intake/mixed.pdf'))});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 const issue=page.getByTestId('pending-issue').filter({hasText:'来源未完整读取'});
 await expect(issue).toContainText('mixed.pdf');
 const disposal=issue.getByTestId('disposal-option');
 await expect(disposal).toContainText('标记「mixed.pdf」分区 2 不适用');
 await expect(disposal.getByRole('button',{name:'提交处置'})).toBeDisabled();
 await disposal.getByLabel(/处置原因/).fill('第 2 页是空白页，确认不适用');
 const [response]=await Promise.all([
  postResponse(page,disposalUrl),
  disposal.getByRole('button',{name:'提交处置'}).click(),
 ]);
 expect(response.status()).toBe(200);
 const request=response.request().postDataJSON() as Record<string,unknown>;
 const body=await response.json();
 expect(request).toMatchObject({action:'partition_not_applicable',partition:2,
  reason:'第 2 页是空白页，确认不适用'});
 expect(body.entry).toMatchObject({action:'partition_not_applicable',partition:2,
  reason:'第 2 页是空白页，确认不适用'});
 await expect(page.getByTestId('correction-success')).toContainText('处置已记录');
 // 视图刷新：预览失效后对象区回到空态。
 await expect(page.getByText('生成映射预览后，在这里查看对象。')).toBeVisible();
});
