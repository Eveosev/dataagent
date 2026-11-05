"""Deterministic comparators for the judgment and compute families (08 §5.3).

Judgment: per record and per rule the verdict must match; ``unknown`` is
scored per ``unknown_policy``; the delivery's ``Assessment.target_ref`` must
locate the gold's record by **full identity** together with the rule among
the delivery's own references, and one Assessment is the unique delivery of
at most **one** record×rule expectation — a rule target reused across
records, or a record target standing in for several rules, is not a
per-record per-rule comparison (r38 F4). The criteria's evidence
requirements must be resolvable from the **delivery** — basis refs, target
and dependencies, never the gold's own listing — and the evidence must
locate the expected fields through **structured** references whose source
anchors exist *and resolve against the cited source content*: a free-form
basis string that merely *contains* a field name, a ``field:`` evidence
without source anchors, or an anchor whose source revision is not a
content address that the store actually holds with a selector that locates
a value, is not evidence (reviews B4, r35 F3, r38 F5). Business verdict
aliases from the application layer (``satisfied`` / ``violated``) are
mapped onto the canonical gold vocabulary (review B5).

Compute: numeric comparison inside the criteria tolerance with finite
values only, unit/grain/filters alignment, and every gold-required metric
must actually be delivered (review B4).
"""

from __future__ import annotations

import math
from typing import Any

from dataagent_contracts.core import Verdict

from dataagent_governance.contracts import (
    EvaluationDelivery,
    ExpectedComputation,
    ExpectedJudgment,
)

__all__ = ["compare_judgment", "compare_compute", "deterministic_evaluators"]

# Business verdict vocabularies that mean the same thing as the canonical
# gold values (05 core ``Verdict``). The application layer's DA07.5 emits the
# canonical values; older/other producers may use the business aliases.
_VERDICT_ALIASES = {
    "satisfied": "pass",
    "violated": "fail",
    "passed": "pass",
    "failed": "fail",
}


def _canonical_verdict(verdict: Any) -> str:
    actual = getattr(verdict, "value", verdict)
    actual = str(actual)
    return _VERDICT_ALIASES.get(actual, actual)


def _local_name(ref: str) -> str:
    """The id's local name: the last ``:``/``/`` segment, revision stripped.

    The application layer compiles ``rule:limit`` into an ``ExecutableSpec``
    whose id is the rule's local name (``limit``); a delivery that cites the
    compiled spec still points at the rule (W0 §4 source-refs chain,
    approximated deterministically by the naming convention).
    """

    return ref.split("@", 1)[0].rsplit(":", 1)[-1].rsplit("/", 1)[-1]


def _extends(anchor: str, ref: str) -> bool:
    """``ref`` points at ``anchor`` itself, a subtree of it, at the same
    id under any revision (``anchor@r2`` still locates ``anchor``), or at
    the anchor's local name (the compiled-spec id of the same rule).

    The local-name branch is for the *rule* side only — a compiled
    ``ExecutableSpec`` named after its rule still points at that rule. It
    must never stand in for record identity: see
    ``_rule_target_locates_record`` (r40 F4).
    """

    if ref == anchor:
        return True
    if ref.startswith(anchor + ":") or ref.startswith(anchor + "/"):
        return True
    if "@" in ref and ref.split("@", 1)[0] == anchor:
        return True
    local = _local_name(anchor)
    return bool(local) and _local_name(ref) == local


def _rule_target_locates_record(rule_id: str, target_id: str) -> bool:
    """The delivery targets the *rule itself* (r38 F4 single-pair shape).

    Exact rule identity only — same id, subtree, or any revision — never
    the local-name fallback (r40 F4): ``record:required@r1`` and
    ``spec:required@r1`` share ``rule:required``'s local name but are
    different objects; without the record's full key in the target they do
    not locate the record.
    """

    return (
        target_id == rule_id
        or target_id.startswith(rule_id + ":")
        or target_id.startswith(rule_id + "/")
        or ("@" in target_id and target_id.split("@", 1)[0] == rule_id)
    )


def _locates_record(ref_id: str, record_key: str) -> bool:
    """Full-identity record location (r38 F4).

    ``record:<key>``, ``<prefix>:<key>``, ``<prefix>/<key>`` or the bare key
    all locate the record — but the *local name* of a namespaced key never
    does: ``tenant:alpha/c1`` and ``record:tenant:beta/c1`` are different
    records even though both end in ``c1``.
    """

    return (
        ref_id == record_key
        or ref_id.endswith(":" + record_key)
        or ref_id.endswith("/" + record_key)
    )


