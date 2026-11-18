"""Session, goal and real job creation in one local transaction."""
from pathlib import Path
from uuid import uuid4
from dataagent_contracts.intake import IntakeSession, JobHandle, EventPage
from dataagent_contracts.ontology import OntologyRevision
from dataagent_ontology.registry import entry_row, parse_entry
from dataagent_runtime.ports.workbench_store import Write, ChangeSet, VersionConflict
from .ontology_discovery import DISCOVERY_MODE, MODE_EXTENSION


DISCOVERY_FILE_SUFFIXES = {'.csv', '.tsv', '.json', '.jsonl', '.xlsx', '.xlsm'}
DISCOVERY_DOCUMENT_SUFFIXES = {'.pdf', '.docx'}
DISCOVERY_SOURCE_KINDS = {'sqlite', 'rest'}

# The mapping target pinned on a task: {ontology_id, revision, concept}.
TARGET_EXTENSION = 'dataagent.mapping_target'
# The revision target of a discovery task: {ontology_id, base_revision,
# registry_revision}.  A discovery task that names one may only publish a new
# revision of that ontology; an unset value publishes a new ontology.
REVISION_EXTENSION = 'dataagent.revision_target'


def mapping_target(session):
    """The mapping target pinned on one task, or None when it was never set."""
    return (session.extensions or {}).get(TARGET_EXTENSION) or None


def revision_target(session):
    """The published ontology a discovery task intends to revise, if any."""
    return (session.extensions or {}).get(REVISION_EXTENSION) or None


def _check_discovery_source(source):
    """Discovery accepts table-shaped and document (docx, PDF) sources."""
    if source.kind in DISCOVERY_SOURCE_KINDS:
        return
    if source.kind == 'file':
        suffix = Path(source.locator_ref).suffix.lower()
        if suffix in DISCOVERY_FILE_SUFFIXES | DISCOVERY_DOCUMENT_SUFFIXES:
            return
    raise ValueError(
        'ontology discovery supports CSV, TSV, Excel, JSON/JSONL, REST, SQLite '
        'and document (docx, PDF) sources')


class SessionService:
    def __init__(self, store, scope, subject, authorization, *, default_target=None):
        # ``default_target`` returns the builtin definition used when a task
        # does not name one; it is read at start time so a host that swaps the
        # builtin (and registers the new revision) pins the current one.
        self.store, self.scope = store, scope
        self.subject, self.authorization = subject, authorization
        self.default_target = default_target

    def check(self, ctx):
        if (ctx.scope_ref,ctx.subject_ref,ctx.authorization_ref) != (self.scope,self.subject,self.authorization):
            raise PermissionError('context does not match trusted local workspace owner')

    def _pin_target(self, target):
        """Resolve a {ontology_id, concept} request to the registered revision."""
        if hasattr(target, 'model_dump'):
            target = target.model_dump(mode='json')
        if not isinstance(target, dict) or not target.get('ontology_id'):
            raise ValueError('mapping target needs ontology_id')
        ontology_id = target['ontology_id']
        row = self.store.current('ontology', ontology_id, scope=self.scope)
        if row is None:
            raise ValueError(f'unknown ontology: {ontology_id}')
        # A retired definition stays readable for old tasks but may not be
        # chosen for a new one.
        entry = parse_entry(entry_row(self.store, self.scope, ontology_id))
        if entry is not None and entry.state != 'active':
            raise ValueError(f'ontology is retired for new tasks: {ontology_id}')
        ontology = OntologyRevision.model_validate(row['body'])
        try:
            name, _ = ontology.resolve_concept(target.get('concept') or '')
        except KeyError as exc:
            raise ValueError(f'unknown concept in ontology {ontology_id}: '
                             f'{target.get("concept")}') from exc
        return {'ontology_id': ontology_id, 'revision': row['revision'], 'concept': name}

    def _pin_revision_target(self, ontology_id):
        """Resolve a discovery task's revision target to the revision it amends.

        Only an ontology published from this workspace's discovery flow can be
        revised: the builtin is the workspace fallback and its revision belongs
        to the host, and a retired ontology is closed for new work.  The task
        pins both the definition revision and the registry row so a revision
        published while this task is open makes the candidate stale instead of
        silently merging two changes.
        """
        entry_row_ = entry_row(self.store, self.scope, ontology_id)
        entry = parse_entry(entry_row_)
        if entry is None:
            raise ValueError(f'unknown ontology: {ontology_id}')
        if entry.origin != 'discovery':
            raise ValueError(
                f'the builtin ontology cannot be revised: {ontology_id}')
        if entry.state != 'active':
            raise ValueError(f'ontology is retired for new tasks: {ontology_id}')
        row = self.store.current('ontology', ontology_id, scope=self.scope)
        if row is None:
            raise ValueError(f'unknown ontology: {ontology_id}')
        definition = OntologyRevision.model_validate(row['body'])
        return {'ontology_id': ontology_id,
                'base_revision': definition.revision,
                'registry_revision': entry_row_['revision']}

    def start(self, sources, goal, ctx, *, mode="mapping", target=None,
              revise_ontology_id=None):
        self.check(ctx)
        if goal.authorization_ref != self.authorization:
            raise PermissionError('goal authorization is not the host authorization')
        if not sources or len({s.source_id for s in sources}) != len(sources):
            raise ValueError('sources must have distinct identifiers')
        if mode not in ('mapping', DISCOVERY_MODE):
            raise ValueError('unknown intake mode')
        if revise_ontology_id is not None and mode != DISCOVERY_MODE:
            raise ValueError('revise_ontology_id requires ontology_discovery mode')
        if revise_ontology_id is not None and target is not None:
            raise ValueError('name either revise_ontology_id or target, not both')
        pinned = None
        revision = None
        if mode == DISCOVERY_MODE:
            # The agent tool exposes ``revise_ontology_id``; the HTTP start
            # route carries the same choice as ``target`` because it shares the
            # tool input contract.  A discovery target therefore names the
            # ontology to revise, never a mapping target.
            if target is not None:
                if hasattr(target, 'model_dump'):
                    target = target.model_dump(mode='json')
                if not isinstance(target, dict) or target.get('concept'):
                    raise ValueError(
                        'discovery intake does not fix a mapping target')
                revise_ontology_id = target.get('ontology_id')
            if revise_ontology_id is not None:
                revision = self._pin_revision_target(revise_ontology_id)
            for source in sources:
                _check_discovery_source(source)
        elif target is not None:
            pinned = self._pin_target(target)
        elif self.default_target is not None:
            builtin = self.default_target()
            if builtin is not None:
                pinned = self._pin_target({'ontology_id': builtin.id,
                                           'concept': builtin.resolve_concept()[0]})
        sid, jid, gid = uuid4().hex, uuid4().hex, uuid4().hex
        extensions = {}
        if mode == DISCOVERY_MODE:
            extensions[MODE_EXTENSION] = mode
        if revision:
            extensions[REVISION_EXTENSION] = revision
        if pinned:
            extensions[TARGET_EXTENSION] = pinned
        session = IntakeSession(id=sid,revision='1',goal_ref=gid+'@1',sources=sources,
            job_ref=jid,next_actions=['probe'],
            extensions=extensions or None)
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
