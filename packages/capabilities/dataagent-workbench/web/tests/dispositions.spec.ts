import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {humanDetail} from '../src/client';
import {pinBuiltinOntology,slowTimeout} from './support';

// G2 处置入口 + FDE-11 可读性 + FDE2-06 按问题类型给处置：真实数据行的缺键、
// 转换失败不再给「排除表头行」（只有疑似表头或无关行才给排除）；类型转换失败
// 给「去对象页纠正当前值」和「修改映射转换（重新提案）」；同根因合并计数。
//
// 处置提交走真实后端路由 POST /api/sessions/<id>/dispositions 与 /review 的
// allow_partial（B1 已挂出）：请求与响应契约从真实网络交互里核对，不拦截；
// 视图刷新（处置使预览失效、部分保存使接入落盘）用页面状态断言。
// 原始异常只保留在折叠「详情」，列表摘要只能是中文（FDE2-06）。
test('异常原文只进详情，列表摘要用中文',()=>{
 const raw="Invalid isoformat string: 'not-a-date'";
 expect(humanDetail(raw)).toEqual({summary:'日期时间格式无法解析',detail:raw});
});

const disposalUrl=/\/api\/sessions\/[^/]+\/dispositions$/;
const reviewUrl=/\/api\/sessions\/[^/]+\/review$/;
const python=process.env.DATAAGENT_TEST_PYTHON;
const missingNumberCsv=Buffer.from('number,amount,currency,issuer\nINV-001,1260,CNY,华信办公\n,900,CNY,北明科技\n');
// 第 2 行把表头原样重复了一遍：探查会把它当数据记录，处置时才算「疑似表头行」。
const repeatedHeaderCsv=Buffer.from('number,amount,currency,issuer\nnumber,amount,currency,issuer\nINV-001,1260,CNY,华信办公\n');

async function openObjectPage(page:import('@playwright/test').Page,files:Parameters<import('@playwright/test').Page['setInputFiles']>[1],missingKey=false){
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入缺键记录并核对处置入口');
 await page.getByLabel('选择材料').setInputFiles(files);
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 // 预览问题用中文说明并点名对象，不再显示内部代码（FDE2-11）。
 await expect(page.getByTestId('mapping-issues')).not.toContainText('ontology.');
 if(missingKey)await expect(page.getByTestId('mapping-issues')).toContainText('缺少身份字段值，无法确定对象');
 await page.getByRole('button',{name:'打开对象页'}).click();
 await expect(page.getByRole('heading',{name:'核对业务对象'})).toBeVisible();
}

test('缺键的真实数据行不给「排除表头行」处置',async({page})=>{
 slowTimeout(40000);
 await openObjectPage(page,{name:'发票.csv',mimeType:'text/csv',buffer:missingNumberCsv},true);
 // FDE-11：缺键对象不显示 candidate:<哈希>，改用来源描述点名（第 3 行是文件里的原始行号）。
 await expect(page.locator('.source-tab').filter({hasText:'来源行 3'})).toContainText('发票.csv · 来源行 3（缺少单据编号）');
 await expect(page.getByText(/candidate:/)).toHaveCount(0);
 // FDE-11：徽标与列名是中文。
 await expect(page.locator('.mapping-panel .panel-heading .badge')).toContainText('采购单据');
 await expect(page.locator('.detail-panel .panel-heading .badge')).toContainText('未核对');
 await expect(page.locator('.mapping-table thead th').first()).toHaveText('本体属性');
 // FDE2-06：这是真实数据行（900 / CNY / 北明科技），不是表头——不给「排除」，
 // 让用户去补单号或部分保存，而不是把真数据排掉（问题文案沿用 FDE2-11 的
 // 通用说法「缺少身份字段值」）。
 const issue=page.getByTestId('pending-issue').filter({hasText:'缺少身份字段值'});
 await expect(issue).toContainText('阻断');
 await expect(issue.getByTestId('disposal-option')).toHaveCount(0);
 await expect(issue).not.toContainText('排除表头行或明显无关的记录');
 // 整批被拦的出路仍在：只保存无问题对象。
 await expect(page.getByTestId('partial-save')).toBeVisible();
});

