"""W3.2: each parser output must retain the source FileRef.content_digest."""

from __future__ import annotations

import json

from conftest import build_pdf, call, file_ref, write_file


def assert_digest_present(result, source):
    blob = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert source.content_digest in blob, (
        f"{result.execution_ref.operation} output does not carry the source "
        f"content_digest {source.content_digest}: {blob[:400]}"
    )


def test_delimited_output_carries_source_content_digest(runtime, ctx, workspace):
    write_file(workspace, "data.csv", b"a,b\n1,2\n")
    source = file_ref(workspace, "data.csv").model_copy(update={"revision": "rev:input"})
    result = call("parse_delimited_file", {"file_ref": source}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    assert_digest_present(result, source)


def test_json_output_carries_source_content_digest(runtime, ctx, workspace):
    write_file(workspace, "records.json", b'[{"a": 1}]')
    source = file_ref(workspace, "records.json").model_copy(update={"revision": "rev:input"})
    result = call("parse_json_records", {"file_ref": source}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    assert_digest_present(result, source)


def test_pdf_output_carries_source_content_digest(runtime, ctx, workspace):
    build_pdf(workspace / "policy.pdf", ["Amount: 5800 CNY"])
    source = file_ref(workspace, "policy.pdf").model_copy(update={"revision": "rev:input"})
    result = call("parse_text_pdf", {"file_ref": source}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    assert_digest_present(result, source)
