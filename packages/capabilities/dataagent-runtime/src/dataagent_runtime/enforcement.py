"""DA12.1 enforcement hooks shared by every layer (08 §4.3).

Two hooks:

- **Access recheck** — before ``invoke`` reads input resources, resolve
  ``authorization_ref`` to an ``AccessDecision`` and require: ``allow``, not
  expired, ``resource_ref`` covers every input resource, purpose consistent.
  Otherwise ``failed`` with code ``da12.access_denied``.
- **Egress check** — before an ``InferencePort`` generates an
  ``inference_request``, require an ``EgressDecision`` covering all of its
  content. ``allow`` passes content through; ``allow_masked`` attaches only
  the masked artifact; ``deny`` or missing strips content and returns
  ``needs_input`` with code ``da12.egress_required``.

Kernel path: when ``kernel_session_id`` is present *and* the trusted host
declared the kernel guard effective, the access recheck only verifies that a
decision exists; the guard conclusion is authoritative. Without the
declaration the call is treated as a no-kernel path and fully rechecked
(08 §11, feasibility review §7.3).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from dataagent_contracts.core import (
    AccessDecision,
    CallContext,
    EgressDecision,
    Issue,
    ModelDestination,
    Severity,
    VersionedRef,
)

from dataagent_runtime.adapters.local_content import canonical_bytes, digest_bytes
from dataagent_runtime.errors import NeedsInputError
from dataagent_runtime.policy.context import is_legacy_context

EnforcementMode = Literal["off", "warn", "enforce"]

ACCESS_DENIED_CODE = "da12.access_denied"
EGRESS_REQUIRED_CODE = "da12.egress_required"

# W0 seam spec §5: the content keys of an inference_request are the only
# model-visible content channel; structure keys are never stripped. Every
# stdout channel (MCP, CLI summary, CLI ``--detail full``) strips these keys
# under ``enforce`` when a request cites no usable EgressDecision.
EGRESS_CONTENT_KEYS = (
    "statement",
    "conditions",
    "exceptions",
    "fields",
    "table",
    "metrics",
    "samples",
    "metric_statements",
    "metric_filters",
    "metric_ids",
    "metric_additivity",
    "metric_units",
    "requirement",
    "blocking_ambiguities",
)


@dataclass(frozen=True)
class EnforcementConfig:
    mode: EnforcementMode = "warn"
    # Trusted-host declaration that the kernel guard is wired and effective.
    # Mere presence of ``kernel_session_id`` never suffices (review §7.3).
    # Only the legacy rollback path may use it to skip the per-decision
    # checks; v1 has no call-bound proof and rechecks in full (codex r8).
    kernel_guard_declared: bool = False


def enforcement_from_env(enforcement: EnforcementConfig | None = None) -> EnforcementConfig:
    """Trusted-host wiring for the process entries (MCP/CLI).

    ``DATAAGENT_ENFORCEMENT_MODE`` is the only env switch (08 §4.3: off/warn/
    enforce, development default warn, S0 acceptance runs enforce). Mint hosts
    inject it through the ``.mcp.json`` server descriptor ``env`` map — the
    kernel clears the subprocess environment, so nothing else reaches the
    server. Unset or unrecognized values keep the development default.
    """

    if enforcement is not None:
        return enforcement
    mode = os.environ.get("DATAAGENT_ENFORCEMENT_MODE", "").strip().lower()
    if mode in {"off", "warn", "enforce"}:
        return EnforcementConfig(mode=mode)
    return EnforcementConfig()


@dataclass
class RecheckOutcome:
    ok: bool
    issue: Issue | None = None
    kernel_path: bool = False
    reasons: list[str] = field(default_factory=list)


def now() -> datetime:
    return datetime.now(timezone.utc)


def _ref_covers(decision_ref: VersionedRef, input_ref: VersionedRef) -> bool:
    """Coverage: exact identity, or an asset-tree prefix at a boundary.

    A decision for ``table:orders`` covers ``table:orders/2024-01``; a decision
    for ``content:<hex>`` covers exactly that content revision. Revisions must
    agree unless the decision names a whole asset subtree (``*`` revision).
    """

    if decision_ref.id == input_ref.id:
        return decision_ref.revision in {input_ref.revision, "*"}
    if input_ref.id.startswith(decision_ref.id) and input_ref.id[len(decision_ref.id)] in {
        "/",
        ":",
    }:
        return decision_ref.revision in {input_ref.revision, "*"}
    return False


def _deny(reasons: list[str], *, kernel_path: bool = False) -> RecheckOutcome:
    issue = Issue(
        code=ACCESS_DENIED_CODE,
        severity=Severity.error,
        message="access recheck failed: " + "; ".join(reasons),
        retryable=False,
        suggested_action="obtain an AccessDecision covering the input resources, "
        "then retry with its decision_id as authorization_ref",
    )
    return RecheckOutcome(ok=False, issue=issue, kernel_path=kernel_path, reasons=reasons)


def access_recheck(
    ctx: CallContext,
    resolver: Callable[[str], AccessDecision | None],
    resource_refs: list[VersionedRef],
    *,
    config: EnforcementConfig = EnforcementConfig(),
    at: datetime | None = None,
    legacy: bool | None = None,
) -> RecheckOutcome:
    """Recheck ``authorization_ref`` against the resources this call reads.

    ``legacy=True`` restores the old behavior for the one-release rollback:
    the ``None``-subject skip and the kernel-guard shortcut. ``invoke``
    passes it from the resolved source.

    The kernel-guard shortcut is rollback-only. It trusts
    ``kernel_guard_declared`` and verifies only that the decision exists,
    which lets a caller-supplied ``authorization_ref`` bypass a deny, an
    expired decision, a subject mismatch and resource coverage. v1 therefore
    rechecks the decision outcome, subject and resources even when a host
    ``session_id`` is present (codex r8).
    """

    if legacy is None:
        legacy = is_legacy_context()
    if config.mode == "off":
        return RecheckOutcome(ok=True)
    decision = resolver(ctx.authorization_ref)
    if decision is None:
        return _deny(
            [f"authorization_ref {ctx.authorization_ref!r} does not resolve to an AccessDecision"]
        )
    kernel_path = (
        bool(ctx.kernel_session_id) and config.kernel_guard_declared and bool(legacy)
    )
    if kernel_path:
        # Old behavior, rollback only: the declared guard is authoritative and
        # existence of the decision is all that is verified.
        return RecheckOutcome(ok=True, kernel_path=True)

    reasons: list[str] = []
    if decision.decision != "allow":
        reasons.append(f"decision {decision.decision_id} outcome is {decision.decision}")
    moment = at or now()
    if decision.valid_until is not None and moment > decision.valid_until:
        reasons.append(f"decision {decision.decision_id} expired at {decision.valid_until}")
    if ctx.purpose is None:
        reasons.append("CallContext.purpose is missing; the trusted host must fix the purpose")
    elif ctx.purpose != decision.purpose:
        reasons.append(
            f"purpose mismatch: call purpose {ctx.purpose!r} != decision purpose "
            f"{decision.purpose!r}"
        )
    if ctx.subject_ref is None:
        # r41 X1: a missing subject used to skip the comparison entirely
        # (fail-open). The resolved context always carries a subject (host,
        # environment or local-owner); an empty one means a caller bypassed
        # resolution, so fail closed. The legacy switch restores the old
        # ``None`` skip for the one-release rollback.
        if not legacy:
            reasons.append(
                "CallContext.subject_ref is missing; the trusted host must fix the subject"
            )
    elif not str(ctx.subject_ref).strip():
        if legacy:
            # Old code only skipped ``None``; an empty string was compared and
            # rejected as a mismatch.
            if decision.subject_ref != ctx.subject_ref:
                reasons.append(
                    f"subject mismatch: executing subject {ctx.subject_ref!r} != "
                    f"decision subject {decision.subject_ref!r}"
                )
        else:
            reasons.append(
                "CallContext.subject_ref is missing; the trusted host must fix the subject"
            )
    elif ctx.subject_ref != decision.subject_ref:
        reasons.append(
            f"subject mismatch: executing subject {ctx.subject_ref!r} != decision subject "
            f"{decision.subject_ref!r}"
        )
    for ref in resource_refs:
        if not _ref_covers(decision.resource_ref, ref):
            reasons.append(
                f"decision {decision.decision_id} resource {decision.resource_ref} does not "
                f"cover input resource {ref}"
            )
    if reasons:
        return _deny(reasons)
    return RecheckOutcome(ok=True)


@dataclass
class EgressOutcome:
    allowed: bool
    request: dict[str, Any]
    issue: Issue | None = None
    masked: bool = False
    reasons: list[str] = field(default_factory=list)


# Keys the gate strips from a request whose egress failed; ``content`` is the
# generic InferencePort payload key (r38 F1 also binds it, below).
_CONTENT_KEY = "content"

# A covered ref of this shape names content by address; the revision *is*
# the digest of the bytes the decision approved.
_DIGEST_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")


def _inline_content_digest(value: Any) -> str | None:
    """Canonical digest of the inline content (same canonicalization as the
    shared content store), or ``None`` if it cannot be serialized."""

    try:
        return digest_bytes(canonical_bytes(value))
    except (TypeError, ValueError):
        return None


def _covered_addresses(decision: EgressDecision) -> set[str]:
    """Content addresses the decision covers, by revision.

    A ref whose revision is ``sha256:<hex>`` names content *by address*: the
    revision is the digest of the bytes the decision approved. The id part
    is presentation — the same bytes stored (and approved) as
    ``table:orders@sha256:<d>`` and re-cited as ``content:<x>@sha256:<d>``
    are the same content, so coverage follows the address.
    """

    return {
        str(r).split("@", 1)[-1]
        for r in decision.content_refs
        if _DIGEST_REVISION.match(str(r).split("@", 1)[-1])
    }


def _ref_is_covered(ref: str, covered: set[str], covered_addresses: set[str]) -> bool:
    """Is ``ref`` covered — exactly, or by its content address?"""

    if ref in covered:
        return True
    revision = ref.split("@", 1)[-1]
    return _DIGEST_REVISION.match(revision) is not None and revision in covered_addresses


def _fail_of(request: dict[str, Any], reasons: list[str]) -> EgressOutcome:
    stripped = {k: v for k, v in request.items() if k != _CONTENT_KEY}
    issue = Issue(
        code=EGRESS_REQUIRED_CODE,
        severity=Severity.error,
        message="egress check failed: " + "; ".join(reasons),
        retryable=False,
        suggested_action="obtain an EgressDecision covering the content, then retry",
    )
    return EgressOutcome(allowed=False, request=stripped, issue=issue, reasons=reasons)


def egress_check(
    request: dict[str, Any],
    *,
    get_egress: Callable[[str], EgressDecision | None],
    load_masked: Callable[[str], Any] | None = None,
    config: EnforcementConfig = EnforcementConfig(),
) -> EgressOutcome:
    """Gate an ``inference_request`` on an EgressDecision (08 §4.3).

    The request carries ``content_refs`` (list of ``<id>@<revision>``),
    ``destination`` (``model_ref``/``deployment``) and the reference of the
    EgressDecision it relies on. ``allow`` passes the request through;
    ``allow_masked`` replaces the content with the masked artifact;
    ``deny``/missing/mismatch strips the content.

    r38 F1: an ``allow`` decision must bind the *actual* content, not just
    the reference strings. The inline ``content`` payload is canonically
    digested and must equal the revision — the content address — of a ref
    the decision covers; any inline rewrite, or fresh content smuggled
    next to clean refs, fails closed with the content stripped. Refs whose
    revision is not a content address cannot be verified and never satisfy
    the binding.

    r40 F1: the same address binding applies to ``content_refs`` themselves.
    A ref is covered when the decision covers it exactly *or* when its
    revision is the content address of bytes the decision covers — the id
    part of such a ref is presentation, the bytes are what was approved.
    Refs with label revisions (``r1``) still need exact-string coverage.
    """

    if config.mode == "off":
        return EgressOutcome(allowed=True, request=request)

    content_refs = list(request.get("content_refs") or [])
    carries_content = request.get("content") is not None
    if not content_refs:
        if carries_content:
            # Content that cites no content_refs cannot be verified against
            # any EgressDecision; letting it through would bypass the gate.
            return _fail_of(
                request,
                ["inference_request carries content without content_refs; the "
                 "content cannot be checked against an EgressDecision"],
            )
        return EgressOutcome(allowed=True, request=request)

    def _fail(reasons: list[str]) -> EgressOutcome:
        return _fail_of(request, reasons)

    destination = request.get("destination") or {}
    target = destination.get("model_ref") or request.get("model_ref")
    deployment = destination.get("deployment")
    if not target or not deployment:
        return _fail(
            ["inference_request destination is required: model_ref and deployment "
             "must name the model the content is sent to"]
        )

    ref = request.get("egress_decision_ref")
    if not isinstance(ref, str) or not ref:
        return _fail(["inference_request carries content without an egress_decision_ref"])
    decision = get_egress(ref)
    if decision is None:
        return _fail([f"egress decision {ref!r} does not resolve"])
    covered = {str(r) for r in decision.content_refs}
    covered_addresses = _covered_addresses(decision)
    missing = [
        str(r)
        for r in content_refs
        if not _ref_is_covered(str(r), covered, covered_addresses)
    ]
    if missing:
        return _fail([f"egress decision does not cover content: {', '.join(missing)}"])

    if target != decision.destination.model_ref:
        return _fail(
            [f"destination mismatch: request targets {target!r}, decision covers "
             f"{decision.destination.model_ref!r}"]
        )
    if deployment != decision.destination.deployment:
        return _fail(
            [f"deployment mismatch: request targets {deployment!r}, decision covers "
             f"{decision.destination.deployment!r}"]
        )

    if decision.decision == "allow":
        if carries_content:
            actual = _inline_content_digest(request.get("content"))
            if actual is None or actual not in covered_addresses:
                return _fail(
                    ["inference_request carries inline content that does not bind "
                     "to any content address the egress decision covers; the "
                     "decision approved referenced content, not this payload"]
                )
        return EgressOutcome(allowed=True, request=request)
    if decision.decision == "allow_masked":
        if not decision.masking_ref or load_masked is None:
            return _fail(["masked egress requires a resolvable masking artifact"])
        masked_content = load_masked(decision.masking_ref)
        rewritten = dict(request)
        rewritten["content"] = masked_content
        rewritten["masked"] = True
        return EgressOutcome(allowed=True, request=rewritten, masked=True)
    return _fail([f"egress decision {decision.decision_id} is {decision.decision}"])


def guarded_inference(
    inner: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    get_egress: Callable[[str], EgressDecision | None],
    load_masked: Callable[[str], Any] | None = None,
    config: EnforcementConfig = EnforcementConfig(),
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Wrap an ``InferencePort`` with the egress check.

    A denied, unresolvable or unbound decision never reaches the model:
    ``inner`` is not called, the content is stripped from the request and
    the caller receives a needs-input marker carrying the egress issue —
    a request for the missing input (the decision), not an execution
    failure and never a model reply over unapproved content (r38 F1).
    """

    def infer(request: dict[str, Any]) -> dict[str, Any]:
        outcome = egress_check(
            request,
            get_egress=get_egress,
            load_masked=load_masked,
            config=config,
        )
        if not outcome.allowed:
            return {
                "needs_input": True,
                "egress_issue": (
                    outcome.issue.model_dump(mode="json") if outcome.issue else None
                ),
                **outcome.request,
            }
        return inner(outcome.request)

    return infer


class _EgressDenied(NeedsInputError):
    """Legacy carrier for a denied egress (r38 F1: ``guarded_inference``
    now fails closed by returning a needs-input marker instead of raising;
    the class stays importable for older compositions that catch it)."""

    def __init__(self, issue: Issue | None):
        if issue is None:
            issue = Issue(
                code=EGRESS_REQUIRED_CODE,
                severity=Severity.error,
                message="egress check failed",
                retryable=False,
            )
        super().__init__(issue)


__all__ = [
    "EnforcementConfig",
    "EnforcementMode",
    "RecheckOutcome",
    "EgressOutcome",
    "access_recheck",
    "egress_check",
    "enforcement_from_env",
    "guarded_inference",
    "ACCESS_DENIED_CODE",
    "EGRESS_REQUIRED_CODE",
]
