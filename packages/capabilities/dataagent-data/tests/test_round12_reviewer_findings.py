"""Round 12: reviewer F1 (English preventive verbs) and F2 (DA03.16.2 anchors).

Reviewer probe F1: ``Expenses should avoid exceeding 5000 CNY`` scopes the
comparison exactly like the Chinese preventive forms fixed in rounds 7-11. The
reversed condition ``exceeding 5000 CNY`` must be rejected by the parser, the
anchor text check and the ``define_business_rules`` atomic entry; the correct
``not exceeding 5000 CNY`` must stay grounded.

Reviewer probe F2: DA03.16.2 used to store any caller-supplied anchor without
resolving it, so a fabricated precondition (page 999 of an unknown file) was
recorded and could evaluate to ``satisfied``. The atom now resolves every
condition anchor and forces an ungrounded condition to UNKNOWN.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from conftest import build_pdf, call, file_ref
from dataagent_contracts.core import (
    AssetRef,
    CallContext,
    DocumentRef,
    SourceAnchor,
    VersionedRef,
)
from dataagent_data.contracts.layer import DocumentContent, PageContent
from dataagent_data.anchors import (
    _comparison_analysis,
    _comparison_bounds,
    _comparison_scope_is_ambiguous,
    anchor_supports_text,
)


def _anchor(anchor_text: str = "anchor") -> SourceAnchor:
    return SourceAnchor(
        source_ref="file:en",
        source_revision="r1",
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": 0,
            "char_end": len(anchor_text),
        },
    )


def _content(anchor_text: str) -> DocumentContent:
    return DocumentContent(pages=[PageContent(page=1, text=anchor_text)])


def _document(runtime, ctx, workspace, lines: list[str]) -> tuple[DocumentRef, str]:
    build_pdf(workspace / "review.pdf", lines)
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "review.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    page_text = runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]
    return document, page_text


def _text_anchor(document: DocumentRef, page_text: str, needle: str) -> SourceAnchor:
    start = page_text.index(needle)
    return SourceAnchor(
        source_ref=document.original_ref.id,
        source_revision=document.original_ref.revision,
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": start + len(needle),
        },
    )


# ---------------------------------------------------------------------------
# F1: English preventive verbs state the negated direction.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anchor_text", "direction"),
    [
        ("Expenses should avoid exceeding 5000 CNY", "lower"),
        ("Expenses should prevent falling below 5000 CNY", "upper"),
        ("Expenses exceeding 5000 CNY should be avoided", "lower"),
        ("Expenses exceeding 5000 CNY are prohibited", "lower"),
        ("Avoid unnecessary costs exceeding 5000 CNY", "lower"),
        ("Avoid not exceeding 5000 CNY", "upper"),
        ("5000 CNY or more should be avoided", "lower"),
        ("Expenses banned from exceeding 5000 CNY", "lower"),
        ("Expenses barred from exceeding 5000 CNY", "lower"),
        ("Expenses exceeding 5000 CNY are banned", "lower"),
    ],
)
def test_english_preventive_verb_states_the_negated_direction(anchor_text, direction):
    assert _comparison_bounds(anchor_text) == {(direction, Decimal(5000))}
    assert _comparison_scope_is_ambiguous(anchor_text) is False


def test_english_preventive_verb_rejects_the_reversed_condition():
    content = _content("Expenses should avoid exceeding 5000 CNY")
    anchor = _anchor("Expenses should avoid exceeding 5000 CNY")
    assert anchor_supports_text(content, anchor, "not exceeding 5000 CNY") == ""
    assert anchor_supports_text(content, anchor, "avoid exceeding 5000 CNY") == ""
    assert anchor_supports_text(content, anchor, "exceeding 5000 CNY") != ""


def test_english_preventive_verb_rejects_the_reversed_upper_condition():
    content = _content("Expenses should prevent falling below 5000 CNY")
    anchor = _anchor("Expenses should prevent falling below 5000 CNY")
    assert anchor_supports_text(content, anchor, "prevent falling below 5000 CNY") == ""
    assert anchor_supports_text(content, anchor, "falling below 5000 CNY") != ""


def test_english_preventive_unreadable_scope_is_fail_closed():
    for text in (
        "Avoid and prevent exceeding 5000 CNY",
        "do not avoid exceeding 5000 CNY",
        "Expenses exceeding 5000 CNY should not be avoided",
    ):
        assert _comparison_scope_is_ambiguous(text) is True, text


def test_english_preventive_does_not_over_reject_unrelated_verbs():
    for text in (
        "To avoid delays, expenses exceeding 5000 CNY require approval",
        "Expenses exceeding 5000 CNY require approval to avoid fraud",
        "avoidance costs exceed 5000 CNY",
        "prevention costs exceed 5000 CNY",
        "Bar costs exceed 5000 CNY",
        "Ban costs exceed 5000 CNY",
        "Stop costs exceed 5000 CNY",
    ):
        assert _comparison_bounds(text) == {("upper", Decimal(5000))}, text
        assert _comparison_scope_is_ambiguous(text) is False, text


def _define_rule(runtime, ctx, anchor_text: str, condition_text: str):
    blocks_ref = runtime.content.put(_content(anchor_text).model_dump(mode="json"))
    document = DocumentRef(
        # r32-gov B1: the document asset must be digest-bound to its blocks
        # (every product parse path already is; see load_document_content).
        asset=AssetRef(
            id="asset:en",
            kind="document",
            scope_ref="tenant:test/project:p1",
            revision=blocks_ref,
            resolver="local_content",
            locator=blocks_ref,
            digest=blocks_ref,
        ),
        original_ref=VersionedRef(id="file:en", revision="r1"),
        content_type="text",
        blocks_ref=blocks_ref,
        page_count=1,
    )
    # Locally built documents must register their source binding so that
    # load_document_content accepts them (reviewer F1 fail-closed rule).
    from dataagent_data.preparation.documents import register_document_blocks

    register_document_blocks(runtime, document)
    return call(
        "define_business_rules",
        {
            "statement": "expense threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": condition_text,
                        "anchors": [_anchor(anchor_text)],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )


def test_english_preventive_verb_atomic_entry(runtime, ctx):
    reversed_condition = _define_rule(
        runtime, ctx, "Expenses should avoid exceeding 5000 CNY", "exceeding 5000 CNY"
    )
    assert reversed_condition.status.value == "needs_input"
    assert any(
        issue.code == "da02.anchor_value_mismatch"
        for issue in reversed_condition.issues
    )

    grounded = _define_rule(
        runtime, ctx, "Expenses should avoid exceeding 5000 CNY", "not exceeding 5000 CNY"
    )
    assert grounded.status.value == "ok", grounded.issues


# ---------------------------------------------------------------------------
# F2: DA03.16.2 resolves condition anchors and keeps ungrounded facts UNKNOWN.
# ---------------------------------------------------------------------------


def _preconditions_payload(anchors: list[dict], document=None, rule_ref="rule:pre"):
    payload = {
        "rule_ref": rule_ref,
        "proposal": {
            "conditions": [
                {
                    "condition_id": "c1",
                    "text": "Trip must be pre-approved",
                    "anchors": anchors,
                }
            ],
            "combination": "all(c1)",
        },
        "facts": {"c1": True},
    }
    if document is not None:
        payload["document_ref"] = document
    return payload


def test_precondition_fabricated_anchor_is_not_ok(runtime, ctx):
    bogus = {
        "source_ref": "file:does-not-exist",
        "source_revision": "r1",
        "selector": {
            "kind": "pdf_text_span",
            "page": 999,
            "char_start": 0,
            "char_end": 10,
        },
    }
    result = call(
        "define_rule_preconditions",
        _preconditions_payload([bogus]),
        ctx,
        runtime,
    )
    assert result.status.value == "partial", result.issues
    assert result.data.evaluation.verdict == "unknown"
    assert result.data.draft.conditions[0].anchors == []
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_not_found" in codes
    assert "da03.unanchored_condition" in codes
    assert "c1" in result.data.draft.unknowns


def test_precondition_source_must_match_document(runtime, ctx, workspace):
    document, page_text = _document(
        runtime, ctx, workspace, ["Trip must be pre-approved"]
    )
    anchor = _text_anchor(document, page_text, "Trip must be pre-approved")
    wrong = {**anchor.model_dump(mode="json"), "source_ref": "file:other"}
    result = call(
        "define_rule_preconditions",
        _preconditions_payload([wrong], document=document),
        ctx,
        runtime,
    )
    assert result.status.value == "partial"
    assert result.data.evaluation.verdict == "unknown"
    assert result.data.draft.conditions[0].anchors == []


def test_precondition_anchor_must_support_the_condition(runtime, ctx, workspace):
    document, page_text = _document(
        runtime, ctx, workspace, ["Trip must be pre-approved"]
    )
    anchor = _text_anchor(document, page_text, "Trip must be pre-approved")
    payload = _preconditions_payload([anchor], document=document)
    payload["proposal"]["conditions"][0]["text"] = "All invoices must be stamped"
    result = call("define_rule_preconditions", payload, ctx, runtime)
    assert result.status.value == "partial"
    assert result.data.evaluation.verdict == "unknown"
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_precondition_grounded_anchor_is_ok(runtime, ctx, workspace):
    document, page_text = _document(
        runtime, ctx, workspace, ["Trip must be pre-approved"]
    )
    anchor = _text_anchor(document, page_text, "Trip must be pre-approved")
    result = call(
        "define_rule_preconditions",
        _preconditions_payload([anchor], document=document),
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    assert result.data.evaluation.verdict == "satisfied"
    assert len(result.data.draft.conditions[0].anchors) == 1


def test_precondition_canonical_versioned_rule_ref_is_accepted(runtime, ctx):
    result = call(
        "define_rule_preconditions",
        {**_preconditions_payload([], rule_ref="draft:rule:abc@r1"), "declared_facts": True},
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    assert result.data.draft.rule_ref == "draft:rule:abc@r1"
    assert "@" not in result.data.draft_ref.id
