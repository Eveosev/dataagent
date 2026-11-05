import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *
from dataagent_governance.evaluation.criteria_samples import _digest, CRITERIA_KIND, confirm_acceptance_criteria
from datetime import datetime, timezone
from dataagent_runtime.enforcement import access_recheck, EnforcementConfig
from dataagent_contracts.core import CallContext
# --- confirmation: self-declared confirmer, ancient timestamp, arbitrary authority_ref
rt = make_rt(PolicyDocument(policy_id="tenant:default", revision="r1"))
r = invoke("draft_acceptance_criteria", {"delivery_target": "t", "proposal": JUDGMENT}, ctx(), runtime=rt).data.criteria
payload = rt.versions.get(CRITERIA_KIND, r.id, r.revision)
conf = CriteriaConfirmation(confirmation_id="c-forged", criteria_id=r.id, criteria_revision=r.revision, criteria_digest=_digest(payload),
    confirmer_ref="user:boss", confirmed_at=datetime(2000, 1, 1, tzinfo=timezone.utc), authority_ref="anything")
act = confirm_acceptance_criteria(rt, r.id, r.revision, conf, authorized_confirmers={"user:boss"})
print("[R10] confirmation dated 2000-01-01, body-declared confirmer, authority 'anything' ->", act.status.value, act.confirmation_ref)
# --- subject check skipped when ctx.subject_ref is None
policy = PolicyDocument(policy_id="tenant:default", revision="r1", rules=[
    PolicyRule(rule_id="a", effect="allow", subjects=["user:admin"], resources=["table:payroll"], purposes=["audit"],
               field_constraints=["emp"])])
rt2 = make_rt(policy, subject="user:admin", purpose="audit")
dec = invoke("check_access_scope", {"resource_ref": "table:payroll@*"}, ctx(), runtime=rt2).data.decision
c = CallContext(request_id="r", scope_ref="s", authorization_ref=dec.decision_id, purpose="audit")  # no subject
out = access_recheck(c, rt2.decisions.get_access, [VersionedRef(id="table:payroll", revision="x")], config=EnforcementConfig(mode="enforce"))
print("[R1b] recheck with subject_ref omitted ->", out.ok)
# --- field_constraints not enforced on read
print("[R11] decision field_constraints:", dec.field_constraints)
t = table_ref(rt2, "payroll", ["emp", "salary"], [["e1", 100], ["e2", 999]])
body = {"spec": {"spec_id": "s", "revision": "r1", "backend_kind": "sql", "expression_or_call": {"sql": "SELECT emp, salary FROM payroll", "dialect": "duckdb"}},
        "input_tables": [t.model_dump(mode="json")], "output_table": t.model_dump(mode="json"), "declared_grain": ["salary"], "measure_fields": ["salary"]}
g = invoke("check_result_grain_and_merge", body, ctx(authorization_ref=dec.decision_id), runtime=rt2)
print("[R11] grain check reading non-visible 'salary' ->", g.status, g.data.report.items[0].details, g.data.report.items[2].evidence)
# --- join direction false positive
rt3 = make_rt(PolicyDocument(policy_id="tenant:default", revision="r1", rules=[
    PolicyRule(rule_id="t", effect="allow", subjects=["user:alice"], resources=["table:*"], purposes=["monthly_report"])]))
auth = invoke("check_access_scope", {"resource_ref": "table@*"}, ctx(), runtime=rt3).data.decision.decision_id
orders = table_ref(rt3, "orders", ["order_id", "region", "amount"], [["o1", "n", 1], ["o2", "n", 2], ["o3", "s", 3]])
regions = table_ref(rt3, "regions", ["region", "label"], [["n", "North"], ["s", "South"]])
out_t = table_ref(rt3, "out", ["order_id", "region", "amount"], [["o1", "n", 1], ["o2", "n", 2], ["o3", "s", 3]])
for sql in ["SELECT o.order_id, o.region, o.amount FROM orders o JOIN regions r ON o.region = r.region",
            "SELECT o.order_id, o.region, o.amount FROM regions r JOIN orders o ON r.region = o.region"]:
    body = {"spec": {"spec_id": "s", "revision": "r1", "backend_kind": "sql", "expression_or_call": {"sql": sql, "dialect": "duckdb"}},
            "input_tables": [orders.model_dump(mode="json"), regions.model_dump(mode="json")], "output_table": out_t.model_dump(mode="json"),
            "declared_grain": ["order_id"]}
    g = invoke("check_result_grain_and_merge", body, ctx(authorization_ref=auth), runtime=rt3)
    j = g.data.report.items[1]
    print("[R12]", sql.split("FROM")[1].strip()[:40], "->", j.outcome, "| grain:", g.data.report.items[0].outcome, "| output rows 3 = orders rows 3")
