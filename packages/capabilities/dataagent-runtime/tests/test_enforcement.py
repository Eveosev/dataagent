from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    CallContext,
    EgressDecision,
    EgressOutcome,
    ModelDestination,
    VersionedRef,
)
from dataagent_runtime.adapters.local_content import canonical_bytes, digest_bytes
from dataagent_runtime.enforcement import (
    ACCESS_DENIED_CODE,
    EGRESS_REQUIRED_CODE,
    EnforcementConfig,
    access_recheck,
    egress_check,
    guarded_inference,
)

RESOURCE = VersionedRef(id="table:orders", revision="r1")
FUTURE = datetime(2030, 1, 1, tzinfo=timezone.utc)
PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)


def ctx(**kwargs):
    base = dict(
        request_id="req:1",
        scope_ref="tenant:demo",
        authorization_ref="ad:1",
        subject_ref="user:alice",
        purpose="monthly_report",
    )
    base.update(kwargs)
    return CallContext(**base)


def decision(**kwargs):
    base = dict(
        decision_id="ad:1",
        policy_ref=VersionedRef(id="policy:tenant", revision="r1"),
        subject_ref="user:alice",
        resource_ref=RESOURCE,
        purpose="monthly_report",
        decision=AccessOutcome.allow,
        valid_until=FUTURE,
    )
    base.update(kwargs)
    return AccessDecision(**base)


def test_recheck_allows_covering_decision():
    outcome = access_recheck(ctx(), lambda ref: decision(), [RESOURCE])
    assert outcome.ok and not outcome.kernel_path


def test_recheck_off_mode_skips():
    outcome = access_recheck(
        ctx(),
        lambda ref: None,
        [RESOURCE],
        config=EnforcementConfig(mode="off"),
    )
    assert outcome.ok


def test_recheck_unresolvable_authorization_denies():
    outcome = access_recheck(ctx(), lambda ref: None, [RESOURCE])
    assert not outcome.ok
    assert outcome.issue.code == ACCESS_DENIED_CODE


def test_recheck_deny_outcome_denies():
    outcome = access_recheck(
        ctx(), lambda ref: decision(decision=AccessOutcome.deny), [RESOURCE]
    )
    assert not outcome.ok
    assert "outcome is deny" in outcome.reasons[0]


def test_recheck_expired_denies():
    outcome = access_recheck(ctx(), lambda ref: decision(valid_until=PAST), [RESOURCE])
    assert not outcome.ok
    assert any("expired" in r for r in outcome.reasons)


def test_recheck_uncovered_resource_denies():
    other = VersionedRef(id="table:customers", revision="r1")
    outcome = access_recheck(ctx(), lambda ref: decision(), [RESOURCE, other])
    assert not outcome.ok
    assert any("table:customers" in r for r in outcome.reasons)


def test_recheck_asset_prefix_covers_subtree():
    child = VersionedRef(id="table:orders/2024-01", revision="r1")
    outcome = access_recheck(ctx(), lambda ref: decision(), [child])
    assert outcome.ok


def test_recheck_purpose_mismatch_denies():
    outcome = access_recheck(ctx(purpose="fraud_scan"), lambda ref: decision(), [RESOURCE])
    assert not outcome.ok
    assert any("purpose mismatch" in r for r in outcome.reasons)


def test_recheck_missing_purpose_denies():
    outcome = access_recheck(ctx(purpose=None), lambda ref: decision(), [RESOURCE])
    assert not outcome.ok
    assert any("purpose is missing" in r for r in outcome.reasons)


def test_recheck_subject_mismatch_denies():
    outcome = access_recheck(ctx(subject_ref="user:bob"), lambda ref: decision(), [RESOURCE])
    assert not outcome.ok
    assert any("subject mismatch" in r for r in outcome.reasons)


def test_recheck_legacy_kernel_path_only_checks_existence():
    # Legacy rollback: expired + deny + uncovered, but the guard is declared.
    config = EnforcementConfig(mode="enforce", kernel_guard_declared=True)
    outcome = access_recheck(
        ctx(kernel_session_id="ks:1"),
        lambda ref: decision(decision=AccessOutcome.deny, valid_until=PAST),
        [VersionedRef(id="table:elsewhere", revision="r9")],
        config=config,
        legacy=True,
    )
    assert outcome.ok and outcome.kernel_path


