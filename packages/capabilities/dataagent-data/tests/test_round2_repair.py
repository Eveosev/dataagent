"""Round-2 repair acceptance: trace migration, OCR geometry, anchors, digests.

Each test encodes one item of the lead repair order that had no dedicated
regression test before.
"""

from __future__ import annotations

import io
import sqlite3

from conftest import build_pdf, build_pdf_pages, call, file_ref, write_file

from dataagent_contracts.core import SourceAnchor
from dataagent_data.contracts.layer import DocumentContent, PageContent
from dataagent_data.anchors import (
    anchor_value_mismatch,
    find_text_span,
    find_value_span,
)


# --- P0-1: trace store and shared writer -----------------------------------


def test_duplicate_correction_returns_stored_payload_ref(runtime, ctx):
    payload = {
        "task_ref": "task:dup@r1",
        "target_ref": "rec:1@r1",
        "field_id": "amount",
        "old_value": 1,
        "new_value": 2,
        "explanation": "typo",
        "scope_ref": "tenant:test",
        "event_id": "evt:dup",
        "kernel_session_id": "sess:dup",
    }
    first = call("append_user_correction", payload, ctx, runtime)
    second = call("append_user_correction", payload, ctx, runtime)
    assert first.status.value == "ok", first.issues
    assert second.status.value == "ok", second.issues
    assert second.data.payload_ref == first.data.payload_ref
    records = runtime.traces.read_from("task:dup@r1")
    assert len(records) == 1
    assert records[0].cursor == 1


