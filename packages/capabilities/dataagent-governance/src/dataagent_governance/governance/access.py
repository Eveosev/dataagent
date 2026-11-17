"""DA12.1.1 access scope check and DA12.1.4 model-context egress (08 §5.1).

Both are business-conclusion operations: ``deny`` and ``indeterminate`` are
``status=ok`` results carrying the decision (08 §4.1). The minted
``decision_id`` doubles as the ``authorization_ref`` of later calls; the
egress ``decision_id`` is what an ``inference_request`` must cite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    EgressDecision,
    EgressOutcome,
    ModelDestination,
    VersionedRef,
)

from dataagent_governance.contracts import MaskedArtifactRef, SensitivityReport
from dataagent_governance.governance.sensitivity import mask_content, scan_content
from dataagent_governance.policy import evaluate_access, evaluate_egress
from dataagent_governance.runtime.errors import invalid_input, not_found
from dataagent_runtime import operation
from dataagent_runtime.policy.context import is_legacy_context


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _authority(rt, ctx):  # noqa: ANN001
    """Subject and purpose are already resolved by the one context resolver.

    ``invoke`` resolves the trusted channels (host ``_meta``, host-injected
    environment, local-owner) before a handler runs; re-applying the
    runtime's configured authority here would override a host ``_meta``
    context that outranks it. The ``DATAAGENT_CONTEXT_RESOLVER=legacy``
    switch is the one-release exception: the old handler used the runtime
    host authority first, so keep that precedence on the rollback path.
    """

    if is_legacy_context(runtime=rt):
        subject = rt.host_subject_ref or ctx.subject_ref
        purpose = rt.host_purpose or ctx.purpose
    else:
        subject = ctx.subject_ref
        purpose = ctx.purpose
    if not subject:
        raise invalid_input(
            "no executing subject: set CallContext.subject_ref or configure the "
            "trusted host authority (call arguments cannot supply it)",
            target="context.subject_ref",
        )
    if not purpose:
        raise invalid_input(
            "no purpose: set CallContext.purpose or configure the trusted host "
            "authority (call arguments cannot supply it)",
            target="context.purpose",
        )
    return subject, purpose


def _load_policy(rt, policy_ref):  # noqa: ANN001
    return rt.policy.load(policy_ref)


def _ref_covers(decision_ref: VersionedRef, ref: VersionedRef) -> bool:
    """Same coverage rule as the shared runtime recheck (08 §4.3)."""

    if decision_ref.id == ref.id:
        return decision_ref.revision in {ref.revision, "*"}
    if ref.id.startswith(decision_ref.id) and ref.id[len(decision_ref.id)] in {"/", ":"}:
        return decision_ref.revision in {ref.revision, "*"}
    return False


def _table_anchor(payload: object) -> VersionedRef | None:
    """Derive the source table asset of governed table content.

    Only the data-layer ``TableData`` shape — ``columns`` each bound to a
    ``field_id`` by a parsed schema, plus ``rows`` and a ``sheet`` — carries a
    derivation back to a table asset. Ad-hoc content has no anchor: it cannot
    be tied to any governed read and is therefore never "covered".
    """

    if not isinstance(payload, dict):
        return None
    columns = payload.get("columns")
    rows = payload.get("rows")
    sheet = payload.get("sheet")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return None
    if not isinstance(sheet, str) or not sheet:
        return None
    for column in columns:
        if not isinstance(column, dict) or not column.get("field_id"):
            return None
    return VersionedRef(id=f"table:{sheet}", revision="*")


def _content_covered(rt, access, ref, policy) -> bool:  # noqa: ANN001
    """Does the basis AccessDecision cover ``ref``?

    Two ways to establish coverage:

    - structural: the decision's resource covers the ref itself (a decision
      minted for ``content:<id>@<digest>`` or a covering subtree), the same
      rule the shared runtime recheck applies;
    - content-anchored: the content is governed table data derived from the
      table asset named by its sheet, and the policy still allows the
      decision's subject/purpose to read that asset.
    """

    if _ref_covers(access.resource_ref, ref):
        return True
    try:
        payload = rt.content.get_json(str(ref).split("@")[-1])
    except Exception:  # noqa: BLE001 - unreadable content is simply not covered
        return False
    anchor = _table_anchor(payload)
    if anchor is None:
        return False
    derived = anchor.model_copy(update={"revision": str(ref).split("@")[-1]})
    recheck = evaluate_access(
        policy,
        subject_ref=access.subject_ref,
        requester_ref=None,
        resource_ref=derived,
        action="read",
        purpose=access.purpose,
    )
    return recheck.decision is AccessOutcome.allow


# --- DA12.1.1 check_access_scope ---------------------------------------- #


class CheckAccessScopeInput(BaseModel):
    resource_ref: VersionedRef
    action: Literal["read"] = "read"
    policy_ref: VersionedRef | None = None


class CheckAccessScopeOutput(BaseModel):
    decision: AccessDecision


@operation(
    "DA12.1.1",
    input_model=CheckAccessScopeInput,
    output_model=CheckAccessScopeOutput,
    writes=True,
    description="访问范围检查：主体/资源/动作/用途匹配本地策略，产出 AccessDecision",
)
def check_access_scope(input_obj: CheckAccessScopeInput, ctx, rt):  # noqa: ANN001
    subject, purpose = _authority(rt, ctx)
    policy = _load_policy(rt, input_obj.policy_ref)
    decision = evaluate_access(
        policy,
        subject_ref=subject,
        requester_ref=ctx.requester_ref,
        resource_ref=input_obj.resource_ref,
        action=input_obj.action,
        purpose=purpose,
    )
    rt.decisions.save_access(decision)
    return CheckAccessScopeOutput(decision=decision)


# --- DA12.1.4 check_model_context_egress -------------------------------- #


class CheckModelContextEgressInput(BaseModel):
    content_refs: list[VersionedRef] = Field(min_length=1)
    destination: ModelDestination
    access_decision_ref: str = Field(min_length=1)


class CheckModelContextEgressOutput(BaseModel):
    decision: EgressDecision
    sensitivity: SensitivityReport
    masking: MaskedArtifactRef | None = None


@operation(
    "DA12.1.4",
    input_model=CheckModelContextEgressInput,
    output_model=CheckModelContextEgressOutput,
    writes=True,
    description="模型上下文可见性与外发控制：敏感识别、脱敏产物与 EgressDecision",
)
def check_model_context_egress(input_obj: CheckModelContextEgressInput, ctx, rt):  # noqa: ANN001
    subject, purpose = _authority(rt, ctx)
    access = rt.decisions.get_access(input_obj.access_decision_ref)
    if access is None:
        raise not_found(
            f"AccessDecision not found: {input_obj.access_decision_ref}; mint one with "
            "check_access_scope first"
        )
    now = _now()
    if access.decision is not AccessOutcome.allow:
        raise invalid_input(
            f"basis AccessDecision {access.decision_id} is {access.decision.value}; "
            "egress requires an allow decision"
        )
    if access.valid_until is not None and now > access.valid_until:
        raise invalid_input(f"basis AccessDecision {access.decision_id} has expired")

    # The basis decision must bind the current call, exactly like the runtime
    # access recheck (08 §4.3): the trusted subject and purpose that ask for
    # the egress must be the ones the decision was minted for.
    if access.subject_ref != subject:
        raise invalid_input(
            f"basis AccessDecision {access.decision_id} belongs to subject "
            f"{access.subject_ref!r}, not the executing subject {subject!r}"
        )
    if access.purpose != purpose:
        raise invalid_input(
            f"basis AccessDecision {access.decision_id} was minted for purpose "
            f"{access.purpose!r}, not {purpose!r}"
        )

    policy = _load_policy(rt, None)
    # ... and it must cover the content being sent (08 §5.1 外发输入).
    for ref in input_obj.content_refs:
        if not _content_covered(rt, access, ref, policy):
            raise invalid_input(
                f"basis AccessDecision {access.decision_id} resource "
                f"{access.resource_ref} does not cover content {ref}"
            )
    declared_fields = sorted(
        {
            field
            for rule in policy.rules
            for field in rule.sensitive_fields
        }
    )

    # Deterministic sensitivity identification over the actual content.
    # Every content gets a masked payload — non-sensitive ones pass through
    # unchanged: an allow_masked artifact is "the content with the sensitive
    # parts removed", so non-sensitive content must survive it, never vanish.
    findings: list = []
    per_content: list[tuple[str, MaskedArtifactRef, object]] = []
    for ref in input_obj.content_refs:
        payload = rt.content.get_json(str(ref).split("@")[-1])
        report = scan_content(payload, declared_fields)
        findings.extend(
            finding.model_copy(update={"content_ref": str(ref)}).model_dump(mode="json")
            for finding in report.findings
        )
        masked, artifact = mask_content(payload, declared_fields)
        per_content.append((str(ref), artifact, masked))
    sensitive = bool(findings)
    outcome, reasons = evaluate_egress(
        policy, deployment=input_obj.destination.deployment, sensitive=sensitive
    )

    masking: MaskedArtifactRef | None = None
    if outcome == "allow_masked":
        artifacts = []
        for ref, artifact, masked_payload in per_content:
            digest = rt.content.put(masked_payload)
            artifacts.append(
                artifact.model_copy(
                    update={
                        "mask_id": f"mask:{uuid.uuid4().hex[:12]}",
                        "source_content_ref": ref,
                        "masked_content_ref": digest,
                    }
                )
            )
        if len(artifacts) == 1:
            # Single content: the merged artifact points at the masked
            # payload itself (08 §5.1 脱敏产物内容寻址保存).
            merged_ref = artifacts[0].masked_content_ref
        else:
            # One EgressDecision carries one masking_ref: the merged
            # artifact's masked_content_ref points at the masked payload
            # bundle — the content refs plus one row per content, in
            # content_refs order — which is exactly what the inference
            # request carries after egress_check's rewrite.
            merged_ref = rt.content.put(
                {
                    "content_refs": [str(r) for r in input_obj.content_refs],
                    "rows": [masked for _, _, masked in per_content],
                }
            )
        masking = MaskedArtifactRef(
            mask_id=f"mask:{uuid.uuid4().hex[:12]}",
            source_content_ref=str(input_obj.content_refs[0]),
            masked_content_ref=merged_ref,
            entries=[entry for a in artifacts for entry in a.entries],
        )

    decision = EgressDecision(
        decision_id=f"ed:{uuid.uuid4().hex[:16]}",
        content_refs=input_obj.content_refs,
        destination=input_obj.destination,
        decision=EgressOutcome(outcome),
        visible_fields=access.field_constraints,
        masking_ref=masking.mask_id if masking else None,
        access_decision_ref=access.decision_id,
        receipt_ref=None,
    )
    # Persist the masking artifact so masking_ref resolves later.
    if masking is not None:
        rt.versions.save(
            "mask", masking.mask_id, masking.model_dump(mode="json")
        )
    rt.decisions.save_egress(decision)
    return CheckModelContextEgressOutput(
        decision=decision,
        sensitivity=SensitivityReport(content_ref="multi", findings=findings),
        masking=masking,
    )


__all__ = [
    "check_access_scope",
    "check_model_context_egress",
    "CheckAccessScopeInput",
    "CheckAccessScopeOutput",
    "CheckModelContextEgressInput",
    "CheckModelContextEgressOutput",
]
