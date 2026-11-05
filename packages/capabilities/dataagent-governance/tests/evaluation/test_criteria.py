"""DA11.5.1 criteria drafting and confirmation tests (08 §10.3, review §9)."""

from __future__ import annotations

from datetime import datetime, timezone

from dataagent_runtime.invoke import invoke

from dataagent_governance.contracts import CriteriaConfirmation
from dataagent_governance.evaluation.criteria_samples import (
    CRITERIA_KIND,
    _digest,
    confirm_acceptance_criteria,
)


def ctx():
    return {
        "request_id": "req:1",
        "scope_ref": "tenant:demo",
        "authorization_ref": "seed",
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }


PROPOSAL = {
    "owner_ref": "user:alice",
    "family": "judgment",
    "expected_outputs": "每月报销单判定：金额上限、票据齐全",
    "evidence_requirements": ["rule:amount_limit", "rule:receipt_present"],
    "unknown_policy": "count_as_fail",
    "thresholds": {"pass_rate": 0.9},
    "strata": ["region"],
}


def test_phase_one_returns_needs_input_with_context(rt):
    result = invoke(
        "draft_acceptance_criteria",
        {"delivery_target": "月度报销判定"},
        ctx(),
        runtime=rt,
    )
    assert result.status == "needs_input"
    issue = result.issues[0]
    assert issue.inference_request["role"] == "acceptance_criteria_draft"
    assert "unknown_policy" in issue.inference_request["delivery_target_fields"]
    assert issue.suggested_action


def test_phase_two_validates_and_saves_draft(rt):
    result = invoke(
        "draft_acceptance_criteria",
        {"delivery_target": "月度报销判定", "proposal": PROPOSAL},
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok"
    ref = result.data.criteria
    assert ref.status == "draft"
    assert ref.confirmation_ref is None
    payload = rt.versions.get(CRITERIA_KIND, ref.id, ref.revision)
    assert payload["family"] == "judgment"


def test_invalid_thresholds_rejected(rt):
    bad = dict(PROPOSAL, thresholds={"pass_rate": 1.5})
    result = invoke(
        "draft_acceptance_criteria",
        {"proposal": bad},
        ctx(),
        runtime=rt,
    )
    assert result.status == "failed"
    assert "pass_rate" in result.issues[0].message


def test_judgment_requires_pass_rate(rt):
    bad = dict(PROPOSAL, thresholds={"other": 1.0})
    result = invoke(
        "draft_acceptance_criteria",
        {"proposal": bad},
        ctx(),
        runtime=rt,
    )
    assert result.status == "failed"


def _drafted(rt):
    result = invoke(
        "draft_acceptance_criteria",
        {"delivery_target": "t", "proposal": PROPOSAL},
        ctx(),
        runtime=rt,
    )
    return result.data.criteria


def _confirmation(rt, ref, **over):
    payload = rt.versions.get(CRITERIA_KIND, ref.id, ref.revision)
    base = dict(
        confirmation_id="conf:1",
        criteria_id=ref.id,
        criteria_revision=ref.revision,
        criteria_digest=_digest(payload),
        confirmer_ref="user:boss",
        confirmed_at=datetime.now(timezone.utc),
        authority_ref="tenant:owner",
    )
    base.update(over)
    return CriteriaConfirmation(**base)


def test_confirmation_requires_authorized_confirmer(rt):
    ref = _drafted(rt)
    confirmation = _confirmation(rt, ref)
    result = invoke.__wrapped__ if False else None  # placeholder guard
    try:
        confirm_acceptance_criteria(
            rt,
            ref.id,
            ref.revision,
            confirmation,
            authorized_confirmers=set(),
        )
        raise AssertionError("expected failure")
    except Exception as exc:
        assert "not authorized" in str(exc)


def test_confirmation_binds_content_digest(rt):
    ref = _drafted(rt)
    forged = _confirmation(rt, ref, criteria_digest="sha256:" + "0" * 64)
    try:
        confirm_acceptance_criteria(
            rt, ref.id, ref.revision, forged, authorized_confirmers={"user:boss"}
        )
        raise AssertionError("expected failure")
    except Exception as exc:
        assert "digest" in str(exc)


def test_confirmation_targets_wrong_revision_rejected(rt):
    ref = _drafted(rt)
    misdirected = _confirmation(rt, ref, criteria_revision="r999")
    try:
        confirm_acceptance_criteria(
            rt, ref.id, ref.revision, misdirected, authorized_confirmers={"user:boss"}
        )
        raise AssertionError("expected failure")
    except Exception as exc:
        assert "different criteria revision" in str(exc)


def test_valid_confirmation_activates_new_revision(rt):
    ref = _drafted(rt)
    confirmation = _confirmation(rt, ref)
    active = confirm_acceptance_criteria(
        rt, ref.id, ref.revision, confirmation, authorized_confirmers={"user:boss"}
    )
    assert active.status == "active"
    assert active.confirmation_ref == "conf:1"
    assert active.revision != ref.revision  # new revision, old draft untouched
    payload = rt.versions.get(CRITERIA_KIND, ref.id, ref.revision)
    assert payload["status"] == "draft"


def test_active_criteria_cannot_be_reconfirmed_or_rewritten(rt):
    ref = _drafted(rt)
    active = confirm_acceptance_criteria(
        rt,
        ref.id,
        ref.revision,
        _confirmation(rt, ref),
        authorized_confirmers={"user:boss"},
    )
    replay = _confirmation(rt, active, confirmation_id="conf:1")
    try:
        confirm_acceptance_criteria(
            rt, active.id, active.revision, replay, authorized_confirmers={"user:boss"}
        )
        raise AssertionError("expected failure")
    except Exception as exc:
        assert "already active" in str(exc)
