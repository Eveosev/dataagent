"""Platform ``policy`` family (R1): trusted context resolution.

The context resolver lives in :mod:`dataagent_runtime.policy.context` and is
the only definition of ``resolve_context`` in the repository (enforced by
``scripts/check_layering.py``). Future policy submodules (access, egress,
secrets) join this package in later R steps.
"""

from __future__ import annotations

from .context import (
    AUTHORIZATION_ENV,
    CONTEXT_RESOLVER_ENV,
    HOST_PURPOSE_ENV,
    HOST_SESSION_ENV,
    HOST_SUBJECT_ENV,
    HOST_TURN_ENV,
    LEGACY,
    LOCAL_PURPOSE,
    ContextResolutionError,
    is_legacy_context,
    resolve_context,
    resolved_context,
    with_authorization,
    workspace_scope,
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
    "is_legacy_context",
    "resolve_context",
    "resolved_context",
    "with_authorization",
    "workspace_scope",
]