def test_legacy_trace_database_is_migrated(tmp_path):
    from dataagent_data.adapters.storage.sqlite import (
        SqliteDatabase,
        SqliteTraceRepository,
    )

    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE trace_events (
            session_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            cursor INTEGER NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            ts_ms INTEGER NOT NULL,
            PRIMARY KEY (session_id, event_id),
            UNIQUE (session_id, cursor)
        );
        """
    )
    connection.execute(
        "INSERT INTO trace_events VALUES "
        "('task:old', 'evt:old', 1, 'dataagent.note', '{}', 0)"
    )
    connection.commit()
    connection.close()

    repository = SqliteTraceRepository(SqliteDatabase(path))
    assert [record.event_id for record in repository.read_from("task:old")] == ["evt:old"]
    record, duplicate = repository.append(
        "task:old",
        event_id="evt:new",
        kind="dataagent.note",
        payload={"n": 1},
        ts_ms=1,
        kernel_session_id="sess:old",
    )
    assert duplicate is False
    assert record.cursor == 2
    assert [item.event_id for item in repository.read_by_kernel_session("sess:old")] == ["evt:new"]


def test_trace_atoms_reject_missing_task_ref(runtime, ctx):
    result = call(
        "append_task_event",
        {"event_id": "e", "event_type": "note", "actor_ref": "agent:1"},
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


# --- P0-3: source digest integrity -----------------------------------------


def test_malformed_content_digest_is_invalid_input(runtime, ctx, workspace):
    write_file(workspace, "data.csv", b"a,b\n1,2\n")
    reference = file_ref(workspace, "data.csv").model_copy(
        update={"content_digest": "not-a-digest"}
    )
    result = call("parse_delimited_file", {"file_ref": reference}, ctx, runtime)
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_ocr_output_carries_source_content_digest(runtime, ctx, workspace):
    runtime.ocr_engine = _FakeEngine([("abc", 0.9)])
    build_pdf(workspace / "scan.pdf", ["ignored"])
    source = file_ref(workspace, "scan.pdf").model_copy(update={"revision": "rev:input"})
    result = call("ocr_pdf", {"file_ref": source, "dpi": 72}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    assert result.data.source_content_digest == source.content_digest


# --- P0-4: anchor value checks ---------------------------------------------


def _content(text: str) -> DocumentContent:
    return DocumentContent(pages=[PageContent(page=1, text=text)])


def _anchor(content: DocumentContent) -> SourceAnchor:
    text = content.pages[0].text
    return SourceAnchor(
        source_ref="file:policy",
        source_revision="sha256:" + "a" * 64,
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": 0,
            "char_end": len(text),
        },
    )


def test_numeric_anchor_requires_exact_number():
    content = _content("Amount: 1.5 CNY")
    assert anchor_value_mismatch(content, _anchor(content), 15)
    assert anchor_value_mismatch(content, _anchor(content), 1.5) == ""


def test_numeric_anchor_respects_sign():
    content = _content("Balance: 500 CNY")
    assert anchor_value_mismatch(content, _anchor(content), -500)
    assert anchor_value_mismatch(content, _anchor(content), 500) == ""


def test_numeric_anchor_accepts_thousands_separator():
    content = _content("Amount: 5,800 CNY")
    assert anchor_value_mismatch(content, _anchor(content), "5800") == ""


def test_text_fallback_returns_precise_span():
    content = _content("Amount:5,800.00 CNY")
    found = find_text_span(content, "5800.00")
    assert found is not None
    page, start, end = found
    assert page == 1
    assert content.pages[0].text[start:end] == "5,800.00"


def test_text_fallback_does_not_fall_back_to_whole_page():
    content = _content("nothing relevant here")
    assert find_text_span(content, "5800") is None


def test_value_relocation_matches_whole_number_tokens():
    content = _content("Rate: 1.5; total ¥5,800.00")
    assert find_value_span(content, 15) is None
    found = find_value_span(content, 5800)
    assert found is not None
    assert content.pages[0].text[found[1] : found[2]] == "5,800.00"


# --- P0-5: OCR geometry ----------------------------------------------------


class _FakeEngine:
    engine_ref = "fake"
    engine_version = "1.0"

    def __init__(self, blocks: list[tuple[str, float]]):
        self._blocks = blocks
        self.seen: list[bytes] = []

    def recognize(self, image_bytes, *, lang=None):
        from dataagent_data.adapters.ocr.engine import OcrBlock

        self.seen.append(image_bytes)
        return [
            OcrBlock(text=text, bbox=[1, 2, 3, 4], confidence=score)
            for text, score in self._blocks
        ]


def _png(workspace, name: str = "src.png", size: tuple[int, int] = (40, 20)):
    from PIL import Image

    Image.new("RGB", size, "white").save(workspace / name)
    return file_ref(workspace, name)


def test_ocr_block_offsets_include_newline_separators(runtime, ctx, workspace):
    runtime.ocr_engine = _FakeEngine([("abc", 0.9), ("def", 0.9)])
    build_pdf(workspace / "scan.pdf", ["ignored"])
    result = call(
        "ocr_pdf",
        {"file_ref": file_ref(workspace, "scan.pdf"), "dpi": 72},
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    content = runtime.content.get_json(result.data.document.blocks_ref)
    page = content["pages"][0]
    assert page["text"] == "abc\ndef"
    assert [(b["char_start"], b["char_end"]) for b in page["blocks"]] == [
        (0, 3),
        (4, 7),
    ]
    for block in page["blocks"]:
        assert page["text"][block["char_start"] : block["char_end"]] == block["text"]


def test_ocr_pdf_keeps_original_page_numbers(runtime, ctx, workspace):
    runtime.ocr_engine = _FakeEngine([("two", 0.9)])
    build_pdf_pages(workspace / "scan2.pdf", [["page one"], ["page two"]])
    result = call(
        "ocr_pdf",
        {"file_ref": file_ref(workspace, "scan2.pdf"), "pages": "2", "dpi": 72},
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    assert result.data.page_count == 1
    content = runtime.content.get_json(result.data.document.blocks_ref)
    assert content["pages"][0]["page"] == 2
    assert content["pages"][0]["blocks"][0]["page"] == 2


def test_ocr_image_region_crops_before_engine(runtime, ctx, workspace):
    from PIL import Image

    source = _png(workspace, size=(40, 20))
    engine = _FakeEngine([("x", 0.9)])
    runtime.ocr_engine = engine
    result = call(
        "ocr_image", {"file_ref": source, "region": "5,4,25,14"}, ctx, runtime
    )
    assert result.status.value == "ok", result.issues
    with Image.open(io.BytesIO(engine.seen[0])) as image:
        assert image.size == (20, 10)


def test_ocr_image_orientation_rotates_before_engine(runtime, ctx, workspace):
    from PIL import Image

    source = _png(workspace, size=(40, 20))
    engine = _FakeEngine([("x", 0.9)])
    runtime.ocr_engine = engine
    result = call(
        "ocr_image", {"file_ref": source, "orientation": "90"}, ctx, runtime
    )
    assert result.status.value == "ok", result.issues
    with Image.open(io.BytesIO(engine.seen[0])) as image:
        assert image.size == (20, 40)


def test_ocr_image_invalid_region_is_invalid_input(runtime, ctx, workspace):
    runtime.ocr_engine = _FakeEngine([("x", 0.9)])
    result = call(
        "ocr_image", {"file_ref": _png(workspace), "region": "nope"}, ctx, runtime
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


# --- P1-8: remaining per-atom negative coverage ----------------------------


def test_corrupt_workbook_calc_state_fails_cleanly(runtime, ctx, workspace):
    write_file(workspace, "broken.xlsx", b"not a zip")
    result = call(
        "inspect_workbook_calc_state",
        {"file_ref": file_ref(workspace, "broken.xlsx")},
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_ocr_pdf_missing_dependency_is_explicit(runtime, ctx, workspace, monkeypatch):
    from dataagent_data.adapters.ocr.engine import RapidOcrEngine

    monkeypatch.setattr(RapidOcrEngine, "create", classmethod(lambda cls: None))
    runtime.ocr_engine = None
    build_pdf(workspace / "scan.pdf", ["ignored"])
    result = call(
        "ocr_pdf", {"file_ref": file_ref(workspace, "scan.pdf")}, ctx, runtime
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "dependency_unavailable"
