import {useEffect,useState} from 'react';
import {api,display} from '../client';

type WorkflowRun={
 id:string;
 revision:number;
 state:string;
 work_spec:{goal:string};
 business_key:string;
 current_step?:string;
 message?:string;
 completed:string[];
 receipt_refs:string[];
 unknown_action_ref?:string;
 wait_ref?:string;
};

const states:Record<string,string>={
 active:'等待推进',waiting:'等待业务状态',needs_input:'需要补充信息',
 paused:'已暂停',cancelled:'已取消',completed:'已核验完成',failed:'校验失败',
 unknown:'动作结果待对账',replan_required:'需要更新流程',revoked:'授权已撤销',
};

export function WorkflowPage({id,onError}:{id:string;onError:(error:unknown)=>void}){
 const [run,setRun]=useState<WorkflowRun|null>(null);
 const [busy,setBusy]=useState(false);
 const path='/api/workflows/'+encodeURIComponent(id);
 async function refresh(){setRun(await api<WorkflowRun>(path));}
 useEffect(()=>{refresh().catch(onError);},[id]);
 async function control(command:string){
  setBusy(true);
  try{setRun(await api<WorkflowRun>(path+'/control','POST',{command}));}
  catch(error){onError(error);}
  finally{setBusy(false);}
 }
 if(!run)return <main className="loading">正在读取工作流…</main>;
 const terminal=['completed','failed','cancelled','revoked'].includes(run.state);
 return <main className="intake-home">
  <h1>{run.work_spec.goal}</h1>
  <section className="intake-card">
   <h2>{states[run.state]||run.state}</h2>
   <dl className="object-values">
    <div><dt>业务键</dt><dd>{run.business_key}</dd></div>
    <div><dt>执行修订</dt><dd>{run.revision}</dd></div>
    <div><dt>当前步骤</dt><dd>{display(run.current_step)}</dd></div>
   </dl>
   {run.message&&<p>{run.message}</p>}
   {run.unknown_action_ref&&<p className="notice amber">待核对动作 {run.unknown_action_ref}</p>}
   {run.wait_ref&&<p>等待记录 {run.wait_ref}</p>}
   {run.completed.length>0&&<details><summary>已完成步骤（{run.completed.length}）</summary><ol>{run.completed.map(step=><li key={step}>{step}</li>)}</ol></details>}
   {run.receipt_refs.length>0&&<details><summary>动作回执（{run.receipt_refs.length}）</summary><ul>{run.receipt_refs.map(ref=><li key={ref}>{ref}</li>)}</ul></details>}
   <div className="save-buttons">
    <button className="secondary" onClick={()=>refresh().catch(onError)} disabled={busy}>刷新状态</button>
    {!terminal&&run.state==='paused'&&<button className="secondary" onClick={()=>control('resume')} disabled={busy}>恢复</button>}
    {!terminal&&run.state!=='paused'&&<button className="secondary" onClick={()=>control('pause')} disabled={busy}>暂停</button>}
    {!terminal&&!['paused','needs_input','replan_required'].includes(run.state)&&
     <button className="primary" onClick={()=>control('advance')} disabled={busy}>{run.unknown_action_ref?'查询动作结果':'推进工作流'}</button>}
   </div>
  </section>
 </main>;
}
