"""Human-gated publication of a completed discovery draft into an ontology.

The agent may complete a discovery draft into a multi-concept definition and
store it as a candidate.  Only the local web channel may confirm it: the
confirmation names the exact draft, the source snapshot digest and the
candidate definition digest, and every check is repeated server-side inside
one transaction.  A discovery task may instead name a published ontology as
its revision target: the candidate is then the next revision of that
ontology, the human sees the structural difference against the current
revision, and the same transaction registers the new revision, advances the
registry and pointer, and writes the publication audit.  Older revisions and
tasks pinned to them are never migrated or deleted.
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
    pointer_row, revision_record,
)
from dataagent_ontology.revisions import definition_diff
from dataagent_runtime.ports.workbench_store import ChangeSet, VersionConflict, Write
from .ontology_discovery import DISCOVERY_MODE, is_discovery
from .session_service import revision_target


CANDIDATE_KIND = 'ontology_candidate'
PUBLICATION_KIND = 'ontology_publication'
# The exact source files as first observed by a probe.  Publication compares
# against this record, never against a baseline captured at prepare time.
SOURCE_VERSION_KIND = 'source_version'

_SQLITE_SUFFIXES = (('', 'main'), ('-wal', 'wal'), ('-shm', 'shm'),
                    ('-journal', 'journal'))

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
    # A destructive revision (identity change, deleted property or concept)
    # needs a second, explicit acknowledgement that old published objects stay
    # on the old revision and are not migrated.
    acknowledge_no_migration: StrictBool = False


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


# A review writes a new draft revision whose proposal content is unchanged;
# only these fields describe where the review stands.  Candidate validity is
# bound to the proposal content and its lineage, never to a review-only
# revision, so approving a pending draft does not invalidate a candidate.
_REVIEW_FIELDS = frozenset({'ref', 'state', 'reviewed_draft_ref'})


def draft_content(draft):
    """The part of a draft a publication candidate is built from."""
    return {key: value for key, value in draft.items() if key not in _REVIEW_FIELDS}


def draft_content_digest(draft):
    return digest(draft_content(draft))


def draft_content_ref(draft):
    """The proposal a draft's content came from; stable across its review."""
    return draft.get('reviewed_draft_ref') or draft.get('ref')


def _session_content(session):
    """The parts of a task revision a candidate's content depends on.

    A review changes the task revision and the draft pointer; it changes
    neither the sources, their observation refs nor the task identity.
    """
    return {
        'goal_ref': session.goal_ref,
        'sources': [source.model_dump(mode='json') for source in session.sources],
        'extensions': session.extensions or {},
        'selected_versions': {
            key: value for key, value in session.selected_versions.items()
            if key != DISCOVERY_MODE},
    }


def _candidate_matches_draft(body, draft):
    """Whether a candidate was built from this draft's content and proposal."""
    return (body.get('draft_content_digest') == draft_content_digest(draft)
            and body.get('draft_content_ref') == draft_content_ref(draft))


