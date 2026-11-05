"""DA07.5.1 / DA07.5.2: three-valued interpreter over the closed AST (07 §5.1)."""

from __future__ import annotations

import pytest

from dataagent_contracts.core import (
    CapabilityStatus,
    EngineBinding,
    ExecutableSpec,
)

from dataagent_application.execution import expressions as exe
from dataagent_runtime.errors import CapabilityError


def _spec(ast, spec_id="s1"):
    return ExecutableSpec(
        spec_id=spec_id,
        revision="r1",
        backend_kind="expression",
        expression_or_call=ast,
        engine_binding=EngineBinding(engine_id="dataagent-expression", engine_version="0.1.0"),
    )


def _record(fields):
    return {
        "asset": {
            "id": "rec:1",
            "kind": "record",
            "scope_ref": "scope-1",
            "revision": "r1",
            "resolver": "content",
            "locator": "sha256:" + "0" * 64,
        },
        "document_ref": "doc:1@r1",
        "target_schema_ref": "schema:x@r1",
        "fields": fields,
    }


_ANCHOR = {
    "source_ref": "invoice-1",
    "source_revision": "r1",
    "selector": {"kind": "excel_cell", "sheet": "S1", "range": "B2"},
}


def _field(field_id, value, *, status="extracted", value_type=None, anchors=None):
    item = {
        "field_id": field_id,
        "status": status,
        "value_type": value_type or ("number" if isinstance(value, (int, float)) else "string"),
    }
    if value is not None:
        item["value"] = value
    if status == "extracted":
        item["evidence"] = anchors or [dict(_ANCHOR)]
    elif anchors:
        item["evidence"] = anchors
    if status == "conflict":
        item["alternatives"] = [value, value]
    return item


LE = {
    "op": "le",
    "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 5000}],
}


def test_missing_value_yields_unknown_not_false(runtime, ctx):
    record = _record([_field("amount", None, status="missing")])
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(LE), "record": record}), ctx, runtime
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.assessment.verdict == "unknown"
    assert "amount" in result.data.assessment.unknowns


def test_conflict_value_yields_unknown(runtime, ctx):
    record = _record([_field("amount", 999, status="conflict")])
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(LE), "record": record}), ctx, runtime
    )
    assert result.data.assessment.verdict == "unknown"


def test_pass_fail_and_evidence(runtime, ctx):
    ok = _record([_field("amount", 1200)])
    bad = _record([_field("amount", 9000)])
    r1 = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(LE), "record": ok}), ctx, runtime
    )
    r2 = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(LE), "record": bad}), ctx, runtime
    )
    assert r1.data.assessment.verdict == "pass"
    assert r2.data.assessment.verdict == "fail"
    assert r1.data.assessment.evidence[0].id == "field:amount"
    assert r1.data.assessment.evidence[0].value == 1200


def test_kleene_and_or_not(runtime, ctx):
    unknown = _record([_field("amount", None, status="missing")])
    ast_true = {"op": "literal", "value": True}
    # unknown AND false = false; unknown AND true = unknown; unknown OR true = true
    a = {"op": "and", "args": [LE, ast_true]}
    b = {"op": "and", "args": [LE, {"op": "literal", "value": False}]}
    c = {"op": "or", "args": [LE, ast_true]}
    d = {"op": "not", "args": [LE]}
    for ast, expected in ((a, "unknown"), (b, "fail"), (c, "pass"), (d, "unknown")):
        result = exe.evaluate_scalar_expression(
            exe.EvaluateScalarInput.model_validate({"spec": _spec(ast), "record": unknown}), ctx, runtime
        )
        assert result.data.assessment.verdict == expected, ast


def test_is_missing_is_decidable_even_when_value_missing(runtime, ctx):
    record = _record([_field("amount", None, status="missing")])
    ast = {"op": "is_missing", "args": [{"op": "field", "field_id": "amount"}]}
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(ast), "record": record}), ctx, runtime
    )
    assert result.data.assessment.verdict == "pass"


