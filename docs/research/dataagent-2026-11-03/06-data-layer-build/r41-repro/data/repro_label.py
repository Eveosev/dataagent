import hashlib, tempfile, pathlib
from dataagent_contracts.core import AccessDecision, AccessOutcome, VersionedRef
from dataagent_data.runtime import create
from dataagent_data.invoke import invoke
from dataagent_runtime.enforcement import EnforcementConfig
base=pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-502/data")); ws=base/"ws"; ws.mkdir()
(ws/"report.csv").write_bytes(b"k,v\npublic,1\n"); (ws/"secret.csv").write_bytes(b"name,salary\nalice,99999\n")
def fr(id_, rev, name):
    p=(ws/name).read_bytes(); d="sha256:"+hashlib.sha256(p).hexdigest()
    return {"id":id_,"kind":"file","scope_ref":"t","revision":rev,"resolver":"workspace","locator":name,
            "digest":d,"media_type":"text/csv","filename":name,"size_bytes":len(p),"content_digest":d}
rt=create(workspace_root=ws,data_root=base/"d",enforcement=EnforcementConfig(mode="enforce"))
rt.decisions.save_access(AccessDecision(decision_id="ad:report",policy_ref=VersionedRef(id="p",revision="r1"),
  subject_ref="user:alice",resource_ref=VersionedRef(id="file:report",revision="*"),purpose="report",
  decision=AccessOutcome.allow,valid_until="2030-01-01T00:00:00Z"))
ctx={"request_id":"r","scope_ref":"t","authorization_ref":"ad:report","subject_ref":"user:alice","purpose":"report"}
r=invoke("parse_delimited_file",{"file_ref":fr("file:report","rev:1","report.csv")},ctx,runtime=rt); print("legit report.csv:",r.status.value)
r=invoke("parse_delimited_file",{"file_ref":fr("file:report","rev:evil","secret.csv")},ctx,runtime=rt)
print("file:report@rev:evil -> locator secret.csv:",r.status.value,[i.code for i in r.issues])
if r.data:
    t=r.data.table; print("   rows:", rt.content.get_json(t.data_ref).get("rows"))
r=invoke("parse_delimited_file",{"file_ref":fr("file:report/x","rev:1","secret.csv")},ctx,runtime=rt)
print("file:report/x (subtree prefix) -> secret.csv:",r.status.value)
