"""Local policy evaluator (08 §5.1).

Evaluation order: an explicit ``deny`` match wins over any ``allow``; without
a matching rule the outcome is ``indeterminate`` (denied downstream). The
result carries the matched rule's field/row constraints, masking obligations
and validity window.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from dataagent_contracts.core import AccessDecision, AccessOutcome, VersionedRef

from dataagent_governance.contracts import PolicyDocument, PolicyRule
from dataagent_governance.policy.document import (
    purpose_matches,
    resource_matches,
    subject_matches,
)

__all__ = ["evaluate_access", "evaluate_egress"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _matching_rules(
    policy: PolicyDocument,
    *,
    subject_ref: str,
    resource_ref: VersionedRef,
    action: str,
    purpose: str,
) -> list[PolicyRule]:
    matched = []
    for rule in policy.rules:
        if not any(subject_matches(p, subject_ref) for p in rule.subjects):
            continue
        if not any(resource_matches(p, resource_ref) for p in rule.resources):
            continue
        if action not in rule.actions:
            continue
        if not any(purpose_matches(p, purpose) for p in rule.purposes):
            continue
        matched.append(rule)
    return matched


def evaluate_access(
    policy: PolicyDocument,
    *,
    subject_ref: str,
    requester_ref: str | None,
    resource_ref: VersionedRef,
    action: str,
    purpose: str,
) -> AccessDecision:
    matched = _matching_rules(
        policy,
        subject_ref=subject_ref,
        resource_ref=resource_ref,
        action=action,
        purpose=purpose,
    )
    denies = [r for r in matched if r.effect == "deny"]
    allows = [r for r in matched if r.effect == "allow"]
    if denies:
        rule = denies[0]
        return AccessDecision(
            decision_id=f"ad:{uuid.uuid4().hex[:16]}",
            policy_ref=VersionedRef(id=policy.policy_id, revision=policy.revision),
            subject_ref=subject_ref,
            requester_ref=requester_ref,
            action="read" if action == "read" else action,
            resource_ref=resource_ref,
            purpose=purpose,
            decision=AccessOutcome.deny,
            field_constraints=rule.field_constraints,
            row_constraints=rule.row_constraints,
            masking_obligations=list(rule.masking_obligations),
            valid_until=_now() + timedelta(seconds=policy.default_validity_seconds),
            reasons=[f"deny rule {rule.rule_id}", *rule.reasons],
        )
    if allows:
        rule = allows[0]
        valid_until = rule.valid_until or (
            _now() + timedelta(seconds=policy.default_validity_seconds)
        )
        return AccessDecision(
            decision_id=f"ad:{uuid.uuid4().hex[:16]}",
            policy_ref=VersionedRef(id=policy.policy_id, revision=policy.revision),
            subject_ref=subject_ref,
            requester_ref=requester_ref,
            action="read" if action == "read" else action,
            resource_ref=resource_ref,
            purpose=purpose,
            decision=AccessOutcome.allow,
            field_constraints=rule.field_constraints,
            row_constraints=rule.row_constraints,
            masking_obligations=list(rule.masking_obligations),
            valid_until=valid_until,
            reasons=[f"allow rule {rule.rule_id}", *rule.reasons],
        )
    return AccessDecision(
        decision_id=f"ad:{uuid.uuid4().hex[:16]}",
        policy_ref=VersionedRef(id=policy.policy_id, revision=policy.revision),
        subject_ref=subject_ref,
        requester_ref=requester_ref,
        action="read" if action == "read" else action,
        resource_ref=resource_ref,
        purpose=purpose,
        decision=AccessOutcome.indeterminate,
        valid_until=_now() + timedelta(seconds=policy.default_validity_seconds),
        reasons=["no matching policy rule; indeterminate is treated as deny"],
    )


def evaluate_egress(
    policy: PolicyDocument,
    *,
    deployment: str,
    sensitive: bool,
) -> tuple[str, list[str]]:
    """Return ``(outcome, reasons)`` for an egress attempt.

    Explicit ``deny`` wins; the vendor_api floor forces at least
    ``allow_masked`` when sensitive content is headed to a vendor API, even
    if a rule said ``allow`` (08 §5.1).
    """

    matched = [
        r
        for r in policy.egress_rules
        if not r.deployments or deployment in r.deployments
    ]
    applicable = [
        r
        for r in matched
        if r.sensitive is None or r.sensitive is sensitive
    ]
    denies = [r for r in applicable if r.effect == "deny"]
    if denies:
        return "deny", [f"deny egress rule {denies[0].rule_id}", *denies[0].reasons]
    allows = [r for r in applicable if r.effect in {"allow", "allow_masked"}]
    if allows:
        rule = allows[0]
        outcome = rule.effect
        reasons = [f"egress rule {rule.rule_id}", *rule.reasons]
        if deployment == "vendor_api" and sensitive and outcome == "allow":
            outcome = "allow_masked"
            reasons.append("vendor_api floor: sensitive content requires masking")
        return outcome, reasons
    return "deny", ["no matching egress rule; treated as deny"]