test('疑似表头行给排除处置并走真实后端',async({page})=>{
 slowTimeout(40000);
 await openObjectPage(page,{name:'发票.csv',mimeType:'text/csv',buffer:repeatedHeaderCsv});
 // 第 2 行的值就是各列列名：整行与表头相似，转换失败旁给出排除处置。
 const issue=page.getByTestId('pending-issue').filter({hasText:'值无法按目标类型转换'});
 await expect(issue).toContainText('可纠正');
 const disposal=issue.getByTestId('disposal-option');
 await expect(disposal).toContainText('排除「发票.csv」来源行 2');
 // 原因空白时不可提交。
 const reason=disposal.getByLabel(/处置原因/);
 await expect(disposal.getByRole('button',{name:'提交处置'})).toBeDisabled();
 await reason.fill('重复的表头行，不是单据');
 await expect(disposal.getByRole('button',{name:'提交处置'})).toBeEnabled();
 const [response]=await Promise.all([
  postResponse(page,disposalUrl),
  disposal.getByRole('button',{name:'提交处置'}).click(),
 ]);
 expect(response.status()).toBe(200);
 const request=response.request().postDataJSON() as Record<string,unknown>;
 const body=await response.json();
 // 提交的是可审计的处置契约：动作、来源、记录与原因齐全，修订带校验。
 expect(request).toMatchObject({action:'exclude_record',source_id:expect.any(String),
  record:0,reason:'重复的表头行，不是单据'});
 expect(String(request.expected_revision)).toMatch(/^[0-9]+$/);
 // 真实后端记录了处置审计并使预览失效。
 expect(body.entry).toMatchObject({action:'exclude_record',record:0,
  reason:'重复的表头行，不是单据',source_id:expect.any(String)});
 expect(String(body.session_revision)).toMatch(/^[0-9]+$/);
 await expect(page.getByTestId('correction-success')).toContainText('处置已记录');
 // 视图刷新：预览失效后对象区回到空态，阻断问题不再挂着。
 await expect(page.getByText('生成映射预览后，在这里查看对象。')).toBeVisible();
 await expect(page.getByTestId('pending-issues')).toHaveCount(0);
});

test('只保存无问题对象需要填写原因并走真实后端 allow_partial',async({page})=>{
 slowTimeout(40000);
 await openObjectPage(page,{name:'发票.csv',mimeType:'text/csv',buffer:missingNumberCsv});
 const partial=page.getByTestId('partial-save');
 await expect(partial).toBeVisible();
 await expect(partial).toContainText('只保存无问题对象');
 const reason=partial.getByLabel('部分保存原因');
 await expect(partial.getByRole('button',{name:'只保存无问题对象'})).toBeDisabled();
 await reason.fill('先保存有单号的对象，缺键记录单独处理');
 await expect(partial.getByRole('button',{name:'只保存无问题对象'})).toBeEnabled();
 const [response]=await Promise.all([
  postResponse(page,reviewUrl),
  partial.getByRole('button',{name:'只保存无问题对象'}).click(),
 ]);
 expect(response.status()).toBe(200);
 const request=response.request().postDataJSON() as Record<string,unknown>;
 const body=await response.json();
 // 提交契约：allow_partial 与原因走顶层，决定范围是整批映射。
 expect(request).toMatchObject({allow_partial:true,reason:'先保存有单号的对象，缺键记录单独处理',
  decision:{target_scope:'mapping',decision:'save'}});
 // 真实后端按计划放行：INV-001 保存，缺键记录挂起为未识别，无对象被挡。
 expect(body.partial).toBe(true);
 expect(body.saved).toHaveLength(1);
 expect((body.saved[0] as {values:{number?:string}}).values.number).toBe('INV-001');
 expect(body.suspended).toHaveLength(0);
 expect(body.unidentified_records).toHaveLength(1);
 await expect(page.getByTestId('correction-success')).toContainText('已按部分保存放行无阻断的对象');
 // 成功后视图刷新：接入进入已保存，对象只读。
 await expect(page.getByText('接入已保存，对象为只读。')).toBeVisible();
});

test('空白页来源可标记分区不适用',async({page})=>{
 slowTimeout(40000);
 // mixed.pdf 第 2 页是空白页：来源未完整读取（阻断）旁给出标记分区不适用的处置。
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入混排发票并核对空白页处置');
 await page.getByLabel('选择材料').setInputFiles({name:'mixed.pdf',mimeType:'application/pdf',
  buffer:await import('node:fs').then(fs=>fs.readFileSync('../../dataagent-scenarios/fixtures/intake/mixed.pdf'))});
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await page.getByRole('button',{name:'打开对象页'}).click();
 const issue=page.getByTestId('pending-issue').filter({hasText:'来源未完整读取'});
 await expect(issue).toContainText('mixed.pdf');
 const disposal=issue.getByTestId('disposal-option');
 await expect(disposal).toContainText('标记「mixed.pdf」分区 2 不适用');
 await expect(disposal.getByRole('button',{name:'提交处置'})).toBeDisabled();
 await disposal.getByLabel(/处置原因/).fill('第 2 页是空白页，确认不适用');
 const [response]=await Promise.all([
  postResponse(page,disposalUrl),
  disposal.getByRole('button',{name:'提交处置'}).click(),
 ]);
 expect(response.status()).toBe(200);
 const request=response.request().postDataJSON() as Record<string,unknown>;
 const body=await response.json();
 expect(request).toMatchObject({action:'partition_not_applicable',partition:2,
  reason:'第 2 页是空白页，确认不适用'});
 expect(body.entry).toMatchObject({action:'partition_not_applicable',partition:2,
  reason:'第 2 页是空白页，确认不适用'});
 await expect(page.getByTestId('correction-success')).toContainText('处置已记录');
 // 视图刷新：预览失效后对象区回到空态。
 await expect(page.getByText('生成映射预览后，在这里查看对象。')).toBeVisible();
});

