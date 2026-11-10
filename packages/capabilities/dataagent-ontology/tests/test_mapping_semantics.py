from decimal import Decimal
import pytest
from dataagent_contracts.ontology import OntologyRevision, MappingSpec
from dataagent_contracts.intake import SourceProfile
from dataagent_ontology.mapping import materialize
from dataagent_ontology.facts import relation_key


def ontology():
    return OntologyRevision(id='invoice',revision='1',entity_type='Invoice',
        properties={'number':{'value_type':'string','required':True},
        'company':{'value_type':'string','required':True},'amount':{'value_type':'decimal','required':True}},
        identity_fields=['company','number'])


def profile(rows):
    anchors={f'{i}.{field}':[{'source_ref':'source','source_revision':'digest',
        'selector':{'kind':'record_key','keys':{'row':i+2},'field':field}}]
        for i,row in enumerate(rows) for field in row}
    return SourceProfile(source_id='source',source_revision='digest',kind='csv',records=rows,
        fields=['number','company','minor'],anchors=anchors,total_partitions=1,completed_partitions=[1],metadata={'structure_fingerprint':'schema'})


def mapping(**kwargs):
    return MappingSpec(id='m',revision='1',ontology_revision='invoice@1',source_fingerprint='schema',
        bindings={'number':{'source_field':'number'},'company':{'source_field':'company'},
                  'amount':{'source_field':'minor','transform':'minor_to_major'}},**kwargs)


def test_minor_units_use_decimal():
    result=materialize(ontology(),mapping(),[profile([{'number':'A','company':'C','minor':'12345678901234567890123456789009'}])],scope='T')
    assert result.instances[0].values['amount']==Decimal('123456789012345678901234567890.09')
    assert not result.issues


def test_missing_required_binding_is_reported():
    m=mapping();m.bindings.pop('amount');m.unmapped['minor']='extension'
    result=materialize(ontology(),m,[profile([{'number':'A','company':'C','minor':'100'}])],scope='T')
    assert any(i['code']=='ontology.required_binding_missing' and i['target']=='amount' for i in result.issues)
    assert result.instances[0].extensions['source.unmapped']['minor']=='100'


def test_same_name_does_not_merge_tenants_and_composite_keys_keep_all_parts():
    p=profile([{'number':'A','company':'C','minor':'100'},{'number':'A','company':'D','minor':'100'}])
    a=materialize(ontology(),mapping(),[p],scope='one')
    b=materialize(ontology(),mapping(),[p],scope='two')
    assert len({x.id for x in a.instances})==2
    assert a.instances[0].id!=b.instances[0].id


def test_conflicting_sources_keep_both_assertions():
    p=profile([{'number':'A','company':'C','minor':'100'},{'number':'A','company':'C','minor':'200'}])
    result=materialize(ontology(),mapping(),[p],scope='T')
    assert len(result.instances)==1
    assert any(i['code']=='ontology.conflicting_values' for i in result.issues)
    assert result.instances[0].values['amount'] is None
    assert len([a for a in result.assertions if a.relation=='amount'])==2


def test_nary_relation_preserves_roles_and_set_semantics():
    from dataagent_contracts.ontology import RoleBinding
    roles=[RoleBinding(role='order',value='O1'),RoleBinding(role='amount',value='100.00',value_type='decimal'),RoleBinding(role='currency',value='CNY')]
    assert relation_key('T','price',roles)==relation_key('T','price',roles)
    assert relation_key('T','price',roles)!=relation_key('T','price',list(reversed(roles)))
    changed=roles.copy();changed[1]=RoleBinding(role='amount',value='100.0',value_type='decimal')
    assert relation_key('T','price',roles)==relation_key('T','price',changed)


def test_mapping_cannot_silently_target_other_ontology_or_structure():
    with pytest.raises(ValueError):
        materialize(ontology(),mapping().model_copy(update={'ontology_revision':'invoice@2'}),[],scope='T')
    with pytest.raises(ValueError):
        materialize(ontology(),mapping().model_copy(update={'source_fingerprint':'wrong'}),[profile([])],scope='T')


def test_materialized_nary_relation_has_ontology_role_order_and_evidence():
    onto=ontology();onto.relations={'price':['invoice','amount','currency']}
    m=mapping();relations={'price':{
        'currency':{'source_field':'currency'},'invoice':{'source_field':'$entity'},
        'amount':{'source_field':'minor','transform':'minor_to_major'}}}
    # Validation is part of the public proposal boundary.
    m=MappingSpec.model_validate({**m.model_dump(), 'relation_bindings':relations})
    p=profile([{'number':'A','company':'C','minor':'100','currency':'CNY'}])
    result=materialize(onto,m,[p],scope='T')
    facts=[f for f in result.facts if f.relation=='price']
    assert len(facts)==1
    assert [r.role for r in facts[0].role_bindings]==['invoice','amount','currency']
    assert facts[0].role_bindings[1].value==Decimal('1')
    assert facts[0].assertion_refs
