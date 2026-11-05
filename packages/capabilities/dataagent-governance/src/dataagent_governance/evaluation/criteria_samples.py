"""DA11.5.1 criteria drafting, DA11.5.6 sample isolation, DA11.5.5 acceptance.

Also hosts the criteria confirmation entry (feasibility review §9): a
management function — deliberately *not* a Catalog operation — that only an
authorized confirmer can use to activate a draft, binding the criteria
content digest and revision and minting a new revision. Repair flows can
never rewrite an already-active revision.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from statistics import median
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from dataagent_contracts.core import (
    AcceptanceReport,
    CallContext,
    CaseResult,
    Cost,
    Coverage,
    CriteriaRef,
    EvaluationSetRef,
    HumanEffort,
    Latency,
    MetricBundle,
    QualityMetric,
    SplitRole,
    Stratum,
    UnknownRate,
    VersionedRef,
    validate_acceptance_report,
)
from dataagent_runtime import operation

from dataagent_governance.adapters.deterministic_evaluators import (
    compare_compute,
    compare_judgment,
)
from dataagent_governance.contracts import (
    AcceptanceCriteriaDraft,
    CriteriaConfirmation,
    CriteriaProposal,
    EvaluationCaseDraft,
    EvaluationDelivery,
    ExpectedComputation,
    ExpectedJudgment,
)
from dataagent_governance.runtime.errors import invalid_input, not_found, version_conflict

CRITERIA_KIND = "criteria"
CONFIRMATION_KIND = "criteria_confirmation"

LOCAL_VAULT_LIMIT = (
    "本地样本库是约定隔离，不是安全边界；金标只经 DA11.5.5 读取，其他读取记入暴露台账并降级"
)

# A revision of this shape names content by address; only such an anchor can
# be verified against the shared content store (r38 F5).
_DIGEST_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")
_MISSING = object()


def _json_pointer(document: Any, pointer: Any) -> Any:
    """Minimal RFC 6901 resolution; ``_MISSING`` when the pointer misses."""

    if not pointer:
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return _MISSING
    node = document
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                return _MISSING
            node = node[token]
        elif isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node):
                return _MISSING
            node = node[int(token)]
        else:
            return _MISSING
    return node


def anchor_resolution_error(rt, anchor) -> str | None:  # noqa: ANN001
    """Why one source anchor does not resolve, or ``None`` when it does.

    An anchor is evidence only when it actually locates its source value
    (r38 F5): the cited revision must be a content address the shared store
    holds, and the selector must resolve against that content. The
    governance layer resolves anchors through the shared content store
    alone — it never imports the data layer — so selector kinds only the
    data layer can resolve (``excel_cell`` and friends) are reported as
    unresolvable rather than waved through.
    """

    revision = str(getattr(anchor, "source_revision", "") or "")
    source_ref = str(getattr(anchor, "source_ref", "") or "")
    label = f"{source_ref}@{revision}"
    if not _DIGEST_REVISION.match(revision):
        return (
            f"source anchor {label}: source_revision is not a content address; "
            "the cited source version cannot be verified"
        )
    try:
        payload = rt.content.get(revision)
    except Exception:  # noqa: BLE001 - unreadable source is an unresolvable anchor
        return f"source anchor {label}: source content is not available"
    selector = getattr(anchor, "selector", None)
    kind = getattr(selector, "kind", None)
    if kind != "json_pointer":
        return (
            f"source anchor {label}: selector kind {kind!r} cannot be resolved "
            "by the acceptance evaluator (json_pointer only)"
        )
    try:
        document = json.loads(payload)
    except Exception:  # noqa: BLE001 - non-JSON source cannot answer a json pointer
        return f"source anchor {label}: source content is not JSON"
    pointer = getattr(selector, "pointer", None)
    if _json_pointer(document, pointer) is _MISSING:
        return (
            f"source anchor {label}: selector {pointer!r} does not locate a "
            "value in the source content"
        )
    return None


def assessment_anchor_errors(rt, assessment) -> list[str]:  # noqa: ANN001
    """All unresolvable source anchors an Assessment's evidence carries."""

    errors: list[str] = []
    for evidence in getattr(assessment, "evidence", None) or []:
        for anchor in getattr(evidence, "source_anchors", None) or []:
            error = anchor_resolution_error(rt, anchor)
            if error is not None:
                errors.append(error)
    return errors


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- DA11.5.1 draft_acceptance_criteria --------------------------------- #