def _digest_file(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def _source_state(workspace, source):
    """The exact bytes a published definition and mapping may rely on.

    A SQLite database is one logical file plus its journal, WAL and shared
    memory sidecars: uncheckpointed WAL frames are part of the observed state.
    File sources are digested directly.  The result is JSON-stable so it can
    be stored with the probe and compared byte-for-byte at prepare/confirm.
    """
    path = _inside((Path(workspace) / source.locator_ref).resolve(), Path(workspace))
    if not path.is_file():
        raise ValueError('source file is no longer readable; discover again')
    if source.kind == 'sqlite':
        files = {}
        for suffix, label in _SQLITE_SUFFIXES:
            sidecar = path if not suffix else path.with_name(path.name + suffix)
            files[label] = _digest_file(sidecar) if sidecar.is_file() else None
        return {'source_id': source.source_id, 'kind': source.kind,
                'locator_ref': source.locator_ref, 'files': files}
    return {'source_id': source.source_id, 'kind': source.kind,
            'locator_ref': source.locator_ref, 'digest': _digest_file(path)}


def record_source_versions(wb, session, source_id=None):
    """Pin a source's version when its profile is written.

    Called from ``_store_profile`` as each source finishes probing, before the
    next source runs.  ``source_id`` limits the write to that source; the same
    profile ref is never re-pinned, even when its capture was unreadable, so
    recovering a file without re-probing cannot unblock publication.
    """
    if session is None or not is_discovery(session):
        return
    previous = wb.store.current(SOURCE_VERSION_KIND, session.id, scope=wb.scope)
    previous_body = previous['body'] if previous is not None else {}
    recorded = dict((previous_body or {}).get('sources') or {})
    changed = False
    for source in session.sources:
        if source_id is not None and source.source_id != source_id:
            continue
        if source.kind not in {'file', 'sqlite'}:
            continue
        ref = session.selected_versions.get('profile:' + source.source_id)
        if not ref:
            continue
        entry = recorded.get(source.source_id)
        if isinstance(entry, dict) and entry.get('profile_ref') == ref:
            continue
        try:
            state = _source_state(wb.workspace, source)
        except (OSError, PermissionError, ValueError) as exc:
            state = {'source_id': source.source_id, 'kind': source.kind,
                     'locator_ref': source.locator_ref,
                     'unreadable': str(exc)[:200]}
        recorded[source.source_id] = {'profile_ref': ref, 'state': state}
        changed = True
    if not changed:
        return
    body = {'session_id': session.id, 'sources': recorded, 'observed_at': _now()}
    wb.store.commit(ChangeSet(writes=[Write(
        SOURCE_VERSION_KIND, session.id, wb.scope, body,
        previous['revision'] if previous is not None else None)]))


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


def _dropped_draft_items(draft, completed_ids, completed_columns,
                         concept_entities):
    """Draft-selected items the completion left out of the candidate.

    A completion may carry only some of the draft's properties and only some
    of its selected relationships.  Draft entities may not be omitted: the
    completeness gate below rejects that, so the ``concept`` branch here is
    defensive only and is not an accepted publication path.  The candidate
    summary lists every reachable difference so the publish page can show the
    human exactly which draft choices the published definition drops.
    Relationship references are the evidence ids the disposition gate already
    uses, so the page can pair a dropped relationship with its disposition.
    """
    dropped = []
    for link in draft.get('relationships') or []:
        evidence_id = link.get('id')
        if evidence_id in completed_ids:
            continue
        dropped.append({
            'kind': 'relationship', 'ref': str(evidence_id),
            'name': str(link.get('name') or ''),
            'source_table': str(link.get('source_table') or ''),
            'source_columns': list(link.get('source_columns') or []),
            'target_table': str(link.get('target_table') or ''),
            'target_columns': list(link.get('target_columns') or []),
            'cardinality': str(link.get('cardinality') or ''),
        })
    for entity in draft.get('entities') or []:
        name = str(entity.get('name') or '')
        if name not in concept_entities:
            dropped.append({
                'kind': 'concept', 'ref': name, 'name': name,
                'table': str(entity.get('table') or ''),
            })
            continue
        carried = completed_columns.get(name, set())
        for prop in entity.get('properties') or []:
            if prop.get('column') in carried:
                continue
            dropped.append({
                'kind': 'property', 'ref': '%s.%s' % (name, prop.get('name')),
                'concept': name, 'name': str(prop.get('name') or ''),
                'column': str(prop.get('column') or ''),
                'table': str(entity.get('table') or ''),
            })
    return dropped


def build_candidate(wb, draft, catalog, completion, *, revision='1'):
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
    completed_columns = {}
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
        # A table with no rows has columns and declared keys but no identity
        # sample; publishing it would promise a concept nobody has observed.
        rows_observed = table.get('rows_observed')
        if not isinstance(rows_observed, int) or rows_observed < 1:
            raise ValueError(
                'concept %r has no observed sample rows in the confirmed snapshot '
                '(table %r); discover again or exclude the table explicitly'
                % (spec.entity, table.get('name')))

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
            # Every attribute needs at least one non-null value in the exact
            # sample the human confirms; a column that is entirely empty has
            # no anchor to compare against.
            if (observed.get('distinct_values', 0) < 1
                    or observed.get('null_rows', 0) >= rows_observed):
                raise ValueError(
                    'property %r has no observed value in the confirmed snapshot '
                    '(table %r, column %r); discover again or exclude it explicitly'
                    % (name, table.get('name'), column))
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
        identity_columns = frozenset(spec.properties[field].column for field in identity)
        observed_keys = [frozenset(key) for key in table.get('identity_keys') or []]
        if identity_columns not in observed_keys:
            raise ValueError(
                'identity columns %r are not unique in the observed sample; observed keys: %r'
                % (sorted(identity_columns), [sorted(key) for key in observed_keys]))
        concepts[concept] = ConceptDefinition(entity_type=entity_type,
            properties=properties, identity_fields=identity)
        concept_tables[concept] = table['name']
        completed_columns[spec.entity] = used_columns
        evidence_concepts[concept] = {
            'entity': spec.entity, 'source_id': table['source_id'],
            'table': table['name'], 'grain': entity.get('grain') or '',
            'rows_observed': table.get('rows_observed'),
            'coverage': table.get('coverage'), 'identity_fields': identity,
            'identity_columns': sorted(identity_columns),
            'properties': anchors,
        }

    # Gate boundary: a published concept is never silently dropped from the
    # draft.  The diff's concept branch stays defensive for a future explicit
    # flow; today only properties and relationships can be left out.
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

    concept_entities = {info['entity']: concept
                        for concept, info in evidence_concepts.items()}
    dropped = _dropped_draft_items(draft, completed_ids, completed_columns,
                                   concept_entities)

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

    definition = OntologyRevision(id=completion.ontology_id, revision=revision,
        concepts=concepts, relations=relations)
    return {
        'definition': definition,
        'definition_digest': digest(definition.model_dump(mode='json')),
        'default_concept': next(iter(concepts)),
        'evidence': {'concepts': evidence_concepts,
                     'relations': evidence_relations,
                     'gaps': list(gaps), 'coverage': coverage,
                     'dispositions': dispositions, 'dropped': dropped},
        'dispositions': dispositions,
        'dropped': dropped,
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
        by_id = {profile.source_id: profile for profile in profiles}
        files = []
        for source in session.sources:
            if source.kind not in {'file', 'sqlite'}:
                continue
            try:
                state = _source_state(self.wb.workspace, source)
            except OSError:
                raise ValueError('source file is no longer readable; discover again') from None
            profile = by_id.get(source.source_id)
            if (source.kind == 'file' and profile is not None
                    and state['digest'] != profile.source_revision):
                raise ValueError('source changed since it was observed; discover again')
            files.append(state)
        return files

    def _verify_probe_sources(self, session):
        """Compare live sources with the per-source versions pinned at probe time.

        The recorded profile ref must still be the one selected on the session:
        a source that was re-probed has new evidence, so a candidate built from
        the old profile refs is stale even if the file happens to be unchanged.
        """
        sources = [source for source in session.sources
                   if source.kind in {'file', 'sqlite'}]
        if not sources:
            return
        row = self.wb.store.current(SOURCE_VERSION_KIND, session.id, scope=self.wb.scope)
        if row is None:
            raise ValueError('source observation version was not recorded; discover again')
        recorded = (row['body'] or {}).get('sources') or {}
        for source in sources:
            entry = recorded.get(source.source_id)
            expected = entry.get('state') if isinstance(entry, dict) else None
            if not isinstance(expected, dict) or expected.get('unreadable'):
                raise ValueError('source observation version is missing; discover again')
            ref = session.selected_versions.get('profile:' + source.source_id)
            if entry.get('profile_ref') != ref:
                raise ValueError('source observation changed; discover again')
            try:
                actual = _source_state(self.wb.workspace, source)
            except OSError:
                raise ValueError('source file is no longer readable; discover again') from None
            if actual != expected:
                raise ValueError('source changed since it was observed; discover again')

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
    def _revision_instance_outlook(self, ontology_id, previous, definition):
        """Instance counts per concept on the revision being replaced, and the
        concepts whose published objects stay behind on it (FDE3-01).

        A new revision is registered empty: every task keeps its own pinned
        revision, so the current revision's released objects are invisible to
        any query that defaults to the new one until the data is taken in
        again.  The confirmation page names those concepts instead of the old
        blanket「已发布实例不受影响」, which read as the data still being
        visible.
        """
        stats = self.wb.queries._stats()
        released = ((stats.get(ontology_id, {}).get('revisions') or {})
                    .get(previous.revision, {}).get('concepts') or {})
        names = list(definition.concepts) + [name for name in previous.concepts
                                             if name not in definition.concepts]
        counts = {name: int(released.get(name, 0)) for name in names}
        reintake = [name for name in definition.concepts
                    if counts.get(name, 0) > 0]
        return counts, reintake

    def _verify_revision_outlook(self, body, definition):
        """Recompute the candidate's released-instance outlook before publishing
        (FDE3-01 review).

        The confirmation page uses the outlook captured at prepare time to
        decide whether the new revision needs a re-intake acknowledgement.
        Another task can release objects into the current revision after that
        point; confirming the stale outlook would publish a revision whose
        objects the user was told are unaffected.  Any change in the counts or
        in the concepts needing re-intake requires a fresh candidate and a
        fresh human check.
        """
        previous_row = self.wb.store.get('ontology', body['ontology_id'],
                                         body['previous_revision'],
                                         scope=self.wb.scope)
        if previous_row is None:
            raise VersionConflict(
                'ontology revision changed; prepare the candidate again')
        previous = OntologyRevision.model_validate(previous_row['body'])
        counts, reintake = self._revision_instance_outlook(
            body['ontology_id'], previous, definition)
        recorded_counts = {}
        if isinstance(body.get('current_revision_instance_counts'), dict):
            for name, count in body['current_revision_instance_counts'].items():
                try:
                    recorded_counts[str(name)] = int(count)
                except (TypeError, ValueError):
                    recorded_counts[str(name)] = -1
        recorded_reintake = sorted(str(name) for name in
                                   (body.get('reintake_concepts') or []))
        if (recorded_counts != counts
                or recorded_reintake != sorted(reintake)):
            raise VersionConflict(
                'candidate is stale; published instances changed; '
                'prepare the candidate again')

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
        if (draft.get('ref') != completion.draft_ref
                and draft.get('reviewed_draft_ref') != completion.draft_ref):
            raise VersionConflict('discovery draft changed; complete the latest draft')
        if draft.get('state') == 'rejected':
            raise ValueError('rejected discovery drafts cannot be published')
        catalog = state['catalog']
        if draft.get('source_revision') != catalog.get('source_revision'):
            raise ValueError('source observation changed; discover again')

        target = revision_target(session)
        previous_definition = None
        entry = None
        entry_current = None
        if target is not None:
            # Revision publication: the exact ontology named at intake start is
            # the only one this task may amend, and the revision it pinned must
            # still be the current one.
            if completion.ontology_id != target.get('ontology_id'):
                raise ValueError(
                    'completion ontology_id must equal revise_ontology_id: %s'
                    % target.get('ontology_id'))
            entry_current = entry_row(wb.store, wb.scope, completion.ontology_id)
            entry = parse_entry(entry_current)
            if entry is None:
                raise ValueError('ontology not registered: %s' % completion.ontology_id)
            if entry.origin != 'discovery':
                raise ValueError('the builtin ontology cannot be revised: %s'
                                 % completion.ontology_id)
            if entry.state != 'active':
                raise ValueError('ontology is retired for new tasks: %s'
                                 % completion.ontology_id)
            if (entry.ontology_revision != target.get('base_revision')
                    or entry_current['revision'] != target.get('registry_revision')):
                raise VersionConflict('ontology revision changed; start discovery again')
            current_definition = wb.store.current('ontology', completion.ontology_id,
                                                  scope=wb.scope)
            if current_definition is None:
                raise ValueError('ontology not registered: %s' % completion.ontology_id)
            previous_definition = OntologyRevision.model_validate(
                current_definition['body'])
            next_revision = str(int(previous_definition.revision) + 1)
        else:
            if wb.store.current('ontology', completion.ontology_id, scope=wb.scope) is not None:
                raise ValueError('ontology id is already registered: %s' % completion.ontology_id)
            if entry_row(wb.store, wb.scope, completion.ontology_id) is not None:
                raise ValueError('ontology id is already registered: %s' % completion.ontology_id)
            next_revision = '1'

        self._verify_probe_sources(session)
        source_files = self._live_sources(session, profiles)
        snapshot_files = self._snapshot_files(profiles)
        candidate = build_candidate(wb, draft, catalog, completion,
                                    revision=next_revision)
        diff = {}
        destructive = False
        previous_revision = ''
        if previous_definition is not None:
            previous_revision = previous_definition.revision
            diff = definition_diff(previous_definition, candidate['definition'])
            destructive = diff['destructive']
        # FDE3-01: appended candidate fields.  The counts describe the
        # revision being replaced, never the candidate definition.
        instance_counts, reintake_concepts = ({}, [])
        if previous_definition is not None:
            instance_counts, reintake_concepts = self._revision_instance_outlook(
                completion.ontology_id, previous_definition,
                candidate['definition'])
        profile_refs = list(draft.get('profile_refs') or state.get('profile_refs') or [])
        source_snapshot = source_snapshot_digest(catalog, profile_refs)

        previous = wb.store.current(CANDIDATE_KIND, session.id, scope=wb.scope)
        revision = str(int(previous['revision']) + 1) if previous else '1'
        ref = '%s@%s' % (session.id, revision)
        body = {
            'ref': ref, 'session_id': session.id,
            'session_revision': session.revision,
            'session_content_digest': digest(_session_content(session)),
            'draft_ref': draft['ref'], 'draft_state': draft.get('state'),
            'draft_content_digest': draft_content_digest(draft),
            'draft_content_ref': draft_content_ref(draft),
            'source_revision': catalog.get('source_revision'),
            'structure_fingerprint': catalog.get('structure_fingerprint'),
            'profile_refs': profile_refs,
            'source_snapshot': source_snapshot,
            'source_files': source_files, 'snapshot_files': snapshot_files,
            'ontology_id': completion.ontology_id,
            'ontology_revision': candidate['definition'].revision,
            'previous_revision': previous_revision,
            'registry_revision': (entry_current['revision']
                                  if entry_current is not None else None),
            'revision_diff': diff,
            'destructive': destructive,
            'current_revision_instance_counts': instance_counts,
            'reintake_concepts': reintake_concepts,
            'title': (completion.title
                      or (entry.title if entry is not None else '')
                      or completion.ontology_id),
            'definition': candidate['definition'].model_dump(mode='json'),
            'definition_digest': candidate['definition_digest'],
            'default_concept': candidate['default_concept'],
            'evidence': candidate['evidence'],
            'dispositions': candidate['dispositions'],
            'dropped': candidate['dropped'],
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
            'previous_revision': body.get('previous_revision') or '',
            'revision_diff': body.get('revision_diff') or {},
            'destructive': bool(body.get('destructive')),
            'requires_no_migration_ack': bool(body.get('destructive')),
            'current_revision_instance_counts':
                dict(body.get('current_revision_instance_counts') or {}),
            'reintake_concepts': list(body.get('reintake_concepts') or []),
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
            'dropped': list(body.get('dropped') or []),
            'confirm_route': '/api/sessions/%s/publish/confirm' % body['session_id'],
            'instructions': ('打开工作台，核对来源快照摘要与候选定义摘要后由人确认发布；'
                             '草案审核是可选步骤，草案仍待审核时确认发布会在同一事务里'
                             '一并审核。MCP 工具不能代为确认。'),
        }

    def candidate(self, session_id, ctx):
        session = self.wb.sessions.get(session_id, ctx)
        row = self.wb.store.current(CANDIDATE_KIND, session_id, scope=self.wb.scope)
        if row is None:
            return None
        body = row['body']
        view = {**body, 'candidate_revision': row['revision']}
        # Reviewing the draft moves the draft pointer and the task revision but
        # keeps the proposal content.  Present the candidate against that
        # reviewed draft so the web page neither calls it stale nor confirms a
        # draft reference the task no longer points at.  The task content
        # digest is checked too: a source/profile change is already a stale
        # candidate even before the harder source checks run at confirmation.
        draft = self._selected_draft(session)
        if (body.get('state') == 'candidate' and draft is not None
                and _candidate_matches_draft(body, draft)
                and body.get('session_content_digest')
                == digest(_session_content(session))):
            view.update(draft_ref=draft['ref'], draft_state=draft.get('state'),
                        session_revision=session.revision)
        return view

    def _selected_draft(self, session):
        """The draft the task currently points at, without rebuilding evidence."""
        ref = session.selected_versions.get(DISCOVERY_MODE)
        if not ref:
            return None
        try:
            draft_id, revision = ref.rsplit('@', 1)
        except ValueError:
            return None
        row = self.wb.store.get(DISCOVERY_MODE, draft_id, revision,
                                scope=self.wb.scope)
        return row['body'] if row is not None else None

    # ---------------------------------------------------------------- confirm
    def confirm(self, session_id, confirmation, ctx):
        wb = self.wb
        if not confirmation.confirmed:
            raise ValueError('ontology publication requires explicit human confirmation')
        session = wb.sessions.get(session_id, ctx)
        if not is_discovery(session):
            raise ValueError('publication requires an ontology_discovery task')
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
        # A draft review moves the task revision without touching content.  A
        # confirmation built from the candidate's own task revision stays
        # valid; every content-bearing check below decides staleness.
        if confirmation.expected_revision not in {session.revision,
                                                  body.get('session_revision')}:
            raise VersionConflict('task changed; prepare the candidate again')
        if body.get('session_content_digest') != digest(_session_content(session)):
            raise VersionConflict('task content changed; prepare the candidate again')
        if body.get('source_snapshot') != confirmation.source_snapshot:
            raise VersionConflict('confirmation does not name the prepared source snapshot')
        if body.get('definition_digest') != confirmation.definition_digest:
            raise VersionConflict('confirmation does not name the prepared definition')

        profiles, state = self._state(session)
        draft = state.get('draft')
        if draft is None or not _candidate_matches_draft(body, draft):
            raise VersionConflict('discovery draft changed; prepare the candidate again')
        if draft.get('state') == 'rejected':
            raise ValueError('rejected discovery drafts cannot be published')
        if confirmation.draft_ref not in {body.get('draft_ref'), draft.get('ref')}:
            raise VersionConflict('confirmation does not name the prepared draft')
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
        self._verify_probe_sources(session)
        self._verify_sources(session, profiles, body)

        completion = PublishPrepare.model_validate(body['completion'])
        target = revision_target(session)
        is_revision = bool(body.get('previous_revision'))
        entry_current = None
        if is_revision:
            # The registry is the concurrency gate: a revision may only be
            # published against the exact registry row and current revision the
            # candidate was built from.  A second revision prepared from the
            # same base therefore loses here (or at the transactional write),
            # never by overwriting the first one.
            if target is None or target.get('ontology_id') != body['ontology_id']:
                raise ValueError('candidate is not a revision target of this task')
            entry_current = entry_row(wb.store, wb.scope, body['ontology_id'])
            registry_entry = parse_entry(entry_current)
            if registry_entry is None:
                raise ValueError('ontology not registered: %s' % body['ontology_id'])
            if registry_entry.origin != 'discovery':
                raise ValueError('the builtin ontology cannot be revised: %s'
                                 % body['ontology_id'])
            if registry_entry.state != 'active':
                raise ValueError('ontology is retired for new tasks: %s'
                                 % body['ontology_id'])
            if (registry_entry.ontology_revision != body['previous_revision']
                    or entry_current['revision'] != body.get('registry_revision')):
                raise VersionConflict(
                    'ontology revision changed; prepare the candidate again')
            if body.get('destructive') and not confirmation.acknowledge_no_migration:
                raise ValueError(
                    'destructive ontology revision requires acknowledging that '
                    'old data will not be migrated')
        rebuilt = build_candidate(wb, draft, catalog, completion,
                                  revision=body['ontology_revision'])
        if rebuilt['definition_digest'] != body['definition_digest']:
            raise VersionConflict('candidate definition changed; prepare it again')
        definition = rebuilt['definition']
        current_definition = wb.store.current('ontology', definition.id,
                                              scope=wb.scope)
        if is_revision:
            if definition.revision != str(int(registry_entry.ontology_revision) + 1):
                raise VersionConflict(
                    'ontology revision changed; prepare the candidate again')
            if current_definition is None:
                raise ValueError('ontology not registered: %s' % definition.id)
            definition_expected = current_definition['revision']
            registry_expected = entry_current['revision']
            # The candidate's re-intake outlook is a snapshot; release writes
            # made after prepare must force a new candidate (FDE3-01 review).
            self._verify_revision_outlook(body, definition)
        else:
            if current_definition is not None:
                raise ValueError('ontology id is already registered: %s' % definition.id)
            definition_expected = None
            registry_expected = None

        now = _now()
        writes = []
        events = []
        bundled_review = None
        approved_ref = draft['ref']
        if draft.get('state') == 'pending':
            # One human confirmation also approves the pending draft: the
            # publication transaction carries the review, so the user does not
            # have to approve the draft and then confirm the publication.
            draft_row = wb.store.current(DISCOVERY_MODE, session.id, scope=wb.scope)
            if draft_row is None or draft_row['body'].get('ref') != draft['ref']:
                raise VersionConflict('discovery draft changed; prepare it again')
            approved_ref = '%s@%s' % (session.id, int(draft_row['revision']) + 1)
            approved = {**draft, 'ref': approved_ref, 'state': 'approved',
                        'reviewed_draft_ref': draft['ref']}
            updated_session = session.model_dump(mode='json')
            updated_session.update({
                'revision': str(int(session.revision) + 1),
                'phase': 'saved', 'next_actions': [],
                'selected_versions': {**session.selected_versions,
                                      DISCOVERY_MODE: approved_ref},
            })
            bundled_review = {
                'decision': 'approve', 'target_scope': 'discovery',
                'draft_ref': draft['ref'], 'approved_draft_ref': approved_ref,
                'via': 'publish_confirmation',
                'note': '随发布确认一并审核',
                'subject_ref': ctx.subject_ref, 'recorded_at': now,
                'reason': confirmation.reason,
            }
            writes.extend([
                Write(DISCOVERY_MODE, session.id, wb.scope, approved,
                      draft_row['revision']),
                Write('session', session.id, wb.scope, updated_session,
                      session.revision),
                Write('review', uuid4().hex, wb.scope, bundled_review),
            ])
            job = wb.store.current('job', session.job_ref, scope=wb.scope)
            if job is not None:
                writes.append(Write('job', session.job_ref, wb.scope, {
                    **job['body'], 'state': 'completed', 'checkpoint': 'approved',
                    'result_ref': approved_ref,
                }, job['revision']))
            events.append({
                'session_id': session.id, 'scope': wb.scope,
                'type': 'intake.updated', 'phase': 'saved',
                'revision': updated_session['revision'],
            })
        diff = body.get('revision_diff') or {}
        previous_revision = body.get('previous_revision') or ''
        if is_revision:
            record = revision_record(definition, published_at=now,
                published_by=ctx.subject_ref,
                source_snapshot=body['source_snapshot'],
                definition_digest=body['definition_digest'],
                previous_revision=previous_revision, diff=diff,
                destructive=bool(body.get('destructive')))
            history = list(registry_entry.revisions or [])
            if not history:
                # A workspace published before revision history existed still
                # gets its first revision listed, from the entry and the
                # definition that entry names.
                previous_row = wb.store.get('ontology', definition.id,
                                            previous_revision, scope=wb.scope)
                if previous_row is not None:
                    history.append(revision_record(
                        OntologyRevision.model_validate(previous_row['body']),
                        published_at=registry_entry.published_at,
                        published_by=registry_entry.published_by,
                        source_snapshot=registry_entry.source_snapshot))
            history.append(record)
            default_concept = (registry_entry.default_concept
                               if registry_entry.default_concept in definition.concepts
                               else next(iter(definition.concepts)))
            entry = registry_entry.model_copy(update={
                'ontology_revision': definition.revision,
                'title': body['title'],
                'concepts': list(definition.concepts),
                'default_concept': default_concept,
                'source_snapshot': body['source_snapshot'],
                'published_by': ctx.subject_ref,
                'published_at': now,
                'revisions': history,
            })
        else:
            entry = build_entry(definition, origin='discovery', title=body['title'],
                source_snapshot=body['source_snapshot'], published_by=ctx.subject_ref,
                published_at=now, definition_digest=body['definition_digest'])
        pointer = pointer_row(wb.store, wb.scope)
        publication_extensions = None
        if bundled_review is not None:
            publication_extensions = {'dataagent.draft_review': {
                'decision': 'approve', 'via': 'publish_confirmation',
                'draft_ref': draft['ref'], 'approved_draft_ref': approved_ref,
                'note': '随发布确认一并审核',
            }}
        publication = OntologyPublication(action='publish', ontology_id=definition.id,
            ontology_revision=definition.revision,
            definition_digest=body['definition_digest'],
            source_snapshot=body['source_snapshot'], draft_ref=body['draft_ref'],
            subject_ref=ctx.subject_ref, recorded_at=now, reason=confirmation.reason,
            previous_revision=previous_revision, diff=diff,
            extensions=publication_extensions)
        publication_id = uuid4().hex
        updated = {**body, 'state': 'published', 'publication_ref': publication_id,
                   'confirmed_at': now, 'confirmed_by': ctx.subject_ref,
                   'confirmed_draft_ref': draft['ref']}
        publish_audit = {
            'decision': 'publish', 'target_scope': 'ontology',
            'ontology_id': definition.id, 'candidate_ref': body['ref'],
            'draft_ref': body['draft_ref'],
            'source_snapshot': body['source_snapshot'],
            'definition_digest': body['definition_digest'],
            'previous_revision': previous_revision,
            'revision_diff': diff,
            'destructive': bool(body.get('destructive')),
            'subject_ref': ctx.subject_ref, 'recorded_at': now,
            'reason': confirmation.reason,
        }
        if is_revision:
            publish_audit['acknowledge_no_migration'] = bool(
                confirmation.acknowledge_no_migration)
        if bundled_review is not None:
            publish_audit['draft_review'] = bundled_review
        writes.extend([
            Write('ontology', definition.id, wb.scope,
                  definition.model_dump(mode='json'), definition_expected),
            Write(REGISTRY_KIND, definition.id, wb.scope,
                  entry.model_dump(mode='json'), registry_expected),
            Write(POINTER_KIND, POINTER_ID, wb.scope, {
                'ontology_id': definition.id, 'concept': entry.default_concept,
                'updated_at': now, 'updated_by': ctx.subject_ref,
            }, pointer['revision'] if pointer is not None else None),
            Write(PUBLICATION_KIND, publication_id, wb.scope,
                  publication.model_dump(mode='json')),
            Write('review', uuid4().hex, wb.scope, publish_audit),
            Write(CANDIDATE_KIND, session.id, wb.scope, updated, candidate_revision),
        ])
        wb.store.commit(ChangeSet(writes=writes, events=[*events, {
            'session_id': session.id, 'scope': wb.scope,
            'type': 'ontology.published', 'ontology_id': definition.id,
            'revision': definition.revision,
        }]))
        return {
            'state': 'published', 'ontology_id': definition.id,
            'ontology_revision': definition.revision,
            'previous_revision': previous_revision,
            'revision_diff': diff,
            'destructive': bool(body.get('destructive')),
            'definition_digest': body['definition_digest'],
            'source_snapshot': body['source_snapshot'],
            'draft_ref': body['draft_ref'], 'candidate_ref': body['ref'],
            'confirmed_draft_ref': draft['ref'],
            'approved_draft_ref': approved_ref,
            'draft_review': ('approved_with_publish_confirmation'
                             if bundled_review is not None else 'already_approved'),
            'confirmed_by': ctx.subject_ref, 'confirmed_at': now,
            'publication_ref': publication_id,
            'default_concept': entry.default_concept,
            'registry': entry.model_dump(mode='json'),
        }
