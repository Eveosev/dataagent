"""Runtime wiring for layer packages.

A layer package builds its own runtime on top of the shared adapters; this
module provides the default local composition (content store + versioned
repository + decision store) and the DA12.1 enforcement configuration.
``dataagent-runtime`` itself ships no operations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dataagent_runtime.adapters.gold_ledger import GoldExposureLedger
from dataagent_runtime.adapters.local_content import LocalContentStore
from dataagent_runtime.adapters.sqlite import (
    SqliteDatabase,
    SqliteDecisionStore,
    SqliteVersionedRepository,
)
from dataagent_runtime.enforcement import EnforcementConfig, enforcement_from_env


def resolve_roots(
    workspace_root: str | os.PathLike[str] | None = None,
    data_root: str | os.PathLike[str] | None = None,
) -> tuple[Path, Path]:
    """The (workspace, data_root) pair every layer's ``create()`` starts from.

    Precedence (08 §2): the explicit argument, then the host environment
    (``DATAAGENT_WORKSPACE`` / ``DATAAGENT_DATA_ROOT``), then the conventional
    ``<workspace>/.dataagent``. Shared here so every layer resolves the
    same way instead of restating the chain.
    """

    workspace = Path(
        workspace_root or os.environ.get("DATAAGENT_WORKSPACE") or Path.cwd()
    ).resolve()
    root = Path(
        data_root
        or os.environ.get("DATAAGENT_DATA_ROOT")
        or (workspace / ".dataagent")
    ).resolve()
    return workspace, root


@dataclass
class Runtime:
    workspace_root: Path
    data_root: Path
    content: LocalContentStore
    versions: SqliteVersionedRepository
    decisions: SqliteDecisionStore
    db: SqliteDatabase
    enforcement: EnforcementConfig = field(default_factory=EnforcementConfig)
    # Trusted-host authority (review §7.1): fixed subject/purpose used for
    # every call on this runtime — call arguments can never set or override
    # them (B7). Configured explicitly, or via the host-injected environment
    # (DATAAGENT_HOST_SUBJECT_REF / DATAAGENT_HOST_PURPOSE).
    host_subject_ref: str | None = None
    host_purpose: str | None = None
    inference: Any | None = None
    # Layer-owned extras (W1b): the data layer wires its trace repository
    # and optional OCR engine here; other layers leave them unset.
    traces: Any | None = None
    ocr_engine: Any | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def access_resolver(self, authorization_ref: str):
        """Resolve ``authorization_ref`` for the DA12.1 access recheck.

        Decisions live in the shared ``data_root/db/decisions.sqlite3``:
        every layer composing on the same ``data_root`` resolves the
        AccessDecision another layer minted (08 §2 共享 data_root / §4.3).
        """

        return self.decisions.get_access(authorization_ref)

    @classmethod
    def create(
        cls,
        workspace_root: str | os.PathLike[str] | None = None,
        data_root: str | os.PathLike[str] | None = None,
        *,
        enforcement: EnforcementConfig | None = None,
        host_subject_ref: str | None = None,
        host_purpose: str | None = None,
        inference: Any | None = None,
        ocr_engine: Any | None = None,
        versions: Any | None = None,
        decisions: Any | None = None,
        db: Any | None = None,
        traces: Any | None = None,
    ) -> "Runtime":
        """Compose the default local runtime.

        ``versions``/``decisions``/``db``/``traces`` let a layer swap in its
        own adapters (W1b: the data layer's versioned store carries the trace
        tables) while keeping the shared wiring — roots, decisions file,
        content store, gold-exposure ledger, enforcement, host authority.
        """

        workspace, root = resolve_roots(workspace_root, data_root)
        (root / "content").mkdir(parents=True, exist_ok=True)
        (root / "db").mkdir(parents=True, exist_ok=True)
        db = db if db is not None else SqliteDatabase(root / "db" / "runtime.sqlite3")
        # DA12.1 decisions are shared across every layer composing on the same
        # data_root (08 §2): a governance-minted AccessDecision is what the
        # data/application recheck resolves, so it lives in its own SQLite file
        # instead of the layer-private versioned store.
        decision_db = SqliteDatabase(root / "db" / "decisions.sqlite3")
        content = LocalContentStore(root / "content")
        # r38 F3: every content read through the shared store consults the
        # cross-layer gold-exposure ledger — reading a registered gold
        # expectation anywhere other than the acceptance evaluator records
        # an exposure (the vault suspends the hook for its trusted read).
        content.read_hook = GoldExposureLedger(root / "vault").read_hook()
        return cls(
            workspace_root=workspace,
            data_root=root,
            content=content,
            versions=versions if versions is not None else SqliteVersionedRepository(db),
            decisions=decisions if decisions is not None else SqliteDecisionStore(decision_db),
            db=db,
            enforcement=enforcement_from_env(enforcement),
            # Trusted-host authority: configuration first, then the
            # host-injected environment (Mint clears the subprocess env, so
            # only values the host deliberately writes in the server
            # descriptor reach here). Call arguments never set these.
            host_subject_ref=host_subject_ref or os.environ.get("DATAAGENT_HOST_SUBJECT_REF"),
            host_purpose=host_purpose or os.environ.get("DATAAGENT_HOST_PURPOSE"),
            inference=inference,
            ocr_engine=ocr_engine,
            traces=traces,
        )


_DEFAULT: Runtime | None = None


def default_runtime() -> Runtime:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Runtime.create()
    return _DEFAULT


def reset_default_runtime() -> None:
    global _DEFAULT
    _DEFAULT = None
