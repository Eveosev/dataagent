"""DA10.1.1 / DA10.3.1 / DA10.3.3 presentation atoms (07 §5.5)."""

from __future__ import annotations

import io

from openpyxl import load_workbook

from dataagent_contracts.core import CapabilityStatus

from dataagent_application.presentation import reports, workbooks


def _scalar_result(value=300):
    return {
        "result_id": "res:abc",
        "target_ref": "req:1@r1",
        "form": "scalar",
        "value": value,
        "grain": "total",
        "unit": "CNY",
        "evidence_refs": ["spec:sql1"],
        "completeness": {
            "extent": "complete_in_declared_scope",
            "declared_scope": "SQL execution",
        },
        "sql_digest": "sha256:" + "a" * 64,
        "engine_binding": {"engine_id": "duckdb", "engine_version": "2.0.0"},
        "semantic_versions": ["mtd-amount@r1"],
        "assumptions": ["时间边界含月末"],
    }


def test_build_result_workbook_writes_values_only(runtime, ctx):
    result = workbooks.build_result_workbook(
        workbooks.BuildResultWorkbookInput.model_validate({"result": _scalar_result()}),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.sheets == ["结果", "口径与来源", "假设与未覆盖"]
    blob = runtime.content.get(result.data.asset.digest)
    book = load_workbook(io.BytesIO(blob))
    assert book["结果"]["A1"].value == "value"
    assert book["结果"]["A2"].value == 300
    rows = {r[0].value: r[1].value for r in book["口径与来源"].iter_rows(min_row=2)}
    assert rows["sql_digest"].startswith("sha256:")
    assert rows["engine"] == "duckdb@2.0.0"
    assert rows["metric_version"] == "mtd-amount@r1"
    # no formulas anywhere
    for sheet in book.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                assert not (isinstance(cell.value, str) and cell.value.startswith("="))


def test_build_result_workbook_table_form_loads_stored_rows(runtime, ctx):
    from tests.conftest import store_table
    from dataagent_application import helpers

    table = store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Total", "field_id": "total", "value_type": "number"},
        ],
        rows=[["north", 100], ["south", 200]],
    )
    # emulate a stored computed table
    payload = {
        "columns": [
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Total", "field_id": "total", "value_type": "number"},
        ],
        "rows": [["north", 100], ["south", 200]],
        "row_meta": [{"role": "detail", "reason": "computed"} for _ in range(2)],
    }
    digest = runtime.content.put(payload)
    table_id = "computed:abc123"
    revision = runtime.versions.save("computed_table", table_id, {"data_ref": digest, "row_count": 2})
    result_payload = {
        **_scalar_result(),
        "form": "table",
        "value": None,
        "table_ref": f"{table_id}@{revision}",
    }
    result = workbooks.build_result_workbook(
        workbooks.BuildResultWorkbookInput.model_validate({"result": result_payload}), ctx, runtime
    )
    assert result.status is CapabilityStatus.ok
    blob = runtime.content.get(result.data.asset.digest)
    book = load_workbook(io.BytesIO(blob))
    assert [c.value for c in book["结果"][1]] == ["Region", "Total"]
    assert book["结果"]["A2"].value == "north"


# --- DA10.3.1 / DA10.3.3 -------------------------------------------------------


REPORT_INPUT = {
    "title": "十月费用报告",
    "conclusion": "十月费用合计 300 元，环比上升。",
    "sections": [
        {
            "heading": "分区域明细",
            "body_markdown": "north 100，south 200。",
            "evidence_refs": ["field:amount", "table:tbl1"],
        }
    ],
    "evidence": [
        {
            "id": "field:amount",
            "evidence_type": "extracted_value",
            "value": 300,
            "obtained_by": "da07.1.3/execute_duckdb_sql",
            "source_anchors": [
                {
                    "source_ref": "doc-1",
                    "source_revision": "r1",
                    "selector": {"kind": "text_span", "unit_ref": "unit:char", "char_start": 0, "char_end": 12},
                }
            ],
        },
        {
            "id": "table:tbl1",
            "evidence_type": "computation_result",
            "obtained_by": "da07.1.3/execute_duckdb_sql",
        },
    ],
    "undecidable": ["c2 区域口径未判定"],
    "not_covered": ["十一月数据"],
    "acceptance_summary": "DA11.5.5 验收通过（示例）",
}