// 用系统临时目录里的 xlsx 复现 FDE2-02/FDE2-06：日期列被错绑为 decimal。
// xlsx 用 Python 标准库 zipfile 手工打包（t="d" 日期单元格，openpyxl 读回
// datetime → ISO 字符串），不依赖工作台环境里的第三方包。
function buildDateColumnXlsx():string{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'dataagent-xlsx-'));
 const file=path.join(dir,'报销明细.xlsx');
 execFileSync(python!,['-c',`import sys,zipfile
rows=[('number','amount','currency')]
for i in range(5):rows.append((f'BX-2026-000{i+1}',f'2026-03-0{i+2}T00:00:00','CNY'))
def cell(ref,kind,value):
    if kind=='d':return f'<c r="{ref}" t="d"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
sheet=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
for r,row in enumerate(rows,1):
    parts=[]
    for col,value in zip('ABC',row):
        kind='d' if col=='B' and r>1 else 's'
        parts.append(cell(f'{col}{r}',kind,value))
    sheet.append(f'<row r="{r}">'+''.join(parts)+'</row>')
sheet.append('</sheetData></worksheet>')
with zipfile.ZipFile(sys.argv[1],'w') as z:
    z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
     '<Default Extension="xml" ContentType="application/xml"/>'
     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
     '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
     '</Types>')
    z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
     '</Relationships>')
    z.writestr('xl/workbook.xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
     'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
     '<sheets><sheet name="明细" sheetId="1" r:id="rId1"/></sheets></workbook>')
    z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
     '</Relationships>')
    z.writestr('xl/worksheets/sheet1.xml',''.join(sheet))
`,file]);
 return file;
}

test('xlsx 日期列错绑为 decimal：按根因合并计数，处置按类型给',async({page})=>{
 test.skip(!python,'run scripts/verify_browser.py to share the python interpreter');
 slowTimeout(40000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入报销明细并核对日期列的处置');
 await page.getByLabel('选择材料').setInputFiles(buildDateColumnXlsx());
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 // 默认绑定把日期列绑到金额（decimal）：5 行全部转换失败。
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByText('1 项待核对')).toBeVisible();
 await expect(page.getByText('涉及 5 行')).toBeVisible();
 await page.getByRole('button',{name:'打开对象页'}).click();
 // FDE2-06：同一列 5 行转换失败是 1 条根因、影响 5 行（不是 5×2 项），
 // 阻断数按根因数计，整批保存仍被这一条根因拦下。
 await expect(page.getByTestId('pending-issues')).toContainText('1 项待核对');
 await expect(page.getByTestId('pending-issues')).toContainText('涉及 5 行');
 await expect(page.getByTestId('pending-issues')).toContainText('阻断 1 项');
 // 同根因合并成一条「金额 × 5 行」，说明全中文，原始英文异常不出现。
 const group=page.getByTestId('pending-issue').filter({hasText:'× 5 行'});
 await expect(group).toHaveCount(1);
 await expect(group).toContainText('「金额」 × 5 行 · 值无法按目标类型转换');
 expect(await group.innerText()).not.toContain('ConversionSyntax');
 expect(await page.getByTestId('pending-issues').innerText()).not.toContain('[<class');
 // 类型转换失败给两条出路，不再提供「排除表头行或明显无关的记录」。
 // 组头只负责改映射；纠正入口逐行给出，避免整组按钮只作用于第一行。
 await expect(group.getByTestId('conversion-actions')).toContainText('修改映射转换（重新提案）');
 await expect(group.getByTestId('conversion-actions')).toContainText('展开「查看各行」逐行定位纠正');
 await expect(group.getByTestId('conversion-actions')).not.toContainText('去对象页纠正');
 await expect(group.getByTestId('disposal-option')).toHaveCount(0);
 await expect(page.getByTestId('pending-issues')).not.toContainText('排除表头行');
 // 各行收进折叠详情：展开后 5 行都在，每行都有自己的「纠正当前值」入口。
 await group.getByText('查看各行',{exact:true}).click();
 const rows=group.locator('.group-rows li');
 await expect(rows).toHaveCount(5);
 await expect(rows.first()).toContainText('BX-2026-0001');
 for(const row of await rows.all())
  await expect(row.getByTestId('conversion-row-actions')).toContainText('去对象页纠正「金额」');
 // 点第二行的纠正入口：跳到对象页时选中该对象，并定位到出错字段「金额」。
 await rows.nth(1).getByRole('button',{name:'去对象页纠正「金额」'}).click();
 await expect(page.locator('.source-tab.active')).toContainText('BX-2026-0002');
 await expect(page.getByLabel('纠正的属性')).toHaveValue('amount');
 // 处置入口回到映射页修订转换（重新提案）。
 await group.getByRole('button',{name:'修改映射转换（重新提案）'}).click();
 await expect(page.getByRole('heading',{name:/核对来源与/})).toBeVisible();
 await expect(page.getByLabel('金额 来源字段')).toHaveValue('amount');
});

