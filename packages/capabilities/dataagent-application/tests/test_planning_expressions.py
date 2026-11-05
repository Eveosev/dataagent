"""DA06.3.5 (AST generation) and DA06.3.1 (SQL generation) two-phase atoms."""

from __future__ import annotations

import pytest

from dataagent_contracts.core import CapabilityStatus

from dataagent_application.planning import expressions as plan
from dataagent_runtime.errors import CapabilityError

from tests.conftest import store_table

RULE = {
    "statement": "单笔报销金额不得超过 5000 元，且必须属于可报销区域",
    "conditions": [
        {"condition_id": "c1", "text": "金额不超过 5000 元", "referenced_fields": ["amount"]},
        {"condition_id": "c2", "text": "区域属于可报销区域", "referenced_fields": ["region"]},
    ],
    "combination": "c1 and c2",
    "exceptions": [{"text": "经财务总监特批的除外"}],
}

FIELDS = [
    {"field_id": "region", "name": "区域", "path": "region", "value_type": "string"},
    {"field_id": "amount", "name": "金额", "path": "amount", "value_type": "number"},
]

AST = {
    "op": "and",
    "args": [
        {
            "op": "le",
            "args": [
                {"op": "field", "field_id": "amount", "condition_id": "c1"},
                {"op": "literal", "value": 5000},
            ],
        },
        {
            "op": "in",
            "args": [
                {"op": "field", "field_id": "region", "condition_id": "c2"},
                {"op": "literal", "value": ["north", "south"]},
            ],
        },
    ],
}


def _expr_input(**overrides):
    payload = {"rule": RULE, "fields": FIELDS}
    payload.update(overrides)
    return plan.GenerateFunctionExpressionsInput.model_validate(payload)


def test_first_call_returns_needs_input_with_ast_shape(runtime, ctx):
    result = plan.generate_function_expressions(_expr_input(), ctx, runtime)
    assert result.status is CapabilityStatus.needs_input
    request = result.issues[0].inference_request
    assert "'condition_id'" in request["ast_shape"]["field_leaf"]
    assert {c["condition_id"] for c in request["conditions"]} == {"c1", "c2"}


def test_happy_path_builds_spec_with_engine_binding(runtime, ctx):
    result = plan.generate_function_expressions(
        _expr_input(proposal={"expression": AST}), ctx, runtime
    )
    # The rule carries an exception clause that the proposal did not compile:
    # the spec is produced, but the result is partial with a warning.
    assert result.status is CapabilityStatus.partial
    assert any(i.code == "da06.exceptions_not_compiled" for i in result.issues)
    spec = result.data.spec
    assert spec.backend_kind == "expression"
    assert spec.engine_binding.engine_id == "dataagent-expression"
    assert spec.expression_or_call == AST


def test_non_closed_operator_is_rejected(runtime, ctx):
    bad = {"op": "python_eval", "args": [{"op": "literal", "value": "1"}]}
    with pytest.raises(CapabilityError, match="non-closed operator"):
        plan.generate_function_expressions(_expr_input(proposal={"expression": bad}), ctx, runtime)


def test_unknown_field_is_rejected(runtime, ctx):
    bad = {
        "op": "eq",
        "args": [{"op": "field", "field_id": "ghost"}, {"op": "literal", "value": 1}],
    }
    with pytest.raises(CapabilityError, match="outside the bound schema"):
        plan.generate_function_expressions(_expr_input(proposal={"expression": bad}), ctx, runtime)


def test_uncovered_condition_is_rejected(runtime, ctx):
    partial = {
        "op": "le",
        "args": [
            {"op": "field", "field_id": "amount", "condition_id": "c1"},
            {"op": "literal", "value": 5000},
        ],
    }
    with pytest.raises(CapabilityError, match="not covered"):
        plan.generate_function_expressions(_expr_input(proposal={"expression": partial}), ctx, runtime)


