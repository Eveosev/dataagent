"""DA11.5.5 business acceptance tests (08 §10.4, §10.6)."""

from __future__ import annotations

from dataagent_contracts.core import Assessment, ComputedResult, VersionedRef
from dataagent_runtime.invoke import invoke

from dataagent_governance.evaluation.criteria_samples import (
    CRITERIA_KIND,
    _digest,
    confirm_acceptance_criteria,
)
from tests.conftest import content_ref


def ctx():
    return {
        "request_id": "req:1",
        "scope_ref": "tenant:demo",
        "authorization_ref": "seed",
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }


JUDGMENT_PROPOSAL = {
    "owner_ref": "user:alice",
    "family": "judgment",
    "expected_outputs": "报销单判定",
    "evidence_requirements": ["rule:amount_limit"],
    "unknown_policy": "count_as_fail",
    "thresholds": {"pass_rate": 1.0},
    "strata": ["region"],
}

COMPUTE_PROPOSAL = {
    "owner_ref": "user:alice",
    "family": "compute",
    "expected_outputs": "月度总额",
    "evidence_requirements": ["metric:monthly_total"],
    "unknown_policy": "count_as_fail",
    "thresholds": {"pass_rate": 1.0},
    "tolerance_relative": 0.01,
    "strata": ["region"],
}