def test_type_mismatch_fails_with_issue(runtime, ctx):
    record = _record([_field("region", "north")])
    ast = {
        "op": "le",
        "args": [{"op": "field", "field_id": "region"}, {"op": "literal", "value": 5000}],
    }
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(ast), "record": record}), ctx, runtime
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da07.expression_type_mismatch"


def test_exception_hit_yields_not_applicable_and_unknown_exception_stays_unknown(runtime, ctx):
    record = _record([_field("amount", 9000)])
    exception = _spec(
        {"op": "eq", "args": [{"op": "field", "field_id": "region"}, {"op": "literal", "value": "vip"}]},
        spec_id="exc1",
    )
    record_vip = _record([_field("amount", 9000), _field("region", "vip")])
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate(
            {"spec": _spec(LE), "exceptions": [exception.model_dump(mode="json")], "record": record_vip}
        ),
        ctx,
        runtime,
    )
    assert result.data.assessment.verdict == "not_applicable"

    unknown_exception = _spec(
        {"op": "eq", "args": [{"op": "field", "field_id": "note"}, {"op": "literal", "value": "x"}]},
        spec_id="exc2",
    )
    result2 = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate(
            {
                "spec": _spec(LE),
                "exceptions": [unknown_exception.model_dump(mode="json")],
                "record": _record([_field("amount", 100), _field("note", None, status="missing")]),
            }
        ),
        ctx,
        runtime,
    )
    assert result2.data.assessment.verdict == "unknown"


def test_applicable_false_yields_not_applicable(runtime, ctx):
    record = _record([_field("amount", 100)])
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(LE), "record": record, "applicable": False}),
        ctx,
        runtime,
    )
    assert result.data.assessment.verdict == "not_applicable"


def test_scalar_requires_expression_backend(runtime, ctx):
    record = _record([_field("amount", 100)])
    sql_spec = {
        "spec_id": "s2",
        "revision": "r1",
        "backend_kind": "sql",
        "expression_or_call": {"sql": "SELECT 1"},
    }
    with pytest.raises(CapabilityError, match="backend_kind=expression"):
        exe.evaluate_scalar_expression(
            exe.EvaluateScalarInput.model_validate({"spec": sql_spec, "record": record}), ctx, runtime
        )


# --- DA07.5.2 table -------------------------------------------------------------


def _table_payload(table):
    return {
        "asset": table.asset.model_dump(mode="json"),
        "schema_ref": "schema:x@r1",
        "data_ref": table.data_ref,
    }


def test_table_evaluation_per_row_with_counts(runtime, ctx, expense_table):
    ast = {
        "op": "gt",
        "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 150}],
    }
    result = exe.evaluate_table_expression(
        exe.EvaluateTableInput.model_validate(
            {"spec": _spec(ast), "table_ref": _table_payload(expense_table)}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.counts == {"pass": 1, "fail": 1, "unknown": 0, "not_applicable": 0, "error": 0}
    assert result.data.assessment.verdict == "unknown"  # mixed
    assert any(i.code == "da07.table_rows_excluded" for i in result.issues)


def test_table_missing_cell_gives_row_unknown_not_fail(runtime, ctx, expense_table):
    from tests.conftest import store_table

    table = store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number"},
        ],
        rows=[["north", None], ["south", 5000]],
    )
    ast = LE
    result = exe.evaluate_table_expression(
        exe.EvaluateTableInput.model_validate({"spec": _spec(ast), "table_ref": _table_payload(table)}),
        ctx,
        runtime,
    )
    assert result.data.counts["unknown"] == 1
    assert result.data.counts["fail"] == 0  # unknown never folds to fail


def test_table_all_pass_yields_pass(runtime, ctx, expense_table):
    ast = {
        "op": "lt",
        "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 10000}],
    }
    result = exe.evaluate_table_expression(
        exe.EvaluateTableInput.model_validate(
            {"spec": _spec(ast), "table_ref": _table_payload(expense_table)}
        ),
        ctx,
        runtime,
    )
    assert result.data.assessment.verdict == "pass"


