import {test,expect} from '@playwright/test';
import path from 'node:path';
import {readFileSync,writeFileSync} from 'node:fs';

function sessionId(page:{url():string},key:string){
 return new URL(page.url()).hash.match(new RegExp(key+'=([0-9a-f]+)'))![1];
}

test('对象页完成当前值纠正、映射修订与本体草案',async({page})=>{
 test.setTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入发票并在对象页核对');
 await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.csv'));
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByLabel('amount 转换方式').selectOption('minor_to_major');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 await expect(page.getByTestId('object-amount')).toHaveText('1260');
 // 当前值纠正：只更新本对象并重验，保留来源原值。
 await page.getByLabel('纠正的属性').selectOption('amount');
 // 切换对象会清空编辑，前一对象的纠正不会写到当前对象。
 await page.getByLabel('纠正后的值').fill('1250');
 await page.getByRole('button',{name:/INV-002/}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-002');
 await expect(page.getByLabel('纠正后的值')).toHaveValue('');
 await page.getByRole('button',{name:/INV-001/}).click();
 await expect(page.getByTestId('object-number')).toHaveText('INV-001');
 await page.getByLabel('纠正后的值').fill('1250');
 await page.getByLabel('修改原因').fill('用户核对金额');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1250');
 await expect(page.getByText('纠正记录')).toBeVisible();
 await expect(page.getByText('amount → 1250')).toBeVisible();
 // 映射修订：回到映射页改绑定并生成新预览，同类输入重跑。
 await page.getByRole('radio',{name:'修改这类来源的映射'}).check();
 await page.getByRole('button',{name:'去映射页修订'}).click();
 await page.getByLabel('amount 转换方式').selectOption('integer');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 // 映射修订改变来源值后，纠正值仍生效，但必须把映射新算得的值和采用操作摆出来。
 await expect(page.getByTestId('preview-amount')).toHaveText('1250');
 await expect(page.getByTestId('mapping-correction-hint')).toContainText('映射已变化，纠正值仍生效；映射新算得的值为 126000');
 await page.getByRole('button',{name:'采用新映射值'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('126000');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('126000');
 await page.getByRole('radio',{name:'修改这类来源的映射'}).check();
 await expect(page.getByText(/:mapping@2/)).toBeVisible();
 // 本体草案：只登记草案，正式本体不改修订。
 await page.getByRole('radio',{name:'提出本体草案'}).check();
 await page.getByLabel('建议新增的属性名').fill('issuer_type');
 await page.getByLabel('值类型').selectOption('string');
 await page.getByLabel('修改原因').fill('补充开票方类型');
 await page.getByRole('button',{name:'提交本体草案'}).click();
 await expect(page.getByText('本体草案待审核')).toBeVisible();
 await expect(page.getByText('正式本体仍为 procurement@1，草案未生效')).toBeVisible();
 await expect(page.getByTestId('object-amount')).toHaveText('126000');
});

test('采用新映射值后保存只发布最新金额',async({page,request})=>{
 test.setTimeout(40000);
 // 独立的字段指纹，避免保存的映射被其他用例复用而改变它们的默认转换。
 const csv=test.info().outputPath('adopt-save.csv');
 writeFileSync(csv,'number,amount_minor,currency,batch_ref\nINV-901,126000,CNY,B-901\n');
 await page.goto('/');
 await page.getByLabel('接入目标').fill('采用新映射值并保存');
 await page.getByLabel('选择材料').setInputFiles(csv);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByLabel('amount 转换方式').selectOption('minor_to_major');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await page.getByLabel('纠正的属性').selectOption('amount');
 await page.getByLabel('纠正后的值').fill('1250');
 await page.getByLabel('修改原因').fill('用户核对金额');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1250');
 await page.getByRole('radio',{name:'修改这类来源的映射'}).check();
 await page.getByRole('button',{name:'去映射页修订'}).click();
 await page.getByLabel('amount 转换方式').selectOption('integer');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1250');
 await page.getByRole('button',{name:'采用新映射值'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('126000');
 const sid=sessionId(page,'session');
 await page.getByRole('button',{name:'保存接入',exact:true}).click();
 await expect(page.getByText('接入已保存')).toBeVisible();
 const saved=await (await request.get(`/api/sessions/${sid}/objects`)).json();
 expect(saved.objects[0].values.amount).toBe('126000');
 expect(saved.corrections.filter((c:{property:string})=>c.property==='amount')).toHaveLength(1);
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('126000');
});

async function openObjectPageWithPreview(page:import('@playwright/test').Page){
 await page.goto('/');
 await page.getByLabel('接入目标').fill('并发核对同一份发票');
 await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.csv'));
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByLabel('amount 转换方式').selectOption('minor_to_major');
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('1260');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1260');
 await page.getByLabel('纠正的属性').selectOption('amount');
}

async function chatSideCorrection(request:import('@playwright/test').APIRequestContext,sid:string){
 const view=await (await request.get(`/api/sessions/${sid}/objects`)).json();
 const chat=await request.post(`/api/sessions/${sid}/review`,{data:{expected_revision:view.session.revision,
  decision:{preview_ref:view.preview_ref,target_scope:'instance',decision:'save',changes:{
   entity_id:view.objects[0].id,property:'currency',value:'USD',reason:'聊天侧核对'}}}});
 expect(chat.ok()).toBeTruthy();
}

test('聊天与页面并发修改同一任务时保留编辑并拒绝过期决定',async({page,request})=>{
 test.setTimeout(40000);
 await openObjectPageWithPreview(page);
 // 页面开始编辑，基准修订冻结。
 await page.getByLabel('纠正后的值').fill('1250');
 const sid=sessionId(page,'object');
 await chatSideCorrection(request,sid);
 // 页面的过期决定被拒绝，编辑保留。
 await page.getByLabel('修改原因').fill('页面核对金额');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByRole('alert')).toContainText('当前编辑已保留');
 await expect(page.getByLabel('纠正后的值')).toHaveValue('1250');
 // 冲突期间提交入口被替换为显式核对，立即再点无法用过期编辑换新修订提交。
 await expect(page.getByRole('button',{name:'保存当前值并校验'})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'已核对，重新提交'})).toBeVisible();
 // 按提示重新载入，本地编辑恢复后可以再提交。
 await page.reload();
 await expect(page.getByTestId('object-amount')).toHaveText('1260');
 await expect(page.getByLabel('纠正后的值')).toHaveValue('1250');
 await expect(page.getByLabel('修改原因')).toHaveValue('页面核对金额');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1250');
 await expect(page.getByTestId('object-currency')).toHaveText('USD');
});

test('冲突后在页面上显式核对才能重新提交',async({page,request})=>{
 test.setTimeout(40000);
 await openObjectPageWithPreview(page);
 await page.getByLabel('纠正后的值').fill('1250');
 const sid=sessionId(page,'object');
 await chatSideCorrection(request,sid);
 await page.getByLabel('修改原因').fill('页面核对金额');
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByRole('alert')).toContainText('当前编辑已保留');
 // 核对最新值后显式确认，同一编辑以最新修订重新提交。
 await expect(page.getByTestId('object-currency')).toHaveText('USD');
 await page.getByRole('button',{name:'已核对，重新提交'}).click();
 await page.getByRole('button',{name:'保存当前值并校验'}).click();
 await expect(page.getByTestId('object-amount')).toHaveText('1250');
 await expect(page.getByTestId('object-currency')).toHaveText('USD');
});

test('准备重启恢复的任务状态',async({page})=>{
 const stateFile=process.env.DATAAGENT_TEST_STATE_FILE;
 test.skip(!stateFile||process.env.DATAAGENT_TEST_STAGE==='recovery','仅在 verify_browser 两阶段运行时执行');
 test.setTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('为重启恢复准备任务');
 await page.getByLabel('选择材料').setInputFiles(path.resolve('../../dataagent-scenarios/fixtures/intake/invoices.csv'));
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByLabel('currency 来源字段').selectOption('');
 await page.getByLabel('amount 来源字段').selectOption('amount_minor');
 await page.getByLabel('amount 转换方式').selectOption('integer');
 await expect(page.getByText('草稿已保存')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('preview-amount')).toHaveText('126000');
 await expect(page.getByText('3 项待核对')).toBeVisible();
 const {writeFileSync}=await import('node:fs');
 writeFileSync(stateFile!,JSON.stringify({session_id:sessionId(page,'session')}));
});

test('服务重启后恢复材料、草稿与未解决项',async({page})=>{
 test.skip(process.env.DATAAGENT_TEST_STAGE!=='recovery','仅在重启恢复阶段执行');
 const state=JSON.parse(readFileSync(process.env.DATAAGENT_TEST_STATE_FILE!,'utf8'));
 await page.goto('/#object='+state.session_id);
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
 // 材料与对象值恢复。
 await expect(page.getByTestId('object-amount')).toHaveText('126000');
 await expect(page.locator('.source-table')).toBeVisible();
 await expect(page.getByText('INV-001').first()).toBeVisible();
 // 未解决项恢复。
 await expect(page.getByText('未解决').first()).toBeVisible();
 await expect(page.getByText('3 项待核对')).toBeVisible();
 // 草稿恢复。
 await page.getByRole('button',{name:'返回映射页'}).click();
 await expect(page.getByLabel('amount 转换方式')).toHaveValue('integer');
});
