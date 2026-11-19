import {test,expect} from '@playwright/test';
import {humanDetail} from '../src/client';
import {awaitProbed,pinBuiltinOntology,slowTimeout} from './support';

// D5a 补审：humanDetail 对中英混合原文的判定。主文案只出现映射后的中文；
// 未识别的英文或混合原文（含少量中文的英文报错）只进可展开的「详情」。
test('humanDetail：中英混合与英文原文只进详情，中文原文进主文案',()=>{
 // 含少量中文的英文原文不再凭几个汉字被当成中文直通主文案。
 const mixed="could not convert '华信' to decimal";
 expect(humanDetail(mixed)).toEqual({summary:'',detail:mixed});
 expect(humanDetail('invalid decimal')).toEqual({summary:'',detail:'invalid decimal'});
 // 主体是中文、只夹短英文片段（如 NaN）的原文同样进详情，不数中英字符多少。
 expect(humanDetail('金额无效: NaN')).toEqual({summary:'',detail:'金额无效: NaN'});
 // 中文原文（含带数字的定位）仍按原文进主文案；无中文也无拉丁字母的片段进详情。
 expect(humanDetail('各来源的字段值不一致')).toEqual({summary:'各来源的字段值不一致'});
 expect(humanDetail('第 2 行')).toEqual({summary:'第 2 行'});
 expect(humanDetail('1250')).toEqual({summary:'',detail:'1250'});
 // 已知原文映射成中文说法；前缀匹配保留拼接的字段名。
 expect(humanDetail('nonfinite number')).toEqual({summary:'数值超出可表示范围'});
 expect(humanDetail('recorded fields no longer resolve in the source: amountInCents'))
  .toEqual({summary:'来源字段在当前来源中已不再可解析：amountInCents'});
});

test('对象页问题主文案不出现未识别英文，原文折叠进详情',async({page})=>{
 slowTimeout(40000);
 // 用路由改写注入一条 detail 为中英混合原文的问题，覆盖页面接线：
 // 主文案只给中文理由，混合原文收进折叠的「详情」。
 await page.route('**/api/sessions/*/objects',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  body.issues=[{code:'ontology.conversion_failed',target:'amount',entity_id:body.objects[0]?.id,
   detail:"could not convert '华信' to decimal"}];
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对混合原文的问题说明');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount,currency,issuer\nINV-001,1250,CNY,华信办公\n')});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitProbed(page);
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 const issue=page.getByTestId('pending-issue');
 await expect(issue).toHaveCount(1);
 // 主文案只给中文理由；折叠的详情不计入可见文本，英文原文不出现。
 await expect(issue).toContainText('值无法按目标类型转换');
 expect(await issue.innerText()).not.toContain('could not convert');
 // 原文完整保留在可展开的「详情」里，供需要时核对。
 const detail=issue.locator('.tech-detail');
 await expect(detail).toHaveCount(1);
 await expect(detail.locator('pre')).toContainText("could not convert '华信' to decimal");
});
