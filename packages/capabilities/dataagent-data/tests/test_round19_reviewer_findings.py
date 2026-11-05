"""Round 19 regressions: the reviewer's four semantic-support bypasses.

The reviewer's r19 report (`reviewer_r19_report.md`, P1 F1-F4) confirmed via
real MCP two-phase calls that ten rewrites still returned ``ok`` with empty
``unknowns``/``unresolved`` and were persisted:

- F1 applicability scope: the scope expression was only checked term-by-term
  (``ungrounded_terms``), so a negated / bound-reversed / connective-swapped
  scope passed because ``not``/``above``/``and`` are coverage stopwords.
- F2 metric filter: a filter was only checked for field *existence* in the
  bound schema, so a fabricated value (``'refunded'``) and a reversed
  operator (``!=``) passed while the source states ``status = 'paid'``.
- F3 comparison subject binding: the per-subject binding dropped
  inclusivity, so two subjects sharing one threshold could swap
  ``above``/``at least`` while the global bound set stayed identical.
- F4 guard drop: the verbatim-substring fast path returned before any
  structural check, so quoting only the consequent of a conditional (or the
  head of an ``only after`` clause) dropped the whole guard and still
  persisted an unconditional rule / satisfied precondition.

The gates now: ``semantic_divergence`` holds scope expressions to the same
structural invariants as quotes; metric filters may not diverge from
predicates their sources state on the field; subject bindings keep the
boundary (strict/inclusive); and a dropped guard fails closed, while quoting
the antecedent (the legitimate precondition form) stays grounded.
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


def _rule_call(runtime, ctx, workspace, name, anchor_text, condition_text):
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


def _precondition_call(runtime, ctx, workspace, name, anchor_text, condition_text):
    document = _parsed(runtime, ctx, workspace, name, [anchor_text])
    return call(
        "define_rule_preconditions",
        {
            "rule_ref": "rule:r19@r1",
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
            "facts": {"c1": True},
        },
        ctx,
        runtime,
    )


def _applicability_call(runtime, ctx, workspace, name, anchor_text, scope_expression):
    document = _parsed(runtime, ctx, workspace, name, [anchor_text])
    return call(
        "define_rule_applicability",
        {
            "rule_ref": "rule:r19@r1",
            "document_ref": document,
            "sources": [_full_page_anchor(document, runtime)],
            "proposal": {"scope_expression": scope_expression},
        },
        ctx,
        runtime,
    )


def _metric_call(runtime, ctx, workspace, name, anchor_text, filters):
    document = _parsed(runtime, ctx, workspace, name, [anchor_text])
    return call(
        "define_metric_formula",
        {
            "statement": anchor_text,
            "document_ref": document,
            "sources": [_full_page_anchor(document, runtime)],
            "available_fields": ["amount", "status", "department"],
            "proposal": {
                "measure_field": "amount",
                "aggregation": "sum",
                "grain": "department",
                "dimensions": ["department"],
                "unit": "CNY",
                "filters": filters,
            },
        },
        ctx,
        runtime,
    )


def _rejected(result):
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes
    if result.data is not None and result.data.draft is not None:
        assert not result.data.draft.definition.conditions


# ------------------------------------------------ F4: dropped guards
@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        # Consequent of an "if/then" quoted as an unconditional rule.
        (
            "If claims are approved then invoices may be filed.",
            "Invoices may be filed.",
        ),
        # Head of an "only after" clause quoted without its guard.
        (
            "Invoices may be filed only after claims are approved.",
            "Invoices may be filed",
        ),
        # "only if" reads the same guard ("B only if A" ~ "if A then B").
        (
            "Invoices may be filed only if claims are approved.",
            "Invoices may be filed.",
        ),
        # "unless" states an exception; dropping it broadens the rule.
        (
            "Invoices may be filed unless claims are rejected.",
            "Invoices may be filed.",
        ),
    ],
)
def test_f4_guard_drop_is_rejected(
    runtime, ctx, workspace, anchor_text, condition_text
):
    _rejected(_rule_call(runtime, ctx, workspace, "f4.pdf", anchor_text, condition_text))


def test_f4_guard_drop_precondition_stays_unknown(runtime, ctx, workspace):
    """The guard stays unresolved instead of concluding "satisfied"."""

    result = _precondition_call(
        runtime,
        ctx,
        workspace,
        "f4prec.pdf",
        "If claims are approved then invoices may be filed.",
        "Invoices may be filed.",
    )
    assert result.status.value == "partial", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes
    assert result.data.evaluation.verdict == "unknown"
    assert result.data.draft.unknowns == ["c1"]


def test_f4_quoting_the_antecedent_keeps_the_guard(runtime, ctx, workspace):
    """The antecedent itself is the legitimate precondition form."""

    rules = _rule_call(
        runtime,
        ctx,
        workspace,
        "f4ante.pdf",
        "If claims are approved then invoices may be filed.",
        "Claims are approved.",
    )
    assert rules.status.value == "ok", rules.issues

    preconditions = _precondition_call(
        runtime,
        ctx,
        workspace,
        "f4ante2.pdf",
        "Invoices may be filed only after claims are approved.",
        "Claims are approved.",
    )
    assert preconditions.status.value == "ok", preconditions.issues
    assert preconditions.data.evaluation.verdict == "satisfied"


def test_f4_full_conditional_quote_stays_grounded(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f4full.pdf",
        "Invoices may be filed only after claims are approved.",
        "Invoices may be filed only after claims are approved.",
    )
    assert result.status.value == "ok", result.issues


def test_f4_chinese_guard_pair_is_checked(runtime, ctx, workspace):
    _rejected(
        _rule_call(
            runtime,
            ctx,
            workspace,
            "f4cn.pdf",
            "发票只有在理赔获批后方可提交。",
            "发票可以提交。",
        )
    )


# ------------------------------------------------ F3: inclusivity per subject
def test_f3_shared_threshold_inclusivity_swap_is_rejected(runtime, ctx, workspace):
    """Same global bound set, opposite boundary per subject (reviewer F3)."""

    _rejected(
        _rule_call(
            runtime,
            ctx,
            workspace,
            "f3.pdf",
            "Claims above 5000 CNY and invoices at least 5000 CNY require approval.",
            "Claims at least 5000 CNY and invoices above 5000 CNY require approval.",
        )
    )


def test_f3_shared_threshold_inclusivity_swap_precondition_unknown(
    runtime, ctx, workspace
):
    result = _precondition_call(
        runtime,
        ctx,
        workspace,
        "f3prec.pdf",
        "Claims above 5000 CNY and invoices at least 5000 CNY require approval.",
        "Claims at least 5000 CNY and invoices above 5000 CNY require approval.",
    )
    assert result.status.value == "partial", result.issues
    assert result.data.evaluation.verdict == "unknown"
    assert result.data.draft.unknowns == ["c1"]


def test_f3_verbatim_shared_threshold_stays_grounded(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f3verb.pdf",
        "Claims above 5000 CNY and invoices at least 5000 CNY require approval.",
        "Claims above 5000 CNY and invoices at least 5000 CNY require approval.",
    )
    assert result.status.value == "ok", result.issues


def test_f3_single_subject_fragment_keeps_its_boundary(runtime, ctx, workspace):
    """A fragment still quotes one subject's bound with its boundary."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f3frag.pdf",
        "Claims above 5000 CNY and invoices at least 5000 CNY require approval.",
        "Claims above 5000 CNY",
    )
    assert result.status.value == "ok", result.issues


