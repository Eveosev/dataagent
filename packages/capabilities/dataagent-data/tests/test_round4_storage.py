"""Round 4 storage/runtime guarantees (06 §14 item 4)."""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

import pytest
from pydantic import BaseModel

from dataagent_contracts.core import (
    CallContext,
    CapabilityStatus,
    StandardErrorCode,
)

from dataagent_data.adapters.storage.sqlite import (
    SqliteDatabase,
    SqliteTraceRepository,
    SqliteVersionedRepository,
)
from dataagent_runtime.errors import CapabilityError, invalid_input


def _version_writer(path: str, worker: int) -> None:
    repo = SqliteVersionedRepository(SqliteDatabase(path))
    for index in range(5):
        repo.save("thing", "shared", {"worker": worker, "index": index})


def _trace_writer(path: str, worker: int) -> None:
    repo = SqliteTraceRepository(SqliteDatabase(path))
    for index in range(5):
        repo.append(
            "task:shared",
            event_id=f"evt:{worker}:{index}",
            kind="dataagent.note",
            payload={"worker": worker, "index": index},
            ts_ms=worker * 10 + index,
            kernel_session_id="sess:shared",
        )


def test_concurrent_version_writes_do_not_collide(tmp_path):
    path = str(tmp_path / "db.sqlite3")
    SqliteDatabase(path)
    workers = [mp.Process(target=_version_writer, args=(path, number)) for number in range(4)]
    for process in workers:
        process.start()
    for process in workers:
        process.join(30)
        assert process.exitcode == 0

    repo = SqliteVersionedRepository(SqliteDatabase(path))
    revisions = repo.revisions("thing", "shared")
    assert len(revisions) == 20
    assert len(set(revisions)) == 20
    assert revisions == [f"r{index}" for index in range(1, 21)]


def test_concurrent_trace_append_has_unique_cursors(tmp_path):
    path = str(tmp_path / "db.sqlite3")
    SqliteDatabase(path)
    workers = [mp.Process(target=_trace_writer, args=(path, number)) for number in range(4)]
    for process in workers:
        process.start()
    for process in workers:
        process.join(30)
        assert process.exitcode == 0

    repo = SqliteTraceRepository(SqliteDatabase(path))
    records = repo.read_from("task:shared", 1, 100)
    assert len(records) == 20
    assert [record.cursor for record in records] == list(range(1, 21))


def test_same_event_id_with_different_payload_is_a_version_conflict(tmp_path):
    repo = SqliteTraceRepository(SqliteDatabase(tmp_path / "db.sqlite3"))
    first, duplicate = repo.append(
        "task:a", event_id="evt:1", kind="dataagent.note", payload={"x": 1}, ts_ms=1
    )
    assert duplicate is False
    same, duplicate = repo.append(
        "task:a", event_id="evt:1", kind="dataagent.note", payload={"x": 1}, ts_ms=999
    )
    assert duplicate is True and same.cursor == first.cursor
    with pytest.raises(CapabilityError) as caught:
        repo.append(
            "task:a", event_id="evt:1", kind="dataagent.note", payload={"x": 2}, ts_ms=1
        )
    assert caught.value.code is StandardErrorCode.version_conflict


def test_read_from_is_session_scoped_and_kernel_view_is_separate(tmp_path):
    repo = SqliteTraceRepository(SqliteDatabase(tmp_path / "db.sqlite3"))
    repo.append(
        "task:a",
        event_id="evt:a",
        kind="dataagent.note",
        payload={},
        ts_ms=1,
        kernel_session_id="sess:1",
    )
    repo.append(
        "task:b",
        event_id="evt:b",
        kind="dataagent.note",
        payload={},
        ts_ms=2,
        kernel_session_id="sess:1",
    )
    assert [record.event_id for record in repo.read_from("task:a")] == ["evt:a"]
    assert repo.read_from("sess:1") == []
    assert [record.event_id for record in repo.read_by_kernel_session("sess:1")] == [
        "evt:a",
        "evt:b",
    ]


