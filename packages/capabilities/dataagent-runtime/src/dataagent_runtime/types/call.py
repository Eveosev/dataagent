"""Call-context types from the iface ``types`` family (R1).

The authoritative shape of :class:`CallMeta` is
``agent-kernel@ae6c3d5 kernel/iface/src/types/mod.rs:7-11``::

    pub struct CallMeta {
        pub session_id: String,
        pub call_id: String,
        pub turn: u64,
    }

Its doc comment fixes two rules this module keeps: the three fields must be
readable on every tool call (transport layer, not tool arguments), and they
must not be copied into a tool parameter schema. :class:`ResolvedContext` is
the local envelope that carries the resolved :class:`CallContext` together
with the host metadata and the source that won resolution.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from dataagent_contracts.core import CallContext

__all__ = [
    "CALL_META_FIELDS",
    "CallMeta",
    "ContextSource",
    "ResolvedContext",
]

# The iface field names, in order. Never rename these to layer-specific
# spellings (``kernel_session_id`` is the CallContext mirror, not the wire
# name the host sends in ``_meta``).
CALL_META_FIELDS = ("session_id", "call_id", "turn")


class CallMeta(BaseModel):
    """Mirror of iface ``CallMeta`` (session_id, call_id, turn)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    turn: int = Field(ge=0, le=2**64 - 1)


class ContextSource(str, Enum):
    """Which channel supplied the authoritative identity of a call.

    ``HOST_META`` is the MCP ``_meta`` channel (the only place the host can
    place :class:`CallMeta` and a host context); ``HOST_ENV`` is the
    host-injected environment (``DATAAGENT_HOST_*`` and the Kernel tool
    broker variables); ``LOCAL_OWNER`` is the single-user fallback for a
    local process; ``LEGACY`` is the one-version rollback path selected by
    ``DATAAGENT_CONTEXT_RESOLVER=legacy``.
    """

    HOST_META = "host-meta"
    HOST_ENV = "host-env"
    LOCAL_OWNER = "local-owner"
    LEGACY = "legacy"


class ResolvedContext(BaseModel):
    """A ``CallContext`` plus the proof of where its authority came from.

    The wrapper is what entry points and ``invoke`` pass around. It is not a
    wire type: the contract stays :class:`~dataagent_contracts.core.CallContext`,
    so downstream code that only needs the context reads ``.context``.
    ``hints_ignored`` records caller-writable fields that resolution refused
    to use (subject, purpose, scope, kernel call identity), for tests and
    diagnostics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    context: CallContext
    meta: CallMeta
    source: ContextSource
    hints_ignored: tuple[str, ...] = ()
    # Authority fields that actually came from the host ``_meta`` channel.
    # ``invoke`` may let the runtime's configured host authority fill the
    # rest, but never overwrite these.
    host_fields: tuple[str, ...] = ()

    @property
    def call_context(self) -> CallContext:
        """The resolved contract object (kept explicit for call sites)."""

        return self.context

    def with_context(self, context: CallContext) -> "ResolvedContext":
        """Copy with a replaced ``CallContext`` (e.g. ``--authorize``)."""

        return self.model_copy(update={"context": context})


def mapping_of(value: Any) -> dict[str, Any] | None:
    """Best-effort mapping view of a context-shaped value (no validation)."""

    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            data = dump(mode="python")
        except TypeError:  # pragma: no cover - alternate model_dump signatures
            data = dump()
        if isinstance(data, Mapping):
            return {str(key): item for key, item in data.items()}
    return None
