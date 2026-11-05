import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *
rt = make_rt(PolicyDocument(policy_id="tenant:default", revision="r1"))
cases = [{"case_id": f"c{i}", "input_ref": f"doc:invoice-{i}@r1", "expected_ref": str(content_ref(rt, [{"i": i}])),
          "group_keys": {"g": f"g{i}"}} for i in range(5)]
r = invoke("isolate_acceptance_samples", {"cases": cases, "group_keys": ["g"], "freeze": True}, ctx(), runtime=rt)
print("[R13] 5 distinct inputs with label revision r1 ->", r.status, r.data.evaluation_set.counts, r.data.warnings)
# same input content under two different group keys: only dropped, cross-role warning never emitted
same = str(content_ref(rt, {"x": 1}))
cases2 = [{"case_id": "a", "input_ref": same, "expected_ref": str(content_ref(rt, [{"a": 1}])), "group_keys": {"g": "A"}},
          {"case_id": "b", "input_ref": same.replace("content:", "content:alias-"), "expected_ref": str(content_ref(rt, [{"b": 1}])), "group_keys": {"g": "B"}}]
r2 = invoke("isolate_acceptance_samples", {"cases": cases2, "group_keys": ["g"]}, ctx(), runtime=rt)
print("[R13] ", r2.data.evaluation_set.counts, r2.data.warnings)
