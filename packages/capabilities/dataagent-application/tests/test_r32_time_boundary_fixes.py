"""Regression tests for the tester r32 time-window boundary bypass (B1).

The bound window is half-open: ``>= from`` and ``< to`` (07 §5.2), with
``> <from - 1 day>`` / ``<= <to - 1 day>`` accepted as the date-granularity
equivalents. Before this round the checker accepted *both* operators at the
same endpoint value — ``> from`` (drops the inclusive start row) and
``<= to`` (keeps the exclusive end row) — so three different totals carried
the same metric version. With a boundary row present on each side (Jan 1
inside, Feb 1 outside) the bound total is 340; the loose forms deliver
300 / 840 / 840. Only one operator/value pair per endpoint may carry the
metric's version.
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
    # one approved row on each window boundary: 2026-01-01 belongs to the
    # bound window (inclusive start), 2026-02-01 does not (exclusive end)
    return store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number", "unit": "CNY"},
            {"name": "Approved", "field_id": "approved", "value_type": "boolean"},
            {"name": "Occurred On", "field_id": "occurred_on", "value_type": "date"},
        ],
        rows=[
            ["north", 40, True, "2026-01-01"],
            ["north", 100, True, "2026-01-05"],
            ["south", 200, True, "2026-01-20"],
            ["south", 50, False, "2026-01-08"],
            ["north", 500, True, "2026-02-01"],
            ["south", 700, True, "2026-02-02"],
            ["north", 900, True, "2025-12-01"],
        ],
    )


def _metric():
    return {
        "draft_id": "m-r32",
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


# the bound window: >= '2026-01-01' AND < '2026-02-01' (bound total 340)
_WINDOW = "occurred_on >= '2026-01-01' AND occurred_on < '2026-02-01'"


@pytest.mark.parametrize(
    ("window", "endpoint_label"),
    [
        # ``> from`` drops the inclusive start row (delivers 300, not 340)
        ("occurred_on > '2026-01-01' AND occurred_on < '2026-02-01'", "start"),
        # ``<= to`` keeps the exclusive end row (delivers 840, not 340)
        ("occurred_on >= '2026-01-01' AND occurred_on <= '2026-02-01'", "end"),
        # BETWEEN inherits the hole: it expands to >= low AND <= high
        ("occurred_on BETWEEN '2026-01-01' AND '2026-02-01'", "end"),
    ],
)
def test_boundary_shifted_window_forms_are_rejected(
    runtime, ctx, caliber_case, window, endpoint_label
):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {window} GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "time range is not applied" in result.issues[0].message
    assert endpoint_label in result.issues[0].message


def test_narrowed_end_day_form_is_rejected(runtime, ctx, caliber_case):
    """``< <to - 1 day>`` is narrower than the bound exclusive end."""

    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        "WHERE approved = true AND occurred_on > '2025-12-31' "
        "AND occurred_on < '2026-01-31' GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"


@pytest.mark.parametrize(
    "window",
    [
        # the bound half-open window itself
        "occurred_on >= '2026-01-01' AND occurred_on < '2026-02-01'",
        # the date-granularity equivalent endpoints
        "occurred_on > '2025-12-31' AND occurred_on <= '2026-01-31'",
        # BETWEEN with the equivalent exclusive end
        "occurred_on BETWEEN '2026-01-01' AND '2026-01-31'",
    ],
)
def test_equivalent_windows_still_deliver_the_bound_total(
    runtime, ctx, caliber_case, window
):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        f"WHERE approved = true AND {window} GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok
    assert _delivered_total(runtime, ctx, table, requirement, metric, result) == 340.0
