"""DA03.4.1 metric definition and DA03.4.3 business rule definition."""

from __future__ import annotations

import re
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    Aggregation,
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    DocumentRef,
    ExceptionClause,
    Issue,
    LifecycleStatus,
    Measure,
    MetricDefinition,
    MetricFilter,
    MetricTime,
    RuleCondition,
    RuleDefinition,
    SemanticDraft,
    Severity,
    SourceAnchor,
    VersionedRef,
)

from dataagent_data.preparation.documents import load_document_content
from dataagent_data import helpers
from dataagent_data.anchors import (
    AnchorResolver,
    anchor_invalid_reason,
    anchor_span_text,
    anchor_supports_text,
    ungrounded_terms,
)
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricProposal(_Model):
    measure_field: str = Field(min_length=1)
    aggregation: str = "sum"
    filters: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    time_field: str | None = None
    time_grain: str | None = None
    grain: str = Field(min_length=1)
    unit: str | None = None
    additivity: str = "additive"
    depends_on: list[VersionedRef] = Field(default_factory=list)


class DefineMetricInput(_Model):
    statement: str = Field(min_length=1)
    scope_ref: str | None = None
    document_ref: DocumentRef | None = None
    available_fields: list[str] = Field(default_factory=list)
    sources: list[SourceAnchor] = Field(default_factory=list)
    proposal: MetricProposal | None = None


class DefineMetricOutput(_Model):
    draft: SemanticDraft


# The leading token of a filter expression is the field it constrains
# ("status != 'refunded'", "状态 = '已支付'"); anything before the first
# whitespace/comparator is taken as the field name.
_FILTER_FIELD = re.compile(r"^\s*(?P<field>[^\s!=<>~]+)")
# Full predicate shape of a filter: field, comparison operator, literal value.
_FILTER_PREDICATE = re.compile(
    r"^\s*(?P<field>[^\s!=<>~]+)\s*(?P<op>!=|>=|<=|=|>|<)\s*(?P<value>.+?)\s*$"
)
# Predicates a definition source text states inline, e.g. the
# "status = 'paid'" inside "Sum amount for status = 'paid' by department.".
# The value alternatives are ordered: quoted strings first (they may contain
# commas/semicolons), then numbers with thousands separators, then a bare
# token. Quotes are folded onto their ASCII forms *before* matching (N4):
# PDF extraction renders 'paid,final' as ’paid,final’, and a regex run on
# the raw text would truncate the literal at the comma. The numeric
# alternative must end on a token boundary (reviewer r21 F2): without it
# "status = 1000USD" states only "1000", and a proposal filtering on the
# truncated constant agrees with a value the source never stated. A
# trailing '.' counts as a boundary only when no digit follows it, so the
# sentence-final "1,000." reads as 1000 while decimals stay inside the
# literal. The sign is part of the literal (F4: "-1,000" is one number, not
# a truncated "-1").
_SOURCE_PREDICATE = re.compile(
    r"(?P<field>[^\W\d_]\w*)\s*(?P<op>!=|>=|<=|=|>|<)\s*"
    r"(?P<value>'[^']*'|\"[^\"]*\"|"
    r"-?\d+(?:,\d{3})*(?:\.\d+)?(?=$|[\s,;]|\.(?!\d))"
    r"|[^\s,;]+)"
)
# Curly quotes as extracted from PDFs, folded before any tokenization.
_QUOTE_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
# Grain vocabulary that is not field-bound but still a legitimate aggregation
# grain component (a time grain without an explicit ``time_field``).
_TIME_GRAIN_TERMS = frozenset(
    {"day", "week", "month", "quarter", "year", "date", "hour"}
)


# An unquoted numeric literal, in valid thousands syntax only: optional
# sign, digits, groups of exactly three, optional decimal part. Commas are
# removed from -- and only from -- this shape (reviewer r21 F1).
_NUMERIC_LITERAL = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
# Sentence-final punctuation a bare token may carry when the predicate sits
# at the end of a source sentence ("... for amount > 1,000." or
# "... status = paid."). Quoted literals keep it: it is their content.
_SENTENCE_FINAL = ".。!?;；…?"


