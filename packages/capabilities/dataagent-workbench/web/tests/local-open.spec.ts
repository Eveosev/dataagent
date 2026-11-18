import {test,expect} from '@playwright/test';

// FDE-15：未认证时点「打开本地工作台」要在当前页给出结果；
// FDE-18：favicon 可用，不再每页 404。
test('未认证时打开本地工作台按钮在当前页给出结果',async({page})=>{
 await page.route('**/api/identity',route=>route.fulfill({status:401,json:{error:'authentication_required'}}));
 let opened:Record<string,unknown>|undefined;
 await page.route('**/local/open',async route=>{
  opened=route.request().postDataJSON();
  await route.fulfill({json:{opened:true,session_id:null,url:'http://127.0.0.1:12345/#'}});
 });
 await page.goto('/');
 await page.getByRole('button',{name:'打开本地工作台'}).click();
 // 按钮点击后在当前页给出结果与可复制的链接，而不是毫无反馈。
 await expect(page.getByTestId('local-open-result')).toContainText('已在默认浏览器打开工作台');
 await expect(page.getByTestId('local-open-result')).toContainText('http://127.0.0.1:12345/#');
 expect(opened).toEqual({});
});

test('未认证时打开本地工作台失败也在当前页给出中文原因',async({page})=>{
 await page.route('**/api/identity',route=>route.fulfill({status:401,json:{error:'authentication_required'}}));
 await page.route('**/local/open',route=>route.fulfill({status:500,json:{detail:'boom'}}));
 await page.goto('/');
 await page.getByRole('button',{name:'打开本地工作台'}).click();
 await expect(page.getByTestId('local-open-result')).toContainText('boom');
});

test('favicon 可用（FDE-18）',async({request})=>{
 const response=await request.get('/favicon.svg');
 expect(response.status()).toBe(200);
});