def test_recheck_v1_kernel_path_still_verifies_the_decision():
    """r8: a host session plus a declared guard must not skip the recheck.

    The caller can put ``authorization_ref`` in ``arguments.context``; with
    only an existence check that handle would turn a deny into access.
    """

    config = EnforcementConfig(mode="enforce", kernel_guard_declared=True)
    outcome = access_recheck(
        ctx(kernel_session_id="ks:1"),
        lambda ref: decision(decision=AccessOutcome.deny, valid_until=PAST),
        [VersionedRef(id="table:elsewhere", revision="r9")],
        config=config,
        legacy=False,
    )
    assert not outcome.ok and not outcome.kernel_path
    assert any("outcome is deny" in r for r in outcome.reasons)


def test_recheck_v1_kernel_path_checks_subject_and_resource():
    config = EnforcementConfig(mode="enforce", kernel_guard_declared=True)
    other = VersionedRef(id="table:elsewhere", revision="r9")

    subject = access_recheck(
        ctx(kernel_session_id="ks:1", subject_ref="user:mallory"),
        lambda ref: decision(),
        [RESOURCE],
        config=config,
        legacy=False,
    )
    assert not subject.ok
    assert any("subject mismatch" in r for r in subject.reasons)

    resource = access_recheck(
        ctx(kernel_session_id="ks:1"),
        lambda ref: decision(),
        [other],
        config=config,
        legacy=False,
    )
    assert not resource.ok
    assert any("does not cover input resource" in r for r in resource.reasons)


def test_recheck_kernel_session_without_declaration_still_rechecks():
    config = EnforcementConfig(mode="enforce", kernel_guard_declared=False)
    outcome = access_recheck(
        ctx(kernel_session_id="ks:1"),
        lambda ref: decision(decision=AccessOutcome.deny),
        [RESOURCE],
        config=config,
        legacy=False,
    )
    assert not outcome.ok


# --- egress --- #


def egress(**kwargs):
    base = dict(
        decision_id="ed:1",
        content_refs=[VersionedRef(id="content:abc", revision=CLEAN_DIGEST)],
        destination=ModelDestination(model_ref="model:llm", deployment="vendor_api"),
        decision=EgressOutcome.allow,
        access_decision_ref="ad:1",
    )
    base.update(kwargs)
    return EgressDecision(**base)


CLEAN_CONTENT = "raw text with 13800138000"
# r38 F1: an allow decision binds the actual content — the covered ref's
# revision must be the content address of exactly these bytes.
CLEAN_DIGEST = digest_bytes(canonical_bytes(CLEAN_CONTENT))


REQUEST = {
    "content": CLEAN_CONTENT,
    "content_refs": [f"content:abc@{CLEAN_DIGEST}"],
    "destination": {"model_ref": "model:llm", "deployment": "vendor_api"},
    "egress_decision_ref": "ed:1",
}


def test_egress_allow_passes_content_through():
    outcome = egress_check(REQUEST, get_egress=lambda ref: egress())
    assert outcome.allowed
    assert outcome.request["content"] == REQUEST["content"]


def test_egress_allow_rebound_inline_content_denied():
    # r38 F1: reusing a clean decision's refs with rewritten inline content
    # must not pass: the decision approved the referenced bytes, not this.
    request = dict(REQUEST, content="SECRET text with 13800138000")
    outcome = egress_check(request, get_egress=lambda ref: egress())
    assert not outcome.allowed
    assert "content" not in outcome.request
    assert any("does not bind" in r for r in outcome.reasons)


def test_egress_allow_inline_content_with_unaddressed_refs_denied():
    # A covered ref whose revision is not a content address cannot verify
    # any inline content: fail closed rather than pass on ref strings.
    decision = egress(
        content_refs=[VersionedRef(id="content:abc", revision="r1")]
    )
    outcome = egress_check(
        dict(REQUEST, content_refs=["content:abc@r1"]),
        get_egress=lambda ref: decision,
    )
    assert not outcome.allowed
    assert "content" not in outcome.request
    assert any("does not bind" in r for r in outcome.reasons)


def test_egress_missing_decision_strips_content():
    outcome = egress_check(REQUEST, get_egress=lambda ref: None)
    assert not outcome.allowed
    assert "content" not in outcome.request
    assert outcome.issue.code == EGRESS_REQUIRED_CODE


def test_egress_deny_strips_content():
    outcome = egress_check(
        REQUEST, get_egress=lambda ref: egress(decision=EgressOutcome.deny)
    )
    assert not outcome.allowed
    assert "content" not in outcome.request


