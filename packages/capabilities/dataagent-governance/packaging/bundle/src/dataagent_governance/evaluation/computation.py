"""DA11.2.3 result grain and merge check (08 §5.4).

Tables are decoded through the **shared versioned codec**
(``dataagent_runtime.ports.tabular``, W0 §1.1): identity is ``field_id``
(human column names are never used as SQL/measure identities, W0 §1.2),
unknown payload versions are rejected instead of guessed, and only
``detail`` rows participate in sums and counts so totals are never
double-counted. DuckDB computes over the decoded tables; sqlglot parses the
SQL's join and grouping structure. Where the source side provides no totals
or consistent snapshot the item is ``unknown`` — row counts being close is
never accepted as correctness (08 §5.4). A join that the checker cannot
analyse (CROSS JOIN, non-equi, USING) is ``unknown`` too, never a vacuous
pass (review B8) — and coverage is tracked per join node, so one analysable
join cannot whitewash an unanalysed sibling (review r35 F4).
"""

from __future__ import annotations

import uuid
from typing import Any

import duckdb
import sqlglot
from pydantic import BaseModel, Field
from sqlglot import exp

from dataagent_contracts.core import ExecutableSpec, TableRef, VersionedRef
from dataagent_runtime.ports.tabular import DecodedTable, decode_table

from dataagent_governance.contracts import GrainCheckItem, GrainMergeReport, PaginationReceipt
from dataagent_governance.runtime.errors import invalid_input
from dataagent_runtime import operation


class CheckResultGrainAndMergeInput(BaseModel):
    spec: ExecutableSpec
    input_tables: list[TableRef] = Field(min_length=1)
    output_table: TableRef
    declared_grain: list[str] = Field(min_length=1)
    measure_fields: list[str] = Field(default_factory=list)
    pagination: PaginationReceipt | None = None


class CheckResultGrainAndMergeOutput(BaseModel):
    report: GrainMergeReport


def _decoded_table(rt, table: TableRef) -> DecodedTable:  # noqa: ANN001
    """Decode through the shared codec; unknown versions fail closed."""

    return decode_table(rt.content, table)


def _column_names(table: DecodedTable) -> list[str]:
    # W0 §1.2: the stable identity is field_id; SQL, declared grains and
    # measures all reference field ids, never the human column names.
    return list(table.field_ids)


def _duckdb_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE"
    return "VARCHAR"


def _register_table(
    con: duckdb.DuckDBPyConnection, name: str, table: DecodedTable
) -> None:
    """Register the decoded table's **detail rows** under their field ids."""

    names = _column_names(table)
    rows = [table.rows[index] for index in table.detail_rows()]
    # Scan for the first non-null value per column before falling back to
    # VARCHAR; rows may hold NULLs.
    types = []
    for index in range(len(names)):
        inferred = "VARCHAR"
        for row in rows:
            if row[index] is not None:
                inferred = _duckdb_type(row[index])
                break
        types.append(inferred)
    columns = ", ".join(f'"{n}" {t}' for n, t in zip(names, types))
    con.execute(f'CREATE TABLE "{name}" ({columns})')
    if rows:
        placeholders = ", ".join("?" for _ in names)
        con.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})', rows)


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _equi_pairs(
    on: exp.Expression,
    alias_to_table: dict[str, str],
    prior_sides: set[str],
    new_sides: set[str],
) -> list[tuple[str, str, str, str]]:
    """Equality pairs that genuinely constrain one join (r38 F6).

    Only an equality that is the ``ON`` expression itself or sits under AND
    conjunctions of it describes an equi-join; an ``EQ`` below an ``OR``
    (or inside arithmetic) does not, and treating it as a pair would
    under-report fan-out. An equality moreover only constrains *this* join
    when one side belongs to the table the join introduces and the other
    to the tables already in scope: ``l.id = l.id`` or a predicate over
    prior tables only says nothing about the newly joined input. The pair
    is normalized to ``(prior_table, prior_col, new_table, new_col)`` so
    the writing order of the equality never flips the cardinality reading.
    """

    pairs: list[tuple[str, str, str, str]] = []
    for eq in on.find_all(exp.EQ):
        # The equality must sit inside AND conjunctions of the ON clause
        # only: an EQ below an OR (or inside arithmetic) does not constrain
        # the join and must not be counted as an equi pair.
        if eq is on:
            constrained = True  # the whole ON clause is the equality
        else:
            constrained = False
            node = eq.parent
            while node is not None:
                if node is on:
                    # reached the root through ANDs only: fine when the
                    # root itself is an AND (ON a = b AND c = d)
                    constrained = isinstance(on, exp.And)
                    break
                if not isinstance(node, exp.And):
                    break
                node = node.parent
        if not constrained:
            continue
        left, right = eq.this, eq.expression
        if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
            continue
        left_side = left.table or left.name
        right_side = right.table or right.name
        if left_side in new_sides and right_side in prior_sides:
            prior_col, new_col = right, left
        elif right_side in new_sides and left_side in prior_sides:
            prior_col, new_col = left, right
        else:
            # same-side, both-new or prior-only equality: it does not
            # connect the newly joined table to the accumulated input.
            continue
        pairs.append(
            (
                alias_to_table.get(prior_col.table, prior_col.table),
                prior_col.name,
                alias_to_table.get(new_col.table, new_col.table),
                new_col.name,
            )
        )
    return pairs


