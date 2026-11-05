"""Product tests for the reviewer gov-r35 blockers (F1–F4).

Every adversarial shape the reviewer drove through the real governance MCP
(``reviewer_gov_r35_adversarial.py``) is pinned here as a unit-level
regression test on the same fixtures the package suite uses:

* F1 — sensitivity scan/mask closes over *all* content that reaches the
  model: generic JSON with a ``rows`` key, extra table fields, structured
  cells and metadata included; unscannable shapes are rejected, never clean;
* F2 — acceptance eligibility is decided on the cited frozen manifest's own
  gold digests against the irreversible exposure index, so rewriting the
  latest case list (or rebinding a case id to fresh gold) cannot restore an
  exposed gold to unseen;
* F3 — the judgment comparator matches the delivery's target record/rule
  and resolves the criteria's requirements from the delivery itself, with
  source-anchored field evidence;
* F4 — join cardinality coverage is tracked per join node, so one analysable
  join cannot whitewash an unanalysed CROSS/non-equi sibling.
"""

from __future__ import annotations

import pytest

from dataagent_contracts.core import VersionedRef
from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.invoke import invoke

from dataagent_governance.contracts import (
    CriteriaConfirmation,
    EgressRule,
    PolicyDocument,
    PolicyRule,
)
from dataagent_governance.evaluation import (
    confirm_acceptance_criteria,
    isolate_acceptance_samples,
)
from dataagent_governance.governance.sensitivity import mask_content, scan_content
from dataagent_governance.runtime import GovernanceRuntime
from dataagent_governance.runtime.errors import CapabilityError, invalid_input
from tests.conftest import content_ref, source_anchor

from tests.governance.test_r24_fixes import (
    _acceptance_report,
    _confirm_criteria,
    _sensitivity_runtime,
    ctx,
)


# --- F1: no content shape is clean by shortcut -------------------------------- #


def _egress(rt, payload):
    """Mint the access decision, then ask for a vendor egress of payload."""

    ref = content_ref(rt, payload)
    access = (
        invoke("check_access_scope", {"resource_ref": str(ref)}, ctx(), runtime=rt)
        .data.decision.decision_id
    )
    return invoke(
        "check_model_context_egress",
        {
            "content_refs": [str(ref)],
            "destination": {"model_ref": "model:vendor", "deployment": "vendor_api"},
            "access_decision_ref": access,
        },
        ctx(),
        runtime=rt,
    )


def _masked_payload(rt, result):
    _revision, artifact = rt.versions.current(
        "mask", result.data.decision.masking_ref
    )
    return rt.content.get_json(artifact["masked_content_ref"])


@pytest.mark.parametrize(
    "payload",
    [
        # a generic JSON object whose *rows* happen to be dicts: not a table
        pytest.param(
            {"rows": [{"secret_code": "SECRET-R35", "phone": 13800138000}]},
            id="json-rows-of-dicts",
        ),
        # a valid table shape carrying an extra sensitive top-level field
        pytest.param(
            {
                "sheet": "orders",
                "columns": [{"field_id": "amount", "name": "amount"}],
                "rows": [[1]],
                "secret_code": "SECRET-R35",
            },
            id="table-extra-field",
        ),
        # a valid table shape with a structured (dict) cell
        pytest.param(
            {
                "sheet": "orders",
                "columns": [{"field_id": "metadata", "name": "metadata"}],
                "rows": [[{"secret_code": "SECRET-R35"}]],
            },
            id="table-structured-cell",
        ),
        # table metadata (row_meta) is content too: a declared key inside it
        pytest.param(
            {
                "sheet": "orders",
                "columns": [{"field_id": "amount", "name": "amount"}],
                "rows": [[1]],
                "row_meta": [{"role": "detail", "secret_code": "SECRET-R35"}],
            },
            id="table-row-meta",
        ),
    ],
)
def test_sensitive_content_is_found_and_masked_whatever_the_shape(tmp_path, payload):
    rt = _sensitivity_runtime(tmp_path)
    result = _egress(rt, payload)
    assert result.status == "ok", result.issues
    findings = result.data.sensitivity.findings
    assert any(f.kind == "declared_field" and f.field == "secret_code" for f in findings)
    # vendor_api + sensitive content: masked at best, never a raw allow
    assert result.data.decision.decision.value in {"allow_masked", "deny"}
    if result.data.decision.decision.value == "allow_masked":
        masked = _masked_payload(rt, result)
        assert "SECRET-R35" not in str(masked)
        assert "13800138000" not in str(masked)


