"""Local policy document model (08 §5.1).

A policy is a JSON document stored in the versioned repository under the
``policy`` kind; ``PolicyRef`` is its ``VersionedRef``. Rules match on
subject, resource (``VersionedRef`` prefix or asset type), action and purpose.
Evaluation order: explicit ``deny`` wins, then ``allow``; no matching rule is
``indeterminate`` (treated as deny). The port leaves room for Cedar-style
engines in stage 2; S0 ships only this local evaluator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, Field

from dataagent_contracts.core._base import ExtModel

__all__ = ["PolicyRule", "EgressRule", "PolicyDocument"]


class PolicyRule(ExtModel):
    rule_id: str = Field(min_length=1)
    effect: Literal["allow", "deny"]
    # Subject patterns: exact ``user:alice`` or ``*``.
    subjects: list[str] = Field(min_length=1)
    # Resource patterns: ``table:orders@r1`` (exact), ``table:orders``
    # (asset subtree, any revision), ``table:*`` (asset type).
    resources: list[str] = Field(min_length=1)
    actions: list[str] = Field(default_factory=lambda: ["read"])
    # Purpose patterns: exact purpose string or ``*``.
    purposes: list[str] = Field(default_factory=lambda: ["*"])
    field_constraints: list[str] | None = None
    row_constraints: str | None = None
    masking_obligations: list[str] = Field(default_factory=list)
    # Field names this policy declares sensitive; DA12.1.4 uses them for
    # deterministic sensitivity identification on structured content.
    sensitive_fields: list[str] = Field(default_factory=list)
    valid_until: AwareDatetime | None = None
    reasons: list[str] = Field(default_factory=list)


class EgressRule(ExtModel):
    rule_id: str = Field(min_length=1)
    effect: Literal["allow", "allow_masked", "deny"]
    # Deployment positions this rule applies to; empty means all.
    deployments: list[Literal["local", "private_cloud", "vendor_api"]] = Field(
        default_factory=list
    )
    # ``None`` matches any content; ``True`` only content flagged sensitive
    # by the deterministic identifier; ``False`` only clean content.
    sensitive: bool | None = None
    reasons: list[str] = Field(default_factory=list)


class PolicyDocument(ExtModel):
    policy_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    rules: list[PolicyRule] = Field(default_factory=list)
    egress_rules: list[EgressRule] = Field(default_factory=list)
    # Default validity window for minted AccessDecisions (seconds).
    default_validity_seconds: int = Field(default=3600, ge=1)
