from __future__ import annotations

import pytest
from pydantic import ValidationError

from dataagent_contracts.core import (
    AcceptanceReport,
    AccessDecision,
    AccessOutcome,
    CapabilityResult,
    CapabilityStatus,
    CaseResult,
    Completeness,
    CompletenessExtent,
    CorrectionRef,
    CriteriaRef,
    DataBatchRef,
    DocumentUnitRef,
    EgressDecision,
    EgressOutcome,
    FieldValue,
    FieldValueStatus,
    Latency,
    LifecycleStatus,
    MetricBundle,
    Coverage,
    UnknownRate,
    HumanEffort,
    Severity,
    VersionedRef,
    Verdict,
)
from samples import anchor, asset, completeness

def complete() -> Completeness:
    return Completeness(
        extent=CompletenessExtent.complete_in_declared_scope, declared_scope="scope"
    )


def metric_bundle() -> MetricBundle:
    return MetricBundle(
        coverage=Coverage(covered=1, total=1),
        unknown=UnknownRate(count=0, rate=0),
        human=HumanEffort(count=0),
        latency_ms=Latency(p50=1, p95=2),
    )


def test_partial_requires_issues_or_incomplete_scope():
    with pytest.raises(ValidationError, match="partial result requires"):
        CapabilityResult[dict](status=CapabilityStatus.partial, data={}, completeness=complete())
    ok = CapabilityResult[dict](
        status=CapabilityStatus.partial,
        data={},
        completeness=Completeness(extent=CompletenessExtent.truncated, declared_scope="scope"),
    )
    assert ok.status is CapabilityStatus.partial


def test_pending_requires_job_ref():
    with pytest.raises(ValidationError, match="continuation.job_ref"):
        CapabilityResult[dict](status=CapabilityStatus.pending)


def test_needs_input_requires_action_or_alternatives():
    from dataagent_contracts.core import Issue

    with pytest.raises(ValidationError, match="needs_input"):
        CapabilityResult[dict](
            status=CapabilityStatus.needs_input,
            issues=[Issue(code="da02.x", message="m", severity=Severity.error, retryable=False)],
        )


def test_extracted_field_requires_evidence():
    with pytest.raises(ValidationError, match="requires at least one SourceAnchor"):
        FieldValue(field_id="amount", status=FieldValueStatus.extracted, value=1, value_type="number")
    valid = FieldValue(
        field_id="amount",
        status=FieldValueStatus.extracted,
        value=1,
        value_type="number",
        evidence=[anchor()],
    )
    assert valid.value == 1


def test_missing_field_must_not_carry_value():
    with pytest.raises(ValidationError, match="must not carry a value"):
        FieldValue(field_id="amount", status=FieldValueStatus.missing, value=1, value_type="number")


def test_versioned_ref_serialization_contract():
    ref = VersionedRef(id="doc:1", revision="r2")
    assert ref.model_dump_json() == '"doc:1@r2"'
    assert VersionedRef.model_validate_json('"doc:1@r2"') == ref
    with pytest.raises(ValidationError):
        VersionedRef.model_validate("doc:1")


def test_active_criteria_requires_confirmation():
    with pytest.raises(ValidationError, match="confirmation_ref"):
        CriteriaRef(
            id="c",
            revision="r1",
            status=LifecycleStatus.active,
            owner_ref="u",
            expected_outputs="x",
            unknown_policy="report_separately",
        )


def test_correction_event_type_is_locked():
    with pytest.raises(ValidationError, match="correction"):
        CorrectionRef(
            event_id="e",
            task_ref=VersionedRef(id="t", revision="r1"),
            event_type="note",
            timestamp="2026-01-01T00:00:00Z",
            actor_ref="u",
            payload_ref="p",
            target_ref=VersionedRef(id="r", revision="r1"),
            explanation="x",
            scope_ref="s",
        )


def test_access_decision_indeterminate_is_deny():
    decision = AccessDecision(
        decision_id="d",
        policy_ref=VersionedRef(id="p", revision="r1"),
        subject_ref="s",
        action="read",
        resource_ref=VersionedRef(id="r", revision="r1"),
        purpose="p",
        decision=AccessOutcome.indeterminate,
        valid_until="2026-01-01T00:00:00Z",
    )
    assert decision.is_allowed() is False
    assert decision.effective_outcome is AccessOutcome.deny


def test_masked_egress_requires_masking_ref():
    with pytest.raises(ValidationError, match="masking_ref"):
        EgressDecision(
            decision_id="e",
            content_refs=[VersionedRef(id="c", revision="r1")],
            destination={"model_ref": "m", "deployment": "local"},
            decision=EgressOutcome.allow_masked,
            access_decision_ref="a",
        )


def test_document_unit_needs_anchor():
    with pytest.raises(ValidationError):
        DocumentUnitRef(
            asset=asset(),
            parent_document_ref=VersionedRef(id="doc:1", revision="r1"),
            unit_type="clause",
            ordinal_path="1",
            content_ref="c",
            anchors=[],
        )


def test_acceptance_report_requires_cases_or_ref():
    with pytest.raises(ValidationError, match="cases or cases_ref"):
        AcceptanceReport(
            id="r",
            criteria_ref=VersionedRef(id="c", revision="r1"),
            evaluation_set_ref=VersionedRef(id="e", revision="r1"),
            target_ref=VersionedRef(id="t", revision="r1"),
            overall=Verdict.pass_,
            metrics=metric_bundle(),
            coverage_scope="s",
            run_ref="run:1",
        )


def test_data_batch_inline_cap():
    with pytest.raises(ValidationError):
        DataBatchRef(
            asset=asset(),
            source_ref="f",
            row_count=501,
            completeness=complete(),
            inline_rows=[{"i": i} for i in range(501)],
        )
