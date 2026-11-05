from __future__ import annotations

from conftest import build_pdf, call, file_ref


def source_anchor():
    return {
        "source_ref": "file:policy",
        "source_revision": "sha256:aa11",
        "selector": {"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": 5},
    }


def document_anchor(document, runtime=None):
    # Without a runtime the anchor covers a short span at the page start
    # (existence only); pass ``runtime`` to anchor the full first page so the
    # source actually grounds the proposal content (reviewer F4).
    original = document.original_ref
    char_end = 5
    if runtime is not None:
        char_end = len(runtime.content.get_json(document.blocks_ref)["pages"][0]["text"])
    return {
        "source_ref": original.id,
        "source_revision": original.revision,
        "selector": {"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": char_end},
    }


def test_define_metric_two_phase(runtime, ctx, workspace):
    build_pdf(workspace / "metric.pdf", ["Monthly net revenue is amount minus refunds in CNY."])
    parsed = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "metric.pdf")},
        ctx,
        runtime,
    )
    first = call(
        "define_metric_formula",
        {"statement": "monthly net revenue", "available_fields": ["amount", "paid_at"]},
        ctx,
        runtime,
    )
    assert first.status.value == "needs_input"
    assert first.issues[0].inference_request["kind"] == "metric_definition"

    second = call(
        "define_metric_formula",
        {
            "statement": "monthly net revenue",
            "available_fields": ["amount", "paid_at", "store", "status"],
            "document_ref": parsed.data.document,
            "sources": [document_anchor(parsed.data.document, runtime)],
            "proposal": {
                "measure_field": "amount",
                "aggregation": "sum",
                "filters": ["status != 'refunded'"],
                "dimensions": ["store"],
                "time_field": "paid_at",
                "time_grain": "month",
                "grain": "store x month",
                "unit": "CNY",
                "additivity": "additive",
            },
        },
        ctx,
        runtime,
    )
    assert second.status.value == "ok", second.issues
    draft = second.data.draft
    assert draft.kind == "metric"
    assert draft.definition.measure.aggregation.value == "sum"
    stored = runtime.versions.current("semantic_draft", draft.draft_id)
    assert stored is not None


