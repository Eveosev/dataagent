"""R3: rule-judgment semantics gaps.
a) condition declared unsupported is dropped from the spec without a trace -> verdict pass.
b) table evaluation truncated by max_rows still yields overall verdict pass.
c) fields[] omitted -> fabricated field ids / type check skipped.
d) same spec over two different records -> identical assessment_id and target_ref.
e) exception spec carries no engine_binding; rule.applicability_ref ignored when caller omits flag.
"""
import sys
sys.path.insert(0, "/tmp/claude-502/application")
from repro_common import *  # noqa

rt = make_runtime("warn")
RULE = {"statement": "报销金额超过 5000 需主管审批",
        "conditions": [
            {"condition_id": "c1", "text": "金额 > 5000", "referenced_fields": ["amount"]},
            {"condition_id": "c2", "text": "有主管审批记录且审批人非本人", "referenced_fields": ["approver"]}],
        "combination": "c1 and c2",
        "applicability_ref": "rule:applies-only-to-travel"}
FIELDS = [{"field_id": "amount", "value_type": "number"}, {"field_id": "approver", "value_type": "string"}]
gt = {"op": "gt", "args": [{"op": "field", "field_id": "amount", "condition_id": "c1"}, {"op": "literal", "value": 5000}]}

gen = show("a gen with c2 unsupported", invoke("generate_function_expressions", {
    "rule": RULE, "fields": FIELDS, "proposal": {"expression": gt, "unsupported_conditions": ["c2"]}}, ctx(), runtime=rt))
spec = gen.data.spec.model_dump(mode="json")
print("   spec keys:", sorted(spec), "-> no record of unsupported c2")


def rec(amount, approver_status="missing"):
    return {"asset": {"id": f"rec:{amount}", "kind": "extracted_record", "scope_ref": "scope-1", "revision": "r1",
                      "resolver": "content", "locator": "x"},
            "document_ref": {"id": "doc:1", "revision": "r1"}, "target_schema_ref": {"id": "schema:x", "revision": "r1"},
            "fields": [{"field_id": "amount", "status": "extracted", "value": amount, "value_type": "number",
                        "evidence": [{"source_ref": "doc:1", "source_revision": "r1", "selector": {"kind": "text_span", "unit_ref": "u", "char_start": 0, "char_end": 4}}]},
                       {"field_id": "approver", "status": approver_status, "value": None, "value_type": "string"}]}

try:
    r1 = show("a eval amount=6200 approver missing", invoke("evaluate_scalar_expression", {"spec": spec, "record": rec(6200)}, ctx(), runtime=rt))
    print("   verdict:", r1.data.assessment.verdict, "(rule c1 and c2 with c2 unknown must be unknown)")
    r2 = invoke("evaluate_scalar_expression", {"spec": spec, "record": rec(7000)}, ctx(), runtime=rt)
    print("d  ids:", r1.data.assessment.assessment_id, r2.data.assessment.assessment_id,
          "targets:", r1.data.assessment.target_ref, r2.data.assessment.target_ref)
except Exception as e:  # record shape mismatch
    print("record build failed:", e)

# b) truncation
_, tref, _ = store_table(rt, [{"name": "a", "field_id": "amount", "value_type": "number"}], [[6000], [10]])
spec2 = {"spec_id": "e2", "revision": "r1", "backend_kind": "expression", "expression_or_call": gt}
res = show("b table max_rows=1", invoke("evaluate_table_expression", {"spec": spec2, "table_ref": tref, "max_rows": 1}, ctx(), runtime=rt))
print("   overall verdict:", res.data.assessment.verdict, "counts:", res.data.counts, "(row 2 fails)")

# c) fields omitted
fake = {"op": "and", "args": [
    {"op": "gt", "args": [{"op": "field", "field_id": "amount_made_up", "condition_id": "c1"}, {"op": "literal", "value": "abc"}]},
    {"op": "eq", "args": [{"op": "field", "field_id": "nonexistent", "condition_id": "c2"}, {"op": "literal", "value": 1}]}]}
show("c fields omitted, fabricated ids", invoke("generate_function_expressions", {
    "rule": {k: v for k, v in RULE.items() if k != "applicability_ref"}, "proposal": {"expression": fake}}, ctx(), runtime=rt))

# e) exception spec binding
RULE_E = dict(RULE, exceptions=[{"text": "金额小于 100 免审"}])
both = {"op": "and", "args": [gt, {"op": "is_missing", "args": [{"op": "field", "field_id": "approver", "condition_id": "c2"}]}]}
both = {"op": "and", "args": [gt, {"op": "ne", "args": [{"op": "field", "field_id": "approver", "condition_id": "c2"}, {"op": "literal", "value": ""}]}]}
show("e2 natural not(is_missing) for c2", invoke("generate_function_expressions", {
    "rule": RULE, "fields": FIELDS, "proposal": {"expression": {"op": "and", "args": [gt, {"op": "not", "args": [{"op": "is_missing", "args": [{"op": "field", "field_id": "approver", "condition_id": "c2"}]}]}]}}}, ctx(), runtime=rt))
exc = {"op": "lt", "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 100}]}
g = show("e gen with exception", invoke("generate_function_expressions", {
    "rule": RULE_E, "fields": FIELDS, "proposal": {"expression": both, "exceptions": [exc]}}, ctx(), runtime=rt))
print("   exception spec engine_binding:", g.data.exception_specs[0].engine_binding, "spec_id:", g.data.exception_specs[0].spec_id)

# f) non-boolean operand in logic ops (spec not produced by DA06.3.5)
for op in ("and", "or"):
    sp = {"spec_id": "f"+op, "revision": "r1", "backend_kind": "expression",
          "expression_or_call": {"op": op, "args": [{"op": "literal", "value": "张三"}]}}
    rr = invoke("evaluate_scalar_expression", {"spec": sp, "record": rec(1)}, ctx(), runtime=rt)
    print(f"f  {op}('张三') ->", rr.status.value, rr.data.assessment.verdict if rr.data else rr.issues[0].code)
# g) invalid inline record -> execution_unknown instead of invalid_input
rr = invoke("evaluate_scalar_expression", {"spec": spec, "record": {"asset": {}}}, ctx(), runtime=rt)
print("g  bad record ->", rr.status.value, rr.issues[0].code)
