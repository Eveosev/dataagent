"""Round 15 regressions: the residual modality bypasses from the tester re-review.

Round 14 bound deontic modals with per-class *counts*, which the tester's
probes 5-7 still bypassed (report `tester_r15_report.md`, P1):

- Cross-clause swap: "A must x and B may y" restated as "A may x and B must
  y" keeps both class histograms, so the counts agreed while each clause
  changed force (probe 7).
- Wholesale drop: "must be approved" restated as "are approved" /
  "will be approved" dropped the modal entirely; the condition only *loses*
  a class, which the counts allowed (probes 5-6), including the
  ``define_rule_preconditions`` path ("Trip must be pre-approved" ->
  "Trip is pre-approved" -> satisfied).

``anchor_supports_text`` now requires a full restatement of the anchored
clause to keep the *ordered* modality sequence. Fragment quotes keep the
round-12 exemption: "not exceeding 5000 CNY" still quotes "should avoid
exceeding 5000 CNY", because a fragment omits anchor content by design and
its modal drops together with that content.
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


# ------------------------------------------- cross-clause swap (probe 7)
@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        (
            "Claims must be approved and invoices may be filed.",
            "Claims may be approved and invoices must be filed.",
        ),
        (
            "Claims must be approved; invoices may be filed.",
            "Claims may be approved; invoices must be filed.",
        ),
        (
            "Managers must approve claims and auditors may reject invoices.",
            "Managers may approve claims and auditors must reject invoices.",
        ),
    ],
)
def test_f2_cross_clause_modal_swap_is_rejected(
    runtime, ctx, workspace, anchor_text, condition_text
):
    """Same class histogram, opposite force per clause: refused (probe 7)."""

    _rejected(_rule_call(runtime, ctx, workspace, "f2swap.pdf", anchor_text, condition_text))


# ------------------------------------------- wholesale drop (probes 5-6)
@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("Claims above 5000 CNY must be approved.", "Claims above 5000 CNY are approved."),
        ("Claims above 5000 CNY may be approved.", "Claims above 5000 CNY are approved."),
        ("Claims above 5000 CNY should be approved.", "Claims above 5000 CNY are approved."),
        ("Claims above 5000 CNY must be approved.", "Claims above 5000 CNY approved."),
        ("Claims above 5000 CNY must be approved.", "Claims above 5000 CNY will be approved."),
    ],
)
def test_f2_modal_dropped_entirely_is_rejected(
    runtime, ctx, workspace, anchor_text, condition_text
):
    """A full restatement may not drop the modal (probes 5-6)."""

    _rejected(_rule_call(runtime, ctx, workspace, "f2drop.pdf", anchor_text, condition_text))


def test_f2_precondition_modal_drop_is_unknown(runtime, ctx, workspace):
    """define_rule_preconditions must not satisfy a de-modalised condition."""

    build_pdf(workspace / "f2pre.pdf", ["Trip must be pre-approved."])
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "f2pre.pdf")}, ctx, runtime
    ).data.document
    for text in ("Trip is pre-approved", "Trip pre-approved"):
        result = call(
            "define_rule_preconditions",
            {
                "rule_ref": "rule:pre",
                "document_ref": document,
                "proposal": {
                    "conditions": [
                        {
                            "condition_id": "c1",
                            "text": text,
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


# ------------------------------------------- carve-outs that must survive
def test_f2_fragment_quote_may_still_drop_the_modal(runtime, ctx, workspace):
    """Round-12 exemption: a fragment omits anchor content by design."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2frag.pdf",
        "Expenses should avoid exceeding 5000 CNY.",
        "not exceeding 5000 CNY",
    )
    assert result.status.value == "ok", result.issues


def test_f2_same_class_cross_clause_swap_still_grounded(runtime, ctx, workspace):
    """must <-> shall keeps the force on every clause, so the sequence agrees."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2same.pdf",
        "Claims must be approved and invoices shall be filed.",
        "Claims shall be approved and invoices must be filed.",
    )
    assert result.status.value == "ok", result.issues


def test_f2_verbatim_multi_modal_condition_still_grounded(runtime, ctx, workspace):
    """A verbatim quote keeps every modal on its own clause."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2verb.pdf",
        "Claims must be approved and invoices may be filed.",
        "Claims must be approved and invoices may be filed.",
    )
    assert result.status.value == "ok", result.issues
