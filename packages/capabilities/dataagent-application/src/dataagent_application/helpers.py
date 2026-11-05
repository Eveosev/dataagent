"""Small shared helpers for application-layer operations (mirrors 06 helpers)."""

from __future__ import annotations

from typing import Any

from dataagent_contracts.core import (
    AssetRef,
    CallContext,
    Completeness,
    CompletenessExtent,
    Issue,
    Severity,
    VersionedRef,
)
from dataagent_runtime.enforcement import EGRESS_REQUIRED_CODE, egress_check


def complete(declared_scope: str, observed: dict[str, int] | None = None) -> Completeness:
    return Completeness(
        extent=CompletenessExtent.complete_in_declared_scope,
        declared_scope=declared_scope,
        observed=observed,
        snapshot_consistent=True,
    )


def truncated(
    declared_scope: str,
    *,
    reason: str,
    observed: dict[str, int] | None = None,
) -> Completeness:
    return Completeness(
        extent=CompletenessExtent.truncated,
        declared_scope=declared_scope,
        observed=observed,
        reason=reason,
    )


def asset_for(
    digest: str,
    kind: str,
    scope_ref: str,
    *,
    media_type: str | None = None,
    identifier: str | None = None,
) -> AssetRef:
    return AssetRef(
        id=identifier or f"{kind}:{digest.split(':', 1)[1][:16]}",
        kind=kind,
        scope_ref=scope_ref,
        revision=digest,
        resolver="content",
        locator=digest,
        digest=digest,
        media_type=media_type,
    )


def load_table(runtime: Any, table_ref: Any):
    """Decode a stored table through the shared runtime codec (never the data layer)."""

    from dataagent_runtime.ports.tabular import decode_table

    return decode_table(runtime.content, table_ref)


def store_table(runtime: Any, columns: list[dict[str, Any]], rows: list[list[Any]]) -> tuple[VersionedRef, str]:
    """Store a computed table as a version-1 payload; return (VersionedRef, digest)."""

    payload = {
        "columns": columns,
        "rows": rows,
        "row_meta": [{"role": "detail", "reason": "computed result row"} for _ in rows],
    }
    digest = runtime.content.put(payload)
    table_id = f"computed:{digest.split(':', 1)[1][:16]}"
    revision = runtime.versions.save("computed_table", table_id, {"data_ref": digest, "row_count": len(rows)})
    return VersionedRef(id=table_id, revision=revision), digest


def load_computed_table(runtime: Any, table_ref: VersionedRef):
    from dataagent_runtime.ports.tabular import decode_table_payload

    payload = runtime.versions.get("computed_table", table_ref.id, table_ref.revision)
    if payload is None:
        raise ValueError(f"computed table not found: {table_ref}")
    return decode_table_payload(runtime.content.get_json(payload["data_ref"]))


def requirement_id_of(statement: str) -> str:
    """Stable requirement id from the statement text (content-derived, not random)."""

    import hashlib

    return "req:" + hashlib.sha256(statement.encode("utf-8")).hexdigest()[:16]


def context_scope(ctx: CallContext) -> str:
    return ctx.scope_ref


# --- Egress gate (07 §4.1 / §11.3) -------------------------------------------

# Keys of an inference_request that carry model-visible raw content. On a
# denied egress decision these are stripped; the structural keys (kind,
# closed_operators, ast_shape, constraints, instruction, ...) stay so the
# agent can still see what to produce — just not the confidential content.
# r40 F1: every caller free-text key the model can see is in this list —
# the caller's statement, metric statements/filters and requirement travel
# under these keys and are content-addressed by the operations that cite
# them (see expressions/requirements ``_caller_content_ref``).
#
# The tuple itself is the shared runtime's (the egress gate and every
# stdout channel — MCP, CLI summary, CLI ``--detail full`` — strip the
# same keys); re-exported here for the application layer's callers.
from dataagent_runtime.enforcement import EGRESS_CONTENT_KEYS  # noqa: E402


def caller_content_ref(value: Any) -> VersionedRef:
    """Content-addressed ref of caller-supplied model-visible content.

    r40 F1: caller free text projected into an inference_request (a SQL
    statement, metric statements/filters, a requirement) is bound to the
    EgressDecision the same way the rule content is: the operation cites the
    content *by address*, and the shared gate only passes it when the
    decision covers those bytes (the id is presentation; the revision —
    the canonical digest of the value — is what must be covered).
    """

    from dataagent_runtime.adapters.local_content import canonical_bytes, digest_bytes

    digest = digest_bytes(canonical_bytes(value))
    return VersionedRef(id="content:" + digest[len("sha256:") :][:16], revision=digest)


def versioned_ref_str(ref: VersionedRef | dict[str, Any]) -> str:
    """``<id>@<revision>`` wire form used by EgressDecision.content_refs."""

    if isinstance(ref, VersionedRef):
        return f"{ref.id}@{ref.revision}"
    return f"{ref['id']}@{ref['revision']}"


