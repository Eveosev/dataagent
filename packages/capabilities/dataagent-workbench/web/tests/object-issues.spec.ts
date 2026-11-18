import {test,expect} from '@playwright/test';
import path from 'node:path';
import {pinBuiltinOntology,slowTimeout} from './support';

// 跨源场景常有 13 条以上待核对问题；用路由改写把 13 条真实形状的问题注入对象页，
// 覆盖 U3：不再只显示前 5 条，阻断在前、总数与阻断数并列、每条能点到对应对象。
const csv=Buffer.from('number,amount_minor,currency,issuer\nINV-001,126000,CNY,华信办公\nINV-002,90000,CNY,北明科技\nINV-003,75000,CNY,青山贸易\n');

async function openObjectPageWith13Issues(page:import('@playwright/test').Page){
 // 故意把可纠正排在前面：渲染时阻断类必须被提到前面。
 await page.route('**/api/sessions/*/objects',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  const first=body.objects[0],second=body.objects[1],source=body.sources[0].source_id;
  body.issues=[
   {code:'ontology.conflicting_values',entity_id:first.id,target:'amount'},
   {code:'ontology.conflicting_values',entity_id:second.id,target:'issuer'},
   {code:'ontology.conflicting_values',entity_id:second.id,target:'amount'},
   {code:'ontology.conflicting_values',entity_id:first.id,target:'currency'},
   {code:'ontology.required_value_missing',target:'amount',row:2},
   {code:'ontology.required_value_missing',target:'issuer',row:0},
   {code:'ontology.conversion_failed',target:'amount',row:2,detail:'invalid decimal'},
   {code:'ontology.conversion_failed',target:'currency',row:1,detail:'bad value'},
   {code:'ontology.identity_unresolved',row:0},
   {code:'ontology.identity_unresolved',row:1},
   {code:'ontology.required_binding_missing',target:'issuer',source_id:source},
   {code:'ontology.evidence_missing',target:'amount',row:1},
   {code:'ontology.incomplete_source',source_id:source,coverage:'partial'},
  ];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对 13 条待核对问题');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',buffer:csv});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 // 其中一份只有表头：按坏输入标红，另一份探查完成后仍可生成预览。
 await expect(page.getByRole('button',{name:'生成映射预览'})).toBeEnabled();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
}

test('对象页列出全部待核对问题：总数、阻断数与折叠展开',async({page})=>{
 slowTimeout(40000);
 await openObjectPageWith13Issues(page);
 // 头部并列总数与阻断数（FDE2-06）：13 条原始问题里「金额 第 3 行」的缺必填
 // 与转换失败同根因，去重后 12 项；整批保存被任何未解决问题拦下，阻断也计 12。
 await expect(page.getByTestId('pending-issues')).toContainText('12 项待核对');
 await expect(page.getByTestId('pending-issues')).toContainText('阻断 12 项');
 // 去重后 12 项问题按根因合并成 11 条条目（两行缺单号合并为一条「2 行」）。
 // 超过 10 条时折叠尾部：默认 10 条可见，阻断类排在最前。
 await expect(page.getByTestId('pending-issue')).toHaveCount(10);
 await expect(page.getByTestId('pending-issue').first()).toContainText('阻断');
 await expect(page.getByTestId('pending-issue').nth(5)).toContainText('可纠正');
 await expect(page.getByText('展开其余 1 条')).toBeVisible();
 // 展开后每条问题都可见。
 await page.getByRole('button',{name:'展开其余 1 条'}).click();
 await expect(page.getByTestId('pending-issue')).toHaveCount(11);
 await expect(page.getByRole('button',{name:'收起其余问题'})).toBeVisible();
 // 问题文案是中文理由，不是裸 code。
 await expect(page.getByTestId('pending-issues')).toContainText('各来源的字段值不一致');
 await expect(page.getByTestId('pending-issues')).toContainText('缺少单据号，无法确定对象');
});

test('每条问题能点到对应对象',async({page})=>{
 slowTimeout(40000);
 await openObjectPageWith13Issues(page);
 // 对象级冲突问题（entity_id 唯一确定）点回冲突对象 INV-002（默认选中的是 INV-001）。
 await page.getByTestId('pending-issue').filter({hasText:'各来源的字段值不一致'}).nth(1).getByRole('button',{name:'INV-002'}).click();
 await expect(page.locator('.source-tab.active')).toContainText('INV-002');
 // 行号问题来源不明：两行缺单号合并为一条（FDE2-06），组内不给对象入口，
 // 各行显示行号与来源待定。
 const group=page.getByTestId('pending-issue').filter({hasText:'缺少单据号'});
 await expect(group).toHaveCount(1);
 await expect(group).toContainText('2 行 · 缺少单据号，无法确定对象');
 await group.getByText('查看各行').click();
 await expect(group.locator('.group-rows li')).toHaveCount(2);
 await expect(group.locator('.group-rows li').first()).toContainText('第 1 行 · 来源待定');
 await expect(group.locator('.group-rows li').last()).toContainText('第 2 行 · 来源待定');
 await expect(group.locator('.group-rows li').first().getByRole('button')).toHaveCount(0);
 // 来源级问题（无对象可点）显示具体来源名，条目可区分、可处理。
 const sourceIssue=page.getByTestId('pending-issue').filter({hasText:'必填属性没有映射'});
 await expect(sourceIssue).toContainText('invoice.csv');
 await expect(sourceIssue).not.toContainText('映射层');
 // 来源未完整读取同样点出具体来源。
 await expect(page.getByTestId('pending-issue').filter({hasText:'来源未完整读取'})).toContainText('invoice.csv');
});