class DraftAcceptanceCriteriaInput(BaseModel):
    delivery_target: str | None = None
    existing_criteria_id: str | None = None
    proposal: CriteriaProposal | None = None


class DraftAcceptanceCriteriaOutput(BaseModel):
    criteria: CriteriaRef
    draft_id: str


def _validate_proposal(proposal: CriteriaProposal) -> None:
    if proposal.family == "judgment":
        if "pass_rate" not in proposal.thresholds:
            raise invalid_input(
                "judgment criteria require a 'pass_rate' threshold",
                target="proposal.thresholds",
            )
    for name, value in proposal.thresholds.items():
        if name.endswith("_rate") and not 0.0 <= value <= 1.0:
            raise invalid_input(
                f"threshold {name} is a rate and must be within [0, 1]",
                target=f"proposal.thresholds.{name}",
            )
    if proposal.family == "compute":
        if proposal.tolerance_relative < 0 or proposal.tolerance_absolute < 0:
            raise invalid_input("tolerances must be non-negative")


@operation(
    "DA11.5.1",
    input_model=DraftAcceptanceCriteriaInput,
    output_model=DraftAcceptanceCriteriaOutput,
    description="业务验收判据定义（两段式）：先取判据上下文，再提交草案并校验",
    writes=True,
    idempotent=False,
)
def draft_acceptance_criteria(
    input_obj: DraftAcceptanceCriteriaInput, ctx: CallContext, rt
) -> DraftAcceptanceCriteriaOutput:
    if input_obj.proposal is None:
        # Phase 1: the tool offers the delivery target fields, the existing
        # criteria versions and a sample overview; the agent proposes next.
        raise _needs_criteria_input(rt, input_obj)
    _validate_proposal(input_obj.proposal)

    criteria_id = input_obj.existing_criteria_id or f"criteria:{uuid.uuid4().hex[:12]}"
    draft = AcceptanceCriteriaDraft(
        criteria_id=criteria_id,
        revision="r-pending",
        owner_ref=input_obj.proposal.owner_ref,
        delivery_target=input_obj.delivery_target or input_obj.proposal.expected_outputs,
        family=input_obj.proposal.family,
        expected_outputs=input_obj.proposal.expected_outputs,
        evidence_requirements=input_obj.proposal.evidence_requirements,
        unknown_policy=input_obj.proposal.unknown_policy,
        thresholds=input_obj.proposal.thresholds,
        tolerance_relative=input_obj.proposal.tolerance_relative,
        tolerance_absolute=input_obj.proposal.tolerance_absolute,
        strata=input_obj.proposal.strata,
        max_seconds=input_obj.proposal.max_seconds,
        max_cost=input_obj.proposal.max_cost,
        status="draft",
    )
    payload = draft.model_dump(mode="json")
    payload.pop("revision")
    revision = rt.versions.save(CRITERIA_KIND, criteria_id, payload)
    saved = AcceptanceCriteriaDraft.model_validate(
        {**rt.versions.get(CRITERIA_KIND, criteria_id, revision), "revision": revision}
    )
    return DraftAcceptanceCriteriaOutput(
        criteria=CriteriaRef(
            id=saved.criteria_id,
            revision=saved.revision,
            status=saved.status,
            owner_ref=saved.owner_ref,
            expected_outputs=saved.expected_outputs,
            evidence_requirements=saved.evidence_requirements,
            unknown_policy=saved.unknown_policy,
            thresholds=saved.thresholds,
        ),
        draft_id=saved.criteria_id,
    )


