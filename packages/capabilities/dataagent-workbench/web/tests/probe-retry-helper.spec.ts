import {expect,test} from '@playwright/test';
import type {Page} from '@playwright/test';
import {awaitEvidenceProbed,awaitProbed,uniqueTag} from './support';

// 两个探查助手的契约回归：点击重试后必须等这一次 POST /advance 真正返回，
// 不能凭按钮仍可用就认为上一次已经结束。页面用最小 DOM 模拟「请求已发出、
// 组件还没提交禁用状态」的窗口（真实页面里这个窗口很短，但不应靠时序假设）；
// 请求打到真实后端，page.route 只延迟响应，不伪造结果。
async function realSession(page:Page){
 const upload=await page.request.post('/api/files',{
  headers:{'x-file-name':`probe-helper-${uniqueTag()}.csv`},
  data:'number,amount,currency,issuer\nINV-777,1250,CNY,华信办公\n',
 });
 expect(upload.ok(),await upload.text()).toBeTruthy();
 const source=await upload.json();
 const started=await page.request.post('/api/sessions',{
  data:{goal:'核对探查助手不会重复点击',sources:[source],target:{ontology_id:'procurement'}},
 });
 expect(started.ok(),await started.text()).toBeTruthy();
 return (await started.json() as {session_id:string}).session_id;
}
async function prepare(page:Page,html:string){
 await page.goto('/api/identity');
 await page.setContent(html);
}
async function delayAdvance(page:Page){
 let requests=0;
 await page.route('**/api/sessions/*/advance',async route=>{
  requests++;
  const response=await route.fetch();
  await new Promise(resolve=>setTimeout(resolve,800));
  await route.fulfill({response});
 });
 return()=>requests;
}
async function counts(page:Page){
 return page.evaluate(()=>({
  clicks:(window as unknown as {clicks?:number}).clicks||0,
  requests:(window as unknown as {requests?:number}).requests||0,
 }));
}

test('继续探查在上一次请求返回前只点击一次',async({page})=>{
 const sid=await realSession(page);
 await prepare(page,`<button id="retry">继续探查</button><p id="done"></p>
  <script>
   window.clicks=0;window.requests=0;
   const button=document.getElementById('retry');
   button.addEventListener('click',async()=>{
    window.clicks++;window.requests++;
    await fetch('/api/sessions/${sid}/advance',{method:'POST'});
    button.remove();
    document.getElementById('done').textContent='识别与探查已完成';
   });
  </script>`);
 const requests=await delayAdvance(page);
 await awaitProbed(page,15000);
 expect(requests()).toBe(1);
 expect((await counts(page)).clicks).toBe(1);
 await expect(page.getByText('识别与探查已完成')).toBeVisible();
});

test('重新探查在上一次请求返回前只点击一次',async({page})=>{
 const sid=await realSession(page);
 await prepare(page,`<h2>来源证据</h2><button id="retry">重新探查</button>
  <script>
   window.clicks=0;window.requests=0;
   const button=document.getElementById('retry');
   button.addEventListener('click',async()=>{
    window.clicks++;window.requests++;
    await fetch('/api/sessions/${sid}/advance',{method:'POST'});
    button.remove();
   });
  </script>`);
 const requests=await delayAdvance(page);
 await awaitEvidenceProbed(page,15000);
 expect(requests()).toBe(1);
 expect((await counts(page)).clicks).toBe(1);
});
