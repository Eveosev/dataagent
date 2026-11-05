"""Round 17 regressions: the tester r17 blocking findings (B2/B3 + R4c).

``tester_r17_report.md`` §3–§4 reproduced three acceptance gaps against the
06 plan with real ``invoke`` calls:

- R4 (fail-open): an ``auto`` decidability proposal citing fabricated
  ``basis_refs`` (``nonexistent:evidence`` or a lookalike hex id) was
  accepted as ``ok``, persisted with the fabricated ref, and let the
  downstream gap plan conclude ``gaps=0`` (plan §5 step 3 / §10.2).
- R5 (completeness): ``segment_document`` capped at ``max_units`` and the
  extraction first phase capped span text at 300 chars / 30 spans while
  still declaring ``complete_in_declared_scope`` (plan §4.1).
- R4c (cache): ``resolve_decidability_cache`` only compared statements when
  the caller also supplied ``prior_statement``; without it a changed
  statement still hit the cache.
"""

from __future__ import annotations

import sqlite3

from conftest import build_pdf, call, file_ref


def _assess(runtime, ctx, basis, *, requirement_ref="rule:1@r1", unknowns=None):
    return call(
        "assess_automatic_decidability",
        {
            "requirement_ref": requirement_ref,
            "statement": "check amount",
            "proposal": {
                "verdict": "auto",
                "basis_refs": basis,
                "dependency_refs": [],
                "unknowns": unknowns or [],
                "next_actions": [],
            },
        },
        ctx,
        runtime,
    )


def _parse_pdf(runtime, ctx, workspace, name, lines):
    build_pdf(workspace / name, lines)
    return call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, name)}, ctx, runtime
    ).data.document


def _assessment_rows(runtime, like):
    conn = sqlite3.connect(runtime.data_root / "db" / "dataagent.sqlite3")
    try:
        return conn.execute(
            "SELECT payload FROM objects WHERE kind='decidability_assessment' "
            "AND payload LIKE ?",
            (f"%{like}%",),
        ).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# R4: fabricated basis refs must not ground an auto verdict
# ---------------------------------------------------------------------------


def test_fabricated_basis_ref_downgrades_auto(runtime, ctx):
    result = _assess(runtime, ctx, ["nonexistent:evidence"])
    assert result.status.value == "partial"
    assert result.data.verdict.value == "needs_evidence"
    assert result.issues[0].code == "da03.auto_unverifiable_basis"
    # The fabricated ref is dropped, not persisted as if it were evidence.
    assert result.data.basis_refs == []
    assert _assessment_rows(runtime, "nonexistent:evidence") == []


def test_lookalike_basis_ref_downgrades_auto(runtime, ctx):
    result = _assess(runtime, ctx, ["evidence:0000000000000000"])
    assert result.status.value == "partial"
    assert result.data.verdict.value == "needs_evidence"
    assert result.issues[0].code == "da03.auto_unverifiable_basis"
    assert result.data.basis_refs == []


def test_mixed_basis_keeps_only_resolvable_refs(runtime, ctx):
    runtime.versions.save("evidence", "ev:1", {"note": "fixture"})
    result = _assess(runtime, ctx, ["ev:1", "nonexistent:evidence"])
    assert result.status.value == "partial"
    assert result.data.verdict.value == "needs_evidence"
    assert result.issues[0].code == "da03.auto_unverifiable_basis"
    assert result.data.basis_refs == ["ev:1"]


def test_resolvable_basis_refs_still_ground_auto(runtime, ctx, workspace):
    document = _parse_pdf(runtime, ctx, workspace, "policy.pdf", ["Amount: 5800 CNY"])
    # A registered source file ref (id@revision) and a content blob are both
    # real runtime evidence and must keep the verdict auto (no overfitting).
    for ref in (str(document.original_ref), document.blocks_ref):
        result = _assess(runtime, ctx, [ref])
        assert result.status.value == "ok", result.issues
        assert result.data.verdict.value == "auto"
    stored = runtime.versions.save("evidence", "ev:2", {"note": "fixture"})
    result = _assess(runtime, ctx, [f"ev:2@{stored}"])
    assert result.status.value == "ok", result.issues
    assert result.data.verdict.value == "auto"


