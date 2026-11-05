"""Product tests for the reviewer gov-r38 blockers (F1–F6).

Every adversarial shape the reviewer drove through the real governance /
application / data MCP paths (``reviewer_gov_r38_independent.py``) is pinned
here as a unit-level regression test on the package fixtures:

* F2 — identifiers carried by JSON object **keys** are findings exactly like
  values; masking rewrites the keys (with collision handling) and locators
  never leak the raw key;
* F3 — reading a registered gold digest through any official read path
  (governance egress scanning, a data-layer file read simulated through the
  shared ledger) records an exposure and the case can no longer pass as
  unseen acceptance;
* F4 — one Assessment is the unique delivery of at most one record×rule
  expectation: a rule target reused across records, a record target
  standing in for several rules, and a local-name collision between
  namespaced records all fail;
* F5 — a source anchor that does not resolve against content the shared
  store holds (label revision, missing content, non-json_pointer selector,
  missing pointer target) is not evidence;
* F6 — a join predicate's equality orientation is not its side orientation:
  pairs are normalized to (prior side, newly joined side), so a reversed
  equality still detects the 1:N fan-out while same-side and prior-only
  predicates leave the join unanalysed.
"""

from __future__ import annotations

import json

import pytest

from dataagent_runtime.adapters.gold_ledger import GoldExposureLedger
from dataagent_runtime.invoke import invoke

from dataagent_governance.contracts import EgressRule, PolicyDocument, PolicyRule
from dataagent_governance.governance.sensitivity import mask_content, scan_content

from tests.conftest import content_ref, source_anchor
from tests.governance.test_r24_fixes import (
    _acceptance_report,
    _confirm_criteria,
    ctx,
)

from tests.governance.test_r35_fixes import GOLD, _table, _grain


# --- F2: JSON object keys are model-visible content -------------------------- #


# egress over plain (non-table) content: a policy that allows the content
# resources and the vendor destination, mirroring the reviewer probe setup
CONTENT_POLICY = PolicyDocument(
    policy_id="tenant:default",
    revision="r1",
    rules=[
        PolicyRule(
            rule_id="allow-content",
            effect="allow",
            subjects=["user:alice"],
            resources=["content"],
            purposes=["monthly_report"],
        )
    ],
    egress_rules=[
        EgressRule(rule_id="vendor-api", effect="allow", deployments=["vendor_api"]),
    ],
)


def _egress_decision_for(rt, payload):
    rt.policy.save(CONTENT_POLICY)
    ref = content_ref(rt, payload)
    text = f"{ref.id}@{ref.revision}"
    access = (
        invoke("check_access_scope", {"resource_ref": text}, ctx(), runtime=rt)
        .data.decision.decision_id
    )
    return invoke(
        "check_model_context_egress",
        {
            "content_refs": [text],
            "destination": {"model_ref": "model:vendor", "deployment": "vendor_api"},
            "access_decision_ref": access,
        },
        ctx(),
        runtime=rt,
    )


def test_identifier_object_keys_are_findings(rt):
    keyed = {"13800138000": {"ok": True}, "alice@example.com": "public"}
    report = scan_content(keyed, ["secret_code"])
    kinds = {(f.kind, f.field) for f in report.findings}
    assert ("phone", None) in kinds
    assert ("email", None) in kinds


def test_identifier_object_keys_masked_with_collision_handling(rt):
    keyed = {
        "13800138000": 1,
        "13800138001": 2,  # masks to a colliding shape
        "nested": {"bob@corp.com": True},
    }
    masked, artifact = mask_content(keyed, [])
    wire = json.dumps(masked, ensure_ascii=False) + json.dumps(
        [e.locator for e in artifact.entries]
    )
    assert "13800138000" not in wire
    assert "13800138001" not in wire
    assert "bob@corp.com" not in wire
    # distinct masked keys stay distinct
    assert len(set(masked)) == len(masked)
    assert set(masked["nested"].values()) == {True}


def test_declared_field_masking_rewrites_keys_inside_the_cell(rt):
    payload = {"secret_code": {"13800138000": True, "ok": 2}}
    masked, _artifact = mask_content(payload, ["secret_code"])
    wire = json.dumps(masked, ensure_ascii=False)
    assert "13800138000" not in wire
    assert "ok" in wire  # non-identifier keys keep their names


def test_key_findings_never_leak_the_key_in_locators():
    report = scan_content(
        {"13800138000": {"x": "alice@example.com"}}, ["secret_code"]
    )
    for finding in report.findings:
        assert "13800138000" not in finding.locator


def test_keyed_content_gets_vendor_floor_through_the_mcp_path(rt):
    # the reviewer's exact payload: identifiers only in keys must reach the
    # shared egress gate as sensitive content
    keyed = {"13800138000": {"ok": True}, "alice@example.com": "public"}
    result = _egress_decision_for(rt, keyed)
    assert result.status == "ok", result.issues
    assert result.data.decision.decision == "allow_masked"
    assert result.data.sensitivity.findings


# --- F3: official reads of gold record an exposure ---------------------------- #


