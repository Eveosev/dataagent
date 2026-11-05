"""Round 4 acceptance probes not covered by the existing suite (06 §14).

Rows 1, 2, 4 and 5 of §14 are checked end-to-end here:

* row 1: a ``pages`` subset must still resolve ``pdf_bbox`` by page number;
* row 1: a rule condition whose text is not supported by its anchor must not
  survive as a grounded condition;
* row 2: the regular Excel parser must keep the original row numbers so a
  merged range after a skipped empty row is not reported as "outside table
  bounds";
* row 4: the decidability cache must be invalidated by a statement or
  requirement-revision change, not only by dependency changes;
* row 5: extraction and decidability results must be readable back from the
  VersionedRepository using the ids returned in their results.
"""

from __future__ import annotations

from openpyxl import Workbook

from conftest import build_pdf, build_pdf_pages, call, file_ref

from dataagent_data.preparation.documents import load_document_content
from dataagent_data import helpers
from dataagent_data.anchors import anchor_invalid_reason


# ---------------------------------------------------------------------------
# §14 row 2: regular Excel + empty row + merged range
# ---------------------------------------------------------------------------


def test_regular_excel_keeps_row_numbers_for_merges_after_empty_row(
    runtime, ctx, workspace
):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "S"
    sheet.append(["a", "b"])
    sheet.append(["x", 1])
    sheet.append([None, None])  # empty row that parse_regular_excel drops
    sheet.append(["y", 2])
    sheet.merge_cells("A4:A5")  # merged range starts after the dropped row
    path = workspace / "merged_with_gap.xlsx"
    workbook.save(path)

    parsed = call(
        "parse_regular_excel",
        {"file_ref": file_ref(workspace, path.name)},
        ctx,
        runtime,
    )
    assert parsed.status.value in {"ok", "partial"}, parsed.issues
    table = helpers.load_table(runtime, parsed.data.tables[0])
    assert table.rows == [["x", 1], ["y", 2]]
    # The producer must hand the original row numbers to expand_merged_cells.
    assert table.source.get("row_numbers") == [2, 4]

    expanded = call(
        "expand_merged_cells", {"table_ref": parsed.data.tables[0]}, ctx, runtime
    )
    assert expanded.status.value == "ok", [
        (issue.code, issue.message) for issue in expanded.issues
    ]
    assert [item["range"] for item in expanded.data.expanded_ranges] == ["A4:A5"]
    assert helpers.load_table(runtime, expanded.data.table).rows[-1][0] == "y"


def test_regular_excel_merge_over_skipped_row_does_not_overwrite_later_data(
    runtime, ctx, workspace
):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "S"
    sheet.append(["a", "b"])
    sheet.append(["x", 1])
    sheet.append([None, None])  # skipped by parse_regular_excel
    sheet.append(["y", 2])
    # The merged range covers the skipped row: the value of a *later* data row
    # (row 4) must never be overwritten with row 2's merged value.
    sheet.merge_cells("B2:B3")
    path = workspace / "merge_over_gap.xlsx"
    workbook.save(path)

    parsed = call(
        "parse_regular_excel",
        {"file_ref": file_ref(workspace, path.name)},
        ctx,
        runtime,
    )
    assert parsed.status.value in {"ok", "partial"}, parsed.issues
    table = helpers.load_table(runtime, parsed.data.tables[0])
    assert table.rows == [["x", 1], ["y", 2]]
    assert table.source.get("row_numbers") == [2, 4]

    expanded = call(
        "expand_merged_cells", {"table_ref": parsed.data.tables[0]}, ctx, runtime
    )
    assert expanded.status.value == "ok", [
        (issue.code, issue.message) for issue in expanded.issues
    ]
    assert helpers.load_table(runtime, expanded.data.table).rows == [
        ["x", 1],
        ["y", 2],
    ]


# ---------------------------------------------------------------------------
# §14 row 1: rule condition text must be grounded in its anchor
# ---------------------------------------------------------------------------


def test_business_rule_condition_text_must_match_its_anchor(runtime, ctx, workspace):
    build_pdf(
        workspace / "policy.pdf",
        ["1. Scope", "Claims above 5000 CNY require department head approval."],
    )
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    page_text = load_document_content(runtime, document).pages[0].text
    start = page_text.index("Claims above")
    end = page_text.index("approval.") + len("approval.")
    anchor = {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": end,
        },
    }

    result = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "Weather must be sunny on Mars",
                        "anchors": [anchor],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )

    # The anchor exists, but its text does not support the condition; the
    # ungrounded condition must not be accepted as a rule definition.
    assert result.status.value == "needs_input", result.issues
    assert result.data is None
    assert any(
        issue.code in {"da03.unanchored_condition", "da02.anchor_value_mismatch"}
        for issue in result.issues
    ), [(issue.code, issue.message) for issue in result.issues]


# ---------------------------------------------------------------------------
# §14 row 1: pages subset + pdf_bbox by page number (end-to-end)
# ---------------------------------------------------------------------------


