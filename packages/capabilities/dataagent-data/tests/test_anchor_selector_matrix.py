"""Round 4 anchor-selector matrix (06 §14 item 1).

Every selector must resolve against real payloads. Fabricated values and
unavailable payloads are reported as ``missing`` with an explicit reason; an
unknown selector never passes through the old fail-open empty string.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from dataagent_contracts.core import SourceAnchor

from conftest import build_xlsx, call, file_ref

from dataagent_data.contracts.layer import DocumentContent, PageContent, TextBlock
from dataagent_data import helpers
from dataagent_data.anchors import (
    AnchorResolver,
    anchor_invalid_reason,
    anchor_value_mismatch,
    find_value_span,
    resolve_json_pointer,
)


def anchor(selector: dict, source_ref: str = "file:x", revision: str = "sha256:abc") -> SourceAnchor:
    return SourceAnchor(
        source_ref=source_ref,
        source_revision=revision,
        selector=selector,
    )


def pdf_content() -> DocumentContent:
    return DocumentContent(
        pages=[
            # Page 1 is absent on purpose: pages=2-3 must still resolve by number.
            PageContent(
                page=2,
                text="Amount: 35 % and 1.5kg, dated 2024-05-01",
                blocks=[
                    TextBlock(
                        page=2,
                        text="Amount: 35 %",
                        bbox=(0, 0, 100, 20),
                        char_start=0,
                        char_end=12,
                    )
                ],
            ),
            PageContent(page=3, text="second page"),
        ]
    )


def resolver() -> AnchorResolver:
    content = pdf_content()
    return AnchorResolver(
        content,
        units={"unit:1": "Total 3.5% due"},
        records=[
            {"id": "a", "v": 1},
            {"id": "b", "v": 2},
            {"id": "dup", "v": 1},
            {"id": "dup", "v": 2},
        ],
        tables={"Sheet": [[None, "h"], ["r", 1200]]},
        json_documents={
            "file:json": {"a/b": {"m~n": [1, 2]}},
        },
    )


def test_pdf_text_span_uses_page_number_not_list_index():
    content = pdf_content()
    good = anchor({"kind": "pdf_text_span", "page": 2, "char_start": 0, "char_end": 6})
    assert anchor_invalid_reason(content, good) == ""
    missing = anchor({"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": 1})
    assert "page 1 does not exist" in anchor_invalid_reason(content, missing)
    beyond = anchor({"kind": "pdf_text_span", "page": 3, "char_start": 0, "char_end": 999})
    assert "outside the page" in anchor_invalid_reason(content, beyond)


def test_pdf_bbox_page_subset_and_non_covering_box():
    content = pdf_content()
    good = anchor({"kind": "pdf_bbox", "page": 2, "bbox": [0, 0, 10, 10]})
    assert anchor_invalid_reason(content, good) == ""
    off = anchor({"kind": "pdf_bbox", "page": 2, "bbox": [500, 500, 510, 510]})
    assert "does not cover" in anchor_invalid_reason(content, off)
    missing = anchor({"kind": "pdf_bbox", "page": 1, "bbox": [0, 0, 10, 10]})
    assert "page 1 does not exist" in anchor_invalid_reason(content, missing)


def test_text_span_requires_persisted_unit_body():
    good = anchor({"kind": "text_span", "unit_ref": "unit:1", "char_start": 0, "char_end": 5})
    assert anchor_invalid_reason(resolver(), good) == ""
    missing = anchor({"kind": "text_span", "unit_ref": "unit:nope", "char_start": 0, "char_end": 5})
    assert "not persisted" in anchor_invalid_reason(resolver(), missing)
    beyond = anchor({"kind": "text_span", "unit_ref": "unit:1", "char_start": 0, "char_end": 999})
    assert "outside the unit text" in anchor_invalid_reason(resolver(), beyond)


def test_json_pointer_rfc6901_escapes_and_array_bounds():
    good = anchor(
        {"kind": "json_pointer", "pointer": "/a~1b/m~0n/1"}, source_ref="file:json"
    )
    assert anchor_value_mismatch(resolver(), good, 2) == ""
    bad = anchor(
        {"kind": "json_pointer", "pointer": "/a~1b/m~0n/9"}, source_ref="file:json"
    )
    assert "out of range" in anchor_invalid_reason(resolver(), bad)
    unknown = anchor({"kind": "json_pointer", "pointer": "/nope"}, source_ref="file:json")
    assert "does not exist" in anchor_invalid_reason(resolver(), unknown)
    unavailable = anchor({"kind": "json_pointer", "pointer": "/a"}, source_ref="file:missing")
    assert "not available" in anchor_invalid_reason(resolver(), unavailable)
    assert resolve_json_pointer({"x": 1}, "/x") == 1


def test_excel_cell_resolves_sheet_and_range():
    good = anchor({"kind": "excel_cell", "sheet": "Sheet", "range": "B2"})
    assert anchor_value_mismatch(resolver(), good, 1200) == ""
    no_sheet = anchor({"kind": "excel_cell", "sheet": "Missing", "range": "A1"})
    assert "not available" in anchor_invalid_reason(resolver(), no_sheet) or "does not exist" in anchor_invalid_reason(resolver(), no_sheet)
    empty = anchor({"kind": "excel_cell", "sheet": "Sheet", "range": "D9"})
    assert "outside" in anchor_invalid_reason(resolver(), empty) or "empty" in anchor_invalid_reason(resolver(), empty)


def test_record_key_matches_one_row():
    good = anchor(
        {"kind": "record_key", "keys": {"id": "b"}, "field": "id"},
        source_ref="file:json",
    )
    assert anchor_value_mismatch(resolver(), good, "b") == ""
    missing = anchor(
        {"kind": "record_key", "keys": {"id": "z"}, "field": "id"},
        source_ref="file:json",
    )
    assert "no record" in anchor_invalid_reason(resolver(), missing)
    duplicate = anchor(
        {"kind": "record_key", "keys": {"id": "dup"}, "field": "id"},
        source_ref="file:json",
    )
    assert "multiple records" in anchor_invalid_reason(resolver(), duplicate)


def test_record_key_anchors_one_field_not_the_whole_row():
    selector = {"kind": "record_key", "keys": {"id": "b"}, "field": "v"}
    good = anchor(selector, source_ref="file:json")
    assert anchor_value_mismatch(resolver(), good, 2) == ""
    # Other fields of the matched row are not evidence for this anchor.
    assert anchor_value_mismatch(resolver(), good, "b") != ""


def test_unknown_selector_is_not_fail_open():
    fake = SourceAnchor.model_construct(
        source_ref="file:x",
        source_revision="sha256:abc",
        selector=SimpleNamespace(kind="mystery_selector"),
    )
    assert "unsupported anchor kind" in anchor_invalid_reason(resolver(), fake)
    assert anchor_value_mismatch(resolver(), fake, "anything") != ""


@pytest.mark.parametrize(
    ("surface", "value"),
    [
        ("3.5%", "35%"),
        ("1.5kg", "15kg"),
        ("A-1", "A1"),
    ],
)
def test_string_normalization_does_not_manufacture_matches(surface, value):
    content = DocumentContent(pages=[PageContent(page=1, text=surface)])
    good = anchor({"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": len(surface)})
    assert anchor_value_mismatch(content, good, value) != ""


@pytest.mark.parametrize(
    ("surface", "value"),
    [
        ("¥5,800.00", 5800),
        ("35 %", 35),
        ("1.5", 1.5),
    ],
)
def test_legitimate_surface_forms_still_match(surface, value):
    content = DocumentContent(pages=[PageContent(page=1, text=surface)])
    good = anchor({"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": len(surface)})
    assert anchor_value_mismatch(content, good, value) == ""


def test_value_none_is_never_supported():
    content = DocumentContent(pages=[PageContent(page=1, text="anything")])
    good = anchor({"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": 8})
    assert anchor_value_mismatch(content, good, None) != ""


def test_numeric_relocation_ignores_date_fragments():
    content = DocumentContent(pages=[PageContent(page=1, text="2024-05-01 amount 999")])
    assert find_value_span(content, -5) is None
    assert find_value_span(content, 999) is not None


@pytest.mark.parametrize(
    ("selector", "fabricated"),
    [
        ({"kind": "pdf_text_span", "page": 2, "char_start": 0, "char_end": 6}, 777),
        ({"kind": "text_span", "unit_ref": "unit:1", "char_start": 0, "char_end": 5}, 777),
        ({"kind": "json_pointer", "pointer": "/a~1b/m~0n/1"}, 777),
        ({"kind": "excel_cell", "sheet": "Sheet", "range": "B2"}, 777),
        ({"kind": "record_key", "keys": {"id": "b"}, "field": "v"}, 777),
    ],
)
def test_fabricated_value_is_rejected_by_every_selector(selector, fabricated):
    target = anchor(selector, source_ref="file:json") if selector["kind"] == "json_pointer" else anchor(selector)
    assert anchor_value_mismatch(resolver(), target, fabricated) != ""


# -- revision-scoped parse cache (Round 4.3) --------------------------------


def _excel_anchor(revision: str, source_ref: str = "file:report") -> SourceAnchor:
    return SourceAnchor(
        source_ref=source_ref,
        source_revision=revision,
        selector={"kind": "excel_cell", "sheet": "Sheet", "range": "B2"},
    )


def _pointer_anchor(
    revision: str, pointer: str, source_ref: str = "file:report"
) -> SourceAnchor:
    return SourceAnchor(
        source_ref=source_ref,
        source_revision=revision,
        selector={"kind": "json_pointer", "pointer": pointer},
    )


def _register(runtime, workspace, name: str, source_id: str, **kwargs):
    ref = file_ref(workspace, name, id=source_id, **kwargs)
    helpers.register_file_ref(runtime, ref)
    return ref


def test_excel_parse_cache_is_scoped_by_revision(runtime, workspace):
    """rev2 first used to poison the cache so rev1's empty B2 resolved as 200."""

    build_xlsx(workspace / "report-rev1.xlsx", {"Sheet": [["h"], ["r", 100]]})
    build_xlsx(workspace / "report-rev2.xlsx", {"Sheet": [["h"], ["r", 200]]})
    rev1 = _register(runtime, workspace, "report-rev1.xlsx", "file:report")
    rev2 = _register(runtime, workspace, "report-rev2.xlsx", "file:report")

    resolver = AnchorResolver(runtime=runtime)
    assert resolver.resolve(_excel_anchor(rev2.revision)).text == "200"
    assert resolver.resolve(_excel_anchor(rev1.revision)).text == "100"

    resolver = AnchorResolver(runtime=runtime)
    assert resolver.resolve(_excel_anchor(rev1.revision)).text == "100"
    assert resolver.resolve(_excel_anchor(rev2.revision)).text == "200"


