import tempfile, pathlib, json
from dataagent_contracts.core import CallContext, AccessDecision
from dataagent_data.runtime import create
from dataagent_data.invoke import invoke
print("deadline:", CallContext.model_fields["deadline"].annotation)
print("valid_until:", AccessDecision.model_fields["valid_until"].annotation)
base = pathlib.Path(tempfile.mkdtemp(dir="/tmp/claude-502/data"))
rt = create(workspace_root=base, data_root=base/".d")
ctx = {"request_id":"r","scope_ref":"s","authorization_ref":"a","deadline":"2020-01-01T00:00:00"}
try:
    r = invoke("append_task_event", {"task_ref":"task:x@r1","event_id":"e1","actor_ref":"u"}, ctx, runtime=rt)
    print("naive deadline ->", r.status.value, [i.message for i in r.issues])
except Exception as e:
    print("naive deadline -> EXCEPTION", type(e).__name__, e)
import os
os.environ["DATAAGENT_HOST_SUBJECT_REF"]="user:host"; os.environ["DATAAGENT_HOST_PURPOSE"]="host_purpose"
rt2 = create(workspace_root=base, data_root=base/".d2")
print("data-layer runtime host_subject_ref/purpose:", rt2.host_subject_ref, rt2.host_purpose)
from dataagent_runtime.runtime import Runtime
rt3 = Runtime.create(workspace_root=base, data_root=base/".d3")
print("shared Runtime.create host_subject_ref/purpose:", rt3.host_subject_ref, rt3.host_purpose)
