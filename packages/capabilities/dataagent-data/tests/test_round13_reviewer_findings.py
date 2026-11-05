"""Round 13 regressions: the P1 findings from the independent review.

Each test reproduces one reviewer probe exactly (F1-F6 in the review report)
and asserts the fail-closed behaviour introduced in this round:

- F1  a ``DocumentRef`` that recombines one source's ``original_ref`` with
      another document's ``blocks_ref`` is refused by ``load_document_content``;
- F2  comparison inclusivity, logical connectives and argument order are part
      of rule-condition grounding;
- F3  conditions without anchors cannot conclude from ``facts`` unless the
      caller explicitly opts in with ``declared_facts``;
- F4  applicability scopes and metric fields that no source/schema supports
      become explicit unknowns/unresolved instead of an "ok" draft;
- F5  an anchored value that contradicts the target field's type/unit is a
      conflict, not an extraction;
- F6  trace events persist their actor, refuse to re-state it, and a naive
      timestamp fails before any write.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------- F1
def test_f1_cross_document_blocks_ref_is_refused(runtime, ctx, workspace):
    build_pdf(workspace / "real.pdf", ["Amount: 100 CNY."])
    build_pdf(workspace / "other.pdf", ["Amount: 999 CNY."])
    real = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "real.pdf")}, ctx, runtime
    ).data.document
    other = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "other.pdf")}, ctx, runtime
    ).data.document
    forged = real.model_copy(update={"blocks_ref": other.blocks_ref})
    result = call(
        "extract_fields_to_schema",
        {
            "document_ref": forged.model_dump(mode="json"),
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
                    "value": 999,
                    "value_type": "money",
                    "unit": "CNY",
                    "anchors": [_full_page_anchor(real, runtime)],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert result.status.value == "failed", result.issues
    assert result.issues[0].code == "invalid_input"
    # r32-gov B1: the asset-content binding fires before the parse-record
    # lookup, so a rebound blocks_ref is refused as unbound content.
    assert "not the document asset's content" in result.issues[0].message


# ---------------------------------------------------------------- F2
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


def test_f2_inclusivity_swap_is_rejected(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2a.pdf",
        "Claims above 5000 CNY require approval.",
        "Claims at least 5000 CNY require approval.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_f2_and_or_swap_is_rejected(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2b.pdf",
        "Claims and invoices require approval.",
        "Claims or invoices require approval.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_f2_argument_role_swap_is_rejected(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2c.pdf",
        "Managers approve employees.",
        "Employees approve managers.",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


def test_f2_verbatim_condition_still_grounded(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2d.pdf",
        "Claims above 5000 CNY require approval.",
        "Claims above 5000 CNY require approval.",
    )
    assert result.status.value == "ok", result.issues


def test_f2_chinese_inclusive_boundary_swap_is_rejected(runtime, ctx, workspace):
    result = _rule_call(
        runtime,
        ctx,
        workspace,
        "f2e.pdf",
        "报销金额不得超过5000元。",
        "报销金额低于5000元。",
    )
    assert result.status.value == "needs_input", result.issues
    codes = {issue.code for issue in result.issues}
    assert "da02.anchor_value_mismatch" in codes


# ---------------------------------------------------------------- F3
def test_f3_facts_alone_cannot_conclude_satisfied(runtime, ctx):
    payload = {
        "rule_ref": "rule:1@r1",
        "proposal": {
            "conditions": [
                {"condition_id": "c1", "text": "Trip must be pre-approved", "anchors": []}
            ],
            "combination": "all(c1)",
        },
        "facts": {"c1": True},
    }
    result = call("define_rule_preconditions", payload, ctx, runtime)
    assert result.status.value == "partial", result.issues
    assert result.data.evaluation.verdict == "unknown"
    assert result.data.draft.unknowns == ["c1"]
    codes = {issue.code for issue in result.issues}
    assert "da03.unanchored_condition" in codes

    explicit = call(
        "define_rule_preconditions", {**payload, "declared_facts": True}, ctx, runtime
    )
    assert explicit.status.value == "ok", explicit.issues
    assert explicit.data.evaluation.verdict == "satisfied"


# ---------------------------------------------------------------- F4
def test_f4_applicability_ungrounded_scope_becomes_unknown(runtime, ctx, workspace):
    build_pdf(workspace / "scope.pdf", ["This policy covers expense claims in CN."])
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "scope.pdf")}, ctx, runtime
    ).data.document
    result = call(
        "define_rule_applicability",
        {
            "rule_ref": "rule:1@r1",
            "document_ref": document,
            "sources": [_full_page_anchor(document, runtime)],
            "proposal": {
                "scope_expression": "All Martian spacecraft in 2099",
                "object_types": ["spacecraft"],
                "scenarios": ["interplanetary war"],
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "partial", result.issues
    assert result.data.unknowns, "ungrounded scope must be recorded as unknowns"
    joined = "\n".join(result.data.unknowns)
    assert "scope_expression" in joined and "scenario" in joined
    codes = {issue.code for issue in result.issues}
    assert "da03.scope_not_grounded" in codes


def test_f4_metric_unbound_fields_become_unresolved(runtime, ctx, workspace):
    build_pdf(
        workspace / "metric.pdf", ["This policy covers expense claims in CN."]
    )
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "metric.pdf")}, ctx, runtime
    ).data.document
    result = call(
        "define_metric_formula",
        {
            "statement": "monthly net revenue",
            "document_ref": document,
            "sources": [_full_page_anchor(document, runtime)],
            "available_fields": ["amount"],
            "proposal": {
                "measure_field": "amount",
                "aggregation": "avg",
                "grain": "galaxy x century",
                "filters": ["ghost_field = 999"],
                "dimensions": ["nonexistent_field"],
                "unit": "BTC",
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "partial", result.issues
    unresolved = result.data.draft.unresolved
    assert any("nonexistent_field" in item for item in unresolved)
    assert any("ghost_field" in item for item in unresolved)
    assert any("galaxy" in item for item in unresolved)
    assert any("BTC" in item for item in unresolved)


# ---------------------------------------------------------------- F5
def test_f5_target_schema_type_and_unit_are_enforced(runtime, ctx, workspace):
    build_pdf(workspace / "f5.pdf", ["Name: Alice."])
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "f5.pdf")}, ctx, runtime
    ).data.document
    text = _page_text(runtime, document)
    result = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "Amount",
                    "path": "/amount",
                    "value_type": "number",
                    "unit": "CNY",
                    "nullable": False,
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": "Alice",
                    "value_type": "string",
                    "unit": "BTC",
                    "anchors": [
                        {
                            "source_ref": document.original_ref.id,
                            "source_revision": document.original_ref.revision,
                            "selector": {
                                "kind": "pdf_text_span",
                                "page": 1,
                                "char_start": text.index("Alice"),
                                "char_end": text.index("Alice") + len("Alice"),
                            },
                        }
                    ],
                }
            ],
        },
        ctx,
        runtime,
    )
    field = result.data.record.fields[0]
    assert field.status.value == "conflict", field
    assert field.value is None
    assert field.alternatives == ["Alice"]
    codes = {issue.code for issue in result.issues}
    assert "da02.field_type_mismatch" in codes


def test_f5_conforming_value_still_extracts(runtime, ctx, workspace):
    build_pdf(workspace / "f5b.pdf", ["Amount: 100 CNY."])
    document = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "f5b.pdf")}, ctx, runtime
    ).data.document
    result = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "Amount",
                    "path": "/amount",
                    "value_type": "number",
                    "unit": "CNY",
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 100,
                    "value_type": "number",
                    "unit": "CNY",
                    "anchors": [_full_page_anchor(document, runtime)],
                }
            ],
        },
        ctx,
        runtime,
    )
    field = result.data.record.fields[0]
    assert field.status.value == "extracted", result.issues
    assert field.value == 100


# ---------------------------------------------------------------- F6a
def test_f6a_actor_is_persisted_and_not_restatable(runtime, ctx):
    base = {
        "task_ref": "task:a@r1",
        "event_id": "actor-review",
        "actor_ref": "user:alice",
        "timestamp": "2026-11-04T10:00:00+00:00",
        "payload": {"x": 1},
    }
    first = call("append_task_event", base, ctx, runtime)
    assert first.status.value == "ok"
    stored = runtime.traces.get_event("task:a@r1", "actor-review")
    assert stored.payload["actor_ref"] == "user:alice"

    replay = call("append_task_event", base, ctx, runtime)
    assert replay.status.value == "ok"
    assert replay.data.actor_ref == "user:alice"
    assert replay.completeness.observed["duplicate"] == 1

    hijack = call(
        "append_task_event", {**base, "actor_ref": "user:mallory"}, ctx, runtime
    )
    assert hijack.status.value == "failed", hijack.issues
    assert hijack.issues[0].code == "version_conflict"


def test_f6b_naive_timestamp_fails_without_side_effects(runtime, ctx):
    before = runtime.traces.last_cursor("task:naive@r1")
    result = call(
        "append_task_event",
        {
            "task_ref": "task:naive@r1",
            "event_id": "naive-time",
            "actor_ref": "user:alice",
            "timestamp": "2026-11-04T10:00:00",
            "payload": {"x": 1},
        },
        ctx,
        runtime,
    )
    assert result.status.value == "failed", result.issues
    assert result.issues[0].code == "invalid_input"
    assert "timezone-aware" in result.issues[0].message
    after = runtime.traces.last_cursor("task:naive@r1")
    assert after == before, "a rejected input must not advance the trace cursor"
