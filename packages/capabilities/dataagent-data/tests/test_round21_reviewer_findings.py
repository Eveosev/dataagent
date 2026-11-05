"""Round 21 regressions: the reviewer's metric tokenizer/gate findings.

The reviewer's r21 report (`reviewer_r21_report.md`) confirmed via real MCP
two-phase calls + SQLite reads that the r20 fixes introduced or left three
classes of silent fabrication in ``define_metric_formula``:

- F1 (P1): ``_normalize_filter_value`` stripped quotes *and then* removed
  digit-commas from any string, so a quoted ``'12,34'`` / ``'v1,2'`` source
  silently agreed with a proposal filtering on ``'1234'`` / ``'v12'`` --
  ``ok``, no ``unresolved``, draft persisted. A quoted literal is a string:
  its content is verbatim, and only unquoted numeric literals in valid
  thousands syntax get their separators removed.
- F2 (P1): the r20 numeric alternative had no token boundary, so the source
  ``status = 1000USD`` stated only ``1000``: the same-value filter was
  wrongly downgraded (stated='1000') while the *truncated* ``status =
  '1000'`` passed as ``ok`` and persisted. The tokenizer must consume the
  complete literal.
- F3 (P1): ``_dropped_source_constraints`` only checked *field* coverage, so
  a source stating ``amount >= 1000 and amount <= 5000`` was satisfied by a
  proposal carrying only ``amount >= 1000`` -- the necessary upper bound was
  silently deleted. Coverage is per stated predicate, not per field.
- F4 (P2, same tokenizer): the numeric alternative had no sign, so
  ``amount > -1,000`` stated ``-1`` and the legitimate ``amount > -1000``
  was rejected as a divergence.

The tests below replay only the second (proposal) phase of the two-phase
atom against the real runtime; the two-phase + SQLite persistence behaviour
itself is asserted in ``test_f1_fabricated_string_persists_with_unresolved``
via the versioned store.
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
    """``define_metric_formula`` with a proposal over a full-page PDF anchor.

    ``available_fields=None`` omits the optional schema, as the reviewer's
    probe did; a list binds it. Only the proposal (second) phase is replayed
    here.
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


_RANGE_SOURCE = "Sum amount CNY for amount >= 1000 and amount <= 5000 by department."


