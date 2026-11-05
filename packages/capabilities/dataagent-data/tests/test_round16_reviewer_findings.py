"""Round 16 regressions: the reviewer's residual semantic-support bypasses.

The reviewer's r16 report (`reviewer_r16_report.md`, P1 R1/R2) confirmed via
real MCP that four rewrites of an anchored clause still returned
``ok / issues=[] / unresolved=[]`` and were persisted:

- R1 fragment exemption: dropping one peripheral content token (the
  ``Policy:`` label or a tail qualifier like ``promptly``) turned a full
  restatement into a "fragment" and skipped the modality sequence, so
  "Claims may be approved and invoices must be filed" was saved against
  "Policy: Claims must be approved and invoices may be filed".
- R2 comparison subject swap: two subjects sharing a threshold keep the
  global bound set identical while each direction is reversed
  ("claims above 5000 and invoices below 5000" -> the reverse).
- R2 conditional direction: "If claims are approved then invoices may be
  filed" restated as "Claims are approved if invoices may be filed".
- R2 connective scope: "A and B or C" restated as "A or B and C" keeps both
  connective counts while changing their scope.

``anchor_supports_text`` now binds each deontic modal to the content it
scopes (a fragment may quote a clause with its own force but may not
borrow another clause's), keeps the connectives as an *ordered* sequence,
compares the conditional antecedent, and requires each comparison to stay
attached to the subject the anchor attaches it to.
"""

from __future__ import annotations

import pytest

from conftest import build_pdf, call, file_ref, write_file


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


def _rule_call(runtime, ctx, workspace, name, anchor_text, condition_text):
    build_pdf(workspace / name, [anchor_text])
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, name)}, ctx, runtime
    ).data.document
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


def _rejected(result):
    """A rewritten condition must not be grounded nor persisted."""

    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes
    if result.data is not None and result.data.draft is not None:
        assert not result.data.draft.definition.conditions


class _FakeOcrEngine:
    """Minimal engine stand-in; the R6 probes never reach recognition."""

    engine_ref = "fake"
    engine_version = "1.0"

    def recognize(self, image_bytes, *, lang=None):  # pragma: no cover
        return []


# ------------------------------------------------ R1: fragment + modal swap
@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        # The exact reviewer probes: only the "Policy:" label or the tail
        # qualifier separates the quote from a full restatement.
        (
            "Policy: Claims must be approved and invoices may be filed.",
            "Claims may be approved and invoices must be filed.",
        ),
        (
            "Claims must be approved and invoices may be filed promptly.",
            "Claims may be approved and invoices must be filed.",
        ),
        # Borrowing: the force is kept but moved onto another clause.
        (
            "Claims must be approved and invoices may be filed.",
            "Invoices must be filed and claims may be approved.",
        ),
    ],
)
def test_r1_fragment_modal_swap_is_rejected(
    runtime, ctx, workspace, anchor_text, condition_text
):
    _rejected(
        _rule_call(
            runtime, ctx, workspace, "r1swap.pdf", anchor_text, condition_text
        )
    )


def test_r1_precondition_fragment_swap_is_unknown(runtime, ctx, workspace):
    """The same rewrite as a precondition must not satisfy on facts."""

    build_pdf(
        workspace / "r1pre.pdf",
        ["Policy: Claims must be approved and invoices may be filed."],
    )
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "r1pre.pdf")}, ctx, runtime
    ).data.document
    result = call(
        "define_rule_preconditions",
        {
            "rule_ref": "rule:policy",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "Claims may be approved and invoices must be filed.",
                        "anchors": [_full_page_anchor(document, runtime)],
                    }
                ],
                "combination": "all(c1)",
            },
            "facts": {"c1": True},
        },
        ctx,
        runtime,
    )
    assert result.status.value == "partial", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes
    assert result.data.evaluation.verdict == "unknown"
    assert result.data.draft.unknowns == ["c1"]


# ------------------------------------------------ R2: structural rewrites
@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        # Comparison subject swap: the global bound set is identical.
        (
            "Claims above 5000 CNY and invoices below 5000 CNY require approval.",
            "Claims below 5000 CNY and invoices above 5000 CNY require approval.",
        ),
        # Conditional direction reversal, both phrasings.
        (
            "If claims are approved then invoices may be filed.",
            "Claims are approved if invoices may be filed.",
        ),
        (
            "If claims are approved then invoices may be filed.",
            "If invoices may be filed then claims are approved.",
        ),
        # Connective scope swap: counts agree, the binding does not.
        (
            "Claims and invoices or receipts require approval.",
            "Claims or invoices and receipts require approval.",
        ),
    ],
)
def test_r2_structural_rewrite_is_rejected(
    runtime, ctx, workspace, anchor_text, condition_text
):
    _rejected(
        _rule_call(
            runtime, ctx, workspace, "r2swap.pdf", anchor_text, condition_text
        )
    )