def _evidence_ids(delivery_assessment: Any) -> dict[str, bool]:
    """``id -> carries at least one source anchor``.

    A ``field:<field>`` evidence locates its field only when it says where
    the value came from; without source anchors it is an unverifiable claim,
    not evidence (r35 F3).
    """

    ids: dict[str, bool] = {}
    for evidence in getattr(delivery_assessment, "evidence", None) or []:
        evidence_id = str(getattr(evidence, "id", "") or "")
        if evidence_id:
            anchored = bool(getattr(evidence, "source_anchors", None))
            ids[evidence_id] = ids.get(evidence_id, False) or anchored
    return ids


def _locates_field(
    evidence_ids: dict[str, bool], basis: set[str], anchors: set[str], field: str
) -> bool:
    """Can the delivery's evidence locate ``field`` under one of the anchors?

    Structured evidence wins: an ``EvidenceRef`` with id ``field:<field>``
    *and* at least one source anchor (the W0 §4 convention) names the field
    that participated. Otherwise a basis reference of the form
    ``<anchor>:<field>`` (or ``<anchor>/<field>``) locates the field inside
    the rule/requirement the gold names. A bare substring match, or a
    ``field:`` evidence without source anchors, is never evidence.
    """

    if evidence_ids.get(f"field:{field}"):
        return True
    for anchor in anchors:
        if f"{anchor}:{field}" in basis or f"{anchor}/{field}" in basis:
            return True
    return False


def compare_judgment(
    criteria: dict[str, Any],
    expected: list[ExpectedJudgment],
    delivery: EvaluationDelivery,
) -> tuple[Verdict, list[str]]:
    unknown_policy = criteria.get("unknown_policy", "count_as_fail")
    reasons: list[str] = []
    if delivery.timed_out or delivery.budget_exhausted:
        return Verdict.fail, ["delivery timed out or exhausted its budget"]
    if delivery.assessment is None:
        return Verdict.fail, ["judgment case requires an Assessment delivery"]
    assessment = delivery.assessment
    basis = {str(ref) for ref in assessment.basis_refs}
    evidence_ids = _evidence_ids(assessment)
    target = str(assessment.target_ref)
    target_id = target.split("@", 1)[0]
    dependencies = {
        str(ref) for ref in getattr(assessment, "dependency_refs", None) or []
    }
    # What the delivery itself cites; the gold's own listing can never
    # substitute for it (r35 F3).
    delivery_refs = basis | dependencies | {target}
    requirements = [str(r) for r in criteria.get("evidence_requirements") or []]
    unknowns = 0
    fails = 0
    # Unique record×rule delivery association (r38 F4): every expected
    # (record, rule) pair must be covered by this delivery, and one
    # Assessment — one verdict object — can cover at most ONE pair. A
    # rule-targeted assessment reused across several records, a record
    # target standing in for several rules of the same record, and a
    # local-name collision between namespaced records all fail here.
    # r40 F4: the record side never falls back to the rule's local name —
    # a target that merely shares it (``record:required`` / ``spec:required``
    # against rule ``rule:required``) is a different object and does not
    # locate the record.
    covered: list[ExpectedJudgment] = []
    for exp in expected:
        record_located = _locates_record(target_id, exp.record_key) or (
            _rule_target_locates_record(exp.rule_id, target_id)
        )
        rule_located = any(_extends(exp.rule_id, ref) for ref in delivery_refs)
        if not record_located or not rule_located:
            fails += 1
            reasons.append(
                f"{exp.record_key}/{exp.rule_id}: evidence_missing — delivery "
                f"target {target_id!r} does not locate the expected record "
                "(full identity) together with the rule among the delivery's "
                "own references"
            )
            continue
        covered.append(exp)
    if len(covered) > 1:
        fails += len(covered)
        reasons.append(
            "evidence_missing — a single Assessment carries one verdict and "
            f"cannot be the unique delivery for {len(covered)} record×rule "
            "expectations ("
            + ", ".join(f"{e.record_key}/{e.rule_id}" for e in covered)
            + "); deliver one Assessment per expectation"
        )
        covered = []
    for exp in covered:
        anchors = set(requirements) | {exp.rule_id}
        actual = _canonical_verdict(assessment.verdict)
        if actual == "unknown":
            # ``unknown`` is scored per unknown_policy (08 §5.3).
            if unknown_policy == "count_as_fail":
                fails += 1
                reasons.append(
                    f"{exp.record_key}/{exp.rule_id}: delivery verdict unknown counts as fail"
                )
            else:
                unknowns += 1
                reasons.append(
                    f"{exp.record_key}/{exp.rule_id}: delivery verdict unknown reported separately"
                )
            continue
        if actual != exp.expected_verdict:
            fails += 1
            reasons.append(
                f"{exp.record_key}/{exp.rule_id}: expected {exp.expected_verdict}, "
                f"delivery verdict {actual}"
            )
            continue
        for field in exp.expected_evidence_fields:
            if not _locates_field(evidence_ids, basis, anchors, field):
                fails += 1
                reasons.append(
                    f"{exp.record_key}/{exp.rule_id}: evidence_missing for field {field}"
                )
    # The criteria's evidence requirements must be resolvable **from the
    # delivery** (review B4, r35 F3): each one is located by a basis ref, a
    # dependency, or the assessment's target — possibly at another
    # revision of the same id. What the gold itself lists can never
    # substitute for what the delivery cites.
    for requirement in requirements:
        if not any(_extends(requirement, ref) for ref in delivery_refs):
            fails += 1
            reasons.append(
                f"evidence_missing: criteria requirement {requirement} is not resolvable "
                "from the delivery's basis, target or dependencies"
            )
    if fails:
        return Verdict.fail, reasons
    if unknowns:
        return Verdict.unknown, reasons
    return Verdict.pass_, reasons


