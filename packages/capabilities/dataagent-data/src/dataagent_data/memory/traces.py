"""DA04.1 task trace atoms backed by the kernel-shaped append-only store."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    CorrectionRef,
    TraceEventRef,
    TraceEventType,
    VersionedRef,
)

from dataagent_data import helpers
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _append(
    runtime,
    *,
    task_ref: VersionedRef,
    event_id: str,
    event_type: TraceEventType,
    payload: dict[str, Any],
    timestamp: datetime | None,
    actor_ref: str,
    invocation_ref: str | None,
    invocation_id: str | None = None,
    kernel_session_id: str | None = None,
    kernel_call_id: str | None = None,
    authorization_ref: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Shared writer: every trace atom persists the same enriched envelope."""

    ts = timestamp or helpers.now()
    # A naive timestamp is a client format error (the contract requires
    # AwareDatetime). Reject it *before* any write so a failed call leaves no
    # cursor advance behind (reviewer F6b); previously the event was stored
    # and only the output validation failed afterwards.
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise invalid_input(
            f"timestamp must be timezone-aware: {ts.isoformat()}",
            target="timestamp",
        )
    # Check event identity before writing the payload: on a conflicting
    # re-submit the storage layer raises, and a pre-write would leave content
    # that no event references (r5-plan item 5).
    existing = runtime.traces.get_event(str(task_ref), event_id)
    payload_ref = (
        existing.payload.get("payload_ref")
        if existing is not None and "payload_ref" in existing.payload
        else runtime.content.put(payload)
    )
    # ``actor_ref`` is part of the persisted event identity (reviewer F6a):
    # the store compares the enriched payload on a duplicate submit, so a
    # different actor is refused as a version conflict instead of silently
    # re-stating who performed the event, and a replay returns the actor that
    # was recorded first.
    enriched = {
        "payload_ref": payload_ref,
        "kernel_session_id": kernel_session_id,
        "kernel_call_id": kernel_call_id,
        "invocation_id": invocation_id,
        "invocation_ref": invocation_ref,
        "authorization_ref": authorization_ref,
        "actor_ref": actor_ref,
        "payload": payload,
    }
    record, duplicate = runtime.traces.append(
        str(task_ref),
        event_id=event_id,
        kind=f"dataagent.{event_type.value}",
        payload=enriched,
        ts_ms=int(ts.timestamp() * 1000),
        kernel_session_id=kernel_session_id,
    )
    stored_ref = record.payload.get("payload_ref", payload_ref)
    fields: dict[str, Any] = {
        "event_id": event_id,
        "task_ref": task_ref,
        "event_type": event_type,
        "timestamp": datetime.fromtimestamp(record.ts_ms / 1000, tz=ts.tzinfo),
        "actor_ref": record.payload.get("actor_ref", actor_ref),
        "payload_ref": stored_ref,
        "invocation_ref": invocation_ref,
        "kernel_session_id": kernel_session_id,
        "kernel_call_id": kernel_call_id,
        "kernel_cursor": None,
    }
    return fields, duplicate


class AppendTaskEventInput(_Model):
    task_ref: VersionedRef
    event_id: str = Field(min_length=1)
    event_type: TraceEventType = TraceEventType.task_state
    timestamp: datetime | None = None
    actor_ref: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    invocation_ref: str | None = None
    kernel_session_id: str | None = None
    kernel_call_id: str | None = None


@operation(
    "DA04.1.1",
    input_model=AppendTaskEventInput,
    output_model=TraceEventRef,
    writes=True,
    description="任务事件记录",
    idempotent=True,
)
def append_task_event(
    data: AppendTaskEventInput, ctx: CallContext, runtime
) -> CapabilityResult[TraceEventRef]:
    fields, duplicate = _append(
        runtime,
        task_ref=data.task_ref,
        event_id=data.event_id,
        event_type=data.event_type,
        payload=data.payload,
        timestamp=data.timestamp,
        actor_ref=data.actor_ref,
        invocation_ref=data.invocation_ref,
        kernel_session_id=data.kernel_session_id or ctx.kernel_session_id,
        kernel_call_id=data.kernel_call_id or ctx.kernel_call_id,
        authorization_ref=ctx.authorization_ref,
    )
    event = TraceEventRef(**fields)
    return CapabilityResult[TraceEventRef](
        status=CapabilityStatus.ok,
        data=event,
        issues=[],
        completeness=helpers.complete("trace event", {"duplicate": int(duplicate)}),
    )


