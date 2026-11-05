"""r40 F1: every model-visible caller content is bound to the EgressDecision.

Two residual bypasses of the r38/r39 closure, both fixed here:

- **F1a** — ``fields[].value_type`` (and any caller free text smuggled
  through the field metadata) reached the model under a decision that only
  covered the rule. The projection is now *rebuilt*: only fields the bound
  rule references travel, and ``value_type`` must be a member of a closed
  vocabulary — anything else is refused without echoing it.
- **F1b** — ``generate_single_table_sql`` wrote the caller's statement /
  metric statements / fixed filters / requirement into the request while
  citing only the table asset, so a table-only decision vouched for caller
  free text. Every caller-supplied request section is now cited *by content
  address*: the decision must cover those exact bytes (the shared gate
  matches a covered revision by its digest, whatever the id).

Controls: a clean field list still reaches the request under a rule-only
decision, and a decision that covers the statement's content address lets a
legitimate statement travel.
"""

from __future__ import annotations

import json

import pytest

from dataagent_contracts.core import EgressDecision, EgressOutcome, ModelDestination
from dataagent_runtime.errors import CapabilityError

from dataagent_application import helpers
from dataagent_application.planning import expressions as plan

RULE = {
    "statement": "单笔报销金额不得超过 5000 元",
    "conditions": [
        {"condition_id": "c1", "text": "金额不超过 5000 元", "referenced_fields": ["amount"]}
    ],
    "combination": "c1",
}

DESTINATION = {"model_ref": "model:vendor", "deployment": "vendor_api"}


def _expr_input(runtime, **overrides):
    payload = {
        "rule": RULE,
        "rule_ref": None,
        "fields": [{"field_id": "amount", "value_type": "number"}],
        "destination": DESTINATION,
    }
    payload.update(overrides)
    return plan.GenerateFunctionExpressionsInput.model_validate(payload)


def _save_decision(runtime, decision_id, content_refs, outcome=EgressOutcome.allow):
    runtime.decisions.save_egress(
        EgressDecision(
            decision_id=decision_id,
            content_refs=content_refs,
            destination=ModelDestination(
                model_ref=DESTINATION["model_ref"], deployment=DESTINATION["deployment"]
            ),
            decision=outcome,
            access_decision_ref="ad-1",
        )
    )
    return decision_id


def _stored_rule_input(runtime):
    digest = runtime.content.put(RULE)
    return _expr_input(
        runtime, rule_ref={"id": "rule:limit", "revision": digest}
    )


# --- F1a: fields are rebuilt, never caller free text -------------------------- #


def test_value_type_outside_the_vocabulary_is_refused_without_echo(runtime, ctx):
    wire = _stored_rule_input(runtime)
    wire.fields = [
        {
            "field_id": "amount",
            "value_type": "SECRET-R40 value_type 13800138000",
        }
    ]
    with pytest.raises(CapabilityError) as caught:
        plan.generate_function_expressions(wire, ctx, runtime)
    message = str(caught.value)
    assert "closed vocabulary" in message
    # the refusal never echoes the caller content it rejected
    assert "SECRET-R40" not in message
    assert "13800138000" not in message


