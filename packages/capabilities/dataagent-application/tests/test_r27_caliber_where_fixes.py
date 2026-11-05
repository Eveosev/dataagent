"""Regression tests for the tester r27 caliber-smuggling shapes (B1).

The r24/r25/r26 rounds closed scope, aggregate-shape and column-lineage
bypasses. The shapes below filter the *delivered groups/rows* after — or
around — the bound aggregate while keeping its text intact: a QUALIFY
clause (top level, inside a CTE, inside a derived table), a WHERE on a
CTE/derived-table column that was already aggregated (a post-aggregation
WHERE is a HAVING in disguise), and extra WHERE conjuncts outside the
bound filters (a dimension filter, a measure filter, an IN list, or the
column-less constant ``1 = 0``). None of them may pass with the metric's
version attached.

The legal controls from the same round stay green: the exact aggregate,
the ``SELECT *`` CTE passthrough and the outer WHERE over an *unfiltered*
CTE chain remain accepted and deliver the bound total 300.
"""

from __future__ import annotations

import pytest

from dataagent_contracts.core import CapabilityStatus

from dataagent_application import helpers
from dataagent_application.execution import sql as sql_exec
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
        "draft_id": "m-r27",
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


@pytest.mark.parametrize(
    "sql",
    [
        # QUALIFY is a HAVING/LIMIT-class group filter: it keeps one of the
        # two bound groups (100 instead of 300).
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region "
        f"QUALIFY row_number() OVER (ORDER BY region) = 1",
        # the same QUALIFY inside a CTE the result reads
        f"WITH q AS (SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region "
        f"QUALIFY row_number() OVER (ORDER BY region) = 1) "
        f"SELECT region, total FROM q",
        # the same QUALIFY inside a derived table
        f"SELECT region, total FROM (SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region "
        f"QUALIFY row_number() OVER (ORDER BY region) = 1) s",
    ],
)
def test_qualify_shapes_are_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric, sql.format(t=name, w=_WINDOW)
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "QUALIFY" in result.issues[0].message


@pytest.mark.parametrize(
    "sql",
    [
        # a WHERE on an already-aggregated CTE column keeps south only (200)
        f"WITH agg AS (SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region) "
        f"SELECT region, total FROM agg WHERE total > 150",
        # the same over a derived table
        f"SELECT region, total FROM (SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} GROUP BY region) s "
        f"WHERE total > 150",
    ],
)
def test_post_aggregation_where_is_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric, sql.format(t=name, w=_WINDOW)
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "post-aggregation WHERE" in result.issues[0].message


@pytest.mark.parametrize(
    "sql",
    [
        # an undeclared dimension filter narrows the caliber to north (100)
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} AND region = 'north' GROUP BY region",
        # a measure-value pre-filter keeps the 200 row only
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} AND amount > 150 GROUP BY region",
        # an IN list filters the dimension the same way
        f"SELECT region, sum(amount) AS total FROM {{t}} "
        f"WHERE approved = true AND {{w}} AND region IN ('north') GROUP BY region",
        # an extra filter inside a CTE the result reads narrows it too
        f"WITH base AS (SELECT * FROM {{t}} "
        f"WHERE approved = true AND {{w}} AND region = 'north') "
        f"SELECT region, sum(amount) AS total FROM base GROUP BY region",
    ],
)
def test_extra_where_filters_are_rejected(runtime, ctx, caliber_case, sql):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric, sql.format(t=name, w=_WINDOW)
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "extra WHERE filter" in result.issues[0].message


def test_constant_false_conjunct_is_rejected(runtime, ctx, caliber_case):
    """``1 = 0`` is the equivalent of LIMIT 0 and delivers an empty result."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} AND 1 = 0 GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "without referencing a column" in result.issues[0].message


def test_in_list_on_bound_time_field_is_rejected(runtime, ctx, caliber_case):
    """An IN form on a bound column cannot be checked against the window."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} "
        f"AND occurred_on IN ('2026-01-05') GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "cannot check" in result.issues[0].message


def test_control_shapes_still_deliver_the_bound_total(runtime, ctx, caliber_case):
    """The exact aggregate and the CTE passthrough keep passing at 300."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    for sql in (
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
        f"WITH base AS (SELECT * FROM {name}) "
        f"SELECT region, sum(amount) AS total FROM base "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    ):
        result = _generate(runtime, ctx, table, requirement, metric, sql)
        assert result.status is CapabilityStatus.ok
        assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 300.0


def test_cte_chain_with_bound_filters_only_still_passes(runtime, ctx, caliber_case):
    """A read CTE whose WHERE holds only the bound conjuncts is fine."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT * FROM {name} "
        f"WHERE approved = true AND {_WINDOW}) "
        f"SELECT region, sum(amount) AS total FROM base GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok
    assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 300.0


def test_aggregated_cte_column_without_outer_where_still_passes(
    runtime, ctx, caliber_case
):
    """Reading an aggregated CTE column is fine; filtering it is not (above)."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH agg AS (SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region) "
        f"SELECT region, total FROM agg",
    )
    assert result.status is CapabilityStatus.ok
    assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 300.0
