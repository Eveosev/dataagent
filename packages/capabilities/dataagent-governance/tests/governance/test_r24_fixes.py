"""Product tests for the r24 reviewer blockers (B1–B9) in the governance layer.

Every behavior the reviewer probed through ``reviewer_r24_probe.py`` /
``reviewer_r24_grain_codec_probe.py`` is pinned here as a unit-level
regression test on the same fixtures the package suite uses.
"""

from __future__ import annotations

import math

from dataagent_contracts.core import AccessOutcome, CallContext, VersionedRef
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.invoke import invoke

from dataagent_governance.contracts import (
    CriteriaConfirmation,
    EgressRule,
    PolicyDocument,
    PolicyRule,
)
from dataagent_governance.evaluation import (
    confirm_acceptance_criteria,
    isolate_acceptance_samples,
)
from dataagent_governance.runtime import GovernanceRuntime
from tests.conftest import content_ref, orders_table, source_anchor


def ctx(**overrides) -> CallContext:
    base = {
        "request_id": "req:r24",
        "scope_ref": "tenant:demo",
        "authorization_ref": "seed",
        # the wire identity: used whenever the test clears the host
        # authority so that the caller identity is the acting one
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }
    base.update(overrides)
    return CallContext.model_validate(base)


def _mint(rt, resource: str) -> str:
    return (
        invoke("check_access_scope", {"resource_ref": resource}, ctx(), runtime=rt)
        .data.decision.decision_id
    )


# --- B2: sensitivity covers numeric cells and JSON structure ------------------ #


def _sensitivity_runtime(tmp_path):
    runtime = GovernanceRuntime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
        host_subject_ref="user:alice",
        host_purpose="monthly_report",
    )
    runtime.policy.save(
        PolicyDocument(
            policy_id="tenant:default",
            revision="r1",
            rules=[
                PolicyRule(
                    rule_id="allow-all",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["table", "content"],
                    purposes=["monthly_report"],
                    sensitive_fields=["secret_code"],
                )
            ],
            egress_rules=[
                EgressRule(rule_id="vendor", effect="allow", deployments=["vendor_api"])
            ],
        )
    )
    return runtime


def test_numeric_sensitive_values_are_found_and_masked(tmp_path):
    rt = _sensitivity_runtime(tmp_path)
    payload = {
        "sheet": "orders",
        "columns": [
            {"name": "phone", "field_id": "c1"},
            {"name": "secret_code", "field_id": "c2"},
        ],
        "rows": [[13800138000, 600001]],
        "row_meta": [],
        "merged_ranges": [],
        "source": {},
    }
    ref = content_ref(rt, payload)
    access = _mint(rt, "table@*")
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:vendor", "deployment": "vendor_api"},
            "access_decision_ref": access,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok"
    findings = {(f.kind, f.field) for f in result.data.sensitivity.findings}
    # the numeric phone cell is scanned as text; the declared column too
    assert any(kind == "phone" for kind, _ in findings)
    assert ("declared_field", "secret_code") in findings
    _revision, artifact = rt.versions.current("mask", result.data.decision.masking_ref)
    masked = rt.content.get_json(artifact["masked_content_ref"])
    # and both survive only through the masked artifact
    assert "13800138000" not in str(masked)
    assert "600001" not in str(masked)


def test_declared_json_keys_are_found_and_masked(tmp_path):
    rt = _sensitivity_runtime(tmp_path)
    payload = {"nested": {"secret_code": "SHHH-SECRET-VALUE", "safe": "ok"}}
    ref = content_ref(rt, payload)
    access = _mint(rt, str(ref))
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:vendor", "deployment": "vendor_api"},
            "access_decision_ref": access,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok"
    assert any(
        f.kind == "declared_field" and f.field == "secret_code"
        for f in result.data.sensitivity.findings
    )
    _revision, artifact = rt.versions.current("mask", result.data.decision.masking_ref)
    masked = rt.content.get_json(artifact["masked_content_ref"])
    assert "SHHH-SECRET-VALUE" not in str(masked)
    assert masked["nested"]["safe"] == "ok"


def test_sensitive_fields_from_policy_declare_the_columns(rt):
    from dataagent_governance.governance.sensitivity import scan_content

    report = scan_content(orders_table(), ["contact_phone"])
    fields = {f.field for f in report.findings}
    assert "contact_phone" in fields


# --- B3: the exposure ledger survives set re-creation ------------------------- #