# ------------------------------------------------ carve-outs that must survive
def test_r1_fragment_keeps_its_own_modal(runtime, ctx, workspace):
    """A fragment quotes one clause with the force the anchor gave it."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "r1frag.pdf",
        "Policy: Claims must be approved and invoices may be filed.",
        "Invoices may be filed",
    )
    assert result.status.value == "ok", result.issues


def test_r2_conditional_paraphrase_keeps_direction(runtime, ctx, workspace):
    """Dropping "then" for a comma does not reverse the implication."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "r2cond.pdf",
        "If claims are approved then invoices may be filed.",
        "If claims are approved, invoices may be filed.",
    )
    assert result.status.value == "ok", result.issues


def test_r2_comparison_fragment_keeps_subject_binding(runtime, ctx, workspace):
    """A fragment may quote one subject's bound with its direction."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "r2frag.pdf",
        "Claims above 5000 CNY and invoices below 5000 CNY require approval.",
        "Claims above 5000 CNY",
    )
    assert result.status.value == "ok", result.issues


def test_r2_verbatim_two_subject_bounds_still_grounded(runtime, ctx, workspace):
    """A verbatim quote keeps both bounds on their own subjects."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "r2verb.pdf",
        "Claims above 5000 CNY and invoices below 5000 CNY require approval.",
        "Claims above 5000 CNY and invoices below 5000 CNY require approval.",
    )
    assert result.status.value == "ok", result.issues


# ------------------------------------------------ R6: internal failures are
# not the caller's fault (reviewer r16 §3 R6): only known format/file errors
# map to invalid_input; anything else must surface as execution_unknown.
def test_r6_internal_workbook_failure_is_execution_unknown(
    runtime, ctx, workspace, monkeypatch
):
    from dataagent_data.adapters import parsers

    def _bug(*args, **kwargs):
        raise RuntimeError("internal parser bug")

    monkeypatch.setattr(parsers.excel, "load_workbook", _bug)
    write_file(workspace, "fine.xlsx", b"whatever")
    result = call(
        "parse_regular_excel", {"file_ref": file_ref(workspace, "fine.xlsx")}, ctx, runtime
    )
    assert result.status.value == "failed", result.issues
    assert result.issues[0].code == "execution_unknown", result.issues


def test_r6_corrupt_workbook_is_still_invalid_input(runtime, ctx, workspace):
    write_file(workspace, "broken.xlsx", b"this is not a zip")
    result = call(
        "parse_regular_excel", {"file_ref": file_ref(workspace, "broken.xlsx")}, ctx, runtime
    )
    assert result.status.value == "failed", result.issues
    assert result.issues[0].code == "invalid_input", result.issues


def test_r6_internal_ocr_failure_is_execution_unknown(
    runtime, ctx, workspace, monkeypatch
):
    import pdfplumber

    class _Bug:
        def __enter__(self):
            raise RuntimeError("internal renderer bug")

        def __exit__(self, *args):
            return False

    runtime.ocr_engine = _FakeOcrEngine()
    monkeypatch.setattr(pdfplumber, "open", lambda *a, **k: _Bug())
    write_file(workspace, "scan.pdf", b"%PDF-1.4 whatever")
    result = call(
        "ocr_pdf", {"file_ref": file_ref(workspace, "scan.pdf")}, ctx, runtime
    )
    assert result.status.value == "failed", result.issues
    assert result.issues[0].code == "execution_unknown", result.issues


def test_r6_corrupt_pdf_ocr_is_still_invalid_input(runtime, ctx, workspace):
    runtime.ocr_engine = _FakeOcrEngine()
    write_file(workspace, "broken.pdf", b"this is not a pdf at all")
    result = call(
        "ocr_pdf", {"file_ref": file_ref(workspace, "broken.pdf")}, ctx, runtime
    )
    assert result.status.value == "failed", result.issues
    assert result.issues[0].code == "invalid_input", result.issues