def compare_compute(
    criteria: dict[str, Any],
    expected: list[ExpectedComputation],
    delivery: EvaluationDelivery,
) -> tuple[Verdict, list[str]]:
    tolerance_relative = float(criteria.get("tolerance_relative", 0.0) or 0.0)
    tolerance_absolute = float(criteria.get("tolerance_absolute", 0.0) or 0.0)
    reasons: list[str] = []
    if delivery.timed_out or delivery.budget_exhausted:
        return Verdict.fail, ["delivery timed out or exhausted its budget"]
    if delivery.computed_result is None:
        return Verdict.fail, ["compute case requires a ComputedResult delivery"]
    result = delivery.computed_result
    target_id = str(result.target_ref).split("@")[0]
    matched = False
    for exp in expected:
        if target_id != exp.metric_id and result.result_id != exp.metric_id:
            continue
        matched = True
        try:
            value = float(result.value)
        except (TypeError, ValueError):
            reasons.append(f"{exp.metric_id}: delivery value is not numeric")
            continue
        if not math.isfinite(value):
            # "NaN"/inf parse as floats but compare as always-inside-tolerance;
            # they are not numbers a criteria can accept (review B4).
            reasons.append(f"{exp.metric_id}: delivery value is not a finite number")
            continue
        window = tolerance_absolute + tolerance_relative * abs(exp.expected_value)
        if abs(value - exp.expected_value) > window:
            reasons.append(
                f"{exp.metric_id}: expected {exp.expected_value}, got {value} "
                f"(tolerance {window})"
            )
        if exp.unit is not None and result.unit != exp.unit:
            reasons.append(
                f"{exp.metric_id}: unit mismatch: expected {exp.unit!r}, got {result.unit!r}"
            )
        if result.grain != exp.grain:
            reasons.append(
                f"{exp.metric_id}: grain mismatch: expected {exp.grain!r}, got {result.grain!r}"
            )
        if sorted(map(str, exp.filters_applied)) != sorted(map(str, result.filters_applied)):
            reasons.append(
                f"{exp.metric_id}: filters mismatch: expected {exp.filters_applied}, "
                f"got {result.filters_applied}"
            )
    if not matched:
        reasons.append("no delivery matched the expected computations")
    # Every gold-required metric must be delivered (review B4): a delivery
    # that reports only a subset of the required outputs is not acceptable.
    delivered = {target_id, str(result.result_id)}
    for exp in expected:
        if exp.metric_id not in delivered:
            reasons.append(
                f"{exp.metric_id}: required metric is not delivered"
            )
    if reasons:
        return Verdict.fail, reasons
    return Verdict.pass_, reasons


class DeterministicEvaluators:
    """EvaluatorPort implementation dispatching on the criteria family."""

    def compare(
        self, criteria: dict[str, Any], case: dict[str, Any], delivery: dict[str, Any]
    ) -> Any:
        expected = delivery.get("expected")
        evaluation_delivery = EvaluationDelivery.model_validate(delivery["delivery"])
        if criteria["family"] == "judgment":
            gold = [ExpectedJudgment.model_validate(e) for e in expected]
            return compare_judgment(criteria, gold, evaluation_delivery)
        gold = [ExpectedComputation.model_validate(e) for e in expected]
        return compare_compute(criteria, gold, evaluation_delivery)


deterministic_evaluators = DeterministicEvaluators()
