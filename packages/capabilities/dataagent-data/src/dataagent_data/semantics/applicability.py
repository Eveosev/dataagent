"""DA03.16 applicability, preconditions, normalization and UNKNOWN handling."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    Assessment,
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    DocumentRef,
    Issue,
    Severity,
    SourceAnchor,
    VersionedRef,
)

from dataagent_data.contracts.layer import ApplicabilityDraft
from dataagent_data.preparation.documents import load_document_content
from dataagent_data import helpers
from dataagent_data.anchors import (
    AnchorResolver,
    anchor_invalid_reason,
    anchor_span_text,
    anchor_supports_text,
    semantic_divergence,
    ungrounded_terms,
)
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation


class ApplicabilityVerdict(StrEnum):
    applies = "applies"
    not_applies = "not_applies"
    unknown = "unknown"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApplicabilityProposal(_Model):
    scope_expression: str = Field(min_length=1)
    object_types: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class DefineApplicabilityInput(_Model):
    rule_ref: str = Field(min_length=1)
    document_ref: DocumentRef | None = None
    object_types: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    sources: list[SourceAnchor] = Field(default_factory=list)
    proposal: ApplicabilityProposal | None = None


@operation(
    "DA03.16.1",
    writes=True,
    input_model=DefineApplicabilityInput,
    output_model=ApplicabilityDraft,
    description="适用范围表达（两段式）",
    idempotent=False,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def define_rule_applicability(
    data: DefineApplicabilityInput, ctx: CallContext, runtime
) -> CapabilityResult[ApplicabilityDraft]:
    if data.proposal is None:
        return CapabilityResult[ApplicabilityDraft](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da03.inference_required",
                    severity=Severity.info,
                    message="agent-provided applicability scope is required",
                    retryable=False,
                    suggested_action="replay with scope_expression and its sources",
                    inference_request={
                        "kind": "applicability",
                        "rule_ref": data.rule_ref,
                        "object_types": data.object_types,
                        "scenarios": data.scenarios,
                        "instruction": "Express who/what/when this rule covers; keep unknowns explicit.",
                    },
                )
            ],
            completeness=helpers.complete("applicability preparation"),
        )
    if not data.sources:
        return CapabilityResult[ApplicabilityDraft](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da03.source_required",
                    severity=Severity.info,
                    message="applicability draft requires a definition source",
                    retryable=False,
                    suggested_action="attach the clause or policy SourceAnchor",
                )
            ],
            completeness=helpers.complete("applicability preparation"),
        )
    proposal = data.proposal
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
                    f"applicability source: {reason}",
                    severity=Severity.warning,
                    suggested_action="attach a source anchor that exists in the supplied document/file",
                )
            )
            continue
        valid_sources.append(source)
    if not valid_sources:
        return CapabilityResult[ApplicabilityDraft](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=issues
            + [
                Issue(
                    code="da03.source_required",
                    severity=Severity.info,
                    message="no verifiable applicability source remains",
                    retryable=False,
                    suggested_action="attach a document_ref or a stored file with a resolvable anchor",
                )
            ],
            completeness=helpers.complete("applicability preparation"),
        )
    # A valid definition source anchors the *existence* of the clause, not
    # the proposal's content (reviewer F4): a scope of "All Martian spacecraft
    # in 2099" must not be saved as an "ok" draft with no unknowns just
    # because the cited source resolves. Every proposal field is checked
    # term-by-term against the union of the valid sources; anything the
    # sources do not state stays an explicit unknown.
    source_text = "\n".join(
        (anchor_span_text(resolver, source) or "") for source in valid_sources
    )
    effective_object_types = proposal.object_types or data.object_types
    effective_scenarios = proposal.scenarios or data.scenarios
    unknowns = list(proposal.unknowns)
    proposed_fields: list[tuple[str, str]] = [
        ("scope_expression", proposal.scope_expression)
    ] + [("object_type", item) for item in effective_object_types] + [
        ("scenario", item) for item in effective_scenarios
    ]
    for label, value in proposed_fields:
        missing = ungrounded_terms(value, source_text)
        if missing:
            unknowns.append(
                f"{label} not grounded in the supplied sources: {', '.join(missing)}"
            )
            issues.append(
                Issue(
                    code="da03.scope_not_grounded",
                    severity=Severity.warning,
                    message=(
                        f"{label} {value[:60]!r} states term(s) {missing} that "
                        "no valid source anchor supports"
                    ),
                    target=label,
                    retryable=False,
                    suggested_action=(
                        "quote the supporting clause, or keep the unsupported "
                        "part in unknowns"
                    ),
                )
            )
    # Term grounding alone cannot catch a scope that reverses the source's
    # deterministic structure: "not covered", "below 5000" for "above 5000",
    # "or" for "and" all keep every content term yet state the opposite
    # (reviewer F1). The scope expression is held to the same structural
    # invariants the rule path enforces on quotes; a violation stays an
    # explicit unknown instead of an "ok" draft.
    for reason in semantic_divergence(proposal.scope_expression, source_text):
        unknowns.append(
            f"scope_expression may diverge from the supplied sources: {reason}"
        )
        issues.append(
            Issue(
                code="da03.scope_semantic_divergence",
                severity=Severity.warning,
                message=(
                    f"scope_expression {proposal.scope_expression[:60]!r} {reason}"
                ),
                target="scope_expression",
                retryable=False,
                suggested_action=(
                    "restate the scope with the structure the source states, or "
                    "keep the diverging part in unknowns"
                ),
            )
        )
    draft = ApplicabilityDraft(
        draft_id=f"draft:applicability:{uuid.uuid4().hex[:12]}",
        rule_ref=data.rule_ref,
        scope_expression=proposal.scope_expression,
        object_types=effective_object_types,
        scenarios=effective_scenarios,
        sources=valid_sources,
        unknowns=unknowns,
    )
    runtime.versions.save("applicability_draft", draft.draft_id, draft.model_dump(mode="json"))
    return CapabilityResult[ApplicabilityDraft](
        status=CapabilityStatus.partial if issues else CapabilityStatus.ok,
        data=draft,
        issues=issues,
        completeness=helpers.complete("applicability scope"),
    )


class Precondition(_Model):
    condition_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    anchors: list[SourceAnchor] = Field(default_factory=list)


class PreconditionProposal(_Model):
    conditions: list[Precondition] = Field(min_length=1)
    combination: str = "all"


class PreconditionsDraft(_Model):
    rule_ref: str
    conditions: list[Precondition]
    combination: str
    logic: str = "three_valued"
    unknowns: list[str] = Field(default_factory=list)


class DefinePreconditionsInput(_Model):
    rule_ref: str = Field(min_length=1)
    document_ref: DocumentRef | None = None
    conditions: list[Precondition] = Field(default_factory=list)
    proposal: PreconditionProposal | None = None
    facts: dict[str, bool] = Field(default_factory=dict)
    # Caller-declared facts are only trusted as an explicit, auditable trust
    # decision (reviewer F3). By default a condition without a verifiable
    # anchor stays UNKNOWN no matter what ``facts`` claim: omitting the
    # document used to make ``facts`` alone conclude "satisfied".
    declared_facts: bool = False


class PreconditionEvaluation(_Model):
    verdict: Literal["satisfied", "violated", "unknown"]
    missing_facts: list[str] = Field(default_factory=list)


class DefinePreconditionsOutput(_Model):
    draft: PreconditionsDraft
    evaluation: PreconditionEvaluation | None = None
    draft_ref: VersionedRef | None = None


def _parse_combination(combination: str) -> tuple[str, list[str]]:
    import re

    match = re.fullmatch(r"\s*(all|any|not)\s*(?:\((.*)\))?\s*", combination)
    if not match:
        raise invalid_input(f"unsupported precondition combination: {combination}")
    operator = match.group(1)
    body = match.group(2) or ""
    ids = [item.strip() for item in body.split(",") if item.strip()]
    return operator, ids


def _three_valued(operator: str, values: list[bool | None]) -> bool | None:
    if operator == "not":
        value = values[0] if values else None
        return None if value is None else not value
    if operator == "all":
        if any(value is False for value in values):
            return False
        if any(value is None for value in values):
            return None
        return True
    if operator == "any":
        if any(value is True for value in values):
            return True
        if any(value is None for value in values):
            return None
        return False
    raise invalid_input(f"unsupported operator: {operator}")


@operation(
    "DA03.16.2",
    input_model=DefinePreconditionsInput,
    output_model=DefinePreconditionsOutput,
    writes=True,
    description="生效前提表达（两段式）",
    idempotent=False,
    # DA12.1 access recheck reads this field (08 §4.3, W1d).
    resource_fields=("document_ref",),
)
def define_rule_preconditions(
    data: DefinePreconditionsInput, ctx: CallContext, runtime
) -> CapabilityResult[DefinePreconditionsOutput]:
    if data.proposal is None:
        return CapabilityResult[DefinePreconditionsOutput](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da03.inference_required",
                    severity=Severity.info,
                    message="agent-provided precondition structure is required",
                    retryable=False,
                    suggested_action="replay with conditions and a three-valued combination",
                    inference_request={
                        "kind": "preconditions",
                        "rule_ref": data.rule_ref,
                        "conditions": [c.model_dump(mode="json") for c in data.conditions],
                        "operators": ["all", "any", "not"],
                        "instruction": "Missing facts must stay unknown, never false.",
                    },
                )
            ],
            completeness=helpers.complete("precondition preparation"),
        )
    proposal = data.proposal
    operator, ids = _parse_combination(proposal.combination)
    by_id = {condition.condition_id: condition for condition in proposal.conditions}
    if operator == "not" and len(ids) != 1:
        raise invalid_input("not(...) requires exactly one condition id")
    if ids:
        unknown_ids = set(ids) - set(by_id)
        if unknown_ids:
            raise invalid_input(f"combination references unknown conditions: {sorted(unknown_ids)}")
    else:
        ids = list(by_id)
    # Plan §5 step 2/3: every condition anchor must resolve in the source and
    # the anchored text must actually support the condition. A fabricated
    # precondition anchor must never be stored and then used to conclude
    # "satisfied"; the condition is kept (so the caller sees what failed) but
    # marked unresolved and forced to UNKNOWN instead of trusting the caller's
    # fact. Conditions without anchors are unresolved unless the caller makes
    # an explicit ``declared_facts`` trust decision (reviewer F3): "no
    # evidence" must not turn into "satisfied" merely because the document was
    # omitted from the request.
    content = (
        load_document_content(runtime, data.document_ref)
        if data.document_ref is not None
        else None
    )
    resolver = AnchorResolver(content, runtime=runtime)
    issues: list[Issue] = []
    unresolved: set[str] = set()
    validated: list[Precondition] = []

    def anchor_reason(anchor: SourceAnchor) -> str:
        if data.document_ref is not None:
            original = data.document_ref.original_ref
            if anchor.source_ref != original.id:
                return "anchor source_ref does not match the document"
            if anchor.source_revision != original.revision:
                return "anchor source_revision does not match the document revision"
        return anchor_invalid_reason(resolver, anchor)

    for condition in proposal.conditions:
        if not condition.anchors:
            if data.document_ref is not None or not data.declared_facts:
                unresolved.add(condition.condition_id)
                issues.append(
                    Issue(
                        code="da03.unanchored_condition",
                        severity=Severity.warning,
                        message=(
                            f"condition {condition.condition_id} has no anchor; "
                            "kept unresolved"
                        ),
                        target=condition.condition_id,
                        retryable=False,
                        suggested_action=(
                            "attach the clause text and a valid anchor, or "
                            "explicitly set declared_facts to trust caller "
                            "assertions"
                        ),
                    )
                )
            validated.append(condition)
            continue
        grounded: list[SourceAnchor] = []
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
            unresolved.add(condition.condition_id)
            issues.append(
                Issue(
                    code="da03.unanchored_condition",
                    severity=Severity.warning,
                    message=(
                        f"condition {condition.condition_id} is not supported by "
                        "any of its anchors; kept unresolved"
                    ),
                    target=condition.condition_id,
                    retryable=False,
                    suggested_action="quote the clause text in the condition or supply its anchor",
                )
            )
            validated.append(
                Precondition(
                    condition_id=condition.condition_id,
                    text=condition.text,
                    anchors=[],
                )
            )
            continue
        validated.append(
            Precondition(
                condition_id=condition.condition_id,
                text=condition.text,
                anchors=grounded,
            )
        )
    values = [None if condition_id in unresolved else data.facts.get(condition_id) for condition_id in ids]
    missing = [
        condition_id for condition_id, value in zip(ids, values) if value is None
    ]
    verdict_value = _three_valued(operator, values)
    evaluation = PreconditionEvaluation(
        verdict="unknown" if verdict_value is None else ("satisfied" if verdict_value else "violated"),
        missing_facts=missing,
    )
    draft = PreconditionsDraft(
        rule_ref=data.rule_ref,
        conditions=validated,
        combination=proposal.combination,
        unknowns=sorted(set(missing) | unresolved),
    )
    # A rule reference may be the contract's canonical ``<id>@<revision>``
    # serialization. The draft id must not embed that '@' (VersionedRef id
    # forbids it), so the identifier part is used for the generated id while
    # ``rule_ref`` keeps the caller's original reference.
    draft_id_base = data.rule_ref
    if "@" in data.rule_ref:
        try:
            draft_id_base = VersionedRef.model_validate(data.rule_ref).id
        except ValueError as exc:
            raise invalid_input(
                "rule_ref must not contain '@' unless it is '<id>@<revision>' "
                f"without whitespace: {exc}",
                target="rule_ref",
            ) from exc
    draft_id = f"{draft_id_base}:{uuid.uuid4().hex[:12]}"
    draft_revision = runtime.versions.save(
        "preconditions", draft_id, draft.model_dump(mode="json")
    )
    return CapabilityResult[DefinePreconditionsOutput](
        status=CapabilityStatus.partial if issues else CapabilityStatus.ok,
        data=DefinePreconditionsOutput(
            draft=draft,
            evaluation=evaluation,
            draft_ref=VersionedRef(id=draft_id, revision=draft_revision),
        ),
        issues=issues,
        completeness=helpers.complete("preconditions", {"conditions": len(validated)}),
    )

class NormalizePreconditionsInput(_Model):
    conditions: list[Precondition] = Field(min_length=1)
    synonyms: dict[str, str] = Field(default_factory=dict)
    proven_equivalences: list[list[str]] = Field(default_factory=list)


class NormalizedPrecondition(_Model):
    condition_id: str
    canonical_text: str
    merged_condition_ids: list[str]


class NormalizePreconditionsOutput(_Model):
    conditions: list[NormalizedPrecondition]
    mapping: dict[str, str] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)


def _normalize_condition(text: str) -> str:
    import re

    return re.sub(r"[\s，,。;；:：、（）()]", "", text).lower()


@operation(
    "DA03.16.3",
    input_model=NormalizePreconditionsInput,
    output_model=NormalizePreconditionsOutput,
    description="前置引用与去重",
)
def normalize_precondition_references(
    data: NormalizePreconditionsInput, ctx: CallContext, runtime
) -> CapabilityResult[NormalizePreconditionsOutput]:
    canonical: list[NormalizedPrecondition] = []
    mapping: dict[str, str] = {}
    conflicts: list[str] = []
    index: dict[str, NormalizedPrecondition] = {}
    by_id: dict[str, NormalizedPrecondition] = {}
    for condition in data.conditions:
        key = data.synonyms.get(condition.text, condition.text)
        key = _normalize_condition(key)
        if key in index:
            existing = index[key]
            existing.merged_condition_ids.append(condition.condition_id)
            mapping[condition.condition_id] = existing.condition_id
            by_id[condition.condition_id] = existing
            continue
        item = NormalizedPrecondition(
            condition_id=condition.condition_id,
            canonical_text=condition.text,
            merged_condition_ids=[],
        )
        index[key] = item
        by_id[condition.condition_id] = item
        canonical.append(item)
    # Merge only explicit, proven equivalences. Same words are already merged
    # above, but textual similarity alone is never used as proof.
    for left, right in data.proven_equivalences:
        left_item = by_id.get(left)
        right_item = by_id.get(right)
        if left_item is None or right_item is None or left_item is right_item:
            continue
        keep, drop = (left_item, right_item) if left_item in canonical else (right_item, left_item)
        if drop not in canonical:
            continue
        for condition_id, mapped in list(mapping.items()):
            if mapped is drop.condition_id:
                mapping[condition_id] = keep.condition_id
        keep.merged_condition_ids.append(drop.condition_id)
        keep.merged_condition_ids.extend(drop.merged_condition_ids)
        mapping[drop.condition_id] = keep.condition_id
        by_id[drop.condition_id] = keep
        canonical.remove(drop)
    # Collapse equivalence chains (c5 -> c3 -> c1) and dedupe merged ids.
    for condition_id in list(mapping):
        target = mapping[condition_id]
        seen = {condition_id}
        while target in mapping and mapping[target] != target and target not in seen:
            seen.add(target)
            target = mapping[target]
        mapping[condition_id] = target
    for item in canonical:
        item.merged_condition_ids = list(dict.fromkeys(item.merged_condition_ids))
    return CapabilityResult[NormalizePreconditionsOutput](
        status=CapabilityStatus.ok,
        data=NormalizePreconditionsOutput(
            conditions=canonical, mapping=mapping, conflicts=conflicts
        ),
        completeness=helpers.complete("preconditions", {"conditions": len(canonical)}),
    )

class ResolveUnknownApplicabilityInput(_Model):
    applicability: Assessment[ApplicabilityVerdict]
    missing_evidence: list[str] = Field(default_factory=list)
    policy: Literal["collect_evidence", "wait", "human"] = "collect_evidence"


@operation(
    "DA03.16.4",
    input_model=ResolveUnknownApplicabilityInput,
    output_model=Assessment[ApplicabilityVerdict],
    description="适用性未知处置",
)
def resolve_unknown_applicability(
    data: ResolveUnknownApplicabilityInput, ctx: CallContext, runtime
) -> CapabilityResult[Assessment[ApplicabilityVerdict]]:
    if data.applicability.verdict is not ApplicabilityVerdict.unknown:
        raise invalid_input("resolve_unknown_applicability only accepts verdict=unknown")
    if data.policy == "human":
        actions = ["route_to_human_review"]
        next_actions = ["human adjudication required; do not skip the record"]
    elif data.policy == "wait":
        actions = ["wait_for_evidence"]
        next_actions = ["hold the record until the missing evidence arrives"]
    else:
        actions = ["collect_evidence"]
        next_actions = ["collect the listed evidence and re-evaluate applicability"]
    if data.missing_evidence:
        next_actions.extend(f"missing: {item}" for item in data.missing_evidence)
    assessment = data.applicability.model_copy(
        update={
            "assessment_id": f"asmt:applicability:{uuid.uuid4().hex[:12]}",
            "unknowns": data.applicability.unknowns + data.missing_evidence,
            "next_actions": next_actions,
        }
    )
    return CapabilityResult[Assessment[ApplicabilityVerdict]](
        status=CapabilityStatus.ok,
        data=assessment,
        issues=[
            Issue.standard(
                "da03.applicability_unknown",
                "applicability remains unknown; it is not converted to applies/not_applies",
                severity=Severity.warning,
                suggested_action="; ".join(actions),
            )
        ],
        completeness=helpers.complete("unknown applicability handling"),
    )
