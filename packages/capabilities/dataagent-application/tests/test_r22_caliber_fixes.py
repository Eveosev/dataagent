"""Regression tests for the tester r22 caliber-binding fixes (B1).

A bound requirement pins the measure column, the aggregation (without
DISTINCT), the fixed filters *as unconditional conjuncts* and the time
window (start and end values). A SQL that neutralises a fixed filter with
OR/NOT, replaces the time window or aggregates DISTINCT must not pass with
the metric's version attached.
"""

from __future__ import annotations

import pytest

from dataagent_contracts.core import CapabilityStatus

from dataagent_application.planning import expressions as plan
from dataagent_application.planning import requirements as req

from conftest import store_table


def _table_payload(table):
    return {
        "asset": table.asset.model_dump(mode="json"),
        "schema_ref": "schema:x@r1",
        "data_ref": table.data_ref,
    }


@pytest.fixture()
def time_table(runtime):
    return store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number", "unit": "CNY"},
            {"name": "Approved", "field_id": "approved", "value_type": "boolean"},
            {"name": "Occurred On", "field_id": "occurred_on", "value_type": "date"},
        ],
        rows=[
            ["north", 100, True, "2026-01-05"],
            ["south", 200, True, "2026-01-20"],
            ["north", 50, False, "2026-01-08"],
        ],
    )


def _metric():
    return {
        "draft_id": "m-cal",
        "revision": "r1",
        "kind": "metric",
        "definition": {
            "statement": "approved amount by region",
            "measure": {"field_ref": "amount", "aggregation": "sum"},
            "filters": [
                {"text": "approved = true", "referenced_fields": ["approved"]}
            ],
            "dimensions": ["region"],
            "time": {"time_field": "occurred_on", "grain": "month"},
            "grain": "region x month",
            "additivity": "additive",
            "unit": "CNY",
        },
        "scope_ref": "scope-1",
        "sources": [
            {
                "source_ref": "doc-1",
                "source_revision": "r1",
                "selector": {
                    "kind": "text_span",
                    "unit_ref": "unit:char",
                    "char_start": 0,
                    "char_end": 8,
                },
            }
        ],
        "status": "validated",
    }


@pytest.fixture()
def caliber_case(runtime, ctx, time_table):
    metric = _metric()
    bound = req.bind_metrics_and_dimensions(
        req.BindMetricsAndDimensionsInput.model_validate(
            {
                "statement": "approved amount by region for January 2026",
                "table_ref": _table_payload(time_table),
                "metrics": [metric],
                "proposal": {
                    "metric_ids": [metric["draft_id"]],
                    "dimensions": ["region"],
                    "grain": "region x month",
                },
            }
        ),
        ctx,
        runtime,
    )
    assert bound.status is CapabilityStatus.ok
    requirement = bound.data.requirement.model_dump(mode="json")
    requirement["time"] = {
        "from": "2026-01-01T00:00:00+00:00",
        "to": "2026-02-01T00:00:00+00:00",
    }
    return time_table, requirement, metric


def _generate(runtime, ctx, table, requirement, metric, sql):
    return plan.generate_single_table_sql(
        plan.GenerateSingleTableSqlInput.model_validate(
            {
                "table_ref": _table_payload(table),
                "metrics": [metric],
                "requirement": requirement,
                "proposal": {"sql": sql},
            }
        ),
        ctx,
        runtime,
    )


_WINDOW = "occurred_on >= '2026-01-01' AND occurred_on < '2026-02-01'"


def test_time_window_aligned_sql_passes(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


def test_time_window_between_form_passes(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        "WHERE approved = true AND occurred_on BETWEEN "
        "'2026-01-01' AND '2026-01-31' GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


def test_wrong_time_window_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        "WHERE approved = true AND occurred_on >= '2020-01-01' GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "time range is not applied" in result.issues[0].message
    assert "2026-01-01" in result.issues[0].message


def test_time_column_only_is_not_null_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND occurred_on IS NOT NULL GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "time range is not applied" in result.issues[0].message


def test_fixed_filter_neutralised_by_or_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE (approved = true OR approved = false) AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "operator/value" in result.issues[0].message


def test_fixed_filter_negated_with_not_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE NOT approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "operator/value" in result.issues[0].message


def test_sum_distinct_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(DISTINCT amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "DISTINCT" in result.issues[0].message


def test_time_window_under_or_does_not_bind(runtime, ctx, caliber_case):
    """A window stated as an OR alternative constrains nothing."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        "WHERE approved = true AND ("
        "occurred_on >= '2026-01-01' OR occurred_on < '2026-01-01') "
        "GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "time range is not applied" in result.issues[0].message