// FDE2-05 回归：任务里有两份材料、当前概念只映射了其中一份。处置一行后
// 重新生成预览，页面必须沿用提案固定的来源范围，不能把未映射材料也映射进
// 来（真实现场：问题 40 → 126、对象 20 → 31）。
const ledgerCsv=Buffer.from('number,amount_minor,currency\nnumber,amount_minor,currency\nINV-001,126000,CNY\nINV-002,90000,CNY\n');
const otherCsv=Buffer.from('number,amount,currency,note\nX-001,500.00,CNY,另一概念\nX-002,600.00,CNY,另一概念\nX-003,700.00,CNY,另一概念\n');

test('未映射来源在处置一行后重新生成预览时保持不映射',async({page})=>{
 test.setTimeout(60000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入两份材料但只映射其中一份');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'ledger.csv',mimeType:'text/csv',buffer:ledgerCsv},
  {name:'other.csv',mimeType:'text/csv',buffer:otherCsv},
 ]);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session')!;
 expect(sid).toBeTruthy();
 const view=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string};ontology:{id:string;revision:string};ontology_concept:string;
  profiles:{source_id:string;fields:string[];metadata:{structure_fingerprint:string}}[];
 };
 const mapped=view.profiles.find(profile=>!profile.fields.includes('note'))!;
 const other=view.profiles.find(profile=>profile.fields.includes('note'))!;
 expect(mapped&&other).toBeTruthy();
 const proposalFor=(source:typeof mapped)=>({id:'candidate',revision:'1',
  ontology_revision:`${view.ontology.id}@${view.ontology.revision}`,concept:view.ontology_concept,
  source_fingerprint:source.metadata.structure_fingerprint,
  bindings:{number:{source_field:'number'},
   amount:source.fields.includes('amount_minor')
    ?{source_field:'amount_minor',transform:'minor_to_major'}
    :{source_field:'amount'},
   currency:{source_field:'currency'}}});
 const proposal=proposalFor(mapped),otherProposal=proposalFor(other);
 // 用户此前编辑过来源 B：服务端草稿先留下 B 的绑定。随后 Agent 把范围
 // 缩窄为只含 A；缩窄提案必须同时清掉草稿里的 B，否则最终保存仍会因
 // 草稿含范围外来源而报冲突。
 const stale=await page.request.put(`/api/sessions/${sid}/draft`,{
  data:{expected_revision:view.session.revision,draft:{source_bindings:{
   [mapped.source_id]:proposal.bindings,[other.source_id]:otherProposal.bindings}}}});
 expect(stale.ok(),await stale.text()).toBeTruthy();
 const staleView=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string};draft:{source_bindings:Record<string,unknown>}};
 expect(staleView.draft.source_bindings[other.source_id]).toBeTruthy();
 // Agent 的单来源提案：只给 ledger 建映射，另一份材料留在任务里但未映射。
 const posted=await page.request.post(`/api/sessions/${sid}/source-proposals`,{
  data:{proposals:{[mapped.source_id]:proposal},expected_revision:staleView.session.revision}});
 expect(posted.ok(),await posted.text()).toBeTruthy();
 const narrowed=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{selected_versions:Record<string,string>};draft:{source_bindings:Record<string,unknown>}};
 expect(narrowed.draft.source_bindings[other.source_id]).toBeUndefined();
 expect(narrowed.session.selected_versions[`mapping:${other.source_id}`]).toBeFalsy();
 await page.reload();
 await expect(page.getByRole('button',{name:'打开对象页'})).toBeVisible();
 await page.getByRole('button',{name:'打开对象页'}).click();
 // 初始预览：ledger 的 4 条记录成对象，other 只有一条来源级问题。
 await expect(page.getByTestId('pending-issues')).toContainText('2 项待核对');
 await expect(page.getByTestId('pending-issues')).toContainText('阻断 2 项');
 const unmappedIssue=page.getByTestId('pending-issue').filter({hasText:'该来源未用于当前映射'});
 await expect(unmappedIssue).toContainText('other.csv');
 // 审核第 8 轮：对象页给出中文说明与回映射页的入口，不在这里改来源范围。
 await expect(unmappedIssue.getByTestId('include-mapping-hint'))
  .toContainText('返回映射页点「纳入映射」');
 await expect(unmappedIssue.getByRole('button',{name:'返回映射页纳入'})).toBeVisible();
 // 疑似表头行的转换失败给「排除」，处置一行并写入审计。
 const conversion=page.getByTestId('pending-issue').filter({hasText:'值无法按目标类型转换'});
 await expect(conversion.getByTestId('disposal-option')).toContainText('排除');
 await conversion.getByLabel(/处置原因/).fill('重复的表头行，不是单据');
 await conversion.getByRole('button',{name:'提交处置'}).click();
 await expect(page.getByTestId('correction-success')).toContainText('处置已记录');
 await expect(page.getByText('生成映射预览后，在这里查看对象。')).toBeVisible();
 // 重新生成预览：只映射提案覆盖的 ledger，other 仍是来源级问题，对象不膨胀。
 await page.getByRole('button',{name:'返回映射页'}).click();
 await expect(page.getByRole('heading',{name:/核对来源与/})).toBeVisible();
 const [regenerated]=await Promise.all([
  page.waitForResponse(response=>response.request().method()==='POST'&&/source-proposals$/.test(response.url())),
  page.getByRole('button',{name:'生成映射预览'}).click(),
 ]);
 expect(regenerated.status()).toBe(200);
 const body=await regenerated.json() as {instances:{values:{number?:string}}[];issues:{code?:string}[];source_revisions:Record<string,string>;mapping:{bindings:Record<string,{source_field:string;transform?:string}>}};
 expect(body.instances).toHaveLength(2);
 expect(Object.keys(body.source_revisions)).toEqual([mapped.source_id]);
 expect(body.issues.map(issue=>issue.code)).toEqual(['ontology.source_unmapped']);
 expect(body.instances.map(instance=>instance.values.number).sort()).toEqual(['INV-001','INV-002']);
 // 处置使预览失效后，重新生成仍沿用 Agent 的转换（金额按分转主币），
 // 不退回同名默认绑定——否则必填金额缺失，计数又会失真。
 expect(body.mapping.bindings.amount).toMatchObject({source_field:'amount_minor',transform:'minor_to_major'});
 await expect(page.getByLabel('金额 来源字段')).toHaveValue('amount_minor');
 await expect(page.getByTestId('mapping-issues')).toContainText('该来源未用于当前映射');
 // 未映射来源同时给出「纳入映射」入口，不再只有整源处置这一条路。
 await expect(page.getByTestId('include-mapping-option'))
  .toContainText('把「other.csv」纳入映射');
 // 来源级处置「本任务不使用该来源」：原因必填，写入审计。
 const sourceDisposal=page.getByTestId('disposal-option').filter({hasText:'本任务不使用'});
 await expect(sourceDisposal).toContainText('本任务不使用「other.csv」');
 const submit=sourceDisposal.getByRole('button',{name:'提交处置'});
 await expect(submit).toBeDisabled();
 await sourceDisposal.getByLabel(/处置原因：本任务不使用/).fill('这份材料属于另一个概念，本任务不使用');
 await expect(submit).toBeEnabled();
 const [disposed]=await Promise.all([
  page.waitForResponse(response=>response.request().method()==='POST'&&disposalUrl.test(response.url())),
  submit.click(),
 ]);
 expect(disposed.status()).toBe(200);
 const disposedBody=await disposed.json() as {entry:{action:string;source_id:string;reason:string}};
 expect(disposedBody.entry).toMatchObject({action:'ignore_source',source_id:other.source_id,
  reason:'这份材料属于另一个概念，本任务不使用'});
 // 处置后重新生成：来源级问题消失，只剩 ledger 的 2 个对象，整批可以保存。
 const [cleared]=await Promise.all([
  page.waitForResponse(response=>response.request().method()==='POST'&&/source-proposals$/.test(response.url())),
  page.getByRole('button',{name:'生成映射预览'}).click(),
 ]);
 expect(cleared.status()).toBe(200);
 const clearedBody=await cleared.json() as {instances:unknown[];issues:unknown[]};
 expect(clearedBody.issues).toEqual([]);
 expect(clearedBody.instances).toHaveLength(2);
 await expect(page.getByTestId('mapping-issues')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'保存接入'})).toBeEnabled();
 await page.getByRole('button',{name:'保存接入'}).click();
 await expect(page.getByRole('heading',{name:'接入已保存'})).toBeVisible();
 // 最终保存只含 ledger 的两个对象，未映射且已整源处置的 other 不再出现。
 const saved=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  preview:{instances:{values:{number?:string}}[]}|null};
 expect(saved.preview?.instances.map(instance=>instance.values.number).sort())
  .toEqual(['INV-001','INV-002']);
});

