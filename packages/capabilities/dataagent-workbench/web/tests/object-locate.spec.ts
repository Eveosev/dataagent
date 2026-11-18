import {test,expect} from '@playwright/test';
import path from 'node:path';

test('SQLite 对象值的来源定位显示表与主键',async({page})=>{
 test.setTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入 SQLite 发票库并核对来源定位');
 await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/cross-source/samples/ledger.db'));
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 // 数据库定位是「表 / 主键」的可读格式，不再是内部对象。
 await expect(page.getByText('ledger.db · 表 invoice · 主键 id = 1').first()).toBeVisible();
 await expect(page.getByText('[object Object]')).toHaveCount(0);
 // 选中金额后左侧来源表定位到该记录。
 await page.getByRole('button',{name:'amount',exact:true}).click();
 await expect(page.locator('.selected-source-row .selected-cell').first()).toHaveText('1260');
});

const pagedCsv=Buffer.from('number,amount_minor,currency\nINV-001,126000,CNY\nINV-002,90000,CNY\nINV-003,75000,CNY\n');

async function openPagedObjectPage(page:import('@playwright/test').Page,mode:'with'|'without'|'mismatch'){
 // 把 CSV 来源改写成 REST 分页形态：同一 pointer 每页重复（/items/0、/items/1），页序号是
 // 区分记录的唯一信息。with/without 模拟 F1 前后的两种数据；mismatch 制造混合数据——
 // 锚点页码陈旧（全部停在第 1 页），证据页码正常推进，页码明确但不匹配。
 await page.route('**/api/sessions/*/objects',async route=>{
  const response=await route.fetch();
  const body=await response.json();
  const anchorPage=(row:number)=>mode==='without'?undefined:mode==='mismatch'?1:Math.floor(row/2)+1;
  const evidencePage=(row:number)=>mode==='without'?undefined:Math.floor(row/2)+1;
  const toRest=(row:number,field:string,page?:number)=>({kind:'json_pointer',pointer:`/items/${row%2}/${field}`,
   ...(page!==undefined?{page}:{})});
  for(const source of body.sources||[]){
   if(!source.anchors)continue;
   for(const [key,anchors] of Object.entries(source.anchors)){
    const dot=key.indexOf('.');
    const row=Number(key.slice(0,dot)),field=key.slice(dot+1);
    source.anchors[key]=anchors.map((anchor:Record<string,unknown>)=>({...anchor,selector:toRest(row,field,anchorPage(row))}));
   }
  }
  for(const object of body.objects||[]){
   for(const entries of Object.values(object.evidence||{})){
    for(const evidence of entries){
     if(evidence.selector?.kind==='record_key'&&typeof evidence.selector.keys?.row==='number'){
      const row=evidence.selector.keys.row-2;
      evidence.selector=toRest(row,String(evidence.selector.field),evidencePage(row));
     }
    }
   }
  }
  await route.fulfill({response,json:body});
 });
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入 REST 分页发票并核对高亮行');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',buffer:pagedCsv});
 await page.getByRole('button',{name:'开始接入'}).click();
 await page.getByText('识别与探查已完成').waitFor();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
}

test('REST 分页记录按页序号定位到正确来源行',async({page})=>{
 test.setTimeout(40000);
 await openPagedObjectPage(page,'with');
 // INV-003 在第 2 页 /items/0，与第 1 页的 INV-001 同 pointer，只能靠页序号区分。
 await page.getByRole('button',{name:'INV-003'}).click();
 await page.getByRole('button',{name:'amount',exact:true}).click();
 await expect(page.getByText('invoice.csv · 第 2 页 · /items/0/amount_minor').first()).toBeVisible();
 await expect(page.locator('.selected-source-row .selected-cell').first()).toHaveText('75000');
});

test('selector 无页序号时退回旧逻辑命中第一条来源记录',async({page})=>{
 test.setTimeout(40000);
 await openPagedObjectPage(page,'without');
 await page.getByRole('button',{name:'INV-003'}).click();
 await page.getByRole('button',{name:'amount',exact:true}).click();
 // 旧逻辑只比对 selector：同 pointer 的第一条（INV-001）被高亮，定位不带页码。
 await expect(page.getByText('invoice.csv · /items/0/amount_minor').first()).toBeVisible();
 await expect(page.locator('.selected-source-row .selected-cell').first()).toHaveText('126000');
});

