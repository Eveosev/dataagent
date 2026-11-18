"""The workspace ontology registry: builtin, discovery-published and retired.

A registered definition stays immutable in the ``ontology`` revision store.
The registry adds the facts readers must not guess: where a definition came
from, whether it may be chosen for new tasks, and which concept a task pins
when it does not name one.  Retiring an entry never deletes definitions or
released instances; it only stops new tasks from defaulting to it.
"""
from pathlib import Path

from dataagent_contracts.ontology import OntologyRegistryEntry, OntologyRevision


REGISTRY_KIND = 'ontology_registry'
POINTER_KIND = 'ontology_pointer'
POINTER_ID = 'current'


class DefaultTarget:
    """The definition and concept pinned by a task without an explicit target.

    ``SessionService`` asks the default for its ``id`` and one concept; this
    adapter answers both while keeping the concrete revision available.
    """

    def __init__(self, definition, concept):
        self.definition = definition
        self.id = definition.id
        self.concept = concept

    def resolve_concept(self, name=''):
        return self.definition.resolve_concept(name or self.concept)


def load_definition(path):
    return OntologyRevision.model_validate_json(Path(path).read_text())


def entry_row(store, scope, ontology_id):
    return store.current(REGISTRY_KIND, ontology_id, scope=scope)


def parse_entry(row):
    return None if row is None else OntologyRegistryEntry.model_validate(row['body'])


def entries(store, scope):
    rows = store.query(REGISTRY_KIND, scope, limit=1000)
    return [(OntologyRegistryEntry.model_validate(row['body']), row) for row in rows]


def pointer_row(store, scope):
    return store.current(POINTER_KIND, POINTER_ID, scope=scope)


def build_entry(definition, *, origin='builtin', title='', source_snapshot='',
                published_by='', published_at='', definition_digest='',
                previous_revision='', diff=None, destructive=False):
    concepts = list(definition.concepts)
    record = revision_record(definition, published_at=published_at,
        published_by=published_by, source_snapshot=source_snapshot,
        definition_digest=definition_digest, previous_revision=previous_revision,
        diff=diff, destructive=destructive)
    return OntologyRegistryEntry(
        id=definition.id, ontology_revision=definition.revision, origin=origin,
        title=title or definition.id, concepts=concepts,
        default_concept=concepts[0] if concepts else '',
        source_snapshot=source_snapshot, published_by=published_by,
        published_at=published_at, revisions=[record])


def revision_record(definition, *, published_at='', published_by='',
                    source_snapshot='', definition_digest='',
                    previous_revision='', diff=None, destructive=False):
    """One entry of an ontology's visible revision history.

    The definition itself stays in the immutable ``ontology`` revision store;
    this record only carries what the library page shows: which revision was
    published when and by whom, what changed against its predecessor, and
    whether that change was destructive.
    """
    return {
        'revision': definition.revision,
        'published_at': published_at,
        'published_by': published_by,
        'source_snapshot': source_snapshot,
        'definition_digest': definition_digest,
        'previous_revision': previous_revision,
        'destructive': bool(destructive),
        'diff': dict(diff or {}),
    }