def _isolated_set(rt, gold):
    samples = invoke(
        "isolate_acceptance_samples",
        {
            "cases": [
                {
                    "case_id": "c1",
                    "input_ref": "content:input@sha256:0",
                    "expected_ref": f"content:gold@{rt.content.put(gold)}",
                    "group_keys": {"entity": "c1"},
                }
            ],
            "group_keys": ["entity"],
            "freeze": True,
        },
        ctx(),
        runtime=rt,
    ).data.evaluation_set
    return samples


def _accept(rt, samples, gold=GOLD):
    criteria = invoke(
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
    active = _confirm_criteria(rt, criteria)
    return invoke(
        "evaluate_business_acceptance",
        {
            "criteria_ref": f"{active.id}@{active.revision}",
            "evaluation_set_ref": f"{samples.id}@{samples.revision}",
            "deliveries": [
                {
                    "case_id": "c1",
                    "assessment": {
                        "assessment_id": "as:1",
                        "target_ref": "record:c1@r1",
                        "verdict": "pass",
                        "basis_refs": ["rule:limit:amount"],
                        "evidence": [
                            {
                                "id": "field:amount",
                                "evidence_type": "extracted_value",
                                "obtained_by": "probe",
                                "source_anchors": [
                                    source_anchor(
                                        rt, {"records": [{"amount": 100}]},
                                        "/records/0/amount",
                                    )
                                ],
                            }
                        ],
                    },
                }
            ],
        },
        ctx(),
        runtime=rt,
    ).data.report


def test_gold_read_through_governance_egress_records_exposure(rt):
    samples = _isolated_set(rt, GOLD)
    assert _accept(rt, samples).overall == "pass"  # before the exposure
    gold_digest = rt.vault.get_set(str(samples.id), str(samples.revision))["cases"][0][
        "expected_ref"
    ].split("@")[-1]
    # an official governance read: the egress scan reads the gold content
    _egress_decision_for(rt, GOLD)
    assert gold_digest in rt.vault.exposed_digests()
    after = _accept(rt, samples)
    assert after.overall == "fail"
    assert after.cases == []


def test_gold_read_through_the_cross_layer_ledger_demotes(rt):
    # a data/application-layer read on the same data_root writes the shared
    # ledger; the vault must honour it exactly like its own index
    samples = _isolated_set(rt, GOLD)
    gold_digest = rt.vault.get_set(str(samples.id), str(samples.revision))["cases"][0][
        "expected_ref"
    ].split("@")[-1]
    ledger = GoldExposureLedger(rt.data_root / "vault")
    assert ledger.is_gold(gold_digest)
    ledger.note_exposure(gold_digest, purpose="file-read", accessed_by="data-layer")
    assert gold_digest in rt.vault.exposed_digests()
    assert _accept(rt, samples).overall == "fail"


# --- F4: unique record×rule delivery association ------------------------------ #


@pytest.fixture()
def delivery_factory(rt):
    # the evidence anchor must resolve against this runtime's store
    def make(target, basis=("rule:limit:amount",)):
        return {
            "case_id": "c1",
            "assessment": {
                "assessment_id": "as:1",
                "target_ref": target,
                "verdict": "pass",
                "basis_refs": list(basis),
                "evidence": [
                    {
                        "id": "field:amount",
                        "evidence_type": "extracted_value",
                        "obtained_by": "probe",
                        "source_anchors": [
                            source_anchor(
                                rt, {"records": [{"amount": 100}]}, "/records/0/amount"
                            )
                        ],
                    }
                ],
            },
        }

    return make


def test_rule_target_reused_across_records_fails(rt, delivery_factory):
    gold = GOLD + [
        {
            "record_key": "c2",
            "rule_id": "rule:limit",
            "expected_verdict": "pass",
            "expected_evidence_fields": ["amount"],
        }
    ]
    report = _acceptance_report(
        rt, delivery_factory("rule:limit@r1"), gold, family="judgment"
    )
    assert report.overall == "fail"
    assert "cannot be the unique delivery" in (report.cases[0].notes or "")


def test_record_target_reused_across_rules_fails(rt, delivery_factory):
    gold = GOLD + [
        {
            "record_key": "c1",
            "rule_id": "rule:other",
            "expected_verdict": "pass",
            "expected_evidence_fields": ["amount"],
        }
    ]
    report = _acceptance_report(
        rt, delivery_factory("record:c1@r1"), gold, family="judgment"
    )
    assert report.overall == "fail"
    notes = report.cases[0].notes or ""
    assert "cannot be the unique delivery" in notes or "evidence_missing" in notes


def test_wrong_namespace_record_fails_on_full_identity(rt, delivery_factory):
    gold = [
        {
            "record_key": "tenant:alpha/c1",
            "rule_id": "rule:limit",
            "expected_verdict": "pass",
            "expected_evidence_fields": ["amount"],
        }
    ]
    # a different namespaced record with the same local name must not match
    report = _acceptance_report(
        rt, delivery_factory("record:tenant:beta/c1@r1"), gold, family="judgment"
    )
    assert report.overall == "fail"
    assert "does not locate the expected record" in (report.cases[0].notes or "")


def test_single_pair_rule_target_still_passes(rt, delivery_factory):
    # the compiled-spec shape of r24's real delivery: one record, one rule,
    # the target is the rule itself
    report = _acceptance_report(
        rt, delivery_factory("rule:limit@r1"), GOLD, family="judgment"
    )
    assert report.overall == "pass"


# --- F5: source anchors must resolve ----------------------------------------- #


def test_label_revision_anchor_is_not_evidence(rt):
    delivery = {
        "case_id": "c1",
        "assessment": {
            "assessment_id": "as:1",
            "target_ref": "record:c1@r1",
            "verdict": "pass",
            "basis_refs": ["rule:limit:amount"],
            "evidence": [
                {
                    "id": "field:amount",
                    "evidence_type": "extracted_value",
                    "obtained_by": "probe",
                    "source_anchors": [
                        {
                            "source_ref": "orders.csv",
                            "source_revision": "r1",
                            "selector": {"kind": "excel_cell", "sheet": "S", "range": "B2"},
                        }
                    ],
                }
            ],
        },
    }
    report = _acceptance_report(rt, delivery, GOLD, family="judgment")
    assert report.overall == "fail"
    assert "source_revision is not a content address" in (report.cases[0].notes or "")


def test_unresolvable_pointer_is_not_evidence(rt):
    # a real content address, but a pointer that locates nothing
    digest = rt.content.put({"records": [{"amount": 100}]})
    delivery = {
        "case_id": "c1",
        "assessment": {
            "assessment_id": "as:1",
            "target_ref": "record:c1@r1",
            "verdict": "pass",
            "basis_refs": ["rule:limit:amount"],
            "evidence": [
                {
                    "id": "field:amount",
                    "evidence_type": "extracted_value",
                    "obtained_by": "probe",
                    "source_anchors": [
                        {
                            "source_ref": "content:x",
                            "source_revision": digest,
                            "selector": {"kind": "json_pointer", "pointer": "/nope/0"},
                        }
                    ],
                }
            ],
        },
    }
    report = _acceptance_report(rt, delivery, GOLD, family="judgment")
    assert report.overall == "fail"
    assert "does not locate a value" in (report.cases[0].notes or "")


def test_resolvable_anchor_passes(rt, delivery_factory):
    report = _acceptance_report(
        rt, delivery_factory("record:c1@r1"), GOLD, family="judgment"
    )
    assert report.overall == "pass"


# --- F6: join side closure and orientation invariance ------------------------ #


def _one_to_many_tables(rt):
    left = _table(rt, "left_t", ["id", "amount"], [["l1", 0]])
    many = _table(rt, "right_t", ["id", "rid"], [["l1", "r1"], ["l1", "r2"], ["l1", "r3"]])
    out = _table(
        rt, "out_t", ["id", "rid", "amount"],
        [["l1", "r1", 0], ["l1", "r2", 0], ["l1", "r3", 0]],
    )
    return left, many, out


def test_reversed_equality_still_detects_the_one_to_many(rt):
    left, many, out = _one_to_many_tables(rt)
    result = _grain(
        rt,
        "SELECT l.id, r.rid, l.amount FROM left_t l JOIN right_t r ON r.id = l.id",
        [left, many],
        out,
        ("id", "rid"),
    )
    assert result.status == "ok", result.issues
    items = {i.check: i for i in result.data.report.items}
    assert items["join_cardinality"].outcome == "fail"
    assert result.data.report.overall == "fail"


def test_same_side_equality_does_not_support_the_join(rt):
    left, many, out = _one_to_many_tables(rt)
    result = _grain(
        rt,
        "SELECT l.id, r.rid, l.amount FROM left_t l JOIN right_t r ON l.id = l.id",
        [left, many],
        out,
        ("id", "rid"),
    )
    assert result.status == "ok", result.issues
    items = {i.check: i for i in result.data.report.items}
    assert items["join_cardinality"].outcome == "unknown"


def test_prior_tables_only_predicate_does_not_support_the_second_join(rt):
    left = _table(rt, "left_t", ["id", "amount"], [["l1", 0]])
    one = _table(rt, "right_one", ["id"], [["l1"]])
    many = _table(rt, "right_t", ["id", "rid"], [["l1", "r1"], ["l1", "r2"], ["l1", "r3"]])
    out = _table(
        rt, "out_t", ["id", "rid", "amount"],
        [["l1", "r1", 0], ["l1", "r2", 0], ["l1", "r3", 0]],
    )
    result = _grain(
        rt,
        "SELECT l.id, r.rid, l.amount FROM left_t l "
        "JOIN right_one o ON l.id = o.id JOIN right_t r ON l.id = o.id",
        [left, one, many],
        out,
        ("id", "rid"),
    )
    assert result.status == "ok", result.issues
    items = {i.check: i for i in result.data.report.items}
    assert items["join_cardinality"].outcome == "unknown"