def _needs_criteria_input(rt, input_obj: DraftAcceptanceCriteriaInput):  # noqa: ANN001
    from dataagent_contracts.core import Issue
    from dataagent_runtime.errors import NeedsInputError

    current = rt.versions.current(CRITERIA_KIND, input_obj.existing_criteria_id or "")
    existing = []
    if input_obj.existing_criteria_id:
        existing = [
            f"{input_obj.existing_criteria_id}@{current[0]}" if current else None
        ]
        existing = [e for e in existing if e]
    set_current = rt.versions.current("eval_set", "")
    sample_overview = (
        {"sets": 0} if set_current is None else {"sets": 1, "counts": set_current[1].get("counts")}
    )
    return NeedsInputError(
        Issue(
            code="invalid_input",
            severity="warning",
            message="submit the acceptance criteria proposal to continue",
            retryable=False,
            suggested_action="call draft_acceptance_criteria again with 'proposal'",
            inference_request={
                "role": "acceptance_criteria_draft",
                "delivery_target_fields": [
                    "expected_outputs",
                    "evidence_requirements",
                    "unknown_policy",
                    "thresholds",
                    "tolerance_relative",
                    "tolerance_absolute",
                    "strata",
                ],
                "existing_criteria": existing,
                "sample_overview": sample_overview,
                "constraints": {
                    "family": ["judgment", "compute"],
                    "unknown_policy": ["count_as_fail", "report_separately"],
                    "note": "修复流程不能改写已 active 的判据；draft 转 active 需有权主体确认",
                },
            },
        )
    )


# --- confirmation entry (review §9) -------------------------------------- #


def confirm_acceptance_criteria(
    rt,
    criteria_id: str,
    criteria_revision: str,
    confirmation: CriteriaConfirmation,
    *,
    authorized_confirmers: set[str],
) -> CriteriaRef:
    """Activate a draft; management entry, not a Catalog operation.

    The confirmation must bind this criteria's content digest and revision and
    come from an authorized confirmer; activation writes a **new** revision
    and never rewrites an existing active one.
    """

    # Authorization first: an unauthorized caller must not even probe
    # whether a criteria revision exists.
    if confirmation.confirmer_ref not in authorized_confirmers:
        raise invalid_input(
            f"confirmer {confirmation.confirmer_ref} is not authorized to activate criteria",
            target="confirmation.confirmer_ref",
        )
    payload = rt.versions.get(CRITERIA_KIND, criteria_id, criteria_revision)
    if payload is None:
        raise not_found(f"criteria not found: {criteria_id}@{criteria_revision}")
    draft = AcceptanceCriteriaDraft.model_validate(
        {**payload, "revision": criteria_revision}
    )
    if draft.status == "active":
        raise version_conflict(
            f"criteria {criteria_id}@{criteria_revision} is already active; "
            "repairs must draft a new revision"
        )
    if confirmation.confirmation_id in _seen_confirmations(rt, criteria_id):
        raise version_conflict(f"confirmation {confirmation.confirmation_id} already used")
    if (
        confirmation.criteria_id != criteria_id
        or confirmation.criteria_revision != criteria_revision
    ):
        raise invalid_input(
            "confirmation targets a different criteria revision; refusing",
            target="confirmation",
        )
    if confirmation.criteria_digest != _digest(payload):
        raise invalid_input(
            "confirmation digest does not match the criteria content; refusing "
            "a stale or mis-targeted confirmation",
            target="confirmation.criteria_digest",
        )
    rt.versions.save(
        CONFIRMATION_KIND,
        confirmation.confirmation_id,
        confirmation.model_dump(mode="json"),
    )
    active = draft.model_copy(
        update={"status": "active", "confirmation_ref": confirmation.confirmation_id}
    )
    new_payload = active.model_dump(mode="json")
    new_payload.pop("revision")
    revision = rt.versions.save(
        CRITERIA_KIND, criteria_id, new_payload, expected_revision=criteria_revision
    )
    return CriteriaRef(
        id=criteria_id,
        revision=revision,
        status=active.status,
        owner_ref=active.owner_ref,
        expected_outputs=active.expected_outputs,
        evidence_requirements=active.evidence_requirements,
        unknown_policy=active.unknown_policy,
        thresholds=active.thresholds,
        confirmation_ref=active.confirmation_ref,
    )


