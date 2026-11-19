import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {awaitProbed,slowTimeout,uniqueTag} from './support';

// T53 D1 的回归：探查失败后页面给「继续探查」，重试请求返回前不能再点一次。
// 这里用真实的探查预算耗尽制造 retry_probe（第一次推进用很小的预算，只完成
// 一段就返回可续跑的 profile），再由网页用服务默认预算续跑完成；page.route
// 只把这一次 /advance 的响应延迟，结果仍由真实后端给出，不伪造。
let workspace=process.env.DATAAGENT_TEST_WORKSPACE||'';
const python=process.env.DATAAGENT_TEST_PYTHON;

// verify_browser.py 不把工作区路径传给 Playwright：上传一个探针文件取得
// locator_ref，再到系统临时目录里找到同一文件，从而定位当前服务的工作区。
async function resolveWorkspace(page:Page){
 if(workspace)return;
 const response=await page.request.post('/api/files',{
  headers:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN||'',
   'x-file-name':`probe-retry-workspace-${uniqueTag()}.csv`},
  data:'probe\n',
 });
 expect(response.ok(),await response.text()).toBeTruthy();
 const {locator_ref}=await response.json() as {locator_ref?:string};
 const root=os.tmpdir();
 const found=fs.readdirSync(root).filter(name=>name.startsWith('dataagent-ui-'))
  .map(name=>path.join(root,name))
  .filter(dir=>fs.existsSync(path.join(dir,'.dataagent','db','workbench.sqlite3')))
  .find(dir=>{
   const file=path.resolve(dir,String(locator_ref||''));
   return file.startsWith(path.resolve(dir)+path.sep)&&fs.existsSync(file);
  });
 if(!found||!locator_ref)throw new Error(`cannot find the running workspace for ${locator_ref}`);
 fs.rmSync(path.resolve(found,locator_ref),{force:true});
 workspace=found;
}

// MCP 进程从工作区 .mint/packages/dataagent 找已安装数据层；验收工作区没有
// 装包，把同一 checkout 的 dataagent-data 链接进去（与 publish.spec 相同）。
function ensureDataLayer(){
 const packages=path.join(workspace!,'.mint','packages','dataagent');
 fs.mkdirSync(packages,{recursive:true});
 const link=path.join(packages,'data-layer@local');
 if(!fs.existsSync(link))fs.symlinkSync(path.resolve('../../dataagent-data'),link,'dir');
}

function callTool(name:string,args:Record<string,unknown>,env?:Record<string,string>){
 const request={jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}};
 const line=execFileSync(python!,['-m','dataagent_workbench.interfaces.mcp_server'],{
  cwd:workspace,env:{...process.env,...env},input:JSON.stringify(request)+'\n',encoding:'utf8',
 });
 const {result}=JSON.parse(line);
 if(result.isError)throw new Error(`tool ${name} failed: ${result.content[0].text}`);
 const summary=JSON.parse(result.content[0].text);
 return JSON.parse(fs.readFileSync(path.join(workspace!,summary.result_path),'utf8')).data;
}