def _draft_and_confirm(rt, proposal):
    result = invoke(
        "draft_acceptance_criteria",
        {"delivery_target": "t", "proposal": proposal},
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok", result.issues
    ref = result.data.criteria
    payload = rt.versions.get(CRITERIA_KIND, ref.id, ref.revision)
    from dataagent_governance.contracts import CriteriaConfirmation
    from datetime import datetime, timezone

    confirmation = CriteriaConfirmation(
        confirmation_id=f"conf:{ref.id}",
        criteria_id=ref.id,
        criteria_revision=ref.revision,
        criteria_digest=_digest(payload),
        confirmer_ref="user:boss",
        confirmed_at=datetime.now(timezone.utc),
        authority_ref="tenant:owner",
    )
    return confirm_acceptance_criteria(
        rt, ref.id, ref.revision, confirmation, authorized_confirmers={"user:boss"}
    )


def _judgment_gold(case_id, verdict="pass", with_evidence=True):
    return [
        {
            "record_key": case_id,
            "rule_id": "rule:amount_limit",
            "expected_verdict": verdict,
            "expected_evidence_fields": ["amount"] if with_evidence else [],
        }
    ]


def _assessment(case_id, verdict, basis=("rule:amount_limit:amount",)):
    return {
        "case_id": case_id,
        "assessment": {
            "assessment_id": f"as:{case_id}",
            "target_ref": f"record:{case_id}@r1",
            "verdict": verdict,
            "basis_refs": list(basis),
            "unknowns": [],
            "next_actions": [],
        },
    }


def _isolate(rt, n_cases=6, region="north"):
    cases = []
    for i in range(n_cases):
        input_ref = content_ref(rt, {"record": f"r{i}"})
        expected_ref = content_ref(rt, _judgment_gold(f"r{i}"))
        cases.append(
            {
                "case_id": f"r{i}",
                "input_ref": str(input_ref),
                "expected_ref": str(expected_ref),
                "group_keys": {"region": region},
            }
        )
    result = invoke(
        "isolate_acceptance_samples",
        {
            "cases": cases,
            "group_keys": ["region"],
            "role_weights": {
                "development": 0.34,
                "regression": 0.33,
                "unseen_acceptance": 0.33,
            },
            "freeze": True,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok", result.issues
    return result.data.evaluation_set


def _unseen_case_ids(rt, set_ref):
    cases = rt.vault.list_cases(str(set_ref.id), str(set_ref.revision), "unseen_acceptance")
    return [c["case_id"] for c in cases]


def test_acceptance_pass_report_has_six_metric_classes_and_strata(rt):
    criteria = _draft_and_confirm(rt, JUDGMENT_PROPOSAL)
    set_ref = _isolate(rt, 6)
    unseen = _unseen_case_ids(rt, set_ref)
    deliveries = [_assessment(c, "pass") for c in unseen]
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
            "dependency_versions": ["pkg:dataagent-data@0.1.0"],
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok", result.issues
    report = result.data.report
    assert report.overall == "pass"
    # six metric classes populated
    assert report.metrics.quality and report.metrics.quality[0].name == "pass_rate"
    assert report.metrics.coverage.covered == report.metrics.coverage.total == len(unseen)
    assert report.metrics.unknown.rate == 0.0
    assert report.metrics.human.count == 0
    assert report.metrics.cost is None
    assert report.metrics.latency_ms.p50 >= 0
    assert report.metrics.strata and report.metrics.strata[0].key == "region=north"
    assert any("约定隔离" in limit for limit in report.limits)
    assert report.dependency_versions


def test_missing_delivery_counts_in_denominator(rt):
    criteria = _draft_and_confirm(rt, JUDGMENT_PROPOSAL)
    set_ref = _isolate(rt, 6)
    unseen = _unseen_case_ids(rt, set_ref)
    deliveries = [_assessment(c, "pass") for c in unseen[:-1]]  # last one missing
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    report = result.data.report
    assert report.overall == "fail"
    assert report.metrics.quality[0].denominator == len(unseen)  # missing in denominator
    assert report.metrics.quality[0].numerator == len(unseen) - 1


def test_timeout_delivery_counts_in_denominator(rt):
    criteria = _draft_and_confirm(rt, JUDGMENT_PROPOSAL)
    set_ref = _isolate(rt, 6)
    unseen = _unseen_case_ids(rt, set_ref)
    deliveries = [_assessment(c, "pass") for c in unseen[:-1]]
    deliveries.append({"case_id": unseen[-1], "timed_out": True})
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    report = result.data.report
    assert report.overall == "fail"
    assert any("timed out" in (c.notes or "") for c in report.cases)


def test_unknown_scored_by_policy_count_as_fail(rt):
    criteria = _draft_and_confirm(rt, JUDGMENT_PROPOSAL)
    set_ref = _isolate(rt, 6)
    unseen = _unseen_case_ids(rt, set_ref)
    deliveries = [
        _assessment(unseen[0], "unknown"),
        *[_assessment(c, "pass") for c in unseen[1:]],
    ]
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    report = result.data.report
    assert report.overall == "fail"
    assert report.metrics.unknown.count == 1
    assert any("unknown counts as fail" in (c.notes or "") for c in report.cases)


def test_evidence_missing_fails_the_case(rt):
    criteria = _draft_and_confirm(rt, JUDGMENT_PROPOSAL)
    set_ref = _isolate(rt, 6)
    unseen = _unseen_case_ids(rt, set_ref)
    deliveries = [
        _assessment(unseen[0], "pass", basis=()),  # no basis refs
        *[_assessment(c, "pass") for c in unseen[1:]],
    ]
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    report = result.data.report
    assert report.overall == "fail"
    assert any("evidence_missing" in (c.notes or "") for c in report.cases)


def test_draft_criteria_cannot_drive_acceptance(rt):
    result = invoke(
        "draft_acceptance_criteria",
        {"delivery_target": "t", "proposal": JUDGMENT_PROPOSAL},
        ctx(),
        runtime=rt,
    )
    draft = result.data.criteria
    set_ref = _isolate(rt, 6)
    unseen = _unseen_case_ids(rt, set_ref)
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{draft.id}@{draft.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": [_assessment(c, "pass") for c in unseen],
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "failed"
    assert "active" in result.issues[0].message


def test_unfrozen_set_cannot_drive_acceptance(rt):
    criteria = _draft_and_confirm(rt, JUDGMENT_PROPOSAL)
    cases = []
    for i in range(6):
        cases.append(
            {
                "case_id": f"r{i}",
                "input_ref": str(content_ref(rt, {"record": f"r{i}"})),
                "expected_ref": str(content_ref(rt, _judgment_gold(f"r{i}"))),
                "group_keys": {"region": "north"},
            }
        )
    result = invoke(
        "isolate_acceptance_samples",
        {"cases": cases, "group_keys": ["region"], "freeze": False},
        ctx(),
        runtime=rt,
    )
    set_ref = result.data.evaluation_set
    unseen = _unseen_case_ids(rt, set_ref)
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": [_assessment(c, "pass") for c in unseen],
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "failed"
    assert "frozen" in result.issues[0].message


def test_compute_family_acceptance_with_tolerance(rt):
    criteria = _draft_and_confirm(rt, COMPUTE_PROPOSAL)
    cases = []
    for i in range(6):
        input_ref = content_ref(rt, {"table": f"t{i}"})
        expected_ref = content_ref(
            rt,
            [
                {
                    "metric_id": "metric:monthly_total",
                    "expected_value": 1000.0,
                    "unit": "CNY",
                    "grain": "每月每门店",
                    "filters_applied": ["status != refunded"],
                }
            ],
        )
        cases.append(
            {
                "case_id": f"c{i}",
                "input_ref": str(input_ref),
                "expected_ref": str(expected_ref),
                "group_keys": {"region": "north"},
            }
        )
    result = invoke(
        "isolate_acceptance_samples",
        {
            "cases": cases,
            "group_keys": ["region"],
            "role_weights": {
                "development": 0.34,
                "regression": 0.33,
                "unseen_acceptance": 0.33,
            },
            "freeze": True,
        },
        ctx(),
        runtime=rt,
    )
    set_ref = result.data.evaluation_set
    unseen = _unseen_case_ids(rt, set_ref)

    def computed(case_id, value, grain="每月每门店"):
        return {
            "case_id": case_id,
            "computed_result": {
                "result_id": f"res:{case_id}",
                "target_ref": "metric:monthly_total@r1",
                "form": "scalar",
                "value": value,
                "unit": "CNY",
                "grain": grain,
                "filters_applied": ["status != refunded"],
                "evidence_refs": ["ev:1"],
                "completeness": {
                    "extent": "complete_in_declared_scope",
                    "declared_scope": "全量",
                },
            },
        }

    # 1005 is inside the 1% tolerance; 1100 is not; one wrong grain fails.
    values = {"v": 1005.0}
    deliveries = []
    for index, case_id in enumerate(unseen):
        if index == 0:
            deliveries.append(computed(case_id, 1100.0))
        elif index == 1:
            deliveries.append(computed(case_id, 1000.0, grain="每天每门店"))
        else:
            deliveries.append(computed(case_id, 1005.0))
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    report = result.data.report
    assert report.overall == "fail"
    notes = " | ".join(c.notes or "" for c in report.cases)
    assert "expected 1000.0, got 1100.0" in notes
    assert "grain mismatch" in notes
    # tolerance accepted 1005
    assert "1005.0" not in notes


def test_exposed_gold_case_is_not_accepted_as_unseen_via_old_revision(rt):
    """§10.3: 读取金标后样本降为 regression，冻结旧版也不能当 unseen 用."""

    criteria = _draft_and_confirm(rt, JUDGMENT_PROPOSAL)
    set_ref = _isolate(rt, 9)
    unseen = _unseen_case_ids(rt, set_ref)
    target = unseen[0]
    rt.vault.read_gold(
        str(set_ref.id),
        str(set_ref.revision),
        target,
        purpose="debug",
        accessed_by="cli",
    )
    current = rt.versions.current("eval_set", str(set_ref.id))[1]
    roles = {c["case_id"]: c["role"] for c in current["cases"]}
    assert roles[target] == "regression"

    deliveries = [_assessment(c, "pass") for c in unseen]  # includes the exposed one
    result = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{set_ref.id}@{set_ref.revision}",
            "deliveries": deliveries,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok", result.issues
    report = result.data.report
    assert target not in {c.case_id for c in report.cases}
    assert report.metrics.coverage.total == len(unseen) - 1
