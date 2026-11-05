"""Application-layer specific types (07 §4.2).

``ExecutableSpec`` and ``EngineBinding`` live in ``dataagent-contracts``
``core.semantics`` (migrated per 07 §4.2). ``RequirementSpec``, ``Ambiguity``
and ``ReportDraft`` are consumed only by this layer and stay here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dataagent_contracts.core import (
    EvidenceRef,
    MetricFilter,
    TimeRange,
    VersionedRef,
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Requirement binding and clarification (DA06.1) -------------------------


AmbiguityKind = Literal[
    "metric_definition",
    "time_boundary",
    "unit_or_currency",
    "grain_dedup",
    "filter_scope",
]


class Ambiguity(_Model):
    """One ambiguity that changes the result if resolved differently (DA06.1.3)."""

    ambiguity_id: str = Field(min_length=1)
    kind: AmbiguityKind
    description: str = Field(min_length=1)
    result_impact: str = Field(min_length=1)
    blocking: bool = False
    affected: list[str] = Field(default_factory=list)


class RequirementSpec(_Model):
    """Bound requirement: metrics, dimensions, time, filters, grain (DA06.1.1)."""

    requirement_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    metrics: list[VersionedRef] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    time: TimeRange | None = None
    filters: list[MetricFilter] = Field(default_factory=list)
    grain: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)


class ParsedFilter(_Model):
    field_id: str = Field(min_length=1)
    operator: Literal["eq", "ne", "lt", "le", "gt", "ge", "in", "between", "like"]
    values: list[Any] = Field(min_length=1)

    @model_validator(mode="after")
    def _arity(self) -> "ParsedFilter":
        if self.operator == "between" and len(self.values) != 2:
            raise ValueError("between filter requires exactly two values")
        return self


class TimeFilterProposal(_Model):
    time: TimeRange | None = None
    filters: list[ParsedFilter] = Field(default_factory=list)


class ClarificationQuestion(_Model):
    ambiguity_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    alternatives: list[str] = Field(default_factory=list)


class ClarificationProposal(_Model):
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    answers: list[dict[str, Any]] = Field(default_factory=list)


# --- Reports (DA10.3) --------------------------------------------------------


class ReportSection(_Model):
    heading: str = Field(min_length=1)
    body_markdown: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class ReportDraft(_Model):
    draft_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    title: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    sections: list[ReportSection] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    undecidable: list[str] = Field(default_factory=list)
    not_covered: list[str] = Field(default_factory=list)
    acceptance_summary: str | None = None

    @property
    def evidence_ids(self) -> set[str]:
        return {item.id for item in self.evidence}
