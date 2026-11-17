import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {api,ApiError} from './client';
import {IntakePage} from './pages/IntakePage';
import {MappingPage} from './pages/MappingPage';
import {ObjectPage} from './pages/ObjectPage';
import {WorkflowPage} from './pages/WorkflowPage';
import './style.css';
function App(){
 const hash=new URLSearchParams(location.hash.slice(1));const [session,setSession]=useState(hash.get('session')||''),[workflow,setWorkflow]=useState(hash.get('workflow')||''),[object,setObject]=useState(hash.get('object')||''),[authenticated,setAuthenticated]=useState<boolean|null>(null),[error,setError]=useState('');
 function failure(e:unknown){
  setError(e instanceof ApiError&&e.status===409?'任务已有更新，当前编辑已保留。请重新载入并核对。':
   e instanceof Error?e.message:String(e));
 }
 useEffect(()=>{(async()=>{
  const nonce=hash.get('nonce');if(nonce){await api('/api/auth','POST',{nonce});history.replaceState(null,'',workflow?'#workflow='+workflow:session?'#session='+session:'#');}
  await api('/api/identity');setAuthenticated(true);
 })().catch(()=>setAuthenticated(false));},[]);
 function openSession(id:string){setSession(id);setError('');history.replaceState(null,'','#session='+id);api(`/api/sessions/${id}/advance`,'POST',{}).catch(failure);}
 return <><header className="app-header"><a href="#" className="brand" onClick={e=>{e.preventDefault();setSession('');setWorkflow('');history.replaceState(null,'','#');}}><span className="brand-icon">D</span>DataAgent<span className="brand-section">接入工作台</span></a><span className="workspace-badge"><span className="dot"/>本地工作区</span></header>
 {error&&<div className="error-banner" role="alert"><span>{error}</span><button aria-label="关闭提示" onClick={()=>setError('')}>×</button></div>}
 {authenticated===null?<main className="loading">正在连接工作区…</main>:!authenticated?<main className="intake-home"><h1>打开本地工作台</h1><p className="muted">通过本机浏览器入口查看你的材料与接入任务。</p><button className="primary" onClick={()=>api('/local/open','POST',workflow?{run_id:workflow}:session?{session_id:session}:{}).catch(failure)}>打开本地工作台</button></main>:workflow?<WorkflowPage id={workflow} onError={failure}/>:object?<ObjectPage key={object} sessionId={object} onBack={()=>{setSession(object);setObject('');history.replaceState(null,'','#session='+object);}} onError={failure}/>:session?<MappingPage key={session} sessionId={session} onNew={()=>{setSession('');history.replaceState(null,'','#');}} onOpenObjects={()=>{setObject(session);history.replaceState(null,'','#object='+session);}} onError={failure}/>:<IntakePage onStart={openSession} onError={failure}/>}
 </>;
}
createRoot(document.getElementById('root')!).render(<App/>);