// 审核第 8 轮：未映射来源除了「本任务不使用」，还必须能显式「纳入映射」。
// 即使来源 B 的绑定与同名默认值完全一致（用户没改过任何字段），点一次也要
// 把它带回提案范围，而不是因为 bindingsEdited=false 被继续留在范围外。
test('未映射来源可沿用默认绑定纳入映射并重新提案',async({page})=>{
 test.setTimeout(60000);
 // 干净的两份材料：只验证「纳入映射」本身，不掺入表头行处置。
 const cleanLedger=Buffer.from('number,amount_minor,currency\nINV-001,126000,CNY\nINV-002,90000,CNY\n');
 await page.goto('/');
 await page.getByLabel('接入目标').fill('把未映射来源按默认绑定纳入映射');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'ledger.csv',mimeType:'text/csv',buffer:cleanLedger},
  {name:'other.csv',mimeType:'text/csv',buffer:otherCsv},
 ]);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session')!;
 expect(sid).toBeTruthy();
 const view=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string};ontology:{id:string;revision:string};ontology_concept:string;
  profiles:{source_id:string;fields:string[];metadata:{structure_fingerprint:string}}[];
 };
 const mapped=view.profiles.find(profile=>!profile.fields.includes('note'))!;
 const other=view.profiles.find(profile=>profile.fields.includes('note'))!;
 expect(mapped&&other).toBeTruthy();
 const proposalFor=(source:typeof mapped)=>({id:'candidate',revision:'1',
  ontology_revision:`${view.ontology.id}@${view.ontology.revision}`,concept:view.ontology_concept,
  source_fingerprint:source.metadata.structure_fingerprint,
  bindings:{number:{source_field:'number'},
   amount:source.fields.includes('amount_minor')
    ?{source_field:'amount_minor',transform:'minor_to_major'}
    :{source_field:'amount'},
   currency:{source_field:'currency'}}});
 // Agent 先只映射 ledger；other 保持未映射并产生来源级问题。
 const narrow=await page.request.post(`/api/sessions/${sid}/source-proposals`,{
  data:{proposals:{[mapped.source_id]:proposalFor(mapped)},expected_revision:view.session.revision}});
 expect(narrow.ok(),await narrow.text()).toBeTruthy();
 await page.reload();
 await expect(page.getByTestId('mapping-issues')).toContainText('该来源未用于当前映射');
 const include=page.getByTestId('include-mapping-option');
 await expect(include).toContainText('把「other.csv」纳入映射');
 await expect(include).toContainText('默认同名绑定可直接使用');
 await include.getByRole('button',{name:'纳入映射'}).click();
 await expect(page.getByTestId('mapping-correction-notice'))
  .toContainText('已将「other.csv」纳入映射范围');
 await expect(include.getByRole('button',{name:'已纳入，待生成预览'})).toBeDisabled();
 const [rebuilt]=await Promise.all([
  page.waitForResponse(response=>response.request().method()==='POST'&&/source-proposals$/.test(response.url())),
  page.getByRole('button',{name:'生成映射预览'}).click(),
 ]);
 expect(rebuilt.status()).toBe(200);
 const body=await rebuilt.json() as {instances:unknown[];issues:unknown[];
  source_revisions:Record<string,string>};
 expect(Object.keys(body.source_revisions).sort()).toEqual([mapped.source_id,other.source_id].sort());
 expect(body.instances).toHaveLength(5);
 // 第二次提案确实带上了 other，并且沿用同名默认绑定（未编辑过任何字段）。
 const posted=rebuilt.request().postDataJSON() as {
  proposals:Record<string,{bindings:Record<string,{source_field:string;transform?:string}>}>};
 const otherProposal=posted.proposals[other.source_id];
 expect(Object.keys(otherProposal.bindings).sort()).toEqual(['amount','currency','number']);
 expect(otherProposal.bindings.amount).toMatchObject({source_field:'amount'});
 expect(otherProposal.bindings.number).toMatchObject({source_field:'number'});
 expect(otherProposal.bindings.currency).toMatchObject({source_field:'currency'});
 // 纳入后来源级问题消失，网页按最新范围重建（不再有未映射来源）。
 await expect(page.getByTestId('mapping-issues')).toHaveCount(0);
 const after=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{selected_versions:Record<string,string>};preview:{issues:unknown[]}|null};
 expect(after.session.selected_versions[`mapping:${other.source_id}`]).toBeTruthy();
 expect(after.preview?.issues).toEqual([]);
});

