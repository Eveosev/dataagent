"""DA03.15 decidability assessment, gaps, coverage and dependency-aware cache."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import (
    Assessment,
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    Issue,
    Severity,
    VersionedRef,
)

from dataagent_data.contracts.layer import CoverageItem, CoverageMap, Gap, GapPlan
from dataagent_data import helpers
from dataagent_runtime.errors import invalid_input
from dataagent_data.registry import operation


class DecidabilityVerdict(StrEnum):
    auto = "auto"
    needs_evidence = "needs_evidence"
    needs_human = "needs_human"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DecidabilityProposal(_Model):
    verdict: DecidabilityVerdict
    basis_refs: list[str] = Field(default_factory=list)
    dependency_refs: list[VersionedRef] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


def _requirement_target_ref(requirement_ref: str, ctx: CallContext) -> VersionedRef | None:
    """Validate the requirement reference before it reaches the handler body.

    A malformed ``requirement_ref`` / ``expected_revision`` is caller input,
    so it must surface as ``invalid_input`` rather than falling through to
    ``execution_unknown`` (06 §14 item 5). ``None`` means the reference has no
    revision and no revision was supplied: the caller must supply one.
    """

    if not requirement_ref.strip():
        raise invalid_input(
            "requirement_ref must not be blank", target="requirement_ref"
        )
    if ctx.expected_revision is not None:
        revision = ctx.expected_revision
        if not revision or any(ch.isspace() for ch in revision):
            raise invalid_input(
                "context.expected_revision must be a non-empty revision without whitespace",
                target="context.expected_revision",
            )
    if "@" in requirement_ref:
        try:
            return VersionedRef.model_validate(requirement_ref)
        except ValueError as exc:
            raise invalid_input(
                f"requirement_ref must be '<id>@<revision>' without whitespace: {exc}",
                target="requirement_ref",
            ) from exc
    if ctx.expected_revision is None:
        return None
    if any(ch.isspace() for ch in requirement_ref):
        raise invalid_input(
            "requirement_ref must not contain whitespace", target="requirement_ref"
        )
    return VersionedRef(id=requirement_ref, revision=ctx.expected_revision)


class AssessDecidabilityInput(_Model):
    requirement_ref: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    available_data: list[VersionedRef] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    target_quality: str | None = None
    proposal: DecidabilityProposal | None = None


def _unverifiable_basis_refs(runtime, basis_refs: list[str]) -> list[str]:
    """Basis refs that name nothing this runtime can produce.

    A resolvable ref is either a persisted versioned object (matched by full
    ``object_id`` or ``<object_id>@<revision>``) or a content-addressed blob
    (``sha256:<64 hex>``). Anything else — including lookalike ids such as
    ``evidence:0000000000000000`` — is unverifiable, and an ``auto`` verdict
    resting on it must be downgraded rather than persisted (tester r17 R4).
    """

    unverifiable: list[str] = []
    for ref in basis_refs:
        if not ref.strip():
            unverifiable.append(ref)
            continue
        if runtime.content.exists(ref):
            continue
        if not runtime.versions.ref_exists(ref):
            unverifiable.append(ref)
    return unverifiable


@operation(
    "DA03.15.1",
    input_model=AssessDecidabilityInput,
    output_model=Assessment[DecidabilityVerdict],
    writes=True,
    description="自动判断能力评估（两段式）",
    idempotent=False,
)
def assess_automatic_decidability(
    data: AssessDecidabilityInput, ctx: CallContext, runtime
) -> CapabilityResult[Assessment[DecidabilityVerdict]]:
    # Caller input is validated even for the first (inference-request) phase;
    # a malformed ref is ``invalid_input``, never ``execution_unknown``.
    target_ref = _requirement_target_ref(data.requirement_ref, ctx)
    if data.proposal is None:
        request = {
            "kind": "decidability",
            "statement": data.statement,
            "available_data": [str(ref) for ref in data.available_data],
            "tools": data.tools,
            "verdicts": [item.value for item in DecidabilityVerdict],
            "instruction": (
                "mark auto only when data and method are sufficient; otherwise needs_evidence "
                "or needs_human. Explain each gap in unknowns."
            ),
        }
        return CapabilityResult[Assessment[DecidabilityVerdict]](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da03.inference_required",
                    severity=Severity.info,
                    message="agent-provided decidability assessment is required",
                    retryable=False,
                    suggested_action="replay with a verdict and its basis",
                    inference_request=request,
                )
            ],
            completeness=helpers.complete("decidability preparation"),
        )
    proposal = data.proposal
    if target_ref is None:
        return CapabilityResult[Assessment[DecidabilityVerdict]](
            status=CapabilityStatus.needs_input,
            data=None,
            issues=[
                Issue(
                    code="da03.requirement_revision_required",
                    severity=Severity.info,
                    message=(
                        "requirement_ref has no revision and no expected_revision was "
                        "supplied; a stable requirement version is required for the cache key"
                    ),
                    retryable=False,
                    suggested_action="pass requirement_ref as '<id>@<revision>'",
                )
            ],
            completeness=helpers.complete("decidability preparation"),
        )
    verdict = proposal.verdict
    issues: list[Issue] = []
    basis_refs = list(proposal.basis_refs)
    if verdict is DecidabilityVerdict.auto and not basis_refs:
        verdict = DecidabilityVerdict.needs_evidence
        issues.append(
            Issue.standard(
                "da03.auto_without_basis",
                "auto verdict had no basis; downgraded to needs_evidence",
                severity=Severity.warning,
                suggested_action="attach the data/method evidence or keep needs_evidence",
            )
        )
    if verdict is DecidabilityVerdict.auto and basis_refs:
        # An ``auto`` verdict claims sufficiency, so every cited basis must
        # resolve to something this runtime actually produced: a persisted
        # versioned object (``<object_id>`` / ``<object_id>@<revision>``) or a
        # content-addressed blob. A ref that matches nothing is treated as
        # fabricated and never grounds ``auto`` (06 §5 step 3, §10.2; tester
        # r17 R4). Unverifiable refs are dropped so the fabricated strings are
        # not persisted as if they were evidence.
        unverifiable = _unverifiable_basis_refs(runtime, basis_refs)
        if unverifiable:
            verdict = DecidabilityVerdict.needs_evidence
            issues.append(
                Issue.standard(
                    "da03.auto_unverifiable_basis",
                    "auto verdict cited basis refs that resolve to no stored "
                    f"object or content: {', '.join(unverifiable)}; "
                    "downgraded to needs_evidence",
                    severity=Severity.warning,
                    suggested_action=(
                        "cite evidence that exists in this runtime, or keep needs_evidence"
                    ),
                )
            )
            dropped = set(unverifiable)
            basis_refs = [ref for ref in basis_refs if ref not in dropped]
    if verdict is DecidabilityVerdict.auto and proposal.unknowns:
        verdict = DecidabilityVerdict.needs_evidence
        issues.append(
            Issue.standard(
                "da03.auto_with_unknowns",
                "auto verdict carried unknowns; downgraded to needs_evidence",
                severity=Severity.warning,
                suggested_action="resolve the unknowns or keep needs_evidence",
            )
        )
    assessment = Assessment[DecidabilityVerdict](
        assessment_id=f"asmt:decidability:{uuid.uuid4().hex[:12]}",
        target_ref=target_ref,
        verdict=verdict,
        basis_refs=basis_refs,
        dependency_refs=proposal.dependency_refs or data.available_data,
        unknowns=proposal.unknowns,
        next_actions=proposal.next_actions,
    )
    runtime.versions.save(
        "decidability_assessment", assessment.assessment_id, assessment.model_dump(mode="json")
    )
    status = CapabilityStatus.partial if issues else CapabilityStatus.ok
    return CapabilityResult[Assessment[DecidabilityVerdict]](
        status=status,
        data=assessment,
        issues=issues,
        completeness=helpers.complete("decidability assessment"),
    )


class IdentifyGapsInput(_Model):
    assessment: Assessment[DecidabilityVerdict]
    missing_materials: list[str] = Field(default_factory=list)
    allowed_methods: list[str] = Field(default_factory=list)


@operation(
    "DA03.15.2",
    input_model=IdentifyGapsInput,
    output_model=GapPlan,
    description="补证与人工需求识别",
)
def identify_evidence_or_human_gaps(
    data: IdentifyGapsInput, ctx: CallContext, runtime
) -> CapabilityResult[GapPlan]:
    gaps: list[Gap] = []
    assessment = data.assessment
    requirement_id = str(assessment.target_ref)
    if assessment.verdict is DecidabilityVerdict.needs_human:
        gaps.append(
            Gap(
                requirement_id=requirement_id,
                kind="human",
                description="judgment requires human discretion",
                route="human_review",
                reason="; ".join(assessment.unknowns) or "no automatic basis",
            )
        )
    elif assessment.verdict is DecidabilityVerdict.needs_evidence:
        unknowns = assessment.unknowns or ["missing evidence"]
        for unknown in unknowns:
            gaps.append(
                Gap(
                    requirement_id=requirement_id,
                    kind="evidence",
                    description=unknown,
                    route="collect_evidence",
                    reason="decidability is needs_evidence",
                )
            )
    for material in data.missing_materials:
        gaps.append(
            Gap(
                requirement_id=requirement_id,
                kind="data",
                description=f"missing material: {material}",
                route="request_material",
                reason="material was declared missing by the caller",
            )
        )
    routes = sorted({gap.route for gap in gaps})
    plan = GapPlan(requirement_ref=requirement_id, gaps=gaps, routes=routes)
    return CapabilityResult[GapPlan](
        status=CapabilityStatus.ok,
        data=plan,
        completeness=helpers.complete("gap plan", {"gaps": len(gaps)}),
    )


class CoverageRequirement(_Model):
    requirement_id: str = Field(min_length=1)
    assessment: Assessment[DecidabilityVerdict]


class MarkCoverageInput(_Model):
    requirements: list[CoverageRequirement] = Field(min_length=1)
    allowed_scope: str | None = None


@operation(
    "DA03.15.3",
    input_model=MarkCoverageInput,
    output_model=CoverageMap,
    description="自动处理范围标注",
)
def mark_automation_coverage(
    data: MarkCoverageInput, ctx: CallContext, runtime
) -> CapabilityResult[CoverageMap]:
    items: list[CoverageItem] = []
    counts = {"auto": 0, "needs_evidence": 0, "needs_human": 0}
    for requirement in data.requirements:
        verdict = requirement.assessment.verdict
        # Conservative: anything not explicitly auto stays outside automation.
        if verdict is DecidabilityVerdict.auto:
            bucket = "auto"
        elif verdict is DecidabilityVerdict.needs_evidence:
            bucket = "needs_evidence"
        else:
            bucket = "needs_human"
        counts[bucket] += 1
        items.append(
            CoverageItem(
                requirement_id=requirement.requirement_id,
                verdict=bucket,
                reason="; ".join(requirement.assessment.unknowns),
            )
        )
    coverage = CoverageMap(
        total=len(items),
        covered=counts["auto"],
        needs_evidence=counts["needs_evidence"],
        human=counts["needs_human"],
        items=items,
    )
    return CapabilityResult[CoverageMap](
        status=CapabilityStatus.ok,
        data=coverage,
        completeness=helpers.complete(
            "requirements", {"requirements": coverage.total, "auto": coverage.covered}
        ),
    )


class CacheResolution(_Model):
    hit: bool
    changed_dependencies: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ResolveDecidabilityCacheInput(_Model):
    prior: Assessment[DecidabilityVerdict]
    current_dependencies: list[VersionedRef] = Field(min_length=1)
    previous_dependencies: list[VersionedRef] | None = None
    statement: str | None = None
    prior_statement: str | None = None
    requirement_ref: str | None = None


@operation(
    "DA03.15.4",
    input_model=ResolveDecidabilityCacheInput,
    output_model=CacheResolution,
    description="判定缓存与依赖失效",
)
def resolve_decidability_cache(
    data: ResolveDecidabilityCacheInput, ctx: CallContext, runtime
) -> CapabilityResult[CacheResolution]:
    previous = (
        data.previous_dependencies
        if data.previous_dependencies is not None
        else list(data.prior.dependency_refs)
    )
    if data.requirement_ref is not None and str(data.prior.target_ref) != data.requirement_ref:
        return CapabilityResult[CacheResolution](
            status=CapabilityStatus.ok,
            data=CacheResolution(
                hit=False,
                reasons=[
                    f"requirement version changed: {data.prior.target_ref} != {data.requirement_ref}"
                ],
            ),
            completeness=helpers.complete("cache decision"),
        )
    if (
        data.statement is not None
        and data.prior_statement is not None
        and data.statement != data.prior_statement
    ):
        return CapabilityResult[CacheResolution](
            status=CapabilityStatus.ok,
            data=CacheResolution(
                hit=False,
                reasons=["statement changed; cached assessment is not reusable"],
            ),
            completeness=helpers.complete("cache decision"),
        )
    if data.statement is not None and data.prior_statement is None:
        # The caller supplied the current statement but not the one the cached
        # assessment was made for, so equality cannot be confirmed. A hit would
        # let a changed statement reuse a stale verdict (tester r17 R4c);
        # invalidate conservatively, like the empty dependency list below.
        return CapabilityResult[CacheResolution](
            status=CapabilityStatus.ok,
            data=CacheResolution(
                hit=False,
                reasons=[
                    "prior statement not supplied; cannot confirm the cached "
                    "assessment was made for this statement"
                ],
            ),
            completeness=helpers.complete("cache decision"),
        )
    if not previous:
        return CapabilityResult[CacheResolution](
            status=CapabilityStatus.ok,
            data=CacheResolution(
                hit=False,
                reasons=["cached assessment has no dependency list; conservatively invalidated"],
            ),
            completeness=helpers.complete("cache decision"),
        )
    before = {str(ref) for ref in previous}
    after = {str(ref) for ref in data.current_dependencies}
    changed = sorted(before.symmetric_difference(after))
    if changed:
        return CapabilityResult[CacheResolution](
            status=CapabilityStatus.ok,
            data=CacheResolution(
                hit=False,
                changed_dependencies=changed,
                reasons=["dependency set changed; reassessment required"],
            ),
            completeness=helpers.complete("cache decision"),
        )
    return CapabilityResult[CacheResolution](
        status=CapabilityStatus.ok,
        data=CacheResolution(hit=True, reasons=["all dependency versions match"]),
        completeness=helpers.complete("cache decision"),
    )
