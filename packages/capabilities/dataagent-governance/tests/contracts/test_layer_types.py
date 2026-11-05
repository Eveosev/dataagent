"""Layer contract round-trip tests (08 §10.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dataagent_contracts.core import AccessOutcome, EgressOutcome, ModelDestination, VersionedRef

from dataagent_governance.contracts import (
    AcceptanceCriteriaDraft,
    CriteriaConfirmation,
    EgressRule,
    EvaluationCaseDraft,
    EvaluationDelivery,
    ExpectedComputation,
    ExpectedJudgment,
    ExposureLedgerEntry,
    GrainCheckItem,
    GrainMergeReport,
    MaskedArtifactRef,
    MaskedEntry,
    PolicyDocument,
    PolicyRule,
    SensitivityFinding,
    SensitivityReport,
)


def test_policy_document_roundtrip():
    doc = PolicyDocument(
        policy_id="tenant:default",
        revision="r1",
        rules=[
            PolicyRule(
                rule_id="a",
                effect="allow",
                subjects=["user:alice"],
                resources=["table:*"],
                sensitive_fields=["phone"],
            )
        ],
        egress_rules=[EgressRule(rule_id="e", effect="allow_masked", deployments=["vendor_api"])],
    )
    again = PolicyDocument.model_validate(doc.model_dump(mode="json"))
    assert again == doc


def test_criteria_draft_requires_confirmation_when_active():
    with pytest.raises(ValidationError, match="confirmation_ref"):
        AcceptanceCriteriaDraft(
            criteria_id="c:1",
            revision="r1",
            owner_ref="user:alice",
            delivery_target="t",
            family="judgment",
            expected_outputs="x",
            evidence_requirements=["a"],
            unknown_policy="count_as_fail",
            status="active",
        )


def test_delivery_requires_exactly_one_payload():
    with pytest.raises(ValidationError):
        EvaluationDelivery(case_id="c1")
    # a timeout/budget marker is a legitimate payload-free delivery
    marker = EvaluationDelivery(case_id="c1", timed_out=True)
    assert marker.timed_out and marker.assessment is None


def test_grain_report_overall_consistency():
    with pytest.raises(ValidationError, match="overall"):
        GrainMergeReport(
            report_id="g:1",
            spec_ref=VersionedRef(id="spec:1", revision="r1"),
            declared_grain=["k"],
            items=[GrainCheckItem(check="grain_key_uniqueness", outcome="unknown", details="d")],
            overall="pass",
        )


def test_sensitivity_report_hides_values():
    report = SensitivityReport(
        content_ref="content:a@r1",
        findings=[
            SensitivityFinding(kind="phone", count=2, sample_digest="sha256:abc", locator="row:0")
        ],
    )
    dumped = report.model_dump(mode="json")
    assert "13800138000" not in str(dumped)
    assert report.sensitive and report.kinds == ["phone"]


def test_masked_artifact_keeps_original_digests():
    artifact = MaskedArtifactRef(
        mask_id="mask:1",
        source_content_ref="content:a@r1",
        masked_content_ref="sha256:" + "1" * 64,
        entries=[
            MaskedEntry(
                field="phone",
                locator="row:0",
                replacement="1********0",
                original_digest="sha256:" + "2" * 64,
            )
        ],
    )
    assert artifact.entries[0].original_digest.startswith("sha256:")


def test_confirmation_binds_criteria():
    with pytest.raises(ValidationError):
        CriteriaConfirmation(
            confirmation_id="conf:1",
            criteria_id="c:1",
            criteria_revision="",
            criteria_digest="sha256:x",
            confirmer_ref="user:boss",
            confirmed_at="2026-11-04T12:00:00Z",
            authority_ref="tenant:owner",
        )