def test_pdf_page_subset_still_resolves_bbox_by_page_number(runtime, ctx, workspace):
    build_pdf_pages(
        workspace / "three_pages.pdf", [["page one"], ["page two"], ["page three"]]
    )
    parsed = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "three_pages.pdf"), "pages": "2-3"},
        ctx,
        runtime,
    )
    assert parsed.status.value == "ok", parsed.issues
    content = load_document_content(runtime, parsed.data.document)
    assert [page.page for page in content.pages] == [2, 3]
    block = content.pages[1].blocks[0]
    from dataagent_contracts.core import SourceAnchor

    anchor = SourceAnchor(
        source_ref=parsed.data.document.original_ref.id,
        source_revision=parsed.data.document.original_ref.revision,
        selector={"kind": "pdf_bbox", "page": 3, "bbox": list(block.bbox)},
    )
    assert anchor_invalid_reason(content, anchor) == ""
    assert block.text in content.pages[1].text


# ---------------------------------------------------------------------------
# §14 row 1: a PDF line that cannot be located must not fabricate a span
# ---------------------------------------------------------------------------


def test_pdf_line_locate_failure_does_not_fabricate_char_range(monkeypatch):
    from dataagent_data.adapters.parsers import pdf as pdf_parser

    class FakePage:
        width = 100
        height = 100

        def extract_text(self):
            return "hello"

        def extract_text_lines(self):
            return [{"text": "HELLO", "x0": 0, "top": 0, "x1": 10, "bottom": 10}]

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def close(self):
            pass

    class FakePdfplumber:
        @staticmethod
        def open(path):
            return FakePdf()

    monkeypatch.setattr(pdf_parser, "_pdfplumber", lambda: FakePdfplumber)
    content, issues = pdf_parser.parse_pdf("not-a-real.pdf")
    page = content.pages[0]
    mismatched = [
        (block.text, block.char_start, block.char_end)
        for block in page.blocks
        if page.text[block.char_start : block.char_end] != block.text
    ]
    assert not mismatched, (
        "a line that text extraction could not locate must be reported, "
        f"not given a fabricated span: {mismatched}; issues={issues}"
    )
    # §14 row 1: the failure must be reported as an issue, and the unlocatable
    # line must not survive as a block with a fabricated span.
    codes = {issue.get("code") for issue in issues}
    assert "da01.line_not_located" in codes, issues
    assert all(block.text != "HELLO" for block in page.blocks)


# ---------------------------------------------------------------------------
# §14 row 4: decidability cache key includes statement and revision
# ---------------------------------------------------------------------------


def _prior_assessment():
    return {
        "assessment_id": "asmt:cache",
        "target_ref": "rule:1@r1",
        "verdict": "auto",
        "basis_refs": ["ev:1"],
        "dependency_refs": ["engine:expr@1"],
        "unknowns": [],
        "next_actions": [],
    }


def test_decidability_cache_is_invalidated_by_revision_and_statement(runtime, ctx):
    revision_change = call(
        "resolve_decidability_cache",
        {
            "prior": _prior_assessment(),
            "current_dependencies": ["engine:expr@1"],
            "requirement_ref": "rule:1@r2",
        },
        ctx,
        runtime,
    )
    assert revision_change.data.hit is False
    assert any("requirement" in reason for reason in revision_change.data.reasons)

    statement_change = call(
        "resolve_decidability_cache",
        {
            "prior": _prior_assessment(),
            "current_dependencies": ["engine:expr@1"],
            "prior_statement": "check amount",
            "statement": "check amount and currency",
        },
        ctx,
        runtime,
    )
    assert statement_change.data.hit is False
    assert any("statement" in reason for reason in statement_change.data.reasons)


# ---------------------------------------------------------------------------
# §14 row 5: persisted extraction and decidability results are readable
# ---------------------------------------------------------------------------


def test_extraction_and_decidability_results_are_readable(runtime, ctx, workspace):
    build_pdf(workspace / "amount.pdf", ["Amount: 5800 CNY"])
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "amount.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    page_text = load_document_content(runtime, document).pages[0].text
    start = page_text.index("5800")
    anchor = {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": start + 4,
        },
    }
    extracted = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "amount",
                    "path": "/amount",
                    "value_type": "money",
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 5800,
                    "value_type": "money",
                    "anchors": [anchor],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert extracted.status.value == "ok", extracted.issues
    stored = runtime.versions.current("extracted_record", extracted.data.record.asset.id)
    assert stored is not None
    assert stored[1]["fields"][0]["status"] == "extracted"

    assessment = call(
        "assess_automatic_decidability",
        {
            "requirement_ref": "rule:1@r1",
            "statement": "check amount",
            "proposal": {
                "verdict": "auto",
                # The extracted record is a real, persisted object, so it is
                # a resolvable basis (round 17 refuses fabricated refs).
                "basis_refs": [extracted.data.record.asset.id],
                "dependency_refs": [],
                "unknowns": [],
                "next_actions": [],
            },
        },
        ctx,
        runtime,
    )
    assert assessment.status.value == "ok", assessment.issues
    assert (
        runtime.versions.current(
            "decidability_assessment", assessment.data.assessment_id
        )
        is not None
    )
