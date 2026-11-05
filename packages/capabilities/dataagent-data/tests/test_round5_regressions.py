"""Round 5 regression tests for the P0/P1 defects reported in r4-review/r5.

D1/D2: a rule condition must keep both the threshold and the comparison
direction stated by its anchor; a substring must not bypass those checks.
D3: a sparse or "N/A"-bearing first data row must be kept as data instead of
being folded into a multi-row header.
D4: two concurrent ``register_extraction_schema_version`` calls carrying the
same ``expected_revision`` must produce exactly one ``version_conflict``.
"""

from __future__ import annotations

import threading

from conftest import build_pdf, build_xlsx, call, file_ref

from dataagent_data.preparation.structure import recover_header_block

CLAUSE = "Claims above 5000 CNY require department head approval."


def _rule_document(runtime, ctx, workspace):
    build_pdf(workspace / "policy.pdf", ["1. Scope", CLAUSE])
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    page_text = runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]
    start = page_text.index("Claims above")
    anchor = {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": start + len(CLAUSE),
        },
    }
    return document, anchor


def _define_rule(runtime, ctx, document, anchor, condition_text):
    return call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": condition_text,
                        "anchors": [anchor],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )


def test_rule_condition_rejects_reversed_comparison_direction(runtime, ctx, workspace):
    document, anchor = _rule_document(runtime, ctx, workspace)
    for index, text in enumerate(
        [
            "claims below 5000 CNY",
            "claims less than 5000 CNY",
        ]
    ):
        result = _define_rule(runtime, ctx, document, anchor, text)
        assert result.status.value == "needs_input", text
        assert result.data is None, text
        codes = {issue.code for issue in result.issues}
        assert "da02.anchor_value_mismatch" in codes, (text, codes)
        assert "da03.unanchored_condition" in codes, (text, codes)

    positive = _define_rule(runtime, ctx, document, anchor, "claims above 5000 CNY")
    assert positive.status.value == "ok", positive.issues
    assert len(positive.data.draft.definition.conditions) == 1


def test_rule_condition_that_drops_the_threshold_is_rejected(runtime, ctx, workspace):
    document, anchor = _rule_document(runtime, ctx, workspace)
    # Both are substrings of the clause but drop the 5000 threshold and the
    # comparison; the substring fast path must not accept them.
    for text in ("department head approval", "require department head approval."):
        result = _define_rule(runtime, ctx, document, anchor, text)
        assert result.status.value == "needs_input", text
        assert result.data is None, text
        codes = {issue.code for issue in result.issues}
        assert "da02.anchor_value_mismatch" in codes, (text, codes)

    # The full clause is still accepted.
    result = _define_rule(runtime, ctx, document, anchor, CLAUSE)
    assert result.status.value == "ok", result.issues


def test_rule_condition_cannot_borrow_another_clauses_comparison(
    runtime, ctx, workspace
):
    build_pdf(
        workspace / "two_clauses.pdf",
        [
            "Claims above 5000 CNY require approval.",
            "Claims below 100 CNY are exempt.",
        ],
    )
    parsed = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "two_clauses.pdf")},
        ctx,
        runtime,
    )
    document = parsed.data.document
    page_text = runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]
    start = page_text.index("Claims above")
    end = page_text.index("exempt.") + len("exempt.")
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

    def define(text):
        return _define_rule(runtime, ctx, document, anchor, text)

    # "lower" occurs in the anchor, but it bounds 100 -- not 5000.
    reversed_pair = define("claims below 5000 CNY")
    assert reversed_pair.status.value == "needs_input"
    codes = {issue.code for issue in reversed_pair.issues}
    assert "da02.anchor_value_mismatch" in codes, codes

    assert define("claims below 100 CNY").status.value == "ok"
    assert define("claims above 5000 CNY").status.value == "ok"


def test_negated_comparator_phrases_are_not_double_counted():
    from decimal import Decimal

    from dataagent_data.anchors import _comparison_bounds

    assert _comparison_bounds("no less than 5000") == {("upper", Decimal(5000))}
    assert _comparison_bounds("not less than 5000") == {("upper", Decimal(5000))}
    assert _comparison_bounds("no more than 5000") == {("lower", Decimal(5000))}
    assert _comparison_bounds("5000 and below") == {("lower", Decimal(5000))}
    # "below" belongs to 100, not to 5000.
    assert _comparison_bounds("above 5000 and below 100") == {
        ("upper", Decimal(5000)),
        ("lower", Decimal(100)),
    }