def test_clean_table_is_allowed_and_survives_masking_verbatim(tmp_path):
    rt = _sensitivity_runtime(tmp_path)
    payload = {
        "sheet": "orders",
        "columns": [
            {"field_id": "amount", "name": "amount"},
            {"field_id": "note", "name": "note"},
        ],
        "rows": [[1, "ok"], [2, "fine"]],
        "row_meta": [],
        "merged_ranges": [],
        "source": {"origin": "fixture"},
    }
    result = _egress(rt, payload)
    assert result.status == "ok", result.issues
    assert result.data.sensitivity.findings == []
    assert result.data.decision.decision.value == "allow"
    # and a masked pass-through of clean content is the content itself
    masked, artifact = mask_content(payload, ["secret_code"])
    assert masked == payload
    assert artifact.entries == []


def test_unscannable_shape_is_rejected_not_clean():
    with pytest.raises(CapabilityError):
        scan_content({"weird": object()}, ["secret_code"])
    with pytest.raises(CapabilityError):
        mask_content({"weird": object()}, ["secret_code"])


# --- F2: exposed gold stays demoted in the cited frozen revision -------------- #


GOLD = [
    {
        "record_key": "c1",
        "rule_id": "rule:limit",
        "expected_verdict": "pass",
        "expected_evidence_fields": ["amount"],
    }
]


def _judgment_set(rt, gold, case_id="c1", set_id=None):
    """Isolate one judgment case and freeze it (a fresh gold each call)."""

    return (
        invoke(
            "isolate_acceptance_samples",
            {
                "cases": [
                    {
                        "case_id": case_id,
                        "input_ref": str(content_ref(rt, {"record": case_id})),
                        "expected_ref": str(content_ref(rt, gold)),
                        "group_keys": {"entity": case_id},
                    }
                ],
                "group_keys": ["entity"],
                "freeze": True,
                "role_weights": {
                    "development": 0,
                    "regression": 0,
                    "unseen_acceptance": 1,
                },
                **({"set_id": set_id} if set_id else {}),
            },
            ctx(),
            runtime=rt,
        )
        .data.evaluation_set
    )


def _active_criteria(rt):
    drafted = invoke(
        "draft_acceptance_criteria",
        {
            "delivery_target": "t",
            "proposal": {
                "owner_ref": "user:alice",
                "family": "judgment",
                "expected_outputs": "o",
                "evidence_requirements": ["rule:limit"],
                "unknown_policy": "count_as_fail",
                "thresholds": {"pass_rate": 1.0},
            },
        },
        ctx(),
        runtime=rt,
    ).data.criteria
    return _confirm_criteria(rt, drafted)


def _assessment(case_id="c1", verdict="pass"):
    return {
        "case_id": case_id,
        "assessment": {
            "assessment_id": f"as:{case_id}",
            "target_ref": f"record:{case_id}@r1",
            "verdict": verdict,
            "basis_refs": ["rule:limit:amount"],
            "evidence": [],
        },
    }


def _accept(rt, criteria, samples, delivery):
    return invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{criteria.id}@{criteria.revision}",
            "evaluation_set_ref": f"{samples.id}@{samples.revision}",
            "deliveries": [delivery],
        },
        ctx(),
        runtime=rt,
    )


