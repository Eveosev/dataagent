"""Human-gated publication of a completed discovery draft into a new ontology.

The agent may complete a discovery draft into a multi-concept definition and
store it as a candidate.  Only the local web channel may confirm it: the
confirmation names the exact draft, the source snapshot digest and the
candidate definition digest, and every check is repeated server-side inside
one transaction.  M1 publishes a definition once; changing an existing
definition stays in P2.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from dataagent_contracts.ontology import (
    ConceptDefinition, OntologyPublication, OntologyRevision, PropertyDefinition,
    RelationDefinition,
)
from dataagent_ontology.identity import digest
from dataagent_ontology.registry import (
    POINTER_ID, POINTER_KIND, REGISTRY_KIND, build_entry, entry_row, parse_entry,
    pointer_row,
)
from dataagent_runtime.ports.workbench_store import ChangeSet, VersionConflict, Write
from .ontology_discovery import is_discovery


CANDIDATE_KIND = 'ontology_candidate'
PUBLICATION_KIND = 'ontology_publication'

PropertyType = Literal['string', 'decimal', 'integer', 'boolean', 'date', 'datetime']

# A completion may not promise a type the observed column cannot satisfy.
_TYPE_AFFINITIES = {
    'string': frozenset({'text', 'integer', 'real', 'numeric', 'boolean'}),
    'decimal': frozenset({'integer', 'real', 'numeric'}),
    'integer': frozenset({'integer'}),
    'boolean': frozenset({'boolean'}),
    'date': frozenset({'text'}),
    'datetime': frozenset({'text'}),
}


class _Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PropertyCompletion(_Input):
    """One formal property backed by an observed column."""
    column: str = Field(min_length=1, description='证据列：目录里本表已观察到的列')
    value_type: PropertyType
    required: bool = False
    description: str = ''


class ConceptCompletion(_Input):
    """One draft entity completed into a publishable concept."""
    entity: str = Field(min_length=1, description='草案里的实体名（EntityProposal.name）')
    concept: str | None = Field(default=None, description='概念名；缺省用实体名')
    entity_type: str | None = Field(default=None, description='实体类型；缺省用概念名')
    properties: dict[str, PropertyCompletion] = Field(min_length=1)
    identity_fields: list[str] = Field(min_length=1,
        description='身份字段，必须在 properties 里且在样本中无空值、唯一')


class RelationCompletion(_Input):
    """One selected relationship with explicit endpoints, direction and roles."""
    evidence_id: str
    name: str = Field(default='', description='关系名；缺省用草案里的关系名')
    subject_concept: str = Field(min_length=1, description='起点概念（证据的 source_table）')
    object_concept: str = Field(min_length=1, description='终点概念（证据的 target_table）')
    roles: list[str] = Field(min_length=2, max_length=2,
        description='按 [起点, 终点] 顺序的两个角色名')


class Disposition(_Input):
    """An explicit exclude/accept decision for an open item or coverage gap."""
    kind: Literal['unresolved_table', 'unresolved_relationship', 'coverage_gap', 'coverage']
    ref: str = Field(min_length=1)
    action: Literal['exclude', 'accept']
    reason: str = Field(min_length=1)


class PublishPrepare(_Input):
    session_id: str
    expected_revision: str
    draft_ref: str
    ontology_id: str = Field(min_length=2, max_length=64,
        pattern=r'^[a-z][a-z0-9-]*[a-z0-9]$')
    title: str = ''
    concepts: list[ConceptCompletion] = Field(min_length=1, max_length=100)
    relations: list[RelationCompletion] = Field(default_factory=list, max_length=300)
    dispositions: list[Disposition] = Field(default_factory=list, max_length=2000)
    reason: str = ''


class PublishConfirmation(_Input):
    """The exact facts a human confirms in the web channel."""
    candidate_ref: str
    draft_ref: str
    source_snapshot: str
    definition_digest: str
    expected_revision: str
    confirmed: StrictBool
    reason: str = ''


class PublishConfirm(PublishConfirmation):
    """MCP/CLI shape: the session id travels with the confirmation request."""
    session_id: str


class RetireRequest(_Input):
    reason: str = Field(min_length=1)
    expected_revision: str | None = Field(default=None,
        description='当前注册表修订；传入时过期请求被拒绝')
    confirmed: StrictBool


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digest_file(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(path, workspace):
    try:
        path.relative_to(workspace)
    except ValueError:
        raise PermissionError('source path is outside the workspace') from None
    return path


def _gap_reference(gap, index):
    """Stable, human-quotable reference for one catalog coverage gap."""
    if isinstance(gap, dict) and gap.get('ref'):
        return str(gap['ref'])
    return 'gap:%d' % index


def _table_index(catalog):
    return {table['name']: table for table in catalog.get('tables') or []}


def _check_property_name(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('property names must not be blank')
    if name != name.strip():
        raise ValueError('property names must not have surrounding whitespace: %r' % name)
    if len(name) > 120:
        raise ValueError('property name is too long: %r' % name[:40])


def _allowed_columns(allowlist, source_id):
    if allowlist is None:
        return None
    if isinstance(allowlist, dict):
        return set(allowlist.get(source_id, []))
    return set(allowlist)


def build_candidate(wb, draft, catalog, completion):
    """Validate a completion against its draft and catalog; return the definition.

    Every annotation comes from the server-side evidence: a concept names an
    observed table, a property names an observed column inside the disclosure
    scope, a relation names a selected relationship evidence id and its
    direction must match the evidence.  Missing identity, unsatisfiable types,
    fabricated fields and unhandled open items raise ``ValueError``.
    """
    tables = _table_index(catalog)
    entities = {}
    for entity in draft.get('entities') or []:
        name = entity.get('name')
        if not name or name in entities:
            raise ValueError('discovery draft has duplicate or unnamed entities')
        entities[name] = entity

    allowlist = wb.allowed_model_fields
    concepts = {}
    evidence_concepts = {}
    concept_tables = {}
    entity_types = set()

    seen_entities = set()
    for spec in completion.concepts:
        if spec.entity in seen_entities:
            raise ValueError('draft entity completed twice: %s' % spec.entity)
        seen_entities.add(spec.entity)
        entity = entities.get(spec.entity)
        if entity is None:
            raise ValueError('completion names an entity outside the draft: %s' % spec.entity)
        table = tables.get(entity.get('table'))
        if table is None:
            raise ValueError('draft entity has no observed table: %s' % spec.entity)

        concept = (spec.concept or entity.get('name') or '').strip()
        if not concept:
            raise ValueError('concept names must not be blank: %s' % spec.entity)
        if concept in concepts:
            raise ValueError('duplicate concept name: %s' % concept)
        entity_type = (spec.entity_type or concept).strip()
        if entity_type in entity_types:
            raise ValueError('entity type %r is used by two concepts' % entity_type)
        entity_types.add(entity_type)

        allowed = _allowed_columns(allowlist, table['source_id'])
        properties = {}
        anchors = {}
        used_columns = set()
        for name, prop in spec.properties.items():
            _check_property_name(name)
            column = prop.column
            observed = (table.get('columns') or {}).get(column)
            if observed is None:
                raise ValueError(
                    'property %r references an unobserved column %r (no evidence)'
                    % (name, column))
            if allowed is not None and column not in allowed:
                raise ValueError(
                    'property %r uses a column outside the disclosed scope: %s'
                    % (name, column))
            if column in used_columns:
                raise ValueError('one observed column backs two properties: %s' % column)
            used_columns.add(column)
            affinity = observed.get('affinity') or 'unknown'
            if affinity not in _TYPE_AFFINITIES[prop.value_type]:
                raise ValueError(
                    'property %r value type %s cannot be satisfied by observed column %r '
                    '(%s)' % (name, prop.value_type, column, affinity))
            if prop.required and observed.get('blank_rows', 0):
                raise ValueError(
                    'required property %r has blank values in the observed sample'
                    % name)
            properties[name] = PropertyDefinition(value_type=prop.value_type,
                required=prop.required, description=prop.description)
            anchors[name] = {
                'source_id': table['source_id'], 'table': table['name'],
                'column': column, 'value_type': prop.value_type,
                'required': prop.required, 'affinity': affinity,
                'blank_rows': observed.get('blank_rows', 0),
                'null_rows': observed.get('null_rows', 0),
                'distinct_values': observed.get('distinct_values', 0),
            }

        identity = list(spec.identity_fields)
        if len(set(identity)) != len(identity):
            raise ValueError('duplicate identity fields on %s' % concept)
        missing = [field for field in identity if field not in properties]
        if missing:
            raise ValueError('identity fields must also be properties: %s'
                             % ','.join(missing))
        for field in identity:
            column = spec.properties[field].column
            observed = (table.get('columns') or {}).get(column) or {}
            if observed.get('blank_rows', 0):
                raise ValueError('identity field %r has blank values in the observed sample'
                                 % field)
            if observed.get('null_rows', 0):
                raise ValueError('identity field %r has null values in the observed sample'
                                 % field)
        observed_keys = [frozenset(key) for key in table.get('identity_keys') or []]
        if frozenset(identity) not in observed_keys:
            raise ValueError(
                'identity fields %r are not unique in the observed sample; observed keys: %r'
                % (identity, [sorted(key) for key in observed_keys]))
        concepts[concept] = ConceptDefinition(entity_type=entity_type,
            properties=properties, identity_fields=identity)
        concept_tables[concept] = table['name']
        evidence_concepts[concept] = {
            'entity': spec.entity, 'source_id': table['source_id'],
            'table': table['name'], 'grain': entity.get('grain') or '',
            'rows_observed': table.get('rows_observed'),
            'coverage': table.get('coverage'), 'identity_fields': identity,
            'properties': anchors,
        }

    missing_entities = sorted(set(entities) - seen_entities)
    if missing_entities:
        raise ValueError('every draft entity must be completed: %s'
                         % ','.join(missing_entities))

    relations = {}
    evidence_relations = {}
    selected = {item.get('id'): item for item in draft.get('relationships') or []}
    completed_ids = set()
    for spec in completion.relations:
        if spec.evidence_id in completed_ids:
            raise ValueError('relationship completed twice: %s' % spec.evidence_id)
        completed_ids.add(spec.evidence_id)
        link = selected.get(spec.evidence_id)
        if link is None:
            raise ValueError('relationship has no selected evidence: %s' % spec.evidence_id)
        subject = spec.subject_concept
        obj = spec.object_concept
        for concept in (subject, obj):
            if concept not in concepts:
                raise ValueError('relationship endpoint is not a completed concept: %s' % concept)
        if concept_tables[subject] != link.get('source_table'):
            raise ValueError('relation %s subject must be the evidence source concept'
                             % spec.evidence_id)
        if concept_tables[obj] != link.get('target_table'):
            raise ValueError('relation %s object must be the evidence target concept'
                             % spec.evidence_id)
        roles = list(spec.roles)
        if len(roles) != 2 or len(set(roles)) != 2 or any(not role.strip() for role in roles):
            raise ValueError('a relation needs two distinct, non-blank ordered roles')
        name = (spec.name or link.get('name') or '').strip()
        if not name:
            raise ValueError('relation names must not be blank: %s' % spec.evidence_id)
        if name in relations:
            raise ValueError('duplicate relation name: %s' % name)
        relations[name] = RelationDefinition(roles=roles, subject_concept=subject,
            object_concept=obj)
        evidence_relations[name] = {
            'evidence_id': spec.evidence_id,
            'source_id': link.get('source_id'), 'source_table': link.get('source_table'),
            'source_columns': link.get('source_columns'),
            'target_table': link.get('target_table'),
            'target_columns': link.get('target_columns'),
            'matched_rows': link.get('matched_rows'),
            'checked_rows': link.get('checked_rows'),
            'ambiguous': link.get('ambiguous', False),
            'subject_concept': subject, 'object_concept': obj, 'roles': roles,
        }

    # Every selected relationship the completion drops, and every open item the
    # draft already knew about, must be excluded or accepted explicitly.
    required = []
    for name in draft.get('unresolved_tables') or []:
        required.append(('unresolved_table', str(name)))
    for link in draft.get('unresolved_relationships') or []:
        required.append(('unresolved_relationship', str(link.get('id'))))
    gaps = draft.get('gaps')
    if gaps is None:
        gaps = catalog.get('gaps') or []
    for index, gap in enumerate(gaps, 1):
        required.append(('coverage_gap', _gap_reference(gap, index)))
    coverage = draft.get('coverage') or catalog.get('coverage') or 'unknown'
    if coverage != 'full':
        required.append(('coverage', coverage))
    for evidence_id in selected:
        if evidence_id not in completed_ids:
            required.append(('unresolved_relationship', str(evidence_id)))

    given = {}
    for item in completion.dispositions:
        key = (item.kind, item.ref)
        if key in given:
            raise ValueError('duplicate disposition: %s' % (item.ref,))
        if key not in required:
            raise ValueError('disposition does not match an open item: %s %s'
                             % (item.kind, item.ref))
        given[key] = item
    missing = [key for key in required if key not in given]
    if missing:
        raise ValueError(
            'open items and coverage gaps must be excluded or accepted before '
            'publication: %s' % ', '.join('%s:%s' % key for key in missing))
    dispositions = [item.model_dump(mode='json') for item in completion.dispositions]

    definition = OntologyRevision(id=completion.ontology_id, revision='1',
        concepts=concepts, relations=relations)
    return {
        'definition': definition,
        'definition_digest': digest(definition.model_dump(mode='json')),
        'default_concept': next(iter(concepts)),
        'evidence': {'concepts': evidence_concepts,
                     'relations': evidence_relations,
                     'gaps': list(gaps), 'coverage': coverage,
                     'dispositions': dispositions},
        'dispositions': dispositions,
    }


def source_snapshot_digest(catalog, profile_refs):
    """What the human confirms about the source: revision, refs and structure."""
    return digest([catalog.get('source_revision'), sorted(profile_refs),
                   catalog.get('structure_fingerprint')])


class PublishService:
    def __init__(self, wb):
        self.wb = wb

    # ---------------------------------------------------------------- evidence
    def _state(self, session):
        profiles = self.wb.intake._profiles(session)
        state = self.wb.discovery.state(session, profiles)
        if state is None or state.get('catalog') is None:
            raise ValueError('ontology discovery has no source evidence to publish')
        return profiles, state

    def _snapshot_files(self, profiles):
        workspace = self.wb.workspace.resolve()
        files = []
        for profile in profiles:
            pages = profile.metadata.get('pages')
            if isinstance(pages, list) and pages:
                for page in pages:
                    ref = page.get('snapshot_ref')
                    revision = page.get('response_revision')
                    if not ref or not revision:
                        raise ValueError('source snapshot reference is missing; discover again')
                    path = _inside((workspace / ref).resolve(), workspace)
                    actual = _digest_file(path)
                    if actual != revision:
                        raise ValueError('source snapshot changed; discover again')
                    files.append({'source_id': profile.source_id,
                                  'snapshot_ref': ref, 'digest': actual,
                                  'page': page.get('number')})
                continue
            ref = profile.metadata.get('snapshot_ref')
            if not ref:
                raise ValueError('source snapshot reference is missing; discover again')
            path = _inside((workspace / ref).resolve(), workspace)
            actual = _digest_file(path)
            if actual != profile.source_revision:
                raise ValueError('source snapshot changed; discover again')
            files.append({'source_id': profile.source_id,
                          'snapshot_ref': ref, 'digest': actual})
        return files

    def _live_sources(self, session, profiles):
        workspace = self.wb.workspace.resolve()
        by_id = {profile.source_id: profile for profile in profiles}
        files = []
        for source in session.sources:
            if source.kind not in {'file', 'sqlite'}:
                continue
            path = _inside((workspace / source.locator_ref).resolve(), workspace)
            if not path.is_file():
                raise ValueError('source file is no longer readable; discover again')
            actual = _digest_file(path)
            profile = by_id.get(source.source_id)
            if (source.kind == 'file' and profile is not None
                    and actual != profile.source_revision):
                raise ValueError('source changed since it was observed; discover again')
            files.append({'source_id': source.source_id,
                          'locator_ref': source.locator_ref, 'digest': actual})
        return files

    def _verify_sources(self, session, profiles, body):
        if body.get('profile_refs'):
            current = [session.selected_versions.get('profile:' + profile.source_id)
                       for profile in profiles]
            current = [ref for ref in current if ref]
            if sorted(current) != sorted(body['profile_refs']):
                raise ValueError('source observation changed; discover again')
        if self._snapshot_files(profiles) != body.get('snapshot_files'):
            raise ValueError('source snapshot changed; discover again')
        if self._live_sources(session, profiles) != body.get('source_files'):
            raise ValueError('source changed since it was observed; discover again')

    # ---------------------------------------------------------------- prepare
    def prepare(self, completion, ctx):
        wb = self.wb
        session = wb.sessions.get(completion.session_id, ctx)
        if not is_discovery(session):
            raise ValueError('publication requires an ontology_discovery task')
        if session.revision != completion.expected_revision:
            raise VersionConflict('discovery session changed; reload inputs')
        profiles, state = self._state(session)
        draft = state.get('draft')
        if draft is None:
            raise ValueError('submit a discovery draft before completing it')
        if draft.get('ref') != completion.draft_ref:
            raise VersionConflict('discovery draft changed; complete the latest draft')
        if draft.get('state') == 'rejected':
            raise ValueError('rejected discovery drafts cannot be published')
        catalog = state['catalog']
        if draft.get('source_revision') != catalog.get('source_revision'):
            raise ValueError('source observation changed; discover again')

        if wb.store.current('ontology', completion.ontology_id, scope=wb.scope) is not None:
            raise ValueError('ontology id is already registered: %s' % completion.ontology_id)
        if entry_row(wb.store, wb.scope, completion.ontology_id) is not None:
            raise ValueError('ontology id is already registered: %s' % completion.ontology_id)

        source_files = self._live_sources(session, profiles)
        snapshot_files = self._snapshot_files(profiles)
        candidate = build_candidate(wb, draft, catalog, completion)
        profile_refs = list(draft.get('profile_refs') or state.get('profile_refs') or [])
        source_snapshot = source_snapshot_digest(catalog, profile_refs)

        previous = wb.store.current(CANDIDATE_KIND, session.id, scope=wb.scope)
        revision = str(int(previous['revision']) + 1) if previous else '1'
        ref = '%s@%s' % (session.id, revision)
        body = {
            'ref': ref, 'session_id': session.id,
            'session_revision': session.revision,
            'draft_ref': draft['ref'], 'draft_state': draft.get('state'),
            'source_revision': catalog.get('source_revision'),
            'structure_fingerprint': catalog.get('structure_fingerprint'),
            'profile_refs': profile_refs,
            'source_snapshot': source_snapshot,
            'source_files': source_files, 'snapshot_files': snapshot_files,
            'ontology_id': completion.ontology_id, 'ontology_revision': '1',
            'title': completion.title or completion.ontology_id,
            'definition': candidate['definition'].model_dump(mode='json'),
            'definition_digest': candidate['definition_digest'],
            'default_concept': candidate['default_concept'],
            'evidence': candidate['evidence'],
            'dispositions': candidate['dispositions'],
            'completion': completion.model_dump(mode='json'),
            'state': 'candidate', 'created_at': _now(), 'created_by': ctx.subject_ref,
        }
        wb.store.commit(ChangeSet(writes=[Write(CANDIDATE_KIND, session.id, wb.scope,
            body, previous['revision'] if previous else None)]))
        return self._summary(body)

    def _summary(self, body):
        return {
            'candidate_ref': body['ref'],
            'state': 'awaiting_human_confirmation',
            'human_confirmation_required': True,
            'ontology_id': body['ontology_id'],
            'ontology_revision': body['ontology_revision'],
            'title': body['title'],
            'default_concept': body['default_concept'],
            'concept_names': list((body['definition'].get('concepts') or {}).keys()),
            'relations': list((body['definition'].get('relations') or {}).keys()),
            'definition': body['definition'],
            'definition_digest': body['definition_digest'],
            'draft_ref': body['draft_ref'],
            'source_revision': body['source_revision'],
            'source_snapshot': body['source_snapshot'],
            'profile_refs': list(body.get('profile_refs') or []),
            'structure_fingerprint': body.get('structure_fingerprint', ''),
            'session_revision': body['session_revision'],
            'dispositions': body['dispositions'],
            'confirm_route': '/api/sessions/%s/publish/confirm' % body['session_id'],
            'instructions': ('打开工作台，核对草案修订、来源快照摘要与候选定义摘要后，'
                             '由人确认发布；MCP 工具不能代为确认。'),
        }

    def candidate(self, session_id, ctx):
        self.wb.sessions.get(session_id, ctx)
        row = self.wb.store.current(CANDIDATE_KIND, session_id, scope=self.wb.scope)
        if row is None:
            return None
        return {**row['body'], 'candidate_revision': row['revision']}

    # ---------------------------------------------------------------- confirm
    def confirm(self, session_id, confirmation, ctx):
        wb = self.wb
        if not confirmation.confirmed:
            raise ValueError('ontology publication requires explicit human confirmation')
        session = wb.sessions.get(session_id, ctx)
        if not is_discovery(session):
            raise ValueError('publication requires an ontology_discovery task')
        if session.revision != confirmation.expected_revision:
            raise VersionConflict('task changed; prepare the candidate again')
        try:
            candidate_id, candidate_revision = confirmation.candidate_ref.rsplit('@', 1)
        except ValueError:
            raise ValueError('candidate ref must be id@revision') from None
        if candidate_id != session.id:
            raise ValueError('candidate belongs to another task')
        row = wb.store.get(CANDIDATE_KIND, candidate_id, candidate_revision, scope=wb.scope)
        if row is None:
            raise KeyError('publication candidate not found')
        body = row['body']
        if body.get('state') == 'published':
            raise VersionConflict('candidate was already published')
        current = wb.store.current(CANDIDATE_KIND, session.id, scope=wb.scope)
        if current is None or current['revision'] != candidate_revision:
            if (current is not None
                    and current['body'].get('state') == 'published'
                    and current['body'].get('ref') == confirmation.candidate_ref):
                raise VersionConflict('candidate was already published')
            raise VersionConflict('candidate is stale; prepare it again')
        if body.get('session_revision') != session.revision:
            raise VersionConflict('candidate is stale; prepare it again')
        if body.get('draft_ref') != confirmation.draft_ref:
            raise VersionConflict('confirmation does not name the prepared draft')
        if body.get('source_snapshot') != confirmation.source_snapshot:
            raise VersionConflict('confirmation does not name the prepared source snapshot')
        if body.get('definition_digest') != confirmation.definition_digest:
            raise VersionConflict('confirmation does not name the prepared definition')

        profiles, state = self._state(session)
        draft = state.get('draft')
        if draft is None or draft.get('ref') != body['draft_ref']:
            raise VersionConflict('discovery draft changed; prepare the candidate again')
        if draft.get('state') == 'rejected':
            raise ValueError('rejected discovery drafts cannot be published')
        catalog = state['catalog']
        if catalog.get('source_revision') != body.get('source_revision'):
            raise ValueError('source changed since it was observed; discover again')
        if catalog.get('structure_fingerprint') != body.get('structure_fingerprint'):
            raise ValueError('source structure changed; discover again')
        profile_refs = list(draft.get('profile_refs') or state.get('profile_refs') or [])
        if sorted(profile_refs) != sorted(body.get('profile_refs') or []):
            raise ValueError('source observation changed; discover again')
        if source_snapshot_digest(catalog, profile_refs) != body['source_snapshot']:
            raise ValueError('source snapshot changed; discover again')
        self._verify_sources(session, profiles, body)

        completion = PublishPrepare.model_validate(body['completion'])
        rebuilt = build_candidate(wb, draft, catalog, completion)
        if rebuilt['definition_digest'] != body['definition_digest']:
            raise VersionConflict('candidate definition changed; prepare it again')
        definition = rebuilt['definition']
        if wb.store.current('ontology', definition.id, scope=wb.scope) is not None:
            raise ValueError('ontology id is already registered: %s' % definition.id)

        now = _now()
        entry = build_entry(definition, origin='discovery', title=body['title'],
            source_snapshot=body['source_snapshot'], published_by=ctx.subject_ref,
            published_at=now)
        pointer = pointer_row(wb.store, wb.scope)
        publication = OntologyPublication(action='publish', ontology_id=definition.id,
            ontology_revision=definition.revision,
            definition_digest=body['definition_digest'],
            source_snapshot=body['source_snapshot'], draft_ref=body['draft_ref'],
            subject_ref=ctx.subject_ref, recorded_at=now, reason=confirmation.reason)
        publication_id = uuid4().hex
        updated = {**body, 'state': 'published', 'publication_ref': publication_id,
                   'confirmed_at': now, 'confirmed_by': ctx.subject_ref}
        writes = [
            Write('ontology', definition.id, wb.scope,
                  definition.model_dump(mode='json')),
            Write(REGISTRY_KIND, definition.id, wb.scope,
                  entry.model_dump(mode='json')),
            Write(POINTER_KIND, POINTER_ID, wb.scope, {
                'ontology_id': definition.id, 'concept': entry.default_concept,
                'updated_at': now, 'updated_by': ctx.subject_ref,
            }, pointer['revision'] if pointer is not None else None),
            Write(PUBLICATION_KIND, publication_id, wb.scope,
                  publication.model_dump(mode='json')),
            Write('review', uuid4().hex, wb.scope, {
                'decision': 'publish', 'target_scope': 'ontology',
                'ontology_id': definition.id, 'candidate_ref': body['ref'],
                'draft_ref': body['draft_ref'],
                'source_snapshot': body['source_snapshot'],
                'definition_digest': body['definition_digest'],
                'subject_ref': ctx.subject_ref, 'recorded_at': now,
                'reason': confirmation.reason,
            }),
            Write(CANDIDATE_KIND, session.id, wb.scope, updated, candidate_revision),
        ]
        wb.store.commit(ChangeSet(writes=writes, events=[{
            'session_id': session.id, 'scope': wb.scope,
            'type': 'ontology.published', 'ontology_id': definition.id,
            'revision': definition.revision,
        }]))
        return {
            'state': 'published', 'ontology_id': definition.id,
            'ontology_revision': definition.revision,
            'definition_digest': body['definition_digest'],
            'source_snapshot': body['source_snapshot'],
            'draft_ref': body['draft_ref'], 'candidate_ref': body['ref'],
            'confirmed_by': ctx.subject_ref, 'confirmed_at': now,
            'publication_ref': publication_id,
            'default_concept': entry.default_concept,
            'registry': entry.model_dump(mode='json'),
        }
