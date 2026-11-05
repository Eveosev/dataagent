"""Semantic, rule, metric, assessment and evidence contracts (05 §3.3.4)."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_serializer, model_validator
from ._base import ExtModel  # noqa: E402

from .envelope import Completeness
from .refs import AssetRef, SourceAnchor, VersionedRef
from .vocab import Aggregation, EvidenceType, LifecycleStatus

__all__ = [
    "RuleCondition",
    "ExceptionClause",
    "RuleDefinition",
    "Measure",
    "MetricFilter",
    "MetricTime",
    "MetricDefinition",
    "SemanticDraft",
    "EvidenceRef",
    "EngineBinding",
    "Assessment",
    "ComputedResult",
    "TimeRange",
    "ExecutableSpec",
]

V = TypeVar("V")


_Model = ExtModel


class RuleCondition(_Model):
    condition_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    referenced_fields: list[str] = Field(default_factory=list)
    anchors: list[SourceAnchor] = Field(default_factory=list)


class ExceptionClause(_Model):
    text: str = Field(min_length=1)
    anchors: list[SourceAnchor] = Field(default_factory=list)


class RuleDefinition(_Model):
    statement: str = Field(min_length=1)
    conditions: list[RuleCondition] = Field(default_factory=list)
    combination: str
    exceptions: list[ExceptionClause] = Field(default_factory=list)
    applicability_ref: str | None = None
    precondition_refs: list[str] = Field(default_factory=list)
    decidability_ref: str | None = None

    @model_validator(mode="after")
    def _combination_refs_conditions(self) -> "RuleDefinition":
        if not self.combination:
            return self
        ids = {c.condition_id for c in self.conditions}
        # Combination is a small textual expression over condition ids. Tokens
        # other than identifiers/operators are rejected so ids stay checkable.
        for token in (
            self.combination.replace("(", " ").replace(")", " ").replace(",", " ").split()
        ):
            if token in {"and", "or", "not", "all", "any"}:
                continue
            if token.startswith(("all", "any", "not")) and token not in {"all", "any", "not"}:
                continue
            if token not in ids:
                raise ValueError(f"combination references unknown token: {token}")
        return self


class Measure(_Model):
    field_ref: str = Field(min_length=1)
    aggregation: Aggregation


class MetricFilter(_Model):
    text: str = Field(min_length=1)
    referenced_fields: list[str] = Field(default_factory=list)


class MetricTime(_Model):
    time_field: str = Field(min_length=1)
    grain: str | None = None
    calendar_ref: str | None = None


class MetricDefinition(_Model):
    statement: str = Field(min_length=1)
    measure: Measure
    filters: list[MetricFilter] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    time: MetricTime | None = None
    unit: str | None = None
    grain: str = Field(min_length=1)
    additivity: Literal["additive", "semi_additive", "non_additive"]
    depends_on: list[VersionedRef] = Field(default_factory=list)
    certified_ref: str | None = None


class TimeRange(_Model):
    from_: AwareDatetime | None = Field(default=None, alias="from")
    to: AwareDatetime | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_serializer(mode="wrap")
    def _serialize_from(self, handler):  # noqa: ANN001
        data = handler(self)
        if "from_" in data:
            data["from"] = data.pop("from_")
        return data


class SemanticDraft(_Model):
    draft_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    kind: Literal["rule", "metric", "entity", "relationship", "dimension"]
    definition: RuleDefinition | MetricDefinition
    scope_ref: str = Field(min_length=1)
    sources: list[SourceAnchor] = Field(min_length=1)
    status: LifecycleStatus
    effective_time: TimeRange | None = None
    unresolved: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _definition_matches_kind(self) -> "SemanticDraft":
        if self.kind == "rule" and not isinstance(self.definition, RuleDefinition):
            raise ValueError("kind=rule requires a RuleDefinition")
        if self.kind == "metric" and not isinstance(self.definition, MetricDefinition):
            raise ValueError("kind=metric requires a MetricDefinition")
        if self.status not in {LifecycleStatus.draft, LifecycleStatus.validated}:
            raise ValueError("S0 SemanticDraft status is limited to draft/validated")
        return self


class EvidenceRef(_Model):
    id: str = Field(min_length=1)
    evidence_type: EvidenceType
    source_anchors: list[SourceAnchor] = Field(default_factory=list)
    value: Any | None = None
    obtained_by: str = Field(min_length=1)
    verification_ref: str | None = None


class EngineBinding(_Model):
    """Coordinates of the engine that produced or will execute a spec.

    07 §5.4: package name, engine version and, when available, the locked
    wheel digest. Consumers compare against the actually installed version
    and fail closed on mismatch (``da07.engine_version_mismatch``).
    """

    engine_id: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    wheel_digest: str | None = None


class Assessment(_Model, Generic[V]):
    assessment_id: str = Field(min_length=1)
    target_ref: VersionedRef
    verdict: V
    basis_refs: list[str] = Field(default_factory=list)
    dependency_refs: list[VersionedRef] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    # 07 §5.1 (additive, 0.1.x): the field values and anchors that actually
    # participated in the evaluation, so a verdict can be traced without
    # re-running the expression. ``basis_refs`` stays free-form string ids;
    # this field carries the structured evidence.
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ComputedResult(_Model):
    result_id: str = Field(min_length=1)
    target_ref: VersionedRef
    form: Literal["scalar", "table"]
    value: Any | None = None
    table_ref: VersionedRef | None = None
    unit: str | None = None
    grain: str = Field(min_length=1)
    filters_applied: list[str] = Field(default_factory=list)
    time_range: TimeRange | None = None
    semantic_versions: list[VersionedRef] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    certified: bool = False
    evidence_refs: list[str] = Field(min_length=1)
    completeness: Completeness
    # 07 §5.2 (additive, 0.1.x): SQL digest and the engine binding that
    # produced the result, consumed by DA11.4.5 (engine consistency
    # regression) and DA12.6 (reproduction conditions).
    sql_digest: str | None = None
    engine_binding: EngineBinding | None = None

    @model_validator(mode="after")
    def _form_payload(self) -> "ComputedResult":
        if self.form == "scalar" and self.value is None:
            raise ValueError("scalar result requires value")
        if self.form == "table" and self.table_ref is None:
            raise ValueError("table result requires table_ref")
        return self


class ExecutableSpec(_Model):
    """Executable form of a rule or metric: closed expression AST or SQL.

    Migrated from the application layer into ``core.semantics`` (07 §4.2) so
    DA11.2.3 (result grain and merge checks) and DA11.4.5 can consume it
    without importing the application package.

    Two shapes (07 §5.1 / §5.2):

    - ``backend_kind = "expression"``: ``expression_or_call`` is a JSON AST
      over the closed operator set (comparisons, arithmetic, logic, ``in``,
      ``between``, ``is_missing``, date difference, string match). Anything
      else is rejected at validation time.
    - ``backend_kind = "sql"``: ``expression_or_call`` is
      ``{"sql": <single statement>, "dialect": <optional>}``.
    """

    spec_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    backend_kind: Literal["expression", "sql"]
    expression_or_call: dict[str, Any] = Field(min_length=1)
    source_refs: list[VersionedRef] = Field(default_factory=list)
    engine_binding: EngineBinding | None = None

    @model_validator(mode="after")
    def _payload_matches_backend(self) -> "ExecutableSpec":
        if self.backend_kind == "sql":
            sql = self.expression_or_call.get("sql")
            if not isinstance(sql, str) or not sql.strip():
                raise ValueError("backend_kind=sql requires expression_or_call['sql'] text")
            if ";" in sql.strip().rstrip(";"):
                raise ValueError("sql payload must be a single statement")
        else:
            node = self.expression_or_call.get("op")
            if not isinstance(node, str) or not node:
                raise ValueError(
                    "backend_kind=expression requires an AST object with an 'op' key"
                )
        return self

    @property
    def sql(self) -> str | None:
        if self.backend_kind != "sql":
            return None
        return str(self.expression_or_call["sql"])