def _scope_names(node: exp.Expression | None) -> set[str]:
    """Aliases/table names a subtree references (the join's own input)."""

    if node is None:
        return set()
    return {table.alias_or_name for table in node.find_all(exp.Table)}


def _join_analyses(sql: str) -> list[dict[str, Any]]:
    """Per-join support: every join node with its side-closed equality pairs.

    Coverage is tracked **per join node** (r35 F4) and **per join sides**
    (r38 F6): each join contributes the table it introduces (``new``) and
    is analysed against the tables already in scope (``prior`` — the FROM
    input plus every earlier join). A CROSS JOIN, a non-equi join, a
    ``USING`` join, or an ``ON`` that only mentions one side's tables
    carries no side-closed equality pair and stays unanalysed — one
    analysable join must never whitewash the fan-out of another.
    """

    tree = sqlglot.parse_one(sql)
    alias_to_table: dict[str, str] = {}
    for table in tree.find_all(exp.Table):
        alias = table.alias_or_name
        alias_to_table[alias] = table.name
    prior_sides: set[str] = set()
    from_clause = tree.args.get("from")
    if from_clause is not None:
        prior_sides |= _scope_names(from_clause.this)
    analyses: list[dict[str, Any]] = []
    for join in tree.find_all(exp.Join):
        on = join.args.get("on")
        new_sides = _scope_names(join.this)
        pairs = (
            _equi_pairs(on, alias_to_table, prior_sides, new_sides)
            if on is not None
            else []
        )
        analyses.append({"pairs": pairs})
        prior_sides |= new_sides
    return analyses


def _distinct_count(con: duckdb.DuckDBPyConnection, table: str, column: str) -> int:
    row = con.execute(
        f"SELECT COUNT(DISTINCT {_quoted(column)}) FROM {_quoted(table)}"
    ).fetchone()
    return int(row[0])


