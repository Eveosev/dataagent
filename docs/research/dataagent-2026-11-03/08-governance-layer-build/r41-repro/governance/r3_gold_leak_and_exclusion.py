import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *
policy = PolicyDocument(policy_id="tenant:default", revision="r1", rules=[
    PolicyRule(rule_id="allow-orders", effect="allow", subjects=["user:alice"], resources=["table:orders"], purposes=["monthly_report"])],
    egress_rules=[EgressRule(rule_id="local", effect="allow", deployments=["local"])])
rt = make_rt(policy)
crit = draft_and_confirm(rt, COMPUTE)
golds = [[{"metric_id": "metric:monthly_total", "expected_value": 1000.0 + i * 111, "unit": "CNY", "grain": "月"}] for i in range(4)]
set_ref, cases = isolate(rt, golds)
print("unseen count:", set_ref.counts)
def evaluate(deliveries):
    r = invoke("evaluate_business_acceptance", {"criteria_ref": f"{crit.id}@{crit.revision}",
        "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}", "deliveries": deliveries}, ctx(), runtime=rt)
    assert r.status == "ok", r.issues
    return r.data.report
# --- R3: one garbage run returns every gold value in CaseResult.notes, no exposure recorded
rep = evaluate([computed(c["case_id"], 0.0) for c in cases])
print("[R3] overall", rep.overall, "notes:", [c.notes for c in rep.cases])
print("[R3] exposed digests after evaluation:", len(rt.vault.exposed_digests()))
# --- R4: deliver correct values for c0,c1 (learned from notes), wrong for c2,c3; then expose c2,c3 gold
#         through an ordinary MCP-reachable operation (egress check reads the cited content first)
access = invoke("check_access_scope", {"resource_ref": "table:orders@*"}, ctx(), runtime=rt).data.decision
for c in cases[2:]:
    ref = c["expected_ref"]
    r = invoke("check_model_context_egress", {"content_refs": [ref], "destination": {"model_ref": "m", "deployment": "local"},
               "access_decision_ref": access.decision_id}, ctx(), runtime=rt)
    print("[R4] egress on gold", c["case_id"], "->", r.status, r.issues[0].message[:60] if r.issues else "")
deliv = [computed("c0", 1000.0), computed("c1", 1111.0), computed("c2", 0.0), computed("c3", 0.0)]
rep = evaluate(deliv)
m = rep.metrics
print("[R4] overall", rep.overall, "cases", [(c.case_id, c.verdict) for c in rep.cases],
      "quality", m.quality[0].numerator, "/", m.quality[0].denominator, "coverage", m.coverage.covered, "/", m.coverage.total)
print("[R4] coverage_scope:", rep.coverage_scope); print("[R4] limits:", rep.limits)