def test_compose_report_stores_draft_and_renders_markdown(runtime, ctx):
    result = reports.compose_document_report(
        reports.ComposeDocumentReportInput.model_validate(REPORT_INPUT), ctx, runtime
    )
    assert result.status is CapabilityStatus.ok
    draft = result.data.draft
    assert draft.evidence[0].source_anchors[0].source_ref == "doc-1"
    assert "依据" in result.data.markdown and "field:amount" in result.data.markdown
    stored = runtime.versions.get("report_draft", result.data.report_ref.id, result.data.report_ref.revision)
    assert stored["title"] == "十月费用报告"


def test_compose_report_rejects_unbacked_evidence_refs(runtime, ctx):
    bad = {**REPORT_INPUT, "sections": [{**REPORT_INPUT["sections"][0], "evidence_refs": ["ghost"]}]}
    from dataagent_runtime.errors import CapabilityError

    try:
        reports.compose_document_report(
            reports.ComposeDocumentReportInput.model_validate(bad), ctx, runtime
        )
        raised = False
    except CapabilityError as exc:
        raised = "no EvidenceRef backs" in str(exc)
    assert raised


def test_export_md_and_html_content_addressed(runtime, ctx):
    composed = reports.compose_document_report(
        reports.ComposeDocumentReportInput.model_validate(REPORT_INPUT), ctx, runtime
    )
    ref = composed.data.report_ref.model_dump(mode="json")
    exported = reports.export_report_format(
        reports.ExportReportFormatInput.model_validate({"report_ref": ref, "format": "md"}),
        ctx,
        runtime,
    )
    assert exported.status is CapabilityStatus.ok
    markdown = runtime.content.get_text(exported.data.asset.digest)
    assert "# 十月费用报告" in markdown
    assert any(i.code == "da10.export_not_publication" for i in exported.issues)

    html_out = reports.export_report_format(
        reports.ExportReportFormatInput.model_validate({"report_ref": ref, "format": "html"}),
        ctx,
        runtime,
    )
    html = runtime.content.get_text(html_out.data.asset.digest)
    assert "<h1>十月费用报告</h1>" in html
    assert "<script>" not in html  # everything is escaped


def test_export_docx_without_dependency_is_unavailable_not_silent(runtime, ctx):
    import importlib.util

    composed = reports.compose_document_report(
        reports.ComposeDocumentReportInput.model_validate(REPORT_INPUT), ctx, runtime
    )
    ref = composed.data.report_ref.model_dump(mode="json")
    if importlib.util.find_spec("docx") is not None:
        out = reports.export_report_format(
            reports.ExportReportFormatInput.model_validate({"report_ref": ref, "format": "docx"}),
            ctx,
            runtime,
        )
        assert out.status is CapabilityStatus.ok
        blob = runtime.content.get(out.data.asset.digest)
        assert blob[:2] == b"PK"  # xlsx/docx zip container
    else:
        from dataagent_runtime.errors import CapabilityError

        try:
            reports.export_report_format(
                reports.ExportReportFormatInput.model_validate({"report_ref": ref, "format": "docx"}),
                ctx,
                runtime,
            )
            raised = False
        except CapabilityError as exc:
            raised = "python-docx" in str(exc) or "dependency" in str(exc)
        assert raised


def test_export_requires_draft_or_ref(runtime, ctx):
    from dataagent_runtime.errors import CapabilityError

    try:
        reports.export_report_format(
            reports.ExportReportFormatInput.model_validate({"format": "md"}), ctx, runtime
        )
        raised = False
    except CapabilityError:
        raised = True
    assert raised
