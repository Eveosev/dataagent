import {useState} from 'react';
import {display,transformNames,propertyLabel,entityTypeLabel,conceptOf} from '../client';
import type {View,FieldBinding,CorrectionView} from '../client';
export function MappingDetail({view,field,binding,raw,dirty,recordIndex,onCorrect,onAdopt,onSchema,readOnly}:{readOnly:boolean;view:View;field:string;binding?:FieldBinding;raw:unknown;dirty:boolean;recordIndex:number;onCorrect:(value:string,reason:string)=>Promise<void>;onAdopt:(correction:CorrectionView)=>Promise<void>;onSchema:(name:string,reason:string)=>Promise<void>}){
 const [range,setRange]=useState('mapping');const [value,setValue]=useState('');const [reason,setReason]=useState('');const [name,setName]=useState('');const [busy,setBusy]=useState(false);
 const instance=view.preview?.instances?.[recordIndex];
 const correction=view.correction_views?.find(item=>item.entity_id===instance?.id&&item.property===field);
 async function save(){setBusy(true);try{range==='instance'?await onCorrect(value,reason):await onSchema(name,reason);}finally{setBusy(false);}}
 async function adopt(){if(!correction)return;setBusy(true);try{await onAdopt(correction);}finally{setBusy(false);}}
 return <aside className="detail-panel"><div className="panel-heading"><span>字段详情</span><span className="badge">{entityTypeLabel(conceptOf(view.ontology,view.ontology_concept).entity_type)}</span></div><h2 title={field}>{field?propertyLabel(field):'选择一个目标字段'}</h2>
 {field&&<><dl className="field-comparison"><div><dt>来源值</dt><dd>{display(raw)}</dd></div><div><dt>转换方式</dt><dd>{transformNames[binding?.transform||'identity']}</dd></div><div className="after-value"><dt>本体值</dt><dd data-testid={`preview-${field}`}>{dirty?'待更新':display(instance?.values?.[field])}</dd></div></dl>
 {correction&&!dirty&&<div className="notice amber correction-conflict" data-testid="mapping-correction-hint"><strong>{propertyLabel(field)}：映射已变化，纠正值仍生效；映射新算得的值为 {display(correction.mapping_value)}</strong>
  {!readOnly&&<button className="secondary" disabled={busy} onClick={adopt}>采用新映射值</button>}</div>}
 {!readOnly&&<><label className="label">修改范围</label><div className="range-options">{[['mapping','修改这类来源的映射'],['instance','纠正当前对象的值'],['ontology','提出本体调整']].map(([id,label])=><label key={id}><input type="radio" name="range" value={id} checked={range===id} onChange={()=>setRange(id)}/>{label}</label>)}</div>
 {range==='mapping'?<p className="help">在映射表中选择来源字段和转换方式，生成新预览后核对。保存后的映射可用于符合条件的新材料。</p>:<div className="edit-current">
  <label className="label">{range==='instance'?'纠正后的值':'建议新增的属性名'}</label><input aria-label={range==='instance'?'纠正后的值':'建议新增的属性名'} value={range==='instance'?value:name} onChange={e=>range==='instance'?setValue(e.target.value):setName(e.target.value)}/>
  <label className="label" htmlFor="correction-reason">修改原因</label><textarea id="correction-reason" rows={3} value={reason} onChange={e=>setReason(e.target.value)}/>
  <p className="help">{range==='instance'?'保留来源原值，将本次纠正作为用户证据保存并重新校验。':'生成独立本体草案，正式定义经审核后再产生新修订。'}</p>
  <button className="secondary" disabled={busy||!reason.trim()||(range==='instance'?!instance||!value.trim():!name.trim())} onClick={save}>{range==='instance'?'保存当前值并校验':'提交本体调整草案'}</button>
 </div>}</>}</>}
 </aside>;
}
