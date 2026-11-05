# R2: authorization_ref "policy:<anything>" resolves to an allow over table@* -> explicit deny on table:secret bypassed
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *
policy = PolicyDocument(policy_id="tenant:default", revision="r1", rules=[
    PolicyRule(rule_id="allow-all-tables", effect="allow", subjects=["user:alice"], resources=["table:*"], purposes=["monthly_report"]),
    PolicyRule(rule_id="deny-secret", effect="deny", subjects=["*"], resources=["table:secret"], purposes=["*"]),
])
rt = make_rt(policy)
direct = invoke("check_access_scope", {"resource_ref": "table:secret@*"}, ctx(), runtime=rt)
print("direct check_access_scope(table:secret) ->", direct.data.decision.decision.value)
d = rt.access_resolver("policy:does-not-exist@r999")
print("access_resolver('policy:does-not-exist@r999') ->", d.decision.value, d.resource_ref, d.policy_ref)
t = table_ref(rt, "secret", ["k", "v"], [["a", 1], ["b", 2]])
body = {"spec": {"spec_id": "s", "revision": "r1", "backend_kind": "sql", "expression_or_call": {"sql": "SELECT k, v FROM secret", "dialect": "duckdb"}},
        "input_tables": [t.model_dump(mode="json")], "output_table": t.model_dump(mode="json"), "declared_grain": ["k"], "measure_fields": ["v"]}
r = invoke("check_result_grain_and_merge", body, ctx(authorization_ref="policy:does-not-exist@r999"), runtime=rt)
print("grain check on table:secret, enforce, authorization_ref=policy:... ->", r.status, [i.code for i in r.issues])
print("evidence leaked:", r.data.report.items[2].evidence if r.data else None)
