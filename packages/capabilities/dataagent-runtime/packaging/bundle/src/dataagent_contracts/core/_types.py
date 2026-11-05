"""Stable inventory of S0 core types.

The count is part of the contract: 37 types = 35 concrete types + 2 generics
(``CapabilityResult<T>``, ``Assessment<V>``). Embedded structures such as
``FieldSpec`` are intentionally excluded, matching 05-contracts.md §3.2.
"""

from __future__ import annotations

CONCRETE_TYPES: tuple[str, ...] = (
    # envelope (6)
    "CallContext",
    "Issue",
    "ExecutionRef",
    "Continuation",
    "Completeness",
    "Budget",
    # refs (5)
    "VersionedRef",
    "AssetRef",
    "FileRef",
    "SourceAnchor",
    "Selector",
    # data (7)
    "SchemaRef",
    "TableRef",
    "DataBatchRef",
    "DocumentRef",
    "DocumentUnitRef",
    "ExtractedRecordRef",
    "FieldValue",
    # semantics (6)
    "SemanticDraft",
    "EvidenceRef",
    "RuleDefinition",
    "MetricDefinition",
    "ComputedResult",
    "ExecutableSpec",
    # task (3)
    "TaskContextRef",
    "TraceEventRef",
    "CorrectionRef",
    # evaluation (5)
    "CriteriaRef",
    "EvaluationSetRef",
    "AcceptanceReport",
    "CaseResult",
    "MetricBundle",
    # governance (3)
    "AccessDecision",
    "EgressDecision",
    "ComponentMeta",
)

GENERIC_TYPES: tuple[str, ...] = ("CapabilityResult", "Assessment")

CORE_TYPES: tuple[str, ...] = CONCRETE_TYPES + GENERIC_TYPES

EMBEDDED_TYPES: tuple[str, ...] = (
    "FieldSpec",
    "OcrInfo",
    "Confidence",
    "RuleCondition",
    "ExceptionClause",
    "Measure",
    "MetricFilter",
    "MetricTime",
    "TimeRange",
    "QualityMetric",
    "Coverage",
    "UnknownRate",
    "HumanEffort",
    "Cost",
    "Latency",
    "Stratum",
    "ModelDestination",
    "EngineBinding",
)

assert len(CONCRETE_TYPES) == len(set(CONCRETE_TYPES)) == 35
assert len(GENERIC_TYPES) == 2
assert len(CORE_TYPES) == 37