def _confirm_criteria(rt, criteria) -> VersionedRef:
    from dataagent_governance.evaluation.criteria_samples import _digest

    payload = rt.versions.get("criteria", criteria.id, criteria.revision)
    confirmation = CriteriaConfirmation(
        confirmation_id=f"conf:{criteria.id}",
        criteria_id=criteria.id,
        criteria_revision=criteria.revision,
        criteria_digest=_digest(payload),
        confirmer_ref="user:boss",
        confirmed_at="2026-11-05T00:00:00Z",
        authority_ref="tenant:owner",
    )
    return confirm_acceptance_criteria(
        rt, criteria.id, criteria.revision, confirmation, authorized_confirmers={"user:boss"}
    )


def _judgment_case_set(rt):
    """(evaluation set, active criteria ref) over one judgment gold case."""

    drafted = invoke(
        "draft_acceptance_criteria",
        {"delivery_target": "amount limit judgment"},
        ctx(),
        runtime=rt,
    )
    criteria = invoke(
        "draft_acceptance_criteria",
        {
            "delivery_target": "amount limit judgment",
            "proposal": {
                "owner_ref": "user:alice",
                "family": "judgment",
                "expected_outputs": "amount is below 5000 passes",
                "evidence_requirements": ["rule:limit"],
                "unknown_policy": "count_as_fail",
                "thresholds": {"pass_rate": 1.0},
            },
        },
        ctx(),
        runtime=rt,
    ).data.criteria
    active = _confirm_criteria(rt, criteria)
    input_digest = rt.content.put({"record_key": "c1"})
    gold_digest = rt.content.put(
        [
            {
                "record_key": "c1",
                "rule_id": "rule:limit",
                "expected_verdict": "pass",
                "expected_evidence_fields": ["amount"],
            }
        ]
    )
    samples = invoke(
        "isolate_acceptance_samples",
        {
            "cases": [
                {
                    "case_id": "c1",
                    "input_ref": f"content:record@{input_digest}",
                    "expected_ref": f"content:gold@{gold_digest}",
                    "group_keys": {"entity": "c1"},
                }
            ],
            "group_keys": ["entity"],
            "freeze": True,
        },
        ctx(),
        runtime=rt,
    ).data.evaluation_set
    return samples, f"{active.id}@{active.revision}"


def test_gold_exposure_persists_across_set_recreation_and_demotes(rt):
    samples, _criteria_ref = _judgment_case_set(rt)
    assert rt.vault.exposure_ledger(str(samples.id)) == []  # gold not touched yet
    # a gold read outside the acceptance purpose is recorded and demotes the
    # case, whatever set it was made through: content-addressed (B3)
    rt.vault.read_gold(
        str(samples.id), str(samples.revision), "c1",
        purpose="debug", accessed_by="reviewer",
    )
    ledger = rt.vault.exposure_ledger(str(samples.id))
    assert ledger, "gold exposure must be recorded"
    # a re-created set over the same gold content inherits the exposure
    recreated, _criteria_ref2 = _judgment_case_set(rt)
    roles = rt.vault.current_roles(str(recreated.id))
    assert roles["c1"] == "regression"


def test_empty_eligible_unseen_reports_missing_not_measured_zero(rt):
    """B3/B9: exhausted sample sets report, they never claim measured zeros."""

    samples, criteria_ref = _judgment_case_set(rt)
    rt.vault.read_gold(
        str(samples.id), str(samples.revision), "c1",
        purpose="debug", accessed_by="reviewer",
    )
    recreated, _criteria_ref2 = _judgment_case_set(rt)
    # a delivery still arrives for the exposed case, but the case is no
    # longer eligible as unseen: it is excluded, not silently passed
    report = invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": criteria_ref,
            "evaluation_set_ref": f"{recreated.id}@{recreated.revision}",
            "deliveries": [
                {
                    "case_id": "c1",
                    "assessment": {
                        "assessment_id": "as:1",
                        "target_ref": "rule:limit@r1",
                        "verdict": "pass",
                        "basis_refs": ["spec:limit"],
                        "evidence": [
                            {
                                "id": "field:amount",
                                "evidence_type": "extracted_value",
                                "obtained_by": "da07.5.1/evaluate_scalar_expression",
                            }
                        ],
                    },
                }
            ],
        },
        ctx(),
        runtime=rt,
    )
    assert report.status == "ok"
    assert report.data.report.overall != "pass"
    assert report.data.report.cases == []
    assert report.data.report.cases_ref is not None
    assert any("没有可用的未见验收样本" in limit for limit in report.data.report.limits)


