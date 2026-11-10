"""Immutable revisions and transactional events/outbox in one SQLite database."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from ..ports.workbench_store import ChangeSet, CommitReceipt, VersionConflict


class SqliteWorkbenchStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS wb_records(
                    kind TEXT, id TEXT, scope TEXT, revision INTEGER, body TEXT NOT NULL,
                    PRIMARY KEY(kind,id,scope,revision));
                CREATE TABLE IF NOT EXISTS wb_events(
                    cursor INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT NOT NULL,
                    scope TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS wb_event_scope ON wb_events(scope,session,cursor);
                CREATE TABLE IF NOT EXISTS wb_outbox(
                    scope TEXT, request_key TEXT, payload TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'ready', PRIMARY KEY(scope,request_key));
            ''')

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _record(row):
        return None if row is None else {
            'kind': row['kind'], 'id': row['id'], 'scope': row['scope'],
            'revision': str(row['revision']), 'body': json.loads(row['body'])}

    def get(self, kind, id, revision, *, scope):
        with self._connection() as db:
            return self._record(db.execute('SELECT * FROM wb_records WHERE kind=? AND id=? AND scope=? AND revision=?',
                (kind, id, scope, revision)).fetchone())

    def current(self, kind, id, *, scope):
        with self._connection() as db:
            return self._record(db.execute('SELECT * FROM wb_records WHERE kind=? AND id=? AND scope=? ORDER BY revision DESC LIMIT 1',
                (kind, id, scope)).fetchone())

    def query(self, kind, scope, selector=None, cursor=0, limit=100):
        if not 0 <= cursor or not 1 <= limit <= 1000:
            raise ValueError('invalid pagination')
        with self._connection() as db:
            rows = db.execute('''SELECT r.* FROM wb_records r WHERE kind=? AND scope=?
                AND revision=(SELECT MAX(x.revision) FROM wb_records x
                    WHERE x.kind=r.kind AND x.id=r.id AND x.scope=r.scope) ORDER BY id''', (kind, scope)).fetchall()
        records = [self._record(r) for r in rows]
        selected = [r for r in records if all(r['body'].get(k) == v for k,v in (selector or {}).items())]
        return selected[cursor:cursor+limit]

    def events(self, session, after, *, scope, limit=100):
        if after < 0 or not 1 <= limit <= 1000:
            raise ValueError('invalid event cursor')
        with self._connection() as db:
            rows = db.execute('SELECT * FROM wb_events WHERE session=? AND scope=? AND cursor>? ORDER BY cursor LIMIT ?',
                (session, scope, after, limit+1)).fetchall()
        items = [{**json.loads(r['body']), 'cursor':r['cursor']} for r in rows[:limit]]
        return {'items':items, 'cursor': items[-1]['cursor'] if items else after, 'has_more':len(rows)>limit}

    def commit(self, change_set: ChangeSet):
        revisions = {}
        keys = [(w.kind,w.id,w.scope) for w in change_set.writes]
        if len(keys) != len(set(keys)):
            raise ValueError('duplicate writes in change set')
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                for w in change_set.writes:
                    row = db.execute('SELECT MAX(revision) FROM wb_records WHERE kind=? AND id=? AND scope=?',
                        (w.kind,w.id,w.scope)).fetchone()
                    actual = None if row[0] is None else str(row[0])
                    if actual != w.expected_revision:
                        raise VersionConflict(f'{w.kind}:{w.id}: expected {w.expected_revision}, current {actual}')
                    revision = int(actual or 0) + 1
                    db.execute('INSERT INTO wb_records VALUES(?,?,?,?,?)',
                        (w.kind,w.id,w.scope,revision,json.dumps(w.body,ensure_ascii=False,allow_nan=False)))
                    revisions[f'{w.kind}:{w.id}'] = str(revision)
                for e in change_set.events:
                    session = e['session_id']
                    scopes = db.execute("SELECT DISTINCT scope FROM wb_records WHERE kind='session' AND id=?",(session,)).fetchall()
                    requested_scope = e.get('scope')
                    matching = [r[0] for r in scopes if requested_scope is None or r[0] == requested_scope]
                    if len(matching) != 1:
                        raise ValueError('event requires an unambiguous existing session scope')
                    db.execute('INSERT INTO wb_events(session,scope,body) VALUES(?,?,?)',
                        (session,matching[0],json.dumps(e,ensure_ascii=False,allow_nan=False)))
                for item in change_set.outbox:
                    db.execute('INSERT INTO wb_outbox(scope,request_key,payload) VALUES(?,?,?)',
                        (item['scope'],item['request_key'],json.dumps(item['payload'],allow_nan=False)))
                cursor = db.execute('SELECT COALESCE(MAX(cursor),0) FROM wb_events').fetchone()[0]
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise VersionConflict('request already reserved') from exc
            except BaseException:
                db.rollback()
                raise
        return CommitReceipt(revisions,cursor)
