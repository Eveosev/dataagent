"""Regression tests for the tester r25 aggregate-shape caliber fixes (B1).

W0 §3: the SQL aggregation must be ``<aggregation>(<measure field_id>)``.
The aggregate's *argument* must be the bare measure column, the aggregate
must not carry a FILTER clause, and the projection must deliver the
aggregate untouched (value-preserving CAST aside) — reading a column a CTE
computed by aggregating is only allowed as the bare column. A SQL that is
syntactically correct but transforms the measure must be rejected instead of
delivering a wrong total with the metric's version attached.
"""

from __future__ import annotations

import pytest

from dataagent_contracts.core import CapabilityStatus

from dataagent_application import helpers
from dataagent_application.execution import sql as sql_exec  # noqa: F401  (registers DA07.1.3)
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
            ["north", 900, True, "2025-12-01"],  # outside the bound window
        ],
    )


def _metric():
    return {
        "draft_id": "m-r25",
        "revision": "r1",
        "kind": "metric",
        "definition": {
            "statement": "approved amount by region",
            "measure": {"field_ref": "amount", "aggregation": "sum"},
            "filters": [{"text": "approved = true", "referenced_fields": ["approved"]}],
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


def _delivered_total(runtime, ctx, table, requirement, metric, result):
    executed = sql_exec.execute_duckdb_sql(
        sql_exec.ExecuteDuckdbSqlInput.model_validate(
            {
                "spec": result.data.spec.model_dump(mode="json"),
                "table_refs": [_table_payload(table)],
                "semantic_versions": [{"id": metric["draft_id"], "revision": "r1"}],
                "grain": "region",
                "unit": "CNY",
            }
        ),
        ctx,
        runtime,
    )
    assert executed.status is CapabilityStatus.ok
    computed = helpers.load_computed_table(runtime, executed.data.result.table_ref)
    return sum(
        float(row[1])
        for row in computed.rows
        if len(row) > 1 and isinstance(row[1], (int, float))
    )


_WINDOW = "occurred_on >= '2026-01-01' AND occurred_on < '2026-02-01'"


def test_control_exact_aggregate_passes_and_delivers_bound_total(
    runtime, ctx, caliber_case
):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok
    assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 300.0


@pytest.mark.parametrize(
    "total_expr",
    [
        "sum(amount * 2)",
        "sum(amount + 50)",
        "sum(CASE WHEN region = 'north' THEN amount ELSE 0 END)",
        "sum(amount) FILTER (WHERE approved = false)",
        "sum(amount) * 2",
    ],
)
def test_transformed_aggregate_shapes_are_rejected(runtime, ctx, caliber_case, total_expr):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, {total_expr} AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"


def test_value_preserving_cast_around_aggregate_is_allowed(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, CAST(sum(amount) AS DOUBLE) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok
    assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 300.0


def test_parenthesised_aggregate_is_allowed(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, (sum(amount)) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


def test_cte_aggregated_column_may_be_projected_as_itself(runtime, ctx, caliber_case):
    """Reading a CTE column an inner SELECT computed by aggregating is fine."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region) "
        f"SELECT region, total FROM base",
    )
    assert result.status is CapabilityStatus.ok
    assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 300.0


def test_cte_aggregated_column_scaled_in_outer_select_is_rejected(
    runtime, ctx, caliber_case
):
    """``total * 2`` over an aggregated CTE column delivers 600, not 300."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region) "
        f"SELECT region, total * 2 AS total FROM base",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "aggregated column" in result.issues[0].message


def test_transformed_aggregate_inside_cte_is_rejected(runtime, ctx, caliber_case):
    """The CTE's own projection is shape-checked like the result's."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT region, sum(amount * 2) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region) "
        f"SELECT region, total FROM base",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"


def test_cast_over_cte_aggregated_column_is_allowed(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region) "
        f"SELECT region, CAST(total AS DOUBLE) AS total FROM base",
    )
    assert result.status is CapabilityStatus.ok
    assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 300.0


def test_string_function_over_cte_aggregated_column_is_rejected(
    runtime, ctx, caliber_case
):
    """A non value-preserving wrapper around an aggregated column transforms it."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region) "
        f"SELECT region, coalesce(total, 0) AS total FROM base",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