# ------------------------------------------------ F1: quoted commas are content
@pytest.mark.parametrize(
    ("source", "filter_text"),
    [
        # The reviewer's exact fixtures: the comma is string content, and the
        # digits-only proposals fabricate agreement with it.
        ("Sum amount CNY for status = '12,34' by department.", "status = '1234'"),
        ("Sum amount CNY for status = 'v1,2' by department.", "status = 'v12'"),
    ],
)
def test_f1_quoted_comma_collapsed_to_digits_is_unresolved(
    runtime, ctx, workspace, source, filter_text
):
    result = _metric_call(runtime, ctx, workspace, "f1.pdf", source, [filter_text])
    assert result.status.value == "partial", result.issues
    assert result.data.draft.unresolved, "quoted content must not be re-typed"
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_f1_same_quoted_comma_value_stays_ok(runtime, ctx, workspace):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f1ok.pdf",
        "Sum amount CNY for status = '12,34' by department.",
        ["status = '12,34'"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f1_quoted_numeric_thousands_is_not_a_number(runtime, ctx, workspace):
    """A quoted '1,000' is a string; it may not silently equal 1000."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f1q.pdf",
        "Sum amount CNY for amount > '1,000' by department.",
        ["amount > 1000"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "partial", result.issues
    assert result.data.draft.unresolved


def test_f1_unquoted_thousands_still_matches_plain_number(runtime, ctx, workspace):
    """The N4 control must survive F1: unquoted 1,000 is a numeric literal."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f1n.pdf",
        "Sum amount CNY for amount > 1,000 by department.",
        ["amount > 1000"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f1_fabricated_string_persists_with_unresolved(
    runtime, ctx, workspace
):
    """The degraded draft is persisted *with* its unresolved entries (06 §5).

    A partial is written as a version (not refused), but the fabricated
    agreement must never be stored as a clean ``ok`` fact.
    """

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f1db.pdf",
        "Sum amount CNY for status = '12,34' by department.",
        ["status = '1234'"],
    )
    assert result.status.value == "partial", result.issues
    draft = result.data.draft
    stored = runtime.versions.get("semantic_draft", draft.draft_id, draft.revision)
    assert stored is not None, "the degraded draft must be persisted"
    assert stored["unresolved"] == draft.unresolved
    assert stored["unresolved"], "the persisted draft carries the divergence"


# ------------------------------------------------ F2: complete literal boundary
def test_f2_truncated_bare_literal_is_unresolved(runtime, ctx, workspace):
    """Source ``status = 1000USD``; proposal ``status = '1000'`` must not be ok."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2.pdf",
        "Sum amount CNY for status = 1000USD by department.",
        ["status = '1000'"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "partial", result.issues
    assert result.data.draft.unresolved
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_f2_full_bare_literal_stays_ok(runtime, ctx, workspace):
    """The same-value control the r20 tokenizer wrongly downgraded."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2ok.pdf",
        "Sum amount CNY for status = 1000USD by department.",
        ["status = '1000USD'"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f2_quoted_full_literal_stays_ok(runtime, ctx, workspace):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2q.pdf",
        "Sum amount CNY for status = '1000USD' by department.",
        ["status = '1000USD'"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f2_sentence_final_period_is_not_part_of_the_number(
    runtime, ctx, workspace
):
    """The reviewer's control: ``amount > 1,000.`` at a sentence end."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2p.pdf",
        "Sum amount CNY by department for amount > 1,000.",
        ["amount > 1000"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f2_decimal_literal_stays_ok(runtime, ctx, workspace):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2d.pdf",
        "Sum amount CNY for amount > 1,000.50 by department.",
        ["amount > 1000.50"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


# ------------------------------------------------ F3: per-predicate coverage
def test_f3_second_constraint_on_same_field_is_dropped(runtime, ctx, workspace):
    result = _metric_call(
        runtime, ctx, workspace, "f3.pdf", _RANGE_SOURCE, ["amount >= 1000"]
    )
    assert result.status.value == "partial", result.issues
    assert any("amount <= '5000'" in entry for entry in result.data.draft.unresolved), (
        result.data.draft.unresolved
    )
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_f3_both_constraints_stay_ok(runtime, ctx, workspace):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f3ok.pdf",
        _RANGE_SOURCE,
        ["amount >= 1000", "amount <= 5000"],
        ["amount", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f3_wrong_value_and_dropped_bound_both_reported(runtime, ctx, workspace):
    """A diverging value does not mask the missing necessary predicate."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f3w.pdf",
        _RANGE_SOURCE,
        ["amount >= 2000"],
        ["amount", "department"],
    )
    assert result.status.value == "partial", result.issues
    unresolved = result.data.draft.unresolved
    assert any("diverges" in entry for entry in unresolved)
    assert any("amount <= '5000'" in entry for entry in unresolved)


def test_f3_unparseable_filter_does_not_satisfy_the_bound(runtime, ctx, workspace):
    """A filter the reader cannot parse carries no predicate (N2 + F3)."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f3in.pdf",
        _RANGE_SOURCE,
        ["amount BETWEEN 1000 AND 5000"],
        ["amount", "department"],
    )
    assert result.status.value == "partial", result.issues
    unresolved = result.data.draft.unresolved
    assert any("not a supported predicate" in entry for entry in unresolved)
    assert any("drops" in entry for entry in unresolved)


# ------------------------------------------------ F4: signed numeric literal
def test_f4_negative_thousands_matches_plain_number(runtime, ctx, workspace):
    """The reviewer's P2 control from the same tokenizer fix."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f4.pdf",
        "Sum amount CNY for amount > -1,000 by department.",
        ["amount > -1000"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f4_negative_plain_matches_thousands(runtime, ctx, workspace):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f4r.pdf",
        "Sum amount CNY for amount > -1000 by department.",
        ["amount > -1,000"],
        ["amount", "status", "department"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []
