"""Multi-concept ontology contract: validation, legacy compat and mapping targets."""
from pathlib import Path
import pytest
from pydantic import ValidationError
from dataagent_contracts.ontology import MappingSpec, OntologyRevision


PROCUREMENT = Path(__file__).resolve().parents[2] / 'dataagent-workbench' / 'src' / \
    'dataagent_workbench' / 'ontologies' / 'procurement.json'


def multi_concept(**overrides):
    data = {
        'id': 'expense', 'revision': '1',
        'concepts': {
            'expense_line': {
                'entity_type': 'ExpenseLine',
                'properties': {
                    'line_no': {'value_type': 'string', 'required': True},
                    'city': {'value_type': 'string'},
                },
                'identity_fields': ['line_no'],
            },
            'expense_standard': {
                'entity_type': 'ExpenseStandard',
                'properties': {
                    'standard_no': {'value_type': 'string', 'required': True},
                    'limit': {'value_type': 'decimal', 'required': True},
                },
                'identity_fields': ['standard_no'],
            },
        },
        'relations': {
            'applies_to': {
                'roles': ['line', 'standard'],
                'subject_concept': 'expense_line',
                'object_concept': 'expense_standard',
            },
        },
    }
    data.update(overrides)
    return data


def test_multi_concept_definition_validates_and_resolves_each_concept():
    ontology = OntologyRevision.model_validate(multi_concept())
    assert set(ontology.concepts) == {'expense_line', 'expense_standard'}
    name, concept = ontology.resolve_concept('expense_standard')
    assert name == 'expense_standard'
    assert concept.entity_type == 'ExpenseStandard'
    assert set(concept.properties) == {'standard_no', 'limit'}
    assert ontology.relation_roles('applies_to') == ['line', 'standard']
    assert ontology.relations['applies_to'].subject_concept == 'expense_line'
    assert ontology.relations['applies_to'].object_concept == 'expense_standard'
    with pytest.raises(ValueError):
        ontology.resolve_concept()  # more than one concept: a name is required
    with pytest.raises(KeyError):
        ontology.resolve_concept('expense_report')


def test_legacy_single_concept_definition_reads_as_its_own_concept():
    legacy = OntologyRevision.model_validate_json(PROCUREMENT.read_text())
    assert set(legacy.concepts) == {'PurchaseDocument'}
    name, concept = legacy.resolve_concept()
    assert name == 'PurchaseDocument'
    assert concept.entity_type == legacy.entity_type
    assert concept.properties == legacy.properties
    assert concept.identity_fields == legacy.identity_fields


def test_legacy_definition_serializes_without_the_derived_concepts():
    legacy = OntologyRevision.model_validate_json(PROCUREMENT.read_text())
    body = legacy.model_dump(mode='json')
    # The legacy shape keeps its own field set: no derived concepts map, and
    # relations stay bare ordered role lists.
    assert 'concepts' not in body
    assert set(body) == {'id', 'revision', 'entity_type', 'properties',
                         'identity_fields', 'relations', 'extensions'}
    assert body['relations'] == {'price': ['document', 'amount', 'currency']}
    # A body stored by the previous contract re-validates and re-dumps stably,
    # so re-registering the builtin on an existing workspace stays idempotent.
    restored = OntologyRevision.model_validate(body)
    assert restored == legacy
    assert restored.model_dump(mode='json') == body


def test_mapping_names_the_target_concept_and_defaults_to_empty():
    mapping = MappingSpec.model_validate({'id': 'm', 'revision': '1',
        'ontology_revision': 'expense@1', 'source_fingerprint': 'fp', 'bindings': {}})
    assert mapping.concept == ''
    assert MappingSpec.model_validate({**mapping.model_dump(), 'concept': 'expense_line'}).concept \
        == 'expense_line'


@pytest.mark.parametrize('mutation', [
    # identity field is not one of the concept's properties
    {'concepts': {'a': {'entity_type': 'A', 'properties': {'x': {'value_type': 'string'}},
                        'identity_fields': ['missing']}}},
    # two concepts share one entity type
    {'concepts': {
        'a': {'entity_type': 'A', 'properties': {'x': {'value_type': 'string'}}, 'identity_fields': ['x']},
        'b': {'entity_type': 'A', 'properties': {'y': {'value_type': 'string'}}, 'identity_fields': ['y']}}},
    # relation endpoint concept does not exist
    {'concepts': {
        'a': {'entity_type': 'A', 'properties': {'x': {'value_type': 'string'}}, 'identity_fields': ['x']}},
     'relations': {'r': {'roles': ['p', 'q'], 'subject_concept': 'a', 'object_concept': 'nope'}}},
    # a multi-concept relation without endpoint concepts is ambiguous
    {'concepts': {
        'a': {'entity_type': 'A', 'properties': {'x': {'value_type': 'string'}}, 'identity_fields': ['x']},
        'b': {'entity_type': 'B', 'properties': {'y': {'value_type': 'string'}}, 'identity_fields': ['y']}},
     'relations': {'r': ['p', 'q']}},
    # concepts plus the legacy single-concept fields
    {'concepts': {'a': {'entity_type': 'A', 'properties': {'x': {'value_type': 'string'}},
                        'identity_fields': ['x']}},
     'entity_type': 'A'},
    # neither concepts nor legacy fields
    {},
])
def test_invalid_definitions_are_rejected(mutation):
    with pytest.raises(ValidationError):
        OntologyRevision.model_validate({'id': 'x', 'revision': '1', **mutation})


def test_relation_roles_stay_distinct_and_ordered():
    with pytest.raises(ValidationError):
        OntologyRevision.model_validate(multi_concept(relations={
            'applies_to': {'roles': ['line', 'line'], 'subject_concept': 'expense_line',
                           'object_concept': 'expense_standard'}}))
