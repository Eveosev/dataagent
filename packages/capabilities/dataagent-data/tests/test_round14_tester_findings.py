"""Round 14 regressions: the two blocking findings from the tester re-review.

Both findings survived Round 13 because the guards only covered the exact
probes the reviewer ran:

- F1 trust boundary: ``parse_text_pdf`` copied ``id``/``revision`` straight
  from the caller-supplied ``FileRef``, so a caller could point at real B
  bytes while claiming A's digest-derived identity and forge a binding that
  names A for B's body (tester probe 4). ``read_file_ref`` now refuses a
  revision that is not the verified digest and a digest-derived id that is
  not derived from the verified bytes.
- F2 modality: English modals were stopwords, so ``must be approved`` was
  accepted as a paraphrase of ``may be approved`` (tester probe 3). The
  deontic class counts (strong/weak obligation vs permission) must now agree
  between the anchor clause and the condition.
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


# ---------------------------------------------------------------- F1
def test_f1_spoofed_file_ref_identity_is_refused_at_parse(runtime, ctx, workspace):
    """B's real bytes + A's id/revision must not parse as A (tester probe 4)."""

    build_pdf(workspace / "a.pdf", ["Amount: 100 CNY."])
    build_pdf(workspace / "b.pdf", ["Amount: 999 CNY."])
    ref_a = file_ref(workspace, "a.pdf")
    ref_b = file_ref(workspace, "b.pdf")
    # A was parsed legitimately first, so A's identity exists in the store.
    legit = call("parse_text_pdf", {"file_ref": ref_a}, ctx, runtime)
    assert legit.status.value == "ok", legit.issues
    # B's bytes and B's real content_digest, but the FileRef claims A's
    # digest-derived id and revision.
    spoofed = ref_b.model_copy(update={"id": ref_a.id, "revision": ref_a.revision})
    result = call("parse_text_pdf", {"file_ref": spoofed}, ctx, runtime)
    assert result.status.value == "failed", result.issues
    codes = {issue.code for issue in result.issues}
    assert "invalid_input" in codes
    assert "forged source identity" in result.issues[0].message


def test_f1_spoofed_custom_identity_is_refused(runtime, ctx, workspace):
    """A registered (id, revision) can never be re-bound to different bytes."""

    build_pdf(workspace / "c.pdf", ["Amount: 100 CNY."])
    build_pdf(workspace / "d.pdf", ["Amount: 999 CNY."])
    # D legitimately owns the free-form identity (file:policy, rev:1).
    owned = file_ref(
        workspace, "d.pdf", id="file:policy", revision="rev:1"
    )
    legit = call("parse_text_pdf", {"file_ref": owned}, ctx, runtime)
    assert legit.status.value == "ok", legit.issues
    # C's real bytes and digest, claiming D's registered identity.
    ref_c = file_ref(workspace, "c.pdf")
    spoofed = ref_c.model_copy(update={"id": "file:policy", "revision": "rev:1"})
    result = call("parse_text_pdf", {"file_ref": spoofed}, ctx, runtime)
    assert result.status.value == "failed", result.issues
    codes = {issue.code for issue in result.issues}
    assert "invalid_input" in codes
    assert "already bound to different bytes" in result.issues[0].message


def test_f1_custom_id_with_own_digest_still_parses(runtime, ctx, workspace):
    """A caller-chosen id is fine as long as the revision is the real digest."""

    build_pdf(workspace / "e.pdf", ["Amount: 100 CNY."])
    ref = file_ref(workspace, "e.pdf", id="file:policy")
    result = call("parse_text_pdf", {"file_ref": ref}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    assert result.data.document.original_ref.id == "file:policy"


def test_f1_spoofed_parse_leaves_no_extractable_record(runtime, ctx, workspace):
    """The forged document is never produced, so nothing can be extracted."""

    build_pdf(workspace / "a.pdf", ["Amount: 100 CNY."])
    build_pdf(workspace / "b.pdf", ["Amount: 999 CNY."])
    ref_a = file_ref(workspace, "a.pdf")
    ref_b = file_ref(workspace, "b.pdf")
    document_a = call(
        "parse_text_pdf", {"file_ref": ref_a}, ctx, runtime
    ).data.document
    spoofed = ref_b.model_copy(update={"id": ref_a.id, "revision": ref_a.revision})
    parsed = call("parse_text_pdf", {"file_ref": spoofed}, ctx, runtime)
    assert parsed.status.value == "failed", parsed.issues
    assert parsed.data is None
    # The legitimate A document is unaffected: its binding still verifies.
    extract = call(
        "extract_fields_to_schema",
        {
            "document_ref": document_a,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "Amount",
                    "path": "/amount",
                    "value_type": "money",
                    "unit": "CNY",
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 100,
                    "value_type": "money",
                    "unit": "CNY",
                    "anchors": [_full_page_anchor(document_a, runtime)],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert extract.status.value == "ok", extract.issues
    assert extract.data.record.fields[0].value == 100


# ---------------------------------------------------------------- F2
def test_f2_must_to_may_is_rejected(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal1.pdf",
        "Claims above 5000 CNY must be approved.",
        "Claims above 5000 CNY may be approved.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_f2_may_to_must_is_rejected(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal2.pdf",
        "Claims above 5000 CNY may be approved.",
        "Claims above 5000 CNY must be approved.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_f2_should_to_may_is_rejected(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal3.pdf",
        "Claims above 5000 CNY should be approved.",
        "Claims above 5000 CNY may be approved.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_f2_must_to_should_is_rejected(runtime, ctx, workspace):
    """should is weaker than must: a different deontic class, refused."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal4.pdf",
        "Claims above 5000 CNY must be approved.",
        "Claims above 5000 CNY should be approved.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_f2_verbatim_modal_condition_still_grounded(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal5.pdf",
        "Claims above 5000 CNY must be approved.",
        "Claims above 5000 CNY must be approved.",
    )
    assert result.status.value == "ok", result.issues


def test_f2_same_class_modal_paraphrase_still_grounded(runtime, ctx, workspace):
    """must <-> shall keeps the deontic force and stays acceptable."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal6.pdf",
        "Claims above 5000 CNY shall be approved.",
        "Claims above 5000 CNY must be approved.",
    )
    assert result.status.value == "ok", result.issues


def test_f2_chinese_obligation_to_permission_is_rejected(
    runtime, ctx, workspace
):
    """Chinese modality is content (not stopword) and must already be refused."""

    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal7.pdf",
        "报销金额超过5000元必须审批。",
        "报销金额超过5000元可以审批。",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


@pytest.mark.parametrize(
    ("anchor_text", "condition_text"),
    [
        ("Expenses must be submitted before Friday.", "Expenses can be submitted before Friday."),
        ("Invoices might be rejected.", "Invoices must be rejected."),
        ("Reports could be archived.", "Reports must be archived."),
    ],
)
def test_f2_other_modal_swaps_are_rejected(
    runtime, ctx, workspace, anchor_text, condition_text
):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2modal8.pdf",
        anchor_text,
        condition_text,
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes
