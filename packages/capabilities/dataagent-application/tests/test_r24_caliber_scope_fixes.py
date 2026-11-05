"""Regression tests for the tester r24 caliber-scope fixes (B1).

A bound requirement pins the filters, the time window and the measure
aggregation on the rows the delivered result actually aggregates. A
predicate that only exists in a CTE nobody reads or an EXISTS subquery
binds nothing; an aggregate inside a scalar subquery is not the bound
aggregation; a self-join multiplies rows. None of these may pass with the
metric's version attached — and the honest shapes (a used CTE chain, a
derived table) must keep working.
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
            ["north", 900, True, "2025-12-01"],  # outside the bound window
        ],
    )


def _metric():
    return {
        "draft_id": "m-r24",
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


_WINDOW = "occurred_on >= '2026-01-01' AND occurred_on < '2026-02-01'"


def test_aligned_sql_still_passes(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


def test_filter_only_in_unused_cte_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH f AS (SELECT 1 AS ok FROM {name} WHERE approved = true) "
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "fixed filter" in result.issues[0].message


def test_filter_only_in_exists_subquery_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE {_WINDOW} AND EXISTS "
        f"(SELECT 1 FROM {name} x WHERE x.approved = true) GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "fixed filter" in result.issues[0].message


def test_time_window_only_in_unused_cte_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH w AS (SELECT 1 AS ok FROM {name} WHERE {_WINDOW}) "
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "time range is not applied" in result.issues[0].message


def test_time_window_only_in_exists_subquery_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND EXISTS "
        f"(SELECT 1 FROM {name} x WHERE x.occurred_on >= '2026-01-01' "
        f"AND x.occurred_on < '2026-02-01') GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "time range is not applied" in result.issues[0].message


def test_measure_only_in_scalar_subquery_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, (SELECT sum(amount) FROM {name}) AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "must aggregate" in result.issues[0].message


def test_self_join_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT t.region AS region, sum(t.amount) AS total FROM {name} t "
        f"JOIN {name} x ON true "
        f"WHERE t.approved = true AND t.occurred_on >= '2026-01-01' "
        f"AND t.occurred_on < '2026-02-01' GROUP BY t.region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "self-joins" in result.issues[0].message


def test_cte_joined_with_itself_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT * FROM {name} WHERE approved = true AND {_WINDOW}) "
        f"SELECT b1.region AS region, sum(b1.amount) AS total FROM base b1 "
        f"JOIN base b2 ON true GROUP BY b1.region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "multiplies rows" in result.issues[0].message


def test_used_cte_chain_carries_the_caliber(runtime, ctx, caliber_case):
    """A CTE the result actually reads contributes its WHERE conjuncts."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"WITH base AS (SELECT * FROM {name} WHERE approved = true AND {_WINDOW}) "
        f"SELECT region, sum(amount) AS total FROM base GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


def test_used_derived_table_carries_the_caliber(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM "
        f"(SELECT * FROM {name} WHERE approved = true AND {_WINDOW}) d "
        f"GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


def test_group_by_only_in_scalar_subquery_does_not_satisfy_grain(runtime, ctx, caliber_case):
    """A dimension grouped only inside a scalar subquery is not the bound grain."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, (SELECT sum(amount) FROM {name} GROUP BY region) AS total "
        f"FROM {name} WHERE approved = true AND {_WINDOW}",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"


def test_windowed_aggregate_does_not_satisfy_binding(runtime, ctx, caliber_case):
    """``sum(x) OVER ()`` is a per-row window value, not the group aggregate."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) OVER () AS total FROM {name} "
        f"WHERE approved = true AND {_WINDOW} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "must aggregate" in result.issues[0].message
