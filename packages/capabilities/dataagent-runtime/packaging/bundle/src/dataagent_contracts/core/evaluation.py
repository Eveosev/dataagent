"""Evaluation and acceptance contracts (05-contracts.md §3.3.6)."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from ._base import ExtModel  # noqa: E402

from .refs import VersionedRef
from .vocab import LifecycleStatus, SplitRole, Verdict

__all__ = [
    "CriteriaRef",
    "EvaluationSetRef",
    "CaseResult",
    "QualityMetric",
    "Coverage",
    "UnknownRate",
    "HumanEffort",
    "Cost",
    "Latency",
    "Stratum",
    "MetricBundle",
    "AcceptanceReport",
    "validate_acceptance_report",
]


_Model = ExtModel


class CriteriaRef(_Model):
    id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    status: LifecycleStatus
    owner_ref: str = Field(min_length=1)
    confirmation_ref: str | None = None
    expected_outputs: str = Field(min_length=1)
    evidence_requirements: list[str] = Field(default_factory=list)
    unknown_policy: Literal["count_as_fail", "report_separately"]
    thresholds: dict[str, float] = Field(default_factory=dict)
    valid_from: AwareDatetime | None = None

    @model_validator(mode="after")
    def _active_requires_confirmation(self) -> "CriteriaRef":
        if self.status not in {LifecycleStatus.draft, LifecycleStatus.active}:
            raise ValueError("S0 CriteriaRef status is limited to draft/active")
        if self.status is LifecycleStatus.active and not self.confirmation_ref:
            raise ValueError("active CriteriaRef requires confirmation_ref")
        return self


class EvaluationSetRef(_Model):
    id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    frozen: bool
    split_manifest_ref: str = Field(min_length=1)
    counts: dict[SplitRole, int] = Field(default_factory=dict)
    exposure_ledger_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _counts_non_negative(self) -> "EvaluationSetRef":
        if any(v < 0 for v in self.counts.values()):
            raise ValueError("split counts must be non-negative")
        return self


class CaseResult(_Model):
    case_id: str = Field(min_length=1)
    verdict: Verdict
    evidence_refs: list[str] = Field(default_factory=list)
    notes: str | None = None


class QualityMetric(_Model):
    name: str = Field(min_length=1)
    value: float
    numerator: int | None = None
    denominator: int = Field(ge=0)


class Coverage(_Model):
    covered: int = Field(ge=0)
    total: int = Field(ge=0)


class UnknownRate(_Model):
    count: int = Field(ge=0)
    rate: float = Field(ge=0.0, le=1.0)


class HumanEffort(_Model):
    count: int = Field(ge=0)
    minutes: float | None = Field(default=None, ge=0)


class Cost(_Model):
    amount: float = Field(ge=0)
    currency: str = Field(min_length=1)


class Latency(_Model):
    p50: float = Field(ge=0)
    p95: float = Field(ge=0)


class Stratum(_Model):
    key: str = Field(min_length=1)
    metrics: dict[str, float]


class MetricBundle(_Model):
    quality: list[QualityMetric] = Field(default_factory=list)
    coverage: Coverage
    unknown: UnknownRate
    human: HumanEffort
    cost: Cost | None = None
    latency_ms: Latency
    strata: list[Stratum] | None = None
    missing_records: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coverage_bounds(self) -> "MetricBundle":
        if self.coverage.covered > self.coverage.total:
            raise ValueError("coverage.covered cannot exceed coverage.total")
        return self


class AcceptanceReport(_Model):
    id: str = Field(min_length=1)
    criteria_ref: VersionedRef
    evaluation_set_ref: VersionedRef
    target_ref: VersionedRef
    dependency_versions: list[VersionedRef] = Field(default_factory=list)
    overall: Verdict
    cases: list[CaseResult] = Field(default_factory=list)
    cases_ref: str | None = None
    metrics: MetricBundle
    coverage_scope: str = Field(min_length=1)
    limits: list[str] = Field(default_factory=list)
    run_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _cases_or_ref(self) -> "AcceptanceReport":
        if len(self.cases) > 1000:
            raise ValueError("inline cases are capped at 1000; use cases_ref")
        if not self.cases and not self.cases_ref:
            raise ValueError("AcceptanceReport requires cases or cases_ref")
        return self


def validate_acceptance_report(
    report: AcceptanceReport,
    *,
    criteria: CriteriaRef,
    evaluation_set: EvaluationSetRef,
) -> None:
    """Cross-object acceptance checks that a single JSON object cannot see.

    ``AcceptanceReport`` only carries ``VersionedRef`` values, so this helper
    verifies the referenced objects when the caller already holds them:
    the criteria must be ``active`` (and match the report's ref), the sample
    set must be frozen, and only ``unseen_acceptance`` samples may be used.
    """

    if str(report.criteria_ref) != f"{criteria.id}@{criteria.revision}":
        raise ValueError("report.criteria_ref does not match the supplied CriteriaRef")
    if criteria.status is not LifecycleStatus.active:
        raise ValueError("acceptance requires active criteria")
    if not criteria.confirmation_ref:
        raise ValueError("active criteria requires confirmation_ref")
    if str(report.evaluation_set_ref) != f"{evaluation_set.id}@{evaluation_set.revision}":
        raise ValueError(
            "report.evaluation_set_ref does not match the supplied EvaluationSetRef"
        )
    if not evaluation_set.frozen:
        raise ValueError("acceptance requires a frozen evaluation set")
    unseen = int(evaluation_set.counts.get(SplitRole.unseen_acceptance, 0))
    if unseen <= 0:
        raise ValueError("acceptance requires unseen_acceptance samples")
    if report.cases and len(report.cases) > unseen:
        raise ValueError(
            "acceptance cases cannot exceed the unseen_acceptance sample count"
        )
