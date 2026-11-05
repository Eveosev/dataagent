import tempfile, json
from datetime import datetime, timezone
from pathlib import Path
from dataagent_contracts.core import VersionedRef, AssetRef, TableRef
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.invoke import invoke
from dataagent_governance.contracts import PolicyDocument, PolicyRule, EgressRule, CriteriaConfirmation
from dataagent_governance.runtime import GovernanceRuntime
from dataagent_governance.registry import load_operations
from dataagent_governance.evaluation.criteria_samples import CRITERIA_KIND, _digest, confirm_acceptance_criteria
load_operations()

def make_rt(policy=None, subject="user:alice", purpose="monthly_report", mode="enforce"):
    d = Path(tempfile.mkdtemp(prefix="gov-", dir=__import__("os").environ.get("TMPDIR")))
    rt = GovernanceRuntime.create(workspace_root=d, data_root=d/".dataagent",
        enforcement=EnforcementConfig(mode=mode), host_subject_ref=subject, host_purpose=purpose)
    if policy is not None:
        rt.policy.save(policy)
    return rt

def ctx(**kw):
    base = dict(request_id="req:1", scope_ref="tenant:demo", authorization_ref="seed",
                subject_ref="user:alice", purpose="monthly_report")
    base.update(kw); return base

def content_ref(rt, payload):
    d = rt.content.put(payload)
    return VersionedRef(id=f"content:{d[7:23]}", revision=d)

def table_ref(rt, name, columns, rows, sheet="t"):
    payload = {"sheet": sheet, "columns": [{"name": c, "field_id": c} for c in columns],
               "rows": rows, "row_meta": [], "merged_ranges": [], "source": {"origin": "fixture"}}
    d = rt.content.put(payload)
    asset = AssetRef(id=f"table:{name}", kind="table", scope_ref="tenant:demo", revision=d,
                     resolver="local_content", locator=d, digest=d)
    return TableRef(asset=asset, schema_ref=VersionedRef(id=f"schema:{name}", revision="r1"), data_ref=d)

def draft_and_confirm(rt, proposal):
    r = invoke("draft_acceptance_criteria", {"delivery_target": "t", "proposal": proposal}, ctx(), runtime=rt)
    assert r.status == "ok", r.issues
    ref = r.data.criteria
    payload = rt.versions.get(CRITERIA_KIND, ref.id, ref.revision)
    conf = CriteriaConfirmation(confirmation_id=f"conf:{ref.id}", criteria_id=ref.id, criteria_revision=ref.revision,
        criteria_digest=_digest(payload), confirmer_ref="user:boss", confirmed_at=datetime.now(timezone.utc),
        authority_ref="tenant:owner")
    return confirm_acceptance_criteria(rt, ref.id, ref.revision, conf, authorized_confirmers={"user:boss"})

JUDGMENT = {"owner_ref": "user:alice", "family": "judgment", "expected_outputs": "判定",
            "evidence_requirements": ["rule:amount_limit"], "unknown_policy": "count_as_fail",
            "thresholds": {"pass_rate": 1.0}}
COMPUTE = {"owner_ref": "user:alice", "family": "compute", "expected_outputs": "总额",
           "evidence_requirements": ["metric:monthly_total"], "unknown_policy": "count_as_fail",
           "thresholds": {"pass_rate": 1.0}, "tolerance_relative": 0.0}

def isolate(rt, golds, region_per_case=True, weights=(0.0, 0.0, 1.0)):
    cases = []
    for i, gold in enumerate(golds):
        cases.append({"case_id": f"c{i}", "input_ref": str(content_ref(rt, {"in": i})),
                      "expected_ref": str(content_ref(rt, gold)),
                      "group_keys": {"g": f"g{i}" if region_per_case else "g"}})
    r = invoke("isolate_acceptance_samples", {"cases": cases, "group_keys": ["g"],
        "role_weights": {"development": weights[0], "regression": weights[1], "unseen_acceptance": weights[2]},
        "freeze": True}, ctx(), runtime=rt)
    assert r.status == "ok", r.issues
    return r.data.evaluation_set, cases

def computed(case_id, value, metric="metric:monthly_total", grain="月", unit="CNY", filters=()):
    return {"case_id": case_id, "computed_result": {"result_id": f"res:{case_id}", "target_ref": f"{metric}@r1",
        "form": "scalar", "value": value, "unit": unit, "grain": grain, "filters_applied": list(filters),
        "evidence_refs": ["ev:1"], "completeness": {"extent": "complete_in_declared_scope", "declared_scope": "全量"}}}

def assessment(case_id, verdict, target=None, basis=("rule:amount_limit",)):
    return {"case_id": case_id, "assessment": {"assessment_id": f"as:{case_id}",
        "target_ref": target or f"record:{case_id}@r1", "verdict": verdict, "basis_refs": list(basis),
        "unknowns": [], "next_actions": []}}
