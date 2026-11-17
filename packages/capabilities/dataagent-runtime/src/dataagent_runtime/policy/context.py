"""The one context resolver (R1, closes S0 review X1 in the runtime).

Resolution order, highest first:

1. **Host ``_meta``** — the MCP transport channel. Call metadata is read
   with the iface names ``session_id``, ``call_id``, ``turn`` (agent-kernel
   ``kernel/iface/src/types/mod.rs:7-11``); a host-supplied ``context`` map
   is the host's ``CallContext`` for authority fields. The host context is
   trusted because only the host writes ``_meta``.
2. **Host-injected environment** — ``DATAAGENT_HOST_SUBJECT_REF`` /
   ``DATAAGENT_HOST_PURPOSE`` (the existing trusted-host wiring) and the
   Kernel tool-broker ``AGENTCPM_TOOL_BROKER_SESSION`` /
   ``AGENTCPM_TOOL_BROKER_TURN``.
3. **Local owner** — single-user fallback ``local-owner:<uid>`` with a
   workspace-scoped local authorization. This is a subject, not a grant:
   resource reads still need an AccessDecision that covers them.

``arguments.context`` (the caller-writable map) is a *hint* only: it may
carry the ``authorization_ref`` capability and opaque request fields
(``task_ref``, deadline, budget), but it never supplies subject, purpose,
scope or kernel call identity. Those are ignored and recorded in
``ResolvedContext.hints_ignored``.

``scope_ref`` is always ``workspace:<sha256(path)[:24]>`` in the new path,
the same spelling the workbench already uses, so every package stops
carrying its own scope convention.

Rollback: ``DATAAGENT_CONTEXT_RESOLVER=legacy`` (one release) restores the
old precedence — host ``_meta`` context, then ``arguments.context``, with
the host environment only stamping subject/purpose — and the old scope
spelling.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

from pydantic import ValidationError

from dataagent_contracts.core import CallContext

from dataagent_runtime.types import (
    CALL_META_FIELDS,
    CallMeta,
    ContextSource,
    ResolvedContext,
    mapping_of,
)

__all__ = [
    "AUTHORIZATION_ENV",
    "CONTEXT_RESOLVER_ENV",
    "HOST_PURPOSE_ENV",
    "HOST_SESSION_ENV",
    "HOST_SUBJECT_ENV",
    "HOST_TURN_ENV",
    "LEGACY",
    "LOCAL_PURPOSE",
    "ContextResolutionError",
    "resolve_context",
    "resolved_context",
    "with_authorization",
    "workspace_scope",
]

CONTEXT_RESOLVER_ENV = "DATAAGENT_CONTEXT_RESOLVER"
LEGACY = "legacy"
HOST_SUBJECT_ENV = "DATAAGENT_HOST_SUBJECT_REF"
HOST_PURPOSE_ENV = "DATAAGENT_HOST_PURPOSE"
HOST_SESSION_ENV = "AGENTCPM_TOOL_BROKER_SESSION"
HOST_TURN_ENV = "AGENTCPM_TOOL_BROKER_TURN"
AUTHORIZATION_ENV = "DATAAGENT_AUTHORIZATION_REF"
OLD_SCOPE_ENV = "DATAAGENT_SCOPE_REF"
OLD_DEFAULT_SCOPE = "tenant:local"
OLD_DEFAULT_AUTHORIZATION = "cli:unauthorized"
LOCAL_PURPOSE = "local_owner"
WORKSPACE_ENV = "DATAAGENT_WORKSPACE"

# The fields a host ``_meta.context`` may carry. This is the CallContext
# contract, not a second naming scheme: the iface names for call metadata
# are only CALL_META_FIELDS.
_CONTEXT_FIELDS = frozenset(CallContext.model_fields)

# Fields the resolver itself sources from the trusted channels; a host
# context sets them through the explicit picks below, never through the
# opaque-field merge.
_AUTHORITY_FIELDS = frozenset(
    {
        "request_id",
        "scope_ref",
        "authorization_ref",
        "subject_ref",
        "purpose",
        "kernel_session_id",
        "kernel_call_id",
    }
)


class ContextResolutionError(ValueError):
    """The trusted channels carried a malformed context; fail closed."""


def workspace_scope(workspace_root: str | os.PathLike[str] | None = None) -> str:
    """``workspace:<sha256(resolved path)[:24]>`` — the one scope spelling."""

    root = Path(workspace_root or Path.cwd()).expanduser().resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:24]
    return f"workspace:{digest}"


def _env(environ: Mapping[str, str], key: str) -> str | None:
    value = environ.get(key)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _runtime_value(runtime: Any, name: str) -> Any:
    return getattr(runtime, name, None) if runtime is not None else None


def _call_meta_value(value: Any, *, field: str) -> Any:
    """Validate one host CallMeta value (strings non-empty, turn u64)."""

    if value is None:
        return None
    if field == "turn":
        # iface ``turn: u64``: accept an int or a decimal string only. A
        # float (including 3.0) would silently truncate and is rejected.
        if isinstance(value, bool):
            raise ContextResolutionError("_meta.turn must be an unsigned integer")
        if isinstance(value, int):
            turn = value
        elif isinstance(value, str) and value.strip().isdigit():
            turn = int(value.strip())
        else:
            raise ContextResolutionError("_meta.turn must be an unsigned integer")
        if not 0 <= turn <= 2**64 - 1:
            raise ContextResolutionError("_meta.turn must be an unsigned integer")
        return turn
    text = str(value).strip()
    if not text:
        raise ContextResolutionError(f"_meta.{field} must be a non-empty string")
    return text


def _host_parts(
    host_meta: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a host ``_meta`` map into (CallContext map, CallMeta map).

    Only the iface CallMeta names are read as call metadata. A nested
    ``context`` map is the host's CallContext (the channel the workbench and
    the Kernel adapters use). The old flat shape — a ``_meta`` that itself
    looked like a CallContext — stays readable for one release.
    """

    if isinstance(host_meta, CallContext):
        return mapping_of(host_meta) or {}, {}
    if not isinstance(host_meta, Mapping):
        return {}, {}
    meta: dict[str, Any] = {}
    for field in CALL_META_FIELDS:
        if field in host_meta:
            meta[field] = _call_meta_value(host_meta[field], field=field)
    context: dict[str, Any] = {}
    nested = mapping_of(host_meta.get("context"))
    if nested:
        context.update(
            {key: value for key, value in nested.items() if key in _CONTEXT_FIELDS}
        )
    if "request_id" in host_meta or "authorization_ref" in host_meta:
        # Backwards-compatible flat host context; a map that merely repeats
        # ``subject_ref`` is not a full context and is not promoted here.
        for key in _CONTEXT_FIELDS:
            if key in host_meta:
                context.setdefault(key, host_meta[key])
    return context, meta


