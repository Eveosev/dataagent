"""Product tests for the tester gov-r40 residual defects (F1–F4).

The r39 fixes closed the reviewer r38 blockers; the tester's independent
probe found four same-family residuals, two of which live in this package:

* **F2** — masked object keys that collide (two phone numbers sharing
  first and last digit mask to the same text) silently dropped the earlier
  entry: the masked payload was no longer faithful to the input. Keys are
  now made unique *at insertion time* with a stable ``~<n>`` suffix, both
  in the structural walk and under a declared sensitive field.
* **F4** — record identity still accepted the *rule's local name*: a
  delivery targeting ``record:required@r1`` / ``spec:required@r1`` passed
  acceptance against gold record ``c1`` under rule ``rule:required``
  without ever naming the record. The record side now locates the record
  by full identity (or the r38 single-pair exact rule target) — a local
  name is only ever a *rule-side* compiled-spec approximation.

(The F1 residuals live in dataagent-application; see
``tests/test_r40_egress_content_binding.py`` there.)
"""

from __future__ import annotations

import json

from dataagent_governance.governance.sensitivity import mask_content

from tests.governance.test_r24_fixes import _acceptance_report, ctx
from tests.governance.test_r38_fixes import GOLD
from tests.conftest import source_anchor


def _delivery(target, rt, basis=("rule:limit:amount",)):
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
                        source_anchor(rt, {"records": [{"amount": 100}]})
                    ],
                }
            ],
        },
    }


def _judgment_gold(record_key="c1", rule_id="rule:limit"):
    return [
        {
            "record_key": record_key,
            "rule_id": rule_id,
            "expected_verdict": "pass",
            "expected_evidence_fields": ["amount"],
        }
    ]


# --- F4: the record side never falls back to the rule's local name ------------- #


def test_record_target_with_the_rules_local_name_does_not_locate_the_record(rt):
    # gold record c1 under rule rule:required; the delivery targets
    # record:required@r1 — the rule's *local name*, not the record
    gold = _judgment_gold(rule_id="rule:required")
    for target in ("record:required@r1", "spec:required@r1"):
        report = _acceptance_report(rt, _delivery(target, rt), gold, family="judgment")
        assert report.overall == "fail", target
        note = report.cases[0].notes or ""
        assert "does not locate the expected record" in note, target


def test_wrong_namespace_record_target_does_not_locate_the_record(rt):
    # a namespaced record key is located only by its full namespace: a
    # target ending in the same local name under another namespace fails
    gold = _judgment_gold(record_key="tenant:alpha/c1")
    report = _acceptance_report(
        rt,
        _delivery("record:tenant:beta/c1@r1", rt),
        gold,
        family="judgment",
    )
    assert report.overall == "fail"
    # control: the full namespaced key under any prefix/revision passes
    ok = _acceptance_report(
        rt,
        _delivery("record:tenant:alpha/c1@r1", rt),
        gold,
        family="judgment",
    )
    assert ok.overall == "pass"


def test_full_identity_record_target_still_passes(rt):
    # control: the record's own full key (any prefix/revision) passes
    for target in ("record:c1@r1", "tenant:alpha/c1@r2", "c1@r1"):
        report = _acceptance_report(rt, _delivery(target, rt), _judgment_gold(), family="judgment")
        assert report.overall == "pass", target


def test_exact_rule_target_still_covers_the_single_pair(rt):
    # control (r38 F4 semantics): targeting the rule itself is the
    # single-record single-rule shape; reuse across records still fails
    report = _acceptance_report(
        rt, _delivery("rule:limit@r1", rt), _judgment_gold(), family="judgment"
    )
    assert report.overall == "pass"
    two_records = _judgment_gold() + _judgment_gold(record_key="c2")
    report = _acceptance_report(
        rt, _delivery("rule:limit@r1", rt), two_records, family="judgment"
    )
    assert report.overall == "fail"


# --- F2: colliding masked keys keep every entry -------------------------------- #


def test_colliding_masked_keys_keep_every_entry(rt):
    # two phone numbers sharing first and last digit mask to the same text;
    # the masked payload must keep both entries, not silently drop one
    payload = {"13800138000": {"v": 1}, "13900139000": {"v": 2}}
    masked, artifact = mask_content(payload, [])
    assert len(masked) == 2
    assert masked["1*********0"] == {"v": 1}
    assert masked["1*********0~1"] == {"v": 2}
    # both original keys are gone and the artifact keeps two key entries
    dumped = json.dumps(masked, ensure_ascii=False)
    assert "13800138000" not in dumped and "13900139000" not in dumped
    assert sum(1 for e in artifact.entries if e.field is None) >= 2


def test_colliding_masked_keys_under_a_declared_sensitive_field(rt):
    # the same collision under a declared sensitive field goes through the
    # whole-value masking path — it must keep every entry too
    payload = {"secret_code": {"13800138000": 1, "13900139000": 2}}
    masked, _ = mask_content(payload, ["secret_code"])
    inner = masked["secret_code"]
    # both entries survive with distinct keys; the values under a declared
    # sensitive field are whole-masked, which is the field's obligation
    assert len(inner) == 2
    assert len(set(inner)) == 2


def test_three_way_key_collision_gets_stable_suffixes(rt):
    payload = {
        "13800138000": 1,
        "13900139000": 2,
        "13700137000": 3,
    }
    masked, _ = mask_content(payload, [])
    assert sorted(masked.values()) == [1, 2, 3]
    assert len(masked) == 3
    keys = list(masked)
    assert keys[0] == "1*********0" and keys[1] == "1*********0~1" and keys[2] == "1*********0~2"
