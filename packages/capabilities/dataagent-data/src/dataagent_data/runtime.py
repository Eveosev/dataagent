"""Runtime wiring for the data layer on the shared runtime (W1b).

The shared ``dataagent-runtime`` owns the composition — root resolution
(``DATAAGENT_WORKSPACE`` / ``DATAAGENT_DATA_ROOT``), content store with the
gold-exposure read hook, the shared decisions file, enforcement config and
the module-level default-runtime singleton. The data layer injects its own
pieces (W1b): the versioned store with the trace tables and the reviewed
save paths, the trace repository and the optional OCR engine.

DA12.1 (08 §4.3, W1d): the data layer runs on the shared ``access_recheck``
hook — 22 of the 32 atoms declare ``resource_fields`` and are rechecked
before their handlers read anything. The mode comes from the trusted host:
``DATAAGENT_ENFORCEMENT_MODE`` (``off/warn/enforce``, development default
``warn``; a Mint host injects it through the ``.mcp.json`` server descriptor
``env`` map, which carries ``enforce`` for this bundle). AccessDecisions live
in the shared ``data_root/db/decisions.sqlite3`` so a decision minted by the
governance layer (same ``data_root``) resolves here.
"""

from __future__ import annotations

import os
from typing import Any

from dataagent_data.adapters.storage.sqlite import (
    SqliteDatabase,
    SqliteTraceRepository,
    SqliteVersionedRepository,
)
from dataagent_runtime.runtime import Runtime, resolve_roots

__all__ = ["Runtime", "create", "default_runtime", "reset_default_runtime"]


def create(
    workspace_root: str | os.PathLike[str] | None = None,
    data_root: str | os.PathLike[str] | None = None,
    *,
    enforcement: Any | None = None,
    inference: Any | None = None,
    ocr_engine: Any | None = None,
) -> Runtime:
    # The data layer's versioned store carries the trace tables and the
    # reviewed save paths (W1b); everything else — roots, content store,
    # gold-exposure ledger, the shared decisions file, enforcement wiring
    # and the host authority (12 §5.4: subject/purpose only from the host
    # environment, never from call arguments) — is the shared composition.
    workspace, root = resolve_roots(workspace_root, data_root)
    db = SqliteDatabase(root / "db" / "dataagent.sqlite3")
    return Runtime.create(
        workspace_root=workspace,
        data_root=root,
        enforcement=enforcement,
        inference=inference,
        ocr_engine=ocr_engine,
        db=db,
        versions=SqliteVersionedRepository(db),
        traces=SqliteTraceRepository(db),
    )


_DEFAULT: Runtime | None = None


def default_runtime() -> Runtime:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = create()
    return _DEFAULT


def reset_default_runtime() -> None:
    global _DEFAULT
    _DEFAULT = None