def test_json_parse_cache_is_scoped_by_revision(runtime, workspace):
    (workspace / "report-rev1.json").write_text(
        json.dumps({"clause": {"title": "x"}}), encoding="utf-8"
    )
    (workspace / "report-rev2.json").write_text(
        json.dumps({"clause": {"approver": "alice"}}), encoding="utf-8"
    )
    (workspace / "report-rev3.json").write_text(
        json.dumps({"clause": {"approver": "bob"}}), encoding="utf-8"
    )
    rev1 = _register(runtime, workspace, "report-rev1.json", "file:report")
    rev2 = _register(runtime, workspace, "report-rev2.json", "file:report")
    rev3 = _register(runtime, workspace, "report-rev3.json", "file:report")

    resolver = AnchorResolver(runtime=runtime)
    assert resolver.resolve(_pointer_anchor(rev2.revision, "/clause/approver")).text == "alice"
    missing = resolver.resolve(_pointer_anchor(rev1.revision, "/clause/approver"))
    assert missing.text is None and "does not exist" in missing.reason

    resolver = AnchorResolver(runtime=runtime)
    assert resolver.resolve(_pointer_anchor(rev2.revision, "/clause/approver")).text == "alice"
    assert resolver.resolve(_pointer_anchor(rev3.revision, "/clause/approver")).text == "bob"
    assert resolver.resolve(_pointer_anchor(rev2.revision, "/clause/approver")).text == "alice"