// 合成一份多页文本 PDF：每页都有可读文本，足够让第一次小预算推进只完成一个
// 分段（10 页）并留下续跑点。只依赖基础 PDF 结构，不引入测试依赖。
function multiPagePdf(pages:number){
 const objects=new Map<number,string>(),pageIds:number[]=[],contentIds:number[]=[];
 for(let i=0;i<pages;i++){pageIds.push(4+2*i);contentIds.push(5+2*i);}
 objects.set(1,'<< /Type /Catalog /Pages 2 0 R >>');
 objects.set(2,`<< /Type /Pages /Kids [${pageIds.map(id=>`${id} 0 R`).join(' ')}] /Count ${pages} >>`);
 objects.set(3,'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');
 for(let i=0;i<pages;i++){
  objects.set(pageIds[i],`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] `
   +`/Resources << /Font << /F1 3 0 R >> >> /Contents ${contentIds[i]} 0 R >>`);
  const text=`Page ${i+1}: invoice number INV-${String(i+1).padStart(3,'0')} amount ${i+1} currency CNY`;
  const stream=`BT /F1 12 Tf 72 720 Td (${text}) Tj ET`;
  objects.set(contentIds[i],`<< /Length ${Buffer.byteLength(stream,'latin1')} >>\nstream\n${stream}\nendstream`);
 }
 const chunks:Buffer[]=[];let length=0;
 const push=(value:string)=>{const bytes=Buffer.from(value,'latin1');chunks.push(bytes);length+=bytes.length;};
 push('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n');
 const offsets=new Map<number,number>();
 for(const id of [...objects.keys()].sort((a,b)=>a-b)){
  offsets.set(id,length);
  push(`${id} 0 obj\n${objects.get(id)}\nendobj\n`);
 }
 const xref=length,max=Math.max(...objects.keys());
 push(`xref\n0 ${max+1}\n0000000000 65535 f \n`);
 for(let id=1;id<=max;id++)push(`${String(offsets.get(id)).padStart(10,'0')} 00000 n \n`);
 push(`trailer\n<< /Size ${max+1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
 return Buffer.concat(chunks);
}

async function retryClicks(page:Page){
 return page.evaluate(()=>(window as unknown as {retryClicks?:number}).retryClicks||0);
}

test.beforeEach(async({page})=>{await resolveWorkspace(page);});

test('探查重试在响应未完成时只点击一次，延迟返回后仍完成',async({page})=>{
 test.skip(!workspace||!python,'run scripts/verify_browser.py to share the test workspace with MCP');
 slowTimeout(90000);
 ensureDataLayer();
 const tag=uniqueTag();
 const file=path.join(workspace,`probe-retry-${tag}.pdf`);
 fs.writeFileSync(file,multiPagePdf(60));
 try{
  const started=callTool('intake_start',{goal:'核对探查重试不会重复点击',
   target:{ontology_id:'procurement'},
   sources:[{source_id:'retry-doc',kind:'file',locator_ref:path.basename(file)}]}) as {session_id:string};
  const sid=started.session_id;
  // 第一次推进只给 0.1 秒：60 页的 PDF 完成第一段（10 页）就返回可续跑的
  // profile，后端把任务标成 retry_probe，和真实现场探查失败后的入口一致。
  callTool('intake_advance',{session_id:sid},{DATAAGENT_INTAKE_BUDGET_SECONDS:'0.1'});
  const pending=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as
   {session:{next_actions:string[]}};
  expect(pending.session.next_actions).toContain('retry_probe');

  await page.goto('/#session='+sid);
  const retry=page.getByRole('button',{name:'继续探查'});
  const done=page.getByText('识别与探查已完成');
  await expect(retry).toBeVisible({timeout:20000});

  // 统计这一次点击发出的 advance 请求与真实点击次数；只延迟响应，不改结果。
  const advance=/\/api\/sessions\/[^/]+\/advance$/;
  let advances=0;
  page.on('request',request=>{
   if(request.method()==='POST'&&advance.test(new URL(request.url()).pathname))advances++;
  });
  await page.route(advance,async route=>{
   const response=await route.fetch();
   await new Promise(resolve=>setTimeout(resolve,1200));
   await route.fulfill({response});
  });
  await page.evaluate(()=>{
   const state=window as unknown as {retryClicks:number};
   state.retryClicks=0;
   document.addEventListener('click',event=>{
    const button=(event.target as Element|null)?.closest('button');
    if(button?.textContent?.includes('继续探查'))state.retryClicks++;
   },true);
  });

  const probing=awaitProbed(page,30000);
  await expect.poll(()=>advances).toBe(1);
  // 响应还没返回：按钮应保持不可用，完成文案不能出现，也不能发出第二次
  // 点击/请求。若助手按「按钮可见」就继续，会在这里去点一个尚未恢复的按钮。
  await expect(retry).toBeDisabled();
  await page.waitForTimeout(400);
  expect(advances).toBe(1);
  expect(await retryClicks(page)).toBe(1);
  await expect(done).toHaveCount(0);

  await probing;
  await expect(done).toBeVisible();
  expect(advances).toBe(1);
  expect(await retryClicks(page)).toBe(1);
  const finished=await (await page.request.get(`/api/sessions/${sid}/view`)).json() as
   {session:{next_actions:string[]};profiles:{coverage:string}[]};
  expect(finished.session.next_actions).not.toContain('retry_probe');
  expect(finished.profiles[0]?.coverage).toBe('full');
 }finally{
  fs.rmSync(file,{force:true});
 }
});