def test_table_row_limit_truncates(runtime, ctx, expense_table):
    ast = {
        "op": "gt",
        "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 0}],
    }
    result = exe.evaluate_table_expression(
        exe.EvaluateTableInput.model_validate(
            {"spec": _spec(ast), "table_ref": _table_payload(expense_table), "max_rows": 1}
        ),
        ctx,
        runtime,
    )
    assert any(i.code == "da07.row_limit_reached" for i in result.issues)
    assert len(result.data.verdicts) == 1


# --- B1/B2/B5/N1 regression tests (tester r19) ----------------------------------


def test_nested_is_missing_inside_not_and_or(runtime, ctx):
    """B1: is_missing must be decidable anywhere in the tree, not only at the root."""

    missing = _record([_field("amount", None, status="missing")])
    nested = {
        "op": "not",
        "args": [{"op": "is_missing", "args": [{"op": "field", "field_id": "amount"}]}],
    }
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(nested), "record": missing}),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.assessment.verdict == "fail"  # missing -> not(missing)=False

    combined = {
        "op": "or",
        "args": [
            {"op": "is_missing", "args": [{"op": "field", "field_id": "amount"}]},
            {"op": "literal", "value": False},
        ],
    }
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(combined), "record": missing}),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.assessment.verdict == "pass"


def test_explicit_null_applicability_is_unknown_not_applicable(runtime, ctx):
    """B2: an explicitly unknown applicability must not become a definite verdict."""

    record = _record([_field("amount", 1200)])
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate(
            {"spec": _spec(LE), "record": record, "applicable": None}
        ),
        ctx,
        runtime,
    )
    assert result.data.assessment.verdict == "unknown"
    assert "applicable is unknown" in result.data.assessment.unknowns

    # omitted = no applicability gate: evaluation proceeds
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": _spec(LE), "record": record}),
        ctx,
        runtime,
    )
    assert result.data.assessment.verdict == "pass"


def test_engine_binding_mismatch_fails_closed(runtime, ctx):
    """B5: the spec's EngineBinding is enforced before evaluation."""

    record = _record([_field("amount", 1200)])
    pinned = ExecutableSpec(
        spec_id="s-pin",
        revision="r1",
        backend_kind="expression",
        expression_or_call=LE,
        engine_binding=EngineBinding(engine_id="dataagent-expression", engine_version="9.9.9"),
    )
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate({"spec": pinned.model_dump(mode="json"), "record": record}),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da07.engine_version_mismatch"

    wrong_engine = ExecutableSpec(
        spec_id="s-wrong",
        revision="r1",
        backend_kind="expression",
        expression_or_call=LE,
        engine_binding=EngineBinding(engine_id="duckdb", engine_version="0.1.0"),
    )
    result = exe.evaluate_scalar_expression(
        exe.EvaluateScalarInput.model_validate(
            {"spec": wrong_engine.model_dump(mode="json"), "record": record}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da07.engine_binding_mismatch"


def test_table_row_limit_truncation_is_disclosed(runtime, ctx, expense_table):
    """N1: truncation must surface as partial + truncated completeness."""

    ast = {
        "op": "gt",
        "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 0}],
    }
    result = exe.evaluate_table_expression(
        exe.EvaluateTableInput.model_validate(
            {"spec": _spec(ast), "table_ref": _table_payload(expense_table), "max_rows": 1}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.partial
    assert result.completeness.extent.value == "truncated"
    assert result.completeness.observed["detail_rows"] == 2
    assert result.completeness.observed["evaluated_rows"] == 1


def test_table_engine_binding_mismatch_fails_closed(runtime, ctx, expense_table):
    pinned = ExecutableSpec(
        spec_id="s-pin",
        revision="r1",
        backend_kind="expression",
        expression_or_call=LE,
        engine_binding=EngineBinding(engine_id="dataagent-expression", engine_version="9.9.9"),
    )
    result = exe.evaluate_table_expression(
        exe.EvaluateTableInput.model_validate(
            {"spec": pinned.model_dump(mode="json"), "table_ref": _table_payload(expense_table)}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da07.engine_version_mismatch"