# --- B4: comparator determinism ---------------------------------------------- #


def _acceptance_report(rt, delivery, gold, family="compute", extra=None,
                       requirements=None):
    assessment = delivery.get("assessment")
    if isinstance(assessment, dict):
        for evidence in assessment.get("evidence") or []:
            if isinstance(evidence, dict):
                evidence.setdefault("obtained_by", "da07.5.1/evaluate_scalar_expression")
    # the ComputedResult contract requires grain/filters; keep the test
    # bodies focused on the field under test
    computed = delivery.get("computed_result")
    if isinstance(computed, dict):
        computed.setdefault("grain", "all")
        computed.setdefault("filters_applied", [])
        computed.setdefault("evidence_refs", ["spec:test"])
        computed.setdefault(
            "completeness",
            {"extent": "complete_in_declared_scope", "declared_scope": "test"},
        )
    samples_input = {
        "cases": [
            {
                "case_id": "c1",
                "input_ref": "content:input@sha256:0",
                "expected_ref": f"content:gold@{rt.content.put(gold)}",
                "group_keys": {"entity": "c1"},
            }
        ],
        "group_keys": ["entity"],
        "freeze": True,
    }
    samples = invoke(
        "isolate_acceptance_samples", samples_input, ctx(), runtime=rt
    ).data.evaluation_set
    drafted = invoke(
        "draft_acceptance_criteria",
        {
            "delivery_target": "t",
            "proposal": {
                "owner_ref": "user:alice",
                "family": family,
                "expected_outputs": "o",
                "evidence_requirements": (
                    requirements
                    if requirements is not None
                    else (
                        [gold[0].get("metric_id", "rule:limit")]
                        if family == "compute"
                        else ["rule:limit"]
                    )
                ),
                "unknown_policy": "count_as_fail",
                "thresholds": {"pass_rate": 1.0},
            },
        },
        ctx(),
        runtime=rt,
    ).data.criteria
    active = _confirm_criteria(rt, drafted)
    body = {
        "criteria_ref": f"{active.id}@{active.revision}",
        "evaluation_set_ref": f"{samples.id}@{samples.revision}",
        "deliveries": [delivery],
    }
    if extra:
        body.update(extra)
    result = invoke("evaluate_business_acceptance", body, ctx(), runtime=rt)
    assert result.status == "ok", [
        (i.code, i.message) for i in result.issues
    ]
    return result.data.report


def test_compute_unit_mismatch_fails_deterministically(rt):
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "computed_result": {
                "result_id": "res:1",
                "target_ref": "metric:total@r1",
                "form": "scalar",
                "value": 600.0,
                "unit": "USD",
            },
        },
        [
            {
                "metric_id": "metric:total",
                "expected_value": 600.0,
                "unit": "CNY",
                "grain": "all",
                "filters_applied": [],
            }
        ],
    )
    assert report.overall == "fail"
    assert "unit mismatch" in report.cases[0].notes


def test_compute_nan_and_string_nan_fail_deterministically(rt):
    for value in (float("nan"), "NaN"):
        report = _acceptance_report(
            rt,
            {
                "case_id": "c1",
                "computed_result": {
                    "result_id": "res:1",
                    "target_ref": "metric:total@r1",
                    "form": "scalar",
                    "value": value,
                    "unit": None,
                },
            },
            [
                {
                    "metric_id": "metric:total",
                    "expected_value": 600.0,
                    "unit": None,
                    "grain": "all",
                    "filters_applied": [],
                }
            ],
        )
        assert report.overall == "fail", value
        assert "not a finite number" in report.cases[0].notes


def test_compute_unreported_required_metric_fails(rt):
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "computed_result": {
                "result_id": "res:1",
                "target_ref": "metric:other@r1",
                "form": "scalar",
                "value": 1.0,
                "unit": None,
            },
        },
        [
            {
                "metric_id": "metric:total",
                "expected_value": 600.0,
                "unit": None,
                "grain": "all",
                "filters_applied": [],
            }
        ],
    )
    assert report.overall == "fail"
    assert "required metric is not delivered" in report.cases[0].notes