test('页码明确但不匹配时不回退到其他页的同名 pointer',async({page})=>{
 test.setTimeout(40000);
 await openPagedObjectPage(page,'mismatch');
 await page.getByRole('button',{name:'INV-003'}).click();
 await page.getByRole('button',{name:'amount',exact:true}).click();
 // 证据是第 2 页，锚点全部停在第 1 页：定位仍显示证据页码，但不高亮任何来源行。
 await expect(page.getByText('invoice.csv · 第 2 页 · /items/0/amount_minor').first()).toBeVisible();
 await expect(page.locator('.selected-source-row')).toHaveCount(0);
});

test('纠正后必填属性未解决时提示为中文',async({page})=>{
 test.setTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对纠正提示');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount_minor,currency\nINV-001,126000,CNY\n')});
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 // currency 不映射：纠正金额后必填属性仍未解决，重验被拦。
 await page.getByLabel('currency 来源字段').selectOption('');
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await page.getByLabel('纠正的属性').selectOption('amount');
 await page.getByLabel('纠正后的值').fill('1250');
 await page.getByLabel('修改原因').fill('用户核对金额');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByRole('alert')).toContainText('必填属性仍未解决');
 await expect(page.getByRole('alert')).not.toContainText('required property');
});

test('纠正后的值显示用户纠正来源而不是内部路径',async({page})=>{
 test.setTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对纠正来源');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount_minor,currency\nINV-001,126000,CNY\n')});
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await page.getByLabel('纠正的属性').selectOption('amount');
 await page.getByLabel('纠正后的值').fill('1250');
 await page.getByLabel('修改原因').fill('用户核对金额');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1250');
 await expect(page.getByText('纠正记录')).toBeVisible();
 // 来源证据补充用户纠正：显示来源名与决定定位，不显示内部 JSON 路径。
 await expect(page.getByText(/用户纠正 · 决定 [0-9a-f]{12}…/).first()).toBeVisible();
 await expect(page.getByText('/decision/changes/value')).toHaveCount(0);
 await expect(page.getByText('invoice.csv · 来源行 2').first()).toBeVisible();
});

test('纠正无原始证据的属性时左侧显示决定定位且不高亮来源行',async({page})=>{
 test.setTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对无证据属性的纠正');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount_minor,currency\nINV-001,126000,CNY\n')});
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 // issuer 未映射也没有原始证据：纠正后证据只有审核决定本身。
 await page.getByLabel('纠正的属性').selectOption('issuer');
 await page.getByLabel('纠正后的值').fill('华信办公');
 await page.getByLabel('修改原因').fill('用户补充开票方');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByTestId('object-issuer')).toHaveText('华信办公');
 // 左侧来源定位显示决定定位，不显示内部 JSON 路径，也不高亮任何来源行。
 await expect(page.locator('.source-viewer .source-location')).toContainText('用户纠正 · 决定 ');
 await expect(page.getByText('/decision/changes/value')).toHaveCount(0);
 await expect(page.locator('.selected-source-row')).toHaveCount(0);
 // 证据列同样显示用户纠正来源。
 await expect(page.getByText(/用户纠正 · 决定 [0-9a-f]{12}…/).first()).toBeVisible();
});

test('断网时错误提示为中文',async({page})=>{
 test.setTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并核对断网提示');
 await page.getByLabel('选择材料').setInputFiles({name:'invoice.csv',mimeType:'text/csv',
  buffer:Buffer.from('number,amount_minor,currency\nINV-001,126000,CNY\n')});
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 // 断网后对象页轮询失败：红条是中文网络提示，不是原始英文报错。
 await page.context().setOffline(true);
 await expect(page.getByRole('alert')).toContainText('网络连接失败，请稍后重试');
 await expect(page.getByRole('alert')).not.toContainText('Failed to fetch');
 await page.context().setOffline(false);
});
