"""DA12.1.1 / DA12.1.4 tests (08 §10.2)."""

from __future__ import annotations

import pytest

from dataagent_contracts.core import (
    AccessOutcome,
    EgressOutcome,
    ModelDestination,
    VersionedRef,
)
from dataagent_runtime.enforcement import (
    ACCESS_DENIED_CODE,
    EGRESS_REQUIRED_CODE,
    EnforcementConfig,
    egress_check,
)
from dataagent_runtime.invoke import invoke

from tests.conftest import content_ref, orders_table

ORDERS = VersionedRef(id="table:orders", revision="r1")


def ctx(**kwargs):
    base = dict(
        request_id="req:1",
        scope_ref="tenant:demo",
        authorization_ref="seed",
        subject_ref="user:alice",
        purpose="monthly_report",
    )
    base.update(kwargs)
    return base


def test_allow_produces_saved_decision(rt):
    result = invoke(
        "check_access_scope",
        {"resource_ref": "table:orders@r1"},
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok"
    decision = result.data.decision
    assert decision.decision is AccessOutcome.allow
    assert decision.field_constraints == ["region", "amount"]
    assert decision.masking_obligations == ["mask:phone"]
    # saved: the decision_id resolves in the store
    assert rt.decisions.get_access(decision.decision_id).decision_id == decision.decision_id


def test_no_matching_rule_is_indeterminate_effective_deny(rt):
    result = invoke(
        "check_access_scope",
        {"resource_ref": "doc:unknown@r1"},
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok"  # business conclusion, not a runtime failure
    decision = result.data.decision
    assert decision.decision is AccessOutcome.indeterminate
    assert decision.effective_outcome is AccessOutcome.deny


def test_explicit_deny_wins_over_allow(rt):
    # the trusted host fixes bob as the acting subject; the explicit deny
    # rule for bob must win over the table:orders allow rule
    rt.host_subject_ref = "user:bob"
    result = invoke(
        "check_access_scope",
        {"resource_ref": "table:orders@r1"},
        ctx(subject_ref="user:bob"),
        runtime=rt,
    )
    assert result.data.decision.decision is AccessOutcome.deny
    assert any("deny rule" in r for r in result.data.decision.reasons)


def test_subject_and_purpose_come_from_context_not_arguments(rt):
    # ctx lacks subject/purpose; host authority supplies them (config, not args)
    result = invoke(
        "check_access_scope",
        {"resource_ref": "table:orders@r1"},
        {
            "request_id": "req:2",
            "scope_ref": "tenant:demo",
            "authorization_ref": "seed",
        },
        runtime=rt,
    )
    assert result.status == "ok"
    assert result.data.decision.subject_ref == "user:alice"
    assert result.data.decision.purpose == "monthly_report"


def test_no_host_authority_falls_back_to_local_owner_not_call_arguments(rt):
    # R1: with no host authority the resolver supplies the local-owner
    # subject. A caller-supplied subject/purpose in arguments.context is a
    # hint only and must not become the executing identity (S0 X1).
    rt.host_subject_ref = None
    rt.host_purpose = None
    result = invoke(
        "check_access_scope",
        {"resource_ref": "table:orders@r1"},
        ctx(subject_ref="user:mallory", purpose="exfiltrate"),
        runtime=rt,
    )
    assert result.status == "ok"  # business conclusion, not a runtime failure
    decision = result.data.decision
    assert decision.subject_ref.startswith("local-owner:")
    assert decision.subject_ref != "user:mallory"
    assert decision.purpose == "local_owner"
    # no policy rule covers the local owner: indeterminate (folded to deny)
    assert decision.decision is AccessOutcome.indeterminate


def _mint_access(rt, resource="table:orders@r1", **ctx_over):
    result = invoke(
        "check_access_scope",
        {"resource_ref": resource},
        ctx(**ctx_over),
        runtime=rt,
    )
    return result.data.decision


# --- DA12.1.4 egress ------------------------------------------------------ #


def test_vendor_api_with_sensitive_content_forces_masking(rt):
    access = _mint_access(rt)
    ref = content_ref(rt, orders_table())
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {
                "model_ref": "model:gpt",
                "deployment": "vendor_api",
                "terms_ref": "terms:1",
            },
            "access_decision_ref": access.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok"
    out = result.data
    assert out.decision.decision is EgressOutcome.allow_masked
    assert out.masking is not None
    assert out.masking.masking_ref if hasattr(out.masking, "masking_ref") else True
    kinds = {f.kind for f in out.sensitivity.findings}
    assert "phone" in kinds
    # the masked artifact resolves and no longer contains the raw phone
    masked_payload = rt.content.get_json(out.masking.masked_content_ref)
    flat = str(masked_payload)
    assert "13800138000" not in flat
    assert "1********0" in flat or "*" in flat


def test_local_deployment_allows_sensitive_content(rt):
    access = _mint_access(rt)
    ref = content_ref(rt, orders_table())
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:local-llm", "deployment": "local"},
            "access_decision_ref": access.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert result.data.decision.decision is EgressOutcome.allow


def test_egress_requires_valid_access_decision(rt):
    ref = content_ref(rt, orders_table())
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:local-llm", "deployment": "local"},
            "access_decision_ref": "ad:does-not-exist",
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "not_found"


def test_deny_resource_cannot_get_an_egress_decision(rt):
    # secret resources are denied by policy, so no allow decision exists
    result = invoke(
        "check_access_scope",
        {"resource_ref": "secret:payroll@r1"},
        ctx(),
        runtime=rt,
    )
    assert result.data.decision.decision is AccessOutcome.deny
    ref = content_ref(rt, orders_table())
    egress = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:local-llm", "deployment": "local"},
            "access_decision_ref": result.data.decision.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert egress.status == "failed"  # deny basis is not an authorization


def test_masked_egress_feeds_inference_request_only_masked_content(rt):
    """§10.2: vendor_api + sensitive → inference_request only carries masked."""

    access = _mint_access(rt)
    ref = content_ref(rt, orders_table())
    egress = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "access_decision_ref": access.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    decision = egress.data.decision

    def load_masked(masking_ref):
        artifact = rt.versions.get("mask", masking_ref, _current_revision(rt, "mask", masking_ref))
        return rt.content.get_json(artifact["masked_content_ref"])

    request = {
        "content": orders_table(),
        "content_refs": [str(ref)],
        "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
        "egress_decision_ref": decision.decision_id,
    }
    outcome = egress_check(request, get_egress=rt.decisions.get_egress, load_masked=load_masked)
    assert outcome.allowed and outcome.masked
    assert "13800138000" not in str(outcome.request["content"])


def test_denied_or_missing_egress_strips_content_from_inference_request(rt):
    request = {
        "content": "raw 13800138000",
        "content_refs": ["content:none@r1"],
        "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
        "egress_decision_ref": "ed:none",
    }
    outcome = egress_check(request, get_egress=rt.decisions.get_egress)
    assert not outcome.allowed
    assert "content" not in outcome.request
    assert outcome.issue.code == EGRESS_REQUIRED_CODE


def _current_revision(rt, kind, object_id):
    return rt.versions.current(kind, object_id)[0]


def test_access_and_egress_operations_declare_writes(rt):
    """§10.1: annotations must match observed storage; both ops persist decisions."""

    from dataagent_governance.registry import load_operations
    from dataagent_runtime.registry import list_operations

    load_operations()
    specs = {s.operation: s for s in list_operations()}
    assert specs["check_access_scope"].writes is True
    assert specs["check_model_context_egress"].writes is True


def test_egress_basis_binds_subject_and_purpose(rt):
    # the decision is minted for the fixture host authority (alice/
    # monthly_report); the trusted host then switches to bob/fraud_scan, so
    # the basis decision must be rejected for the new executing identity
    access = _mint_access(rt)
    rt.host_subject_ref = "user:bob"
    rt.host_purpose = "fraud_scan"
    ref = content_ref(rt, orders_table())
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "access_decision_ref": access.decision_id,
        },
        ctx(subject_ref="user:bob", purpose="fraud_scan"),
        runtime=rt,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "invalid_input"
    assert "subject" in result.issues[0].message or "purpose" in result.issues[0].message


def test_egress_basis_covers_the_content(rt):
    access = _mint_access(rt)
    # ad-hoc content: no table anchor, not covered by a table:orders decision
    other = content_ref(rt, {"sheet": "other", "columns": [{"name": "x"}], "rows": [["y"]]})
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(other)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "access_decision_ref": access.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "invalid_input"
    assert "does not cover" in result.issues[0].message


def test_egress_accepts_governed_table_content_anchored_to_an_allowed_table(rt):
    access = _mint_access(rt)  # decision for table:orders
    # governed TableData of another sheet: covered through the table-type
    # allow rule (content-anchored coverage), not through the decision itself
    customers = content_ref(
        rt,
        {
            "sheet": "customers",
            "columns": [
                {"name": "name", "field_id": "c1"},
                {"name": "contact_phone", "field_id": "c2"},
            ],
            "rows": [["张三", "13800138000"]],
        },
    )
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(customers)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "access_decision_ref": access.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok", result.issues
    assert result.data.decision.decision is EgressOutcome.allow_masked


def _phone_table(sheet_phone: str = "13800138000") -> dict:
    return {
        "sheet": "orders",
        "columns": [
            {"name": "order_id", "field_id": "c1"},
            {"name": "phone", "field_id": "c2"},
        ],
        "rows": [["o1", sheet_phone]],
    }


def test_multi_content_egress_artifact_is_the_masked_payload_bundle(rt):
    """§5.1: one EgressDecision, one masking_ref — the merged artifact's
    masked_content_ref must be the masked payload, not artifact metadata,
    and non-sensitive content must survive it."""

    access = _mint_access(rt)
    ref1 = content_ref(rt, _phone_table("13800138000"))
    ref2 = content_ref(rt, _phone_table("13900139000"))
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref1), str(ref2)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "access_decision_ref": access.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok", result.issues
    decision = result.data.decision
    assert decision.decision is EgressOutcome.allow_masked

    artifact = result.data.masking
    assert artifact is not None
    resolved = rt.content.get_json(artifact.masked_content_ref)
    # a bundle document: content_refs + one row per content, in order
    assert isinstance(resolved, dict) and "rows" in resolved
    assert resolved["content_refs"] == [str(ref1), str(ref2)]
    assert len(resolved["rows"]) == 2
    flat = str(resolved)
    assert "13800138000" not in flat and "13900139000" not in flat
    assert "1********0" in flat or "*" in flat
    # every entry anchors a masked value back to the original digest
    entries = {entry.original_digest for entry in artifact.entries}
    assert len(entries) == 2

    # the inference request rewrite carries the bundle, never raw values
    def load_masked(masking_ref):
        revision = _current_revision(rt, "mask", masking_ref)
        stored = rt.versions.get("mask", masking_ref, revision)
        return rt.content.get_json(stored["masked_content_ref"])

    outcome = egress_check(
        {
            "content": [_phone_table("13800138000"), _phone_table("13900139000")],
            "content_refs": [str(ref1), str(ref2)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "egress_decision_ref": decision.decision_id,
        },
        get_egress=rt.decisions.get_egress,
        load_masked=load_masked,
    )
    assert outcome.allowed and outcome.masked
    seen = outcome.request["content"]
    assert isinstance(seen, dict) and "rows" in seen
    assert "13800138000" not in str(seen) and "13900139000" not in str(seen)


def test_multi_content_egress_keeps_non_sensitive_content(rt):
    """Mixed content: the non-sensitive payload passes through the artifact."""

    access = _mint_access(rt)
    sensitive = content_ref(rt, _phone_table())
    plain = content_ref(
        rt,
        {
            "sheet": "orders",
            "columns": [
                {"name": "order_id", "field_id": "c1"},
                {"name": "region", "field_id": "c2"},
            ],
            "rows": [["o2", "north"]],
        },
    )
    result = invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(sensitive), str(plain)],
            "destination": {"model_ref": "model:gpt", "deployment": "vendor_api"},
            "access_decision_ref": access.decision_id,
        },
        ctx(),
        runtime=rt,
    )
    assert result.status == "ok", result.issues
    assert result.data.decision.decision is EgressOutcome.allow_masked
    resolved = rt.content.get_json(result.data.masking.masked_content_ref)
    # the non-sensitive content did not vanish
    assert "north" in str(resolved)
    # and the sensitive one is masked
    assert "13800138000" not in str(resolved)