def _normalize_filter_value(value: str) -> str:
    """Comparable form of a filter/source literal (quotes, case, separators).

    Curly quotes are folded onto their ASCII forms because PDF text
    extraction routinely renders ``'paid'`` as ``’paid’``. A *quoted*
    literal keeps its content verbatim (reviewer r21 F1): ``'12,34'`` and
    ``'v1,2'`` are strings, their commas are part of the value, and a
    proposal filtering on ``'1234'`` / ``'v12'`` must not silently agree
    with them. Case is still folded (``'PAID'`` names the same constant as
    ``'paid'``). Commas are removed only inside an *unquoted* numeric
    literal that is valid thousands syntax (``1,000`` -> ``1000``, N4); a
    bare token merely drops sentence-final punctuation so the tokenizer
    consumes the complete literal (F2: ``1000.`` at a sentence end is still
    ``1000``).
    """

    text = value.strip().translate(_QUOTE_FOLD)
    if len(text) >= 2 and text[0] in "'\"" and text[-1] == text[0]:
        return text[1:-1].strip().lower()
    if _NUMERIC_LITERAL.fullmatch(text):
        return text.replace(",", "").lower()
    return text.rstrip(_SENTENCE_FINAL).strip().lower()


def _source_predicates(source_text: str) -> set[tuple[str, str, str]]:
    """(field, operator, value) predicates a definition source states inline."""

    folded = source_text.translate(_QUOTE_FOLD)
    return {
        (
            match.group("field").lower(),
            match.group("op"),
            _normalize_filter_value(match.group("value")),
        )
        for match in _SOURCE_PREDICATE.finditer(folded)
    }


def _filter_predicate_divergence(
    filter_text: str, source_text: str
) -> str | None:
    """Why a filter diverges from the predicates its sources state (F2).

    A field being in the bound schema does not prove every filter constant or
    operator: when a definition source states predicates on the filter's
    field, the filter may not silently swap the value ("refunded" for "paid")
    or the operator ("!=" for "="), and a filter whose syntax the symbolic
    predicate reader does not support (``status IN ('refunded')``) is an
    *unresolved* comparison, not an agreement: "cannot parse" must never be
    read as "no conflict" (N2). Sources that never constrain the field leave
    the filter to the schema check alone -- there is nothing to diverge
    from, and worded sources ("paid status") must not false-positive on the
    symbolic form.
    """

    predicate = _FILTER_PREDICATE.match(filter_text)
    field_match = _FILTER_FIELD.match(filter_text)
    field = (predicate or field_match).group("field").lower() if (predicate or field_match) else None
    if field is None:
        return None
    stated = {
        (op, value)
        for stated_field, op, value in _source_predicates(source_text)
        if stated_field == field
    }
    if not stated:
        return None
    if predicate is None:
        described = ", ".join(f"{op} {value!r}" for op, value in sorted(stated))
        return (
            f"filter {filter_text!r} on {field} is not a supported predicate "
            "form (field, comparison operator, literal); the definition "
            f"sources state: {described}"
        )
    candidate = (
        predicate.group("op"),
        _normalize_filter_value(predicate.group("value")),
    )
    if candidate not in stated:
        described = ", ".join(f"{op} {value!r}" for op, value in sorted(stated))
        return (
            f"filter {filter_text!r} diverges from the predicate(s) the "
            f"definition sources state for {field}: {described}"
        )
    return None


def _dropped_source_constraints(
    filters: list[str], source_text: str
) -> list[str]:
    """Predicates the sources state that no filter carries (N2, reviewer F3).

    Dropping every filter on a constrained field (``filters=[]``, or filters
    that only mention other fields) deletes the predicate the metric is
    defined by -- "Sum amount for status = 'paid'" silently becomes an
    all-rows sum. Coverage is per *necessary predicate*, not per field
    (reviewer r21 F3): a source that states ``amount >= 1000 and
    amount <= 5000`` defines the metric by both bounds, and a proposal that
    carries only the lower bound silently deletes the upper one. Every
    stated predicate must therefore be carried by some proposal filter; a
    filter that does not parse as a symbolic predicate contributes nothing
    here (``_filter_predicate_divergence`` already flags it explicitly).
    Fields no source constrains impose nothing.
    """

    stated = _source_predicates(source_text)
    if not stated:
        return []
    carried = set()
    for filter_text in filters:
        predicate = _FILTER_PREDICATE.match(filter_text)
        if predicate is None:
            continue
        carried.add(
            (
                predicate.group("field").lower(),
                predicate.group("op"),
                _normalize_filter_value(predicate.group("value")),
            )
        )
    return [
        (
            f"the definition sources state the constraint {field} {op} "
            f"{value!r} that the proposal drops: no filter carries it"
        )
        for field, op, value in sorted(stated - carried)
    ]


