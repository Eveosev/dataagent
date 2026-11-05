"""Regression tests for the tester r20 seam fixes (B1/B2/B3).

- B1: DA06.1.1 binds metric drafts that cite human header names (the data
  layer emits field_ids, but the seam accepts either identity).
- B2: DA06.3.1 caliber binding enforces dimensions/grain and fixed-filter
  operator/value, not just the filter column's presence.
- B3: an ``allow`` EgressDecision lets the inference content through; a
  caller-declared destination that mismatches the decision strips it.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from dataagent_contracts.core import CapabilityStatus, EgressDecision, ModelDestination
from dataagent_runtime.errors import CapabilityError

from dataagent_application.planning import expressions as plan
from dataagent_application.planning import requirements as req

from conftest import store_table


# --- shared fixtures -----------------------------------------------------------


def _table_payload(table):
    return {
        "asset": table.asset.model_dump(mode="json"),
        "schema_ref": "schema:x@r1",
        "data_ref": table.data_ref,
    }


@pytest.fixture()
def named_table(runtime):
    """A bound table whose ids and human names differ (W0 §1.2)."""

    return store_table(
        runtime,
        columns=[
            {"name": "Region", "field_id": "region", "value_type": "string"},
            {"name": "Amount", "field_id": "amount", "value_type": "number", "unit": "CNY"},
            {"name": "Approved", "field_id": "approved", "value_type": "boolean"},
        ],
        rows=[["north", 100, True], ["south", 200, True]],
    )


def _metric(*, field_ref="amount", filter_fields=("approved",)):
    return {
        "draft_id": "m-name-1",
        "revision": "r1",
        "kind": "metric",
        "definition": {
            "statement": "approved amount by region",
            "measure": {"field_ref": field_ref, "aggregation": "sum"},
            "filters": [
                {"text": "approved = true", "referenced_fields": list(filter_fields)}
            ],
            "grain": "region",
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


def _bind(runtime, ctx, table, metric, *, dimensions, grain="region"):
    return req.bind_metrics_and_dimensions(
        req.BindMetricsAndDimensionsInput.model_validate(
            {
                "statement": "approved amount by region",
                "table_ref": _table_payload(table),
                "metrics": [metric],
                "proposal": {
                    "metric_ids": [metric["draft_id"]],
                    "dimensions": list(dimensions),
                    "grain": grain,
                },
            }
        ),
        ctx,
        runtime,
    )


# --- B1: name <-> field_id identity --------------------------------------------


def test_binding_accepts_human_names_and_canonicalizes_to_field_ids(runtime, ctx, named_table):
    """The seam accepts names (data-layer output shape) and binds by id."""

    metric = _metric(field_ref="Amount", filter_fields=("Approved",))
    bound = _bind(runtime, ctx, named_table, metric, dimensions=["Region"])
    assert bound.status is CapabilityStatus.ok
    assert bound.data.requirement.dimensions == ["region"]
    assert bound.data.requirement.filters[0].referenced_fields == ["approved"]


def test_binding_rejects_a_name_that_is_no_column(runtime, ctx, named_table):
    metric = _metric(field_ref="Nonexistent")
    with pytest.raises(CapabilityError, match="not in the bound table schema"):
        _bind(runtime, ctx, named_table, metric, dimensions=["Region"])


def test_ambiguous_name_is_not_resolved(runtime, ctx):
    """A name that maps to several field ids stays raw and fails validation."""

    table = store_table(
        runtime,
        columns=[
            {"name": "Amount", "field_id": "amount", "value_type": "number"},
            {"name": "Amount", "field_id": "amount2", "value_type": "number"},
        ],
        rows=[[1, 2]],
    )
    metric = _metric(field_ref="Amount")
    with pytest.raises(CapabilityError, match="not in the bound table schema"):
        _bind(runtime, ctx, table, metric, dimensions=["amount"])


# --- B2: caliber binding of dimensions and filter constants --------------------


@pytest.fixture()
def caliber_case(runtime, ctx, named_table):
    metric = _metric()
    bound = _bind(runtime, ctx, named_table, metric, dimensions=["region"])
    return named_table, bound.data.requirement.model_dump(mode="json"), metric


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


def test_caliber_aligned_sql_passes(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        "WHERE approved = true GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


def test_caliber_opposite_filter_value_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        "WHERE approved = false GROUP BY region",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "operator/value" in result.issues[0].message


def test_caliber_dropped_dimension_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT sum(amount) AS total FROM {name} WHERE approved = true",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "not grouped" in result.issues[0].message


def test_caliber_non_bound_group_by_is_rejected(runtime, ctx, caliber_case):
    table, requirement, metric = caliber_case
    name = plan._sql_table_name(table)
    result = _generate(
        runtime, ctx, table, requirement, metric,
        f"SELECT approved, sum(amount) AS total FROM {name} "
        "WHERE approved = true GROUP BY approved",
    )
    assert result.status is CapabilityStatus.failed
    assert result.issues[0].code == "da06.sql_caliber_mismatch"
    assert "outside the bound grain" in result.issues[0].message


def test_caliber_time_field_may_be_grouped(runtime, ctx, named_table):
    """The metric's time field is part of the bound grain, not 'extra'."""

    metric = _metric()
    metric["definition"]["time"] = {"time_field": "region", "grain": "month"}
    bound = _bind(runtime, ctx, named_table, metric, dimensions=["region"])
    name = plan._sql_table_name(named_table)
    result = _generate(
        runtime, ctx, named_table,
        bound.data.requirement.model_dump(mode="json"), metric,
        f"SELECT region, sum(amount) AS total FROM {name} "
        "WHERE approved = true GROUP BY region",
    )
    assert result.status is CapabilityStatus.ok