# ------------------------------------------------ F1: applicability scope
@pytest.mark.parametrize(
    ("anchor_text", "scope_expression"),
    [
        # Negation reversal (the grammatical form the term check missed).
        (
            "Employee claims are covered by this policy.",
            "Employee claims are not covered by this policy.",
        ),
        # Comparison bound reversal.
        (
            "This policy covers claims above 5000 CNY.",
            "This policy covers claims below 5000 CNY.",
        ),
        # Connective swap.
        (
            "This policy covers claims and invoices.",
            "This policy covers claims or invoices.",
        ),
        # Guard drop through the scope expression.
        (
            "If claims are approved then invoices may be filed.",
            "Invoices may be filed.",
        ),
    ],
)
def test_f1_scope_divergence_becomes_unknown(
    runtime, ctx, workspace, anchor_text, scope_expression
):
    result = _applicability_call(
        runtime, ctx, workspace, "f1.pdf", anchor_text, scope_expression
    )
    assert result.status.value == "partial", result.issues
    assert result.data.unknowns, "a diverging scope must be recorded as unknowns"
    codes = {issue.code for issue in result.issues}
    assert "da03.scope_semantic_divergence" in codes


def test_f1_untouched_scope_stays_ok(runtime, ctx, workspace):
    result = _applicability_call(
        runtime,
        ctx,
        workspace,
        "f1ok.pdf",
        "This policy applies to employee claims.",
        "This policy applies to employee claims.",
    )
    assert result.status.value == "ok", result.issues
    assert result.data.unknowns == []


# ------------------------------------------------ F2: metric filter predicates
@pytest.mark.parametrize(
    "filter_text",
    [
        # Fabricated constant: the source states 'paid'.
        "status = 'refunded'",
        # Reversed operator.
        "status != 'paid'",
    ],
)
def test_f2_filter_divergence_becomes_unresolved(
    runtime, ctx, workspace, filter_text
):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2.pdf",
        "Sum amount CNY for status = 'paid' by department.",
        [filter_text],
    )
    assert result.status.value == "partial", result.issues
    assert result.data.draft.unresolved, "a diverging filter must stay unresolved"
    codes = {issue.code for issue in result.issues}
    assert "da03.metric_unresolved" in codes


def test_f2_stated_filter_stays_ok(runtime, ctx, workspace):
    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2ok.pdf",
        "Sum amount CNY for status = 'paid' by department.",
        ["status = 'paid'"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []


def test_f2_unconstrained_field_filter_stays_ok(runtime, ctx, workspace):
    """A source that never constrains the field leaves the filter to the schema."""

    result = _metric_call(
        runtime,
        ctx,
        workspace,
        "f2worded.pdf",
        "Monthly net revenue is amount minus refunds in CNY.",
        ["status != 'refunded'"],
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.unresolved == []