def _seen_confirmations(rt, criteria_id: str) -> set[str]:
    seen: set[str] = set()
    current = rt.versions.current(CRITERIA_KIND, criteria_id)
    if current:
        payload = current[1]
        ref = payload.get("confirmation_ref")
        if ref:
            seen.add(ref)
    return seen


# --- DA11.5.6 isolate_acceptance_samples -------------------------------- #


class IsolateAcceptanceSamplesInput(BaseModel):
    cases: list[EvaluationCaseDraft] = Field(min_length=1)
    group_keys: list[str] = Field(min_length=1)
    role_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "development": 0.6,
            "regression": 0.2,
            "unseen_acceptance": 0.2,
        }
    )
    freeze: bool = False
    set_id: str | None = None

    @model_validator(mode="after")
    def _weights_complete(self) -> "IsolateAcceptanceSamplesInput":
        roles = {SplitRole.development, SplitRole.regression, SplitRole.unseen_acceptance}
        if set(self.role_weights) != {r.value for r in roles}:
            raise ValueError("role_weights must cover development/regression/unseen_acceptance")
        if any(w < 0 for w in self.role_weights.values()):
            raise ValueError("role weights must be non-negative")
        total = sum(self.role_weights.values())
        if total <= 0:
            raise ValueError("role weights must sum to a positive value")
        return self


class IsolateAcceptanceSamplesOutput(BaseModel):
    evaluation_set: EvaluationSetRef
    warnings: list[str]


def _group_key(case: EvaluationCaseDraft, group_keys: list[str]) -> str:
    return "|".join(f"{key}={case.group_keys.get(key, '')}" for key in sorted(group_keys))


@operation(
    "DA11.5.6",
    input_model=IsolateAcceptanceSamplesInput,
    output_model=IsolateAcceptanceSamplesOutput,
    description="验收样本隔离：按分组键整组划分、指纹去重、近重复告警、可冻结",
    writes=True,
)
def isolate_acceptance_samples(
    input_obj: IsolateAcceptanceSamplesInput, ctx: CallContext, rt
) -> IsolateAcceptanceSamplesOutput:
    warnings: list[str] = []
    # Content-fingerprint dedup: identical input content appears once.
    fingerprints: dict[str, str] = {}
    unique_cases: list[EvaluationCaseDraft] = []
    for case in input_obj.cases:
        digest = str(case.input_ref).split("@")[-1]
        if digest in fingerprints:
            warnings.append(
                f"near-duplicate fingerprint {digest} dropped for case {case.case_id} "
                f"(kept {fingerprints[digest]})"
            )
            continue
        fingerprints[digest] = case.case_id
        unique_cases.append(case)

    groups: dict[str, list[EvaluationCaseDraft]] = {}
    for case in unique_cases:
        groups.setdefault(_group_key(case, input_obj.group_keys), []).append(case)
    ordered = sorted(groups)

    # Deterministic whole-group assignment by stable hash ordering.
    assignments: dict[str, SplitRole] = {}
    weights = {
        role: input_obj.role_weights[role.value]
        for role in (
            SplitRole.development,
            SplitRole.regression,
            SplitRole.unseen_acceptance,
        )
    }
    total_weight = sum(weights.values()) or 1.0
    target_unseen = weights[SplitRole.unseen_acceptance] / total_weight
    target_regression = weights[SplitRole.regression] / total_weight
    group_hashes = sorted(
        ordered, key=lambda g: hashlib.sha256(g.encode("utf-8")).hexdigest()
    )
    n = len(group_hashes)
    unseen_budget = max(1, round(target_unseen * n)) if n else 0
    regression_budget = max(1 if n >= 3 else 0, round(target_regression * n))
    for index, group in enumerate(group_hashes):
        if index < unseen_budget:
            role = SplitRole.unseen_acceptance
        elif index < unseen_budget + regression_budget:
            role = SplitRole.regression
        else:
            role = SplitRole.development
        for case in groups[group]:
            assignments[case.case_id] = role

    # Same group keys must never straddle roles (whole-group assignment above
    # guarantees it); the near-duplicate cross-role warning covers the same
    # fingerprint that survived dedup via *different* group keys.
    seen_fingerprint_role: dict[str, SplitRole] = {}
    for case in unique_cases:
        digest = str(case.input_ref).split("@")[-1]
        role = assignments[case.case_id]
        if digest in seen_fingerprint_role and seen_fingerprint_role[digest] != role:
            warnings.append(
                f"case {case.case_id}: identical fingerprint appears in two roles "
                f"({seen_fingerprint_role[digest].value} and {role.value})"
            )
        seen_fingerprint_role.setdefault(digest, role)

    ref = rt.vault.create_set(unique_cases, assignments, warnings=warnings, set_id=input_obj.set_id)
    if input_obj.freeze:
        ref = rt.vault.freeze(str(ref.id), str(ref.revision))
    manifest = rt.vault.get_set(str(ref.id), str(ref.revision))
    return IsolateAcceptanceSamplesOutput(
        evaluation_set=EvaluationSetRef(
            id=str(ref.id),
            revision=str(ref.revision),
            frozen=bool(manifest.get("frozen")),
            split_manifest_ref=f"{ref.id}/manifest@{ref.revision}",
            counts={
                SplitRole(role): int(count)
                for role, count in manifest.get("counts", {}).items()
            },
            exposure_ledger_ref=f"{ref.id}/ledger",
        ),
        warnings=warnings,
    )


