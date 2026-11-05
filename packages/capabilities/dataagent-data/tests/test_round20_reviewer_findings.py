"""Round 20 regressions: the reviewer's metric-bypass and fragment-punctuation findings.

The reviewer's r20 report (`reviewer_r20_report.md`) confirmed via real MCP
two-phase calls + SQLite reads:

- N1 (P1): the source-consistency check for metric filters only ran when the
  optional ``available_fields`` schema was supplied, so omitting the schema
  let a fabricated constant (``'refunded'``) and a reversed operator
  (``!=``) through with ``ok / unresolved=[]`` and a persisted draft.
- N2 (P1): only filters that were present *and* parseable were compared with
  the source predicates. ``filters=[]`` (dropping the ``status = 'paid'``
  constraint wholesale) and ``status IN ('refunded')`` (a syntax the symbolic
  reader does not support) both passed as ``ok``: "cannot parse" was treated
  as "no conflict".
- N3 (P2): a legal quoted fragment gained a sentence-final period
  ("Claims must be approved.") and was rejected as using "different logical
  connectives", because the period broke the substring fast path.
- N4 (P2): PDF-extracted curly quotes reached the predicate reader
  un-normalized, so a legitimate ``status = 'paid,final'`` proposal was
  downgraded: the literal was truncated at the comma before quotes were
  folded.

The gates now: source-consistency runs with or without a bound schema; a
dropped or unparseable filter on a source-constrained field is an explicit
``unresolved`` entry; trailing sentence punctuation does not change a quoted
fragment; quotes are folded *before* tokenization and only digit-grouping
commas are removed.
"""

from __future__ import annotations

import pytest

from conftest import build_pdf, call, file_ref


def _page_text(runtime, document) -> str:
    return runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]


def _full_page_anchor(document, runtime) -> dict:
    text = _page_text(runtime, document)
    return {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": 0,
            "char_end": len(text),
        },
    }


def _parsed(runtime, ctx, workspace, name, lines):
    build_pdf(workspace / name, lines)
    return call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, name)}, ctx, runtime
    ).data.document


def _metric_call(
    runtime, ctx, workspace, name, anchor_text, filters, available_fields=None
):
    """``define_metric_formula`` proposal phase over a full-page PDF anchor.

    Only the second (proposal) phase is replayed here; the needs_input
    first phase and the persistence of the resulting draft are exercised
    by the reviewer's MCP probes and by
    ``test_round21_reviewer_findings.py``. ``available_fields=None`` omits
    the optional schema entirely (N1); a list binds it like a normal
    caller would.
    """

    document = _parsed(runtime, ctx, workspace, name, [anchor_text])
    payload = {
        "statement": anchor_text,
        "document_ref": document,
        "sources": [_full_page_anchor(document, runtime)],
        "proposal": {
            "measure_field": "amount",
            "aggregation": "sum",
            "grain": "department",
            "dimensions": ["department"],
            "unit": "CNY",
            "filters": filters,
        },
    }
    if available_fields is not None:
        payload["available_fields"] = available_fields
    return call("define_metric_formula", payload, ctx, runtime)


