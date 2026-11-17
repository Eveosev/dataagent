"""``invoke(operation, input, CallContext) -> CapabilityResult[T]`` (08 §4.1).

Same wire contract as the data layer (06 §4.1), plus the DA12.1 access
recheck in front of any operation that declares ``resource_fields``: the
resources it reads must be covered by the call's ``authorization_ref``.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from dataagent_contracts.core import (
    CallContext,
    CapabilityResult,
    CapabilityStatus,
    ExecutionRef,
    Issue,
    Severity,
    StandardErrorCode,
    VersionedRef,
)

from dataagent_runtime.enforcement import (
    EnforcementConfig,
    RecheckOutcome,
    access_recheck,
)
from dataagent_runtime.errors import CapabilityError, NeedsInputError
from dataagent_runtime.policy.context import (
    ContextResolutionError,
    ResolvedContext,
    _reseal,
    resolve_context,
    verify_resolved,
    workspace_scope,
)
from dataagent_runtime.types import ContextSource
from dataagent_runtime.registry import IMPLEMENTATION_REF, get_spec


def now() -> datetime:
    return datetime.now(timezone.utc)


def _failure(
    code: StandardErrorCode | str,
    message: str,
    *,
    operation: str,
    capability_id: str = "unknown",
    suggested_action: str | None = None,
    retryable: bool = False,
    target: str | None = None,
) -> CapabilityResult[Any]:
    issue = Issue(
        code=code.value if isinstance(code, StandardErrorCode) else code,
        severity=Severity.error,
        message=message,
        retryable=retryable,
        suggested_action=suggested_action,
        target=target,
    )
    return CapabilityResult[Any](
        status=CapabilityStatus.failed,
        issues=[issue],
        execution_ref=ExecutionRef(
            invocation_id=f"inv:{uuid.uuid4().hex[:12]}",
            operation=operation,
            capability_id=capability_id,
            implementation_ref=IMPLEMENTATION_REF,
            started_at=now(),
            finished_at=now(),
        ),
    )


def _to_versioned_ref(value: Any) -> VersionedRef | None:
    if isinstance(value, VersionedRef):
        return value
    asset = getattr(value, "asset", None)
    if asset is not None and getattr(asset, "id", None):
        # TableRef and friends carry an AssetRef with id/revision.
        return VersionedRef(id=asset.id, revision=asset.revision)
    if (
        getattr(value, "id", None)
        and getattr(value, "kind", None)
        and getattr(value, "revision", None)
    ):
        # AssetRef itself (e.g. FileRef): id/revision/kind are direct fields.
        return VersionedRef(id=value.id, revision=value.revision)
    return None


class UnverifiableResourceError(ValueError):
    """A declared resource field produced no verifiable ``VersionedRef``."""

    def __init__(self, field: str, detail: str) -> None:
        self.field = field
        self.detail = detail
        super().__init__(f"resource field {field!r} {detail}")


def _resource_refs(spec_input: BaseModel, resource_fields: tuple[str, ...]) -> list[VersionedRef]:
    """Extract refs, refusing a declared field that cannot be verified.

    A present declared value that does not carry id/kind/revision used to be
    skipped silently; the recheck then saw an empty list and compared no
    resource at all (r41 X2 follow-up). An absent optional resource is left
    absent, matching the old skip.
    """

    refs: list[VersionedRef] = []
    for name in resource_fields:
        value = getattr(spec_input, name, None)
        if value is None:
            # An absent optional resource is not a resource to check; old
            # invoke skipped it. A *present* value must still convert.
            continue
        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                ref = _to_versioned_ref(item)
                if ref is None:
                    raise UnverifiableResourceError(
                        name,
                        f"item {index} does not carry an id/kind/revision reference",
                    )
                refs.append(ref)
        else:
            ref = _to_versioned_ref(value)
            if ref is None:
                raise UnverifiableResourceError(
                    name, "does not carry an id/kind/revision reference"
                )
            refs.append(ref)
    return refs


# Resolvers whose assets are pure content addresses: the asset identity is
# *derived from* the content digest, so the recheck can verify that the
# claimed asset and the content actually read are the same object.
_CONTENT_RESOLVERS = frozenset({"content", "local_content"})

# Sibling fields that name the content object the handler actually reads.
# ``data_ref`` is TableRef's payload pointer; ``field_stats_ref`` is
# ProfileRef's stats payload pointer; ``blocks_ref`` is DocumentRef's parsed
# body pointer. Every field listed here must name the same object as the
# asset it travels with (r28 B1: a ProfileRef whose asset names the allowed
# stats digest while ``field_stats_ref`` points at another, forbidden
# object; r32-gov B1: the same recombination on a DocumentRef, where the
# parse record alone cannot tell which asset the body belongs to).
_WRAPPER_CONTENT_BINDING_FIELDS = ("data_ref", "field_stats_ref", "blocks_ref")

# A flat ``AssetRef`` (e.g. ``FileRef``) *is* the asset: it carries the
# payload pointer itself in ``content_digest`` (``digest`` is the redundant
# spelling of the same claim; the FileRef contract already forces them to
# agree). r30 B1.1: without this branch a FileRef skipped the closure check
# entirely, so an authorized file asset could read another file's bytes.
_FLAT_CONTENT_BINDING_FIELDS = ("content_digest", "digest")


def _is_flat_asset(item: Any) -> bool:
    """``item`` looks like a bare ``AssetRef`` (id/kind/revision/resolver)."""

    return bool(
        getattr(item, "id", None)
        and getattr(item, "kind", None)
        and getattr(item, "revision", None)
        and getattr(item, "resolver", None)
    )


# A revision of this shape names content by address; any other revision is a
# free-form label bound through the layer's identity registry instead.
_DIGEST_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")


def _is_digest_revision(revision: Any) -> bool:
    """``revision`` claims to *be* a content address (``sha256:<64 hex>``)."""

    return isinstance(revision, str) and bool(_DIGEST_REVISION.match(revision))


def _binding_closure_errors(
    name: str,
    holder: Any,
    asset: Any,
    binding_fields: tuple[str, ...],
    *,
    revision_names_content: bool = True,
) -> list[str]:
    """Closure errors for one (holder, asset) pair against its content fields.

    The binding the decision relies on is the revision (the resource ref is
    ``"<id>@<revision>"``): the content that is actually read must be the
    content that revision names. An explicit asset digest is the second,
    redundant spelling of the same invariant and both spellings must agree
    when both are present. This holds for **every** resolver, not only the
    content-addressed ones: ``AssetRef.resolver`` is caller-chosen, so
    trusting a self-declared ``resolver="workspace"`` label to opt out of
    the binding would let any caller detach the covered revision from the
    content actually read (r30 B1.2). A non-content resolver is accepted
    exactly when the asset is still bound to the read content by these
    fields — "verifiable resolver or content binding".

    ``revision_names_content=False`` is the flat ``AssetRef`` case whose
    revision is a free-form label (``rev:1``), not a content address: such an
    identity is bound to its bytes by the layer's immutable identity registry
    (``register_file_ref``), not by the revision, so the runtime has nothing
    to compare here and the handler enforces that registry binding instead.
    """

    bindings = {
        field: getattr(holder, field, None)
        for field in binding_fields
        if getattr(holder, field, None)
    }
    if not bindings:
        return []
    digest = getattr(asset, "digest", None)
    revision = getattr(asset, "revision", None)
    label = f"{name}({getattr(asset, 'id', '?')})"
    if not digest and not revision:
        return [
            f"{label}: content-resolved asset carries neither digest nor "
            "revision; the asset-to-content binding cannot be verified"
        ]
    errors: list[str] = []
    for field, binding in bindings.items():
        if digest and binding != digest:
            errors.append(
                f"{label}: {field} {binding} does not match the asset digest "
                f"{digest}; the asset cannot be rebound to other content"
            )
        if revision_names_content and binding != revision:
            errors.append(
                f"{label}: {field} {binding} is not the asset revision "
                f"{revision!r}; a decision for it would not bind the "
                "content that is actually read"
            )
    # A content-resolved asset's locator is a *content address*: when it is
    # present it must point at the very content the revision/digest names,
    # never at another object's location.
    if getattr(asset, "resolver", None) in _CONTENT_RESOLVERS:
        locator = getattr(asset, "locator", None)
        if locator:
            address = digest or revision
            if locator != address:
                errors.append(
                    f"{label}: locator {locator!r} is not the content address "
                    f"{address!r}; a content-resolved asset cannot be pointed "
                    "at another object's location"
                )
    return errors


def _closure_errors(spec_input: BaseModel, resource_fields: tuple[str, ...]) -> list[str]:
    """Resource-closure errors: a self-reported asset rebound to other content.

    A ``TableRef``-shaped input names an asset (what the authorization was
    minted for) and a ``data_ref`` (the content actually read). A payload
    whose content pointer disagrees with the asset revision/digest is a
    fabricated binding: the decision covers one asset while the reader would
    fetch another object's content (review B1, r28 B1, r30 B1.1/B1.2). The
    same invariant covers every content-binding sibling field, and flat
    ``AssetRef`` inputs (``FileRef``) are their own asset and bind their
    payload through ``content_digest``. Such closures cannot be verified
    and are refused before any read.
    """

    errors: list[str] = []
    for name in resource_fields:
        value = getattr(spec_input, name, None)
        if value is None:
            continue
        items = value if isinstance(value, (list, tuple)) else [value]
        for item in items:
            asset = getattr(item, "asset", None)
            if asset is not None and getattr(asset, "id", None):
                # TableRef/ProfileRef and friends carry an AssetRef with
                # id/revision plus a sibling content pointer.
                errors.extend(
                    _binding_closure_errors(
                        name, item, asset, _WRAPPER_CONTENT_BINDING_FIELDS
                    )
                )
            elif _is_flat_asset(item):
                # A flat AssetRef (e.g. FileRef) is its own asset (r30 B1.1):
                # its payload pointer is the verified ``content_digest``.
                # When the revision claims to be a content address (a digest
                # shape) that pointer must be it; a free-form label revision
                # is an identity-registry claim the handler verifies instead.
                errors.extend(
                    _binding_closure_errors(
                        name,
                        item,
                        item,
                        _FLAT_CONTENT_BINDING_FIELDS,
                        revision_names_content=_is_digest_revision(
                            getattr(item, "revision", None)
                        ),
                    )
                )
    return errors


def _legacy_host_context(rt: Any, ctx: CallContext) -> CallContext:
    """Old ``_host_context``: stamp runtime host authority, resource path only."""

    subject = getattr(rt, "host_subject_ref", None)
    purpose = getattr(rt, "host_purpose", None)
    if not subject and not purpose:
        return ctx
    updates: dict[str, str | None] = {}
    if subject and ctx.subject_ref != subject:
        updates["subject_ref"] = subject
    if purpose and ctx.purpose != purpose:
        updates["purpose"] = purpose
    if not updates:
        return ctx
    return ctx.model_copy(update=updates)


def _resolve_call_context(rt: Any, context: Any) -> ResolvedContext:
    """Resolve one trusted context for the whole call (R1, S0 X1).

    Entry points hand over a :class:`ResolvedContext`; older callers hand
    over a bare ``CallContext``/mapping, which is treated as a *hint* and
    resolved against the trusted channels. Either way the result is the
    context the recheck and every handler see — no-resource handlers
    included, which is what closes the B7 gap on non-resource operations.
    """

    if isinstance(context, ResolvedContext):
        if not verify_resolved(context):
            raise ContextResolutionError(
                "ResolvedContext was not produced by resolve_context or was modified; "
                "the caller must pass a hint, not a trusted envelope"
            )
        resolved = context
        # The legacy path is deliberately frozen: old ``invoke`` stamped the
        # host authority only on the resource-recheck path, never on
        # no-resource operations. Do not apply the new host authority here.
        if resolved.source is ContextSource.LEGACY:
            return resolved
        # The runtime's workspace is authoritative for scope spelling even
        # when an entry point resolved against its own cwd.
        workspace = getattr(rt, "workspace_root", None)
        if workspace is not None:
            scope_ref = workspace_scope(workspace)
            if resolved.context.scope_ref != scope_ref:
                resolved = resolved.model_copy(
                    update={
                        "context": resolved.context.model_copy(
                            update={"scope_ref": scope_ref}
                        )
                    }
                )
        # Host ``_meta`` fields are final. For every field the host did not
        # set, the runtime's configured host authority (explicit or
        # environment) outranks the local-owner/environment value an entry
        # point may have used before a runtime was in hand.
        host_fields = set(resolved.host_fields)
        context_updates: dict[str, Any] = {}
        subject = getattr(rt, "host_subject_ref", None)
        purpose = getattr(rt, "host_purpose", None)
        if (
            subject
            and "subject_ref" not in host_fields
            and resolved.context.subject_ref != subject
        ):
            context_updates["subject_ref"] = subject
        if (
            purpose
            and "purpose" not in host_fields
            and resolved.context.purpose != purpose
        ):
            context_updates["purpose"] = purpose
        session = getattr(rt, "host_session_id", None)
        call = getattr(rt, "host_call_id", None)
        if (
            session
            and "session_id" not in host_fields
            and resolved.context.kernel_session_id != session
        ):
            context_updates["kernel_session_id"] = session
        if (
            call
            and "call_id" not in host_fields
            and resolved.context.kernel_call_id != call
        ):
            context_updates["kernel_call_id"] = call
        if context_updates:
            resolved = resolved.model_copy(
                update={
                    "context": resolved.context.model_copy(
                        update=context_updates
                    )
                }
            )
        if session and "session_id" not in host_fields and resolved.meta.session_id != session:
            resolved = resolved.model_copy(
                update={"meta": resolved.meta.model_copy(update={"session_id": session})}
            )
        if call and "call_id" not in host_fields and resolved.meta.call_id != call:
            resolved = resolved.model_copy(
                update={"meta": resolved.meta.model_copy(update={"call_id": call})}
            )
        turn = getattr(rt, "host_turn", None)
        if (
            turn is not None
            and "turn" not in host_fields
            and resolved.meta.turn != turn
        ):
            resolved = resolved.model_copy(
                update={"meta": resolved.meta.model_copy(update={"turn": turn})}
            )
        return _reseal(resolved)
    return resolve_context(argument_context=context, runtime=rt)


def invoke(
    operation: str,
    payload: dict[str, Any] | None,
    context: CallContext | dict[str, Any] | ResolvedContext,
    *,
    runtime: Any = None,
    resolver: Any = None,
    enforcement: EnforcementConfig | None = None,
) -> CapabilityResult[Any]:
    """Dispatch to a registered operation.

    ``runtime`` must expose the pieces the layer's handlers need (content
    store, versioned repository, decision store, enforcement config ...).
    ``resolver`` resolves ``authorization_ref`` to an ``AccessDecision``;
    when omitted, the runtime's ``access_resolver`` is used, and if that is
    missing too the recheck fails closed for resource-reading operations.

    ``context`` is a resolved envelope from an entry point or a bare
    ``CallContext``/mapping. The bare form is a caller hint: it is resolved
    through :func:`dataagent_runtime.policy.context.resolve_context` before
    the recheck and before any handler runs (R1).
    """

    spec = get_spec(operation)
    if spec is None:
        return _failure(
            StandardErrorCode.unsupported,
            f"operation is not registered: {operation}",
            operation=operation,
            suggested_action="tools/list shows the implemented operations",
        )

    rt = runtime
    if rt is None:
        from dataagent_runtime.runtime import default_runtime

        rt = default_runtime()
    try:
        resolved = _resolve_call_context(rt, context)
    except ContextResolutionError as exc:
        return _failure(
            StandardErrorCode.invalid_input,
            f"invalid CallContext: {exc}",
            operation=operation,
            capability_id=spec.capability_id,
            target="context",
        )
    ctx = resolved.context
    if not ctx.authorization_ref.strip():
        return _failure(
            StandardErrorCode.invalid_input,
            "authorization_ref is required and must not be blank",
            operation=operation,
            capability_id=spec.capability_id,
            target="context.authorization_ref",
        )

    config = enforcement or getattr(rt, "enforcement", None) or EnforcementConfig()

    started = now()
    if ctx.deadline is not None and started > ctx.deadline:
        return _failure(
            StandardErrorCode.timeout,
            "call deadline has already passed",
            operation=operation,
            capability_id=spec.capability_id,
            retryable=True,
        )

    try:
        input_obj = spec.input_model.model_validate(payload or {})
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(p) for p in first.get("loc", ()))
        return _failure(
            StandardErrorCode.invalid_input,
            f"invalid input at {location}: {first['msg']}",
            operation=operation,
            capability_id=spec.capability_id,
            target=location or None,
        )

    # A declared resource field must always produce a verifiable ref, even
    # under ``mode=off``: otherwise an optional/empty/opaque value would make
    # the recheck compare an empty resource list (r41 X2 follow-up).
    resource_refs: list[VersionedRef] | None = None
    if spec.resource_fields:
        try:
            resource_refs = _resource_refs(input_obj, spec.resource_fields)
        except UnverifiableResourceError as exc:
            return _failure(
                StandardErrorCode.invalid_input,
                f"declared resource field cannot be verified: {exc}",
                operation=operation,
                capability_id=spec.capability_id,
                target=exc.field,
            )

    # DA12.1 access recheck in front of any resource read (08 §4.3).
    # ``off`` disables the hook outright; ``warn`` keeps the call running with
    # a warning (development default); ``enforce`` denies before any read.
    if spec.resource_fields and config.mode != "off":
        if resolved.source is ContextSource.LEGACY:
            # Old invoke applied the host authority only here (resource
            # recheck), not to no-resource operations or mode=off calls.
            ctx = _legacy_host_context(rt, ctx)
        resolve = resolver or getattr(rt, "access_resolver", None)
        if resolve is None:
            result = _failure(
                "da12.access_denied",
                "no AccessDecision resolver is wired; refusing to read input resources",
                operation=operation,
                capability_id=spec.capability_id,
            )
        else:
            reasons = _closure_errors(input_obj, spec.resource_fields)
            outcome = (
                RecheckOutcome(
                    ok=False,
                    issue=Issue(
                        code="da12.access_denied",
                        severity=Severity.error,
                        message=(
                            "access recheck failed: unverifiable resource closure: "
                            + "; ".join(reasons)
                        ),
                        retryable=False,
                        suggested_action="supply a TableRef whose asset revision and "
                        "data_ref are the content digest it was minted for",
                    ),
                    reasons=reasons,
                )
                if reasons
                else access_recheck(
                    ctx,
                    resolve,
                    resource_refs or [],
                    config=config,
                )
            )
            if outcome.ok:
                result = None
            elif config.mode == "warn":
                warned = _run_handler(spec, input_obj, ctx, rt, started)
                if outcome.issue is not None:
                    warned.issues.append(
                        Issue(
                            code="da12.access_denied",
                            severity=Severity.warning,
                            message="[warn] " + outcome.issue.message,
                            retryable=False,
                        )
                    )
                result = warned
            else:
                result = _failure(
                    "da12.access_denied",
                    outcome.issue.message if outcome.issue else "access recheck failed",
                    operation=operation,
                    capability_id=spec.capability_id,
                )
        if result is not None:
            return result

    return _run_handler(spec, input_obj, ctx, rt, started)


def _run_handler(
    spec: Any, input_obj: BaseModel, ctx: CallContext, rt: Any, started: datetime
) -> CapabilityResult[Any]:
    try:
        result = spec.handler(input_obj, ctx, rt)
    except NeedsInputError as exc:
        result = CapabilityResult[Any](
            status=CapabilityStatus.needs_input, data=None, issues=[exc.issue]
        )
    except CapabilityError as exc:
        result = CapabilityResult[Any](status=CapabilityStatus.failed, issues=[exc.to_issue()])
    except Exception as exc:  # noqa: BLE001 - mapped, never leaked as a traceback
        result = CapabilityResult[Any](
            status=CapabilityStatus.failed,
            issues=[
                Issue.standard(
                    StandardErrorCode.execution_unknown,
                    f"{type(exc).__name__}: {exc}",
                    retryable=False,
                    suggested_action="inspect the input; do not retry blindly",
                )
            ],
        )
    if not isinstance(result, CapabilityResult):
        # Handlers may return their output model directly; wrap as an ok result.
        result = CapabilityResult[Any](status=CapabilityStatus.ok, data=result)
    finished = now()
    if result.execution_ref is None:
        result.execution_ref = ExecutionRef(
            invocation_id=f"inv:{uuid.uuid4().hex[:12]}",
            operation=spec.operation,
            capability_id=spec.capability_id,
            implementation_ref=IMPLEMENTATION_REF,
            started_at=started,
            finished_at=finished,
        )
    return result