def test_field_the_rule_does_not_reference_is_dropped_from_the_request(runtime, ctx):
    wire = _stored_rule_input(runtime)
    wire.fields = [
        {"field_id": "amount", "value_type": "number"},
        # a legitimate-looking field the rule never references: nothing the
        # decision covers vouches for its metadata, so it must not travel
        {"field_id": "customer_note", "value_type": "string"},
    ]
    result = plan.generate_function_expressions(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    request = result.issues[0].inference_request
    assert request["fields"] == [{"field_id": "amount", "value_type": "number"}]


def test_clean_field_metadata_still_reaches_the_request(runtime, ctx):
    # control: a rule-only decision still lets the (rebuilt) field metadata
    # travel — the closure must not break the legitimate two-phase flow
    digest = runtime.content.put(RULE)
    decision = _save_decision(
        runtime,
        "eg-allow-r40-fields",
        [{"id": "rule:limit", "revision": digest}],
    )
    wire = _stored_rule_input(runtime)
    wire.egress_decision_ref = decision
    result = plan.generate_function_expressions(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    request = result.issues[0].inference_request
    assert request["fields"] == [{"field_id": "amount", "value_type": "number"}]


# --- F1b: generate_single_table_sql cites caller content by address ----------- #


def _sql_input(runtime, table, **overrides):
    payload = {
        "table_ref": {
            "asset": table.asset.model_dump(mode="json"),
            "schema_ref": "schema:x@r1",
            "data_ref": table.data_ref,
        },
        "statement": "按区域求金额合计",
        "metrics": [],
    }
    payload.update(overrides)
    return plan.GenerateSingleTableSqlInput.model_validate(payload)


def test_table_only_decision_does_not_vouch_for_the_caller_statement(runtime, ctx, expense_table):
    decision = _save_decision(
        runtime,
        "eg-allow-r40-table",
        [{"id": expense_table.asset.id, "revision": expense_table.asset.revision}],
    )
    wire = _sql_input(
        runtime,
        expense_table,
        statement="SECRET-R40 statement 13800138000",
        egress_decision_ref=decision,
        destination=DESTINATION,
    )
    result = plan.generate_single_table_sql(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    assert any(i.code == "da12.egress_required" for i in result.issues)
    request = result.issues[0].inference_request
    # the caller free text is stripped from the returned request
    assert request.get("statement") is None
    assert "SECRET-R40" not in json.dumps(
        [i.inference_request for i in result.issues], ensure_ascii=False
    )
    assert "SECRET-R40" not in result.model_dump_json()


def test_decision_covering_the_statement_address_lets_it_travel(runtime, ctx, expense_table):
    # control: a decision that covers the statement's content address (any
    # id — the revision, the digest of the bytes, is what binds) vouches for
    # the caller statement; the bound table stays covered by its own ref
    statement = "按区域求金额合计"
    statement_digest = helpers.caller_content_ref(statement).revision
    decision = _save_decision(
        runtime,
        "eg-allow-r40-statement",
        [
            {"id": expense_table.asset.id, "revision": expense_table.asset.revision},
            {"id": "requirement:text", "revision": statement_digest},
        ],
    )
    wire = _sql_input(
        runtime,
        expense_table,
        statement=statement,
        egress_decision_ref=decision,
        destination=DESTINATION,
    )
    result = plan.generate_single_table_sql(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    assert result.issues[0].code == "da06.inference_required"
    request = result.issues[0].inference_request
    assert request["statement"] == statement


def test_metric_statements_and_filters_need_their_own_coverage(runtime, ctx, expense_table):
    decision = _save_decision(
        runtime,
        "eg-allow-r40-table2",
        [{"id": expense_table.asset.id, "revision": expense_table.asset.revision}],
    )
    metric = {
        "draft_id": "mtd-amount",
        "revision": "r1",
        "kind": "metric",
        "definition": {
            "statement": "SECRET-R40 metric 13800138000",
            "measure": {"field_ref": "amount", "aggregation": "sum"},
            "grain": "region",
            "additivity": "additive",
            "filters": [{"text": "approved = true", "referenced_fields": ["approved"]}],
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
                    "char_end": 5,
                },
            }
        ],
        "status": "validated",
    }
    wire = _sql_input(
        runtime,
        expense_table,
        statement=None,
        metrics=[metric],
        egress_decision_ref=decision,
        destination=DESTINATION,
    )
    result = plan.generate_single_table_sql(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    assert any(i.code == "da12.egress_required" for i in result.issues)
    request = result.issues[0].inference_request
    # the caller free text is stripped from the returned request — the
    # metric statements and their fixed filters travel under content keys,
    # which the failed gate removes entirely
    assert "metrics" not in request
    assert "metric_filters" not in request
    assert "SECRET-R40" not in json.dumps(
        [i.inference_request for i in result.issues], ensure_ascii=False
    )
    assert "SECRET-R40" not in result.model_dump_json()


def test_requirements_first_phase_cites_caller_content_by_address(runtime, ctx, expense_table):
    # the requirement-family first phase binds its caller text by content
    # address too: a decision covering the statement bytes passes, a
    # table-only decision does not vouch for it
    from dataagent_application.planning import requirements as req

    statement = "统计每个区域的报销总额"
    statement_digest = helpers.caller_content_ref(statement).revision
    decision = _save_decision(
        runtime, "eg-allow-r40-req", [{"id": "s", "revision": statement_digest}]
    )
    wire = req.BindMetricsAndDimensionsInput.model_validate(
        {
            "statement": statement,
            "metrics": [],
            "egress_decision_ref": decision,
            "destination": DESTINATION,
        }
    )
    result = req.bind_metrics_and_dimensions(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    assert result.issues[0].code == "da06.inference_required"
    assert result.issues[0].inference_request["statement"] == statement

    table_only = _save_decision(
        runtime,
        "eg-allow-r40-req2",
        [{"id": expense_table.asset.id, "revision": expense_table.asset.revision}],
    )
    wire = req.BindMetricsAndDimensionsInput.model_validate(
        {
            "statement": "SECRET-R40 requirement 13800138000",
            "metrics": [],
            "egress_decision_ref": table_only,
            "destination": DESTINATION,
        }
    )
    result = req.bind_metrics_and_dimensions(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    assert any(i.code == "da12.egress_required" for i in result.issues)
    dumped = json.dumps(
        [i.inference_request for i in result.issues], ensure_ascii=False
    )
    assert "SECRET-R40" not in dumped