def test_bogus_condition_provenance_is_rejected(runtime, ctx):
    bad = {
        "op": "and",
        "args": [
            {
                "op": "le",
                "args": [
                    {"op": "field", "field_id": "amount", "condition_id": "c9"},
                    {"op": "literal", "value": 5000},
                ],
            },
            {
                "op": "in",
                "args": [
                    {"op": "field", "field_id": "region", "condition_id": "c2"},
                    {"op": "literal", "value": ["north"]},
                ],
            },
        ],
    }
    with pytest.raises(CapabilityError, match="unknown condition ids"):
        plan.generate_function_expressions(_expr_input(proposal={"expression": bad}), ctx, runtime)


def test_type_check_rejects_ordered_comparison_between_string_and_number(runtime, ctx):
    bad = {
        "op": "and",
        "args": [
            {
                "op": "lt",
                "args": [
                    {"op": "field", "field_id": "region", "condition_id": "c1"},
                    {"op": "literal", "value": 5000},
                ],
            },
            {
                "op": "in",
                "args": [
                    {"op": "field", "field_id": "region", "condition_id": "c2"},
                    {"op": "literal", "value": ["north"]},
                ],
            },
        ],
    }
    with pytest.raises(CapabilityError, match="type check failed"):
        plan.generate_function_expressions(_expr_input(proposal={"expression": bad}), ctx, runtime)


def test_unsupported_conditions_are_partial_with_warning(runtime, ctx):
    ast_missing_c2 = {
        "op": "le",
        "args": [
            {"op": "field", "field_id": "amount", "condition_id": "c1"},
            {"op": "literal", "value": 5000},
        ],
    }
    result = plan.generate_function_expressions(
        _expr_input(proposal={"expression": ast_missing_c2, "unsupported_conditions": ["c2"]}), ctx, runtime
    )
    assert result.status is CapabilityStatus.partial
    assert any(i.code == "da06.conditions_unsupported" for i in result.issues)


# --- DA06.3.1 SQL -------------------------------------------------------------


def _table_payload(table):
    return {
        "asset": table.asset.model_dump(mode="json"),
        "schema_ref": "schema:x@r1",
        "data_ref": table.data_ref,
    }


def _sql_input(table, **overrides):
    payload = {
        "table_ref": _table_payload(table),
        "statement": "按区域求金额合计",
        "metrics": [
            {
                "draft_id": "mtd-amount",
                "revision": "r1",
                "kind": "metric",
                "definition": {
                    "statement": "金额合计",
                    "measure": {"field_ref": "amount", "aggregation": "sum"},
                    "grain": "region",
                    "additivity": "additive",
                },
                "scope_ref": "scope-1",
                "sources": [
                    {
                        "source_ref": "doc-1",
                        "source_revision": "r1",
                        "selector": {"kind": "text_span", "unit_ref": "unit:char", "char_start": 0, "char_end": 5},
                    }
                ],
                "status": "validated",
            }
        ],
    }
    payload.update(overrides)
    return plan.GenerateSingleTableSqlInput.model_validate(payload)


def test_sql_first_call_returns_needs_input_with_schema(runtime, ctx, expense_table):
    result = plan.generate_single_table_sql(_sql_input(expense_table), ctx, runtime)
    assert result.status is CapabilityStatus.needs_input
    request = result.issues[0].inference_request
    assert request["table"]["sql_name"].startswith("t_")
    assert {f["field_id"] for f in request["table"]["columns"]} == {"region", "amount"}


def test_sql_happy_path(runtime, ctx, expense_table):
    name = plan._sql_table_name(expense_table)
    result = plan.generate_single_table_sql(
        _sql_input(expense_table, proposal={"sql": f'SELECT region, sum(amount) AS total FROM {name} GROUP BY region'}),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.spec.backend_kind == "sql"
    assert plan.sql_digest(result.data.spec.sql) == plan.sql_digest(
        f"SELECT region, sum(amount) AS total FROM {name} GROUP BY region"
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT * FROM other_table",
        "SELECT * FROM read_csv('x.csv')",
        "COPY (SELECT 1) TO 'out.csv'",
        "ATTACH 'other.db' AS other",
        "INSTALL httpfs",
        "CREATE TABLE x AS SELECT 1",
        "UPDATE t SET amount = 0",
    ],
)
def test_sql_security_counterexamples_are_rejected(runtime, ctx, expense_table, sql):
    with pytest.raises(CapabilityError, match="SQL validation failed"):
        plan.generate_single_table_sql(_sql_input(expense_table, proposal={"sql": sql}), ctx, runtime)


