from __future__ import annotations

import pytest

from dataagent_contracts.core import (
    AccessOutcome,
    Aggregation,
    CapabilityStatus,
    CompletenessExtent,
    EgressOutcome,
    EvidenceType,
    FieldValueStatus,
    LifecycleStatus,
    Severity,
    SplitRole,
    StandardErrorCode,
    TraceEventType,
    Verdict,
)

CLOSED = [
    CapabilityStatus,
    StandardErrorCode,
    Severity,
    CompletenessExtent,
    FieldValueStatus,
    Verdict,
    SplitRole,
    LifecycleStatus,
    AccessOutcome,
    EgressOutcome,
]
OPEN = [Aggregation, EvidenceType, TraceEventType]


def test_enum_counts():
    assert len(CLOSED) == 10
    assert len(OPEN) == 3
    assert len(StandardErrorCode) == 10
    assert [c.value for c in StandardErrorCode] == [
        "unauthorized",
        "unsupported",
        "invalid_input",
        "version_conflict",
        "not_found",
        "source_changed",
        "rate_limited",
        "timeout",
        "execution_unknown",
        "dependency_unavailable",
    ]


@pytest.mark.parametrize("enum_type", CLOSED)
def test_closed_enums_reject_unknown(enum_type):
    with pytest.raises(ValueError):
        enum_type("acme:not_a_value")


@pytest.mark.parametrize("enum_type", OPEN)
def test_open_enums_accept_namespaced_extension(enum_type):
    value = enum_type("acme.weighted_mean")
    assert value.value == "acme.weighted_mean"
    assert value == enum_type("acme.weighted_mean")
    with pytest.raises(ValueError):
        enum_type("weighted_mean")
    with pytest.raises(ValueError):
        enum_type("acme:weighted_mean")


def test_verdict_values_are_wire_compatible():
    assert Verdict.pass_.value == "pass"
    assert "not_applicable" in {v.value for v in Verdict}
