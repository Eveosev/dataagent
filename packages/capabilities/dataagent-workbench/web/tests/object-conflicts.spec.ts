import {test,expect} from '@playwright/test';
import {awaitProbed,pinBuiltinOntology,slowTimeout} from './support';

// 两份同构 CSV 对同一张单据给出不同金额：对象页冲突字段并排显示各来源原值，
// 一键采用后左侧未解决计数即时更新（FDE-5）。
async function openConflictingObjectPage(page:import('@playwright/test').Page){
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入两份金额不一致的发票并核对冲突原值');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'发票-a.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount,currency,issuer\nINV-105,1250,CNY,华信办公\n')},
  {name:'发票-b.csv',mimeType:'text/csv',buffer:Buffer.from('number,amount,currency,issuer\nINV-105,2510,CNY,华信办公\n')}]);
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitProbed(page);
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-105');
}

test('冲突字段并排显示各来源原值并可一键采用',async({page})=>{
 slowTimeout(40000);
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

test('同一来源的多个冲突原值逐个展示并都可采用',async({page})=>{
 slowTimeout(40000);
 // 一份 CSV 两行单据号相同、金额不同：后端按 source_id 合并断言，两个原值收在
 // 同一来源条目的 values 里。对象页必须逐个展示两个原值（W1 补审）；定位按来源
 // 整组展示，不把行号声称成某个原值的定位（W2 补审）。
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入一份两行单据号相同金额不同的发票并核对原值');
 await page.getByLabel('选择材料').setInputFiles({name:'发票.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount,currency,issuer\nINV-105,1250,CNY,华信办公\nINV-105,2510,CNY,华信办公\n')});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitProbed(page);
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-105');
 // 冲突字段当前值为空，同一来源的两个原值都可见；定位按来源整组给出（行号含表头）。
 await expect(page.getByTestId('object-amount')).toHaveText('—');
 const conflict=page.getByTestId('object-conflict-amount');
 await expect(conflict).toBeVisible();
 await expect(conflict).toContainText('发票.csv：1250');
 await expect(conflict).toContainText('发票.csv：2510');
 await expect(conflict).toContainText('发票.csv · 来源定位：第 2 行；第 3 行');
 // 不把定位标成某个原值自己的定位。
 await expect(conflict).not.toContainText('1250（');
 await expect(conflict).not.toContainText('2510（');
 // 采用第二个原值：金额立即变为 2510，视图刷新正确——徽标消失、冲突解除、
 // 纠正记录以用户决定留痕。
 await conflict.locator('.conflict-source').filter({hasText:'发票.csv：2510'}).getByRole('button',{name:'采用此值'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('2510');
 await expect(page.locator('.source-tab')).not.toContainText('项未解决');
 await expect(page.getByTestId('object-conflicts')).toHaveCount(0);
 await expect(page.getByTestId('correction-success')).toContainText('纠正已保存：金额 → 2510');
 await expect(page.getByText(/用户纠正 · 决定/).first()).toBeVisible();
});

test('同一来源的重复原值不把全部行号标成每个原值的定位',async({page})=>{
 slowTimeout(40000);
 // 三行单据号相同、金额 1250、2510、1250：后端对原值去重得 [1250, 2510]、对定位
 // 去重得 [第 2 行, 第 3 行, 第 4 行]，两者没有对应关系。页面不得声称这些行号
 // 分别对应每个原值，定位按来源整组展示（W2 补审）。
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入一份三行单据号相同金额重复的发票并核对原值');
 await page.getByLabel('选择材料').setInputFiles({name:'发票.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount,currency,issuer\nINV-105,1250,CNY,华信办公\nINV-105,2510,CNY,华信办公\nINV-105,1250,CNY,华信办公\n')});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitProbed(page);
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-105');
 await expect(page.getByTestId('object-amount')).toHaveText('—');
 const conflict=page.getByTestId('object-conflict-amount');
 await expect(conflict).toBeVisible();
 // 去重后的两个原值都可见、都可采用；来源定位整组列出三行。
 await expect(conflict).toContainText('发票.csv：1250');
 await expect(conflict).toContainText('发票.csv：2510');
 await expect(conflict).toContainText('发票.csv · 来源定位：第 2 行；第 3 行；第 4 行');
 await expect(conflict.locator('.conflict-source')).toHaveCount(2);
 // 任何一个原值后面都不挂括号定位。
 await expect(conflict).not.toContainText('1250（');
 await expect(conflict).not.toContainText('2510（');
 // 采用 2510 仍然可用，视图刷新正确。
 await conflict.locator('.conflict-source').filter({hasText:'发票.csv：2510'}).getByRole('button',{name:'采用此值'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('2510');
 await expect(page.getByTestId('object-conflicts')).toHaveCount(0);
 await expect(page.getByTestId('correction-success')).toContainText('纠正已保存：金额 → 2510');
});