test('预览没有对象时待核对问题仍在对象页显示',async({page})=>{
 slowTimeout(40000);
 // 只有表头的 CSV：零数据行按坏输入标红提示，预览无实例，后端产生
 // no_records（阻断）且仍可打开对象页。
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入空发票并核对零对象问题');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount_minor,currency,issuer\n')});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByTestId('source-problem')).toContainText('只有表头，没有数据行');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 // 零对象也显示全部待核对问题：no_records 与各必填绑定缺失（带来源名）都在页面上。
 await expect(page.getByTestId('pending-issues')).toContainText('4 项待核对');
 await expect(page.getByTestId('pending-issues')).toContainText('阻断 4 项');
 await expect(page.getByTestId('pending-issue')).toHaveCount(4);
 await expect(page.getByTestId('pending-issue').filter({hasText:'没有可映射的记录'})).toContainText('映射层');
 await expect(page.getByTestId('pending-issue').filter({hasText:'必填属性没有映射'}).first()).toContainText('invoice.csv');
});

test('跨来源同序号的行号问题不链接到错误对象',async({page})=>{
 slowTimeout(40000);
 // 两个来源各有第 0 条记录但归并到不同对象：行号类问题不带 source_id，
 // 无法唯一确定归属对象，条目不渲染对象按钮，点出记录序号并标记来源待定。
 await page.route('**/api/sessions/*/objects',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  body.issues=[{code:'ontology.identity_unresolved',row:0}];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入两份发票并核对跨来源行号');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'invoices-a.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount_minor,currency,issuer\nINV-001,126000,CNY,华信办公\nINV-002,90000,CNY,北明科技\n')},
  {name:'invoices-b.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount_minor,currency,issuer\nINV-101,75000,CNY,青山贸易\nINV-102,66000,CNY,华信办公\n')}]);
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 // 其中一份只有表头：按坏输入标红，另一份探查完成后仍可生成预览。
 await expect(page.getByRole('button',{name:'生成映射预览'})).toBeEnabled();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 const issue=page.getByTestId('pending-issue').filter({hasText:'缺少单据号'});
 await expect(issue).toHaveCount(1);
 await expect(issue).toContainText('第 1 行 · 来源待定');
 await expect(issue.getByRole('button')).toHaveCount(0);
 // 两个来源各自的第 0 条记录都在对象列表里，问题没有误指向其中任何一个。
 await expect(page.locator('.source-tab')).toHaveCount(4);
});

test('问题来源该行无锚点时不出现对象入口',async({page})=>{
 slowTimeout(40000);
 // 一份只有表头（无记录、无锚点）与一份有记录：行号 0 在有记录的来源里对应
 // INV-101，但问题的来源该行没有锚点——不得把入口给另一来源同序号的对象。
 await page.route('**/api/sessions/*/objects',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  const anchorless=body.sources.find((source:{anchors?:Record<string,unknown[]>})=>!source.anchors||Object.keys(source.anchors).length===0);
  body.issues=[{code:'ontology.required_value_missing',target:'amount',row:0,source_id:anchorless.source_id}];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入两份发票并核对无锚点行号');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'invoices-empty.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount_minor,currency,issuer\n')},
  {name:'invoices-b.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount_minor,currency,issuer\nINV-101,75000,CNY,青山贸易\nINV-102,66000,CNY,华信办公\n')}]);
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 // 其中一份只有表头：按坏输入标红，另一份探查完成后仍可生成预览。
 await expect(page.getByRole('button',{name:'生成映射预览'})).toBeEnabled();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 // 问题条目显示行号与来源待定，不出现对象入口，也不链接到 INV-101。
 const issue=page.getByTestId('pending-issue');
 await expect(issue).toHaveCount(1);
 await expect(issue).toContainText('第 1 行 · 来源待定');
 await expect(issue).not.toContainText('INV-101');
 await expect(issue.getByRole('button')).toHaveCount(0);
});

test('未知问题码也只显示中文原因，原始异常进折叠详情',async({page})=>{
 test.setTimeout(40000);
 await page.route('**/api/sessions/*/objects',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  body.issues=[{code:'ontology.future_failure',target:'amount',
   entity_id:body.objects[0]?.id,
   detail:"Invalid isoformat string: 'not-a-date'"}];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对未知问题码');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',buffer:csv});
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByRole('button',{name:'生成映射预览'})).toBeEnabled();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 const issue=page.getByTestId('pending-issue');
 await expect(issue).toHaveCount(1);
 // 未识别的问题码给中文兜底，不把 code 或原始异常铺在列表里。
 await expect(issue).toContainText('该项未通过核对');
 await expect(issue).toContainText('日期时间格式无法解析');
 expect(await issue.innerText()).not.toContain('Invalid isoformat');
 // 完整原文仍保留在可展开的「详情」里。
 await expect(issue.locator('.tech-detail pre'))
  .toContainText("Invalid isoformat string: 'not-a-date'");
});
