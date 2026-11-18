import {test,expect} from '@playwright/test';
import {slowTimeout} from './support';

// FDE-10：坏输入用中文直说、进度标红、给出下一步，不再显示「识别与探查已完成」。
test('空文件用中文直说并标红进度',async({page})=>{
 slowTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入空文件并核对坏输入提示');
 await page.getByLabel('选择材料').setInputFiles({name:'空文件.csv',mimeType:'text/csv',buffer:Buffer.alloc(0)});
 await page.getByRole('button',{name:'开始接入'}).click();
 // 来源面板直说原因与下一步，不出现内部代码或来源哈希。
 await expect(page.getByTestId('source-problem')).toContainText('文件是空的，没有可读取的内容');
 await expect(page.getByTestId('source-problem')).toContainText('下一步：请更换文件后新建接入');
 // 进度条标红：识别与探查一步显示失败，副标题不再宣称已完成。
 await expect(page.locator('.step.failed')).toContainText('识别与探查');
 await expect(page.getByText('识别与探查已完成')).toHaveCount(0);
 // 待核对清单点出材料名，而不是内部来源哈希与英文代码。
 await expect(page.getByTestId('mapping-issues')).toContainText('空文件.csv · 材料读取失败');
 await expect(page.getByTestId('mapping-issues')).not.toContainText('intake.probe_failed');
});

test('伪装成 Excel 的文本文件直说不是有效的 Excel',async({page})=>{
 slowTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入伪 Excel 并核对坏输入提示');
 await page.getByLabel('选择材料').setInputFiles({name:'报表.xlsx',
  mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer:Buffer.from('这只是一个普通文本文件，不是 Excel。','utf8')});
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByTestId('source-problem')).toContainText('不是有效的 Excel 文件');
 await expect(page.locator('.step.failed')).toContainText('识别与探查');
 await expect(page.getByText('识别与探查已完成')).toHaveCount(0);
 // 原始报错收进默认折叠的「技术详情」：不直接展示，展开后也不含本机绝对路径。
 const tech=page.getByTestId('tech-detail');
 await expect(tech).toHaveCount(1);
 await expect(tech).not.toHaveAttribute('open');
 await expect(tech.locator('pre')).toBeHidden();
 await tech.locator('summary').click();
 await expect(tech.locator('pre')).toBeVisible();
 await expect(tech.locator('pre')).not.toContainText(/\/Users\/|\/tmp\/|\/var\//);
 // 展开前后，说明区本体都不出现英文原文。
 await expect(page.getByTestId('source-problem')).toContainText('下一步：请更换文件后新建接入');
});

test('只有表头的文件直说没有数据行',async({page})=>{
 slowTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入只有表头的文件并核对坏输入提示');
 await page.getByLabel('选择材料').setInputFiles({name:'只有表头.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount,currency,issuer\n')});
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByTestId('source-problem')).toContainText('只有表头，没有数据行');
 await expect(page.locator('.step.failed')).toContainText('识别与探查');
 await expect(page.getByText('识别与探查已完成')).toHaveCount(0);
});
