import {test,expect} from '@playwright/test';
import {compareDisplayText} from '../src/client';
import {pinBuiltinOntology,slowTimeout} from './support';

// FDE3-04：一个任务固定一个目标概念。限额表 docx 与费用明细 xlsx 一起提交时，
// 限额表没有任务概念的身份列（单据编号），必需属性也大多无法绑定——映射预览
// 必须把它拦在对象之外，给一条来源级「该来源与目标概念不符」，并只提供
// 「本任务不使用该来源」的整源处置；「纳入映射」只在来源与概念相符时提供
// （相符但未映射的来源仍走 source_unmapped，见 dispositions.spec）。
// 处置提交走真实后端 POST /api/sessions/<id>/dispositions 与 source-proposals。

// 最小可解析的合成 Word 限额表：一段标题 + 一张 3 列表（费用类别/城市等级/限额，
// 表头 + 2 行数据）+ 一段备注；列名与任务概念（单据编号/金额/币种）完全不同。
const limitsDocx=Buffer.from(
  'UEsDBBQAAAAIAN0xc115bjPX6AAAAK0BAAATAAAAW0NvbnRlbnRfVHlwZXNdLnhtbH1QyU7DMBD9FWuuKHHggBCK0wPLETiUDxjZ'
 +'k8SqN3nc0v49Tlt6QIXjzFv1+tXeO7GjzDYGBbdtB4KCjsaGScHn+rV5AMEFg0EXAyk4EMNq6NeHRCyqNrCCuZT0KCXrmTxyGxOF'
 +'iowxeyz1zJNMqDc4kbzrunupYygUSlMWDxj6Zxpx64p42df3qUcmxyCeTsQlSwGm5KzGUnG5C+ZXSnNOaKvyyOHZJr6pBJBXExbk'
 +'74Cz7r0Ok60h8YG5vKGvLPkVs5Em6q2vyvZ/mys94zhaTRf94pZy1MRcF/euvSAebfjpL49zD99QSwMEFAAAAAgA3TFzXZv9N+qt'
 +'AAAAKQEAAAsAAABfcmVscy8ucmVsc43POw7CMAwG4KtE3mlaBoRQ0y4IqSsqB7ASN61oHkrCo7cnAwNFDIy2f3+W6/ZpZnanECdn'
 +'BVRFCYysdGqyWsClP232wGJCq3B2lgQsFKFt6jPNmPJKHCcfWTZsFDCm5A+cRzmSwVg4TzZPBhcMplwGzT3KK2ri27Lc8fBpwNpk'
 +'nRIQOlUB6xdP/9huGCZJRydvhmz6ceIrkWUMmpKAhwuKq3e7yCzwpuarF5sXUEsDBBQAAAAIAN0xc12LRuh9oQEAAIgFAAARAAAA'
 +'d29yZC9kb2N1bWVudC54bWy9VEtLAzEQ/itL7jariJTSrQdBr4IVz9vd2C7sJks29nErhWpF0R58YFFEESz4QlSsVfHH2N22J/+C'
 +'Sbf2ARURbS8zk2S++TJfwoSn05YpJRF1DIIVMB6QgYSwRnQDxxWwGJ0dCwLJYSrWVZNgpIAMcsB0JJwK6URbsRBmEi+AnVBKAQnG'
 +'7BCEjpZAluoEiI0wP1sm1FIZX9I4TBGq25RoyHF4fcuEE7I8BS3VwECUjBE9I7wtDBWGRdzHa28/37h/qu+UmwfF5ulR46QchuJI'
 +'WNqyLQCLmW03T9vBAsuYSEqFkqqpgKgaM9EcNXQAW6DeRLEtwjj3M8TkEN4Pv5wscn+3DfsKMp9B822bT1vqgfCQZWyurJ5Wv/Dt'
 +'xF4dfAXqt89u4WJA+7BL8mcq93jLreTqV+v16vmQqfwX/Z4EdhT8Lx15Z+5qvlY9a2ZLXNMh91erZPmTDZkkKI9SwNrrtnv9NgLp'
 +'qpvDl25S/lk72Bktff/obM27K3+8lLzDSz6RapWqWyx4haL3sNG42fWOit7ewXs2N7i6P+hgd4hGPgFQSwECFAMUAAAACADdMXNd'
 +'eW4z1+gAAACtAQAAEwAAAAAAAAAAAAAAgAEAAAAAW0NvbnRlbnRfVHlwZXNdLnhtbFBLAQIUAxQAAAAIAN0xc12b/TfqrQAAACkB'
 +'AAALAAAAAAAAAAAAAACAARkBAABfcmVscy8ucmVsc1BLAQIUAxQAAAAIAN0xc12LRuh9oQEAAIgFAAARAAAAAAAAAAAAAACAAe8B'
 +'AAB3b3JkL2RvY3VtZW50LnhtbFBLBQYAAAAAAwADALkAAAC/AwAAAAA='
 ,'base64');
