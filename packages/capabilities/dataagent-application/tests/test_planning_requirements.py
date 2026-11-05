"""DA06.1.1–1.4 requirement binding, parsing, ambiguity, clarification (07 §5.3)."""

from __future__ import annotations

import pytest

from dataagent_contracts.core import CapabilityStatus

from dataagent_application.planning import requirements as req
from dataagent_runtime.errors import CapabilityError

METRIC = {
    "draft_id": "mtd-amount",
    "revision": "r1",
    "kind": "metric",
    "definition": {
        "statement": "月度费用总额 = 各明细行金额之和",
        "measure": {"field_ref": "amount", "aggregation": "sum"},
        "grain": "month",
        "additivity": "additive",
        "unit": "CNY",
    },
    "scope_ref": "scope-1",
    "sources": [
        {
            "source_ref": "doc-1",
            "source_revision": "r1",
            "selector": {"kind": "text_span", "unit_ref": "unit:char", "char_start": 0, "char_end": 10},
        }
    ],
    "status": "validated",
}


def _bind_input(table, **overrides):
    payload = {
        "statement": "按区域统计本月费用总额",
        "table_ref": {
            "asset": table.asset.model_dump(mode="json"),
            "schema_ref": "schema:x@r1",
            "data_ref": table.data_ref,
        },
        "metrics": [METRIC],
    }
    payload.update(overrides)
    return payload


def test_bind_metrics_first_call_is_needs_input_with_request(runtime, ctx, expense_table):
    result = req.bind_metrics_and_dimensions(req.BindMetricsAndDimensionsInput.model_validate(_bind_input(expense_table)), ctx, runtime)
    assert result.status is CapabilityStatus.needs_input
    request = result.issues[0].inference_request
    assert request["metric_ids"] == ["mtd-amount"]
    assert "region" in request["table_fields"] and "amount" in request["table_fields"]


def test_bind_metrics_happy_path_binds_metric_and_dimension(runtime, ctx, expense_table):
    payload = _bind_input(expense_table, proposal={"metric_ids": ["mtd-amount"], "dimensions": ["region"], "grain": "month"})
    result = req.bind_metrics_and_dimensions(req.BindMetricsAndDimensionsInput.model_validate(payload), ctx, runtime)
    assert result.status is CapabilityStatus.ok
    assert str(result.data.requirement.metrics[0]) == "mtd-amount@r1"
    assert result.data.requirement.dimensions == ["region"]


def test_bind_metrics_rejects_fabricated_metric_and_dimension(runtime, ctx, expense_table):
    payload = _bind_input(expense_table, proposal={"metric_ids": ["mtd-amount", "made-up"], "dimensions": ["region"], "grain": "month"})
    with pytest.raises(CapabilityError, match="not in the bound MetricDefinitions"):
        req.bind_metrics_and_dimensions(req.BindMetricsAndDimensionsInput.model_validate(payload), ctx, runtime)
    payload = _bind_input(expense_table, proposal={"metric_ids": ["mtd-amount"], "dimensions": ["nope"], "grain": "month"})
    with pytest.raises(CapabilityError, match="not in the bound table schema"):
        req.bind_metrics_and_dimensions(req.BindMetricsAndDimensionsInput.model_validate(payload), ctx, runtime)


def test_bind_metrics_rejects_measure_field_outside_schema(runtime, ctx):
    metric = {
        **METRIC,
        "definition": {**METRIC["definition"], "measure": {"field_ref": "ghost", "aggregation": "sum"}},
    }
    from tests.conftest import store_table

    table = store_table(
        runtime,
        columns=[{"name": "A", "field_id": "a", "value_type": "number"}],
        rows=[[1]],
    )
    payload = _bind_input(table, metrics=[metric])
    with pytest.raises(CapabilityError, match="measure field"):
        req.bind_metrics_and_dimensions(req.BindMetricsAndDimensionsInput.model_validate(payload), ctx, runtime)


def test_parse_time_and_filters_happy_and_rejects_unknown_field(runtime, ctx, expense_table):
    first = req.parse_time_and_filters(
        req.ParseTimeAndFiltersInput.model_validate(
            {"statement": "2026 年 10 月的费用", "table_ref": {"asset": expense_table.asset.model_dump(mode="json"), "schema_ref": "schema:x@r1", "data_ref": expense_table.data_ref}}
        ),
        ctx,
        runtime,
    )
    assert first.status is CapabilityStatus.needs_input
    good = {
        "time": {"from": "2026-10-01T00:00:00+08:00", "to": "2026-10-31T23:59:59+08:00"},
        "filters": [{"field_id": "region", "operator": "in", "values": ["north", "south"]}],
    }
    payload = {
        "statement": "2026 年 10 月的费用",
        "table_ref": {"asset": expense_table.asset.model_dump(mode="json"), "schema_ref": "schema:x@r1", "data_ref": expense_table.data_ref},
        "proposal": good,
    }
    result = req.parse_time_and_filters(req.ParseTimeAndFiltersInput.model_validate(payload), ctx, runtime)
    assert result.status is CapabilityStatus.ok
    assert result.data.filters[0].referenced_fields == ["region"]

    bad = {**payload, "proposal": {"filters": [{"field_id": "ghost", "operator": "eq", "values": [1]}]}}
    with pytest.raises(CapabilityError, match="not in the bound table schema"):
        req.parse_time_and_filters(req.ParseTimeAndFiltersInput.model_validate(bad), ctx, runtime)


