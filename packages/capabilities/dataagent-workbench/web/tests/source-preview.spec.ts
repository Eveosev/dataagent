import {test,expect} from '@playwright/test';
import path from 'node:path';

test('CSV 对象值的来源定位',async({page})=>{
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对来源行');
 await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.csv'));
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByLabel('amount 转换方式').selectOption('minor_to_major');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1260');
 // 每个值都带来源定位：文件与来源行。
 await expect(page.getByText('invoices.csv · 来源行 2').first()).toBeVisible();
 // 切换对象后定位到另一条来源记录。
 await page.getByRole('button',{name:/INV-002/}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-002');
 await expect(page.getByText('invoices.csv · 来源行 3').first()).toBeVisible();
 // 选择属性后左侧来源表定位到该行。
 await page.getByRole('button',{name:'amount',exact:true}).click();
 await expect(page.locator('.selected-source-row .selected-cell')).toHaveText('90000');
});

test('PDF 对象值定位到页面与原文',async({page})=>{
 test.setTimeout(30000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入文本发票并核对页面定位');
 await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoice.pdf'));
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByLabel('amount 转换方式').selectOption('minor_to_major');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1260');
 await expect(page.getByText('invoice.pdf · 第 1 页').first()).toBeVisible();
 await page.getByRole('button',{name:'amount',exact:true}).click();
 await expect(page.getByRole('img',{name:'原始材料第 1 页'})).toBeVisible();
 await expect(page.getByLabel('来源高亮')).toBeVisible();
 await page.getByText('查看文本与精确位置').click();
 await expect(page.locator('mark')).toHaveText('126000');
});
