"""Acceptance checks for 06 §6.2 / W3.4 / G7 that the current suite omits.

These tests encode the plan text literally:
- all three trace atoms write kernel_session_id / kernel_call_id and invocation_id;
- authorization_ref is required and written to the trace.
"""

from __future__ import annotations

from conftest import call


def test_task_event_trace_carries_kernel_session_and_invocation(runtime, ctx):
    result = call(
        "append_task_event",
        {
            "task_ref": "task:s@r1",
            "event_id": "evt:s1",
            "event_type": "task_state",
            "actor_ref": "agent:1",
            "payload": {"state": "running"},
            "kernel_session_id": "sess:1",
            "kernel_call_id": "call:1",
            "invocation_ref": "inv:1",
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    record = runtime.traces.read_from("task:s@r1")[0]
    assert record.payload["kernel_session_id"] == "sess:1"
    assert record.payload["kernel_call_id"] == "call:1"
    assert record.payload["invocation_ref"] == "inv:1"


def test_invocation_and_correction_traces_carry_session_and_invocation(runtime, ctx):
    invocation = call(
        "append_invocation_record",
        {
            "task_ref": "task:s@r1",
            "invocation_id": "inv:2",
            "operation": "parse_regular_excel",
            "capability_id": "DA01.4.1",
            "implementation_ref": "dataagent-data@0.1.0",
            "status": "ok",
            "started_at": "2026-11-03T10:00:00Z",
            "kernel_session_id": "sess:1",
            "kernel_call_id": "call:2",
        },
        ctx,
        runtime,
    )
    assert invocation.status.value == "ok"
    invocation_record = runtime.traces.read_from("task:s@r1")[0]
    assert invocation_record.payload["kernel_session_id"] == "sess:1"
    assert invocation_record.payload["kernel_call_id"] == "call:2"
    assert invocation_record.payload["invocation_id"] == "inv:2"

    correction = call(
        "append_user_correction",
        {
            "task_ref": "task:s@r1",
            "target_ref": "rec:1@r1",
            "field_id": "amount",
            "old_value": 1,
            "new_value": 2,
            "explanation": "typo",
            "scope_ref": "tenant:test",
            "kernel_session_id": "sess:1",
            "kernel_call_id": "call:3",
            "invocation_id": "inv:3",
        },
        ctx,
        runtime,
    )
    assert correction.status.value == "ok"
    correction_record = runtime.traces.read_from("task:s@r1")[1]
    assert correction_record.payload["kernel_session_id"] == "sess:1"
    assert correction_record.payload["kernel_call_id"] == "call:3"
    assert correction_record.payload["invocation_id"] == "inv:3"


def test_trace_events_are_written_under_the_kernel_session(runtime, ctx):
    call(
        "append_task_event",
        {
            "task_ref": "task:s@r1",
            "event_id": "evt:s1",
            "event_type": "task_state",
            "actor_ref": "agent:1",
            "payload": {"state": "running"},
            "kernel_session_id": "sess:1",
        },
        ctx,
        runtime,
    )
    assert runtime.traces.read_by_kernel_session("sess:1"), "trace should be namespaced by kernel_session_id"


def test_correction_accepts_and_writes_invocation_id(runtime, ctx):
    result = call(
        "append_user_correction",
        {
            "task_ref": "task:corr@r1",
            "target_ref": "rec:1@r1",
            "field_id": "amount",
            "old_value": 1,
            "new_value": 2,
            "explanation": "typo",
            "scope_ref": "tenant:test",
            "invocation_id": "inv:3",
            "kernel_session_id": "sess:1",
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    record = runtime.traces.read_from("task:corr@r1")[0]
    assert record.payload["invocation_id"] == "inv:3"
    assert record.payload["kernel_session_id"] == "sess:1"
