import {test,expect} from '@playwright/test';

// 两份同构 CSV 对同一张单据给出不同金额：对象页冲突字段并排显示各来源原值，
// 一键采用后左侧未解决计数即时更新（FDE-5）。
async function openConflictingObjectPage(page:import('@playwright/test').Page){
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入两份金额不一致的发票并核对冲突原值');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'发票-a.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount,currency,issuer\nINV-105,1250,CNY,华信办公\n')},
  {name:'发票-b.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount,currency,issuer\nINV-105,2510,CNY,华信办公\n')}]);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-105');
}

test('冲突字段并排显示各来源原值并可一键采用',async({page})=>{
 test.setTimeout(40000);
 await openConflictingObjectPage(page);
 // 冲突字段当前值为空，但各来源原值并排可见，不需要逐个切换来源去猜。
 await expect(page.getByTestId('object-amount')).toHaveText('—');
 const conflict=page.getByTestId('object-conflict-amount');
 await expect(conflict).toBeVisible();
 await expect(conflict).toContainText('金额');
 await expect(conflict).toContainText('发票-a.csv：1250');
 await expect(conflict).toContainText('发票-b.csv：2510');
 await expect(conflict).toContainText('各来源的字段值不一致');
 // 一键采用发票-b 的原值：金额立即变为 2510。
 await conflict.locator('.conflict-source').filter({hasText:'发票-b.csv：2510'}).getByRole('button',{name:'采用此值'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('2510');
 // 纠正冲突后左侧未解决计数即时更新：徽标消失，冲突面板随之消失。
 await expect(page.locator('.source-tab')).not.toContainText('项未解决');
 await expect(page.getByTestId('object-conflicts')).toHaveCount(0);
 await expect(page.getByTestId('correction-success')).toContainText('纠正已保存：金额 → 2510');
 await expect(page.getByText(/用户纠正 · 决定/).first()).toBeVisible();
});
