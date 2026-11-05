"""Local DuckDB execution adapter (DA07.1.3, 07 §5.2).

The SQL is re-validated (single SELECT, bound tables, function blacklist)
before execution. The bound tables are loaded from the shared content store
through the versioned table codec; non-detail rows (subtotal/total/title)
are excluded so aggregates never double count. DuckDB runs in-process with
``enable_external_access=false``; the timeout and row cap come from the
``Budget``. Output is a ``ComputedResult`` with the SQL digest and engine
binding (07 §5.2 / contracts round 5).
"""

from __future__ import annotations

import concurrent.futures
from typing import Any

import duckdb
from pydantic import BaseModel, ConfigDict, Field as PydanticField

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    ComputedResult,
    EngineBinding,
    ExecutableSpec,
    Issue,
    Severity,
    TimeRange,
    VersionedRef,
)

from dataagent_application import helpers
from dataagent_application.execution import engines
from dataagent_application.planning.expressions import (
    _sql_table_name,
    sql_digest,
    validate_single_select_sql,
)
from dataagent_runtime.errors import invalid_input
from dataagent_runtime.registry import operation

SQL_ENGINE_ID = "duckdb"


class _IO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExecuteDuckdbSqlInput(_IO):
    spec: ExecutableSpec
    table_refs: list[dict[str, Any]] = PydanticField(default_factory=list)
    semantic_versions: list[VersionedRef] = PydanticField(default_factory=list)
    filters_applied: list[str] = PydanticField(default_factory=list)
    time_range: dict[str, Any] | None = None
    grain: str = "row"
    unit: str | None = None
    assumptions: list[str] = PydanticField(default_factory=list)
    max_rows: int | None = PydanticField(default=None, ge=1)
    max_seconds: float | None = PydanticField(default=None, gt=0)


class ExecuteDuckdbSqlOutput(_IO):
    result: ComputedResult
    row_count: int
    truncated: bool


_COLUMN_TYPES = {"number": "DOUBLE", "integer": "BIGINT", "float": "DOUBLE", "decimal": "DOUBLE"}


def _create_connection() -> duckdb.DuckDBPyConnection:
    # 07 §5.2: external access disabled and the configuration locked so the
    # SQL under execution cannot relax these settings itself.
    return duckdb.connect(
        config={
            "enable_external_access": False,
            "lock_configuration": True,
            "allow_unsigned_extensions": False,
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
        }
    )


def _load_table(conn: duckdb.DuckDBPyConnection, table_ref: Any, table: Any) -> tuple[str, dict[str, int]]:
    """Register one decoded table as a temp table of detail rows only."""

    sql_name = _sql_table_name(table_ref)
    detail = table.detail_rows()
    col_sql: list[str] = []
    for index, column in enumerate(table.columns):
        declared = _COLUMN_TYPES.get((column.value_type or "").lower())
        if declared is None:
            cells = [table.rows[r][index] for r in detail]
            non_null = [c for c in cells if c is not None]
            if non_null and all(
                isinstance(c, (int, float)) and not isinstance(c, bool) for c in non_null
            ):
                declared = "DOUBLE"
            elif non_null and all(isinstance(c, bool) for c in non_null):
                declared = "BOOLEAN"
            else:
                declared = "VARCHAR"
        col_sql.append(f'"{column.field_id}" {declared}')
    conn.execute(f"CREATE TEMP TABLE \"{sql_name}\" ({', '.join(col_sql)})")
    placeholders = ", ".join("?" for _ in table.columns)
    rows = [list(table.rows[r]) for r in detail]
    if rows:
        conn.executemany(f'INSERT INTO "{sql_name}" VALUES ({placeholders})', rows)
    return sql_name, table.non_detail_summary()