class AppendInvocationRecordInput(_Model):
    task_ref: VersionedRef
    invocation_id: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    implementation_ref: str = Field(min_length=1)
    input_refs: list[str] = Field(default_factory=list)
    output_ref: str | None = None
    error: str | None = None
    status: str = "ok"
    started_at: datetime
    finished_at: datetime | None = None
    actor_ref: str = "dataagent-data"
    kernel_session_id: str | None = None
    kernel_call_id: str | None = None


@operation(
    "DA04.1.2",
    input_model=AppendInvocationRecordInput,
    output_model=TraceEventRef,
    writes=True,
    description="查询/工具调用记录",
    idempotent=True,
)
def append_invocation_record(
    data: AppendInvocationRecordInput, ctx: CallContext, runtime
) -> CapabilityResult[TraceEventRef]:
    event_id = f"invocation:{data.invocation_id}"
    fields, duplicate = _append(
        runtime,
        task_ref=data.task_ref,
        event_id=event_id,
        event_type=TraceEventType.invocation,
        payload={
            "invocation_id": data.invocation_id,
            "operation": data.operation,
            "capability_id": data.capability_id,
            "implementation_ref": data.implementation_ref,
            "input_refs": data.input_refs,
            "output_ref": data.output_ref,
            "error": data.error,
            "status": data.status,
            "started_at": data.started_at.isoformat(),
            "finished_at": data.finished_at.isoformat() if data.finished_at else None,
        },
        timestamp=data.started_at,
        actor_ref=data.actor_ref,
        invocation_ref=data.invocation_id,
        invocation_id=data.invocation_id,
        kernel_session_id=data.kernel_session_id or ctx.kernel_session_id,
        kernel_call_id=data.kernel_call_id or ctx.kernel_call_id,
        authorization_ref=ctx.authorization_ref,
    )
    event = TraceEventRef(**fields)
    return CapabilityResult[TraceEventRef](
        status=CapabilityStatus.ok,
        data=event,
        completeness=helpers.complete("invocation trace", {"duplicate": int(duplicate)}),
    )


class AppendUserCorrectionInput(_Model):
    task_ref: VersionedRef
    target_ref: VersionedRef
    field_id: str | None = None
    old_value: Any | None = None
    new_value: Any | None = None
    explanation: str = Field(min_length=1)
    scope_ref: str = Field(min_length=1)
    event_id: str | None = None
    timestamp: datetime | None = None
    actor_ref: str = "user"
    invocation_id: str | None = None
    kernel_session_id: str | None = None
    kernel_call_id: str | None = None


@operation(
    "DA04.1.3",
    input_model=AppendUserCorrectionInput,
    output_model=CorrectionRef,
    writes=True,
    description="用户纠正记录",
    idempotent=False,
)
def append_user_correction(
    data: AppendUserCorrectionInput, ctx: CallContext, runtime
) -> CapabilityResult[CorrectionRef]:
    event_id = data.event_id or f"correction:{uuid.uuid4().hex[:12]}"
    payload = {
        "target_ref": str(data.target_ref),
        "field_id": data.field_id,
        "old_value": data.old_value,
        "new_value": data.new_value,
        "explanation": data.explanation,
        "scope_ref": data.scope_ref,
    }
    fields, duplicate = _append(
        runtime,
        task_ref=data.task_ref,
        event_id=event_id,
        event_type=TraceEventType.correction,
        payload=payload,
        timestamp=data.timestamp,
        actor_ref=data.actor_ref,
        invocation_ref=data.invocation_id,
        invocation_id=data.invocation_id,
        kernel_session_id=data.kernel_session_id or ctx.kernel_session_id,
        kernel_call_id=data.kernel_call_id or ctx.kernel_call_id,
        authorization_ref=ctx.authorization_ref,
    )
    correction = CorrectionRef(
        **fields,
        target_ref=data.target_ref,
        field_id=data.field_id,
        old_value=data.old_value,
        new_value=data.new_value,
        explanation=data.explanation,
        scope_ref=data.scope_ref,
    )
    return CapabilityResult[CorrectionRef](
        status=CapabilityStatus.ok,
        data=correction,
        completeness=helpers.complete("user correction", {"duplicate": int(duplicate)}),
    )