// 合成费用明细 xlsx：number/amount/currency 三列、2 行数据，与任务概念同名。
const detailXlsx=Buffer.from(
    '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'
 ,'base64');

test('中文序数按序数值排序而不是拼音（FDE2-13 余项）',()=>{
 // 一类 < 二类 < 三类 < 十类（拼音序会排成 二、三、十、一）。
 expect(compareDisplayText('一类','二类')).toBeLessThan(0);
 expect(compareDisplayText('二类','三类')).toBeLessThan(0);
 expect(compareDisplayText('九类','十类')).toBeLessThan(0);
 expect(compareDisplayText('第一','第二')).toBeLessThan(0);
 expect(compareDisplayText('第二','第十一')).toBeLessThan(0);
 // 非数字段沿用中文排序；数字段与普通文本比较不报错。
 expect(compareDisplayText('北京','上海')).toBeLessThan(0);
 expect(compareDisplayText('','一类')).toBeLessThan(0);
});

test('限额表与明细同任务：不符来源被拦截并可整源处置',async({page})=>{
 slowTimeout(60000);
 await page.goto('/');
 await page.getByLabel('接入目标').fill('接入费用明细与限额表并核对来源拦截');
 await page.getByLabel('选择材料').setInputFiles([
  {name:'限额表.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:limitsDocx},
  {name:'明细.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:detailXlsx},
 ]);
 await pinBuiltinOntology(page);
 await page.getByRole('button',{name:'开始接入'}).click();
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
 // 尚无提案固定来源范围：首次生成预览会把两份材料一起提案。
 await page.getByRole('button',{name:'生成映射预览'}).click();
 const issues=page.getByTestId('mapping-issues');
 // 限额表被拦在对象之外：只有明细的 2 个对象，没有逐行缺失值问题。
 await expect(page.locator('.object-section .badge').first()).toHaveText('2 个对象');
 // FDE2-06 余项：标题按根因计数（「N 项根因」），不再把来源级问题逐行放大。
 await expect(page.locator('.notice.amber strong').first()).toHaveText('1 项根因');
 await expect(issues).toContainText('该来源与目标概念不符');
 await expect(issues).toContainText('限额表.docx');
 // 与概念不符的来源不给「纳入映射」，只有整源处置这一条出路。
 await expect(page.getByTestId('include-mapping-option')).toHaveCount(0);
 const disposal=page.getByTestId('disposal-option').filter({hasText:'本任务不使用「限额表.docx」'});
 await expect(disposal).toBeVisible();
 const submit=disposal.getByRole('button',{name:'提交处置'});
 await expect(submit).toBeDisabled();
 await disposal.getByLabel(/处置原因：本任务不使用/).fill('限额表不是费用明细，本任务不使用');
 await expect(submit).toBeEnabled();
 const [disposed]=await Promise.all([
  page.waitForResponse(response=>response.request().method()==='POST'&&/\/sessions\/[^/]+\/dispositions$/.test(response.url())),
  submit.click(),
 ]);
 expect(disposed.status()).toBe(200);
 const body=await disposed.json() as {entry:{action:string;source_id:string}};
 expect(body.entry.action).toBe('ignore_source');
 await expect(page.getByTestId('mapping-correction-notice')).toContainText('处置已记录');
 // 处置后重新生成：来源级问题消失，只剩明细对象，整批可以保存。
 await page.getByRole('button',{name:'生成映射预览'}).click();
 await expect(page.getByTestId('mapping-issues')).toHaveCount(0);
 await expect(page.locator('.object-section .badge').first()).toHaveText('2 个对象');
 await expect(page.getByRole('button',{name:'保存接入'})).toBeEnabled();
 await page.getByRole('button',{name:'保存接入'}).click();
 await expect(page.getByText('接入已保存')).toBeVisible();
});
