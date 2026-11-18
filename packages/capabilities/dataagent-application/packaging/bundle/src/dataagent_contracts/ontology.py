"""Evidence-bearing facts and executable, versioned mapping proposals."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from pydantic import Field, model_serializer, model_validator
from .core._base import ExtModel
from .core.refs import SourceAnchor


class PropertyDefinition(ExtModel):
    value_type: Literal['string', 'decimal', 'integer', 'boolean', 'date', 'datetime', 'reference']
    required: bool = False
    description: str = ''


class ConceptDefinition(ExtModel):
    """One concept of a domain ontology: its entities, attributes and identity."""
    entity_type: str
    properties: dict[str, PropertyDefinition]
    identity_fields: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def check_identity(self):
        if not set(self.identity_fields) <= self.properties.keys():
            raise ValueError('identity fields must exist in concept')
        if len(set(self.identity_fields)) != len(self.identity_fields):
            raise ValueError('duplicate identity fields')
        return self


class RelationDefinition(ExtModel):
    """A directed relation between two concepts with ordered role names."""
    roles: list[str] = Field(min_length=2)
    subject_concept: str = ''
    object_concept: str = ''

    @model_validator(mode='after')
    def check_roles(self):
        if len(self.roles) < 2 or len(set(self.roles)) != len(self.roles):
            raise ValueError('relation requires two or more distinct ordered roles')
        return self


class OntologyRevision(ExtModel):
    """A versioned domain ontology: one or more concepts plus relations.

    A definition carries either ``concepts`` (concept name → definition) or
    the legacy single-concept fields ``entity_type`` / ``properties`` /
    ``identity_fields``; the legacy shape names its only concept after the
    entity type and serializes exactly as before, so stored revisions keep
    their bytes.  Relation values may stay bare ordered role lists (legacy);
    a multi-concept definition must give every relation explicit endpoint
    concepts and direction (subject → object).
    """
    id: str
    revision: str
    entity_type: str = ''
    properties: dict[str, PropertyDefinition] = Field(default_factory=dict)
    identity_fields: list[str] = Field(default_factory=list)
    relations: dict[str, list[str] | RelationDefinition] = Field(default_factory=dict)
    concepts: dict[str, ConceptDefinition] = Field(default_factory=dict)

    @model_validator(mode='before')
    def _derive_single_concept(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get('concepts'):
            if data.get('entity_type') or data.get('properties') or data.get('identity_fields'):
                raise ValueError('define either concepts or the legacy single-concept fields, not both')
            return data
        entity_type = data.get('entity_type')
        if not entity_type:
            raise ValueError('ontology needs concepts or the legacy single-concept fields')
        data = dict(data)
        data['concepts'] = {entity_type: {
            'entity_type': entity_type,
            'properties': data.get('properties') or {},
            'identity_fields': data.get('identity_fields') or [],
        }}
        return data

    @model_validator(mode='after')
    def check_concepts_and_relations(self):
        if not self.concepts:
            raise ValueError('ontology needs at least one concept')
        entity_types = {}
        for name, concept in self.concepts.items():
            if not str(name).strip():
                raise ValueError('concept names must not be empty')
            if concept.entity_type in entity_types:
                raise ValueError('entity type %r is used by concepts %r and %r'
                                 % (concept.entity_type, entity_types[concept.entity_type], name))
            entity_types[concept.entity_type] = name
        single = len(self.concepts) == 1
        for name, relation in self.relations.items():
            if not isinstance(relation, RelationDefinition):
                if not single:
                    raise ValueError('relations in a multi-concept ontology must name their endpoint concepts: %r' % name)
                continue
            subject, obj = relation.subject_concept, relation.object_concept
            if single and not subject and not obj:
                continue
            for endpoint in (subject, obj):
                if not endpoint or endpoint not in self.concepts:
                    raise ValueError('relation %r endpoint concept %r is not defined' % (name, endpoint))
        return self

    @model_serializer(mode='wrap')
    def _keep_legacy_shape(self, handler, info=None):
        data = handler(self)
        if self.entity_type:
            # A legacy single-concept definition serializes without the
            # derived concepts map so registered revisions stay byte-identical.
            data.pop('concepts', None)
        return data

    def resolve_concept(self, name=''):
        """Return (concept name, definition); an empty name selects the only concept."""
        if not name:
            if len(self.concepts) != 1:
                raise ValueError('ontology %s@%s defines %d concepts; name one'
                                  % (self.id, self.revision, len(self.concepts)))
            name = next(iter(self.concepts))
        if name not in self.concepts:
            raise KeyError('unknown concept: %s' % name)
        return name, self.concepts[name]

    def relation_roles(self, name):
        """Ordered role names of one relation, for legacy lists and definitions."""
        relation = self.relations[name]
        return relation.roles if isinstance(relation, RelationDefinition) else list(relation)


class FieldBinding(ExtModel):
    source_field: str
    transform: Literal['identity', 'decimal', 'minor_to_major', 'integer', 'date', 'datetime', 'enum', 'combine', 'choose'] = 'identity'
    options: dict[str, Any] = Field(default_factory=dict)


class MappingSpec(ExtModel):
    id: str
    revision: str
    ontology_revision: str
    concept: str = ''
    source_fingerprint: str
    bindings: dict[str, FieldBinding]
    relation_bindings: dict[str, dict[str, FieldBinding]] = Field(default_factory=dict)
    unmapped: dict[str, Literal['extension', 'unresolved', 'exclude']] = Field(default_factory=dict)
    scope: str = 'workspace'
    identity_strategy: str = 'declared_keys'
    validation_ref: str | None = None


class RoleBinding(ExtModel):
    role: str
    value: Any
    value_type: Literal['string', 'decimal', 'integer', 'boolean', 'date', 'datetime', 'reference'] = 'string'

    @model_validator(mode='after')
    def typed_value(self):
        if self.value is None:
            raise ValueError('relation roles cannot be null')
        if self.value_type == 'decimal':
            self.value = Decimal(str(self.value))
            if not self.value.is_finite():
                raise ValueError('nonfinite decimal')
        return self


class Assertion(ExtModel):
    id: str
    scope: str
    ontology_revision: str
    relation: str
    role_bindings: list[RoleBinding] = Field(min_length=1)
    source_anchors: list[SourceAnchor] = Field(min_length=1)
    mapping_revision: str
    extractor_version: str
    business_time: str | None = None
    observed_time: str | None = None

    @model_validator(mode='after')
    def unique_roles(self):
        roles = [r.role for r in self.role_bindings]
        if len(set(roles)) != len(roles):
            raise ValueError('duplicate roles in assertion')
        return self


class EntityInstance(ExtModel):
    id: str
    scope: str
    entity_type: str
    values: dict[str, Any]
    source_anchors: dict[str, list[SourceAnchor]] = Field(default_factory=dict)
    unresolved: list[str] = Field(default_factory=list)


class RelationFact(ExtModel):
    id: str
    relation: str
    role_bindings: list[RoleBinding]
    assertion_refs: list[str]


class MappingPreview(ExtModel):
    id: str
    revision: str
    ontology_revision: str
    mapping: MappingSpec
    source_revisions: dict[str, str]
    instances: list[EntityInstance]
    issues: list[dict[str, Any]]
    digest: str


class ReviewDecision(ExtModel):
    preview_ref: str
    target_scope: Literal['instance', 'mapping', 'ontology']
    changes: dict[str, Any] = Field(default_factory=dict)
    decision: Literal['save', 'reject'] = 'save'


class ReviewReceipt(ExtModel):
    decision_ref: str
    revision: str
    revalidate: list[str] = Field(default_factory=list)


class DatasetRelease(ExtModel):
    id: str
    revision: str
    preview_ref: str
    digest: str