# --- DA11.5.5 evaluate_business_acceptance ------------------------------- #


class HostObservations(BaseModel):
    """Host-supplied observations for the metric classes the evaluator
    cannot measure itself (review B9).

    Everything left ``None`` is declared as a missing record in the report —
    never reported as a measured zero.
    """

    human_count: int | None = Field(default=None, ge=0)
    human_minutes: float | None = Field(default=None, ge=0)
    cost_amount: float | None = Field(default=None, ge=0)
    cost_currency: str | None = None
    latency_ms: list[float] | None = Field(default=None, min_length=1)


class EvaluateBusinessAcceptanceInput(BaseModel):
    criteria_ref: VersionedRef
    evaluation_set_ref: VersionedRef
    deliveries: list[EvaluationDelivery] = Field(min_length=1)
    dependency_versions: list[VersionedRef] = Field(default_factory=list)
    # Minimal host observations for the six metric classes (review B9):
    # whatever is not supplied is reported as missing, never as a measured 0.
    observations: HostObservations | None = None


class EvaluateBusinessAcceptanceOutput(BaseModel):
    report: AcceptanceReport


@operation(
    "DA11.5.5",
    input_model=EvaluateBusinessAcceptanceInput,
    output_model=EvaluateBusinessAcceptanceOutput,
    description="端到端业务验收：仅用未见验收样本，逐样本按冻结判据比较并产出报告",
)
def evaluate_business_acceptance(
    input_obj: EvaluateBusinessAcceptanceInput, ctx: CallContext, rt
) -> EvaluateBusinessAcceptanceOutput:
    criteria_payload = rt.versions.get(
        CRITERIA_KIND, str(input_obj.criteria_ref.id), str(input_obj.criteria_ref.revision)
    )
    if criteria_payload is None:
        raise not_found(f"criteria not found: {input_obj.criteria_ref}")
    criteria = AcceptanceCriteriaDraft.model_validate(
        {**criteria_payload, "revision": str(input_obj.criteria_ref.revision)}
    )
    criteria_ref = CriteriaRef(
        id=criteria.criteria_id,
        revision=criteria.revision,
        status=criteria.status,
        owner_ref=criteria.owner_ref,
        expected_outputs=criteria.expected_outputs,
        evidence_requirements=criteria.evidence_requirements,
        unknown_policy=criteria.unknown_policy,
        thresholds=criteria.thresholds,
        confirmation_ref=criteria.confirmation_ref,
    )
    set_id = str(input_obj.evaluation_set_ref.id)
    set_revision = str(input_obj.evaluation_set_ref.revision)
    manifest = rt.vault.get_set(set_id, set_revision)
    evaluation_set = EvaluationSetRef(
        id=set_id,
        revision=set_revision,
        frozen=bool(manifest.get("frozen")),
        split_manifest_ref=f"{set_id}/manifest@{set_revision}",
        counts={
            SplitRole(role): int(count)
            for role, count in manifest.get("counts", {}).items()
        },
        exposure_ledger_ref=f"{set_id}/ledger",
    )

    unseen_cases = rt.vault.list_cases(set_id, set_revision, SplitRole.unseen_acceptance)
    # Run-time eligibility snapshot (08 §5.2, review §10): the frozen
    # manifest is immutable, but a case whose gold was exposed after the
    # freeze is demoted to ``regression`` in the current revision. Such a
    # case must not be accepted as unseen through the old frozen revision
    # either. Eligibility is decided on the **gold digests of the cited
    # frozen manifest** against the irreversible, content-addressed
    # exposure index (r35 F2): replacing the latest case list, or rebinding
    # a case id to fresh gold, never restores an exposed gold to unseen —
    # the demotion follows the digest, not the current case-id binding.
    current_roles = rt.vault.current_roles(set_id)
    demoted = {
        case_id
        for case_id, role in current_roles.items()
        if role != SplitRole.unseen_acceptance.value
    }
    exposed_digests = rt.vault.exposed_digests()

    def _gold_digest(case: dict) -> str:  # noqa: ANN001
        return str(case["expected_ref"]).split("@")[-1]

    eligible_unseen = [
        case
        for case in unseen_cases
        if case["case_id"] not in demoted
        and _gold_digest(case) not in exposed_digests
    ]
    deliveries_by_case = {d.case_id: d for d in input_obj.deliveries}

    case_results: list[CaseResult] = []
    stratum_pass: dict[str, list[int]] = {}
    unknown_count = 0
    for case in eligible_unseen:
        case_id = case["case_id"]
        gold = rt.vault.read_gold(
            set_id,
            set_revision,
            case_id,
            purpose="evaluate_business_acceptance",
            accessed_by="DA11.5.5",
        )
        delivery = deliveries_by_case.get(case_id)
        if delivery is None:
            case_results.append(
                CaseResult(
                    case_id=case_id,
                    verdict="fail",
                    notes="delivery missing; counted in the denominator",
                )
            )
            _stratum_count(stratum_pass, case, criteria.strata, False)
            continue
        if delivery.assessment is not None and getattr(
            delivery.assessment.verdict, "value", delivery.assessment.verdict
        ) == "unknown":
            unknown_count += 1
        # r38 F5: an anchor that does not resolve against the cited source
        # content is not evidence — the case fails before any comparison.
        anchor_errors = (
            assessment_anchor_errors(rt, delivery.assessment)
            if delivery.assessment is not None
            else []
        )
        if anchor_errors:
            case_results.append(
                CaseResult(
                    case_id=case_id,
                    verdict="fail",
                    notes="; ".join(
                        ["evidence_missing — " + error for error in anchor_errors]
                    ),
                )
            )
            _stratum_count(stratum_pass, case, criteria.strata, False)
            continue
        criteria_dict = criteria.model_dump(mode="json")
        if criteria.family == "judgment":
            expectations = [ExpectedJudgment.model_validate(g) for g in gold]
            verdict, reasons = compare_judgment(criteria_dict, expectations, delivery)
        else:
            expectations = [ExpectedComputation.model_validate(g) for g in gold]
            verdict, reasons = compare_compute(criteria_dict, expectations, delivery)
        passed = verdict == "pass"
        _stratum_count(stratum_pass, case, criteria.strata, passed)
        case_results.append(
            CaseResult(
                case_id=case_id,
                verdict=verdict,
                notes="; ".join(reasons) if reasons else None,
            )
        )

    total = len(case_results)
    passed = sum(1 for c in case_results if c.verdict == "pass")
    pass_rate = passed / total if total else 0.0
    threshold = float(criteria.thresholds.get("pass_rate", 1.0))
    overall = "pass" if total and pass_rate >= threshold else "fail"

    strata = [
        Stratum(key=key, metrics={"pass_rate": values[0] / values[1]})
        for key, values in sorted(stratum_pass.items())
    ]

    # Six metric classes (08 §5.3): quality/coverage/unknown come from this
    # run; human/cost/latency need host observations. Whatever is not
    # observed is declared in ``missing_records`` and the limits — a missing
    # observation is never written up as a measured zero (review B9).
    observations = input_obj.observations
    missing_records: list[str] = []
    limits = [LOCAL_VAULT_LIMIT]
    if observations is None or observations.human_count is None:
        human = HumanEffort(count=0, minutes=None)
        missing_records.append(
            "human_effort: no host observation supplied; count 0 and minutes null "
            "mean 'not observed', not 'measured zero'"
        )
    else:
        human = HumanEffort(
            count=observations.human_count,
            minutes=observations.human_minutes,
        )
        if observations.human_minutes is None:
            missing_records.append("human_effort.minutes: no host observation supplied")
    if observations is not None and observations.cost_amount is not None:
        cost = Cost(
            amount=observations.cost_amount,
            currency=observations.cost_currency or "CNY",
        )
    else:
        cost = None
        missing_records.append("cost: no host observation supplied; reported as null")
    if observations is not None and observations.latency_ms:
        samples = sorted(observations.latency_ms)
        p50 = samples[len(samples) // 2]
        p95 = samples[min(len(samples) - 1, math.ceil(0.95 * len(samples)) - 1)]
        latency = Latency(p50=float(p50), p95=float(p95))
    else:
        latency = Latency(p50=0.0, p95=0.0)
        missing_records.append(
            "latency_ms: no host observation supplied; p50/p95 0.0 mean "
            "'not observed', not 'measured zero'"
        )
    if missing_records:
        limits.append(
            "六类指标中 quality/coverage/unknown 为本次实测；human/cost/latency 未提供宿主观测，"
            "见 missing_records，缺测不写成实测零"
        )
    if not eligible_unseen:
        # Every unseen case of the cited revision was demoted (gold exposure
        # history is irreversible, B3): a valid fail conclusion with no
        # inline cases, pointing at where the demotions are recorded.
        limits.append(
            "没有可用的未见验收样本（金标暴露历史不可逆，详见暴露台账）"
        )

    report = AcceptanceReport(
        id=f"report:{uuid.uuid4().hex[:12]}",
        criteria_ref=VersionedRef(id=criteria.criteria_id, revision=criteria.revision),
        evaluation_set_ref=VersionedRef(id=set_id, revision=set_revision),
        target_ref=VersionedRef(id=criteria.criteria_id, revision=criteria.revision),
        dependency_versions=input_obj.dependency_versions,
        overall=overall,
        cases=case_results,
        cases_ref=None if case_results else f"{set_id}@{set_revision}#excluded-by-exposure",
        metrics=MetricBundle(
            quality=[
                QualityMetric(name="pass_rate", value=pass_rate, numerator=passed, denominator=total)
            ],
            coverage=Coverage(covered=len(case_results), total=len(eligible_unseen)),
            unknown=UnknownRate(count=unknown_count, rate=unknown_count / total if total else 0.0),
            human=human,
            cost=cost,
            latency_ms=latency,
            strata=strata,
            missing_records=missing_records,
        ),
        coverage_scope=(
            f"unseen_acceptance samples of {set_id}@{set_revision} "
            f"({len(eligible_unseen)} cases)"
        ),
        limits=limits,
        run_ref=f"run:{uuid.uuid4().hex[:12]}",
    )
    validate_acceptance_report(report, criteria=criteria_ref, evaluation_set=evaluation_set)
    return EvaluateBusinessAcceptanceOutput(report=report)


def _stratum_count(
    store: dict[str, list[int]], case: dict[str, Any], strata: list[str], passed: bool
) -> None:
    for key in strata:
        value = case.get("group_keys", {}).get(key)
        if value is None:
            continue
        cell = store.setdefault(f"{key}={value}", [0, 0])
        cell[1] += 1
        if passed:
            cell[0] += 1


__all__ = [
    "draft_acceptance_criteria",
    "isolate_acceptance_samples",
    "evaluate_business_acceptance",
    "confirm_acceptance_criteria",
    "HostObservations",
    "anchor_resolution_error",
    "assessment_anchor_errors",
]
