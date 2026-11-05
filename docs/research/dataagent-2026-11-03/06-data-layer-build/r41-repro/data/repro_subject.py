import hashlib, tempfile, pathlib, json, os, subprocess, sys
from dataagent_contracts.core import AccessDecision, AccessOutcome, VersionedRef
from dataagent_data.runtime import create
base = pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-502/data")); ws = base/"ws"; ws.mkdir()
(ws/"orders.csv").write_bytes(b"a,b\n1,2\n")
p=(ws/"orders.csv").read_bytes(); d="sha256:"+hashlib.sha256(p).hexdigest()
fr={"id":f"file:{d[7:23]}","kind":"file","scope_ref":"t","revision":d,"resolver":"workspace","locator":"orders.csv","digest":d,"media_type":"text/csv","filename":"orders.csv","size_bytes":len(p),"content_digest":d}
rt=create(workspace_root=ws, data_root=base/"data")
rt.decisions.save_access(AccessDecision(decision_id="ad:alice", policy_ref=VersionedRef(id="policy:t",revision="r1"),
  subject_ref="user:alice", resource_ref=VersionedRef(id=fr["id"],revision="*"), purpose="report",
  decision=AccessOutcome.allow, valid_until="2030-01-01T00:00:00Z"))
# Real MCP subprocess in enforce mode, the way .mcp.json launches it
env=dict(os.environ, DATAAGENT_ENFORCEMENT_MODE="enforce", DATAAGENT_WORKSPACE=str(ws), DATAAGENT_DATA_ROOT=str(base/"data"),
         DATAAGENT_HOST_SUBJECT_REF="user:alice", DATAAGENT_HOST_PURPOSE="audit")
def call(i, ctx, meta=None):
    params={"name":"parse_delimited_file","arguments":{"file_ref":fr,"context":ctx}}
    if meta: params["_meta"]={"context":meta}
    return {"jsonrpc":"2.0","id":i,"method":"tools/call","params":params}
msgs=[call(1,{"request_id":"r","scope_ref":"t","authorization_ref":"ad:alice","subject_ref":"user:mallory","purpose":"report"}),
      call(2,{"request_id":"r","scope_ref":"t","authorization_ref":"ad:alice","purpose":"report"}),
      call(3,{"request_id":"r","scope_ref":"t","authorization_ref":"ad:alice","purpose":"report"},
           meta={"request_id":"r","scope_ref":"t","authorization_ref":"ad:alice","subject_ref":"user:mallory","purpose":"other"})]
out=subprocess.run([sys.executable,"-m","dataagent_data.interfaces.mcp_server"],input="\n".join(json.dumps(m) for m in msgs)+"\n",
                   capture_output=True,text=True,env=env).stdout
labels={1:"subject=mallory",2:"subject omitted (HOST_SUBJECT_REF=user:alice, HOST_PURPOSE=audit set in env)",3:"args.context omits subject, _meta.context says mallory/other"}
for line in out.splitlines():
    m=json.loads(line); res=json.loads(m["result"]["content"][0]["text"])
    print(labels[m["id"]],"->",res["status"],[i["message"][:90] for i in res["issues"]])