def test_same_revision_reuses_the_parsed_payload(runtime, workspace):
    build_xlsx(workspace / "report.xlsx", {"Sheet": [["h"], ["r", 100]]})
    (workspace / "report.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    xlsx = _register(runtime, workspace, "report.xlsx", "file:report")
    document = _register(runtime, workspace, "report.json", "file:document")

    resolver = AnchorResolver(runtime=runtime)
    first = resolver._workbook("file:report", xlsx.revision)
    assert first is not None
    assert resolver._workbook("file:report", xlsx.revision) is first
    first_json = resolver._json_document("file:document", document.revision)
    assert first_json == {"a": 1}
    assert resolver._json_document("file:document", document.revision) is first_json


def _metric_sources(anchors, ctx, runtime):
    return call(
        "define_metric_formula",
        {
            "statement": "monthly net revenue",
            "available_fields": ["amount"],
            "sources": anchors,
            "proposal": {
                "measure_field": "amount",
                "aggregation": "sum",
                "grain": "month",
            },
        },
        ctx,
        runtime,
    )


def test_metric_sources_reject_cross_revision_excel_reuse(runtime, ctx, workspace):
    build_xlsx(workspace / "report-rev1.xlsx", {"Sheet": [["h"], ["r"]]})
    build_xlsx(workspace / "report-rev2.xlsx", {"Sheet": [["h"], ["r", 200]]})
    rev1 = _register(runtime, workspace, "report-rev1.xlsx", "file:report")
    rev2 = _register(runtime, workspace, "report-rev2.xlsx", "file:report")
    anchors = {
        "r1": _excel_anchor(rev1.revision).model_dump(mode="json"),
        "r2": _excel_anchor(rev2.revision).model_dump(mode="json"),
    }

    for order in (["r2", "r1"], ["r1", "r2"]):
        result = _metric_sources([anchors[key] for key in order], ctx, runtime)
        assert result.data is not None, result.issues
        assert [source.source_revision for source in result.data.draft.sources] == [
            rev2.revision
        ]
        assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)


def test_metric_sources_reject_cross_revision_json_reuse(runtime, ctx, workspace):
    (workspace / "report-rev1.json").write_text(
        json.dumps({"clause": {"title": "x"}}), encoding="utf-8"
    )
    (workspace / "report-rev2.json").write_text(
        json.dumps({"clause": {"approver": "alice"}}), encoding="utf-8"
    )
    rev1 = _register(runtime, workspace, "report-rev1.json", "file:report")
    rev2 = _register(runtime, workspace, "report-rev2.json", "file:report")
    anchors = {
        "r1": _pointer_anchor(rev1.revision, "/clause/approver").model_dump(mode="json"),
        "r2": _pointer_anchor(rev2.revision, "/clause/approver").model_dump(mode="json"),
    }

    for order in (["r2", "r1"], ["r1", "r2"]):
        result = _metric_sources([anchors[key] for key in order], ctx, runtime)
        assert result.data is not None, result.issues
        assert [source.source_revision for source in result.data.draft.sources] == [
            rev2.revision
        ]
        assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)