def _rule_call(runtime, ctx, workspace, name, anchor_text, condition_text):
    """``define_business_rules`` proposal phase (second phase only)."""

    document = _parsed(runtime, ctx, workspace, name, [anchor_text])
    return call(
        "define_business_rules",
        {
            "statement": "reviewed policy",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": condition_text,
                        "anchors": [_full_page_anchor(document, runtime)],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )


_PAID_SOURCE = "Sum amount CNY for status = 'paid' by department."


# ------------------------------------------------ N1: schema omission
@pytest.mark.parametrize(
    "filter_text",
    [
        # Fabricated constant: the source states 'paid'.
        "status = 'refunded'",
        # Reversed operator.
        "status != 'paid'",
    ],
)
def test_n1_divergent_filter_without_schema_is_unresolved(
    runtime, ctx, workspace, filter_text
):
    result = _metric_call(
        runtime, ctx, workspace, "n1.pdf", _PAID_SOURCE, [filter_text]
    )
    assert result.status.value == "partial", result.issues
    assert result.data.draft.unresolved, "omitting the schema must not disable the check"
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_n1_stated_filter_without_schema_stays_ok(runtime, ctx, workspace):
    result = _metric_call(
        runtime, ctx, workspace, "n1ok.pdf", _PAID_SOURCE, ["status = 'paid'"]
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


# ------------------------------------------------ N2: dropped / unparseable filters
def test_n2_dropped_source_constraint_is_unresolved(runtime, ctx, workspace):
    """``filters=[]`` deletes the predicate the metric is defined by."""

    result = _metric_call(
        runtime, ctx, workspace, "n2drop.pdf", _PAID_SOURCE, [], ["amount", "status", "department"]
    )
    assert result.status.value == "partial", result.issues
    assert any("status" in entry for entry in result.data.draft.unresolved)
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_n2_dropped_source_constraint_without_schema_is_unresolved(
    runtime, ctx, workspace
):
    """The dropped-constraint gate does not depend on the schema either (N1)."""

    result = _metric_call(runtime, ctx, workspace, "n2drop2.pdf", _PAID_SOURCE, [])
    assert result.status.value == "partial", result.issues
    assert any("status" in entry for entry in result.data.draft.unresolved)


def test_n2_unsupported_predicate_syntax_is_unresolved(runtime, ctx, workspace):
    """``status IN ('refunded')`` cannot be read as agreement with '='paid'."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "n2in.pdf",
        _PAID_SOURCE,
        ["status IN ('refunded')"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "partial", result.issues
    assert any("not a supported predicate" in entry for entry in result.data.draft.unresolved)
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_n2_stated_filter_with_schema_stays_ok(runtime, ctx, workspace):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "n2ok.pdf",
        _PAID_SOURCE,
        ["status = 'paid'"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_n2_worded_source_without_filters_stays_ok(runtime, ctx, workspace):
    """A source that states no symbolic predicate imposes no filter duty."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "n2worded.pdf",
        "Monthly net revenue is amount minus refunds in CNY.",
        [],
        ["amount", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


# ------------------------------------------------ N3: trailing sentence punctuation
def test_n3_fragment_with_trailing_period_stays_grounded(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "n3.pdf",
        "Policy: Claims must be approved and invoices may be filed.",
        "Claims must be approved.",
    )
    assert result.status.value == "ok", result.issues


def test_n3_fragment_without_period_stays_grounded(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "n3nopd.pdf",
        "Policy: Claims must be approved and invoices may be filed.",
        "Claims must be approved",
    )
    assert result.status.value == "ok", result.issues


def test_n3_guard_drop_with_trailing_period_still_rejected(runtime, ctx, workspace):
    """Punctuation must not reopen the F4 guard hole."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "n3guard.pdf",
        "If claims are approved then invoices may be filed.",
        "Invoices may be filed.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_n3_connective_swap_with_trailing_period_still_rejected(
    runtime, ctx, workspace
):
    """A full restatement may not swap "and" for "or", period or not."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "n3or.pdf",
        "Policy: Claims must be approved and invoices may be filed.",
        "Policy: Claims must be approved or invoices may be filed.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


# ------------------------------------------------ N4: quote folding and value commas
def test_n4_curly_quoted_comma_value_filter_stays_ok(runtime, ctx, workspace):
    """A PDF-extracted curly-quoted literal keeps its comma (N4).

    The PDF is built with straight quotes; Helvetica text extraction
    returns curly ones, which is exactly the reviewer's fixture.
    """

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "n4.pdf",
        "Sum amount CNY for status = 'paid,final' by department.",
        ["status = 'paid,final'"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_n4_curly_quoted_comma_value_divergence_is_unresolved(
    runtime, ctx, workspace
):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "n4div.pdf",
        "Sum amount CNY for status = 'paid,final' by department.",
        ["status = 'paid'"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "partial", result.issues
    assert result.data.draft.unresolved
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_n4_thousands_separator_value_matches_plain_number(
    runtime, ctx, workspace
):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "n4num.pdf",
        "Sum amount CNY for amount > 1,000 by department.",
        ["amount > 1000"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []
