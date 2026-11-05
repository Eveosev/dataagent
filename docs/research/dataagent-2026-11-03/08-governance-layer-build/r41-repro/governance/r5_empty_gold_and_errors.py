import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *
policy = PolicyDocument(policy_id="tenant:default", revision="r1", rules=[])
rt = make_rt(policy)
crit = draft_and_confirm(rt, JUDGMENT)
set_ref, cases = isolate(rt, [[], []])   # gold content is an empty list
r = invoke("evaluate_business_acceptance", {"criteria_ref": f"{crit.id}@{crit.revision}",
    "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
    "deliveries": [assessment(c["case_id"], "fail", target="record:anything@r1") for c in cases]}, ctx(), runtime=rt)
print("[R5] empty gold ->", r.status, r.data.report.overall, [(c.case_id, c.verdict.value) for c in r.data.report.cases])
# isolate accepts expected_ref that does not exist in the store
bogus = "content:x@sha256:" + "0"*64
r2 = invoke("isolate_acceptance_samples", {"cases": [{"case_id": "z", "input_ref": bogus, "expected_ref": bogus}],
    "group_keys": ["g"], "role_weights": {"development": 0, "regression": 0, "unseen_acceptance": 1}, "freeze": True}, ctx(), runtime=rt)
print("[R5b] isolate with missing gold ->", r2.status)
r3 = invoke("evaluate_business_acceptance", {"criteria_ref": f"{crit.id}@{crit.revision}",
    "evaluation_set_ref": f"{r2.data.evaluation_set.id}@{r2.data.evaluation_set.revision}",
    "deliveries": [assessment("z", "pass")]}, ctx(), runtime=rt)
print("[R5b] evaluate ->", r3.status, [(i.code, i.message[:70]) for i in r3.issues])
# draft criteria: precondition violation surfaces as execution_unknown
d = invoke("draft_acceptance_criteria", {"delivery_target": "t", "proposal": JUDGMENT}, ctx(), runtime=rt).data.criteria
r4 = invoke("evaluate_business_acceptance", {"criteria_ref": f"{d.id}@{d.revision}",
    "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}", "deliveries": [assessment("c0", "pass")]}, ctx(), runtime=rt)
print("[R7] draft criteria ->", r4.status, [(i.code, i.retryable, i.message[:60]) for i in r4.issues])
