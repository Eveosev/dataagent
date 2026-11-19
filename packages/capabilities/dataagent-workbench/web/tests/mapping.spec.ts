import {test,expect} from '@playwright/test';
import path from 'node:path';
import {awaitProbed,pinBuiltinOntology} from './support';

test('文件探查、映射试算、刷新恢复和保存',async({page})=>{
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票，金额 amount_minor 以分为单位');
 await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.csv'));
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await awaitProbed(page);
 await page.getByLabel('金额 来源字段').selectOption('amount_minor');
 await page.getByLabel('金额 转换方式').selectOption('minor_to_major');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 // 对象预览属性名与字段详情用统一中文标签（W1 补审），不显示裸属性名或英文「Ontology 值」。
 await expect(page.locator('.object-values dt')).toHaveText(['单据编号','金额','币种','开票方']);
 await expect(page.getByText('本体值')).toBeVisible();
 await page.screenshot({path:process.env.DATAAGENT_SCREENSHOT || 'test-results/mapping-live.png',fullPage:true});
 await page.reload();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'保存接入',exact:true}).click();
 await expect(page.getByText('接入已保存')).toBeVisible();
});

test('PDF 来源定位、金额转换与发布后查看', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('接入目标').fill('接入文本发票，金额以分为单位');
  await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoice.pdf'));
  await pinBuiltinOntology(page);
  await page.getByRole('button', {name: '开始接入'}).click();
  await awaitProbed(page);
  await page.getByLabel('金额 来源字段').selectOption('amount_minor');
  await page.getByLabel('金额 转换方式').selectOption('minor_to_major');
  await page.getByRole('button', {name: '生成映射预览'}).click();
  await expect(page.getByTestId('preview-amount')).toHaveText('1260');
  await expect(page.getByRole('img', {name: '原始材料第 1 页'})).toBeVisible();
  await expect(page.getByLabel('来源高亮')).toBeVisible();
  await page.getByText('查看文本与精确位置').click();
  await expect(page.locator('mark')).toHaveText('126000');
  await page.getByRole('button', {name: '保存接入', exact: true}).click();
  await expect(page.getByText('接入已保存')).toBeVisible();
  await expect(page.getByLabel('金额 来源字段')).toBeDisabled();
});

test('两份材料分别映射并归并为同一对象', async ({page}) => {
  await page.goto('/');
  await page.getByLabel('接入目标').fill('用两份材料核对同一合成发票');
  await page.getByLabel('选择材料').setInputFiles([
    {name: 'invoice.csv', mimeType: 'text/csv', buffer: Buffer.from('number,amount_minor,currency\nINV-001,126000,CNY\nINV-002,90000,CNY\n')},
    {name: 'invoice.json', mimeType: 'application/json', buffer: Buffer.from('[{"code":"INV-002","total":"900","currency":"CNY"},{"code":"INV-001","total":"1260","currency":"CNY"}]')},
  ]);
  await pinBuiltinOntology(page);
  await page.getByRole('button', {name: '开始接入'}).click();
  await awaitProbed(page);
  await page.getByLabel('金额 来源字段').selectOption('amount_minor');
  await page.getByLabel('金额 转换方式').selectOption('minor_to_major');
  await page.getByRole('button', {name: 'invoice.json'}).click();
  await page.getByLabel('单据编号 来源字段').selectOption('/code');
  await page.getByLabel('金额 来源字段').selectOption('/total');
  await page.getByLabel('币种 来源字段').selectOption('/currency');
  await page.getByRole('button', {name: '生成映射预览'}).click();
  await expect(page.getByText('2 个对象')).toBeVisible();
  await page.getByRole('button', {name: '金额', exact: true}).click();
  await expect(page.getByTestId('preview-amount')).toHaveText('1260');
  await expect(page.getByText('/1/total', {exact: true})).toBeVisible();
  await expect(page.locator('.selected-source-row .selected-cell')).toHaveText('1260');
  await page.getByRole('button', {name: 'invoice.csv'}).click();
  await expect(page.getByLabel('金额 来源字段')).toHaveValue('amount_minor');
  await page.getByRole('button', {name: '保存接入', exact: true}).click();
  await expect(page.getByText('接入已保存')).toBeVisible();
});

test('轮询期间保留本地编辑的基准修订', async ({page, context}) => {
  await page.goto('/');
  await page.getByLabel('接入目标').fill('并发审核同一份发票');
  await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.csv'));
  await pinBuiltinOntology(page);
  await page.getByRole('button', {name: '开始接入'}).click();
  await awaitProbed(page);
  await page.getByLabel('金额 来源字段').selectOption('amount_minor');
  await expect(page.getByText('草稿已保存')).toBeVisible();
  const second = await context.newPage();
  await second.goto(page.url());
  await expect(second.getByLabel('金额 来源字段')).toHaveValue('amount_minor');
  await second.getByLabel('金额 转换方式').selectOption('integer');
  await expect(second.getByText('草稿已保存')).toBeVisible();
  await page.waitForResponse(response => response.url().endsWith('/view') && response.ok());
  await page.getByLabel('金额 转换方式').selectOption('minor_to_major');
  await expect(page.getByRole('alert')).toContainText('当前编辑已保留');
  await second.reload();
  await expect(second.getByLabel('金额 转换方式')).toHaveValue('integer');
});
