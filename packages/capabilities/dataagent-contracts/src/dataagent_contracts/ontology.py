"""Evidence-bearing facts and executable, versioned mapping proposals."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from pydantic import Field, model_validator
from .core._base import ExtModel
from .core.refs import SourceAnchor


class PropertyDefinition(ExtModel):
    value_type: Literal['string', 'decimal', 'integer', 'boolean', 'date', 'datetime', 'reference']
    required: bool = False
    description: str = ''


class OntologyRevision(ExtModel):
    id: str
    revision: str
    entity_type: str
    properties: dict[str, PropertyDefinition]
    identity_fields: list[str] = Field(min_length=1)
    relations: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def check_identity_and_roles(self):
        if not set(self.identity_fields) <= self.properties.keys():
            raise ValueError('identity fields must exist in ontology')
        if len(set(self.identity_fields)) != len(self.identity_fields):
            raise ValueError('duplicate identity fields')
        for roles in self.relations.values():
            if len(roles) < 2 or len(set(roles)) != len(roles):
                raise ValueError('relation requires two or more distinct ordered roles')
        return self


class FieldBinding(ExtModel):
    source_field: str
    transform: Literal['identity', 'decimal', 'minor_to_major', 'integer', 'date', 'datetime', 'enum', 'combine', 'choose'] = 'identity'
    options: dict[str, Any] = Field(default_factory=dict)


class MappingSpec(ExtModel):
    id: str
    revision: str
    ontology_revision: str
    source_fingerprint: str
    bindings: dict[str, FieldBinding]
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