@operation(
    "DA07.1.3",
    input_model=ExecuteDuckdbSqlInput,
    output_model=ExecuteDuckdbSqlOutput,
    description="本地 DuckDB 执行适配：进程内连接、外部访问禁用、预算行数/超时、SQL digest 与 EngineBinding（DA07.1.3）",
    idempotent=True,
)
def execute_duckdb_sql(
    data: ExecuteDuckdbSqlInput, ctx: CallContext, runtime
) -> CapabilityResult[ExecuteDuckdbSqlOutput]:
    from dataagent_contracts.core import TableRef

    if data.spec.backend_kind != "sql":
        raise invalid_input(
            f"execute_duckdb_sql requires backend_kind=sql, got {data.spec.backend_kind}",
            target="spec.backend_kind",
        )
    sql = data.spec.sql
    if sql is None:
        raise invalid_input("spec is not a SQL spec", target="spec")
    # 07 §5.4: the spec's EngineBinding is compared against the installed
    # (and locked) DuckDB before execution; mismatch fails closed.
    if data.spec.engine_binding is not None:
        binding_issue = engines.engine_binding_issue(
            data.spec.engine_binding, expected_engine_id=SQL_ENGINE_ID
        )
        if binding_issue is not None:
            return CapabilityResult[ExecuteDuckdbSqlOutput](
                status=CapabilityStatus.failed, issues=[binding_issue]
            )
    table_refs = [TableRef.model_validate(item) for item in data.table_refs]
    names = {_sql_table_name(ref) for ref in table_refs}
    names |= {ref.asset.id for ref in table_refs}
    errors = validate_single_select_sql(sql, names)
    if errors:
        raise invalid_input("SQL validation failed: " + "; ".join(errors), target="spec.sql")

    issues: list[Issue] = []
    conn = _create_connection()
    try:
        excluded_total: dict[str, int] = {}
        for table_ref in table_refs:
            table = helpers.load_table(runtime, table_ref)
            _sql_name, excluded = _load_table(conn, table_ref, table)
            excluded_total.update(excluded)
        if excluded_total:
            issues.append(
                Issue(
                    code="da07.table_rows_excluded",
                    severity=Severity.info,
                    message=(
                        "non-detail rows excluded from the loaded tables to avoid double "
                        "counting: "
                        + ", ".join(f"{k}={v}" for k, v in sorted(excluded_total.items()))
                    ),
                    retryable=False,
                )
            )
        max_rows = data.max_rows or (ctx.budget.max_rows if ctx.budget else None) or 10000
        max_seconds = data.max_seconds or (ctx.budget.max_seconds if ctx.budget else None)

        def run() -> Any:
            return conn.execute(sql).fetchmany(max_rows + 1)

        if max_seconds is not None:
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                future = pool.submit(run)
                try:
                    fetched = future.result(timeout=float(max_seconds))
                except concurrent.futures.TimeoutError:
                    conn.close()
                    pool.shutdown(wait=False)
                    return CapabilityResult[ExecuteDuckdbSqlOutput](
                        status=CapabilityStatus.failed,
                        issues=[
                            Issue(
                                code="timeout",
                                severity=Severity.error,
                                message=f"SQL exceeded the budget of {max_seconds}s",
                                retryable=True,
                            )
                        ],
                    )
            finally:
                pool.shutdown(wait=False)
        else:
            fetched = run()
        columns = [d[0] for d in (conn.description or [])]
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - best effort cleanup
            pass

    truncated = len(fetched) > max_rows
    rows = fetched[:max_rows]
    if truncated:
        issues.append(
            Issue(
                code="da07.row_limit_reached",
                severity=Severity.warning,
                message=f"result truncated at {max_rows} rows (budget)",
                retryable=True,
            )
        )
    if not columns and rows:
        columns = [f"col{i + 1}" for i in range(len(rows[0]))]

    scalar = len(columns) == 1 and len(rows) == 1
    target_ref = (
        VersionedRef(id=table_refs[0].asset.id, revision=table_refs[0].asset.revision)
        if table_refs
        else VersionedRef(id=data.spec.spec_id, revision=data.spec.revision)
    )
    if scalar:
        value = rows[0][0]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value) if isinstance(value, float) else int(value)
        result = ComputedResult(
            result_id="res:" + sql_digest(f"{sql}:{value}").split(":", 1)[1][:16],
            target_ref=target_ref,
            form="scalar",
            value=value,
            unit=data.unit,
            grain=data.grain,
            filters_applied=data.filters_applied,
            time_range=TimeRange.model_validate(data.time_range) if data.time_range else None,
            semantic_versions=list(data.semantic_versions),
            assumptions=data.assumptions,
            evidence_refs=[f"spec:{data.spec.spec_id}"],
            completeness=helpers.truncated(
                "SQL execution", reason="row cap reached", observed={"rows": max_rows}
            )
            if truncated
            else helpers.complete("SQL execution", {"rows": len(rows)}),
            sql_digest=sql_digest(sql),
            engine_binding=EngineBinding(
                engine_id=SQL_ENGINE_ID, engine_version=duckdb.__version__
            ),
        )
    else:
        payload_columns = [
            {"name": name, "field_id": name, "value_type": "unknown"} for name in columns
        ]
        table_ref_v, digest = helpers.store_table(runtime, payload_columns, [list(r) for r in rows])
        result = ComputedResult(
            result_id="res:" + sql_digest(f"{sql}:{digest}").split(":", 1)[1][:16],
            target_ref=target_ref,
            form="table",
            table_ref=table_ref_v,
            unit=data.unit,
            grain=data.grain,
            filters_applied=data.filters_applied,
            time_range=TimeRange.model_validate(data.time_range) if data.time_range else None,
            semantic_versions=list(data.semantic_versions),
            assumptions=data.assumptions,
            evidence_refs=[f"spec:{data.spec.spec_id}"],
            completeness=helpers.truncated(
                "SQL execution", reason="row cap reached", observed={"rows": max_rows}
            )
            if truncated
            else helpers.complete("SQL execution", {"rows": len(rows)}),
            sql_digest=sql_digest(sql),
            engine_binding=EngineBinding(
                engine_id=SQL_ENGINE_ID, engine_version=duckdb.__version__
            ),
        )
    status = CapabilityStatus.partial if truncated else CapabilityStatus.ok
    return CapabilityResult[ExecuteDuckdbSqlOutput](
        status=status,
        data=ExecuteDuckdbSqlOutput(result=result, row_count=len(rows), truncated=truncated),
        issues=issues,
    )
