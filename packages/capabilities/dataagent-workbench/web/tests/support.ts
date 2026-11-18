import {test} from '@playwright/test';
import type {Page} from '@playwright/test';
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
// browse.spec）会临时把注册表默认指针移到新本体，这里不依赖默认值，
// 用例间互不影响。
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