def _pick(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _resolver_mode(
    runtime: Any, environ: Mapping[str, str], legacy: bool | None
) -> str:
    if legacy is not None:
        return LEGACY if legacy else "v1"
    runtime_value = _runtime_value(runtime, "context_resolver")
    if isinstance(runtime_value, str) and runtime_value.strip().lower() == LEGACY:
        return LEGACY
    env_value = _env(environ, CONTEXT_RESOLVER_ENV)
    if env_value is not None and env_value.lower() == LEGACY:
        return LEGACY
    return "v1"


def _workspace_root(
    runtime: Any,
    environ: Mapping[str, str],
    workspace_root: str | os.PathLike[str] | None,
) -> Path:
    candidate = (
        workspace_root
        or _runtime_value(runtime, "workspace_root")
        or _env(environ, WORKSPACE_ENV)
        or Path.cwd()
    )
    return Path(candidate).expanduser().resolve()


def _local_owner(scope_ref: str) -> tuple[str, str]:
    uid = getattr(os, "getuid", lambda: 0)()
    subject = f"local-owner:{uid}"
    authorization = "local-owner:" + hashlib.sha256(
        (scope_ref + subject).encode("utf-8")
    ).hexdigest()[:24]
    return subject, authorization


def _context_from_values(values: dict[str, Any]) -> CallContext:
    try:
        return CallContext.model_validate(
            {key: value for key, value in values.items() if key in _CONTEXT_FIELDS}
        )
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "context"
        raise ContextResolutionError(
            f"invalid resolved context at {location}: {first['msg']}"
        ) from exc


def _legacy(
    *,
    host_context: dict[str, Any],
    host_meta: dict[str, Any],
    hint: dict[str, Any],
    runtime: Any,
    environ: Mapping[str, str],
) -> ResolvedContext:
    """The one-release rollback path: old precedence and old scope spelling."""

    base: dict[str, Any] = {}
    base.update(hint)
    if host_context:
        # Old ``_context``: ``_meta`` is authoritative over arguments.
        base.update(host_context)
    if not base:
        if runtime is None:
            raise ContextResolutionError(
                "CallContext is required in arguments.context or _meta"
            )
        # The unified CLI never took a context argument: it built one from
        # the host wiring. Keep that shape on the rollback path only when a
        # runtime is in hand; MCP/CLI (no runtime at resolution time) keep
        # their old "context is required" behaviour.
        base = {
            "request_id": f"cli:{uuid.uuid4().hex[:12]}",
            "scope_ref": _env(environ, OLD_SCOPE_ENV) or OLD_DEFAULT_SCOPE,
            "authorization_ref": _env(environ, AUTHORIZATION_ENV)
            or OLD_DEFAULT_AUTHORIZATION,
        }

    subject = _pick(
        _runtime_value(runtime, "host_subject_ref"),
        _env(environ, HOST_SUBJECT_ENV),
        base.get("subject_ref"),
    )
    purpose = _pick(
        _runtime_value(runtime, "host_purpose"),
        _env(environ, HOST_PURPOSE_ENV),
        base.get("purpose"),
    )
    scope_ref = _pick(base.get("scope_ref"), _env(environ, OLD_SCOPE_ENV), OLD_DEFAULT_SCOPE)
    authorization_ref = _pick(
        base.get("authorization_ref"),
        _env(environ, AUTHORIZATION_ENV),
        OLD_DEFAULT_AUTHORIZATION,
    )
    request_id = _pick(base.get("request_id"), f"req:{uuid.uuid4().hex[:12]}")
    values: dict[str, Any] = {
        key: value for key, value in base.items() if key in _CONTEXT_FIELDS
    }
    values.update(
        request_id=request_id,
        scope_ref=scope_ref,
        authorization_ref=authorization_ref,
        subject_ref=subject,
        purpose=purpose,
    )
    scope_hash = hashlib.sha256(str(scope_ref).encode("utf-8")).hexdigest()[:24]
    session = _pick(host_meta.get("session_id"), values.get("kernel_session_id"))
    call = _pick(host_meta.get("call_id"), values.get("kernel_call_id"))
    if session is not None:
        session = _call_meta_value(session, field="session_id")
    if call is not None:
        call = _call_meta_value(call, field="call_id")
    turn = _pick(host_meta.get("turn"), 0)
    # The wire envelope always has a CallMeta; a local process has no host
    # session, so use a local label there but leave the context's kernel ids
    # unset. ``access_recheck`` treats any kernel_session_id as a kernel call
    # when the host declares the guard, so a synthetic one would bypass the
    # full recheck (X1).
    values.update(kernel_session_id=session, kernel_call_id=call)
    context = _context_from_values(values)
    meta = CallMeta(
        session_id=session or f"local:{scope_hash}",
        call_id=call or f"call:{uuid.uuid4().hex[:12]}",
        turn=turn,
    )
    return ResolvedContext(context=context, meta=meta, source=ContextSource.LEGACY)


def resolve_context(
    *,
    host_meta: Mapping[str, Any] | None = None,
    argument_context: Any = None,
    runtime: Any = None,
    environ: Mapping[str, str] | None = None,
    workspace_root: str | os.PathLike[str] | None = None,
    legacy: bool | None = None,
) -> ResolvedContext:
    """Resolve the single trusted ``CallContext`` for a call.

    ``host_meta`` is the MCP ``params._meta`` map; ``argument_context`` is
    the caller-writable ``arguments.context`` hint (a mapping or a
    ``CallContext``). ``runtime`` supplies explicitly configured host
    authority and the workspace root. The result records which channel won.
    """

    environment = os.environ if environ is None else environ
    host_context, host_meta_values = _host_parts(host_meta)
    hint = mapping_of(argument_context) or {}

    if _resolver_mode(runtime, environment, legacy) == LEGACY:
        return _legacy(
            host_context=host_context,
            host_meta=host_meta_values,
            hint=hint,
            runtime=runtime,
            environ=environment,
        )

    root = _workspace_root(runtime, environment, workspace_root)
    scope_ref = workspace_scope(root)
    local_subject, local_authorization = _local_owner(scope_ref)

    env_subject = _env(environment, HOST_SUBJECT_ENV)
    env_purpose = _env(environment, HOST_PURPOSE_ENV)
    env_session = _env(environment, HOST_SESSION_ENV)
    env_turn_raw = _env(environment, HOST_TURN_ENV)
    env_turn = (
        _call_meta_value(env_turn_raw, field="turn") if env_turn_raw is not None else None
    )

    authoritative = bool(host_context) or bool(host_meta_values)
    session_id = _pick(
        host_meta_values.get("session_id"),
        host_context.get("kernel_session_id"),
        _runtime_value(runtime, "host_session_id"),
        env_session,
    )
    call_id = _pick(
        host_meta_values.get("call_id"),
        host_context.get("kernel_call_id"),
        _runtime_value(runtime, "host_call_id"),
    )
    turn = _pick(
        host_meta_values.get("turn"),
        _runtime_value(runtime, "host_turn"),
        env_turn,
        0,
    )
    if session_id is not None:
        session_id = _call_meta_value(session_id, field="session_id")
    if call_id is not None:
        call_id = _call_meta_value(call_id, field="call_id")
    meta = CallMeta(
        session_id=session_id or f"local:{scope_ref.split(':', 1)[-1]}",
        call_id=call_id or f"call:{uuid.uuid4().hex[:12]}",
        turn=turn,
    )

    subject = _pick(
        host_context.get("subject_ref"),
        _runtime_value(runtime, "host_subject_ref"),
        env_subject,
        local_subject,
    )
    purpose = _pick(
        host_context.get("purpose"),
        _runtime_value(runtime, "host_purpose"),
        env_purpose,
        LOCAL_PURPOSE,
    )
    authorization_ref = _pick(
        host_context.get("authorization_ref"),
        _env(environment, AUTHORIZATION_ENV),
        hint.get("authorization_ref"),
        local_authorization,
    )
    request_id = _pick(
        host_context.get("request_id"),
        hint.get("request_id"),
        call_id,
        f"req:{uuid.uuid4().hex[:12]}",
    )

    values: dict[str, Any] = {
        key: value
        for key, value in hint.items()
        if key in _CONTEXT_FIELDS
    }
    values.update(
        request_id=request_id,
        scope_ref=scope_ref,
        authorization_ref=authorization_ref,
        subject_ref=subject,
        purpose=purpose,
        kernel_session_id=session_id,
        kernel_call_id=call_id,
    )
    # Host context owns every opaque field it sets; authority fields were
    # already picked above (the hint never supplies them).
    for key, value in host_context.items():
        if value is not None and key not in _AUTHORITY_FIELDS:
            values[key] = value
    context = _context_from_values(values)

    ignored: list[str] = []
    for field in (
        "subject_ref",
        "purpose",
        "scope_ref",
        "kernel_session_id",
        "kernel_call_id",
    ):
        hint_value = hint.get(field)
        if hint_value is None:
            continue
        current = getattr(context, field, None)
        if str(hint_value) != str(current):
            ignored.append(field)
    if hint.get("authorization_ref") not in (None, authorization_ref):
        ignored.append("authorization_ref")

    if authoritative:
        source = ContextSource.HOST_META
    elif any(
        value is not None
        for value in (
            _runtime_value(runtime, "host_subject_ref"),
            _runtime_value(runtime, "host_purpose"),
            env_subject,
            env_purpose,
            _runtime_value(runtime, "host_session_id"),
            _runtime_value(runtime, "host_call_id"),
            _runtime_value(runtime, "host_turn"),
            env_session,
            env_turn,
        )
    ):
        source = ContextSource.HOST_ENV
    else:
        source = ContextSource.LOCAL_OWNER
    host_fields: list[str] = []
    if host_context.get("subject_ref"):
        host_fields.append("subject_ref")
    if host_context.get("purpose"):
        host_fields.append("purpose")
    if host_meta_values.get("session_id") or host_context.get("kernel_session_id"):
        host_fields.append("session_id")
    if host_meta_values.get("call_id") or host_context.get("kernel_call_id"):
        host_fields.append("call_id")
    if host_meta_values.get("turn") is not None:
        host_fields.append("turn")
    return ResolvedContext(
        context=context,
        meta=meta,
        source=source,
        hints_ignored=tuple(ignored),
        host_fields=tuple(host_fields),
    )


def resolved_context(
    value: Any, *, runtime: Any = None, environ: Mapping[str, str] | None = None
) -> ResolvedContext:
    """Coerce a value already in hand into a ``ResolvedContext``.

    Entry points pass a :class:`ResolvedContext` around; older callers pass
    a ``CallContext``/mapping (which is then treated as a hint and resolved
    against the trusted channels). This is the one adapter ``invoke`` uses,
    so no second resolver exists.
    """

    if isinstance(value, ResolvedContext):
        return value
    return resolve_context(
        argument_context=value, runtime=runtime, environ=environ
    )


def with_authorization(
    resolved: ResolvedContext, authorization_ref: str
) -> ResolvedContext:
    """Replace the capability handle after ``--authorize`` mints one."""

    if not authorization_ref:
        raise ContextResolutionError("authorization_ref must not be blank")
    context = resolved.context.model_copy(update={"authorization_ref": authorization_ref})
    return resolved.with_context(context)
