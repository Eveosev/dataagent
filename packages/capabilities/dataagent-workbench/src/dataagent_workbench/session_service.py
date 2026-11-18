"""Session, goal and real job creation in one local transaction."""
from pathlib import Path
from uuid import uuid4
from dataagent_contracts.intake import IntakeSession, JobHandle, EventPage
from dataagent_runtime.ports.workbench_store import Write, ChangeSet, VersionConflict
from .ontology_discovery import DISCOVERY_MODE, MODE_EXTENSION


DISCOVERY_FILE_SUFFIXES = {'.csv', '.tsv', '.json', '.jsonl', '.xlsx', '.xlsm'}
DISCOVERY_DOCUMENT_SUFFIXES = {'.pdf', '.docx'}
DISCOVERY_SOURCE_KINDS = {'sqlite', 'rest'}


def _check_discovery_source(source):
    """Discovery accepts table-shaped sources; documents wait for D2b."""
    if source.kind in DISCOVERY_SOURCE_KINDS:
        return
    if source.kind == 'file':
        suffix = Path(source.locator_ref).suffix.lower()
        if suffix in DISCOVERY_DOCUMENT_SUFFIXES:
            raise ValueError(
                f'ontology discovery does not support document sources yet '
                f'({source.source_id}); wait for D2b')
        if suffix in DISCOVERY_FILE_SUFFIXES:
            return
    raise ValueError(
        'ontology discovery supports CSV, TSV, Excel, JSON/JSONL, REST and SQLite '
        'sources')


class SessionService:
    def __init__(self, store, scope, subject, authorization):
        self.store, self.scope = store, scope
        self.subject, self.authorization = subject, authorization

    def check(self, ctx):
        if (ctx.scope_ref,ctx.subject_ref,ctx.authorization_ref) != (self.scope,self.subject,self.authorization):
            raise PermissionError('context does not match trusted local workspace owner')

    def start(self, sources, goal, ctx, *, mode="mapping"):
        self.check(ctx)
        if goal.authorization_ref != self.authorization:
            raise PermissionError('goal authorization is not the host authorization')
        if not sources or len({s.source_id for s in sources}) != len(sources):
            raise ValueError('sources must have distinct identifiers')
        if mode not in ('mapping', DISCOVERY_MODE):
            raise ValueError('unknown intake mode')
        if mode == DISCOVERY_MODE:
            for source in sources:
                _check_discovery_source(source)
        sid, jid, gid = uuid4().hex, uuid4().hex, uuid4().hex
        session = IntakeSession(id=sid,revision='1',goal_ref=gid+'@1',sources=sources,
            job_ref=jid,next_actions=['probe'],
            extensions={MODE_EXTENSION: mode} if mode == DISCOVERY_MODE else None)
        self.store.commit(ChangeSet(writes=[
            Write('goal',gid,self.scope,goal.model_copy(update={'id':gid}).model_dump(mode='json')),
            Write('session',sid,self.scope,session.model_dump(mode='json')),
            Write('job',jid,self.scope,{'id':jid,'session_id':sid,'state':'queued','checkpoint':''})],
            events=[{'session_id':sid,'scope':self.scope,'type':'intake.created'}]))
        return JobHandle(session_id=sid,job_ref=jid,revision='1')

    def get(self, session_id, ctx):
        self.check(ctx)
        record = self.store.current('session',session_id,scope=self.scope)
        if record is None:
            raise KeyError('session not found')
        return IntakeSession.model_validate({**record['body'],'revision':record['revision']})

    def events(self, session_id, after, ctx):
        self.get(session_id,ctx)
        return EventPage.model_validate(self.store.events(session_id,after,scope=self.scope))

    def update(self, session_id, expected_revision, changes, ctx, *, extra_writes=()):
        session = self.get(session_id,ctx)
        if session.phase == 'saved':
            raise VersionConflict('saved intake is closed; start a new intake to revise its mapping')
        body = session.model_dump(mode='json')
        if set(changes) - {'phase','selected_versions','issues','next_actions'}:
            raise ValueError('immutable session identity or source selection')
        body.update(changes)
        body['revision'] = str(int(expected_revision)+1)
        updated = IntakeSession.model_validate(body)
        self.store.commit(ChangeSet(writes=[Write('session',session_id,self.scope,
            updated.model_dump(mode='json'),expected_revision),*extra_writes],events=[{
            'session_id':session_id,'scope':self.scope,'type':'intake.updated',
            'phase':updated.phase,'revision':updated.revision}]))
        return updated
