"""SQLite adapters: versioned objects and DA12.1 decisions."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pydantic import ValidationError

from dataagent_contracts.core import AccessDecision, EgressDecision

_SCHEMA = """
CREATE TABLE IF NOT EXISTS objects (
    kind TEXT NOT NULL,
    object_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    payload TEXT NOT NULL,
    digest TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (kind, object_id, revision)
);
CREATE INDEX IF NOT EXISTS objects_digest ON objects(kind, object_id, digest);

CREATE TABLE IF NOT EXISTS access_decisions (
    decision_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS egress_decisions (
    decision_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


class SqliteDatabase:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        """A connection that is committed *and closed* on exit.

        ``with sqlite3.connect(...)`` only commits/rolls back; the
        connection itself stays open until garbage collection (reviewer
        r21 N6, first fixed in the data layer and now unified here). Every
        repository method goes through this helper so a connection's
        lifetime ends with the call that opened it.
        """

        conn = self.connect()
        try:
            with conn:  # commit on success, rollback on error
                yield conn
        finally:
            conn.close()


class SqliteVersionedRepository:
    """Explicit revisions with optimistic concurrency (06 §6 semantics)."""

    def __init__(self, db: SqliteDatabase):
        self.db = db

    def get(self, kind: str, object_id: str, revision: str) -> dict[str, Any] | None:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT payload FROM objects WHERE kind=? AND object_id=? AND revision=?",
                (kind, object_id, revision),
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def current(self, kind: str, object_id: str) -> tuple[str, dict[str, Any]] | None:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT revision, payload FROM objects WHERE kind=? AND object_id=? "
                "ORDER BY rowid DESC LIMIT 1",
                (kind, object_id),
            ).fetchone()
        return (row["revision"], json.loads(row["payload"])) if row else None

    def save(
        self,
        kind: str,
        object_id: str,
        payload: dict[str, Any],
        *,
        expected_revision: str | None = None,
    ) -> str:
        with self.db._lock:
            with self.db.session() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT revision FROM objects WHERE kind=? AND object_id=? "
                    "ORDER BY rowid DESC LIMIT 1",
                    (kind, object_id),
                ).fetchone()
                current = row["revision"] if row else None
                if expected_revision is not None and current != expected_revision:
                    conn.execute("ROLLBACK")
                    from dataagent_runtime.errors import version_conflict

                    raise version_conflict(
                        f"{kind}/{object_id}: expected revision {expected_revision!r}, "
                        f"current is {current!r}"
                    )
                revision = f"r{self._next_seq(conn, kind, object_id)}"
                conn.execute(
                    "INSERT INTO objects (kind, object_id, revision, payload, digest) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (kind, object_id, revision, _canonical(payload), _digest(payload)),
                )
                return revision

    def _next_seq(self, conn: sqlite3.Connection, kind: str, object_id: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM objects WHERE kind=? AND object_id=?",
            (kind, object_id),
        ).fetchone()
        return int(row["n"]) + 1

    def save_content_addressed(
        self,
        kind: str,
        object_id: str,
        payload: dict[str, Any],
        *,
        expected_revision: str | None = None,
    ) -> tuple[str, dict[str, Any], bool]:
        digest = _digest(payload)
        existing = self.find_by_digest(kind, object_id, digest)
        if existing is not None:
            return existing[0], existing[1], True
        revision = self.save(kind, object_id, payload, expected_revision=expected_revision)
        return revision, payload, False

    def find_by_digest(
        self, kind: str, object_id: str, digest: str
    ) -> tuple[str, dict[str, Any]] | None:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT revision, payload FROM objects WHERE kind=? AND object_id=? "
                "AND digest=? ORDER BY rowid LIMIT 1",
                (kind, object_id, digest),
            ).fetchone()
        return (row["revision"], json.loads(row["payload"])) if row else None


def _decode_access(payload: str) -> AccessDecision | None:
    """An ``AccessDecision`` from a stored row, or ``None`` for a legacy row.

    A row that no longer validates is unusable for ``--authorize`` and is
    skipped rather than fatal; the miss is returned, not silently dropped.
    """

    try:
        return AccessDecision.model_validate_json(payload)
    except ValidationError:
        return None


class SqliteDecisionStore:
    """Persistence for DA12.1 access/egress decisions (08 §5.1)."""

    def __init__(self, db: SqliteDatabase):
        self.db = db

    def save_access(self, decision: AccessDecision) -> None:
        with self.db.session() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO access_decisions (decision_id, payload) VALUES (?, ?)",
                (decision.decision_id, decision.model_dump_json()),
            )

    def get_access(self, decision_id: str) -> AccessDecision | None:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT payload FROM access_decisions WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        return AccessDecision.model_validate_json(row["payload"]) if row else None

    def latest_allow(
        self, subject_ref: str | None = None, purpose: str | None = None
    ) -> AccessDecision | None:
        """Newest ``allow`` decision, optionally narrowed by subject/purpose.

        Unified-CLI ``--authorize`` (12 §5.3) resolves the authorization the
        host already minted; it never mints a decision itself. Newest first,
        unresolvable/legacy rows are skipped rather than fatal.
        """

        with self.db.session() as conn:
            rows = conn.execute(
                "SELECT payload FROM access_decisions ORDER BY rowid DESC"
            ).fetchall()
        for row in rows:
            decision = _decode_access(row["payload"])
            if decision is None:
                continue
            if not decision.is_allowed():
                continue
            if subject_ref is not None and decision.subject_ref != subject_ref:
                continue
            if purpose is not None and decision.purpose != purpose:
                continue
            return decision
        return None

    def save_egress(self, decision: EgressDecision) -> None:
        with self.db.session() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO egress_decisions (decision_id, payload) VALUES (?, ?)",
                (decision.decision_id, decision.model_dump_json()),
            )

    def get_egress(self, decision_id: str) -> EgressDecision | None:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT payload FROM egress_decisions WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        return EgressDecision.model_validate_json(row["payload"]) if row else None
