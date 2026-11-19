import {expect,test} from '@playwright/test';
import type {Locator,Page,Request} from '@playwright/test';
import {randomUUID} from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// 单用例超时统一从这里设置：多张卡并行验收时机器负载高，默认按系数放大；
// 需要收紧或进一步放宽时用 DATAAGENT_TEST_TIMEOUT_SCALE 覆盖（1 为不放大）。
const TIMEOUT_SCALE=Number(process.env.DATAAGENT_TEST_TIMEOUT_SCALE||1.5);
export function slowTimeout(ms:number){test.setTimeout(Math.round(ms*TIMEOUT_SCALE));}

// 并行用例共用 verify_browser.py 起的一个工作区：写进工作区的文件名加用例级
// 唯一后缀，不删除也不覆盖其他用例（含重试的其他次执行）可能用到的同名文件。
export function uniqueTag(){
 return `w${test.info().workerIndex}-${randomUUID().slice(0,8)}`;
}

// 依赖内置采购本体的用例显式固定目标：发布本体的用例（publish.spec、
// browse.spec、revision.spec、expense-labels.spec、mapping-source-fit.spec）
// 会临时把注册表默认指针移到新本体，这里不依赖默认值，用例间互不影响。
export async function pinBuiltinOntology(page:Page){
 await page.getByLabel('映射到的本体').selectOption('procurement');
}

// 发布/停用本体会移动注册表默认指针（共享状态），且 publish.spec 还要断言
// 默认指针的取值：这组用例之间用按工作区命名的文件锁串行（其他用例已显式
// 固定目标，不受影响）。持有者异常退出时锁目录会残留，超过时效即可被抢占。
const POINTER_LOCK_STALE_MS=10*60*1000;
function lockDir(workspace:string){
 return path.join(os.tmpdir(),'dataagent-e2e-pointer-'+path.basename(workspace));
}
export async function lockDefaultPointer(workspace:string){
 while(true){
  try{fs.mkdirSync(lockDir(workspace));return;}
  catch{
   try{
    if(Date.now()-fs.statSync(lockDir(workspace)).mtimeMs>POINTER_LOCK_STALE_MS)
     fs.rmSync(lockDir(workspace),{recursive:true,force:true});
   }catch{/* 竞态下目录可能刚被移除，继续等待即可 */}
   await new Promise(resolve=>setTimeout(resolve,250));
  }
 }
}
export function unlockDefaultPointer(workspace:string){
 try{fs.rmSync(lockDir(workspace),{recursive:true,force:true});}catch{/* 锁不存在视为已释放 */}
}

// 探查子进程偶发失败（多 worker 验收的高负载下出现过一次 probe_failed），后端
// 把它标记为 retryable，页面给出「继续探查 / 重新探查」入口。探查相关的等待统一
// 走这两个助手：完成或出现重试入口前先等；点重试后以这一次 POST /advance 的
// 真实响应作为「上一次请求已完成」的依据，再判断是否还需要下一次。
//
// 不能只看按钮可见或恢复可用：点击后 React 要等状态提交才把按钮置灰，在这段
// 窗口里轮询会看到旧的可用状态，从而在上一个请求尚未完成时再次点击（延迟返回
// 时尤其明显）。这里在点击前注册响应监听，并按请求对象排除点击前就在途的
// advance（例如打开任务时的自动推进）。不放宽断言：有界重试耗尽后仍按原来的
// 完成条件失败。
const ADVANCE_PATH=/\/api\/sessions\/[^/]+\/advance$/;
function isAdvanceRequest(request:Request){
 return request.method()==='POST'&&ADVANCE_PATH.test(new URL(request.url()).pathname);
}
const inFlightAdvances=new WeakMap<Page,Set<Request>>();
function trackAdvances(page:Page){
 let inFlight=inFlightAdvances.get(page);
 if(!inFlight){
  inFlight=new Set<Request>();
  page.on('request',request=>{if(isAdvanceRequest(request))inFlight!.add(request);});
  // 收到响应就算这一次推进已经结束：只看 requestfinished 时，route.fulfill
  // 的响应可能迟迟不落到 finished，助手会误以为请求仍在途而一直等待。
  const settle=(request:Request)=>{inFlight!.delete(request);};
  page.on('response',response=>settle(response.request()));
  page.on('requestfinished',settle);
  page.on('requestfailed',settle);
  inFlightAdvances.set(page,inFlight);
 }
 return inFlight;
}
// 助手只在上一次推进真正结束后才做下一次判断；调用时若还有别的推进在途（例如
// 打开任务触发的自动推进），先等它结束，避免把它当成这次重试的响应或重复点击。
async function awaitNoAdvanceInFlight(page:Page,options:{timeout?:number}){
 await expect.poll(()=>trackAdvances(page).size,options).toBe(0);
}
async function clickRetryAndAwait(page:Page,button:Locator,timeout?:number){
 const inFlight=trackAdvances(page);
 const alreadyRunning=new Set(inFlight);
 // 先注册响应监听再点击，快速返回的响应也不会漏掉；点击前已在途的 advance
 // 不属于这一次点击，不拿它的响应当本次重试结束。
 const completed=page.waitForResponse(response=>{
  const request=response.request();
  return isAdvanceRequest(request)&&!alreadyRunning.has(request);
 },{timeout:timeout??30000});
 await button.click();
 await completed;
}

export async function awaitProbed(page:Page,timeout?:number){
 const done=page.getByText('识别与探查已完成');
 const retry=page.getByRole('button',{name:'继续探查'});
 const retryReady=page.getByRole('button',{name:'继续探查',disabled:false});
 const options=timeout?{timeout}:{};
 for(let attempt=0;attempt<2;attempt++){
  await awaitNoAdvanceInFlight(page,options);
  await expect(done.or(retry)).toBeVisible(options);
  if(await done.isVisible())return;
  await clickRetryAndAwait(page,retry,timeout);
  // 本次重试已返回：成功则完成文案出现，失败则按钮重新可用；二者都没出现
  // 前不进入下一次判断。
  await expect(done.or(retryReady)).toBeVisible(options);
 }
 await expect(done).toBeVisible(options);
}

// 发现任务的来源证据：探查失败时证据区也会出现（0 张表），据此不能用「证据
// 出现」当完成条件；失败时页面给「重新探查」入口，出现就重试并等本次请求结束
// （成功则入口消失，失败则按钮重新可用）再判断是否需要下一次。
export async function awaitEvidenceProbed(page:Page,timeout?:number){
 const evidence=page.getByRole('heading',{name:'来源证据'});
 const retry=page.getByRole('button',{name:'重新探查'});
 const options=timeout?{timeout}:{};
 await expect(evidence).toBeVisible(options);
 for(let attempt=0;attempt<2;attempt++){
  await awaitNoAdvanceInFlight(page,options);
  if(!(await retry.isVisible()))break;
  await clickRetryAndAwait(page,retry,timeout);
  await expect.poll(async()=>{
   const count=await retry.count();
   return count===0||await retry.isEnabled();
  },options).toBeTruthy();
 }
 await expect(retry).toHaveCount(0);
}
