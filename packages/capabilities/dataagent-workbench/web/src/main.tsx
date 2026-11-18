import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {api,ApiError,translateError} from './client';
import {IntakePage} from './pages/IntakePage';
import {MappingPage} from './pages/MappingPage';
import {ObjectPage} from './pages/ObjectPage';
import {OntologiesPage} from './pages/OntologiesPage';
import {WorkflowPage} from './pages/WorkflowPage';
import './style.css';
function App(){
 const hash=new URLSearchParams(location.hash.slice(1));const [session,setSession]=useState(hash.get('session')||''),[workflow,setWorkflow]=useState(hash.get('workflow')||''),[object,setObject]=useState(hash.get('object')||''),[ontologies,setOntologies]=useState(hash.get('ontologies')==='1'),[authenticated,setAuthenticated]=useState<boolean|null>(null),[error,setError]=useState('');
 // FDE-15：点击「打开本地工作台」后在当前页给出结果，而不是毫无反馈。
 const [openState,setOpenState]=useState<{ok:boolean;text:string;url?:string}|null>(null);
 function failure(e:unknown){
  setError(e instanceof ApiError&&e.status===409?'任务已有更新，当前编辑已保留。请重新载入并核对。':
   e instanceof Error?translateError(e.message):String(e));
 }
 useEffect(()=>{(async()=>{
  const nonce=hash.get('nonce');if(nonce){await api('/api/auth','POST',{nonce});history.replaceState(null,'',workflow?'#workflow='+workflow:session?'#session='+session:'#');}
  await api('/api/identity');setAuthenticated(true);
 })().catch(()=>setAuthenticated(false));},[]);
 function openSession(id:string){setSession(id);setError('');setOntologies(false);history.replaceState(null,'','#session='+id);api(`/api/sessions/${id}/advance`,'POST',{}).catch(failure);}
 function openOntologies(){setOntologies(true);setError('');history.replaceState(null,'','#ontologies=1');}
 function closeOntologies(){setOntologies(false);history.replaceState(null,'',session?'#session='+session:'#');}
 async function openLocal(){
  setOpenState(null);
  try{
   const result=await api<{opened:boolean;url?:string}>('/local/open','POST',workflow?{run_id:workflow}:session?{session_id:session}:{});
   setOpenState({ok:true,text:'已在默认浏览器打开工作台，请在本机完成认证。',url:result.url});
  }catch(error){
   setOpenState({ok:false,text:error instanceof Error?translateError(error.message):String(error)});
  }
 }
 return <><header className="app-header"><a href="#" className="brand" onClick={e=>{e.preventDefault();setSession('');setWorkflow('');setObject('');setOntologies(false);history.replaceState(null,'','#');}}><span className="brand-icon">D</span>DataAgent<span className="brand-section">接入工作台</span></a>
  <div className="header-side"><button className="header-link" onClick={openOntologies}>本体库</button><span className="workspace-badge"><span className="dot"/>本地工作区</span></div></header>
 {error&&<div className="error-banner" role="alert"><span>{error}</span><button aria-label="关闭提示" onClick={()=>setError('')}>×</button></div>}
 {authenticated===null?<main className="loading">正在连接工作区…</main>:!authenticated?<main className="intake-home"><h1>打开本地工作台</h1><p className="muted">通过本机浏览器入口查看你的材料与接入任务。</p><button className="primary" onClick={openLocal}>打开本地工作台</button>
  {openState&&<p className={openState.ok?'local-open-result ok':'local-open-result warn'} data-testid="local-open-result" role="status">{openState.text}{openState.url&&<>　若浏览器没有自动打开，请在同一台机器上访问 <code>{openState.url}</code></>}</p>}
 </main>:workflow?<WorkflowPage id={workflow} onError={failure}/>:ontologies?<OntologiesPage onNew={()=>{setSession('');setOntologies(false);history.replaceState(null,'','#');}} onBack={session?closeOntologies:undefined} onError={failure}/>:object?<ObjectPage key={object} sessionId={object} onBack={()=>{setSession(object);setObject('');history.replaceState(null,'','#session='+object);}} onError={failure}/>:session?<MappingPage key={session} sessionId={session} onNew={()=>{setSession('');history.replaceState(null,'','#');}} onOpenObjects={()=>{setObject(session);history.replaceState(null,'','#object='+session);}} onOpenOntologies={openOntologies} onError={failure}/>:<IntakePage onStart={openSession} onError={failure}/>}
 </>;
}
createRoot(document.getElementById('root')!).render(<App/>);