# --- B3: egress allow path ------------------------------------------------------


def _rule():
    return {
        "statement": "机密客户 A 的金额不超过 5000",
        "conditions": [
            {"condition_id": "c1", "text": "金额不超过 5000", "referenced_fields": ["amount"]}
        ],
        "combination": "c1",
    }


def _fields():
    return [{"field_id": "amount", "name": "金额", "path": "amount", "value_type": "number"}]


def _save_decision(runtime, decision_id, outcome, *, model_ref="model-x", deployment="vendor_api"):
    runtime.decisions.save_egress(
        EgressDecision(
            decision_id=decision_id,
            content_refs=[
                {"id": "rule:" + hashlib.sha256("机密客户 A 的金额不超过 5000".encode()).hexdigest()[:16],
                 "revision": "r1"}
            ],
            destination=ModelDestination(model_ref=model_ref, deployment=deployment),
            decision=outcome,
            access_decision_ref="ad-1",
        )
    )


def _generate_expressions(runtime, ctx, *, decision_ref, destination=None):
    payload = {
        "rule": _rule(),
        "fields": _fields(),
        "egress_decision_ref": decision_ref,
    }
    if destination is not None:
        payload["destination"] = destination
    return plan.generate_function_expressions(
        plan.GenerateFunctionExpressionsInput.model_validate(payload), ctx, runtime
    )


def test_allow_decision_lets_content_through(runtime, ctx):
    _save_decision(runtime, "eg-allow-1", "allow")
    result = _generate_expressions(runtime, ctx, decision_ref="eg-allow-1")
    assert result.status is CapabilityStatus.needs_input
    request = result.issues[0].inference_request
    assert "机密客户 A" in json.dumps(request, ensure_ascii=False)
    assert request["egress_decision_ref"] == "eg-allow-1"


def test_deny_decision_strips_content(runtime, ctx):
    _save_decision(runtime, "eg-deny-1", "deny")
    result = _generate_expressions(runtime, ctx, decision_ref="eg-deny-1")
    assert result.status is CapabilityStatus.needs_input
    assert "机密客户 A" not in json.dumps(
        [i.inference_request for i in result.issues], ensure_ascii=False
    )


def test_destination_mismatch_with_decision_strips_content(runtime, ctx):
    """A caller-declared destination is checked, not rubber-stamped."""

    _save_decision(runtime, "eg-allow-2", "allow")
    result = _generate_expressions(
        runtime, ctx, decision_ref="eg-allow-2",
        destination={"model_ref": "other-model", "deployment": "vendor_api"},
    )
    assert result.status is CapabilityStatus.needs_input
    assert "机密客户 A" not in json.dumps(
        [i.inference_request for i in result.issues], ensure_ascii=False
    )
    assert result.issues[0].code == "da12.egress_required"


def test_unresolvable_decision_is_reported_as_such(runtime, ctx):
    result = _generate_expressions(runtime, ctx, decision_ref="eg-missing")
    assert result.status is CapabilityStatus.needs_input
    assert "does not resolve" in result.issues[0].message