def test_sparse_first_data_row_is_not_folded_into_the_header():
    recovered = recover_header_block(
        [["name", "q1", "q2"], ["Alice", None, None], ["Bob", 1, 2]]
    )
    assert recovered.header_rows == 1
    assert recovered.columns == ["name", "q1", "q2"]
    assert recovered.rows == [["Alice", None, None], ["Bob", 1, 2]]
    assert recovered.ambiguities


def test_missing_marker_first_data_row_is_not_folded_into_the_header():
    recovered = recover_header_block(
        [["name", "amount"], ["Alice", "N/A"], ["Bob", 5]]
    )
    assert recovered.header_rows == 1
    assert recovered.columns == ["name", "amount"]
    assert recovered.rows == [["Alice", "N/A"], ["Bob", 5]]
    assert recovered.ambiguities


def test_genuine_two_row_header_is_still_detected():
    recovered = recover_header_block(
        [["Amount", "Amount"], ["Budget", "Actual"], [10, 9], [20, 18]]
    )
    assert recovered.header_rows == 2
    assert recovered.columns == ["Amount / Budget", "Amount / Actual"]
    assert recovered.rows == [[10, 9], [20, 18]]
    assert recovered.ambiguities == []


def test_recover_headers_atom_keeps_the_sparse_row_and_reports_ambiguity(
    runtime, ctx, workspace
):
    build_xlsx(
        workspace / "sparse.xlsx",
        {"S": [["name", "q1", "q2"], ["Alice", None, None], ["Bob", 1, 2]]},
    )
    regions = call(
        "detect_workbook_regions",
        {"file_ref": file_ref(workspace, "sparse.xlsx")},
        ctx,
        runtime,
    )
    result = call(
        "recover_headers",
        {"region": regions.data.regions[0]},
        ctx,
        runtime,
    )
    assert result.data.header_rows == 1
    assert result.data.columns == ["name", "q1", "q2"]
    assert result.status.value == "partial"
    assert any(issue.code == "da02.ambiguous_header" for issue in result.issues)
    table = runtime.content.get_json(result.data.table.data_ref)
    assert table["rows"] == [["Alice", None, None], ["Bob", 1, 2]]


def _schema_field(field_id: str) -> dict:
    return {
        "field_id": field_id,
        "name": field_id,
        "path": field_id,
        "value_type": "money",
    }


def test_expected_revision_is_checked_atomically(runtime, ctx):
    call(
        "register_extraction_schema_version",
        {"schema_id": "xschema:concurrent", "fields": [_schema_field("amount")]},
        ctx,
        runtime,
    )
    assert runtime.versions.current("extraction_schema", "xschema:concurrent")[0] == "r1"

    barrier = threading.Barrier(2, timeout=5)
    original_current = runtime.versions.current

    def synchronized_current(kind, object_id):
        barrier.wait()
        return original_current(kind, object_id)

    results: list[tuple[str, str | None]] = []

    def worker(index: int) -> None:
        try:
            result = call(
                "register_extraction_schema_version",
                {
                    "schema_id": "xschema:concurrent",
                    "fields": [_schema_field(f"amount{index}")],
                    "change_note": f"writer {index}",
                    "expected_revision": "r1",
                },
                ctx,
                runtime,
            )
            results.append(
                (result.status.value, result.data.revision if result.data else None)
            )
        except Exception as exc:  # noqa: BLE001 - surfaced by the assertion below
            results.append(("exception", type(exc).__name__))

    runtime.versions.current = synchronized_current  # type: ignore[method-assign]
    try:
        threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        runtime.versions.current = original_current  # type: ignore[method-assign]

    assert sorted(status for status, _ in results) == ["failed", "ok"], results
    assert runtime.versions.revisions("extraction_schema", "xschema:concurrent") == [
        "r1",
        "r2",
    ]
    assert runtime.versions.current("extraction_schema", "xschema:concurrent")[0] == "r2"
