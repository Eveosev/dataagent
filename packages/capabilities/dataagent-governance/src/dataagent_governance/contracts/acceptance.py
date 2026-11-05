"""Acceptance criteria, evaluation cases and exposure ledger (08 §5.2–5.3)."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from dataagent_contracts.core import (
    Assessment,
    ComputedResult,
    SplitRole,
    VersionedRef,
)
from dataagent_contracts.core._base import ExtModel

__all__ = [
    "AcceptanceCriteriaDraft",
    "CriteriaProposal",
    "CriteriaConfirmation",
    "ExpectedJudgment",
    "ExpectedComputation",
    "EvaluationCaseDraft",
    "EvaluationDelivery",
    "ExposureLedgerEntry",
    "PaginationReceipt",
]


class CriteriaProposal(ExtModel):
    """Agent-submitted draft of the acceptance criteria (two-phase DA11.5.1)."""

    owner_ref: str = Field(min_length=1)
    family: Literal["judgment", "compute"]
    # Natural-language statement of what the delivery must achieve.
    expected_outputs: str = Field(min_length=1)
    evidence_requirements: list[str] = Field(min_length=1)
    unknown_policy: Literal["count_as_fail", "report_separately"]
    # Named thresholds, e.g. {"pass_rate": 0.9}. Rates must be within [0, 1].
    thresholds: dict[str, float] = Field(default_factory=dict)
    # Numeric comparison tolerance for the compute family.
    tolerance_relative: float = Field(default=0.0, ge=0.0)
    tolerance_absolute: float = Field(default=0.0, ge=0.0)
    # Task layers used for stratified difference reporting.
    strata: list[str] = Field(default_factory=list)
    # Resource constraints: budget ceilings the delivery must respect.
    max_seconds: float | None = Field(default=None, ge=0)
    max_cost: float | None = Field(default=None, ge=0)


class AcceptanceCriteriaDraft(ExtModel):
    """Persisted criteria; DA11.5.1 only ever writes ``status=draft``."""

    criteria_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    delivery_target: str = Field(min_length=1)
    family: Literal["judgment", "compute"]
    expected_outputs: str = Field(min_length=1)
    evidence_requirements: list[str] = Field(min_length=1)
    unknown_policy: Literal["count_as_fail", "report_separately"]
    thresholds: dict[str, float] = Field(default_factory=dict)
    tolerance_relative: float = 0.0
    tolerance_absolute: float = 0.0
    strata: list[str] = Field(default_factory=list)
    max_seconds: float | None = None
    max_cost: float | None = None
    status: Literal["draft", "active"] = "draft"
    confirmation_ref: str | None = None

    @model_validator(mode="after")
    def _active_requires_confirmation(self) -> "AcceptanceCriteriaDraft":
        if self.status == "active" and not self.confirmation_ref:
            raise ValueError("active criteria requires confirmation_ref")
        return self


class CriteriaConfirmation(ExtModel):
    """Confirmation record from an authorized subject (review §9).

    Binds the criteria **content digest and revision**; a forged, stale or
    mis-targeted confirmation is rejected by the confirmation entry.
    """

    confirmation_id: str = Field(min_length=1)
    criteria_id: str = Field(min_length=1)
    criteria_revision: str = Field(min_length=1)
    criteria_digest: str = Field(min_length=1)
    confirmer_ref: str = Field(min_length=1)
    confirmed_at: AwareDatetime
    # Authority under which the confirmer may activate criteria.
    authority_ref: str = Field(min_length=1)


class ExpectedJudgment(ExtModel):
    """Gold expectation for one rule on one record (judgment family)."""

    record_key: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    expected_verdict: Literal["pass", "fail", "unknown"]
    # Fields the delivery's evidence must be able to locate.
    expected_evidence_fields: list[str] = Field(default_factory=list)


class ExpectedComputation(ExtModel):
    """Gold expectation for one computed number (compute family)."""

    metric_id: str = Field(min_length=1)
    expected_value: float
    unit: str | None = None
    grain: str = Field(min_length=1)
    filters_applied: list[str] = Field(default_factory=list)


class EvaluationCaseDraft(ExtModel):
    """A case: input content plus expected output, with grouping keys."""

    case_id: str = Field(min_length=1)
    # Content refs: input and gold expectations are stored separately.
    input_ref: VersionedRef
    expected_ref: VersionedRef
    # Grouping keys (entity / time window / source cluster). Whole groups are
    # assigned to one role; cases never straddle roles (08 §5.2).
    group_keys: dict[str, str] = Field(default_factory=dict)


class EvaluationDelivery(ExtModel):
    """The delivery under acceptance for one case (08 §5.3)."""

    case_id: str = Field(min_length=1)
    assessment: Assessment | None = None
    computed_result: ComputedResult | None = None
    timed_out: bool = False
    budget_exhausted: bool = False

    @model_validator(mode="after")
    def _exactly_one_payload(self) -> "EvaluationDelivery":
        payloads = [p for p in (self.assessment, self.computed_result) if p is not None]
        if len(payloads) != 1 and not (self.timed_out or self.budget_exhausted):
            raise ValueError(
                "delivery requires exactly one of assessment/computed_result, "
                "or a timeout/budget marker"
            )
        return self


class ExposureLedgerEntry(ExtModel):
    """Gold-read exposure: the case is demoted to regression (08 §5.2)."""

    entry_id: str = Field(min_length=1)
    set_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    accessed_by: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    demoted_to: SplitRole = SplitRole.regression
    at: AwareDatetime


class PaginationReceipt(ExtModel):
    """Pagination/truncation receipt checked by DA11.2.3."""

    page_size: int = Field(ge=1)
    pages: int = Field(ge=1)
    declared_total_rows: int | None = Field(default=None, ge=0)
    truncated: bool = False
