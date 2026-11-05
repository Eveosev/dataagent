from __future__ import annotations

import json
from datetime import datetime

from conftest import build_pdf, build_xlsx, call, file_ref, write_file


def test_parse_regular_excel(runtime, ctx, workspace):
    build_xlsx(
        workspace / "sales.xlsx",
        {
            "Sales": [
                ["name", "amount", "date"],
                ["a", 1, datetime(2026, 1, 1)],
                ["b", 2, datetime(2026, 1, 2)],
            ]
        },
    )
    result = call(
        "parse_regular_excel", {"file_ref": file_ref(workspace, "sales.xlsx")}, ctx, runtime
    )
    assert result.status.value == "ok", result.issues
    assert len(result.data.tables) == 1
    table = result.data.tables[0]
    assert table.asset.digest.startswith("sha256:")
    stored = runtime.content.get_json(table.data_ref)
    assert stored["rows"][0][0] == "a"
    assert result.data.workbook_ref.sheets == ["Sales"]


def test_parse_regular_excel_empty_sheet(runtime, ctx, workspace):
    from openpyxl import Workbook

    wb = Workbook()
    wb.save(workspace / "empty.xlsx")
    result = call(
        "parse_regular_excel", {"file_ref": file_ref(workspace, "empty.xlsx")}, ctx, runtime
    )
    assert result.status.value in {"ok", "partial"}
    assert result.data.tables == []
    assert any(issue.code == "da01.empty_sheet" for issue in result.issues)