def test_metric_rejects_a_source_that_does_not_resolve(runtime, ctx, workspace):
    build_pdf(workspace / "metric.pdf", ["Monthly net revenue."])
    parsed = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "metric.pdf")},
        ctx,
        runtime,
    )
    result = call(
        "define_metric_formula",
        {
            "statement": "monthly net revenue",
            "available_fields": ["amount"],
            "document_ref": parsed.data.document,
            "sources": [source_anchor()],
            "proposal": {
                "measure_field": "amount",
                "aggregation": "sum",
                "grain": "month",
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "needs_input"
    assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)
    assert any(issue.code == "da03.metric_source_required" for issue in result.issues)


def test_define_metric_rejects_unbound_field(runtime, ctx):
    result = call(
        "define_metric_formula",
        {
            "statement": "x",
            "available_fields": ["amount"],
            "sources": [source_anchor()],
            "proposal": {
                "measure_field": "missing",
                "aggregation": "sum",
                "grain": "month",
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_define_business_rules_two_phase_with_anchor_check(runtime, ctx, workspace):
    build_pdf(
        workspace / "policy.pdf",
        ["1. Scope", "Claims above 5000 CNY require department head approval."],
    )
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    content = runtime.content.get_json(document.blocks_ref)
    page_text = content["pages"][0]["text"]
    start = page_text.index("Claims above")
    end = page_text.index("approval.") + len("approval.")
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
    first = call(
        "define_business_rules",
        {"statement": "approval threshold", "document_ref": document},
        ctx,
        runtime,
    )
    assert first.status.value == "needs_input"
    assert first.issues[0].inference_request["kind"] == "business_rules"
    assert first.issues[0].inference_request["clauses"]

    second = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "claims above 5000 CNY",
                        "anchors": [anchor],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert second.status.value == "ok", second.issues
    assert second.data.draft.definition.conditions[0].anchors[0].selector.page == 1


def test_define_business_rules_drops_unanchored_condition(runtime, ctx, workspace):
    result = call(
        "define_business_rules",
        {
            "statement": "x",
            "proposal": {
                "conditions": [{"condition_id": "c1", "text": "no anchor", "anchors": []}],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "needs_input"
    assert any(issue.code == "da03.unanchored_condition" for issue in result.issues)


def decidability_proposal(verdict="auto", basis=None, unknowns=None):
    return {
        "verdict": verdict,
        "basis_refs": basis or [],
        "dependency_refs": ["engine:expr@1", "file:policy@r1"],
        "unknowns": unknowns or [],
        "next_actions": [],
    }


def _register_evidence(runtime, ref="ev:1"):
    """Persist a real evidence object so ``auto`` has a resolvable basis."""

    runtime.versions.save("evidence", ref, {"note": "test evidence fixture"})


def test_assess_decidability_two_phase_and_downgrade(runtime, ctx):
    first = call(
        "assess_automatic_decidability",
        {"requirement_ref": "rule:1@r1", "statement": "check amount", "tools": ["expr"]},
        ctx,
        runtime,
    )
    assert first.status.value == "needs_input"
    assert first.issues[0].inference_request["kind"] == "decidability"

    downgraded = call(
        "assess_automatic_decidability",
        {
            "requirement_ref": "rule:1@r1",
            "statement": "check amount",
            "proposal": decidability_proposal("auto", []),
        },
        ctx,
        runtime,
    )
    assert downgraded.status.value == "partial"
    assert downgraded.data.verdict.value == "needs_evidence"
    assert downgraded.issues[0].code == "da03.auto_without_basis"

    _register_evidence(runtime)
    auto = call(
        "assess_automatic_decidability",
        {
            "requirement_ref": "rule:1@r1",
            "statement": "check amount",
            "proposal": decidability_proposal("auto", ["ev:1"]),
        },
        ctx,
        runtime,
    )
    assert auto.status.value == "ok"
    assert auto.data.verdict.value == "auto"


def test_auto_with_unknowns_downgrades(runtime, ctx):
    _register_evidence(runtime)
    result = call(
        "assess_automatic_decidability",
        {
            "requirement_ref": "rule:1@r1",
            "statement": "check amount",
            "proposal": decidability_proposal("auto", ["ev:1"], ["amount may be stale"]),
        },
        ctx,
        runtime,
    )
    assert result.status.value == "partial"
    assert result.data.verdict.value == "needs_evidence"
    assert result.issues[0].code == "da03.auto_with_unknowns"


def test_decidability_requires_an_explicit_revision(runtime, ctx):
    result = call(
        "assess_automatic_decidability",
        {
            "requirement_ref": "rule:1",
            "statement": "check amount",
            "proposal": decidability_proposal("auto", ["ev:1"]),
        },
        ctx,
        runtime,
    )
    assert result.status.value == "needs_input"
    assert result.issues[0].code == "da03.requirement_revision_required"


def assessment(verdict, unknowns=None):
    return {
        "assessment_id": "asmt:1",
        "target_ref": "rule:1@r1",
        "verdict": verdict,
        "basis_refs": [],
        "dependency_refs": ["engine:expr@1"],
        "unknowns": unknowns or [],
        "next_actions": [],
    }


def test_gap_plan_and_coverage(runtime, ctx):
    gaps = call(
        "identify_evidence_or_human_gaps",
        {
            "assessment": assessment("needs_evidence", ["missing amount"]),
            "missing_materials": ["invoice"],
        },
        ctx,
        runtime,
    )
    assert gaps.status.value == "ok"
    assert {gap.kind for gap in gaps.data.gaps} == {"evidence", "data"}
    assert "collect_evidence" in gaps.data.routes

    human = call(
        "identify_evidence_or_human_gaps",
        {"assessment": assessment("needs_human")},
        ctx,
        runtime,
    )
    assert human.data.gaps[0].kind == "human"

    coverage = call(
        "mark_automation_coverage",
        {
            "requirements": [
                {"requirement_id": "r1", "assessment": assessment("auto")},
                {"requirement_id": "r2", "assessment": assessment("needs_evidence")},
                {"requirement_id": "r3", "assessment": assessment("needs_human")},
            ]
        },
        ctx,
        runtime,
    )
    assert coverage.status.value == "ok"
    assert coverage.data.total == 3
    assert (coverage.data.covered, coverage.data.needs_evidence, coverage.data.human) == (1, 1, 1)


def test_decidability_cache_invalidation(runtime, ctx):
    prior = assessment("auto")
    hit = call(
        "resolve_decidability_cache",
        {
            "prior": prior,
            "current_dependencies": ["engine:expr@1"],
        },
        ctx,
        runtime,
    )
    assert hit.data.hit is True

    miss = call(
        "resolve_decidability_cache",
        {
            "prior": prior,
            "current_dependencies": ["engine:expr@2"],
        },
        ctx,
        runtime,
    )
    assert miss.data.hit is False
    assert miss.data.changed_dependencies

    conservative = call(
        "resolve_decidability_cache",
        {
            "prior": {**prior, "dependency_refs": []},
            "current_dependencies": ["engine:expr@1"],
        },
        ctx,
        runtime,
    )
    assert conservative.data.hit is False
    assert "conservatively invalidated" in conservative.data.reasons[0]


def test_applicability_two_phase(runtime, ctx, workspace):
    build_pdf(workspace / "scope.pdf", ["This policy covers all expense claims in CN for reimbursement."])
    parsed = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "scope.pdf")},
        ctx,
        runtime,
    )
    first = call(
        "define_rule_applicability", {"rule_ref": "rule:1"}, ctx, runtime
    )
    assert first.status.value == "needs_input"

    second = call(
        "define_rule_applicability",
        {
            "rule_ref": "rule:1",
            "document_ref": parsed.data.document,
            "sources": [document_anchor(parsed.data.document, runtime)],
            "proposal": {
                "scope_expression": "all expense claims in CN",
                "object_types": ["expense_claim"],
                "scenarios": ["reimbursement"],
            },
        },
        ctx,
        runtime,
    )
    assert second.status.value == "ok"
    assert second.data.scope_expression == "all expense claims in CN"


def preconditions(*texts):
    return [
        {"condition_id": f"c{i + 1}", "text": text}
        for i, text in enumerate(texts)
    ]


def test_preconditions_three_valued_unknown(runtime, ctx):
    first = call(
        "define_rule_preconditions", {"rule_ref": "rule:1"}, ctx, runtime
    )
    assert first.status.value == "needs_input"

    payload = {
        "rule_ref": "rule:1",
        # Unanchored conditions only conclude from caller-declared facts when
        # the caller explicitly opts in (reviewer F3).
        "declared_facts": True,
        "proposal": {
            "conditions": preconditions("in scope", "approval exists"),
            "combination": "all(c1,c2)",
        },
    }
    unknown = call("define_rule_preconditions", {**payload, "facts": {"c1": True}}, ctx, runtime)
    assert unknown.status.value == "ok"
    assert unknown.data.evaluation.verdict == "unknown"
    assert unknown.data.evaluation.missing_facts == ["c2"]

    violated = call(
        "define_rule_preconditions",
        {**payload, "facts": {"c1": True, "c2": False}},
        ctx,
        runtime,
    )
    assert violated.data.evaluation.verdict == "violated"

    satisfied = call(
        "define_rule_preconditions",
        {**payload, "facts": {"c1": True, "c2": True}},
        ctx,
        runtime,
    )
    assert satisfied.data.evaluation.verdict == "satisfied"


def test_normalize_preconditions_merges_only_proven_equivalences(runtime, ctx):
    result = call(
        "normalize_precondition_references",
        {
            "conditions": preconditions("in scope", "in scope ", "approval exists", "approval present"),
            "proven_equivalences": [["c3", "c4"]],
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    assert len(result.data.conditions) == 2
    assert result.data.mapping["c2"] == "c1"
    assert result.data.mapping["c4"] == "c3"


def test_normalize_keeps_decimal_points(runtime, ctx):
    result = call(
        "normalize_precondition_references",
        {"conditions": preconditions("amount > 1.5", "amount > 15")},
        ctx,
        runtime,
    )
    assert len(result.data.conditions) == 2
    assert result.data.mapping == {}


def test_normalize_does_not_merge_unproven_synonyms(runtime, ctx):
    result = call(
        "normalize_precondition_references",
        {"conditions": preconditions("amount > 0", "positive amount")},
        ctx,
        runtime,
    )
    assert len(result.data.conditions) == 2
    assert result.data.mapping == {}


def test_resolve_unknown_applicability_never_applies(runtime, ctx):
    unknown = {
        "assessment_id": "asmt:app",
        "target_ref": "rule:1@r1",
        "verdict": "unknown",
        "basis_refs": [],
        "dependency_refs": [],
        "unknowns": ["missing contract type"],
        "next_actions": [],
    }
    result = call(
        "resolve_unknown_applicability",
        {
            "applicability": unknown,
            "missing_evidence": ["contract type"],
            "policy": "human",
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok"
    assert result.data.verdict.value == "unknown"
    assert any("human" in action for action in result.data.next_actions)
    assert result.issues[0].code == "da03.applicability_unknown"

    illegal = call(
        "resolve_unknown_applicability",
        {"applicability": {**unknown, "verdict": "applies"}},
        ctx,
        runtime,
    )
    assert illegal.status.value == "failed"
    assert illegal.issues[0].code == "invalid_input"


def _rule_document(runtime, ctx, workspace):
    build_pdf(
        workspace / "rules.pdf",
        [
            "1. Scope",
            "Claims above 5000 CNY require department head approval.",
            "2. Exception",
            "Reimbursements below 100 CNY are exempt.",
        ],
    )
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "rules.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    page_text = runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]

    def anchor(needle: str) -> dict:
        start = page_text.index(needle)
        return {
            "source_ref": document.original_ref.id,
            "source_revision": document.original_ref.revision,
            "selector": {
                "kind": "pdf_text_span",
                "page": 1,
                "char_start": start,
                "char_end": start + len(needle),
            },
        }

    return document, page_text, anchor


def test_rule_definition_drops_exception_not_supported_by_its_anchor(
    runtime, ctx, workspace
):
    document, page_text, anchor = _rule_document(runtime, ctx, workspace)
    clause = "Claims above 5000 CNY require department head approval."
    exception = "Reimbursements below 100 CNY are exempt."
    valid = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "claims above 5000 CNY",
                        "anchors": [anchor(clause)],
                    }
                ],
                "combination": "all(c1)",
                "exceptions": [{"text": exception, "anchors": [anchor(exception)]}],
            },
        },
        ctx,
        runtime,
    )
    assert valid.status.value == "ok", valid.issues
    assert len(valid.data.draft.definition.exceptions) == 1

    fabricated = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "claims above 5000 CNY",
                        "anchors": [anchor(clause)],
                    }
                ],
                "combination": "all(c1)",
                # The anchor is real, but it is the scope clause, not this text.
                "exceptions": [
                    {"text": "Weather must be sunny on Mars", "anchors": [anchor(clause)]}
                ],
            },
        },
        ctx,
        runtime,
    )
    assert fabricated.status.value == "partial"
    assert any(
        issue.code == "da03.unanchored_exception" for issue in fabricated.issues
    )
    assert fabricated.data.draft.definition.exceptions == []


