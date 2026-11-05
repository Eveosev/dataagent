from __future__ import annotations

from conftest import call


def test_append_task_event_dedupes_and_increments(runtime, ctx):
    payload = {
        "task_ref": "task:a@r1",
        "event_id": "evt:1",
        "event_type": "task_state",
        "actor_ref": "agent:1",
        "payload": {"state": "running"},
        "kernel_call_id": "call:1",
    }
    first = call("append_task_event", payload, ctx, runtime)
    assert first.status.value == "ok"
    duplicate = call("append_task_event", payload, ctx, runtime)
    assert duplicate.data.event_id == "evt:1"
    records = runtime.traces.read_from("task:a@r1")
    assert len(records) == 1
    assert records[0].cursor == 1
    assert records[0].payload["kernel_call_id"] == "call:1"

    call(
        "append_task_event",
        {**payload, "event_id": "evt:2", "payload": {"state": "done"}},
        ctx,
        runtime,
    )
    records = runtime.traces.read_from("task:a@r1")
    assert [record.cursor for record in records] == [1, 2]


def test_append_invocation_and_correction_share_one_writer(runtime, ctx):
    invocation = call(
        "append_invocation_record",
        {
            "task_ref": "task:b@r1",
            "invocation_id": "inv:1",
            "operation": "parse_regular_excel",
            "capability_id": "DA01.4.1",
            "implementation_ref": "dataagent-data@0.1.0",
            "input_refs": ["file:a@r1"],
            "status": "ok",
            "started_at": "2026-11-03T10:00:00Z",
            "finished_at": "2026-11-03T10:00:01Z",
        },
        ctx,
        runtime,
    )
    assert invocation.status.value == "ok"
    correction = call(
        "append_user_correction",
        {
            "task_ref": "task:b@r1",
            "target_ref": "rec:1@r1",
            "field_id": "amount",
            "old_value": 1,
            "new_value": 2,
            "explanation": "typo",
            "scope_ref": "tenant:test",
        },
        ctx,
        runtime,
    )
    assert correction.status.value == "ok"
    assert correction.data.event_type.value == "correction"
    records = runtime.traces.read_from("task:b@r1")
    assert [record.cursor for record in records] == [1, 2]
    assert records[0].kind == "dataagent.invocation"
    assert records[1].kind == "dataagent.correction"


def test_checkpoint_verifies_and_detects_change(runtime, ctx):
    call(
        "append_task_event",
        {
            "task_ref": "task:c@r1",
            "event_id": "evt:1",
            "event_type": "note",
            "actor_ref": "agent:1",
            "payload": {"n": 1},
        },
        ctx,
        runtime,
    )
    checkpoint = runtime.traces.checkpoint("task:c@r1")
    assert checkpoint["cursor"] == 1
    assert runtime.traces.verify_checkpoint(checkpoint) is True

    call(
        "append_task_event",
        {
            "task_ref": "task:c@r1",
            "event_id": "evt:2",
            "event_type": "note",
            "actor_ref": "agent:1",
            "payload": {"n": 2},
        },
        ctx,
        runtime,
    )
    assert runtime.traces.verify_checkpoint(checkpoint) is False
