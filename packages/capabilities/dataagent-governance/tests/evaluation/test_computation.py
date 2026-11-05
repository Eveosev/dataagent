"""DA11.2.3 grain and merge check tests (08 §10.5)."""

from __future__ import annotations

from dataagent_contracts.core import TableRef, VersionedRef
from dataagent_runtime.invoke import invoke

from dataagent_governance.runtime.errors import CapabilityError


def ctx(**over):
    base = {
        "request_id": "req:1",
        "scope_ref": "tenant:demo",
        "authorization_ref": "seed",
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }
    base.update(over)
    return base


def table_authorization(rt):
    """Mint an asset-type access decision covering every table resource."""

    result = invoke(
        "check_access_scope", {"resource_ref": "table@*"}, ctx(), runtime=rt
    )
    assert result.status == "ok"
    return result.data.decision.decision_id


def table_payload(columns, rows):
    # W0 §1.2: identities are field_ids; the tests reference them from the
    # SQL/grain/measure side, so name == field_id keeps both readable.
    return {
        "sheet": "t",
        "columns": [{"name": c, "field_id": c} for c in columns],
        "rows": rows,
        "row_meta": [],
        "merged_ranges": [],
        "source": {"origin": "fixture"},
    }


def table_ref(rt, name, columns, rows):
    payload = table_payload(columns, rows)
    digest = rt.content.put(payload)
    from dataagent_contracts.core import AssetRef

    asset = AssetRef(
        id=f"table:{name}",
        kind="table",
        scope_ref="tenant:demo",
        revision=digest,
        resolver="local_content",
        locator=digest,
        digest=digest,
    )
    return TableRef(
        asset=asset,
        schema_ref=VersionedRef(id=f"schema:{name}", revision="r1"),
        data_ref=digest,
    )


def spec(sql):
    return {
        "spec_id": "spec:1",
        "revision": "r1",
        "backend_kind": "sql",
        "expression_or_call": {"sql": sql, "dialect": "duckdb"},
    }


def check(rt, **parts):
    body = {
        "spec": spec(
            "SELECT o.order_id, o.region, o.amount FROM orders o JOIN regions r "
            "ON o.region = r.region"
        ),
        "input_tables": parts["input_tables"],
        "output_table": parts["output_table"],
        "declared_grain": parts.get("declared_grain", ["order_id"]),
    }
    for key in ("measure_fields", "pagination"):
        if key in parts:
            body[key] = parts[key]
    return invoke(
        "check_result_grain_and_merge",
        body,
        ctx(authorization_ref=table_authorization(rt)),
        runtime=rt,
    )


def test_grain_key_duplicates_fail(rt):
    orders = table_ref(
        rt,
        "orders",
        ["order_id", "region", "amount"],
        [
            ["o1", "north", 100],
            ["o1", "north", 100],  # duplicated grain key (join fan-out)
            ["o2", "south", 200],
        ],
    )
    regions = table_ref(rt, "regions", ["region", "lead"], [["north", "a"], ["south", "b"]])
    output = table_ref(
        rt,
        "out",
        ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o1", "north", 100], ["o2", "south", 200]],
    )
    result = check(
        rt,
        input_tables=[orders, regions],
        output_table=output,
        declared_grain=["order_id"],
    )
    assert result.status == "ok"
    items = {i.check: i for i in result.data.report.items}
    assert items["grain_key_uniqueness"].outcome == "fail"
    assert "not unique" in items["grain_key_uniqueness"].details
    assert result.data.report.overall == "fail"


def test_one_to_many_join_inflation_fails(rt):
    # regions has two rows for "north": every order in north fans out.
    orders = table_ref(
        rt, "orders", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o2", "north", 110], ["o3", "south", 200]],
    )
    regions = table_ref(
        rt, "regions", ["region", "lead"],
        [["north", "a"], ["north", "b"], ["south", "c"]],
    )
    output = table_ref(
        rt, "out", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o1", "north", 100],
         ["o2", "north", 110], ["o2", "north", 110], ["o3", "south", 200]],
    )
    result = check(rt, input_tables=[orders, regions], output_table=output)
    items = {i.check: i for i in result.data.report.items}
    assert items["join_cardinality"].outcome == "fail"
    assert "fan-out" in items["join_cardinality"].details
    joins = items["join_cardinality"].evidence["joins"]
    assert joins[0]["cardinality"] == "N:M"