@operation(
    "DA03.4.1",
    writes=True,
    input_model=DefineMetricInput,
    output_model=DefineMetricOutput,
    description="指标公式定义（两段式）",
    idempotent=False,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def define_metric_formula(
    data: DefineMetricInput, ctx: CallContext, runtime
) -> CapabilityResult[DefineMetricOutput]:
    if data.proposal is None:
        request = {
            "kind": "metric_definition",
            "statement": data.statement,
            "available_fields": data.available_fields,
            "aggregations": [item.value for item in Aggregation],
            "additivity": ["additive", "semi_additive", "non_additive"],
            "instruction": (
                "Bind one measure field, aggregation, filters, grain and unit. "
                "Leave depends_on empty when the base metric is unknown."
            ),
        }
        return CapabilityResult[DefineMetricOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da03.inference_required",
                    severity=Severity.info,
                    message="agent-provided metric definition is required",
                    retryable=False,
                    suggested_action="replay with a structured proposal",
                    inference_request=request,
                )
            ],
            completeness=helpers.complete("metric definition preparation"),
        )
    if not data.sources:
        return CapabilityResult[DefineMetricOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da03.metric_source_required",
                    severity=Severity.info,
                    message="a metric draft needs at least one definition source",
                    retryable=False,
                    suggested_action="attach the clause, report or口径说明 as SourceAnchor",
                )
            ],
            completeness=helpers.complete("metric definition preparation"),
        )
    proposal = data.proposal
    # W0 §1.2: the sources' file may have registered extracted tables, whose
    # columns define the name -> field_id identity map. Both identities are
    # acceptable citations; the draft is canonicalized to field_id below.
    field_map = helpers.file_field_map(runtime, data.sources)
    field_ids = set(field_map.values())
    accepted_fields = set(data.available_fields) | field_ids
    if data.available_fields and proposal.measure_field not in accepted_fields:
        raise invalid_input(f"measure field is not in the bound schema: {proposal.measure_field}")
    if (
        proposal.time_field
        and data.available_fields
        and proposal.time_field not in accepted_fields
    ):
        raise invalid_input(f"time field is not in the bound schema: {proposal.time_field}")
    try:
        aggregation = Aggregation(proposal.aggregation)
    except ValueError as exc:
        raise invalid_input(f"unknown aggregation: {proposal.aggregation}") from exc
    if proposal.additivity not in {"additive", "semi_additive", "non_additive"}:
        raise invalid_input(f"unknown additivity: {proposal.additivity}")
    content = (
        load_document_content(runtime, data.document_ref) if data.document_ref else None
    )
    resolver = AnchorResolver(content, runtime=runtime)
    valid_sources: list[SourceAnchor] = []
    issues: list[Issue] = []
    for source in data.sources:
        reason = ""
        if data.document_ref is not None:
            original = data.document_ref.original_ref
            if source.source_ref != original.id:
                reason = "source_ref does not match document_ref"
            elif source.source_revision != original.revision:
                reason = "source_revision does not match document_ref"
        reason = reason or anchor_invalid_reason(resolver, source)
        if reason:
            issues.append(
                Issue.standard(
                    "da02.anchor_not_found",
                    f"metric source: {reason}",
                    severity=Severity.warning,
                    suggested_action="attach a source anchor that exists in the supplied document/file",
                )
            )
            continue
        valid_sources.append(source)
    if not valid_sources:
        return CapabilityResult[DefineMetricOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=issues
            + [
                Issue(
                    code="da03.metric_source_required",
                    severity=Severity.info,
                    message="no verifiable definition source remains for the metric draft",
                    retryable=False,
                    suggested_action="attach a document_ref or a stored file with a resolvable anchor",
                )
            ],
            completeness=helpers.complete("metric definition preparation"),
        )
    # A valid definition source anchors the *existence* of the clause, not
    # the proposal's content (reviewer F4). Field-typed proposal parts are
    # bound to the schema (available_fields) and free-form parts are grounded
    # in the sources; anything unverifiable becomes an explicit ``unresolved``
    # entry instead of an "ok" draft: dimensions and filters that name fields
    # the bound schema does not have, grain terms that are neither a
    # dimension, a field nor a time grain, and a unit no source states.
    source_text = "\n".join(
        (anchor_span_text(resolver, source) or "") for source in valid_sources
    )
    unresolved: list[str] = []
    # W0 §1 field identity (tester r20 B1): ``field_map`` (computed above,
    # from the sources' registered extracted tables) canonicalizes human
    # header names to the stable ``field_id`` the extracted columns carry;
    # the draft cites field identities.

    def _canonical_field(value: str | None) -> str | None:
        if value is None:
            return None
        if value in field_ids:
            return value  # already a stable identity; never rewrite it
        return field_map.get(value, value)

    canonical_measure = _canonical_field(proposal.measure_field)
    canonical_time = _canonical_field(proposal.time_field)
    canonical_dimensions = [
        _canonical_field(dimension) or dimension for dimension in proposal.dimensions
    ]
    canonical_filters: list[MetricFilter] = []
    for filter_text in proposal.filters:
        referenced: list[str] = []
        field_match = _FILTER_FIELD.match(filter_text)
        if field_match:
            referenced_field = _canonical_field(field_match.group("field"))
            if referenced_field in field_ids:
                referenced = [referenced_field]
        canonical_filters.append(MetricFilter(text=filter_text, referenced_fields=referenced))
    # The source-consistency checks below run whether or not a bound schema
    # was supplied: omitting the optional ``available_fields`` must not
    # silently disable them (N1). Only the field-existence checks are
    # conditional, because without a schema there is nothing to check
    # existence against. Resolvable header names count as bound: the
    # extracted tables of the sources' own file are a schema the caller
    # already committed to.
    bound = set(data.available_fields) | set(field_map)
    if bound:
        for dimension in proposal.dimensions:
            if dimension not in bound:
                unresolved.append(
                    f"dimension field is not in the bound schema: {dimension}"
                )
    for filter_text in proposal.filters:
        field_match = _FILTER_FIELD.match(filter_text)
        if (
            field_match
            and bound
            and field_match.group("field") not in bound
        ):
            unresolved.append(
                f"filter field is not in the bound schema: {field_match.group('field')}"
            )
            continue
        divergence = _filter_predicate_divergence(filter_text, source_text)
        if divergence is not None:
            unresolved.append(divergence)
    unresolved.extend(_dropped_source_constraints(proposal.filters, source_text))
    allowed_grain_terms = (
        set(proposal.dimensions)
        | set(data.available_fields)
        | set(canonical_dimensions)
        | ({proposal.time_grain} if proposal.time_grain else set())
        | set(_TIME_GRAIN_TERMS)
    )
    for part in re.split(r"\s+[x×]\s+", proposal.grain):
        for term in re.findall(r"[^\W_]+", part.lower()):
            if term not in allowed_grain_terms:
                unresolved.append(
                    f"grain term is not a bound dimension, field or time grain: {term}"
                )
    if proposal.unit:
        missing_unit = ungrounded_terms(proposal.unit, source_text)
        if missing_unit:
            unresolved.append(
                f"unit {proposal.unit!r} is not grounded in the definition "
                f"sources: {', '.join(missing_unit)}"
            )
    issues.extend(
        Issue.standard(
            "da03.metric_unresolved",
            entry,
            severity=Severity.warning,
            suggested_action=(
                "bind the field to the schema, or ground it in the definition "
                "source before relying on the draft"
            ),
        )
        for entry in unresolved
    )
    definition = MetricDefinition(
        statement=data.statement,
        measure=Measure(field_ref=canonical_measure or proposal.measure_field, aggregation=aggregation),
        filters=canonical_filters,
        dimensions=canonical_dimensions,
        time=(
            MetricTime(time_field=canonical_time or proposal.time_field, grain=proposal.time_grain)
            if proposal.time_field
            else None
        ),
        unit=proposal.unit,
        grain=proposal.grain,
        additivity=proposal.additivity,  # type: ignore[arg-type]
        depends_on=proposal.depends_on,
    )
    draft = SemanticDraft(
        draft_id=f"draft:metric:{uuid.uuid4().hex[:12]}",
        revision="r1",
        kind="metric",
        definition=definition,
        scope_ref=data.scope_ref or ctx.scope_ref,
        sources=valid_sources,
        status=LifecycleStatus.draft,
        unresolved=unresolved,
    )
    runtime.versions.save("semantic_draft", draft.draft_id, draft.model_dump(mode="json"))
    return CapabilityResult[DefineMetricOutput](
        status=CapabilityStatus.partial if (issues or unresolved) else CapabilityStatus.ok,
        data=DefineMetricOutput(draft=draft),
        issues=issues,
        completeness=helpers.complete("metric definition", {"filters": len(definition.filters)}),
    )


