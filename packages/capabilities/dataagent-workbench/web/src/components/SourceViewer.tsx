import {useEffect,useState} from 'react';
import type {SourceProfile} from '../client';
import {display} from '../client';
type Anchor={source_ref:string;selector:{kind:string;page?:number;bbox?:unknown[];char_start?:number;char_end?:number;field?:string;range?:string;sheet?:string;pointer?:string;keys?:Record<string,unknown>}};
export function SourceViewer({sessionId,profile,anchor,recordIndex,sourceField}:{sessionId:string;profile?:SourceProfile;anchor?:Anchor;recordIndex:number;sourceField?:string}){
 const [image,setImage]=useState('');const [problem,setProblem]=useState('');const page=anchor?.selector.page||1;
 useEffect(()=>{
  if(!profile||profile.kind!=='pdf'){setImage('');return;}
  const abort=new AbortController();let objectURL='';setImage('');setProblem('');
  fetch(`/api/sessions/${sessionId}/sources/${profile.source_id}/pages/${page}`,{signal:abort.signal,credentials:'same-origin'})
   .then(async r=>{if(!r.ok)throw new Error('该页预览暂不可用，已保留文本与来源定位。');objectURL=URL.createObjectURL(await r.blob());setImage(objectURL);})
   .catch(e=>{if(e.name!=='AbortError')setProblem(String(e.message));});
  return()=>{abort.abort();if(objectURL)URL.revokeObjectURL(objectURL);};
 },[sessionId,profile?.source_id,page]);
 if(!profile)return <div className="empty">探查后将在此显示来源内容。</div>;
 const metadata=profile.metadata||{};
 const pages=(metadata.pages||[]) as {page:number;text:string;width:number;height:number;blocks?:{bbox:number[];char_start:number;char_end:number}[]}[];
 const info=pages.find(p=>p.page===page);let box=anchor?.selector.bbox?.map(Number);
 if(!box&&anchor?.selector.kind==='pdf_text_span')box=info?.blocks?.find(b=>b.char_start<=(anchor.selector.char_start||0)&&b.char_end>=(anchor.selector.char_end||0))?.bbox;
 const keys=anchor?.selector.keys;
 const recordLocation=keys&&('row' in keys? `来源行 ${display(keys.row)}`:
  Object.entries(keys).map(([key,value])=>`${key} = ${display(value)}`).join(' · '));
 const rowStart=Math.max(0,recordIndex-15);
 return <div className="source-viewer"><div className="source-meta"><span className="badge">{profile.kind.toUpperCase()}</span><span>{profile.coverage==='full'?'当前范围已探查':profile.coverage==='sampled'?'样本探查':profile.coverage==='partial'?'部分结果':'范围待确认'}</span></div>
 {profile.kind==='pdf'?<><div className="source-location">第 {page} 页 / {String(metadata.total_pages||'?')} 页</div><div className="pdf-page">
  {image?<><img src={image} alt={`原始材料第 ${page} 页`}/>{box&&info?.width&&<div className="source-highlight" aria-label="来源高亮" style={{left:`${box[0]/info.width*100}%`,top:`${box[1]/info.height*100}%`,width:`${(box[2]-box[0])/info.width*100}%`,height:`${(box[3]-box[1])/info.height*100}%`}}/>}</>:<p className="muted">{problem||'正在读取页面…'}</p>}
 </div>{info?.text&&<details><summary>查看文本与精确位置</summary><pre className="source-text">{anchor?.selector.kind==='pdf_text_span'?<>{info.text.slice(0,anchor.selector.char_start)}<mark>{info.text.slice(anchor.selector.char_start,anchor.selector.char_end)}</mark>{info.text.slice(anchor.selector.char_end)}</>:info.text}</pre></details>}</>:
 <div className="source-table-scroll"><table className="source-table"><thead><tr><th>#</th>{profile.fields?.map(f=><th key={f}>{f}</th>)}</tr></thead><tbody>{profile.records?.slice(rowStart,rowStart+30).map((row,index)=>{
  const i=rowStart+index;
  return <tr key={i} className={i===recordIndex?'selected-source-row':''}><th>{i+1}</th>{profile.fields?.map(field=><td key={field} className={i===recordIndex&&sourceField===field?'selected-cell':''}>{display(row[field])}</td>)}</tr>;
 })}</tbody></table></div>}
 {(profile.gaps||[]).length>0&&<div className="notice amber">{profile.gaps?.length} 处待补充：{profile.gaps?.map(g=>`分区 ${g.partition} · ${g.code==='ocr_engine_missing'?'需要 OCR 引擎':g.code}`).join('；')}</div>}
 <div className="source-location">{anchor?.selector.kind==='excel_cell'?`${anchor.selector.sheet} · ${anchor.selector.range}`:anchor?.selector.kind==='record_key'?recordLocation:anchor?.selector.kind==='json_pointer'?anchor.selector.pointer:''}</div>
 </div>;
}
