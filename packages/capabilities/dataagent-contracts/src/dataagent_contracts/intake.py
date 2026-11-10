"""Versioned intake goals and observations, independent of transport and domain."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import Field, computed_field, model_validator
from .core._base import ExtModel
from .core.refs import SourceAnchor


class WorkSpec(ExtModel):
    id: str = Field(min_length=1)
    revision: str = '1'
    goal: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)
    authorization_ref: str = Field(min_length=1)
    domain_config_ref: str | None = None


class SourceSelection(ExtModel):
    source_id: str = Field(min_length=1)
    kind: Literal['file', 'sqlite', 'postgres', 'rest', 'web_ui']
    locator_ref: str = Field(min_length=1)
    credential_binding_ref: str | None = None
    requested_scope: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class CoverageGap(ExtModel):
    partition: int | str
    code: str
    detail: str = ''


class SourceObservation(ExtModel):
    source_id: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    kind: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fields: list[str] = Field(default_factory=list)
    records: list[dict[str, Any]] = Field(default_factory=list)
    anchors: dict[str, list[SourceAnchor]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceProfile(SourceObservation):
    total_partitions: int | None = Field(default=None, ge=0)
    completed_partitions: list[int | str] = Field(default_factory=list)
    gaps: list[CoverageGap] = Field(default_factory=list)
    sampled: bool = False
    issues: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode='after')
    def check_coverage(self):
        parts = self.completed_partitions
        if len(set(parts)) != len(parts):
            raise ValueError('duplicate completed partitions')
        if self.total_partitions is not None:
            if len(parts) > self.total_partitions:
                raise ValueError('completed partitions exceed total')
            for p in parts:
                if isinstance(p, int) and not 1 <= p <= self.total_partitions:
                    raise ValueError('partition outside source')
        return self

    @computed_field
    @property
    def coverage(self) -> Literal['full', 'partial', 'sampled', 'unknown']:
        if self.gaps:
            return 'partial'
        if self.sampled:
            return 'sampled'
        if self.total_partitions is None:
            return 'unknown'
        return 'full' if len(self.completed_partitions) == self.total_partitions else 'partial'

    @model_validator(mode='before')
    @classmethod
    def ignore_derived_coverage(cls, value):
        if isinstance(value, dict):
            value = {k: v for k, v in value.items() if k != 'coverage'}
        return value


class IntakeSession(ExtModel):
    id: str
    revision: str
    goal_ref: str
    sources: list[SourceSelection]
    selected_versions: dict[str, str] = Field(default_factory=dict)
    phase: Literal['queued', 'probing', 'needs_input', 'preview', 'saved', 'failed'] = 'queued'
    job_ref: str
    issues: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class JobHandle(ExtModel):
    session_id: str
    job_ref: str
    revision: str


class EventPage(ExtModel):
    items: list[dict[str, Any]]
    cursor: int
    has_more: bool