def test_exposed_gold_stays_demoted_after_case_list_replacement(rt):
    criteria = _active_criteria(rt)
    samples = _judgment_set(rt, GOLD)
    # control: the frozen revision accepts before any exposure
    control = _accept(rt, criteria, samples, _assessment())
    assert control.data.report.overall == "pass"

    # expose the gold through a non-acceptance read
    rt.vault.read_gold(
        str(samples.id), str(samples.revision), "c1",
        purpose="debug", accessed_by="reviewer",
    )
    demoted = _accept(rt, criteria, samples, _assessment())
    assert demoted.data.report.overall == "fail"
    assert demoted.data.report.cases == []

    # a new revision of the same set replaces the case list with fresh gold
    replacement = [
        {
            "record_key": "c2",
            "rule_id": "rule:limit",
            "expected_verdict": "pass",
            "expected_evidence_fields": ["other"],
        }
    ]
    _judgment_set(rt, replacement, case_id="c2", set_id=str(samples.id))

    # the *old frozen revision* must not become acceptable again: the old
    # gold digest is still in the irreversible exposure index (r35 F2)
    replay = _accept(rt, criteria, samples, _assessment())
    assert replay.data.report.overall == "fail"
    assert replay.data.report.cases == []
    assert "金标暴露" in (replay.data.report.limits[-1] if replay.data.report.limits else "")
    old_digest = (
        rt.vault.get_set(str(samples.id), str(samples.revision))["cases"][0][
            "expected_ref"
        ]
        .split("@")[-1]
    )
    assert old_digest in rt.vault.exposed_digests()


def test_exposed_gold_stays_demoted_after_same_case_new_gold(rt):
    criteria = _active_criteria(rt)
    samples = _judgment_set(rt, GOLD)
    rt.vault.read_gold(
        str(samples.id), str(samples.revision), "c1",
        purpose="debug", accessed_by="reviewer",
    )
    # rebind the same case id to fresh gold in a new revision
    fresh_gold = [
        {
            "record_key": "c1-new",
            "rule_id": "rule:limit",
            "expected_verdict": "fail",
            "expected_evidence_fields": ["other"],
        }
    ]
    _judgment_set(rt, fresh_gold, case_id="c1", set_id=str(samples.id))
    replay = _accept(rt, criteria, samples, _assessment())
    assert replay.data.report.overall == "fail"
    assert replay.data.report.cases == []


# --- F3: the delivery itself must locate the record, clauses and fields ------ #


def _field_evidence(rt, field="amount", anchors=True):
    evidence = {
        "id": f"field:{field}",
        "evidence_type": "extracted_value",
        "obtained_by": "da07.5.1/evaluate_scalar_expression",
    }
    if anchors:
        # r38 F5: the anchor must actually resolve — a real JSON source,
        # content-addressed in the shared store, with a json pointer that
        # locates the value.
        evidence["source_anchors"] = [
            source_anchor(rt, {"records": [{"amount": 100}]}, "/records/0/amount")
        ]
    return evidence


def test_correct_target_and_anchored_evidence_passes(rt):
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "assessment": {
                "assessment_id": "as:1",
                "target_ref": "record:c1@r1",
                "verdict": "pass",
                "basis_refs": ["rule:limit:amount"],
                "evidence": [_field_evidence(rt)],
            },
        },
        GOLD,
        family="judgment",
    )
    assert report.overall == "pass"


def test_wrong_record_without_anchored_evidence_fails(rt):
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "assessment": {
                "assessment_id": "as:1",
                # the delivery is about an unrelated record
                "target_ref": "record:unrelated@r99",
                "verdict": "pass",
                # no clause basis at all
                "basis_refs": [],
                # and the field evidence carries no source anchors
                "evidence": [_field_evidence(rt, anchors=False)],
            },
        },
        GOLD,
        family="judgment",
    )
    assert report.overall == "fail"
    notes = report.cases[0].notes or ""
    assert "evidence_missing" in notes
    assert "does not locate the expected record" in notes


def test_gold_listing_cannot_substitute_for_delivery_basis(rt):
    # the criteria demand rule:limit and the gold names rule:limit, but the
    # delivery cites neither: the gold's own listing is not the delivery's
    # citation (r35 F3)
    report = _acceptance_report(
        rt,
        {
            "case_id": "c1",
            "assessment": {
                "assessment_id": "as:1",
                "target_ref": "record:c1@r1",
                "verdict": "pass",
                "basis_refs": ["spec:totally-unrelated"],
                "evidence": [_field_evidence(rt)],
            },
        },
        GOLD,
        family="judgment",
    )
    assert report.overall == "fail"
    assert "evidence_missing" in (report.cases[0].notes or "")


# --- F4: join coverage is tracked per join node ------------------------------- #


