"""SQLite adapters: the data layer's traces on the shared versioned store (W1b).

The ``objects`` schema, the per-call connection lifetime and the plain
``get``/``current``/``find_by_digest`` reads are owned by
``dataagent_runtime.adapters.sqlite`` and inherited here. This module adds
the data layer's own pieces on top: the trace tables (sessions /
trace_events / checkpoints) with their migrations, the reviewed save paths
(the optimistic-concurrency check and the "find digest / append revision"
step share one ``BEGIN IMMEDIATE`` transaction, r4-review #10; a save of
identical content is idempotent), the append-only trace repository, and
``ref_exists`` for refusing fabricated evidence refs (06 §5 step 3).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from dataagent_data.ports.trace import TraceRecord
from dataagent_runtime.adapters.sqlite import (
    SqliteDatabase as _SharedDatabase,
    SqliteVersionedRepository as _SharedRepository,
)

_TRACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS trace_events (
    session_id TEXT NOT NULL,
    kernel_session_id TEXT,
    event_id TEXT NOT NULL,
    cursor INTEGER NOT NULL,
    seq INTEGER,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    ts_ms INTEGER NOT NULL,
    PRIMARY KEY (session_id, event_id),
    UNIQUE (session_id, cursor),
    UNIQUE (seq)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind_prefix TEXT NOT NULL,
    cursor INTEGER NOT NULL,
    digest TEXT NOT NULL
);
"""


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _idempotency_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Event identity excludes the authorization used for this retry.

    The same event retried under a different ``authorization_ref`` is still the
    same event; including it made a legitimate retry fail as a version
    conflict (r5-plan item 5).
    """

    return {key: value for key, value in payload.items() if key != "authorization_ref"}


def _digest(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _version_conflict(message: str):
    # Imported lazily: runtime.errors pulls the runtime package, whose storage
    # adapter imports this module's base (avoid a circular import at load).
    from dataagent_runtime.errors import version_conflict

    return version_conflict(message)


class SqliteDatabase(_SharedDatabase):
    """The shared object store plus the data layer's trace tables."""

    def __init__(self, path):
        super().__init__(path)
        with self.session() as conn:
            conn.executescript(_TRACE_SCHEMA)
            self._migrate(conn)

    def connect(self) -> sqlite3.Connection:
        conn = super().connect()
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Bring pre-existing databases up to the current trace schema."""

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(trace_events)")}
        if "kernel_session_id" not in columns:
            conn.execute("ALTER TABLE trace_events ADD COLUMN kernel_session_id TEXT")
        if "seq" not in columns:
            conn.execute("ALTER TABLE trace_events ADD COLUMN seq INTEGER")
            # Backfill in insertion order so a cross-session page never skips
            # an event that predates the migration.
            conn.execute("UPDATE trace_events SET seq = rowid WHERE seq IS NULL")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS trace_events_seq ON trace_events(seq)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS trace_events_kernel_session "
            "ON trace_events(kernel_session_id, seq)"
        )


class SqliteVersionedRepository(_SharedRepository):
    """The data layer's reviewed save paths on the shared repository.

    Inherited from the shared class: the per-call connection lifetime
    (reviewer r21 N6) and the plain ``get``/``current``/``find_by_digest``
    reads. Kept here: the transactional save paths (see the module docstring)
    and ``ref_exists``.
    """

    def save(self, kind, object_id, payload, *, expected_revision=None) -> str:
        with self.db._lock:
            return self._save_locked(
                kind, object_id, payload, expected_revision=expected_revision
            )

    def _save_locked(self, kind, object_id, payload, *, expected_revision) -> str:
        # BEGIN IMMEDIATE serialises "read current + append" across processes,
        # not just threads. Without it two writers can both compute ``r2`` and
        # one of them surfaces a raw primary-key error.
        with self.db.session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT revision, payload FROM objects WHERE kind=? AND object_id=? "
                "ORDER BY rowid DESC LIMIT 1",
                (kind, object_id),
            ).fetchone()
            current_revision = row["revision"] if row else None
            if expected_revision is not None and expected_revision != current_revision:
                raise _version_conflict(
                    f"version conflict for {kind}:{object_id}: expected {expected_revision}, "
                    f"current {current_revision}"
                )
            if row is not None and _digest(json.loads(row["payload"])) == _digest(payload):
                return current_revision  # idempotent same content
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM objects WHERE kind=? AND object_id=?",
                (kind, object_id),
            ).fetchone()["c"]
            revision = f"r{int(count) + 1}"
            conn.execute(
                "INSERT INTO objects(kind, object_id, revision, payload, digest) VALUES (?,?,?,?,?)",
                (kind, object_id, revision, _canonical(payload), _digest(payload)),
            )
        return revision

    def save_content_addressed(self, kind, object_id, payload, *, expected_revision=None):
        with self.db._lock:
            return self._save_content_addressed_locked(
                kind, object_id, payload, expected_revision=expected_revision
            )

    def _save_content_addressed_locked(
        self, kind, object_id, payload, *, expected_revision
    ):
        digest = _digest(payload)
        with self.db.session() as conn:
            conn.execute("BEGIN IMMEDIATE")
            # The optimistic-concurrency check belongs inside the same
            # transaction as the "find digest / append revision" step: a
            # handler that calls ``current()`` first and this method second has
            # a window in which two writers both observe ``r1`` and both
            # succeed (P1 lost update, r4-review #10).
            if expected_revision is not None:
                current = conn.execute(
                    "SELECT revision FROM objects WHERE kind=? AND object_id=? "
                    "ORDER BY rowid DESC LIMIT 1",
                    (kind, object_id),
                ).fetchone()
                current_revision = current["revision"] if current else None
                if expected_revision != current_revision:
                    raise _version_conflict(
                        f"version conflict for {kind}:{object_id}: expected "
                        f"{expected_revision}, current {current_revision}"
                    )
            existing = conn.execute(
                "SELECT revision, payload FROM objects WHERE kind=? AND object_id=? AND digest=? "
                "ORDER BY rowid LIMIT 1",
                (kind, object_id, digest),
            ).fetchone()
            if existing:
                return existing["revision"], json.loads(existing["payload"]), True
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM objects WHERE kind=? AND object_id=?",
                (kind, object_id),
            ).fetchone()["c"]
            revision = f"r{int(count) + 1}"
            conn.execute(
                "INSERT INTO objects(kind, object_id, revision, payload, digest) VALUES (?,?,?,?,?)",
                (kind, object_id, revision, _canonical(payload), digest),
            )
        return revision, payload, False

    def revisions(self, kind: str, object_id: str) -> list[str]:
        with self.db.session() as conn:
            rows = conn.execute(
                "SELECT revision FROM objects WHERE kind=? AND object_id=? ORDER BY rowid",
                (kind, object_id),
            ).fetchall()
        return [row["revision"] for row in rows]

    def ref_exists(self, ref: str) -> bool:
        """Whether ``ref`` names a persisted object, in either spelling.

        A ref is a full ``object_id`` (some ids already embed ``@``, e.g.
        ``file:<id>@<digest>``) or ``<object_id>@<revision>`` where the id alone
        is unambiguous. Used to refuse fabricated evidence refs (06 §5 step 3).
        """

        with self.db.session() as conn:
            return self._ref_exists(conn, ref)

    @staticmethod
    def _ref_exists(conn: sqlite3.Connection, ref: str) -> bool:
        if not ref:
            return False
        if conn.execute(
            "SELECT 1 FROM objects WHERE object_id=? LIMIT 1", (ref,)
        ).fetchone():
            return True
        object_id, sep, revision = ref.rpartition("@")
        if not sep or not object_id:
            return False
        if revision:
            return (
                conn.execute(
                    "SELECT 1 FROM objects WHERE object_id=? AND revision=? LIMIT 1",
                    (object_id, revision),
                ).fetchone()
                is not None
            )
        return (
            conn.execute(
                "SELECT 1 FROM objects WHERE object_id=? LIMIT 1", (object_id,)
            ).fetchone()
            is not None
        )


class SqliteTraceRepository:
    def __init__(self, db: SqliteDatabase):
        self.db = db

    def create_session(self, session_id: str) -> None:
        with self.db.session() as conn:
            conn.execute("INSERT OR IGNORE INTO sessions(session_id) VALUES (?)", (session_id,))

    def append(
        self,
        session_id: str,
        *,
        event_id: str,
        kind: str,
        payload: dict[str, Any],
        ts_ms: int,
        kernel_session_id: str | None = None,
    ) -> tuple[TraceRecord, bool]:
        self.create_session(session_id)
        with self._lock():
            with self.db.session() as conn:
                # The cursor is "max + 1"; without one writer holding the
                # database write lock two processes both choose the same
                # cursor and one hits the UNIQUE(session_id, cursor) index.
                conn.execute("BEGIN IMMEDIATE")
                existing = conn.execute(
                    "SELECT * FROM trace_events WHERE session_id=? AND event_id=?",
                    (session_id, event_id),
                ).fetchone()
                if existing:
                    if (
                        existing["kind"] != kind
                        or _canonical(_idempotency_payload(json.loads(existing["payload"])))
                        != _canonical(_idempotency_payload(payload))
                    ):
                        raise _version_conflict(
                            f"event_id {event_id} already exists with different content "
                            f"in session {session_id}"
                        )
                    return self._record(existing), True
                row = conn.execute(
                    "SELECT COALESCE(MAX(cursor),0) AS c FROM trace_events WHERE session_id=?",
                    (session_id,),
                ).fetchone()
                cursor = int(row["c"]) + 1
                row = conn.execute(
                    "SELECT COALESCE(MAX(seq),0) AS s FROM trace_events"
                ).fetchone()
                seq = int(row["s"]) + 1
                conn.execute(
                    "INSERT INTO trace_events"
                    "(session_id,kernel_session_id,event_id,cursor,seq,kind,payload,ts_ms) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        session_id,
                        kernel_session_id,
                        event_id,
                        cursor,
                        seq,
                        kind,
                        _canonical(payload),
                        ts_ms,
                    ),
                )
                inserted = conn.execute(
                    "SELECT * FROM trace_events WHERE session_id=? AND event_id=?",
                    (session_id, event_id),
                ).fetchone()
        return self._record(inserted), False

    def _lock(self):
        return self.db._lock

    @staticmethod
    def _record(row: sqlite3.Row) -> TraceRecord:
        return TraceRecord(
            session_id=row["session_id"],
            event_id=row["event_id"],
            cursor=int(row["cursor"]),
            kind=row["kind"],
            payload=json.loads(row["payload"]),
            ts_ms=int(row["ts_ms"]),
            seq=int(row["seq"]) if row["seq"] is not None else None,
        )

    def read_from(self, session_id: str, cursor: int = 1, limit: int = 100) -> list[TraceRecord]:
        """Read one session's stream in cursor order (``StoreContract`` semantics)."""

        with self.db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM trace_events WHERE session_id=? AND cursor>=? "
                "ORDER BY cursor, rowid LIMIT ?",
                (session_id, cursor, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def read_by_kernel_session(
        self, kernel_session_id: str, cursor: int = 1, limit: int = 100
    ) -> list[TraceRecord]:
        """Cross-task view paginated by the global ``seq``, not per-task cursor.

        Each task stream restarts its cursor at 1, so filtering a cross-session
        view by cursor would return page 1 from every task and then stop.
        ``cursor`` here is the next global ``seq`` (start with 1 and continue
        with ``records[-1].seq + 1``).
        """

        with self.db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM trace_events WHERE kernel_session_id=? AND seq>=? "
                "ORDER BY seq LIMIT ?",
                (kernel_session_id, cursor, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def get_event(self, session_id: str, event_id: str) -> TraceRecord | None:
        """Look up one event without reading the whole stream."""

        with self.db.session() as conn:
            row = conn.execute(
                "SELECT * FROM trace_events WHERE session_id=? AND event_id=?",
                (session_id, event_id),
            ).fetchone()
        return self._record(row) if row else None

    def _read_primary(
        self, session_id: str, cursor: int = 1, limit: int = 100
    ) -> list[TraceRecord]:
        with self.db.session() as conn:
            rows = conn.execute(
                "SELECT * FROM trace_events WHERE session_id=? AND cursor>=? "
                "ORDER BY cursor, rowid LIMIT ?",
                (session_id, cursor, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def last_cursor(self, session_id: str) -> int:
        with self.db.session() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(cursor),0) AS c FROM trace_events WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return int(row["c"])

    def checkpoint(self, session_id: str, kind_prefix: str = "") -> dict[str, Any]:
        records = [
            r
            for r in self._read_primary(session_id, 1, 1_000_000)
            if r.kind.startswith(kind_prefix)
        ]
        cursor = records[-1].cursor if records else 0
        body = "".join(_canonical({"event_id": r.event_id, "kind": r.kind, "payload": r.payload}) for r in records)
        digest = "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()
        checkpoint_id = "ckpt:" + hashlib.sha256(f"{session_id}:{kind_prefix}:{cursor}".encode()).hexdigest()[:16]
        with self.db.session() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO checkpoints(checkpoint_id,session_id,kind_prefix,cursor,digest) "
                "VALUES (?,?,?,?,?)",
                (checkpoint_id, session_id, kind_prefix, cursor, digest),
            )
        return {
            "checkpoint_id": checkpoint_id,
            "session_id": session_id,
            "kind_prefix": kind_prefix,
            "cursor": cursor,
            "digest": digest,
        }

    def verify_checkpoint(self, checkpoint: dict[str, Any]) -> bool:
        fresh = self.checkpoint(checkpoint["session_id"], checkpoint.get("kind_prefix", ""))
        return fresh["cursor"] == checkpoint["cursor"] and fresh["digest"] == checkpoint["digest"]