def gate_inference_request(
    runtime: Any,
    request: dict[str, Any],
    decision_ref: str | None,
    *,
    content_refs: list[VersionedRef] | None = None,
    check=egress_check,
    destination: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[Issue], bool]:
    """Gate model-visible content on an ``EgressDecision`` (07 §4.1).

    ``check`` is the shared runtime's egress hook
    (``dataagent_runtime.enforcement.egress_check``); callers pass it
    explicitly so the wiring is visible at the operation.

    The returned request always carries ``egress_decision_ref`` (``None``
    when the caller supplied none). Without a decision reference the gate
    follows the shared runtime's enforcement mode (review B2): ``warn``
    (the development default) lets the content pass with a
    ``da12.egress_required`` warning; ``enforce`` strips the content keys —
    the model context never sees raw content that no EgressDecision covers;
    ``off`` disables the gate. When a decision reference *is* supplied, the
    hook enforces it: ``deny`` / unresolvable / not covering the content
    strips the content keys and the caller must return ``needs_input``
    without the raw content. An ``allow`` decision passes only when the
    request's destination matches the decision's: the caller may declare
    ``destination`` explicitly; without one, the decision's own destination
    is the target (the decision names the one model the content may travel
    to), so ``allow`` is usable while a caller-declared mismatch still fails
    closed.

    Returns ``(request, issues, allowed)``.
    """

    request = dict(request)
    request["egress_decision_ref"] = decision_ref
    if decision_ref is None:
        mode = getattr(getattr(runtime, "enforcement", None), "mode", "warn")
        if mode == "off":
            return request, [], True
        if mode == "enforce":
            # Content without a covering EgressDecision never reaches the
            # model under enforce (B2): strip it, ask for the decision.
            stripped = {k: v for k, v in request.items() if k not in EGRESS_CONTENT_KEYS}
            stripped["egress_decision_ref"] = decision_ref
            return (
                stripped,
                [
                    Issue(
                        code=EGRESS_REQUIRED_CODE,
                        severity=Severity.error,
                        message=(
                            "enforce mode: inference content is not sent to the model "
                            "without an EgressDecision covering it"
                        ),
                        retryable=False,
                        suggested_action="obtain an EgressDecision covering the content and replay with egress_decision_ref",
                    )
                ],
                False,
            )
        return (
            request,
            [
                Issue(
                    code=EGRESS_REQUIRED_CODE,
                    severity=Severity.warning,
                    message=(
                        "inference content is sent to the model without an EgressDecision "
                        "(S0 warn mode); supply egress_decision_ref to enforce the gate"
                    ),
                    retryable=False,
                    suggested_action="obtain an EgressDecision covering the content and replay with egress_decision_ref",
                )
            ],
            True,
        )

    store = getattr(runtime, "decisions", None)
    get_egress = getattr(store, "get_egress", None)
    if get_egress is None:
        stripped = {k: v for k, v in request.items() if k not in EGRESS_CONTENT_KEYS}
        return (
            stripped,
            [
                Issue(
                    code=EGRESS_REQUIRED_CODE,
                    severity=Severity.error,
                    message="egress_decision_ref was supplied but this runtime has no EgressDecision store",
                    retryable=False,
                    suggested_action="run with a runtime wired with a decision store",
                )
            ],
            False,
        )

    decision = get_egress(decision_ref)
    if decision is None:
        # Distinguish an unresolvable decision from a destination problem
        # (review B3): every other failure mode keeps the content stripped.
        stripped = {k: v for k, v in request.items() if k not in EGRESS_CONTENT_KEYS}
        stripped["egress_decision_ref"] = decision_ref
        return (
            stripped,
            [
                Issue(
                    code=EGRESS_REQUIRED_CODE,
                    severity=Severity.error,
                    message=f"egress decision {decision_ref!r} does not resolve",
                    retryable=False,
                    suggested_action="obtain an EgressDecision covering the content, then retry",
                )
            ],
            False,
        )

    gated = dict(request)
    if content_refs:
        gated["content_refs"] = [versioned_ref_str(ref) for ref in content_refs]
    if destination is None and decision.destination is not None:
        # No caller-declared destination: the decision's own destination is
        # the model the content is allowed to travel to.
        destination = {
            "model_ref": decision.destination.model_ref,
            "deployment": decision.destination.deployment,
        }
    if destination is not None:
        gated["destination"] = destination
    outcome = check(gated, get_egress=get_egress)
    if outcome.allowed:
        # allow / allow_masked: the (possibly masked) content may travel.
        return outcome.request, [], True
    stripped = {k: v for k, v in outcome.request.items() if k not in EGRESS_CONTENT_KEYS}
    stripped["egress_decision_ref"] = decision_ref
    return stripped, [outcome.issue] if outcome.issue else [], False