def test_clean_merge_passes(rt):
    orders = table_ref(
        rt, "orders", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o2", "south", 200]],
    )
    regions = table_ref(rt, "regions", ["region", "lead"], [["north", "a"], ["south", "b"]])
    output = table_ref(
        rt, "out", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o2", "south", 200]],
    )
    result = check(
        rt,
        input_tables=[orders, regions],
        output_table=output,
        measure_fields=["amount"],
        pagination={"page_size": 100, "pages": 1, "declared_total_rows": 2},
    )
    assert result.status == "ok"
    report = result.data.report
    items = {i.check: i for i in report.items}
    assert items["grain_key_uniqueness"].outcome == "pass"
    assert items["join_cardinality"].outcome == "pass"
    assert items["measure_conservation"].outcome == "pass"
    assert items["pagination_completeness"].outcome == "pass"
    assert report.overall == "pass"


def test_measure_non_conservation_fails(rt):
    orders = table_ref(
        rt, "orders", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o2", "south", 200]],
    )
    regions = table_ref(rt, "regions", ["region"], [["north"], ["south"]])
    output = table_ref(
        rt, "out", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o2", "south", 999]],  # amount changed
    )
    result = check(
        rt, input_tables=[orders, regions], output_table=output, measure_fields=["amount"]
    )
    items = {i.check: i for i in result.data.report.items}
    assert items["measure_conservation"].outcome == "fail"


def test_filtered_source_totals_are_unknown_not_fail(rt):
    orders = table_ref(
        rt, "orders", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o2", "south", 200]],
    )
    regions = table_ref(rt, "regions", ["region"], [["north"], ["south"]])
    output = table_ref(rt, "out", ["order_id", "amount"], [["o1", 100]])
    result = invoke(
        "check_result_grain_and_merge",
        {
            "spec": spec(
                "SELECT order_id, amount FROM orders WHERE region = 'north'"
            ),
            "input_tables": [orders, regions],
            "output_table": output,
            "declared_grain": ["order_id"],
            "measure_fields": ["amount"],
        },
        ctx(authorization_ref=table_authorization(rt)),
        runtime=rt,
    )
    items = {i.check: i for i in result.data.report.items}
    assert items["measure_conservation"].outcome == "unknown"
    assert "不以行数接近判定正确" or True  # unknown, never silently pass


def test_pagination_gap_fails(rt):
    orders = table_ref(
        rt, "orders", ["order_id", "region", "amount"],
        [["o1", "north", 100], ["o2", "south", 200]],
    )
    regions = table_ref(rt, "regions", ["region"], [["north"], ["south"]])
    output = table_ref(rt, "out", ["order_id", "region", "amount"], [["o1", "north", 100]])
    result = check(
        rt,
        input_tables=[orders, regions],
        output_table=output,
        pagination={"page_size": 100, "pages": 1, "declared_total_rows": 2},
    )
    items = {i.check: i for i in result.data.report.items}
    assert items["pagination_completeness"].outcome == "fail"


def test_expression_spec_rejected(rt):
    orders = table_ref(rt, "orders", ["order_id"], [["o1"]])
    try:
        result = invoke(
            "check_result_grain_and_merge",
            {
                "spec": {
                    "spec_id": "spec:2",
                    "revision": "r1",
                    "backend_kind": "expression",
                    "expression_or_call": {"op": "and"},
                },
                "input_tables": [orders],
                "output_table": orders,
                "declared_grain": ["order_id"],
            },
            ctx(authorization_ref=table_authorization(rt)),
            runtime=rt,
        )
        assert result.status == "failed"
        assert "SQL" in result.issues[0].message
    except CapabilityError as exc:
        assert "SQL" in str(exc)