class _Input(BaseModel):
    pass


def _spec(handler):  # noqa: ANN001
    from dataagent_data.registry import OperationSpec

    return OperationSpec(
        operation="boom",
        capability_id="DA99.0.0",
        source_file="src/dataagent_data/boom.py",
        input_model=_Input,
        output_model=_Input,
        handler=handler,
    )


def test_handler_value_error_is_execution_unknown(runtime, ctx, monkeypatch):
    import importlib

    invoke_module = importlib.import_module("dataagent_runtime.invoke")

    def boom(data, context, runtime_):  # noqa: ANN001
        raise ValueError("not client input")

    monkeypatch.setattr(invoke_module, "get_spec", lambda name: _spec(boom))
    result = invoke_module.invoke("boom", {}, ctx, runtime=runtime)
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "execution_unknown"


def test_explicit_capability_error_is_preserved(runtime, ctx, monkeypatch):
    import importlib

    invoke_module = importlib.import_module("dataagent_runtime.invoke")

    def boom(data, context, runtime_):  # noqa: ANN001
        raise invalid_input("bad field", target="field")

    monkeypatch.setattr(invoke_module, "get_spec", lambda name: _spec(boom))
    result = invoke_module.invoke("boom", {}, ctx, runtime=runtime)
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "invalid_input"
    assert result.issues[0].target == "field"


def test_tools_list_carries_write_annotations():
    from dataagent_data.interfaces.mcp_server import _tools

    tools = {tool["name"]: tool for tool in _tools()}
    assert len(tools) == 32
    # R1: every tool still advertises the context hint, but it is optional.
    # The runtime resolves host authority, so a strict MCP client that only
    # sends declared required arguments must remain able to call.
    for name, tool in tools.items():
        schema = tool["inputSchema"]
        assert "context" in schema["properties"], name
        assert "context" not in schema.get("required", []), name

    read = tools["inspect_workbook_calc_state"]["annotations"]
    idempotent_write = tools["register_extraction_schema_version"]["annotations"]
    non_idempotent_write = tools["define_metric_formula"]["annotations"]
    assert read["readOnlyHint"] is True and read["destructiveHint"] is False
    assert read["idempotentHint"] is True
    assert idempotent_write["readOnlyHint"] is False
    assert idempotent_write["destructiveHint"] is False
    assert idempotent_write["idempotentHint"] is True
    assert non_idempotent_write["readOnlyHint"] is False
    assert non_idempotent_write["destructiveHint"] is False
    assert non_idempotent_write["idempotentHint"] is False

    # Content-addressed writes are idempotent (same bytes => same object);
    # draft/event-id minting writes are not.
    idempotent_writes = {
        "append_task_event",
        "append_invocation_record",
        "register_extraction_schema_version",
        "extract_fields_to_schema",
        "anchor_extracted_values",
        "segment_document",
        "maintain_source_anchors",
        # Round 4.2: these eleven handlers persist file refs / tables /
        # document blocks / profiles (register_file_ref, store_table,
        # store_document_blocks, content.put) but were advertised read-only.
        "parse_regular_excel",
        "extract_irregular_excel",
        "parse_delimited_file",
        "parse_json_records",
        "parse_text_pdf",
        "ocr_pdf",
        "ocr_image",
        "recover_headers",
        "expand_merged_cells",
        "classify_table_rows",
        "profile_table_structure",
    }
    non_idempotent_writes = {
        "define_metric_formula",
        "define_business_rules",
        "define_rule_applicability",
        "append_user_correction",
        "assess_automatic_decidability",
        "define_rule_preconditions",
    }
    persistent_writes = idempotent_writes | non_idempotent_writes
    for name in idempotent_writes:
        assert tools[name]["annotations"]["idempotentHint"] is True, name
    for name in non_idempotent_writes:
        assert tools[name]["annotations"]["idempotentHint"] is False, name

    # Every operation that persists an object must be declared as a write.
    # This is per-operation, not an aggregate count: the previous versions of
    # this test only counted read-only tools and missed eleven persistent
    # writes still advertised as read-only (Round 4.2 P1).
    writes = {
        name
        for name, tool in tools.items()
        if not tool["annotations"]["readOnlyHint"]
    }
    assert writes == persistent_writes
    for name in persistent_writes:
        assert tools[name]["annotations"]["readOnlyHint"] is False, name
    assert len(persistent_writes) == 24
    assert len(writes) == 24
    assert len(idempotent_writes) == 18
    assert len(non_idempotent_writes) == 6

    read_only = set(tools) - writes
    assert read_only == {
        "inspect_workbook_calc_state",
        "detect_workbook_regions",
        "infer_field_types",
        "identify_evidence_or_human_gaps",
        "mark_automation_coverage",
        "resolve_decidability_cache",
        "normalize_precondition_references",
        "resolve_unknown_applicability",
    }
    assert len(read_only) == 8
    assert all(tools[name]["annotations"]["idempotentHint"] for name in read_only)

    # Exact aggregate: 32 total / 8 read-only / 24 writes / 18 idempotent / 6 not.
    assert (
        sum(
            1
            for tool in tools.values()
            if not tool["annotations"]["readOnlyHint"]
            and tool["annotations"]["idempotentHint"]
        )
        == 18
    )
    assert (
        sum(
            1
            for tool in tools.values()
            if not tool["annotations"]["readOnlyHint"]
            and not tool["annotations"]["idempotentHint"]
        )
        == 6
    )
    assert all(
        tool["annotations"]["destructiveHint"] is False for tool in tools.values()
    )


