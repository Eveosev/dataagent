"""Local content-addressed store: the shared runtime implementation (W1b).

The store itself (atomic writes, the read hook that the gold-exposure
ledger wires, digest validation) lives in
``dataagent_runtime.adapters.local_content``; this module re-exports it so
the data layer's storage namespace stays stable.
"""

from __future__ import annotations

from dataagent_runtime.adapters.local_content import (
    LocalContentStore,
    canonical_bytes,
    digest_bytes,
)

__all__ = ["LocalContentStore", "canonical_bytes", "digest_bytes"]