def test_rule_definition_rejects_a_source_anchor_that_does_not_resolve(
    runtime, ctx, workspace
):
    document, _, anchor = _rule_document(runtime, ctx, workspace)
    clause = "Claims above 5000 CNY require department head approval."
    fabricated_source = {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "text_span",
            "unit_ref": "sha256:" + "0" * 64,
            "char_start": 0,
            "char_end": 4,
        },
    }
    result = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "sources": [fabricated_source],
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "claims above 5000 CNY",
                        "anchors": [anchor(clause)],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "partial"
    assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)
    definition_sources = result.data.draft.sources
    assert len(definition_sources) == 1


def test_rule_conditions_reject_contradictions_and_expansions(runtime, ctx, workspace):
    document, _, anchor = _rule_document(runtime, ctx, workspace)
    clause = "Claims above 5000 CNY require department head approval."
    contradicted = [
        "Claims above 5000 CNY do not require department head approval.",
        "Claims above 5000 CNY require no approval at all.",
        "All claims require approval.",
        "Claims above 5000 CNY require department head approval or CFO sign-off.",
    ]
    for index, text in enumerate(contradicted):
        result = call(
            "define_business_rules",
            {
                "statement": "approval threshold",
                "document_ref": document,
                "proposal": {
                    "conditions": [
                        {
                            "condition_id": f"c{index}",
                            "text": text,
                            "anchors": [anchor(clause)],
                        }
                    ],
                    "combination": f"all(c{index})",
                },
            },
            ctx,
            runtime,
        )
        codes = {issue.code for issue in result.issues}
        assert result.status.value == "needs_input", text
        assert result.data is None, text
        assert "da02.anchor_value_mismatch" in codes, (text, codes)
        assert "da03.unanchored_condition" in codes, (text, codes)

    positive = call(
        "define_business_rules",
        {
            "statement": "approval threshold",
            "document_ref": document,
            "proposal": {
                "conditions": [
                    {
                        "condition_id": "c1",
                        "text": "claims above 5000 CNY",
                        "anchors": [anchor(clause)],
                    }
                ],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert positive.status.value == "ok", positive.issues


def test_precondition_draft_ref_can_be_read_back(runtime, ctx):
    result = call(
        "define_rule_preconditions",
        {
            "rule_ref": "rule:pre-1",
            "declared_facts": True,
            "proposal": {
                "conditions": [{"condition_id": "c1", "text": "in scope"}],
                "combination": "all(c1)",
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "ok", result.issues
    draft_ref = result.data.draft_ref
    assert draft_ref is not None
    assert draft_ref.id.startswith("rule:pre-1:")
    stored = runtime.versions.get("preconditions", draft_ref.id, draft_ref.revision)
    assert stored is not None
    assert stored["rule_ref"] == "rule:pre-1"
    assert stored["conditions"][0]["condition_id"] == "c1"
