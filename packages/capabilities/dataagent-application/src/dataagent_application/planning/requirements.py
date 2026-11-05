"""Requirement binding, parsing, ambiguity and clarification (DA06.1.1–1.4).

All four atoms are two-phase: the first call returns ``needs_input`` with an
``inference_request``; the second call carries a ``proposal`` that is
validated deterministically against the bound metric definitions and the
table schema (07 §4.1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field as PydanticField, ValidationError

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    MetricDefinition,
    MetricFilter,
    SemanticDraft,
    Severity,
    TimeRange,
    Issue,
    VersionedRef,
)

from dataagent_application import helpers
from dataagent_application.contracts import (
    Ambiguity,
    AmbiguityKind,
    ClarificationProposal,
    ClarificationQuestion,
    ParsedFilter,
    RequirementSpec,
    TimeFilterProposal,
)
from dataagent_runtime.enforcement import egress_check
from dataagent_runtime.errors import invalid_input
from dataagent_runtime.registry import operation

AMBIGUITY_KINDS: tuple[str, ...] = (
    "metric_definition",
    "time_boundary",
    "unit_or_currency",
    "grain_dedup",
    "filter_scope",
)


class _IO(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _needs_input(
    runtime,
    request: dict[str, Any],
    decision_ref: str | None,
    *,
    code: str,
    message: str,
    suggested_action: str,
    alternatives: list[dict[str, Any]] | None = None,
    destination: dict[str, str] | None = None,
) -> CapabilityResult[Any]:
    """First-phase ``needs_input`` with the request gated on an EgressDecision.

    r40 F1: every caller-supplied model-visible key of the request is cited
    *by content address* (``helpers.caller_content_ref``), so the decision
    must cover those exact bytes — a ``req:<label>@r1`` id could never be
    minted through the governed egress path (its revision does not address
    content), and it did not bind the metric statements that travel next to
    the statement. Derived keys (``table_fields`` from the bound schema)
    are not caller free text and need no separate ref.
    """

    content_refs = [
        helpers.caller_content_ref(value)
        for key, value in request.items()
        if key in helpers.EGRESS_CONTENT_KEYS and value not in (None, [], {})
    ]
    request, gate_issues, allowed = helpers.gate_inference_request(
        runtime, request, decision_ref, content_refs=content_refs, check=egress_check,
        destination=destination,
    )
    if allowed:
        issues = [
            Issue(
                code=code,
                severity=Severity.info,
                message=message,
                retryable=False,
                suggested_action=suggested_action,
                inference_request=request,
                alternatives=alternatives or [],
            )
        ] + gate_issues
    else:
        issues = [
            issue.model_copy(update={"inference_request": request})
            for issue in gate_issues
        ] or [
            Issue(
                code="da12.egress_required",
                severity=Severity.error,
                message="egress decision denied carrying the requirement content to the model",
                retryable=False,
                inference_request=request,
            )
        ]
    return CapabilityResult[Any](status=CapabilityStatus.needs_input, data=None, issues=issues)


def _schema_fields(runtime, table_ref: Any) -> list[dict[str, Any]]:
    table = helpers.load_table(runtime, table_ref)
    return table.schema_fields()


def _field_ids(runtime, table_ref: Any) -> set[str]:
    return {f["field_id"] for f in _schema_fields(runtime, table_ref)}


def _field_identity_index(runtime, table_ref: Any) -> tuple[set[str], dict[str, str]]:
    """Bound ``(field_ids, {name: field_id})`` of one table.

    W0 §1 field identity (tester r20 B1): a bound table carries both the
    stable ``field_id`` and the human header ``name`` of every column, so a
    caller may cite either. A name that maps to several field ids, or that
    collides with another column's id, is ambiguous and is not resolved —
    the raw value then fails the field-id validation.
    """

    fields = _schema_fields(runtime, table_ref)
    field_ids = {f["field_id"] for f in fields}
    name_to_id: dict[str, str] = {}
    ambiguous: set[str] = set()
    for f in fields:
        name = f.get("name")
        field_id = f["field_id"]
        if not name or name == field_id:
            continue
        if name in name_to_id and name_to_id[name] != field_id:
            ambiguous.add(name)
        else:
            name_to_id.setdefault(name, field_id)
    for name in ambiguous:
        name_to_id.pop(name, None)
    for name in list(name_to_id):
        if name in field_ids:
            name_to_id.pop(name)  # a name that is also a column id: unsafe to rewrite
    return field_ids, name_to_id


def _metric_drafts(metrics: list[dict[str, Any]]) -> list[SemanticDraft]:
    drafts = []
    for item in metrics:
        drafts.append(SemanticDraft.model_validate(item))
    for draft in drafts:
        if draft.kind != "metric":
            raise invalid_input(
                f"metrics[] must be kind=metric SemanticDrafts, got kind={draft.kind!r}",
                target="metrics",
            )
    return drafts


# --- DA06.1.1 ----------------------------------------------------------------


class BindMetricsAndDimensionsInput(_IO):
    statement: str = PydanticField(min_length=1)
    table_ref: dict[str, Any] | None = None
    metrics: list[dict[str, Any]] = PydanticField(default_factory=list)
    proposal: dict[str, Any] | None = None
    egress_decision_ref: str | None = None
    destination: dict[str, str] | None = None


class BindMetricsAndDimensionsOutput(_IO):
    requirement: RequirementSpec


@operation(
    "DA06.1.1",
    input_model=BindMetricsAndDimensionsInput,
    output_model=BindMetricsAndDimensionsOutput,
    description="指标与维度绑定（两段式）：绑定的指标、维度必须存在于输入的 MetricDefinition 与表 schema（DA06.1.1）",
)
def bind_metrics_and_dimensions(
    data: BindMetricsAndDimensionsInput, ctx: CallContext, runtime
) -> CapabilityResult[BindMetricsAndDimensionsOutput]:
    from dataagent_contracts.core import TableRef

    drafts = _metric_drafts(data.metrics)
    known_metrics = {d.draft_id: d for d in drafts}
    field_ids: set[str] = set()
    name_to_id: dict[str, str] = {}
    if data.table_ref is not None:
        table_ref = TableRef.model_validate(data.table_ref)
        field_ids, name_to_id = _field_identity_index(runtime, table_ref)

        def _resolve_field(value: str) -> str:
            # W0 §1: a citation may be the field_id or the human header name.
            return name_to_id.get(value, value)

        for draft in drafts:
            measure_field = _resolve_field(draft.definition.measure.field_ref)
            if measure_field not in field_ids:
                raise invalid_input(
                    f"metric {draft.draft_id}: measure field {draft.definition.measure.field_ref!r} "
                    "is not in the bound table schema",
                    target="metrics",
                )
            if draft.definition.time:
                time_field = _resolve_field(draft.definition.time.time_field)
                if time_field not in field_ids:
                    raise invalid_input(
                        f"metric {draft.draft_id}: time field {draft.definition.time.time_field!r} "
                        "is not in the bound table schema",
                        target="metrics",
                    )

    if data.proposal is None:
        request = {
            "kind": "requirement_binding",
            "statement": data.statement,
            "metric_ids": sorted(known_metrics),
            "metric_statements": {d.draft_id: d.definition.statement for d in drafts},
            "table_fields": sorted(field_ids),
            "instruction": (
                "Select the metric ids and dimension field ids the requirement needs, plus "
                "the grain. Every id must come from these lists."
            ),
        }
        return _needs_input(
            runtime,
            request,
            data.egress_decision_ref,
            code="da06.inference_required",
            message="agent-provided metric/dimension binding is required",
            destination=data.destination,
            suggested_action="replay with a proposal {metric_ids, dimensions, grain}",
        )

    proposal = data.proposal
    metric_ids = proposal.get("metric_ids") or []
    dimensions = proposal.get("dimensions") or []
    grain = proposal.get("grain")
    if not metric_ids:
        raise invalid_input("proposal.metric_ids must not be empty", target="proposal.metric_ids")
    if not grain:
        raise invalid_input("proposal.grain is required (e.g. 'day', 'region')", target="proposal.grain")
    fabricated = set(metric_ids) - set(known_metrics)
    if fabricated:
        raise invalid_input(
            f"metric ids not in the bound MetricDefinitions: {sorted(fabricated)}",
            target="proposal.metric_ids",
        )
    resolved_dimensions = [name_to_id.get(dim, dim) for dim in dimensions]
    if field_ids:
        bad_dimensions = set(resolved_dimensions) - field_ids
        if bad_dimensions:
            raise invalid_input(
                f"dimensions not in the bound table schema: {sorted(bad_dimensions)}",
                target="proposal.dimensions",
            )
    bound_drafts = [draft for draft in drafts if draft.draft_id in set(metric_ids)]
    # Fixed filters of the bound metrics are part of the bound caliber (07 §4.1
    # / review §5): they must travel with the RequirementSpec into SQL
    # generation, and every referenced field must exist in the bound table.
    filters: list[MetricFilter] = []
    seen_filters: set[str] = set()
    for draft in bound_drafts:
        for item in draft.definition.filters or []:
            if item.text in seen_filters:
                continue
            seen_filters.add(item.text)
            referenced = [
                name_to_id.get(field_id, field_id)
                for field_id in item.referenced_fields
            ]
            if field_ids:
                unknown = set(referenced) - field_ids
                if unknown:
                    raise invalid_input(
                        f"metric {draft.draft_id}: fixed filter references fields outside "
                        f"the bound table schema: {sorted(unknown)}",
                        target="metrics",
                    )
            filters.append(
                MetricFilter(text=item.text, referenced_fields=referenced)
            )
    requirement = RequirementSpec(
        requirement_id=helpers.requirement_id_of(data.statement),
        statement=data.statement,
        metrics=[
            VersionedRef(id=draft.draft_id, revision=draft.revision)
            for draft in bound_drafts
        ],
        dimensions=list(resolved_dimensions),
        grain=grain,
        filters=filters,
    )
    return CapabilityResult[BindMetricsAndDimensionsOutput](
        status=CapabilityStatus.ok,
        data=BindMetricsAndDimensionsOutput(requirement=requirement),
        completeness=helpers.complete("requirement binding"),
    )


# --- DA06.1.2 ----------------------------------------------------------------


class ParseTimeAndFiltersInput(_IO):
    statement: str = PydanticField(min_length=1)
    table_ref: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    egress_decision_ref: str | None = None
    destination: dict[str, str] | None = None


class ParseTimeAndFiltersOutput(_IO):
    time_range: TimeRange | None
    filters: list[MetricFilter]
    unresolved: list[str]


@operation(
    "DA06.1.2",
    input_model=ParseTimeAndFiltersInput,
    output_model=ParseTimeAndFiltersOutput,
    description="时间与过滤解析（两段式）：时间与过滤值须能解析，字段须在表 schema 内（DA06.1.2）",
)
def parse_time_and_filters(
    data: ParseTimeAndFiltersInput, ctx: CallContext, runtime
) -> CapabilityResult[ParseTimeAndFiltersOutput]:
    from dataagent_contracts.core import TableRef

    field_ids: set[str] = set()
    if data.table_ref is not None:
        field_ids = _field_ids(runtime, TableRef.model_validate(data.table_ref))

    if data.proposal is None:
        request = {
            "kind": "time_and_filters",
            "statement": data.statement,
            "table_fields": sorted(field_ids),
            "time_semantics": "ISO-8601 with timezone; 'from' inclusive, 'to' exclusive unless stated",
            "operators": ["eq", "ne", "lt", "le", "gt", "ge", "in", "between", "like"],
            "instruction": (
                "Extract the time range and the filters the requirement implies. Values must "
                "be ISO-8601 timestamps or JSON scalars."
            ),
        }
        return _needs_input(
            runtime,
            request,
            data.egress_decision_ref,
            code="da06.inference_required",
            message="agent-provided time/filter parse is required",
            destination=data.destination,
            suggested_action="replay with a proposal {time, filters}",
        )

    try:
        parsed = TimeFilterProposal.model_validate(data.proposal)
    except ValidationError as exc:
        # A malformed proposal is caller input, never execution_unknown.
        first = exc.errors()[0]
        location = ".".join(str(p) for p in first.get("loc", ()))
        raise invalid_input(
            f"proposal does not match the time/filter shape at {location or '$'}: {first['msg']}",
            target=f"proposal.{location}".rstrip(".") if location else "proposal",
        ) from exc
    unresolved: list[str] = []
    for item in parsed.filters:
        if field_ids and item.field_id not in field_ids:
            raise invalid_input(
                f"filter field {item.field_id!r} is not in the bound table schema",
                target="proposal.filters",
            )
        for value in item.values:
            if not isinstance(value, (str, int, float, bool)):
                raise invalid_input(
                    f"filter values must be scalars, got {type(value).__name__}",
                    target="proposal.filters",
                )
    if parsed.time is not None:
        if parsed.time.from_ is not None and parsed.time.to is not None:
            if parsed.time.from_ > parsed.time.to:
                raise invalid_input(
                    "time range 'from' must not be after 'to'", target="proposal.time"
                )
        if parsed.time.from_ is None and parsed.time.to is None:
            unresolved.append("time range given without bounds")

    filters = [
        MetricFilter(
            text=f"{item.field_id} {item.operator} {item.values!r}",
            referenced_fields=[item.field_id],
        )
        for item in parsed.filters
    ]
    return CapabilityResult[ParseTimeAndFiltersOutput](
        status=CapabilityStatus.ok,
        data=ParseTimeAndFiltersOutput(
            time_range=parsed.time, filters=filters, unresolved=unresolved
        ),
        completeness=helpers.complete("time and filter parsing"),
    )


# --- DA06.1.3 ----------------------------------------------------------------


class IdentifyCalculationAmbiguitiesInput(_IO):
    statement: str = PydanticField(min_length=1)
    metrics: list[dict[str, Any]] = PydanticField(default_factory=list)
    requirement: dict[str, Any] | None = None
    proposal: dict[str, Any] | None = None
    egress_decision_ref: str | None = None
    destination: dict[str, str] | None = None


class IdentifyCalculationAmbiguitiesOutput(_IO):
    ambiguities: list[Ambiguity]


@operation(
    "DA06.1.3",
    input_model=IdentifyCalculationAmbiguitiesInput,
    output_model=IdentifyCalculationAmbiguitiesOutput,
    description="计算歧义识别（两段式）：多口径、时间边界、币种单位、去重粒度，每项给 result_impact 与 blocking（DA06.1.3）",
)
def identify_calculation_ambiguities(
    data: IdentifyCalculationAmbiguitiesInput, ctx: CallContext, runtime
) -> CapabilityResult[IdentifyCalculationAmbiguitiesOutput]:
    drafts = _metric_drafts(data.metrics)
    requirement = RequirementSpec.model_validate(data.requirement) if data.requirement else None

    if data.proposal is None:
        request = {
            "kind": "calculation_ambiguities",
            "statement": data.statement,
            "metric_statements": {d.draft_id: d.definition.statement for d in drafts},
            "metric_additivity": {d.draft_id: d.definition.additivity for d in drafts},
            "metric_units": {d.draft_id: d.definition.unit for d in drafts},
            "requirement": requirement.model_dump(mode="json") if requirement else None,
            "kinds": list(AMBIGUITY_KINDS),
            "instruction": (
                "List every ambiguity that changes the result if resolved differently "
                "(metric口径, time boundary, currency/unit, dedup grain, filter scope), each "
                "with result_impact and blocking."
            ),
        }
        return _needs_input(
            runtime,
            request,
            data.egress_decision_ref,
            code="da06.inference_required",
            message="agent-provided ambiguity list is required",
            destination=data.destination,
            suggested_action="replay with a proposal {items: [Ambiguity...]}",
        )

    items = data.proposal.get("items") or []
    if not isinstance(items, list):
        raise invalid_input("proposal.items must be a list", target="proposal.items")
    ambiguities = [Ambiguity.model_validate(item) for item in items]
    ids = [a.ambiguity_id for a in ambiguities]
    if len(set(ids)) != len(ids):
        raise invalid_input("ambiguity_id values must be unique", target="proposal.items")

    issues: list[Issue] = []
    # Deterministic backstop: signals the tool can check itself must be
    # represented in the proposal, not silently dropped.
    present_kinds = {a.kind for a in ambiguities}
    if requirement is not None and requirement.time is None and "time_boundary" not in present_kinds:
        ambiguities.append(
            Ambiguity(
                ambiguity_id="amb:auto-time-boundary",
                kind="time_boundary",
                description=(
                    "requirement carries no time bounds; different windows produce "
                    "different results"
                ),
                result_impact="row set changes with the chosen time window",
                blocking=True,
                affected=[m.id for m in requirement.metrics] or [requirement.requirement_id],
            )
        )
        issues.append(
            Issue(
                code="da06.ambiguity_added",
                severity=Severity.warning,
                message="time-boundary ambiguity added by the deterministic check (was missing)",
                retryable=False,
            )
        )
    unitless = [
        d.draft_id
        for d in drafts
        if d.definition.unit is None
        and (d.definition.measure.aggregation in {"sum", "avg"})
    ]
    if unitless and "unit_or_currency" not in present_kinds:
        issues.append(
            Issue(
                code="da06.unit_unknown",
                severity=Severity.warning,
                message=(
                    "metrics without a declared unit participate in sums/averages: "
                    f"{unitless}; unit_or_currency ambiguity was not reported"
                ),
                retryable=False,
            )
        )

    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[IdentifyCalculationAmbiguitiesOutput](
        status=status,
        data=IdentifyCalculationAmbiguitiesOutput(ambiguities=ambiguities),
        issues=issues,
        completeness=helpers.complete("ambiguity identification"),
    )


# --- DA06.1.4 ----------------------------------------------------------------


class GenerateClarificationQuestionsInput(_IO):
    requirement: dict[str, Any]
    proposal: dict[str, Any] | None = None
    egress_decision_ref: str | None = None
    destination: dict[str, str] | None = None


class GenerateClarificationQuestionsOutput(_IO):
    questions: list[ClarificationQuestion]
    assumptions: list[str]
    still_blocking: list[str]


@operation(
    "DA06.1.4",
    input_model=GenerateClarificationQuestionsInput,
    output_model=GenerateClarificationQuestionsOutput,
    description="澄清问题生成（两段式）：blocking 歧义返回 needs_input，Issue.alternatives 列候选及依据（DA06.1.4）",
)
def generate_clarification_questions(
    data: GenerateClarificationQuestionsInput, ctx: CallContext, runtime
) -> CapabilityResult[GenerateClarificationQuestionsOutput]:
    requirement = RequirementSpec.model_validate(data.requirement)
    ambiguities = requirement.ambiguities
    blocking = [a for a in ambiguities if a.blocking]

    if data.proposal is None:
        if not blocking:
            return CapabilityResult[GenerateClarificationQuestionsOutput](
                status=CapabilityStatus.ok,
                data=GenerateClarificationQuestionsOutput(
                    questions=[],
                    assumptions=[
                        f"{a.ambiguity_id}: {a.description} (assumed per proposal-free path)"
                        for a in ambiguities
                    ],
                    still_blocking=[],
                ),
                completeness=helpers.complete("clarification"),
            )
        return _needs_input(
            runtime,
            {
                "kind": "clarification_questions",
                "statement": requirement.statement,
                "blocking_ambiguities": [
                    {
                        "ambiguity_id": a.ambiguity_id,
                        "kind": a.kind,
                        "description": a.description,
                        "result_impact": a.result_impact,
                    }
                    for a in blocking
                ],
                "instruction": (
                    "Pose one clarifying question per blocking ambiguity, with the "
                    "candidate answers; free-form answers are allowed."
                ),
            },
            data.egress_decision_ref,
            code="da06.clarification_required",
            message=f"{len(blocking)} blocking ambiguity(ies) must be clarified before computing",
            suggested_action="replay with a proposal {questions, answers}; free-form answers are allowed",
            alternatives=[
                {
                    "ambiguity_id": a.ambiguity_id,
                    "kind": a.kind,
                    "description": a.description,
                    "result_impact": a.result_impact,
                }
                for a in blocking
            ],
            destination=data.destination,
        )

    parsed = ClarificationProposal.model_validate(data.proposal)
    answered = {a.get("ambiguity_id") for a in parsed.answers if isinstance(a, dict)}
    missing_question = [a.ambiguity_id for a in blocking if a.ambiguity_id not in {q.ambiguity_id for q in parsed.questions}]
    if missing_question:
        raise invalid_input(
            f"every blocking ambiguity needs a question: missing {sorted(missing_question)}",
            target="proposal.questions",
        )
    unknown_ids = {q.ambiguity_id for q in parsed.questions} - {a.ambiguity_id for a in ambiguities}
    if unknown_ids:
        raise invalid_input(
            f"questions reference unknown ambiguity ids: {sorted(unknown_ids)}",
            target="proposal.questions",
        )

    assumptions: list[str] = list(requirement.assumptions)
    still_blocking: list[str] = []
    for answer in parsed.answers:
        ambiguity_id = answer.get("ambiguity_id")
        text = answer.get("answer")
        match = next((a for a in ambiguities if a.ambiguity_id == ambiguity_id), None)
        if match is None:
            raise invalid_input(f"answer references unknown ambiguity: {ambiguity_id}")
        if not isinstance(text, str) or not text.strip():
            still_blocking.append(ambiguity_id)
            continue
        assumptions.append(f"{ambiguity_id} (kind={match.kind}): {text}")
    for item in blocking:
        if item.ambiguity_id not in answered and item.ambiguity_id not in still_blocking:
            still_blocking.append(item.ambiguity_id)

    if still_blocking:
        # A blocking ambiguity that is not resolved keeps the requirement out
        # of computation (B7): never return ``ok`` with blockers outstanding.
        return CapabilityResult[GenerateClarificationQuestionsOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da06.clarification_required",
                    severity=Severity.info,
                    message=(
                        "blocking ambiguities are still unresolved: "
                        f"{sorted(still_blocking)}"
                    ),
                    retryable=False,
                    suggested_action="replay with non-blank answers for every blocking ambiguity",
                )
            ],
            completeness=helpers.complete("clarification"),
        )

    return CapabilityResult[GenerateClarificationQuestionsOutput](
        status=CapabilityStatus.ok,
        data=GenerateClarificationQuestionsOutput(
            questions=parsed.questions,
            assumptions=assumptions,
            still_blocking=still_blocking,
        ),
        completeness=helpers.complete("clarification"),
    )
