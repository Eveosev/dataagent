import os, pathlib, tempfile
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_data.runtime import create
from dataagent_data.invoke import invoke as di
tmp = pathlib.Path(tempfile.mkdtemp(dir=os.environ["TMPDIR"]))
prod = create(workspace_root=tmp, data_root=tmp/".dataagent", enforcement=EnforcementConfig(mode="enforce"))
ctx={"request_id":"r","scope_ref":"tenant:demo","authorization_ref":"ad:totally-bogus","subject_ref":"user:mallory","purpose":"x"}
r = di("append_task_event", {"task_ref":"task:t1@r1","event_id":"e1","actor_ref":"user:mallory","payload":{"note":"x"}}, ctx, runtime=prod)
print("append_task_event enforce + bogus auth:", r.status.value, [(i.code,i.message[:80]) for i in r.issues])