test('前面的行级问题超过 8 条时未映射来源的纳入按钮仍可见可点',async({page})=>{
 test.setTimeout(60000);
 // 9 行的金额列全部转换失败：按根因合并是 1 条问题、影响 9 行，但逐行问题
 // 仍有 9 条。未映射来源的 source_unmapped 追加在这些行级问题之后；页面必须
 // 把来源级问题固定在最前，不能因为只展示前 8 条而藏掉「纳入映射」。
 const badLedger=Buffer.from('number,amount_minor,currency\n'
  +Array.from({length:9},(_,i)=>`INV-${String(i+1).padStart(3,'0')},not-a-number,CNY`).join('\n')+'\n');
 await page.goto('/');
 await page.getByLabel('接入目标').fill('行级问题很多时仍能纳入未映射来源');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'ledger.csv',mimeType:'text/csv',buffer:badLedger},
  {name:'other.csv',mimeType:'text/csv',buffer:otherCsv},
 ]);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session')!;
 expect(sid).toBeTruthy();
 const view=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string};ontology:{id:string;revision:string};ontology_concept:string;
  profiles:{source_id:string;fields:string[];metadata:{structure_fingerprint:string}}[];
 };
 const mapped=view.profiles.find(profile=>!profile.fields.includes('note'))!;
 const other=view.profiles.find(profile=>profile.fields.includes('note'))!;
 const proposalFor=(source:typeof mapped)=>({id:'candidate',revision:'1',
  ontology_revision:`${view.ontology.id}@${view.ontology.revision}`,concept:view.ontology_concept,
  source_fingerprint:source.metadata.structure_fingerprint,
  bindings:{number:{source_field:'number'},
   amount:{source_field:'amount_minor',transform:'minor_to_major'},
   currency:{source_field:'currency'}}});
 const narrow=await page.request.post(`/api/sessions/${sid}/source-proposals`,{
  data:{proposals:{[mapped.source_id]:proposalFor(mapped)},expected_revision:view.session.revision}});
 expect(narrow.ok(),await narrow.text()).toBeTruthy();
 await page.reload();
 // 10 条逐行问题（9 条转换失败 + 1 条未映射来源），合并为 2 条根因、9 行。
 await expect(page.getByTestId('mapping-issues').locator('li')).toHaveCount(9);
 await expect(page.getByText('2 项待核对')).toBeVisible();
 await expect(page.getByText('涉及 9 行')).toBeVisible();
 const include=page.getByTestId('include-mapping-option');
 await expect(include).toContainText(`把「other.csv」纳入映射`);
 await expect(page.getByTestId('mapping-issues').locator('li').first())
  .toContainText('该来源未用于当前映射');
 const button=include.getByRole('button',{name:'纳入映射'});
 await expect(button).toBeEnabled();
 await button.click();
 await expect(page.getByTestId('mapping-correction-notice'))
  .toContainText('已将「other.csv」纳入映射范围');
});

