"""r38 F1: the model-visible rule content is bound to the covered record.

The application layer rebuilds the inference request from the rule content
the cited ``rule_ref`` addresses: the inline rule must match the stored
bytes on everything the model will see (statement, conditions, exceptions),
and ``fields`` travel as structural metadata only (``field_id`` /
``value_type``) — samples and any other caller payload are content no
EgressDecision has covered.
"""

from __future__ import annotations

import pytest

from dataagent_runtime.errors import CapabilityError

from dataagent_application.planning import expressions as plan

RULE = {
    "statement": "单笔报销金额不得超过 5000 元",
    "conditions": [
        {"condition_id": "c1", "text": "金额不超过 5000 元", "referenced_fields": ["amount"]}
    ],
    "combination": "c1",
}


def _input(runtime, **overrides):
    payload = {"rule": RULE, "fields": [{"field_id": "amount", "value_type": "number"}]}
    payload.update(overrides)
    return plan.GenerateFunctionExpressionsInput.model_validate(payload)


def _wire(runtime, rule=RULE, **overrides):
    digest = runtime.content.put(rule)
    rule_ref = {"id": "rule:limit", "revision": digest}
    return _input(runtime, rule_ref=rule_ref, **overrides)


def test_inline_rule_rewrite_is_refused_without_echoing_it(runtime, ctx):
    # the decision covers the stored bytes; the caller swaps the inline copy
    wire = _wire(runtime)
    wire.rule = wire.rule.model_copy(
        update={
            "statement": "SECRET-R38 changed protected clause contact 13800138000",
            "conditions": [
                wire.rule.conditions[0].model_copy(
                    update={"text": "secret_code=SECRET-R38 amount <= 5000"}
                )
            ],
        }
    )
    with pytest.raises(CapabilityError) as caught:
        plan.generate_function_expressions(wire, ctx, runtime)
    message = str(caught.value)
    assert "does not match the content bound to rule_ref" in message
    # the refusal never echoes the content it rejected
    assert "SECRET-R38" not in message
    assert "13800138000" not in message


def test_rule_ref_with_a_label_revision_is_refused(runtime, ctx):
    wire = _input(
        runtime, rule_ref={"id": "rule:limit", "revision": "r1"}
    )
    with pytest.raises(CapabilityError) as caught:
        plan.generate_function_expressions(wire, ctx, runtime)
    assert "content address" in str(caught.value)


def test_rule_ref_that_does_not_resolve_is_refused(runtime, ctx):
    wire = _input(
        runtime,
        rule_ref={"id": "rule:limit", "revision": "sha256:" + "0" * 64},
    )
    with pytest.raises(CapabilityError) as caught:
        plan.generate_function_expressions(wire, ctx, runtime)
    assert "does not resolve to stored content" in str(caught.value)


def test_matching_rule_ref_reaches_the_request(runtime, ctx):
    result = plan.generate_function_expressions(_wire(runtime), ctx, runtime)
    assert result.status.name == "needs_input"
    request = result.issues[0].inference_request
    assert request["statement"] == RULE["statement"]
    assert request["conditions"][0]["text"] == RULE["conditions"][0]["text"]


def test_uncovered_field_payload_is_dropped_from_the_request(runtime, ctx):
    wire = _wire(
        runtime,
        fields=[
            {
                "field_id": "amount",
                "value_type": "number",
                "sample": "SECRET-R38 13800138000",
                "note": "SECRET-R38",
            }
        ],
    )
    result = plan.generate_function_expressions(wire, ctx, runtime)
    assert result.status.name == "needs_input"
    request = result.issues[0].inference_request
    assert request["fields"] == [{"field_id": "amount", "value_type": "number"}]
    import json

    assert "SECRET-R38" not in json.dumps(request, ensure_ascii=False)


def test_inline_conditions_rewrite_is_refused(runtime, ctx):
    wire = _wire(runtime)
    stored = dict(RULE)
    stored["conditions"] = [
        {
            "condition_id": "c1",
            "text": "amount <= 5000",
            "referenced_fields": ["amount"],
        }
    ]
    # stored rule differs only in one condition's text
    wire2 = _wire(runtime, rule=stored)
    wire2.rule = wire2.rule.model_copy(
        update={
            "conditions": [
                wire2.rule.conditions[0].model_copy(
                    update={"text": "amount <= 999999 SECRET-R38"}
                )
            ]
        }
    )
    with pytest.raises(CapabilityError) as caught:
        plan.generate_function_expressions(wire2, ctx, runtime)
    assert "SECRET-R38" not in str(caught.value)