class RuleConditionProposal(_Model):
    condition_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    referenced_fields: list[str] = Field(default_factory=list)
    anchors: list[SourceAnchor] = Field(default_factory=list)


class RuleExceptionProposal(_Model):
    text: str = Field(min_length=1)
    anchors: list[SourceAnchor] = Field(default_factory=list)


class RuleProposal(_Model):
    conditions: list[RuleConditionProposal] = Field(min_length=1)
    combination: str = "all"
    exceptions: list[RuleExceptionProposal] = Field(default_factory=list)


class DefineBusinessRulesInput(_Model):
    statement: str = Field(min_length=1)
    document_ref: DocumentRef | None = None
    scope_ref: str | None = None
    sources: list[SourceAnchor] = Field(default_factory=list)
    proposal: RuleProposal | None = None


class DefineBusinessRulesOutput(_Model):
    draft: SemanticDraft


# Fixed inference-context budget for DA03.4.3's first phase. The limits keep
# the request small, but they must be visible to the caller: silently showing
# pages 1-5 of a 7-page policy makes later clauses invisible to the agent.
_RULE_PREP_PAGE_LIMIT = 5
_RULE_PREP_CLAUSE_LIMIT = 40
_RULE_PREP_TEXT_LIMIT = 300


def _rule_prep_clauses(
    content, source_ref: str, source_revision: str
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    """Collect clause previews plus the reasons the context is truncated."""

    clauses: list[dict[str, Any]] = []
    truncated_text = False
    for page in content.pages[:_RULE_PREP_PAGE_LIMIT]:
        cursor = 0
        for line in page.text.splitlines(keepends=True):
            line_start = cursor
            cursor += len(line)
            text = line.strip()
            if len(text) < 6:
                continue
            if len(text) > _RULE_PREP_TEXT_LIMIT:
                truncated_text = True
            offset = page.text.find(text, line_start)
            if offset < 0:  # stripped text can only start at/after line_start
                offset = line_start
            clauses.append(
                {
                    "page": page.page,
                    "text": text[:_RULE_PREP_TEXT_LIMIT],
                    "anchor": helpers.make_anchor(
                        source_ref=source_ref,
                        source_revision=source_revision,
                        page=page.page,
                        char_start=offset,
                        char_end=min(len(page.text), offset + len(text)),
                    ).model_dump(mode="json"),
                }
            )
            if len(clauses) >= _RULE_PREP_CLAUSE_LIMIT:
                break
        if len(clauses) >= _RULE_PREP_CLAUSE_LIMIT:
            break
    reasons: list[str] = []
    if len(content.pages) > _RULE_PREP_PAGE_LIMIT:
        reasons.append(
            f"{len(content.pages)} pages available, only the first "
            f"{_RULE_PREP_PAGE_LIMIT} were read"
        )
    if len(clauses) >= _RULE_PREP_CLAUSE_LIMIT:
        reasons.append(f"clause list capped at {_RULE_PREP_CLAUSE_LIMIT}")
    if truncated_text:
        reasons.append(
            f"clause text capped at {_RULE_PREP_TEXT_LIMIT} characters"
        )
    observed = {
        "pages": len(content.pages),
        "pages_included": min(len(content.pages), _RULE_PREP_PAGE_LIMIT),
        "clauses": len(clauses),
        "clauses_limit": _RULE_PREP_CLAUSE_LIMIT,
    }
    return clauses, reasons, observed


@operation(
    "DA03.4.3",
    writes=True,
    input_model=DefineBusinessRulesInput,
    output_model=DefineBusinessRulesOutput,
    description="业务规则定义（两段式）",
    idempotent=False,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def define_business_rules(
    data: DefineBusinessRulesInput, ctx: CallContext, runtime
) -> CapabilityResult[DefineBusinessRulesOutput]:
    content = load_document_content(runtime, data.document_ref) if data.document_ref else None
    if data.proposal is None:
        clauses: list[dict[str, Any]] = []
        truncation_reasons: list[str] = []
        observed: dict[str, int] | None = None
        if content is not None and data.document_ref is not None:
            clauses, truncation_reasons, observed = _rule_prep_clauses(
                content,
                data.document_ref.original_ref.id,
                data.document_ref.original_ref.revision,
            )
        request = {
            "kind": "business_rules",
            "statement": data.statement,
            "clauses": clauses,
            "instruction": (
                "Return conditions with the exact clause anchors that appear in the document. "
                "Do not create a condition without an anchor."
            ),
        }
        issues = [
            Issue(
                code="da03.inference_required",
                severity=Severity.info,
                message="agent-provided rule structure is required",
                retryable=False,
                suggested_action="replay with a structured proposal grounded in the clauses",
                inference_request=request,
            )
        ]
        if truncation_reasons:
            reason = "; ".join(truncation_reasons)
            issues.append(
                Issue(
                    code="da03.inference_scope_truncated",
                    severity=Severity.warning,
                    message=f"rule inference context is truncated: {reason}",
                    retryable=False,
                    suggested_action=(
                        "narrow document_ref to the relevant pages or split the "
                        "document so every clause is visible"
                    ),
                )
            )
        completeness = (
            helpers.truncated(
                "rule definition preparation",
                reason="; ".join(truncation_reasons),
                observed=observed,
            )
            if truncation_reasons
            else helpers.complete("rule definition preparation", observed)
        )
        return CapabilityResult[DefineBusinessRulesOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=issues,
            completeness=completeness,
        )

    proposal = data.proposal
    from dataagent_data.semantics.applicability import _parse_combination

    operator, ids = _parse_combination(proposal.combination)
    if operator == "not" and len(ids) != 1:
        raise invalid_input("not(...) requires exactly one condition id")
    if ids:
        unknown = set(ids) - {condition.condition_id for condition in proposal.conditions}
        if unknown:
            raise invalid_input(
                f"combination references unknown conditions: {sorted(unknown)}"
            )
    valid_conditions: list[RuleCondition] = []
    issues: list[Issue] = []
    source_anchors: list[SourceAnchor] = []
    resolver = AnchorResolver(content, runtime=runtime)

    def anchor_reason(anchor: SourceAnchor) -> str:
        if data.document_ref is not None:
            original = data.document_ref.original_ref
            if anchor.source_ref != original.id:
                return "anchor source_ref does not match the document"
            if anchor.source_revision != original.revision:
                return "anchor source_revision does not match the document revision"
        return anchor_invalid_reason(resolver, anchor)

    for anchor in data.sources:
        reason = anchor_reason(anchor)
        if reason:
            issues.append(
                Issue.standard(
                    "da02.anchor_not_found",
                    f"definition source: {reason}",
                    severity=Severity.warning,
                    suggested_action="attach a source anchor that exists in the document",
                )
            )
            continue
        source_anchors.append(anchor)

    for condition in proposal.conditions:
        existing: list[SourceAnchor] = []
        for anchor in condition.anchors:
            reason = anchor_reason(anchor)
            if reason:
                issues.append(
                    Issue(
                        code="da02.anchor_not_found",
                        severity=Severity.warning,
                        message=f"condition {condition.condition_id}: {reason}",
                        target=condition.condition_id,
                        retryable=False,
                        suggested_action="re-anchor the condition or drop it",
                    )
                )
                continue
            existing.append(anchor)
        if not existing:
            issues.append(
                Issue(
                    code="da03.unanchored_condition",
                    severity=Severity.warning,
                    message=f"condition {condition.condition_id} has no valid anchor; dropped",
                    target=condition.condition_id,
                    retryable=False,
                    suggested_action="supply the clause text and a valid anchor",
                )
            )
            continue
        # Existing anchors are not enough: the anchored clause must actually
        # support the condition text (06 §14 item 1).
        grounded: list[SourceAnchor] = []
        for anchor in existing:
            mismatch = anchor_supports_text(resolver, anchor, condition.text)
            if mismatch:
                issues.append(
                    Issue(
                        code="da02.anchor_value_mismatch",
                        severity=Severity.warning,
                        message=f"condition {condition.condition_id}: {mismatch}",
                        target=condition.condition_id,
                        retryable=False,
                        suggested_action="quote the clause text in the condition or re-anchor it",
                    )
                )
                continue
            grounded.append(anchor)
        if not grounded:
            issues.append(
                Issue(
                    code="da03.unanchored_condition",
                    severity=Severity.warning,
                    message=(
                        f"condition {condition.condition_id} is not supported by any "
                        "of its anchors; dropped"
                    ),
                    target=condition.condition_id,
                    retryable=False,
                    suggested_action="quote the clause text in the condition or supply its anchor",
                )
            )
            continue
        source_anchors.extend(grounded)
        valid_conditions.append(
            RuleCondition(
                condition_id=condition.condition_id,
                text=condition.text,
                referenced_fields=condition.referenced_fields,
                anchors=grounded,
            )
        )
    if not valid_conditions or not source_anchors:
        return CapabilityResult[DefineBusinessRulesOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=issues
            + [
                Issue(
                    code="da03.rule_source_required",
                    severity=Severity.info,
                    message="no grounded condition remains for the rule draft",
                    retryable=False,
                    suggested_action="provide at least one anchored condition",
                )
            ],
            completeness=helpers.complete("rule definition preparation"),
        )
    # Deduplicate sources while preserving order.
    unique_sources = list({(a.source_ref, a.source_revision, str(a.selector)): a for a in source_anchors}.values())
    exceptions: list[ExceptionClause] = []
    for item in proposal.exceptions:
        valid = [
            anchor
            for anchor in item.anchors
            if not anchor_reason(anchor)
            and not anchor_supports_text(resolver, anchor, item.text)
        ]
        if not valid:
            issues.append(
                Issue.standard(
                    "da03.unanchored_exception",
                    f"exception has no anchor supporting its text; dropped: {item.text[:80]}",
                    severity=Severity.warning,
                    suggested_action="supply the clause anchor for the exception",
                )
            )
            continue
        exceptions.append(ExceptionClause(text=item.text, anchors=valid))
    try:
        definition = RuleDefinition(
            statement=data.statement,
            conditions=valid_conditions,
            combination=proposal.combination,
            exceptions=exceptions,
        )
    except ValueError as exc:
        raise invalid_input(
            f"invalid proposal: {exc}", target="proposal.combination"
        ) from exc
    draft = SemanticDraft(
        draft_id=f"draft:rule:{uuid.uuid4().hex[:12]}",
        revision="r1",
        kind="rule",
        definition=definition,
        scope_ref=data.scope_ref or ctx.scope_ref,
        sources=unique_sources,
        status=LifecycleStatus.draft,
        unresolved=[],
    )
    runtime.versions.save("semantic_draft", draft.draft_id, draft.model_dump(mode="json"))
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[DefineBusinessRulesOutput](
        status=status,
        data=DefineBusinessRulesOutput(draft=draft),
        issues=issues,
        completeness=helpers.complete(
            "rule conditions", {"conditions": len(valid_conditions), "dropped": len(proposal.conditions) - len(valid_conditions)}
        ),
    )