// FDE2-05 回归：先全量映射两份材料，再缩窄为只映射 ledger，最后在网页点
// 「生成映射预览」。网页必须按最新范围重建，不能因为历史 mapping:<来源>
// 键把已移除的另一份材料重新映射进来（对象/问题数不膨胀）。
test('全量映射后缩窄来源，网页重建不再加回已移除的来源',async({page})=>{
 test.setTimeout(60000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('先全量映射再缩窄来源');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'ledger.csv',mimeType:'text/csv',buffer:ledgerCsv},
  {name:'other.csv',mimeType:'text/csv',buffer:otherCsv},
 ]);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session')!;
 const view=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string;selected_versions:Record<string,string>};ontology:{id:string;revision:string};
  ontology_concept:string;
  profiles:{source_id:string;fields:string[];metadata:{structure_fingerprint:string}}[];
 };
 const mapped=view.profiles.find(profile=>!profile.fields.includes('note'))!;
 const other=view.profiles.find(profile=>profile.fields.includes('note'))!;
 expect(mapped&&other).toBeTruthy();
 const proposalFor=(source:typeof mapped)=>({id:'candidate',revision:'1',
  ontology_revision:`${view.ontology.id}@${view.ontology.revision}`,concept:view.ontology_concept,
  source_fingerprint:source.metadata.structure_fingerprint,
  bindings:{number:{source_field:'number'},
   amount:source.fields.includes('amount_minor')
    ?{source_field:'amount_minor',transform:'minor_to_major'}
    :{source_field:'amount'},
   currency:{source_field:'currency'}}});
 // 第一步：A、B 都提案（全量映射）。
 const full=await page.request.post(`/api/sessions/${sid}/source-proposals`,{
  data:{proposals:{[mapped.source_id]:proposalFor(mapped),[other.source_id]:proposalFor(other)},
   expected_revision:view.session.revision}});
 expect(full.ok(),await full.text()).toBeTruthy();
 const fullView=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string;selected_versions:Record<string,string>}};
 expect(fullView.session.selected_versions[`mapping:${other.source_id}`]).toBeTruthy();
 // 第二步：Agent 缩窄为只映射 A；历史 mapping:B 必须被清掉。
 const narrow=await page.request.post(`/api/sessions/${sid}/proposal`,{
  data:{proposal:proposalFor(mapped),expected_revision:fullView.session.revision}});
 expect(narrow.ok(),await narrow.text()).toBeTruthy();
 const narrowView=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string;selected_versions:Record<string,string>}};
 expect(narrowView.session.selected_versions[`mapping:${other.source_id}`]).toBeFalsy();
 // 第三步：网页重建，只应提交 A；B 保持来源级问题，不再产生行级对象。
 await page.reload();
 await expect(page.getByRole('button',{name:'生成映射预览'})).toBeVisible();
 const [rebuilt]=await Promise.all([
  page.waitForResponse(response=>response.request().method()==='POST'&&/source-proposals$/.test(response.url())),
  page.getByRole('button',{name:'生成映射预览'}).click(),
 ]);
 expect(rebuilt.status()).toBe(200);
 const body=await rebuilt.json() as {instances:{values:{number?:string}}[];
  issues:{code?:string;source_id?:string;row?:number}[];source_revisions:Record<string,string>};
 expect(body.instances).toHaveLength(3);
 expect(Object.keys(body.source_revisions)).toEqual([mapped.source_id]);
 const otherIssues=body.issues.filter(issue=>issue.source_id===other.source_id);
 expect(otherIssues).toHaveLength(1);
 expect(otherIssues[0]).toMatchObject({code:'ontology.source_unmapped'});
 expect(otherIssues[0].row).toBeUndefined();
 const afterRebuild=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{selected_versions:Record<string,string>}};
 expect(afterRebuild.session.selected_versions[`mapping:${other.source_id}`]).toBeFalsy();
});

