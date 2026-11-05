"""Closed and open vocabularies (05-contracts.md §3.4).

Closed enums reject unknown values. Open enums accept a dotted namespaced
extension value (``<ns>.<name>``) so capabilities can add vocabulary without a
new contract release.
"""

from __future__ import annotations

from collections import OrderedDict
from enum import StrEnum
import re
from typing import Any

__all__ = [
    "CapabilityStatus",
    "StandardErrorCode",
    "Severity",
    "CompletenessExtent",
    "FieldValueStatus",
    "Aggregation",
    "EvidenceType",
    "TraceEventType",
    "Verdict",
    "SplitRole",
    "LifecycleStatus",
    "AccessOutcome",
    "EgressOutcome",
]


class CapabilityStatus(StrEnum):
    ok = "ok"
    partial = "partial"
    needs_input = "needs_input"
    pending = "pending"
    failed = "failed"


class StandardErrorCode(StrEnum):
    unauthorized = "unauthorized"
    unsupported = "unsupported"
    invalid_input = "invalid_input"
    version_conflict = "version_conflict"
    not_found = "not_found"
    source_changed = "source_changed"
    rate_limited = "rate_limited"
    timeout = "timeout"
    execution_unknown = "execution_unknown"
    dependency_unavailable = "dependency_unavailable"


class Severity(StrEnum):
    info = "info"
    warning = "warning"
    error = "error"


class CompletenessExtent(StrEnum):
    complete_in_declared_scope = "complete_in_declared_scope"
    page = "page"
    sampled = "sampled"
    truncated = "truncated"
    unknown = "unknown"


class FieldValueStatus(StrEnum):
    extracted = "extracted"
    missing = "missing"
    conflict = "conflict"
    low_confidence = "low_confidence"


class Verdict(StrEnum):
    pass_ = "pass"
    fail = "fail"
    unknown = "unknown"
    not_applicable = "not_applicable"


class SplitRole(StrEnum):
    development = "development"
    regression = "regression"
    unseen_acceptance = "unseen_acceptance"


class LifecycleStatus(StrEnum):
    draft = "draft"
    candidate = "candidate"
    validated = "validated"
    active = "active"
    deprecated = "deprecated"
    invalidated = "invalidated"
    rejected = "rejected"


class AccessOutcome(StrEnum):
    allow = "allow"
    deny = "deny"
    indeterminate = "indeterminate"


class EgressOutcome(StrEnum):
    allow = "allow"
    allow_masked = "allow_masked"
    deny = "deny"


OPEN_NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
OPEN_CACHE_MAX = 128


class _OpenStrEnum(StrEnum):
    """StrEnum that accepts dotted namespaced extension values.

    ``_missing_`` creates a bounded cache of synthetic members for values such
    as ``"acme.weighted_mean"``. Un-namespaced or colon-separated unknown
    values still fail closed (05 §2.4: the namespace separator is ``.``).
    """

    @classmethod
    def _missing_(cls, value: Any):  # type: ignore[override]
        if not isinstance(value, str) or not OPEN_NAMESPACE_PATTERN.match(value):
            return None
        cache = cls.__dict__.get("_open_cache")
        if cache is None:
            cache = OrderedDict()
            setattr(cls, "_open_cache", cache)
        existing = cache.get(value)
        if existing is not None:
            cache.move_to_end(value)
            return existing
        member = str.__new__(cls, value)
        member._name_ = value  # type: ignore[attr-defined]
        member._value_ = value  # type: ignore[attr-defined]
        cls._value2member_map_[value] = member  # type: ignore[attr-defined]
        cache[value] = member
        if len(cache) > OPEN_CACHE_MAX:
            evicted, _ = cache.popitem(last=False)
            cls._value2member_map_.pop(evicted, None)
        return member


class Aggregation(_OpenStrEnum):
    sum = "sum"
    count = "count"
    count_distinct = "count_distinct"
    avg = "avg"
    min = "min"
    max = "max"
    custom = "custom"


class EvidenceType(_OpenStrEnum):
    source_text = "source_text"
    extracted_value = "extracted_value"
    computation_result = "computation_result"
    execution_receipt = "execution_receipt"
    human_judgment = "human_judgment"


class TraceEventType(_OpenStrEnum):
    task_state = "task_state"
    invocation = "invocation"
    correction = "correction"
    decision = "decision"
    note = "note"
