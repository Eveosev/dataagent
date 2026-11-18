import {test,expect} from '@playwright/test';
import path from 'node:path';

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
 await page.getByRole('button',{name:'开始接入'}).click();
 await page.getByText('识别与探查已完成').waitFor();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
}

test('对象页列出全部待核对问题：总数、阻断数与折叠展开',async({page})=>{
 test.setTimeout(40000);
 await openObjectPageWith13Issues(page);
 // 头部并列总数与阻断数：13 条里 5 条阻断（对象页纠正解除不了）。
 await expect(page.getByTestId('pending-issues')).toContainText('13 项待核对');
 await expect(page.getByTestId('pending-issues')).toContainText('阻断 5 项');
 // 超过 10 条时折叠尾部：默认 10 条可见，阻断类排在最前。
 await expect(page.getByTestId('pending-issue')).toHaveCount(10);
 await expect(page.getByTestId('pending-issue').first()).toContainText('阻断');
 await expect(page.getByTestId('pending-issue').nth(5)).toContainText('可纠正');
 await expect(page.getByText('展开其余 3 条')).toBeVisible();
 // 展开后每条问题都可见。
 await page.getByRole('button',{name:'展开其余 3 条'}).click();
 await expect(page.getByTestId('pending-issue')).toHaveCount(13);
 await expect(page.getByRole('button',{name:'收起其余问题'})).toBeVisible();
 // 问题文案是中文理由，不是裸 code。
 await expect(page.getByTestId('pending-issues')).toContainText('各来源的字段值不一致');
 await expect(page.getByTestId('pending-issues')).toContainText('缺少单据号，无法确定对象');
});

test('每条问题能点到对应对象',async({page})=>{
 test.setTimeout(40000);
 await openObjectPageWith13Issues(page);
 // 对象级冲突问题点回冲突对象 INV-002（默认选中的是 INV-001）。
 await page.getByTestId('pending-issue').filter({hasText:'各来源的字段值不一致'}).nth(1).getByRole('button',{name:'INV-002'}).click();
 await expect(page.locator('.source-tab.active')).toContainText('INV-002');
 // 行号问题（缺单据号，第 1 条记录）点回 INV-001。
 await page.getByTestId('pending-issue').filter({hasText:'缺少单据号'}).first().getByRole('button',{name:'INV-001'}).click();
 await expect(page.locator('.source-tab.active')).toContainText('INV-001');
 // 映射层问题（无对应对象）不渲染成对象按钮。
 await expect(page.getByTestId('pending-issue').filter({hasText:'必填属性没有映射'})).toContainText('映射层');
});
