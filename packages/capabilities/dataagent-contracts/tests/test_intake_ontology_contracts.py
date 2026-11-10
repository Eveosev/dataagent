from decimal import Decimal
import pytest
from pydantic import ValidationError
from dataagent_contracts.intake import SourceProfile, WorkSpec
from dataagent_contracts.ontology import Assertion, MappingSpec, OntologyRevision
from dataagent_contracts.core.refs import SourceAnchor


def test_decimal_and_role_tuple_survive_roundtrip():
    fact = Assertion(id='a1', scope='tenant-a', ontology_revision='procurement@1',
        relation='price', role_bindings=[{'role':'order','value':'PO-1'},
        {'role':'amount','value':Decimal('123456789012345678.09'),'value_type':'decimal'}],
        source_anchors=[{'source_ref':'pdf-1','source_revision':'sha1',
                         'selector':{'kind':'pdf_text_span','page':1,'char_start':0,'char_end':5}}],
        mapping_revision='mapping@1', extractor_version='parser@1')
    result = Assertion.model_validate_json(fact.model_dump_json())
    assert result.role_bindings[1].value == Decimal('123456789012345678.09')
    assert result.role_bindings[0].role == 'order'
    assert result.source_anchors[0].source_revision == 'sha1'
    assert result.ontology_revision == 'procurement@1'


def test_partial_document_preserves_page_gaps():
    profile = SourceProfile(source_id='p', source_revision='abc', kind='pdf',
        fields=['amount'], records=[], total_partitions=3, completed_partitions=[1,3],
        gaps=[{'partition':2,'code':'ocr_engine_missing'}])
    restored = SourceProfile.model_validate_json(profile.model_dump_json())
    assert restored.coverage == 'partial'
    assert restored.gaps[0].partition == 2
    with pytest.raises(ValidationError):
        SourceProfile(source_id='p', source_revision='a', kind='pdf',
                      total_partitions=2, completed_partitions=[1,3])


def test_old_source_anchors_remain_readable():
    anchor = SourceAnchor.model_validate({'source_ref':'f','source_revision':'r',
        'selector':{'kind':'excel_cell','sheet':'Sheet1','range':'B2'}})
    assert anchor.selector.range == 'B2'
    ui = SourceAnchor.model_validate({'source_ref':'ui','source_revision':'r',
        'selector':{'kind':'gui_control','observation_ref':'obs@1',
                    'screenshot_ref':'shot@1','control':'button:Submit','viewport':[1280,800]}})
    assert ui.selector.observation_ref == 'obs@1'


def test_required_binding_and_extensions_remain_distinct():
    onto = OntologyRevision(id='invoice', revision='1', entity_type='Invoice',
        properties={'number':{'value_type':'string','required':True},
                    'amount':{'value_type':'decimal'}}, identity_fields=['number'])
    mapping = MappingSpec(id='m', revision='1', ontology_revision='invoice@1',
        source_fingerprint='abc', bindings={'amount':{'source_field':'total'}},
        unmapped={'number':'unresolved'}, extensions={'vendor.extra':'x'})
    assert onto.identity_fields == ['number']
    assert mapping.unmapped['number'] == 'unresolved'
    with pytest.raises(ValidationError):
        MappingSpec.model_validate({**mapping.model_dump(), 'extensions':{'number':'x'}})


def test_goal_and_source_selection_reject_implicit_authority():
    goal=WorkSpec(id='g', goal='ingest invoice', acceptance_criteria=['evidence'],
                  authorization_ref='auth:read')
    assert goal.revision == '1'
    with pytest.raises(ValidationError):
        WorkSpec.model_validate({**goal.model_dump(),'granted_permissions':['write']})


def test_intake_schema_is_available_to_frontend(tmp_path):
    import json, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root/'scripts/generate_schema.py'), '--out', str(tmp_path)], check=True)
    schema_path = tmp_path/'intake.SourceProfile.json'
    assert schema_path.exists(), 'new namespaces must participate in generated schema gate'
    schema = json.loads(schema_path.read_text())
    assert 'source_revision' in schema['required']
    assert 'gaps' in schema['properties']