def test_sql_cte_is_allowed(runtime, ctx, expense_table):
    name = plan._sql_table_name(expense_table)
    sql = f"WITH base AS (SELECT * FROM {name}) SELECT count(*) AS n FROM base"
    result = plan.generate_single_table_sql(_sql_input(expense_table, proposal={"sql": sql}), ctx, runtime)
    assert result.status is CapabilityStatus.ok


# --- B3/B4/B6 regression tests (tester r19) -------------------------------------


def test_inverted_combination_is_rejected(runtime, ctx):
    """B3: an AST that flips rule.combination's and/or must not pass."""

    inverted = {
        "op": "or",
        "args": [AST["args"][0], AST["args"][1]],
    }
    result = plan.generate_function_expressions(
        _expr_input(proposal={"expression": inverted}), ctx, runtime
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.combination_mismatch"


def test_negated_combination_is_rejected(runtime, ctx):
    negated = {"op": "not", "args": [AST]}
    result = plan.generate_function_expressions(
        _expr_input(proposal={"expression": negated}), ctx, runtime
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.combination_mismatch"


def test_matching_combination_still_passes(runtime, ctx):
    result = plan.generate_function_expressions(
        _expr_input(proposal={"expression": AST}), ctx, runtime
    )
    assert result.status is CapabilityStatus.partial  # exceptions_not_compiled warning
    assert not any(i.code == "da06.combination_mismatch" for i in result.issues)


def _bound_requirement(table, ctx, runtime, **overrides):
    """DA06.1.1 output for the fixed-filter metric used below."""

    from dataagent_application.planning import requirements as req

    metric = {
        "draft_id": "mtd-amount",
        "revision": "r1",
        "kind": "metric",
        "definition": {
            "statement": "已批准明细行金额之和",
            "measure": {"field_ref": "amount", "aggregation": "sum"},
            "filters": [{"text": "approved = true", "referenced_fields": ["approved"]}],
            "grain": "month",
            "additivity": "additive",
            "unit": "CNY",
        },
        "scope_ref": "scope-1",
        "sources": [
            {
                "source_ref": "doc-1",
                "source_revision": "r1",
                "selector": {"kind": "text_span", "unit_ref": "unit:char", "char_start": 0, "char_end": 8},
            }
        ],
        "status": "validated",
    }
    payload = {
        "statement": "按区域统计已批准金额",
        "table_ref": _table_payload(table),
        "metrics": [metric],
        "proposal": {"metric_ids": ["mtd-amount"], "dimensions": ["region"], "grain": "month"},
    }
    payload.update(overrides)
    bound = req.bind_metrics_and_dimensions(
        req.BindMetricsAndDimensionsInput.model_validate(payload), ctx, runtime
    )
    assert bound.status is CapabilityStatus.ok
    return bound.data.requirement, metric


def _approved_table(runtime):
    from tests.conftest import store_table

    return store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number"},
            {"name": "Approved", "field_id": "approved", "value_type": "boolean"},
        ],
        rows=[["north", 100, True], ["south", 200, True], ["TOTAL", 300, True]],
        row_meta=[
            {"role": "detail", "reason": ""},
            {"role": "detail", "reason": ""},
            {"role": "total", "reason": "grand total"},
        ],
    )


def test_metric_fixed_filters_travel_into_requirement(runtime, ctx):
    """B4: the bound RequirementSpec carries the metric's fixed filters."""

    table = _approved_table(runtime)
    requirement, _ = _bound_requirement(table, ctx, runtime)
    assert any("approved" in f.text for f in requirement.filters)
    assert requirement.filters[0].referenced_fields == ["approved"]


