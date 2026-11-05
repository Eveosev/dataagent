from __future__ import annotations

from conftest import call


def test_trace_records_authorization_ref(runtime, ctx):
    result = call(
        "append_task_event",
        {
            "task_ref": "task:auth@r1",
            "event_id": "evt:auth",
            "event_type": "task_state",
            "actor_ref": "agent:1",
            "payload": {},
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    record = runtime.traces.read_from("task:auth@r1")[0]
    assert record.payload["authorization_ref"] == ctx.authorization_ref