async function postResponse(page:import('@playwright/test').Page,url:RegExp){
 return page.waitForResponse(response=>response.request().method()==='POST'&&url.test(response.url()));
}

// 旧草稿回归：用户先改过来源 B 的绑定，代理随后把范围缩窄为只含 A。刷新
// 网页时服务端草稿仍带着 B 的绑定，但最新提案范围必须优先；B 不能被旧草稿
// 重新纳入，否则预览又会多出 B 的对象和行级问题。
test('缩窄提案后旧草稿不会把来源重新纳入预览',async({page})=>{
 test.setTimeout(60000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('缩窄提案后核对旧草稿范围');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'ledger.csv',mimeType:'text/csv',buffer:ledgerCsv},
  {name:'other.csv',mimeType:'text/csv',buffer:otherCsv},
 ]);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 const sid=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('session')!;
 const view=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string};ontology:{id:string;revision:string};ontology_concept:string;
  profiles:{source_id:string;fields:string[];metadata:{structure_fingerprint:string}}[];
 };
 const mapped=view.profiles.find(profile=>!profile.fields.includes('note'))!;
 const other=view.profiles.find(profile=>profile.fields.includes('note'))!;
 const proposalFor=(source:typeof mapped)=>({id:'candidate',revision:'1',
  ontology_revision:`${view.ontology.id}@${view.ontology.revision}`,concept:view.ontology_concept,
  source_fingerprint:source.metadata.structure_fingerprint,
  bindings:{number:{source_field:'number'},
   amount:source.fields.includes('amount_minor')
    ?{source_field:'amount_minor',transform:'minor_to_major'}
    :{source_field:'amount'},
   currency:{source_field:'currency'}}});
 // 先建立 A、B 都在范围内的映射，再让用户在页面上改 B 的币种绑定。
 const full=await page.request.post(`/api/sessions/${sid}/source-proposals`,{
  data:{proposals:{[mapped.source_id]:proposalFor(mapped),[other.source_id]:proposalFor(other)},
   expected_revision:view.session.revision}});
 expect(full.ok(),await full.text()).toBeTruthy();
 await page.reload();
 await expect(page.getByRole('button',{name:'生成映射预览'})).toBeVisible();
 await page.getByRole('button',{name:/other\.csv/}).click();
 await page.getByLabel('币种 来源字段').selectOption('note');
 await expect(page.getByText('草稿已保存')).toBeVisible();
 const edited=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as {
  session:{revision:string};draft:{source_bindings:Record<string,Record<string,{source_field:string}>>};
 };
 expect(edited.draft.source_bindings[other.source_id].currency.source_field).toBe('note');
 // 代理缩窄为只含 A；服务端草稿仍保留 B 的旧绑定。
 const narrow=await page.request.post(`/api/sessions/${sid}/proposal`,{
  data:{proposal:proposalFor(mapped),expected_revision:edited.session.revision}});
 expect(narrow.ok(),await narrow.text()).toBeTruthy();
 await page.reload();
 await expect(page.getByRole('button',{name:'生成映射预览'})).toBeVisible();
 const [rebuilt]=await Promise.all([
  page.waitForResponse(response=>response.request().method()==='POST'&&/source-proposals$/.test(response.url())),
  page.getByRole('button',{name:'生成映射预览'}).click(),
 ]);
 expect(rebuilt.status()).toBe(200);
 const body=await rebuilt.json() as {instances:{values:{number?:string}}[];
  issues:{code?:string;source_id?:string;row?:number}[];source_revisions:Record<string,string>};
 expect(body.instances).toHaveLength(3);
 expect(Object.keys(body.source_revisions)).toEqual([mapped.source_id]);
 const otherIssues=body.issues.filter(issue=>issue.source_id===other.source_id);
 expect(otherIssues).toHaveLength(1);
 expect(otherIssues[0]).toMatchObject({code:'ontology.source_unmapped'});
 expect(otherIssues[0].row).toBeUndefined();
});
