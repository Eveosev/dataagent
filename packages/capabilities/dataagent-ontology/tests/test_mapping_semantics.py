from decimal import Decimal
import pytest
from dataagent_contracts.ontology import OntologyRevision, MappingSpec
from dataagent_contracts.intake import CoverageGap, SourceProfile
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


def test_date_binding_accepts_the_midnight_iso_form_the_sheet_reader_emits():
    onto=OntologyRevision(id='invoice',revision='1',entity_type='Invoice',
        properties={'number':{'value_type':'string','required':True},
                    'day':{'value_type':'date','required':True}},
        identity_fields=['number'])
    m=MappingSpec(id='m',revision='1',ontology_revision='invoice@1',source_fingerprint='schema',
        bindings={'number':{'source_field':'number'},
                  'day':{'source_field':'day','transform':'date'}})
    p=profile([{'number':'A','day':'2026-04-08T00:00:00'}]).model_copy(
        update={'fields':['number','day']})
    result=materialize(onto,m,[p],scope='T')
    assert result.instances[0].values=={'number':'A','day':'2026-04-08'}
    assert not result.issues


def _date_ontology():
    return OntologyRevision(id='invoice',revision='1',entity_type='Invoice',
        properties={'number':{'value_type':'string','required':True},
                    'day':{'value_type':'date','required':True}},
        identity_fields=['number'])


def test_date_binding_rejects_a_non_midnight_iso_time_instead_of_truncating_it():
    m=MappingSpec(id='m',revision='1',ontology_revision='invoice@1',source_fingerprint='schema',
        bindings={'number':{'source_field':'number'},
                  'day':{'source_field':'day','transform':'date'}})
    p=profile([{'number':'A','day':'2026-04-08T09:30:00'}]).model_copy(
        update={'fields':['number','day']})
    result=materialize(_date_ontology(),m,[p],scope='T')
    assert result.instances[0].values=={'number':'A'}
    issue=next(i for i in result.issues
               if i['code']=='ontology.conversion_failed' and i['target']=='day')
    assert issue['detail']=='时间不是零点，不能按日期保存'
    assert any(i['code']=='ontology.required_value_missing' and i['target']=='day'
               for i in result.issues)


def test_date_binding_with_an_explicit_format_also_refuses_a_non_midnight_time():
    m=MappingSpec(id='m',revision='1',ontology_revision='invoice@1',source_fingerprint='schema',
        bindings={'number':{'source_field':'number'},
                  'day':{'source_field':'day','transform':'date',
                         'options':{'format':'%Y-%m-%d %H:%M:%S'}}})
    p=profile([{'number':'A','day':'2026-04-08 09:30:00'}]).model_copy(
        update={'fields':['number','day']})
    result=materialize(_date_ontology(),m,[p],scope='T')
    issue=next(i for i in result.issues
               if i['code']=='ontology.conversion_failed' and i['target']=='day')
    assert issue['detail']=='时间不是零点，不能按日期保存'

    midnight=profile([{'number':'B','day':'2026-04-08 00:00:00'}]).model_copy(
        update={'fields':['number','day']})
    accepted=materialize(_date_ontology(),m,[midnight],scope='T')
    assert accepted.instances[0].values=={'number':'B','day':'2026-04-08'}
    assert not accepted.issues


def test_missing_required_binding_is_reported():
    m=mapping();m.bindings.pop('amount');m.unmapped['minor']='extension'
    result=materialize(ontology(),m,[profile([{'number':'A','company':'C','minor':'100'}])],scope='T')
    assert any(i['code']=='ontology.required_binding_missing' and i['target']=='amount' for i in result.issues)
    assert result.instances[0].extensions['source.unmapped']['minor']=='100'


def test_string_partition_disposition_counts_as_acknowledged_coverage():
    p=profile([]).model_copy(update={
        'total_partitions':2,'completed_partitions':['table_a'],
        'gaps':[CoverageGap(partition='table_b',code='read_failed')]})
    assert any(i['code']=='ontology.incomplete_source'
               for i in materialize(ontology(),mapping(),[p],scope='T').issues)
    dispositions=[{'source_id':'source','action':'partition_not_applicable',
                   'partition':'table_b','reason':'空表'}]
    result=materialize(ontology(),mapping(),[p],scope='T',dispositions=dispositions)
    assert not any(i['code']=='ontology.incomplete_source' for i in result.issues)


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


