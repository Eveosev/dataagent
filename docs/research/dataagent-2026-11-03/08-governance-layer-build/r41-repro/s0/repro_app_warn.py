import os, json, pathlib, tempfile
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.runtime import Runtime
import dataagent_application.registry as ar; ar.load_operations()
from dataagent_runtime.invoke import invoke
tmp = pathlib.Path(tempfile.mkdtemp(dir=os.environ["TMPDIR"]))
rule={"statement":"SECRET-RULE amount is below 5000","conditions":[{"condition_id":"c1","text":"amount <= 5000","referenced_fields":["amount"]}],"combination":"c1"}
ctx={"request_id":"r","scope_ref":"tenant:demo","authorization_ref":"ad:bogus","subject_ref":"user:alice","purpose":"monthly_report"}
for mode in (None, "enforce"):
    os.environ.pop("DATAAGENT_ENFORCEMENT_MODE", None)
    if mode: os.environ["DATAAGENT_ENFORCEMENT_MODE"]=mode
    rt = Runtime.create(workspace_root=tmp, data_root=tmp/".dataagent")
    r = invoke("generate_function_expressions", {"rule":rule,"fields":[{"field_id":"amount","value_type":"number"}]}, ctx, runtime=rt)
    s = json.dumps(r.model_dump(mode="json"), ensure_ascii=False)
    print(f"env mode={mode!s:8} runtime={rt.enforcement.mode:8} status={r.status.value} leaks SECRET-RULE={'SECRET-RULE' in s} codes={[i.code for i in r.issues]}")
