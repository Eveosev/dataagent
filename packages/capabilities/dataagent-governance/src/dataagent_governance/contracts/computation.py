"""Grain and merge check report (DA11.2.3, 08 §5.4)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from dataagent_contracts.core import VersionedRef
from dataagent_contracts.core._base import ExtModel

__all__ = ["GrainCheckItem", "GrainMergeReport"]

CheckName = Literal[
    "grain_key_uniqueness",
    "join_cardinality",
    "measure_conservation",
    "pagination_completeness",
]
CheckOutcome = Literal["pass", "fail", "unknown"]


class GrainCheckItem(ExtModel):
    check: CheckName
    outcome: CheckOutcome
    details: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)


class GrainMergeReport(ExtModel):
    report_id: str = Field(min_length=1)
    spec_ref: VersionedRef
    declared_grain: list[str] = Field(min_length=1)
    items: list[GrainCheckItem] = Field(default_factory=list)
    overall: CheckOutcome

    @model_validator(mode="after")
    def _overall_consistency(self) -> "GrainMergeReport":
        outcomes = [item.outcome for item in self.items]
        if "fail" in outcomes:
            if self.overall != "fail":
                raise ValueError("overall must be fail when any item fails")
        elif "unknown" in outcomes and self.overall == "pass":
            raise ValueError("overall cannot be pass while an item is unknown")
        return self