def test_egress_masked_attaches_masked_artifact_only():
    masked = egress(decision=EgressOutcome.allow_masked, masking_ref="sha256:" + "f" * 64)
    outcome = egress_check(
        REQUEST,
        get_egress=lambda ref: masked,
        load_masked=lambda ref: "raw text with 138****000",
    )
    assert outcome.allowed and outcome.masked
    assert outcome.request["content"] == "raw text with 138****000"
    assert outcome.request["masked"] is True


def test_egress_uncovered_content_denies():
    request = dict(REQUEST, content_refs=["content:abc@r1", "content:zzz@r2"])
    outcome = egress_check(request, get_egress=lambda ref: egress())
    assert not outcome.allowed
    assert any("content:zzz" in r for r in outcome.reasons)


def test_egress_destination_mismatch_denies():
    request = dict(REQUEST, destination={"model_ref": "model:other", "deployment": "local"})
    outcome = egress_check(request, get_egress=lambda ref: egress())
    assert not outcome.allowed
    assert any("destination mismatch" in r for r in outcome.reasons)


def test_egress_off_mode_skips():
    outcome = egress_check(
        {"content": "x", "content_refs": ["a@r1"]},
        get_egress=lambda ref: None,
        config=EnforcementConfig(mode="off"),
    )
    assert outcome.allowed


def test_guarded_inference_fails_closed_without_calling_the_model():
    # r38 F1: a denied/unresolvable decision never reaches the model. The
    # port returns a needs-input marker with the content stripped — no
    # exception, and the inner model call must not happen.
    calls = []

    def inner(request):
        calls.append(request)
        return {"ok": True}

    port = guarded_inference(inner, get_egress=lambda ref: None)
    result = port(dict(REQUEST))
    assert calls == []
    assert result["needs_input"] is True
    assert result["egress_issue"]["code"] == EGRESS_REQUIRED_CODE
    assert "content" not in result


def test_guarded_inference_delegates_when_allowed():
    seen = {}

    def inner(request):
        seen.update(request)
        return {"ok": True}

    port = guarded_inference(inner, get_egress=lambda ref: egress())
    assert port(dict(REQUEST)) == {"ok": True}
    assert seen["content"] == REQUEST["content"]


def test_egress_content_without_content_refs_denied():
    # Bypass: raw content citing no content_refs cannot be verified against
    # any EgressDecision, so it must not pass through untouched.
    request = {
        "content": "raw PII 13800138000",
        "destination": {"model_ref": "model:llm", "deployment": "vendor_api"},
        "egress_decision_ref": "ed:missing",
    }
    outcome = egress_check(request, get_egress=lambda ref: egress())
    assert not outcome.allowed
    assert "content" not in outcome.request
    assert outcome.issue.code == EGRESS_REQUIRED_CODE
    assert any("without content_refs" in r for r in outcome.reasons)


def test_egress_destination_is_required():
    # Bypass: a request citing content but no destination must not pass even
    # when the EgressDecision covers the content.
    request = {
        "content": "raw PII 13800138000",
        "content_refs": ["content:abc@r1"],
        "egress_decision_ref": "ed:1",
    }
    outcome = egress_check(request, get_egress=lambda ref: egress())
    assert not outcome.allowed
    assert "content" not in outcome.request
    assert any("destination is required" in r for r in outcome.reasons)


def test_guarded_inference_denial_maps_to_needs_input_via_invoke():
    """08 §4.3: a denied egress is needs_input (missing decision), not failed."""

    from pydantic import BaseModel

    from dataagent_runtime import invoke, operation, reset_registry

    class ProbeInput(BaseModel):
        x: str = "1"

    class ProbeOutput(BaseModel):
        ok: bool = True

    reset_registry()

    @operation("TEST.9.1", input_model=ProbeInput, output_model=ProbeOutput, description="p")
    def egress_probe(input_obj, ctx, runtime):  # noqa: ANN001
        from dataagent_contracts.core import Issue
        from dataagent_runtime.errors import NeedsInputError

        port = guarded_inference(
            lambda req: {"ok": True}, get_egress=lambda ref: None
        )
        reply = port(
            {
                "content": "raw PII",
                "content_refs": ["content:x@r1"],
                "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
                "egress_decision_ref": "ed:missing",
            }
        )
        # r38 F1: the port fails closed with a needs-input marker; a handler
        # surfaces it through the shared two-phase mapping.
        if reply.get("needs_input"):
            raise NeedsInputError(Issue.model_validate(reply.get("egress_issue")))
        return ProbeOutput(ok=bool(reply["ok"]))

    result = invoke("egress_probe", {}, ctx())
    assert result.status == "needs_input"
    assert result.issues[0].code == EGRESS_REQUIRED_CODE
    reset_registry()
