# R1: packaged MCP descriptor sets no host authority -> Agent-written arguments.context picks subject/purpose
import sys, os, json; sys.path.insert(0, os.path.dirname(__file__))
from common import *
from dataagent_runtime.interfaces.mcp_server import handle
import dataagent_governance.runtime.runtime as grt
policy = PolicyDocument(policy_id="tenant:default", revision="r1", rules=[
    PolicyRule(rule_id="admin-payroll", effect="allow", subjects=["user:admin"], resources=["table:payroll"], purposes=["audit"]),
])
# exactly what .mcp.json gives the process: DATAAGENT_ENFORCEMENT_MODE=enforce, no DATAAGENT_HOST_* vars
for k in ("DATAAGENT_HOST_SUBJECT_REF", "DATAAGENT_HOST_PURPOSE"): os.environ.pop(k, None)
os.environ["DATAAGENT_ENFORCEMENT_MODE"] = "enforce"
rt = make_rt(policy, subject=None, purpose=None, mode="enforce")
print("host authority:", rt.host_subject_ref, rt.host_purpose, "mode:", rt.enforcement.mode)
def call(name, args):
    from dataagent_runtime.invoke import invoke as inv
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
    resp = handle(msg, server_name="g", server_version="0", list_operations=lambda: [], invoke=lambda op, p, c: inv(op, p, c, runtime=rt))
    return json.loads(resp["result"]["content"][0]["text"])
agent_ctx = {"request_id": "r", "scope_ref": "tenant:demo", "authorization_ref": "x", "subject_ref": "user:admin", "purpose": "audit"}
out = call("check_access_scope", {"resource_ref": "table:payroll@*", "context": agent_ctx})
d = out["data"]["decision"]; print("check_access_scope ->", d["decision"], d["subject_ref"], d["resource_ref"], d["decision_id"])
t = table_ref(rt, "payroll", ["emp", "salary"], [["e1", 100], ["e1", 200]])
args = {"spec": {"spec_id": "s", "revision": "r1", "backend_kind": "sql", "expression_or_call": {"sql": "SELECT emp, salary FROM payroll", "dialect": "duckdb"}},
        "input_tables": [t.model_dump(mode="json")], "output_table": t.model_dump(mode="json"), "declared_grain": ["emp"],
        "context": {**agent_ctx, "authorization_ref": d["decision_id"]}}
out2 = call("check_result_grain_and_merge", args)
print("grain check under enforce ->", out2["status"], [i["code"] for i in out2.get("issues", [])],
      out2["data"]["report"]["items"][0]["evidence"] if out2.get("data") else None)
