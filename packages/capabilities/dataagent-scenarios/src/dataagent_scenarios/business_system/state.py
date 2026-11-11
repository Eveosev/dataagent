"""Transactional SQLite business state shared by public API, GUI and evaluator."""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid

from fastapi import HTTPException
from pydantic import ValidationError

from .schemas import data_model, domain_config

NATIVE = {'draft': 'DRAFT', 'submitted': 'SUBMITTED', 'waiting_approval': 'AWAITING_REVIEW',
          'approved': 'APPROVED', 'rejected': 'REJECTED'}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class BusinessState:
    def __init__(self, path, config=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, domain TEXT NOT NULL, business_key TEXT NOT NULL,
                    data TEXT NOT NULL, initial_digest TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, approval_due REAL,
                    approval_outcome TEXT, UNIQUE(domain,business_key));
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, record_id TEXT NOT NULL,
                    status TEXT NOT NULL, occurred_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (
                    request_key TEXT PRIMARY KEY, record_id TEXT NOT NULL, digest TEXT NOT NULL,
                    response TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY, record_id TEXT NOT NULL, filename TEXT NOT NULL,
                    content_type TEXT NOT NULL, body BLOB NOT NULL, request_key TEXT UNIQUE,
                    digest TEXT NOT NULL);
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('config', json.dumps(domain_config(config))))
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('faults', '{}'))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def config(self):
        with self.transaction() as db:
            return json.loads(db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])

    def domain(self, name):
        found = self.config()['domains'].get(name)
        if found is None:
            raise HTTPException(404, 'Unknown business domain')
        return found

    def _row(self, db, domain, record_id):
        row = db.execute('SELECT * FROM records WHERE id=? AND domain=?', (record_id, domain)).fetchone()
        if row is None:
            raise HTTPException(404, 'Record not found')
        return row

    def _event(self, db, record_id, status):
        now = timestamp()
        db.execute('UPDATE records SET status=?,updated_at=? WHERE id=?', (status, now, record_id))
        db.execute('INSERT INTO events(record_id,status,occurred_at) VALUES(?,?,?)', (record_id, status, now))

    def _approvals(self, db):
        for row in db.execute("SELECT * FROM records WHERE status='waiting_approval' AND approval_due<=?", (time.time(),)).fetchall():
            self._event(db, row['id'], row['approval_outcome'])

    def _record(self, db, row):
        result = {key: row[key] for key in ('id', 'domain', 'business_key', 'status', 'created_at', 'updated_at')}
        result.update(data=json.loads(row['data']), native_status=NATIVE[row['status']], observed_at=timestamp())
        result['attachments'] = [self._attachment(a) for a in db.execute('SELECT * FROM attachments WHERE record_id=? ORDER BY rowid', (row['id'],))]
        return result

    def _attachment(self, row):
        return {'id': row['id'], 'filename': row['filename'], 'content_type': row['content_type'],
                'size': len(row['body']), 'sha256': hashlib.sha256(row['body']).hexdigest(),
                'download_url': f"/api/attachments/{row['id']}"}

    def validate(self, domain, data, partial=False):
        try:
            return data_model('Fields', self.domain(domain), partial=partial).model_validate(data).model_dump(mode='json', exclude_unset=True)
        except ValidationError as exc:
            raise HTTPException(422, json.loads(exc.json())) from exc

    def create(self, domain, business_key, data):
        data = self.validate(domain, data)
        initial = digest(data)
        with self.transaction() as db:
            row = db.execute('SELECT * FROM records WHERE domain=? AND business_key=?', (domain, business_key)).fetchone()
            if row:
                if row['initial_digest'] != initial:
                    raise HTTPException(409, 'Business key already exists with different original fields')
                return self._record(db, row)
            record_id = uuid.uuid4().hex
            now = timestamp()
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (record_id, domain, business_key, json.dumps(data), initial, 'draft', now, now, None, None))
            self._event(db, record_id, 'draft')
            return self._record(db, self._row(db, domain, record_id))

    def get(self, domain, record_id):
        self.domain(domain)
        with self.transaction() as db:
            self._approvals(db)
            return self._record(db, self._row(db, domain, record_id))

    def records(self, domain, business_key=None, offset=0, limit=None):
        config = self.domain(domain)
        with self.transaction() as db:
            self._approvals(db)
            rows = db.execute('SELECT * FROM records WHERE domain=? AND (? IS NULL OR business_key=?) ORDER BY rowid',
                              (domain, business_key, business_key)).fetchall()
            limit = min(limit or config['page_size'], 100)
            page = rows[offset:offset + limit]
            more = offset + limit < len(rows)
            return {config['collection_field']: [self._record(db, row) for row in page], 'total': len(rows),
                    'has_more': more, 'next_cursor': str(offset + limit) if more else None,
                    'next_offset': offset + limit if more else None, 'observed_at': timestamp()}

    def patch(self, domain, record_id, data):
        data = self.validate(domain, data, partial=True)
        with self.transaction() as db:
            row = self._row(db, domain, record_id)
            if row['status'] != 'draft':
                raise HTTPException(409, 'Only drafts may be edited')
            merged = {**json.loads(row['data']), **data}
            db.execute('UPDATE records SET data=?,updated_at=? WHERE id=?', (json.dumps(merged), timestamp(), record_id))
            return self._record(db, self._row(db, domain, record_id))

    def attach(self, domain, record_id, payload):
        try:
            body = base64.b64decode(payload['content_base64'], validate=True)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, 'Invalid base64 attachment') from exc
        fingerprint = digest(payload)
        with self.transaction() as db:
            row = self._row(db, domain, record_id)
            existing = db.execute('SELECT * FROM attachments WHERE request_key=?', (payload['request_key'],)).fetchone()
            if existing:
                if existing['record_id'] != record_id or existing['digest'] != fingerprint:
                    raise HTTPException(409, 'Attachment request key conflict')
                return self._attachment(existing)
            if row['status'] != 'draft':
                raise HTTPException(409, 'Only drafts accept attachments')
            aid = uuid.uuid4().hex
            db.execute('INSERT INTO attachments VALUES(?,?,?,?,?,?,?)', (aid, record_id, payload['filename'],
                       payload['content_type'], body, payload['request_key'], fingerprint))
            return self._attachment(db.execute('SELECT * FROM attachments WHERE id=?', (aid,)).fetchone())

    def attachment(self, attachment_id):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM attachments WHERE id=?', (attachment_id,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Attachment not found')
            return dict(row)

    def submit(self, domain, record_id, request_key):
        config = self.domain(domain)
        fingerprint = digest({'domain': domain, 'record_id': record_id, 'action': 'submit'})
        with self.transaction() as db:
            row = self._row(db, domain, record_id)
            prior = db.execute('SELECT * FROM requests WHERE request_key=?', (request_key,)).fetchone()
            if prior:
                if prior['digest'] != fingerprint:
                    raise HTTPException(409, 'Submission request key conflict')
                return json.loads(prior['response']), None
            if row['status'] == 'draft':
                try:
                    data_model('Fields', config).model_validate(json.loads(row['data']))
                except ValidationError as exc:
                    raise HTTPException(422, json.loads(exc.json())) from exc
                if config['require_attachment'] and not db.execute('SELECT 1 FROM attachments WHERE record_id=?', (record_id,)).fetchone():
                    raise HTTPException(422, 'Evidence attachment is required')
                self._event(db, record_id, 'submitted')
                self._event(db, record_id, 'waiting_approval')
                delay = config['approval_delay_seconds']
                db.execute('UPDATE records SET approval_due=?,approval_outcome=? WHERE id=?',
                           (time.time() + delay if delay is not None else None, config['approval_outcome'], record_id))
            result = self._record(db, self._row(db, domain, record_id))
            db.execute('INSERT INTO requests VALUES(?,?,?,?)', (request_key, record_id, fingerprint, json.dumps(result)))
            faults = json.loads(db.execute("SELECT value FROM settings WHERE key='faults'").fetchone()[0])
            lost = faults.pop('lose_next_submit_response', False)
            db.execute("UPDATE settings SET value=? WHERE key='faults'", (json.dumps(faults),))
            return result, faults.get('response_delay_seconds', 2) if lost else None

    def events(self, domain, record_id, after=0):
        with self.transaction() as db:
            self._row(db, domain, record_id)
            self._approvals(db)
            rows = db.execute('SELECT * FROM events WHERE record_id=? AND sequence>? ORDER BY sequence LIMIT 101', (record_id, after)).fetchall()
            items = [dict(row) | {'native_status': NATIVE[row['status']]} for row in rows[:100]]
            return {'items': items, 'cursor': items[-1]['sequence'] if items else after, 'has_more': len(rows) > 100}

    def change_config(self, change):
        with self.transaction() as db:
            config = json.loads(db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])
            domain = config['domains'].get(change['domain'])
            if domain is None:
                raise HTTPException(404, 'Unknown domain')
            change = dict(change)
            change.pop('domain')
            field = change.pop('required_field', None)
            if field:
                domain['fields'] = [f for f in domain['fields'] if f['name'] != field['name']] + [field | {'required': True}]
            domain.update(change)
            db.execute("UPDATE settings SET value=? WHERE key='config'", (json.dumps(config),))
            return {'changed': True}

    def faults(self, payload):
        with self.transaction() as db:
            db.execute("UPDATE settings SET value=? WHERE key='faults'", (json.dumps(payload),))
            return {'configured': True}

    def approve(self, domain, record_id, outcome):
        with self.transaction() as db:
            row = self._row(db, domain, record_id)
            if row['status'] != 'waiting_approval':
                raise HTTPException(409, 'Record is not waiting for approval')
            self._event(db, record_id, outcome)
            return self._record(db, self._row(db, domain, record_id))
