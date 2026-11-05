import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from common import *
from dataagent_governance.governance.sensitivity import scan_content
samples = {
  "id_card_in_chinese_text": "申请人身份证110101199003077774号，已核验",
  "id_card_ascii_context": "id 110101199003077774 ok",
  "phone_dashed": "联系电话 138-0013-8000",
  "phone_spaced_+86": "+86 138 0013 8000",
  "bank_card_spaced": "卡号 6222 0202 0000 0000 006",
  "bank_card_plain": "6222020200000000006",
}
from dataagent_governance.governance.sensitivity import _id_card_ok, _luhn_ok
print("checksum sanity: id", _id_card_ok("110101199003077774"), "luhn", _luhn_ok("6222020200000000006"))
for k, v in samples.items():
    print(f"{k:28s} findings={[f.kind for f in scan_content(v, []).findings]}")
# end to end: vendor_api egress of the Chinese-text ID card
policy = PolicyDocument(policy_id="tenant:default", revision="r1", rules=[
    PolicyRule(rule_id="a", effect="allow", subjects=["user:alice"], resources=["content"], purposes=["monthly_report"])],
    egress_rules=[EgressRule(rule_id="vendor", effect="allow", deployments=["vendor_api"])])
rt = make_rt(policy)
ref = content_ref(rt, {"blocks": [{"text": samples["id_card_in_chinese_text"]}, {"text": samples["phone_dashed"]}]})
acc = invoke("check_access_scope", {"resource_ref": f"{ref.id}@{ref.revision}"}, ctx(), runtime=rt).data.decision
r = invoke("check_model_context_egress", {"content_refs": [str(ref)], "destination": {"model_ref": "vendor-x", "deployment": "vendor_api"},
    "access_decision_ref": acc.decision_id}, ctx(), runtime=rt)
print("vendor_api egress ->", r.status, r.issues and r.issues[0].message, r.data and (r.data.decision.decision.value, len(r.data.sensitivity.findings)))
