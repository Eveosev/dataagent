import hashlib, tempfile, pathlib, json
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_data.runtime import create as create_data
from dataagent_data.invoke import invoke as data_invoke
import dataagent_application.registry as areg; areg.load_operations()
from dataagent_runtime.invoke import invoke as rt_invoke
ENF = EnforcementConfig(mode="enforce")
tmp = pathlib.Path(tempfile.mkdtemp(dir=__import__("os").environ["TMPDIR"]))
(tmp/"orders.csv").write_bytes(b"order_id,region,amount\no1,north,100\no2,south,200\n")
b=(tmp/"orders.csv").read_bytes(); d="sha256:"+hashlib.sha256(b).hexdigest()
fr={"id":f"file:{d[7:23]}","kind":"file","scope_ref":"tenant:demo","revision":d,"resolver":"workspace","locator":"orders.csv","digest":d,"media_type":"text/csv","filename":"orders.csv","size_bytes":len(b),"content_digest":d}
ctx=lambda a:{"request_id":"r","scope_ref":"tenant:demo","authorization_ref":a,"subject_ref":"user:alice","purpose":"monthly_report"}
drt=create_data(workspace_root=tmp, data_root=tmp/".dataagent")  # warn default to seed table
p=data_invoke("parse_delimited_file",{"file_ref":fr},ctx("seed"),runtime=drt)
table=p.data.table.model_dump(mode="json")
# 1. application execute_duckdb_sql under enforce with a bogus authorization
from dataagent_runtime.runtime import Runtime
art=Runtime.create(workspace_root=tmp, data_root=tmp/".dataagent", enforcement=ENF)
print("app runtime enforcement:", getattr(art,"enforcement",None))
name="t_"+table["asset"]["id"].split(":",1)[1]
r=rt_invoke("execute_duckdb_sql",{"spec":{"spec_id":"x","revision":"r1","backend_kind":"sql","expression_or_call":{"sql":f'SELECT SUM(c3) FROM "{name}"',"dialect":"duckdb"},"source_refs":[{"id":table["asset"]["id"],"revision":table["asset"]["revision"]}]},"table_refs":[table],"unit":"CNY","grain":"all"},ctx("ad:totally-bogus"),runtime=art,enforcement=ENF)
print("execute_duckdb_sql bogus auth:", r.status, r.data.result.value if r.data else None, [i.code for i in r.issues])
print("engine_binding in result:", r.data.result.model_dump(mode="json").get("engine_binding") if r.data else None)
# 2. data-layer op without resource_fields under enforce, bogus auth
denf=create_data(workspace_root=tmp, data_root=tmp/".dataagent", enforcement=ENF)
import dataagent_data.registry as dreg; dreg.load_operations()
nores=[s.operation for s in dreg.list_operations() if s.source_file.startswith("src/dataagent_data/") and not s.resource_fields]
print("data ops w/o resource_fields:", nores)
r2=data_invoke("append_task_event",{},ctx("ad:totally-bogus"),runtime=denf)
print("append_task_event bogus auth:", r2.status, [i.code for i in r2.issues][:3])
for eb in ({"engine_id":"duckdb","engine_version":"2.0.0"},{"engine_id":"sqlite","engine_version":"3"}):
    spec={"spec_id":"x","revision":"r1","backend_kind":"sql","expression_or_call":{"sql":f'SELECT SUM(c3) FROM "{name}"',"dialect":"duckdb"},"source_refs":[{"id":table["asset"]["id"],"revision":table["asset"]["revision"]}],"engine_binding":eb}
    r=rt_invoke("execute_duckdb_sql",{"spec":spec,"table_refs":[table],"unit":"CNY","grain":"all"},ctx("ad:totally-bogus"),runtime=art,enforcement=ENF)
    print("binding",eb,"->",r.status,[ (i.code,i.message[:80]) for i in r.issues][:2])
# no metric/requirement: SUM over a non-measure arbitrary sql
r=rt_invoke("execute_duckdb_sql",{"spec":{"spec_id":"y","revision":"r1","backend_kind":"sql","expression_or_call":{"sql":f'SELECT SUM(c3)*2 FROM "{name}" WHERE c2=\'north\'',"dialect":"duckdb"},"source_refs":[{"id":table["asset"]["id"],"revision":table["asset"]["revision"]}]},"table_refs":[table],"unit":"CNY","grain":"all"},ctx("ad:totally-bogus"),runtime=art,enforcement=ENF)
print("unbound transformed sql ->", r.status, r.data.result.value if r.data else None, [i.code for i in r.issues])