def test_judgment_verdict_aliases_map_to_core_vocabulary(rt):
    for alias, expected in (("satisfied", "pass"), ("violated", "fail")):
        report = _acceptance_report(
            rt,
            {
                "case_id": "c1",
                "assessment": {
                    "assessment_id": "as:1",
                    "target_ref": "rule:limit@r1",
                    "verdict": alias,
                    "basis_refs": ["spec:limit"],
                    # r35 F3 + r38 F5: a field evidence locates its field
                    # only when it carries source anchors that actually
                    # resolve against content the shared store holds
                    "evidence": [
                        {
                            "id": "field:amount",
                            "evidence_type": "extracted_value",
                            "source_anchors": [
                                source_anchor(
                                    rt,
                                    {"records": [{"amount": 100}]},
                                    "/records/0/amount",
                                )
                            ],
                        }
                    ],
                },
            },
            [
                {
                    "record_key": "c1",
                    "rule_id": "rule:limit",
                    "expected_verdict": "pass",
                    "expected_evidence_fields": ["amount"],
                }
            ],
            family="judgment",
        )
        assert report.cases[0].verdict == expected, alias


def test_judgment_unlocatable_basis_fails_with_evidence_missing(rt):
    # the criteria demand rule:other; neither the gold rule id nor any basis
    # ref resolves it, so the delivery cannot be tied to the requirement
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "assessment": {
                "assessment_id": "as:1",
                "target_ref": "rule:other@r1",
                "verdict": "pass",
                "basis_refs": ["spec:totally-unrelated"],
                "evidence": [{"id": "field:amount", "evidence_type": "extracted_value"}],
            },
        },
        [
            {
                "record_key": "c1",
                "rule_id": "rule:limit",
                "expected_verdict": "pass",
                "expected_evidence_fields": ["amount"],
            }
        ],
        family="judgment",
        requirements=["rule:other"],
    )
    assert report.overall == "fail"
    assert "evidence_missing" in report.cases[0].notes


# --- B7: host authority ------------------------------------------------------ #


def test_host_authority_cannot_be_overridden_by_the_caller(tmp_path):
    runtime = GovernanceRuntime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / ".dataagent",
        enforcement=EnforcementConfig(mode="enforce"),
        host_subject_ref="user:alice",
        host_purpose="review",
    )
    runtime.policy.save(
        PolicyDocument(
            policy_id="tenant:default",
            revision="r1",
            rules=[
                PolicyRule(
                    rule_id="allow",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["table"],
                    purposes=["review"],
                )
            ],
        )
    )
    forged = ctx(subject_ref="user:mallory", purpose="exfil")
    result = invoke(
        "check_access_scope", {"resource_ref": "table@*"}, forged, runtime=runtime
    )
    assert result.status == "ok"
    assert result.data.decision.subject_ref == "user:alice"
    assert result.data.decision.decision is AccessOutcome.allow


# --- B9: six metric classes and honest missing_records ---------------------- #


def test_unobserved_metric_classes_are_declared_missing_not_zero(rt):
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "computed_result": {
                "result_id": "res:1",
                "target_ref": "metric:total@r1",
                "form": "scalar",
                "value": 600.0,
                "unit": None,
            },
        },
        [
            {
                "metric_id": "metric:total",
                "expected_value": 600.0,
                "unit": None,
                "grain": "all",
                "filters_applied": [],
            }
        ],
    )
    metrics = report.metrics
    # all six classes are populated: observed or explicitly missing
    assert metrics.quality and metrics.coverage is not None and metrics.unknown is not None
    assert metrics.human is not None and metrics.latency_ms is not None
    assert metrics.cost is None
    assert any("human_effort" in record for record in metrics.missing_records)
    assert any("cost" in record for record in metrics.missing_records)
    assert any("latency" in record for record in metrics.missing_records)
    assert any("缺测不写成实测零" in limit for limit in report.limits)


def test_host_observations_fill_the_metric_classes(rt):
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "computed_result": {
                "result_id": "res:1",
                "target_ref": "metric:total@r1",
                "form": "scalar",
                "value": 600.0,
                "unit": None,
            },
        },
        [
            {
                "metric_id": "metric:total",
                "expected_value": 600.0,
                "unit": None,
                "grain": "all",
                "filters_applied": [],
            }
        ],
        extra={
            "observations": {
                "human_count": 2,
                "human_minutes": 45.0,
                "cost_amount": 1.25,
                "cost_currency": "CNY",
                "latency_ms": [100.0, 200.0, 300.0, 400.0],
            }
        },
    )
    metrics = report.metrics
    assert metrics.human.count == 2 and metrics.human.minutes == 45.0
    assert metrics.cost.amount == 1.25 and metrics.cost.currency == "CNY"
    assert metrics.latency_ms.p50 == 300.0
    assert metrics.latency_ms.p95 == 400.0
    assert metrics.missing_records == []