def test_sql_wrong_measure_column_is_rejected(runtime, ctx):
    """B4: 'SQL correct, caliber wrong' must not pass with the metric attached."""

    table = _approved_table(runtime)
    requirement, metric = _bound_requirement(table, ctx, runtime)
    name = plan._sql_table_name(table)
    wrong = plan.generate_single_table_sql(
        plan.GenerateSingleTableSqlInput.model_validate(
            {
                "table_ref": _table_payload(table),
                "metrics": [metric],
                "requirement": requirement.model_dump(mode="json"),
                "proposal": {"sql": f"SELECT region, sum(approved) AS total FROM {name} GROUP BY region"},
            }
        ),
        ctx,
        runtime,
    )
    assert wrong.status is CapabilityStatus.failed
    assert wrong.issues[0].code == "da06.sql_caliber_mismatch"


def test_sql_dropping_fixed_filter_is_rejected(runtime, ctx):
    table = _approved_table(runtime)
    requirement, metric = _bound_requirement(table, ctx, runtime)
    name = plan._sql_table_name(table)
    dropped = plan.generate_single_table_sql(
        plan.GenerateSingleTableSqlInput.model_validate(
            {
                "table_ref": _table_payload(table),
                "metrics": [metric],
                "requirement": requirement.model_dump(mode="json"),
                "proposal": {
                    "sql": f"SELECT region, sum(amount) AS total FROM {name} GROUP BY region"
                },
            }
        ),
        ctx,
        runtime,
    )
    assert dropped.status is CapabilityStatus.failed
    assert dropped.issues[0].code == "da06.sql_caliber_mismatch"


def test_sql_with_bound_caliber_passes(runtime, ctx):
    table = _approved_table(runtime)
    requirement, metric = _bound_requirement(table, ctx, runtime)
    name = plan._sql_table_name(table)
    good = plan.generate_single_table_sql(
        plan.GenerateSingleTableSqlInput.model_validate(
            {
                "table_ref": _table_payload(table),
                "metrics": [metric],
                "requirement": requirement.model_dump(mode="json"),
                "proposal": {
                    "sql": (
                        f"SELECT region, sum(amount) AS total FROM {name} "
                        "WHERE approved = true GROUP BY region"
                    )
                },
            }
        ),
        ctx,
        runtime,
    )
    assert good.status is CapabilityStatus.ok


def test_inference_request_is_egress_gated(runtime, ctx):
    """B6: the request always carries egress_decision_ref and is gated."""

    first = plan.generate_function_expressions(_expr_input(), ctx, runtime)
    assert first.status is CapabilityStatus.needs_input
    request = first.issues[0].inference_request
    assert "egress_decision_ref" in request
    # warn mode: content passes, but a warning discloses the missing decision
    assert any(i.code == "da12.egress_required" and i.severity.value == "warning" for i in first.issues)


def test_egress_decision_deny_strips_content(runtime, ctx):
    """B6: deny → needs_input without the raw content (07 §4.1 / §11.3)."""

    from dataagent_contracts.core import EgressDecision, EgressOutcome, ModelDestination

    decision = EgressDecision(
        decision_id="egd:deny-1",
        content_refs=[{"id": "rule:x", "revision": "r1"}],
        destination=ModelDestination(model_ref="model:test", deployment="local"),
        decision=EgressOutcome.deny,
        access_decision_ref="acc:1",
    )
    runtime.decisions.save_egress(decision)
    result = plan.generate_function_expressions(
        _expr_input(egress_decision_ref="egd:deny-1"), ctx, runtime
    )
    assert result.status is CapabilityStatus.needs_input
    request = result.issues[0].inference_request
    assert result.issues[0].severity.value == "error"
    assert "statement" not in request and "conditions" not in request
    assert "exceptions" not in request and "fields" not in request
    assert RULE["statement"] not in str(request)
    assert request["egress_decision_ref"] == "egd:deny-1"
