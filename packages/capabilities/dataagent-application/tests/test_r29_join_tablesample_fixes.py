"""Regression tests for the tester r29 caliber-smuggling shapes (B1/B2).

The r24–r27 rounds closed scope, aggregate-shape, column-lineage and
conjunct bypasses. The shapes below select or multiply the *delivered
rows* through FROM clauses the collector never inspected: a JOIN whose
ON conjunct filters the bound table (a dimension, measure, fixed-filter
or time predicate — an ON conjunct is a WHERE in disguise), a SEMI JOIN,
a post-aggregation filter hidden in a JOIN ON, an ON subquery that
re-reads the bound table outside the read-once guard, and the samplers
(``TABLESAMPLE`` on a source, ``USING SAMPLE`` on the select) that drop
rows before the bound aggregate. None of them may pass with the metric's
version attached.

The matching positive controls live in ``test_r27_caliber_where_fixes.py``.
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
        "draft_id": "m-r29",
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
        # an ON conjunct filters the bound table on a dimension (100, not 300)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"JOIN (SELECT 'north' AS keep) x ON region = x.keep "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # the same with the measure column (200)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"JOIN (SELECT 150 AS threshold) x ON amount > x.threshold "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # an ON conjunct that contradicts the bound fixed filter (0)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"JOIN (SELECT 1 AS one) x ON approved = false "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # an extra time predicate hidden in the ON (200)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"JOIN (SELECT '2026-01-15' AS lo) x ON occurred_on >= x.lo "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # a constant ON conjunct is the equivalent of LIMIT 0 (0)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"JOIN (SELECT 1 AS one) x ON false "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # a SEMI JOIN keeps north only (100)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"SEMI JOIN (SELECT 'north' AS keep) x ON region = x.keep "
        f"WHERE approved = true AND {{w}} GROUP BY region",
    ],
)
def test_join_on_row_filters_are_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric, sql.format(t=name, w=_WINDOW)
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "ON condition" in result.issues[0].message


@pytest.mark.parametrize(
    "sql",
    [
        # a post-aggregation filter hidden in a JOIN ON (200, not 300)
        f"WITH agg AS (SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region) "
        f"SELECT region, total FROM agg a "
        f"JOIN (SELECT 150 AS threshold) y ON a.total > y.threshold",
        # the same over a derived table
        f"SELECT region, total FROM (SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region) a "
        f"JOIN (SELECT 150 AS threshold) y ON a.total > y.threshold",
    ],
)
def test_join_on_after_aggregation_is_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric, sql.format(t=name, w=_WINDOW)
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "ON condition" in result.issues[0].message


def test_join_on_subquery_rereading_bound_table_is_rejected(runtime, ctx, caliber_case):
    """An ON subquery re-reads the bound table outside the read-once guard."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"JOIN (SELECT 1 AS one) x ON amount > (SELECT avg(amount) FROM {name}) "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "ON condition" in result.issues[0].message


@pytest.mark.parametrize(
    "sql",
    [
        # a comma cross join multiplies rows by an unbounded right side
        f"SELECT region, sum(amount) AS total FROM {{t}}, (SELECT 1 AS one) x "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # USING matches rows on shared columns and cannot be checked
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"JOIN (SELECT 'north' AS region) x USING (region) "
        f"WHERE approved = true AND {{w}} GROUP BY region",
    ],
)
def test_cross_and_using_joins_are_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric, sql.format(t=name, w=_WINDOW)
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "JOIN" in result.issues[0].message


@pytest.mark.parametrize(
    "sql",
    [
        # a table-level sampler drops rows before the bound aggregate
        f"SELECT region, sum(amount) AS total FROM {{t}} TABLESAMPLE 1 PERCENT "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # the same sampler inside a CTE the result reads
        f"WITH base AS (SELECT * FROM {{t}} TABLESAMPLE 1 PERCENT) "
        f"SELECT region, sum(amount) AS total FROM base "
        f"WHERE approved = true AND {{w}} GROUP BY region",
        # a select-level sampler (DuckDB USING SAMPLE)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region USING SAMPLE 1 PERCENT",
    ],
)
def test_row_samplers_are_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric, sql.format(t=name, w=_WINDOW)
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "SAMPLE" in result.issues[0].message.upper()
