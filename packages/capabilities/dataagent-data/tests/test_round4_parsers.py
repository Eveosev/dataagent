"""Round 4 parsing/semantics edge cases (06 §14 item 5)."""

from __future__ import annotations

import json

from conftest import build_pdf, call, file_ref, write_file


def test_latin1_fallback_is_reported(runtime, ctx, workspace):
    write_file(workspace, "legacy.csv", "name,note\ncaf\xe9,ok\n".encode("latin-1"))
    result = call(
        "parse_delimited_file",
        {"file_ref": file_ref(workspace, "legacy.csv")},
        ctx,
        runtime,
    )
    assert result.data.encoding == "latin-1"
    assert any(issue.code == "da01.encoding_fallback" for issue in result.issues)
    assert result.status.value == "partial"


def test_json_pointer_records_path_unescapes_tokens(runtime, ctx, workspace):
    document = {
        "a/b": [
            {"items": [{"m~n": 1}]},
            {"items": [{"m~n": 2}]},
        ]
    }
    write_file(workspace, "data.json", json.dumps(document).encode())
    result = call(
        "parse_json_records",
        {
            "file_ref": file_ref(workspace, "data.json"),
            "records_path": "/a~1b/1/items",
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    paths = {field["path"] for field in result.data.fields}
    assert "/m~0n" in paths
    assert result.data.batch.inline_rows == [{"m~n": 2}]


def test_dedupe_names_never_reuses_a_generated_suffix():
    from dataagent_data.adapters.parsers.excel import dedupe_names

    assert dedupe_names(["a", "a_2", "a"]) == ["a", "a_2", "a_3"]
    assert dedupe_names(["a", "a", "a_2"]) == ["a", "a_2", "a_2_2"]


def test_heading_one_and_one_point_one_are_linked(runtime, ctx, workspace):
    build_pdf(workspace / "outline.pdf", ["1. Scope", "1.1 Claims", "Claim body"])
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "outline.pdf")}, ctx, runtime
    )
    result = call("segment_document", {"document_ref": parsed.data.document}, ctx, runtime)
    units = result.data.units
    by_ordinal = {unit.ordinal_path: unit for unit in units}
    assert "1" in by_ordinal
    assert "1.1" in by_ordinal
    assert by_ordinal["1"].asset.id in by_ordinal["1.1"].context_refs
    assert all(unit.anchors for unit in units)
    assert all(
        not (anchor.selector.page == 1 and anchor.selector.char_start == 0 and anchor.selector.char_end == 0)
        for unit in units
        for anchor in unit.anchors
    )
