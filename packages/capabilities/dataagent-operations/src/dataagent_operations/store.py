"""SQLite control state, wait observations, and the shared action outbox."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from dataagent_contracts.workflow import ActionRecord, WaitRecord, WorkflowRun

from .bindings import encode


class AuthorityRevoked(ValueError):
    pass


class LeaseLost(ValueError):
    pass


class OperationsStore:
    def __init__(self, path, scope, authorization):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.scope = scope
        self.authorization = authorization
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ops_records (
                    scope TEXT, authorization TEXT, kind TEXT, id TEXT, body TEXT NOT NULL,
                    PRIMARY KEY(scope, authorization, kind, id));
                CREATE TABLE IF NOT EXISTS ops_grants (
                    scope TEXT, authorization TEXT, revoked INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(scope, authorization));
                CREATE TABLE IF NOT EXISTS ops_leases (
                    run_id TEXT PRIMARY KEY, token TEXT NOT NULL, expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS ops_actions (
                    id TEXT PRIMARY KEY, body TEXT NOT NULL, arguments TEXT NOT NULL,
                    response TEXT, owner_run TEXT, owner_token TEXT);
                CREATE TABLE IF NOT EXISTS ops_run_actions (
                    run_id TEXT, step_id TEXT, action_id TEXT NOT NULL,
                    PRIMARY KEY(run_id, step_id));
                CREATE TABLE IF NOT EXISTS ops_waits (
                    run_id TEXT, step_id TEXT, body TEXT NOT NULL,
                    PRIMARY KEY(run_id, step_id));
            """)
            db.execute("INSERT OR IGNORE INTO ops_grants(scope, authorization) VALUES (?, ?)",
                       (scope, authorization))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, db, kind, key, model):
        row = db.execute(
            "SELECT body FROM ops_records WHERE scope=? AND authorization=? AND kind=? AND id=?",
            (self.scope, self.authorization, kind, key),
        ).fetchone()
        if not row:
            raise ValueError(f"{kind} {key!r} was not found in the current scope")
        return model.model_validate_json(row["body"])

    def put(self, db, kind, value):
        db.execute(
            """INSERT INTO ops_records VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(scope, authorization, kind, id) DO UPDATE SET body=excluded.body""",
            (self.scope, self.authorization, kind, value.id, value.model_dump_json()),
        )

    def run(self, db, run_id):
        return self.get(db, "run", run_id, WorkflowRun)

    def update_run(self, db, run):
        run.revision += 1
        self.put(db, "run", run)

    def authorized(self, db):
        return not db.execute(
            "SELECT revoked FROM ops_grants WHERE scope=? AND authorization=?", (self.scope, self.authorization),
        ).fetchone()[0]

    def revoke(self, db):
        db.execute("UPDATE ops_grants SET revoked=1 WHERE scope=? AND authorization=?",
                   (self.scope, self.authorization))

    def claim(self, db, run_id, lease_seconds):
        self.run(db, run_id)
        now = time.time()
        token = uuid4().hex
        cur = db.execute(
            """INSERT INTO ops_leases VALUES (?, ?, ?) ON CONFLICT(run_id) DO UPDATE
               SET token=excluded.token, expires_at=excluded.expires_at WHERE ops_leases.expires_at<=?""",
            (run_id, token, now + lease_seconds, now),
        )
        return token if cur.rowcount else None

    def current_lease(self, db, run_id):
        return db.execute("SELECT token FROM ops_leases WHERE run_id=? AND expires_at>?",
                          (run_id, time.time())).fetchone()

    def check_lease(self, db, run_id, token):
        row = self.current_lease(db, run_id)
        if row is None or row["token"] != token:
            raise LeaseLost("workflow lease expired or was replaced")

    def renew(self, db, run_id, token, lease_seconds):
        self.check_lease(db, run_id, token)
        db.execute("UPDATE ops_leases SET expires_at=? WHERE run_id=?", (time.time() + lease_seconds, run_id))

    @staticmethod
    def release(db, run_id, token):
        db.execute("DELETE FROM ops_leases WHERE run_id=? AND token=?", (run_id, token))

    @staticmethod
    def action(db, action_id):
        row = db.execute("SELECT * FROM ops_actions WHERE id=?", (action_id,)).fetchone()
        if row is None:
            return None
        return ActionRecord.model_validate_json(row["body"]), json.loads(row["arguments"]), json.loads(row["response"] or "null")

    @staticmethod
    def linked_action(db, run_id, step_id):
        row = db.execute("SELECT action_id FROM ops_run_actions WHERE run_id=? AND step_id=?",
                         (run_id, step_id)).fetchone()
        return row["action_id"] if row else None

    def reserve(self, db, run, step_id, action, arguments):
        linked = self.linked_action(db, run.id, step_id)
        if linked and linked != action.id:
            raise ValueError("step already has a different reserved business action")
        prior = self.action(db, action.id)
        if prior and prior[0].parameters_digest != action.parameters_digest:
            raise ValueError("business action key has already been reserved with different parameters")
        if prior is None:
            db.execute("INSERT INTO ops_actions(id, body, arguments) VALUES (?, ?, ?)",
                       (action.id, action.model_dump_json(), encode(arguments)))
        db.execute("INSERT OR IGNORE INTO ops_run_actions VALUES (?, ?, ?)",
                   (run.id, step_id, action.id))
        return prior[0] if prior else action

    @staticmethod
    def set_dispatch_owner(db, action_id, run_id=None, token=None):
        db.execute("UPDATE ops_actions SET owner_run=?, owner_token=? WHERE id=?", (run_id, token, action_id))

    @staticmethod
    def dispatch_owner(db, action_id):
        return db.execute("SELECT owner_run, owner_token FROM ops_actions WHERE id=?", (action_id,)).fetchone()

    def dispatch_pending(self, db, action_id):
        row = self.dispatch_owner(db, action_id)
        if row["owner_run"] is None:
            return False
        owner = self.current_lease(db, row["owner_run"])
        return owner is not None and owner["token"] == row["owner_token"]

    @staticmethod
    def save_action(db, action, response=None):
        db.execute("UPDATE ops_actions SET body=?, response=COALESCE(?, response) WHERE id=?",
                   (action.model_dump_json(), encode(response) if response is not None else None, action.id))

    @staticmethod
    def actions(db, run_id):
        rows = db.execute(
            """SELECT a.body FROM ops_run_actions r JOIN ops_actions a ON r.action_id=a.id
               WHERE r.run_id=? ORDER BY r.rowid""", (run_id,),
        ).fetchall()
        return [ActionRecord.model_validate_json(row["body"]) for row in rows]

    @staticmethod
    def put_wait(db, wait):
        db.execute(
            """INSERT INTO ops_waits VALUES (?, ?, ?) ON CONFLICT(run_id, step_id)
               DO UPDATE SET body=excluded.body""", (wait.run_id, wait.step_id, wait.model_dump_json()),
        )

    @staticmethod
    def waits(db, run_id):
        rows = db.execute("SELECT body FROM ops_waits WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
        return [WaitRecord.model_validate_json(row["body"]) for row in rows]
