import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *
from dataagent_runtime.enforcement import egress_check
policy = PolicyDocument(policy_id="tenant:default", revision="r1", rules=[
    PolicyRule(rule_id="a", effect="allow", subjects=["user:alice"], resources=["content"], purposes=["monthly_report"])],
    egress_rules=[EgressRule(rule_id="vendor", effect="allow", deployments=["vendor_api"])])
rt = make_rt(policy)
raw = {"statement": "联系人手机 13800138000"}
ref = content_ref(rt, raw)
acc = invoke("check_access_scope", {"resource_ref": f"{ref.id}@{ref.revision}"}, ctx(), runtime=rt).data.decision
eg = invoke("check_model_context_egress", {"content_refs": [str(ref)], "destination": {"model_ref": "vx", "deployment": "vendor_api"},
    "access_decision_ref": acc.decision_id}, ctx(), runtime=rt).data
print("egress decision:", eg.decision.decision.value, "masking_ref", eg.decision.masking_ref)
masked_payload = rt.content.get_json(eg.masking.masked_content_ref)
req = {"content_refs": [str(ref)], "destination": {"model_ref": "vx", "deployment": "vendor_api"},
       "egress_decision_ref": eg.decision.decision_id, "statement": raw["statement"]}
out = egress_check(req, get_egress=rt.decisions.get_egress, load_masked=lambda m: masked_payload)
print("[R8] allow_masked, raw under 'statement' ->", out.allowed, "statement still raw:", out.request.get("statement"), "| content:", out.request.get("content"))
# allow path: content key bound, but other keys are not
policy2 = policy.model_copy(update={"revision": "r2"})
rt2 = make_rt(PolicyDocument(policy_id="tenant:default", revision="r1", rules=policy.rules,
      egress_rules=[EgressRule(rule_id="local", effect="allow", deployments=["local"])]))
clean = content_ref(rt2, {"statement": "金额不超过 100"})
acc2 = invoke("check_access_scope", {"resource_ref": f"{clean.id}@{clean.revision}"}, ctx(), runtime=rt2).data.decision
eg2 = invoke("check_model_context_egress", {"content_refs": [str(clean)], "destination": {"model_ref": "m", "deployment": "local"},
    "access_decision_ref": acc2.decision_id}, ctx(), runtime=rt2).data.decision
req2 = {"content_refs": [str(clean)], "destination": {"model_ref": "m", "deployment": "local"}, "egress_decision_ref": eg2.decision_id,
        "statement": "完全不同的未审批内容 13800138000", "table": [["secret", 1]]}
out2 = egress_check(req2, get_egress=rt2.decisions.get_egress)
print("[R8] allow, unrelated payload under non-'content' keys ->", out2.allowed, list(out2.request))
