"""Platform ``types`` family (R1): call metadata and resolved context.

Mirrors the iface ``types`` family without inventing names: :class:`CallMeta`
has exactly ``session_id``, ``call_id`` and ``turn``. ``CallContext`` is the
existing contract object, re-exported here so the platform family has one
import surface.
"""

from __future__ import annotations

from dataagent_contracts.core import CallContext

from .call import CALL_META_FIELDS, CallMeta, ContextSource, ResolvedContext, mapping_of

__all__ = [
    "CALL_META_FIELDS",
    "CallContext",
    "CallMeta",
    "ContextSource",
    "ResolvedContext",
    "mapping_of",
]
