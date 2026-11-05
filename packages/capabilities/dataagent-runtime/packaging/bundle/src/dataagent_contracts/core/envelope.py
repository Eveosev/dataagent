"""Call envelope: context, result, issues, execution provenance."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from ._base import ExtModel, NAMESPACE_PATTERN  # noqa: E402

from .refs import SourceAnchor, VersionedRef
from .vocab import (
    CapabilityStatus,
    CompletenessExtent,
    Severity,
    StandardErrorCode,
)

_STANDARD_CODES = {code.value for code in StandardErrorCode}

__all__ = [
    "CallContext",
    "Budget",
    "CapabilityResult",
    "Issue",
    "ExecutionRef",
    "Continuation",
    "Completeness",
]

T = TypeVar("T")


_Model = ExtModel


class Budget(_Model):
    max_seconds: int | None = Field(default=None, ge=0)
    max_rows: int | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, ge=0)
    max_cost: float | None = Field(default=None, ge=0)
    currency: str | None = None


class CallContext(_Model):
    request_id: str = Field(min_length=1)
    scope_ref: str = Field(min_length=1)
    authorization_ref: str = Field(min_length=1)
    # Trusted-host authority (08 §2 / feasibility review 2026-11-04 §7): the
    # executing subject and the purpose of the call are fixed by the trusted
    # host configuration, never by call arguments. DA12.1 reads them from
    # here; operation inputs cannot override them.
    subject_ref: str | None = None
    purpose: str | None = None
    requester_ref: str | None = None
    task_ref: VersionedRef | None = None
    kernel_session_id: str | None = None
    kernel_call_id: str | None = None
    deadline: AwareDatetime | None = None
    budget: Budget | None = None
    expected_revision: str | None = None
    idempotency_key: str | None = None


class Issue(_Model):
    code: str = Field(min_length=1)
    severity: Severity
    message: str = Field(min_length=1)
    target: str | None = None
    source_anchor: SourceAnchor | None = None
    retryable: bool
    suggested_action: str | None = None
    alternatives: list[Any] | None = None
    # Field calibration for the two-phase inference protocol (06 §5 / §9 step 7):
    # 05 §3.3.1 lists suggested_action/alternatives but the protocol also needs a
    # machine-readable inference request. Kept optional and additive.
    inference_request: dict[str, Any] | None = None

    @field_validator("code")
    @classmethod
    def _code_is_standard_or_namespaced(cls, value: str) -> str:
        if value in _STANDARD_CODES:
            return value
        if not NAMESPACE_PATTERN.match(value):
            raise ValueError(
                f"Issue.code {value!r} must be a StandardErrorCode or a dotted "
                "namespace like 'da02.anchor_not_found'"
            )
        return value

    @classmethod
    def standard(
        cls,
        code: StandardErrorCode | str,
        message: str,
        *,
        severity: Severity = Severity.error,
        retryable: bool = False,
        suggested_action: str | None = None,
        target: str | None = None,
    ) -> "Issue":
        return cls(
            code=code.value if isinstance(code, StandardErrorCode) else code,
            severity=severity,
            message=message,
            retryable=retryable,
            suggested_action=suggested_action,
            target=target,
        )


class ExecutionRef(_Model):
    invocation_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    implementation_ref: str = Field(min_length=1)
    input_versions: list[VersionedRef] = Field(default_factory=list)
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    receipt_ref: str | None = None


class Continuation(_Model):
    cursor: str | None = None
    job_ref: str | None = None
    subscription_ref: str | None = None
    resume_condition: str | None = None


class Completeness(_Model):
    extent: CompletenessExtent
    declared_scope: str = Field(min_length=1)
    observed: dict[str, int] | None = None
    reason: str | None = None
    snapshot_consistent: bool | None = None


class CapabilityResult(_Model, Generic[T]):
    status: CapabilityStatus
    data: T | None = None
    issues: list[Issue] = Field(default_factory=list)
    execution_ref: ExecutionRef | None = None
    provenance: list[VersionedRef] = Field(default_factory=list)
    completeness: Completeness | None = None
    continuation: Continuation | None = None

    @model_validator(mode="after")
    def _status_constraints(self) -> "CapabilityResult[T]":
        if self.status is CapabilityStatus.failed and not self.issues:
            raise ValueError("failed result requires at least one Issue")
        if self.status is CapabilityStatus.failed and self.data is not None:
            raise ValueError("failed result must not carry data")
        if self.status is CapabilityStatus.partial:
            extent = self.completeness.extent if self.completeness else None
            is_complete = extent is CompletenessExtent.complete_in_declared_scope
            if not self.issues and (self.completeness is None or is_complete):
                raise ValueError(
                    "partial result requires issues or a completeness extent other than "
                    "complete_in_declared_scope"
                )
        if self.status is CapabilityStatus.pending:
            if not self.continuation or not self.continuation.job_ref:
                raise ValueError("pending result requires continuation.job_ref")
        if self.status is CapabilityStatus.needs_input:
            if not any(i.suggested_action or i.alternatives for i in self.issues):
                raise ValueError(
                    "needs_input result requires an Issue with suggested_action or alternatives"
                )
        return self

    @classmethod
    def ok(cls, data: T, **kwargs: Any) -> "CapabilityResult[T]":
        return cls(status=CapabilityStatus.ok, data=data, **kwargs)

    @classmethod
    def failure(cls, issue: Issue, **kwargs: Any) -> "CapabilityResult[T]":
        return cls(status=CapabilityStatus.failed, data=None, issues=[issue], **kwargs)

    @classmethod
    def needs_clarification(cls, issue: Issue, **kwargs: Any) -> "CapabilityResult[T]":
        return cls(status=CapabilityStatus.needs_input, data=None, issues=[issue], **kwargs)