@operation(
    "DA11.2.3",
    input_model=CheckResultGrainAndMergeInput,
    output_model=CheckResultGrainAndMergeOutput,
    description="结果粒度与合并检查：粒度键唯一性、Join 基数与膨胀、度量守恒、分页回执",
    resource_fields=("input_tables", "output_table"),
)
def check_result_grain_and_merge(
    input_obj: CheckResultGrainAndMergeInput, ctx, rt  # noqa: ANN001
) -> CheckResultGrainAndMergeOutput:
    if input_obj.spec.backend_kind != "sql":
        raise invalid_input(
            "DA11.2.3 consumes SQL ExecutableSpecs; expression specs arrive with "
            "the application layer",
            target="spec.backend_kind",
        )
    con = duckdb.connect()
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")

    payloads: dict[str, DecodedTable] = {}
    for table in input_obj.input_tables:
        name = table.asset.id.split(":")[-1] or table.asset.id
        payloads[name] = _decoded_table(rt, table)
        _register_table(con, name, payloads[name])
    output_decoded = _decoded_table(rt, input_obj.output_table)
    _register_table(con, "da_output", output_decoded)
    output_names = _column_names(output_decoded)

    items: list[GrainCheckItem] = []

    # 1. Declared grain keys must be unique in the output.
    missing = [c for c in input_obj.declared_grain if c not in output_names]
    if missing:
        items.append(
            GrainCheckItem(
                check="grain_key_uniqueness",
                outcome="unknown",
                details=f"declared grain keys absent from output: {missing}",
                evidence={"missing_keys": missing},
            )
        )
    else:
        keys = ", ".join(_quoted(c) for c in input_obj.declared_grain)
        duplicates = con.execute(
            f"SELECT {_quoted(input_obj.declared_grain[0])}, COUNT(*) AS n "
            f"FROM da_output GROUP BY {keys} HAVING COUNT(*) > 1 LIMIT 5"
        ).fetchall()
        total = con.execute("SELECT COUNT(*) FROM da_output").fetchone()[0]
        if duplicates:
            items.append(
                GrainCheckItem(
                    check="grain_key_uniqueness",
                    outcome="fail",
                    details=(
                        f"declared grain {input_obj.declared_grain} is not unique: "
                        f"{len(duplicates)}+ duplicated keys over {total} rows"
                    ),
                    evidence={
                        "total_rows": int(total),
                        "sample_duplicates": [list(d) for d in duplicates],
                    },
                )
            )
        else:
            items.append(
                GrainCheckItem(
                    check="grain_key_uniqueness",
                    outcome="pass",
                    details=f"declared grain {input_obj.declared_grain} is unique over {total} rows",
                    evidence={"total_rows": int(total)},
                )
            )

    # 2. Join cardinality and row inflation.
    try:
        joins = _join_analyses(input_obj.spec.sql or "")
    except Exception as exc:  # noqa: BLE001 - unparseable SQL is caller input
        raise invalid_input(f"sqlglot could not parse the spec SQL: {exc}") from exc
    output_rows = con.execute("SELECT COUNT(*) FROM da_output").fetchone()[0]
    if not joins:
        items.append(
            GrainCheckItem(
                check="join_cardinality",
                # A spec without a join is vacuously satisfied: nothing can
                # fan out. "unknown" is reserved for unresolvable join sides.
                outcome="pass",
                details="no join in the spec; nothing to compare",
                evidence={"output_rows": int(output_rows)},
            )
        )
    else:
        # Coverage is tracked per join node (r35 F4): a join without a
        # supported equality predicate (CROSS JOIN, non-equi ON, USING)
        # still multiplies rows and its cardinality is simply not computable.
        # Such a join makes the check at least ``unknown`` — never a vacuous
        # pass washed clean by another, analysable join (B8).
        details: list[str] = []
        evidence: dict[str, Any] = {"joins": [], "output_rows": int(output_rows)}
        inflated = False
        unanalysed = 0
        for join_index, join in enumerate(joins):
            if not join["pairs"]:
                unanalysed += 1
                evidence["joins"].append(
                    {
                        "join_index": join_index,
                        "analyzed": False,
                        "reason": (
                            "no supported equality predicate "
                            "(CROSS JOIN / non-equi / USING)"
                        ),
                    }
                )
                continue
            for left_table, left_col, right_table, right_col in join["pairs"]:
                left_n = _distinct_count(con, left_table, left_col)
                right_n = _distinct_count(con, right_table, right_col)
                left_rows = con.execute(
                    f"SELECT COUNT(*) FROM {_quoted(left_table)}"
                ).fetchone()[0]
                right_rows = con.execute(
                    f"SELECT COUNT(*) FROM {_quoted(right_table)}"
                ).fetchone()[0]
                # Fan-out comes from duplicate keys on the *right* side (each
                # left row matches several right rows); duplicates on both
                # sides are N:M.
                left_dup = int(left_rows) > left_n
                right_dup = int(right_rows) > right_n
                if left_n == 0 or right_n == 0:
                    kind = "unknown"
                elif left_dup and right_dup:
                    kind = "N:M"
                elif right_dup:
                    kind = "1:N"
                elif left_dup:
                    kind = "N:1"
                else:
                    kind = "1:1"
                evidence["joins"].append(
                    {
                        "join_index": join_index,
                        "left": f"{left_table}.{left_col}",
                        "right": f"{right_table}.{right_col}",
                        "left_distinct": left_n,
                        "left_rows": int(left_rows),
                        "right_distinct": right_n,
                        "right_rows": int(right_rows),
                        "cardinality": kind,
                    }
                )
                if kind in {"1:N", "N:M"}:
                    inflated = True
                details.append(
                    f"{left_table}.{left_col} ({left_rows} rows / {left_n} keys) x "
                    f"{right_table}.{right_col} ({right_rows} rows / {right_n} keys) is {kind}"
                )
        if inflated:
            items.append(
                GrainCheckItem(
                    check="join_cardinality",
                    outcome="fail",
                    details="one-to-many join causes row fan-out: " + "; ".join(details),
                    evidence=evidence,
                )
            )
        elif unanalysed:
            items.append(
                GrainCheckItem(
                    check="join_cardinality",
                    outcome="unknown",
                    details=(
                        f"{unanalysed} of {len(joins)} joins carry no supported "
                        "equality predicate (CROSS JOIN / non-equi / USING); their "
                        "cardinality and row inflation cannot be computed and are "
                        "not assumed safe"
                    ),
                    evidence=evidence,
                )
            )
        else:
            items.append(
                GrainCheckItem(
                    check="join_cardinality",
                    outcome="pass",
                    details="; ".join(details),
                    evidence=evidence,
                )
            )

    # 3. Measure conservation (only computable without filters).
    tree = sqlglot.parse_one(input_obj.spec.sql or "")
    has_filter = bool(list(tree.find_all(exp.Where))) or bool(list(tree.find_all(exp.Having)))
    if not input_obj.measure_fields:
        items.append(
            GrainCheckItem(
                check="measure_conservation",
                outcome="unknown",
                details="no measure fields supplied; conservation not computable",
            )
        )
    elif has_filter:
        items.append(
            GrainCheckItem(
                check="measure_conservation",
                outcome="unknown",
                details="spec filters rows (WHERE/HAVING); source totals are not comparable",
            )
        )
    else:
        base_table = next(iter(payloads))
        base_names = _column_names(payloads[base_table])
        sums_ok, notes, evidence = True, [], {}
        for measure in input_obj.measure_fields:
            if measure not in output_names or measure not in base_names:
                sums_ok = False
                notes.append(f"measure {measure} absent from output or input")
                continue
            source_sum = con.execute(
                f"SELECT SUM(TRY_CAST({_quoted(measure)} AS DOUBLE)) "
                f"FROM {_quoted(base_table)}"
            ).fetchone()[0]
            output_sum = con.execute(
                f"SELECT SUM(TRY_CAST({_quoted(measure)} AS DOUBLE)) FROM da_output"
            ).fetchone()[0]
            evidence[measure] = {"source_sum": source_sum, "output_sum": output_sum}
            if source_sum is None or output_sum is None or abs(source_sum - output_sum) > 1e-9:
                sums_ok = False
                notes.append(
                    f"measure {measure}: source sum {source_sum} != output sum {output_sum}"
                )
        if sums_ok and not notes:
            items.append(
                GrainCheckItem(
                    check="measure_conservation",
                    outcome="pass",
                    details="measure totals are conserved through the merge",
                    evidence=evidence,
                )
            )
        else:
            items.append(
                GrainCheckItem(
                    check="measure_conservation",
                    outcome="fail",
                    details="; ".join(notes),
                    evidence=evidence,
                )
            )

    # 4. Pagination / truncation receipt completeness.
    if input_obj.pagination is None:
        items.append(
            GrainCheckItem(
                check="pagination_completeness",
                outcome="unknown",
                details="no pagination receipt supplied",
            )
        )
    else:
        receipt = input_obj.pagination
        expected = receipt.declared_total_rows
        if receipt.truncated:
            items.append(
                GrainCheckItem(
                    check="pagination_completeness",
                    outcome="fail",
                    details="receipt is marked truncated",
                    evidence={"declared_total_rows": expected, "output_rows": int(output_rows)},
                )
            )
        elif expected is None:
            items.append(
                GrainCheckItem(
                    check="pagination_completeness",
                    outcome="unknown",
                    details="receipt carries no declared total; completeness not computable",
                )
            )
        elif int(expected) != int(output_rows):
            items.append(
                GrainCheckItem(
                    check="pagination_completeness",
                    outcome="fail",
                    details=(
                        f"receipt declares {expected} rows but the output has {output_rows}"
                    ),
                    evidence={"declared_total_rows": int(expected), "output_rows": int(output_rows)},
                )
            )
        else:
            items.append(
                GrainCheckItem(
                    check="pagination_completeness",
                    outcome="pass",
                    details=f"receipt matches the output ({output_rows} rows)",
                    evidence={"declared_total_rows": int(expected), "output_rows": int(output_rows)},
                )
            )

    outcomes = [item.outcome for item in items]
    overall = "fail" if "fail" in outcomes else ("unknown" if "unknown" in outcomes else "pass")
    report = GrainMergeReport(
        report_id=f"grain:{uuid.uuid4().hex[:12]}",
        spec_ref=VersionedRef(id=input_obj.spec.spec_id, revision=input_obj.spec.revision),
        declared_grain=input_obj.declared_grain,
        items=items,
        overall=overall,
    )
    return CheckResultGrainAndMergeOutput(report=report)


__all__ = ["check_result_grain_and_merge"]