def test_empty_basis_control_still_downgrades(runtime, ctx):
    result = _assess(runtime, ctx, [])
    assert result.status.value == "partial"
    assert result.data.verdict.value == "needs_evidence"
    assert result.issues[0].code == "da03.auto_without_basis"


# ---------------------------------------------------------------------------
# R4c: cache invalidation without a prior statement is conservative
# ---------------------------------------------------------------------------


def _prior_assessment():
    return {
        "assessment_id": "asmt:cache17",
        "target_ref": "rule:1@r1",
        "verdict": "auto",
        "basis_refs": [],
        "dependency_refs": ["engine:expr@1"],
        "unknowns": [],
        "next_actions": [],
    }


def test_cache_with_statement_but_no_prior_statement_misses(runtime, ctx):
    result = call(
        "resolve_decidability_cache",
        {
            "prior": _prior_assessment(),
            "current_dependencies": ["engine:expr@1"],
            "statement": "check amount",
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    assert result.data.hit is False
    assert any("prior statement" in reason for reason in result.data.reasons)


def test_cache_with_matching_statements_still_hits(runtime, ctx):
    result = call(
        "resolve_decidability_cache",
        {
            "prior": _prior_assessment(),
            "current_dependencies": ["engine:expr@1"],
            "statement": "check amount",
            "prior_statement": "check amount",
        },
        ctx,
        runtime,
    )
    assert result.data.hit is True


# ---------------------------------------------------------------------------
# R5: truncation must be disclosed, not reported as complete
# ---------------------------------------------------------------------------


def test_segment_truncation_is_disclosed(runtime, ctx, workspace):
    document = _parse_pdf(
        runtime,
        ctx,
        workspace,
        "three.pdf",
        [
            "1. Scope",
            "Applies to claims.",
            "2. Approval",
            "Manager approval.",
            "3. Payment",
            "Paid monthly.",
        ],
    )
    result = call("segment_document", {"document_ref": document, "max_units": 2}, ctx, runtime)
    assert result.status.value == "ok"
    assert len(result.data.units) == 2
    assert result.completeness.extent.value == "truncated"
    assert "max_units=2" in result.completeness.reason
    assert result.completeness.observed == {"units": 2, "total_units": 3}


def test_segment_without_truncation_stays_complete(runtime, ctx, workspace):
    document = _parse_pdf(
        runtime,
        ctx,
        workspace,
        "two.pdf",
        ["1. Scope", "Applies to claims.", "2. Approval", "Manager approval."],
    )
    result = call("segment_document", {"document_ref": document}, ctx, runtime)
    assert result.status.value == "ok"
    assert result.completeness.extent.value == "complete_in_declared_scope"


def _extract_first_phase(runtime, ctx, document):
    return call(
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
        },
        ctx,
        runtime,
    )


def test_extract_span_text_truncation_is_disclosed(runtime, ctx, workspace):
    long_line = "Claims above 5000 CNY require department head approval. " + ("x" * 640)
    document = _parse_pdf(runtime, ctx, workspace, "long.pdf", [long_line])
    result = _extract_first_phase(runtime, ctx, document)
    assert result.status.value == "needs_input"
    assert result.data.candidate_spans
    assert max(len(span.text) for span in result.data.candidate_spans) == 300
    assert result.completeness.extent.value == "truncated"
    assert "300" in result.completeness.reason
    assert "truncations" in result.issues[0].inference_request


def test_extract_span_count_cap_is_disclosed(runtime, ctx, workspace):
    lines = [f"Sentence number {i:02d} about some claim above 5000 CNY." for i in range(40)]
    document = _parse_pdf(runtime, ctx, workspace, "many.pdf", lines)
    result = _extract_first_phase(runtime, ctx, document)
    assert result.status.value == "needs_input"
    assert len(result.data.candidate_spans) == 30
    assert result.completeness.extent.value == "truncated"
    assert "capped at 30" in result.completeness.reason


def test_extract_without_truncation_stays_complete(runtime, ctx, workspace):
    document = _parse_pdf(
        runtime, ctx, workspace, "short.pdf", ["Claims above 5000 CNY need approval."]
    )
    result = _extract_first_phase(runtime, ctx, document)
    assert result.status.value == "needs_input"
    assert result.completeness.extent.value == "complete_in_declared_scope"