def _table(rt, name, columns, rows):
    payload = {
        "sheet": name,
        "columns": [{"name": c, "field_id": c} for c in columns],
        "rows": rows,
        "row_meta": [],
        "merged_ranges": [],
        "source": {"origin": "fixture"},
    }
    digest = rt.content.put(payload)
    return {
        "asset": {
            "id": f"table:{name}",
            "kind": "table",
            "scope_ref": "tenant:demo",
            "revision": digest,
            "resolver": "local_content",
            "locator": digest,
            "digest": digest,
        },
        "schema_ref": f"schema:{name}@r1",
        "data_ref": digest,
    }


def _grain(rt, sql, tables, output, grain_keys, measures=("amount",), total_rows=None):
    authorization = (
        invoke("check_access_scope", {"resource_ref": "table@*"}, ctx(), runtime=rt)
        .data.decision.decision_id
    )
    if total_rows is None:
        total_rows = len(output["rows"]) if isinstance(output.get("rows"), list) else 3
    return invoke(
        "check_result_grain_and_merge",
        {
            "spec": {
                "spec_id": "spec:mixed",
                "revision": "r1",
                "backend_kind": "sql",
                "expression_or_call": {"sql": sql, "dialect": "duckdb"},
            },
            "input_tables": tables,
            "output_table": output,
            "declared_grain": list(grain_keys),
            "measure_fields": list(measures),
            "pagination": {"page_size": 10, "pages": 1, "declared_total_rows": total_rows},
        },
        ctx(authorization_ref=authorization),
        runtime=rt,
    )


def test_mixed_equi_and_cross_join_is_not_a_pass(rt):
    left = _table(rt, "left_t", ["id", "amount"], [["l1", 0]])
    right = _table(rt, "right_t", ["id"], [["l1"]])
    other = _table(rt, "other_t", ["rid"], [["r1"], ["r2"], ["r3"]])
    out = _table(
        rt, "out_t", ["id", "rid", "amount"],
        [["l1", "r1", 0], ["l1", "r2", 0], ["l1", "r3", 0]],
    )
    result = _grain(
        rt,
        "SELECT l.id, o.rid, l.amount FROM left_t l "
        "JOIN right_t r ON l.id = r.id CROSS JOIN other_t o",
        [left, right, other],
        out,
        ("id", "rid"),
    )
    assert result.status == "ok", result.issues
    items = {i.check: i for i in result.data.report.items}
    # the CROSS JOIN multiplies rows but is not analysable: at least unknown,
    # never a pass whitewashed by the analysable 1:1 join (r35 F4)
    assert items["join_cardinality"].outcome == "unknown"
    assert result.data.report.overall == "unknown"
    joins = items["join_cardinality"].evidence["joins"]
    assert any(j.get("analyzed") is False for j in joins)
    assert any("cardinality" in j for j in joins)


def test_single_equi_join_control_still_passes(rt):
    left = _table(rt, "left_t", ["id", "amount"], [["l1", 100]])
    right = _table(rt, "right_t", ["id"], [["l1"]])
    out = _table(rt, "out_t", ["id", "amount"], [["l1", 100]])
    result = _grain(
        rt,
        "SELECT l.id, l.amount FROM left_t l JOIN right_t r ON l.id = r.id",
        [left, right],
        out,
        ("id",),
        total_rows=1,
    )
    assert result.status == "ok", result.issues
    items = {i.check: i for i in result.data.report.items}
    assert items["join_cardinality"].outcome == "pass"
    assert result.data.report.overall == "pass"


def test_or_condition_join_is_not_an_equi_pair(rt):
    # an EQ under OR does not constrain the join: the join stays unanalysed
    left = _table(rt, "left_t", ["id", "amount"], [["l1", 100]])
    right = _table(rt, "right_t", ["id"], [["l1"], ["l2"]])
    out = _table(rt, "out_t", ["id", "amount"], [["l1", 100]])
    result = _grain(
        rt,
        "SELECT l.id, l.amount FROM left_t l "
        "JOIN right_t r ON l.id = r.id OR l.amount > 0",
        [left, right],
        out,
        ("id",),
        total_rows=1,
    )
    assert result.status == "ok", result.issues
    items = {i.check: i for i in result.data.report.items}
    assert items["join_cardinality"].outcome == "unknown"
    assert result.data.report.overall == "unknown"