def test_parse_irregular_excel_keeps_ambiguity(runtime, ctx, workspace):
    build_xlsx(
        workspace / "expense.xlsx",
        {
            "明细": [
                ["差旅报销明细"],
                [],
                ["部门", "金额", "日期"],
                ["研发", 100, datetime(2026, 1, 1)],
                [None, 200, datetime(2026, 1, 2)],
                ["合计", 300, None],
            ]
        },
    )
    source = file_ref(workspace, "expense.xlsx")
    result = call("extract_irregular_excel", {"file_ref": source}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    assert len(result.data.tables) == 1, result.issues
    assert len(result.data.regions) == 1
    assert result.data.regions[0].cell_range == "A3:C6"
    table = result.data.tables[0]
    stored = runtime.content.get_json(table.data_ref)
    assert stored["columns"][0]["name"] == "部门"
    assert stored["rows"][-1][0] == "合计"


def test_parse_delimited_flags_bad_rows(runtime, ctx, workspace):
    write_file(workspace, "data.csv", b"name,amount\na,1\nb,2,extra\n")
    result = call(
        "parse_delimited_file", {"file_ref": file_ref(workspace, "data.csv")}, ctx, runtime
    )
    assert result.status.value == "partial"
    assert result.data.row_count == 1
    assert len(result.data.bad_rows) == 1
    assert result.data.bad_rows[0]["cells"] == ["b", "2", "extra"]
    assert result.issues[0].code == "da01.bad_row"
    stored = runtime.content.get_json(result.data.table.data_ref)
    # The bad row is quarantined, not padded/truncated into the table.
    assert stored["rows"] == [["a", "1"]]


def test_parse_delimited_gbk_encoding(runtime, ctx, workspace):
    write_file(workspace, "gbk.csv", "名称,金额\n甲,1\n".encode("gbk"))
    result = call(
        "parse_delimited_file",
        {"file_ref": file_ref(workspace, "gbk.csv"), "encoding": "gbk"},
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    stored = runtime.content.get_json(result.data.table.data_ref)
    assert stored["rows"][0][0] == "甲"


def test_parse_json_records_jsonl_preserves_nesting(runtime, ctx, workspace):
    payload = "\n".join(
        json.dumps(obj)
        for obj in [{"id": 1, "body": {"total": 10}}, {"id": 2, "body": {"total": 20}}]
    ).encode()
    write_file(workspace, "records.jsonl", payload)
    result = call(
        "parse_json_records",
        {"file_ref": file_ref(workspace, "records.jsonl"), "format": "jsonl"},
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    assert result.data.batch.row_count == 2
    assert result.data.batch.inline_rows[0]["body"]["total"] == 10
    assert any(field["path"] == "/body/total" for field in result.data.fields)


def test_parse_json_records_bad_line_is_reported(runtime, ctx, workspace):
    write_file(workspace, "bad.jsonl", b'{"id":1}\nnot-json\n')
    result = call(
        "parse_json_records",
        {"file_ref": file_ref(workspace, "bad.jsonl"), "format": "jsonl"},
        ctx,
        runtime,
    )
    assert result.status.value == "partial"
    assert result.data.bad_records


def test_parse_text_pdf(runtime, ctx, workspace):
    build_pdf(
        workspace / "policy.pdf",
        ["1. Scope", "This policy applies to expense claims.", "2. Approval", "Amount: 5800 CNY"],
    )
    result = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    assert result.status.value == "ok", result.issues
    assert result.data.page_count == 1
    content = runtime.content.get_json(result.data.document.blocks_ref)
    assert "5800" in content["pages"][0]["text"]
    assert content["pages"][0]["blocks"][0]["bbox"]


def test_inspect_workbook_calc_state_1904(runtime, ctx, workspace):
    build_xlsx(
        workspace / "calc1904.xlsx",
        {"Data": [["a", 1], ["b", "=A2+1"]]},
        date1904=True,
    )
    result = call(
        "inspect_workbook_calc_state",
        {"file_ref": file_ref(workspace, "calc1904.xlsx")},
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    state = result.data.state
    assert state.date_system == "1904"
    assert state.formula_cells[0].formula == "=A2+1"
    assert state.needs_recalc


def test_corrupt_workbook_returns_failed_not_exception(runtime, ctx, workspace):
    write_file(workspace, "broken.xlsx", b"this is not a zip")
    result = call(
        "parse_regular_excel", {"file_ref": file_ref(workspace, "broken.xlsx")}, ctx, runtime
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_path_traversal_rejected(runtime, ctx, workspace, tmp_path):
    (tmp_path / "secret.txt").write_text("top secret")
    write_file(workspace, "data.csv", b"a\n1\n")
    ref = file_ref(workspace, "data.csv")
    escaped = ref.model_copy(update={"locator": "../secret.txt"})
    result = call("parse_delimited_file", {"file_ref": escaped}, ctx, runtime)
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_absolute_path_rejected(runtime, ctx, workspace):
    write_file(workspace, "data.csv", b"a\n1\n")
    ref = file_ref(workspace, "data.csv")
    for locator in ("/etc/passwd", "sub/../../etc/passwd"):
        result = call(
            "parse_delimited_file",
            {"file_ref": ref.model_copy(update={"locator": locator})},
            ctx,
            runtime,
        )
        assert result.status.value == "failed"
        assert result.issues[0].code == "invalid_input"


def test_source_digest_mismatch_rejected(runtime, ctx, workspace):
    write_file(workspace, "data.csv", b"a\n1\n")
    ref = file_ref(workspace, "data.csv")
    bad = ref.model_copy(update={"digest": "sha256:" + "0" * 64, "content_digest": "sha256:" + "0" * 64})
    result = call("parse_delimited_file", {"file_ref": bad}, ctx, runtime)
    assert result.status.value == "failed"
    assert result.issues[0].code == "source_changed"


def test_ocr_missing_dependency_is_explicit(runtime, ctx, workspace, monkeypatch):
    from dataagent_data.adapters.ocr.engine import RapidOcrEngine

    monkeypatch.setattr(RapidOcrEngine, "create", classmethod(lambda cls: None))
    runtime.ocr_engine = None
    write_file(workspace, "img.png", b"\x89PNG\r\n\x1a\nfake")
    result = call(
        "ocr_image", {"file_ref": file_ref(workspace, "img.png")}, ctx, runtime
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "dependency_unavailable"


def test_ocr_with_injected_engine(runtime, ctx, workspace):
    from dataagent_data.adapters.ocr.engine import OcrBlock

    class FakeEngine:
        engine_ref = "fake"
        engine_version = "1.0"

        def recognize(self, image_bytes, *, lang=None):
            return [OcrBlock(text="5800", bbox=[1, 2, 3, 4], confidence=0.55)]

    runtime.ocr_engine = FakeEngine()
    write_file(workspace, "img.png", b"\x89PNG\r\n\x1a\nfake")
    result = call(
        "ocr_image", {"file_ref": file_ref(workspace, "img.png")}, ctx, runtime
    )
    assert result.status.value == "partial", result.issues
    assert result.data.document.content_type == "image"
    assert result.data.document.ocr.engine_ref == "fake"
    assert result.data.document.ocr.low_confidence_pages == [1]
    content = runtime.content.get_json(result.data.document.blocks_ref)
    assert content["pages"][0]["text"] == "5800"


def test_ocr_pdf_with_injected_engine(runtime, ctx, workspace):
    from dataagent_data.adapters.ocr.engine import OcrBlock

    class FakeEngine:
        engine_ref = "fake"
        engine_version = "1.0"

        def recognize(self, image_bytes, *, lang=None):
            return [OcrBlock(text="scanned", bbox=[1, 2, 3, 4], confidence=0.9)]

    runtime.ocr_engine = FakeEngine()
    build_pdf(workspace / "scan.pdf", ["ignored"])
    result = call(
        "ocr_pdf",
        {"file_ref": file_ref(workspace, "scan.pdf"), "dpi": 72},
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    assert result.data.page_count == 1
    assert result.data.document.ocr.engine_ref == "fake"
    content = runtime.content.get_json(result.data.document.blocks_ref)
    assert content["pages"][0]["text"] == "scanned"


def test_symlink_escape_rejected(runtime, ctx, workspace, tmp_path):
    outside = tmp_path / "outside.csv"
    outside.write_text("secret")
    (workspace / "link.csv").symlink_to(outside)
    ref = file_ref(workspace, "link.csv")
    result = call("parse_delimited_file", {"file_ref": ref}, ctx, runtime)
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_irregular_region_candidate_and_header_hint(runtime, ctx, workspace):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "S"
    ws.append(["Group", "Group"])
    ws.append(["Name", "Amt"])
    ws.append(["a", 1])
    ws.append(["b", 2])
    wb.save(workspace / "hinted.xlsx")
    result = call(
        "extract_irregular_excel",
        {
            "file_ref": file_ref(workspace, "hinted.xlsx"),
            "regions": ["S!A1:B4"],
            "layout_hints": {"header_rows": 2},
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    table = runtime.content.get_json(result.data.tables[0].data_ref)
    assert table["columns"][0]["name"] == "Group / Name"
    assert table["rows"] == [["a", 1], ["b", 2]]


def test_repository_fixtures_are_parseable(runtime, ctx, workspace):
    import shutil
    from pathlib import Path

    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    shutil.copy2(fixtures / "claims.csv", workspace / "claims.csv")
    shutil.copy2(fixtures / "expense.json", workspace / "expense.json")
    csv_result = call(
        "parse_delimited_file",
        {"file_ref": file_ref(workspace, "claims.csv")},
        ctx,
        runtime,
    )
    assert csv_result.status.value == "ok"
    assert csv_result.data.row_count == 3
    json_result = call(
        "parse_json_records",
        {"file_ref": file_ref(workspace, "expense.json")},
        ctx,
        runtime,
    )
    assert json_result.status.value == "ok"
    assert json_result.data.batch.row_count == 3