def test_parse_time_and_filters_rejects_inverted_range(runtime, ctx):
    payload = {
        "statement": "费用",
        "proposal": {"time": {"from": "2026-12-01T00:00:00+08:00", "to": "2026-01-01T00:00:00+08:00"}},
    }
    with pytest.raises(CapabilityError, match="must not be after"):
        req.parse_time_and_filters(req.ParseTimeAndFiltersInput.model_validate(payload), ctx, runtime)


def test_identify_ambiguities_rejects_bad_kind_and_duplicates(runtime, ctx):
    base = {"statement": "本月费用", "metrics": [METRIC]}
    first = req.identify_calculation_ambiguities(
        req.IdentifyCalculationAmbiguitiesInput.model_validate(base), ctx, runtime
    )
    assert first.status is CapabilityStatus.needs_input
    assert first.issues[0].inference_request["kinds"][0] == "metric_definition"

    bad = {**base, "proposal": {"items": [{"ambiguity_id": "a1", "kind": "weird", "description": "x", "result_impact": "y"}]}}
    with pytest.raises(Exception):
        req.identify_calculation_ambiguities(
            req.IdentifyCalculationAmbiguitiesInput.model_validate(bad), ctx, runtime
        )
    dup = {
        **base,
        "proposal": {
            "items": [
                {"ambiguity_id": "a1", "kind": "time_boundary", "description": "x", "result_impact": "y"},
                {"ambiguity_id": "a1", "kind": "unit_or_currency", "description": "x", "result_impact": "y"},
            ]
        },
    }
    with pytest.raises(CapabilityError, match="unique"):
        req.identify_calculation_ambiguities(
            req.IdentifyCalculationAmbiguitiesInput.model_validate(dup), ctx, runtime
        )


def test_identify_ambiguities_adds_missing_time_boundary_deterministically(runtime, ctx):
    requirement = {
        "requirement_id": "req:1",
        "statement": "本月费用",
        "metrics": ["mtd-amount@r1"],
        "dimensions": ["region"],
        "grain": "month",
    }
    payload = {
        "statement": "本月费用",
        "metrics": [METRIC],
        "requirement": requirement,
        "proposal": {
            "items": [
                {"ambiguity_id": "a1", "kind": "unit_or_currency", "description": "币种未说明", "result_impact": "总额不同", "blocking": False}
            ]
        },
    }
    result = req.identify_calculation_ambiguities(
        req.IdentifyCalculationAmbiguitiesInput.model_validate(payload), ctx, runtime
    )
    assert result.status is CapabilityStatus.partial
    kinds = {a.kind for a in result.data.ambiguities}
    assert "time_boundary" in kinds
    added = [a for a in result.data.ambiguities if a.ambiguity_id == "amb:auto-time-boundary"]
    assert added and added[0].blocking is True


def test_clarification_blocking_returns_needs_input_with_alternatives(runtime, ctx):
    requirement = {
        "requirement_id": "req:1",
        "statement": "本月费用",
        "grain": "month",
        "ambiguities": [
            {"ambiguity_id": "a1", "kind": "time_boundary", "description": "含不含 10 月 31 日?", "result_impact": "行集不同", "blocking": True},
            {"ambiguity_id": "a2", "kind": "unit_or_currency", "description": "币种", "result_impact": "总额不同", "blocking": False},
        ],
    }
    result = req.generate_clarification_questions(
        req.GenerateClarificationQuestionsInput.model_validate({"requirement": requirement}), ctx, runtime
    )
    assert result.status is CapabilityStatus.needs_input
    alternatives = result.issues[0].alternatives
    assert alternatives and alternatives[0]["ambiguity_id"] == "a1"

    proposal = {
        "questions": [{"ambiguity_id": "a1", "question": "时间边界是否含月末?", "alternatives": ["含", "不含"]}],
        "answers": [{"ambiguity_id": "a1", "answer": "含月末"}],
    }
    result = req.generate_clarification_questions(
        req.GenerateClarificationQuestionsInput.model_validate(
            {"requirement": requirement, "proposal": proposal}
        ),
        ctx,
        runtime,
    )
    assert result.status is CapabilityStatus.ok
    assert result.data.still_blocking == []
    assert any("含月末" in a for a in result.data.assumptions)


def test_clarification_requires_question_for_every_blocking_ambiguity(runtime, ctx):
    requirement = {
        "requirement_id": "req:1",
        "statement": "本月费用",
        "grain": "month",
        "ambiguities": [
            {"ambiguity_id": "a1", "kind": "time_boundary", "description": "x", "result_impact": "y", "blocking": True},
        ],
    }
    payload = {"requirement": requirement, "proposal": {"questions": [], "answers": []}}
    with pytest.raises(CapabilityError, match="needs a question"):
        req.generate_clarification_questions(
            req.GenerateClarificationQuestionsInput.model_validate(payload), ctx, runtime
        )
