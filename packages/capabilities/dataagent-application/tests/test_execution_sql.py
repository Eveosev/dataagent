"""DA07.1.3 (DuckDB execution) and DA07.10.1 (engine alignment) (07 §5.2 / §5.4)."""

from __future__ import annotations

import pytest

from dataagent_contracts.core import CapabilityStatus

from dataagent_application.execution import engines, sql
from dataagent_runtime.errors import CapabilityError

from tests.conftest import store_table


def _spec(sql_text):
    return {
        "spec_id": "sqlspec1",
        "revision": "r1",
        "backend_kind": "sql",
        "expression_or_call": {"sql": sql_text, "dialect": "duckdb"},
    }


def _table_payload(table):
    return {
        "asset": table.asset.model_dump(mode="json"),
        "schema_ref": "schema:x@r1",
        "data_ref": table.data_ref,
    }


def test_execute_scalar_sum_excludes_total_row(runtime, ctx, expense_table):
    from dataagent_application.planning.expressions import _sql_table_name

    sql_name = _sql_table_name(expense_table)
    spec = _spec(f"SELECT sum(amount) AS total FROM {sql_name}")
    result = sql.execute_duckdb_sql(
        sql.ExecuteDuckdbSqlInput.model_validate(
            {"spec": spec, "table_refs": [_table_payload(expense_table)], "grain": "total"}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    # 100 + 200, NOT 600: the grand-total row is excluded (W1a double-count counterexample).
    assert result.data.result.value == 300
    assert result.data.result.sql_digest.startswith("sha256:")
    assert result.data.result.engine_binding.engine_id == "duckdb"
    assert any(i.code == "da07.table_rows_excluded" for i in result.issues)


def test_execute_group_by_returns_table_result(runtime, ctx, expense_table):
    from dataagent_application.planning.expressions import _sql_table_name

    sql_name = _sql_table_name(expense_table)
    spec = _spec(
        f"SELECT region, sum(amount) AS total FROM {sql_name} GROUP BY region ORDER BY region"
    )
    result = sql.execute_duckdb_sql(
        sql.ExecuteDuckdbSqlInput.model_validate(
            {"spec": spec, "table_refs": [_table_payload(expense_table)], "grain": "region"}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.result.form == "table"
    table = result.data.result.table_ref
    loaded = runtime.versions.get("computed_table", table.id, table.revision)
    assert loaded["row_count"] == 2
    from dataagent_runtime.ports.tabular import decode_table_payload

    decoded = decode_table_payload(runtime.content.get_json(loaded["data_ref"]))
    assert decoded.rows == (("north", 100.0), ("south", 200.0))


def test_execute_row_budget_truncates_and_flags_completeness(runtime, ctx):
    from dataagent_application.planning.expressions import _sql_table_name

    table = store_table(
        runtime,
        columns=[{"name": "N", "field_id": "n", "value_type": "number"}],
        rows=[[i] for i in range(10)],
    )
    sql_name = _sql_table_name(table)
    spec = _spec(f"SELECT n FROM {sql_name}")
    result = sql.execute_duckdb_sql(
        sql.ExecuteDuckdbSqlInput.model_validate(
            {"spec": spec, "table_refs": [_table_payload(table)], "max_rows": 3}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.partial
    assert result.data.truncated is True
    assert result.data.row_count == 3
    assert result.data.result.completeness.extent.value == "truncated"


@pytest.mark.parametrize(
    "bad_sql",
    [
        "SELECT * FROM other",
        "SELECT 1; SELECT 2",
        "SELECT * FROM read_csv('x.csv')",
        "ATTACH 'x.db' AS x",
        "COPY (SELECT 1) TO 'x.csv'",
    ],
)
def test_execute_rejects_invalid_sql_before_running(runtime, ctx, expense_table, bad_sql):
    from pydantic import ValidationError

    spec = _spec(bad_sql)
    # "SELECT 1; SELECT 2" is rejected by the ExecutableSpec contract itself
    # (single statement); the rest by the sqlglot validator.
    with pytest.raises((CapabilityError, ValidationError)):
        sql.execute_duckdb_sql(
            sql.ExecuteDuckdbSqlInput.model_validate(
                {"spec": spec, "table_refs": [_table_payload(expense_table)]}
            ),
            ctx,
            runtime,
        )


def test_execute_requires_sql_backend(runtime, ctx, expense_table):
    spec = {
        "spec_id": "s",
        "revision": "r1",
        "backend_kind": "expression",
        "expression_or_call": {"op": "literal", "value": True},
    }
    with pytest.raises(CapabilityError, match="backend_kind=sql"):
        sql.execute_duckdb_sql(
            sql.ExecuteDuckdbSqlInput.model_validate(
                {"spec": spec, "table_refs": [_table_payload(expense_table)]}
            ),
            ctx,
            runtime,
        )


# --- DA07.10.1 ---------------------------------------------------------------


def test_engine_alignment_reports_installed_version(runtime, ctx):
    result = engines.acquire_and_align_engine(
        engines.AcquireAndAlignEngineInput.model_validate({"engine_id": "duckdb"}), ctx, runtime
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.binding.engine_id == "duckdb"
    assert result.data.installed_version


def test_engine_version_mismatch_fails_closed(runtime, ctx):
    result = engines.acquire_and_align_engine(
        engines.AcquireAndAlignEngineInput.model_validate(
            {"engine_id": "duckdb", "expected_version": "0.0.1-not-real"}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da07.engine_version_mismatch"


def test_engine_wrong_wheel_digest_fails_closed(runtime, ctx):
    result = engines.acquire_and_align_engine(
        engines.AcquireAndAlignEngineInput.model_validate(
            {"engine_id": "duckdb", "wheel_digest": "sha256:" + "f" * 64}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code in {"da07.engine_version_mismatch", "da07.engine_digest_unavailable"}


def test_engine_unknown_id_rejected(runtime, ctx):
    with pytest.raises(CapabilityError, match="unknown engine_id"):
        engines.acquire_and_align_engine(
            engines.AcquireAndAlignEngineInput.model_validate({"engine_id": "spark"}), ctx, runtime
        )
