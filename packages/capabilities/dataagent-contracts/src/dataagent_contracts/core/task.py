"""Task context, trace events and corrections (05-contracts.md §3.3.5)."""

from __future__ import annotations

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from ._base import ExtModel  # noqa: E402

from .refs import VersionedRef
from .vocab import TraceEventType

__all__ = ["TaskContextRef", "TraceEventRef", "CorrectionRef"]


_Model = ExtModel


class TaskContextRef(_Model):
    task_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    parent_revision: str | None = None
    selected_refs: list[VersionedRef] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class TraceEventRef(_Model):
    event_id: str = Field(min_length=1)
    task_ref: VersionedRef
    event_type: TraceEventType
    timestamp: AwareDatetime
    actor_ref: str = Field(min_length=1)
    payload_ref: str = Field(min_length=1)
    invocation_ref: str | None = None
    kernel_session_id: str | None = None
    kernel_call_id: str | None = None
    kernel_cursor: int | None = Field(default=None, ge=1)


class CorrectionRef(TraceEventRef):
    target_ref: VersionedRef
    field_id: str | None = None
    old_value: Any | None = None
    new_value: Any | None = None
    explanation: str = Field(min_length=1)
    scope_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _is_correction(self) -> "CorrectionRef":
        if self.event_type is not TraceEventType.correction:
            raise ValueError("CorrectionRef.event_type must be 'correction'")
        return self
