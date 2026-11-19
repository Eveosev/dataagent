import {expect,test} from '@playwright/test';
import {awaitProbed,pinBuiltinOntology,slowTimeout} from './support';

// FDE2-10：对象标签用全部身份字段组合。路由把内置采购本体的身份字段改成
// 「币种 + 单据编号」，三份材料的币种相同（第一个身份字段重复），标签仍要
// 能区分；过长时截断，悬停（title）显示完整标签。
test('对象标签用全部身份字段，第一个字段重复也能区分',async({page})=>{
 slowTimeout(40000);
 const sharedCurrency='人民币差旅报销华东区二〇二六年度第一季度备用金';
 await page.route('**/api/sessions/*/objects',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  if(body.ontology){
   if(body.ontology.concepts&&body.ontology.concepts.PurchaseDocument)
    body.ontology.concepts.PurchaseDocument.identity_fields=['currency','number'];
   else body.ontology.identity_fields=['currency','number'];
  }
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入差旅报销并核对对象标签');
 await page.getByLabel('选择材料').setInputFiles({name:'expense.csv',mimeType:'text/csv',
  buffer:Buffer.from(`number,amount_minor,currency\nBX-2026-0001,126000,${sharedCurrency}\nBX-2026-0002,90000,${sharedCurrency}\nBX-2026-0003,75000,${sharedCurrency}\n`)});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitProbed(page);
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 // 三个对象的标签互不重复：第一个身份字段（币种）都一样，靠第二个字段区分。
 const tabs=page.locator('.source-tab');
 await expect(tabs).toHaveCount(3);
 const labels=await tabs.allTextContents();
 expect(new Set(labels).size).toBe(3);
 for(const number of ['BX-2026-0001','BX-2026-0002','BX-2026-0003'])
  await expect(tabs.filter({hasText:number})).toHaveCount(1);
 // 标签过长时截断（带省略号），悬停显示完整组合。
 const first=tabs.filter({hasText:'BX-2026-0001'});
 await expect(first.locator('span').nth(1)).toContainText('…');
 await expect(first).not.toHaveText(sharedCurrency);
 expect(await first.getAttribute('title')).toBe(`${sharedCurrency} · BX-2026-0001`);
});

// FDE2-14：发布日期按浏览器本地时区显示。路由把注册表时间固定在 UTC
// 2026-11-18 23:30（东八区已是 11-19）：按 UTC 截取日期会差一天。
test('发布日期按本地时区显示，不按 UTC 截取',async({page})=>{
 const publishedAt='2026-11-18T23:30:00Z';
 await page.route('**/api/ontologies',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  for(const entry of body.ontologies||[])entry.published_at=publishedAt;
  await route.fulfill({response,json:body});
 });
 await page.goto('/#ontologies=1');
 // 期望值用同一份 JS 时区规则计算，与本机浏览器时区一致。
 const moment=new Date(publishedAt);
 const pad=(part:number)=>String(part).padStart(2,'0');
 const local=`${moment.getFullYear()}-${pad(moment.getMonth()+1)}-${pad(moment.getDate())}`;
 await expect(page.getByText(`发布于 ${local}`).first()).toBeVisible();
 // 本地日期与 UTC 日期不同时（如东八区），按 UTC 截取的「2026-11-18」不应出现；
 // 测试机时区恰为 UTC 时两者相同，跳过该反例断言。
 if(local!=='2026-11-18')await expect(page.getByText('发布于 2026-11-18')).toHaveCount(0);
});