def _store_counts(runtime):
    """Count content-addressed blobs and versioned objects in the runtime."""

    import sqlite3

    content_files = sum(
        1 for path in runtime.content.root.rglob("*") if path.is_file()
    )
    with sqlite3.connect(runtime.versions.db.path) as conn:
        objects = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
    return content_files, objects


def test_persistent_tools_are_advertised_as_writes(runtime, ctx, workspace):
    """Runtime probes: representative handlers of each persistence path really
    write, and the tool annotation says so (Round 4.2 P1)."""

    from conftest import build_xlsx, call, file_ref, write_file

    from dataagent_data.interfaces.mcp_server import _tools

    tools = {tool["name"]: tool for tool in _tools()}

    write_file(workspace, "probe.csv", b"name,amount\na,1\n")
    write_file(workspace, "probe.json", b'[{"id": 1, "total": 10}]')
    build_xlsx(
        workspace / "probe.xlsx",
        {"S": [["name", "amount"], ["a", 1], ["b", 2]]},
    )

    for operation, payload in (
        ("parse_delimited_file", {"file_ref": file_ref(workspace, "probe.csv")}),
        ("parse_json_records", {"file_ref": file_ref(workspace, "probe.json")}),
    ):
        before = _store_counts(runtime)
        result = call(operation, payload, ctx, runtime)
        assert result.status.value in {"ok", "partial"}, (operation, result.issues)
        after = _store_counts(runtime)
        assert after[0] > before[0] or after[1] > before[1], operation
        assert tools[operation]["annotations"]["readOnlyHint"] is False, operation

    before = _store_counts(runtime)
    parsed = call(
        "parse_regular_excel",
        {"file_ref": file_ref(workspace, "probe.xlsx")},
        ctx,
        runtime,
    )
    assert parsed.status.value == "ok", parsed.issues
    after = _store_counts(runtime)
    assert after[0] > before[0] and after[1] > before[1]
    assert tools["parse_regular_excel"]["annotations"]["readOnlyHint"] is False

    table = parsed.data.tables[0]
    before = _store_counts(runtime)
    profile = call("profile_table_structure", {"table_ref": table}, ctx, runtime)
    assert profile.status.value == "ok", profile.issues
    after = _store_counts(runtime)
    assert after[0] > before[0]
    assert tools["profile_table_structure"]["annotations"]["readOnlyHint"] is False
