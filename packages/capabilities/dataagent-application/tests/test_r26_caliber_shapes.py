"""Regression tests for the tester r26 caliber-smuggling shapes (B1).

A bound requirement pins the measure column, the aggregation, the fixed
filters, the time window *and* which groups/rows are delivered. The shapes
below keep the bound aggregate textually intact but change what the
delivered metric version actually sums — a second aggregate in HAVING, an
extra contradictory predicate, a LIMIT, a computed CTE column that shadows
the measure's name, or subtotal rows from ROLLUP/GROUPING SETS. None of
them may pass with the metric's version attached.

The two *legal* shapes the same round asked to keep working are here too:
a value-preserving CAST inside the aggregation and the ``BETWEEN``
equivalent expansion of the bound window.
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
def caliber_table(runtime):
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
            ["north", 900, True, "2025-12-01"],
        ],
    )


def _metric():
    return {
        "draft_id": "m-r26",
        "revision": "r1",
        "kind": "metric",
        "definition": {
            "statement": "approved amount by region for Jan 2026",
            "measure": {"field_ref": "amount", "aggregation": "sum"},
            "filters": [
                {"text": "approved = true", "referenced_fields": ["approved"]}
            ],
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
def caliber_case(runtime, ctx, caliber_table):
    metric = _metric()
    bound = req.bind_metrics_and_dimensions(
        req.BindMetricsAndDimensionsInput.model_validate(
            {
                "statement": "approved amount by region for January 2026",
                "table_ref": _table_payload(caliber_table),
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
    return caliber_table, requirement, metric


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


@pytest.mark.parametrize(
    "sql",
    [
        # HAVING filters the aggregated groups: even the *correct* aggregate
        # inside HAVING is an undeclared group filter.
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region HAVING sum(amount * 2) > 250",
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region HAVING count(*) > 1",
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region HAVING sum(amount) > 150",
        # a second predicate on the bound columns neutralizes the caliber
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} AND occurred_on >= '2030-01-01' GROUP BY region",
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND approved = false AND {{w}} GROUP BY region",
        # LIMIT truncates the delivered rows outside the row budget
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region LIMIT 1",
        # subtotal/grand-total rows change the grain
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY ROLLUP(region)",
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY GROUPING SETS ((region), ())",
    ],
)
def test_caliber_smuggling_shapes_are_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        sql.format(t=name, w=_WINDOW),
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"


@pytest.mark.parametrize(
    "sql",
    [
        # the CTE exports a computed column that shadows the measure's name
        "WITH scaled AS (SELECT region, approved, occurred_on, "
        "amount * 2 AS amount FROM {t}) "
        "SELECT region, sum(amount) AS total FROM scaled "
        "WHERE approved = true AND {w} GROUP BY region",
        # the same via a derived table
        "SELECT region, sum(amount) AS total FROM (SELECT region, approved, "
        "occurred_on, amount * 2 AS amount FROM {t}) s "
        "WHERE approved = true AND {w} GROUP BY region",
        # a predicate on the derived filter column binds nothing
        "WITH neutered AS (SELECT region, occurred_on, amount, "
        "approved OR true AS approved FROM {t}) "
        "SELECT region, sum(amount) AS total FROM neutered "
        "WHERE approved = true AND {w} GROUP BY region",
    ],
)
def test_derived_column_lineage_does_not_carry_the_caliber(
    runtime, ctx, caliber_case, sql
):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        sql.format(t=name, w=_WINDOW),
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"


@pytest.mark.parametrize(
    "sql",
    [
        # value-preserving CAST inside the aggregation keeps every summand
        f"SELECT region, sum(CAST(amount AS DOUBLE)) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # BETWEEN is the equivalent expansion of the bound window
        # (<= <to - 1 day> is the date-granularity equivalent of < to)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND occurred_on BETWEEN '2026-01-01' AND "
        f"'2026-01-31' GROUP BY region",
    ],
)
def test_legal_shapes_still_pass(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        sql.format(t=name, w=_WINDOW),
    )
    assert result.status is CapabilityStatus.ok


def test_control_sql_delivers_the_bound_total(runtime, ctx, caliber_case):
    from dataagent_application.execution import sql as sql_exec
    from dataagent_application import helpers

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok
    executed = sql_exec.execute_duckdb_sql(
        sql_exec.ExecuteDuckdbSqlInput.model_validate(
            {
                "spec": result.data.spec.model_dump(mode="json"),
                "table_refs": [_table_payload(table)],
                "semantic_versions": [{"id": "m-r26", "revision": "r1"}],
                "grain": "region",
                "unit": "CNY",
            }
        ),
        ctx,
        runtime,
    )
    assert executed.status is CapabilityStatus.ok
    computed = helpers.load_computed_table(
        runtime, executed.data.result.table_ref
    )
    total = sum(float(row[1]) for row in computed.rows)
    assert total == 300.0  # 100 + 200; the unapproved 50 and Dec-2025 900 stay out