def multi_concept_ontology():
    return OntologyRevision.model_validate({
        'id': 'expense', 'revision': '1',
        'concepts': {
            'expense_line': {
                'entity_type': 'ExpenseLine',
                'properties': {'line_no': {'value_type': 'string', 'required': True},
                               'city': {'value_type': 'string'},
                               'amount': {'value_type': 'decimal', 'required': True}},
                'identity_fields': ['line_no']},
            'expense_standard': {
                'entity_type': 'ExpenseStandard',
                'properties': {'standard_no': {'value_type': 'string', 'required': True},
                               'city': {'value_type': 'string'},
                               'limit': {'value_type': 'decimal', 'required': True}},
                'identity_fields': ['standard_no']}},
        'relations': {'applies_to': {'roles': ['line', 'standard'],
                                      'subject_concept': 'expense_line',
                                      'object_concept': 'expense_standard'}}})


def test_second_concept_materializes_with_its_own_identity_and_type():
    onto=multi_concept_ontology()
    m=MappingSpec(id='m',revision='1',ontology_revision='expense@1',concept='expense_standard',
        source_fingerprint='schema',bindings={'standard_no':{'source_field':'number'},
        'city':{'source_field':'city'},'limit':{'source_field':'amount','transform':'decimal'}})
    p=profile([{'number':'STD-1','city':'北京','amount':'500'}])
    result=materialize(onto,m,[p],scope='T')
    assert [i.entity_type for i in result.instances]==['ExpenseStandard']
    assert result.instances[0].values=={'standard_no':'STD-1','city':'北京','limit':Decimal('500')}
    assert not result.issues


def test_mapping_without_concept_cannot_target_a_multi_concept_ontology():
    onto=multi_concept_ontology()
    m=MappingSpec(id='m',revision='1',ontology_revision='expense@1',
        source_fingerprint='schema',bindings={'standard_no':{'source_field':'number'}})
    with pytest.raises(ValueError):
        materialize(onto,m,[profile([{'number':'STD-1'}])],scope='T')


def test_mapping_cannot_bind_properties_of_another_concept():
    onto=multi_concept_ontology()
    m=MappingSpec(id='m',revision='1',ontology_revision='expense@1',concept='expense_standard',
        source_fingerprint='schema',bindings={'line_no':{'source_field':'number'}})
    with pytest.raises(ValueError):
        materialize(onto,m,[profile([{'number':'L1'}])],scope='T')


def test_relation_bindings_require_the_subject_concept():
    onto=multi_concept_ontology()
    m=MappingSpec(id='m',revision='1',ontology_revision='expense@1',concept='expense_standard',
        source_fingerprint='schema',bindings={'standard_no':{'source_field':'number'}},
        relation_bindings={'applies_to':{
            'standard':{'source_field':'number'},
            'line':{'source_field':'$entity'}}})
    with pytest.raises(ValueError):
        materialize(onto,m,[profile([{'number':'STD-1'}])],scope='T')


def test_relation_on_the_mapped_concept_materializes():
    onto=multi_concept_ontology()
    m=MappingSpec(id='m',revision='1',ontology_revision='expense@1',concept='expense_line',
        source_fingerprint='schema',bindings={'line_no':{'source_field':'number'},
        'city':{'source_field':'city'},'amount':{'source_field':'amount','transform':'decimal'}},
        relation_bindings={'applies_to':{
            'line':{'source_field':'$entity'},
            'standard':{'source_field':'city'}}})
    p=profile([{'number':'L1','city':'STD-1','amount':'100'}])
    result=materialize(onto,m,[p],scope='T')
    assert [i.entity_type for i in result.instances]==['ExpenseLine']
    facts=[f for f in result.facts if f.relation=='applies_to']
    assert [r.role for r in facts[0].role_bindings]==['line','standard']


def test_legacy_definition_still_materializes_without_a_concept():
    m=mapping()
    result=materialize(ontology(),m,[profile([{'number':'A','company':'C','minor':'100'}])],scope='T')
    assert result.instances[0].entity_type=='Invoice'


def test_row_issues_carry_source_and_entity_for_web_jumps():
    m=MappingSpec(id='m',revision='1',ontology_revision='invoice@1',
        source_fingerprint='schema',bindings={'number':{'source_field':'number'},
        'company':{'source_field':'company'},'amount':{'source_field':'minor','transform':'decimal'}})
    p=profile([{'number':'A','company':'C','minor':'not-a-number'}])
    result=materialize(ontology(),m,[p],scope='T')
    for code in ('ontology.conversion_failed','ontology.required_value_missing'):
        issue=next(i for i in result.issues if i['code']==code)
        assert issue['source_id']=='source'
        assert issue['entity_id']


def test_ossie_export_rejects_a_multi_concept_ontology():
    from dataagent_ontology.adapters.ossie import OssieValidationError, export_ossie
    onto=multi_concept_ontology()
    m=MappingSpec(id='m',revision='1',ontology_revision='expense@1',concept='expense_line',
        source_fingerprint='schema',bindings={'line_no':{'source_field':'number'}})
    with pytest.raises(OssieValidationError) as raised:
        export_ossie(onto,m)
    assert 'single concept' in str(raised.value)
