"""Governance contracts (05-contracts.md §3.3.7)."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from ._base import ExtModel  # noqa: E402

from .refs import VersionedRef
from .vocab import AccessOutcome, EgressOutcome

__all__ = ["AccessDecision", "EgressDecision", "ComponentMeta"]


_Model = ExtModel


class AccessDecision(_Model):
    decision_id: str = Field(min_length=1)
    policy_ref: VersionedRef
    subject_ref: str = Field(min_length=1)
    requester_ref: str | None = None
    action: Literal["read"] = "read"
    resource_ref: VersionedRef
    purpose: str = Field(min_length=1)
    decision: AccessOutcome
    field_constraints: list[str] | None = None
    row_constraints: str | None = None
    masking_obligations: list[str] = Field(default_factory=list)
    valid_until: AwareDatetime
    reasons: list[str] = Field(default_factory=list)

    @property
    def effective_outcome(self) -> AccessOutcome:
        """``indeterminate`` is treated as deny (05 §3.3.7)."""
        return AccessOutcome.allow if self.decision is AccessOutcome.allow else AccessOutcome.deny

    def is_allowed(self) -> bool:
        return self.decision is AccessOutcome.allow


class ModelDestination(ExtModel):
    model_config = ConfigDict(extra="forbid")
    model_ref: str = Field(min_length=1)
    deployment: Literal["local", "private_cloud", "vendor_api"]
    terms_ref: str | None = None


class EgressDecision(_Model):
    decision_id: str = Field(min_length=1)
    content_refs: list[VersionedRef] = Field(min_length=1)
    destination: ModelDestination
    decision: EgressOutcome
    visible_fields: list[str] | None = None
    masking_ref: str | None = None
    access_decision_ref: str = Field(min_length=1)
    receipt_ref: str | None = None

    @model_validator(mode="after")
    def _masked_requires_ref(self) -> "EgressDecision":
        if self.decision is EgressOutcome.allow_masked and not self.masking_ref:
            raise ValueError("allow_masked egress requires masking_ref")
        return self


class ComponentMeta(_Model):
    component_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    capability_ids: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    implementation_ref: str = Field(min_length=1)
    license: str = Field(min_length=1)
    weights_license: str | None = None
    data_license: str | None = None
    distribution: list[Literal["internal", "customer_site", "minthub_public"]] = Field(
        default_factory=list
    )
    requires_contracts: str = Field(min_length=1)
    runtime_requirements: list[str] = Field(default_factory=list)
