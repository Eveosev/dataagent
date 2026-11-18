"""Tasks pin their mapping target: one concept of a multi-concept ontology (D0)."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from dataagent_contracts.ontology import MappingSpec, OntologyRevision
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.interfaces.http_api import create_app
from dataagent_workbench.service_tools import invoke


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


def setup(tmp_path, target=None):
    data = Path(__file__).resolve().parents[2] / 'dataagent-data'
    wb = Workbench(tmp_path, layer_client=LayerClient(data))
    wb.ontology.register(multi_concept_ontology(), wb.ctx)
    (tmp_path / 'rows.csv').write_text('number,city,amount\nR1,北京,500\n')
    args = {'goal': '接入费用数据',
             'sources': [{'source_id': 'rows', 'kind': 'file', 'locator_ref': 'rows.csv'}]}
    if target is not None:
        args['target'] = target
    result = invoke(wb, 'intake_start', args)
    sid = result.data['session_id']
    return wb, wb.intake.advance(sid, wb.ctx)


def standard_proposal(wb, session, concept='expense_standard'):
    request = wb.intake.inference_request(session.id, wb.ctx)
    return MappingSpec(id='candidate', revision='1', ontology_revision='expense@1',
        concept=concept, source_fingerprint=request['sources'][0]['structure_fingerprint'],
        bindings={'standard_no': {'source_field': 'number'},
                  'city': {'source_field': 'city'},
                  'limit': {'source_field': 'amount', 'transform': 'decimal'}})


def test_task_targets_the_second_concept_of_a_multi_concept_ontology(tmp_path):
    wb, s = setup(tmp_path, target={'ontology_id': 'expense', 'concept': 'expense_standard'})
    assert s.phase == 'needs_input'
    request = wb.intake.inference_request(s.id, wb.ctx)
    assert request['allowed_target']['concept'] == 'expense_standard'
    assert request['allowed_target']['entity_type'] == 'ExpenseStandard'
    assert 'standard_no' in request['allowed_target']['properties']
    assert request['proposal_template']['concept'] == 'expense_standard'
    preview = wb.intake.submit_proposal(s.id, standard_proposal(wb, s), s.revision, wb.ctx)
    assert [i.entity_type for i in preview.instances] == ['ExpenseStandard']
    assert preview.instances[0].values['standard_no'] == 'R1'
    assert str(preview.instances[0].values['limit']) == '500'
    assert not preview.issues
    view = wb.intake.view(s.id, wb.ctx)
    assert view['ontology_concept'] == 'expense_standard'
    assert view['ontology']['id'] == 'expense'


def test_two_tasks_with_different_targets_do_not_interfere(tmp_path):
    wb, s_line = setup(tmp_path, target={'ontology_id': 'expense', 'concept': 'expense_line'})
    goal = {'goal': '接入费用数据',
            'sources': [{'source_id': 'rows', 'kind': 'file', 'locator_ref': 'rows.csv'}]}
    standard = invoke(wb, 'intake_start',
                      {**goal, 'target': {'ontology_id': 'expense', 'concept': 'expense_standard'}})
    s_std = wb.intake.advance(standard.data['session_id'], wb.ctx)

    line_request = wb.intake.inference_request(s_line.id, wb.ctx)
    assert line_request['allowed_target']['concept'] == 'expense_line'
    std_request = wb.intake.inference_request(s_std.id, wb.ctx)
    assert std_request['allowed_target']['concept'] == 'expense_standard'

    std_preview = wb.intake.submit_proposal(s_std.id, standard_proposal(wb, s_std),
                                            s_std.revision, wb.ctx)
    assert [i.entity_type for i in std_preview.instances] == ['ExpenseStandard']
    # The line task still refuses the standard concept's properties.
    with pytest.raises(ValueError):
        wb.intake.submit_proposal(s_line.id, standard_proposal(wb, s_line),
                                 s_line.revision, wb.ctx)
    request = wb.intake.inference_request(s_line.id, wb.ctx)
    line = MappingSpec(id='candidate', revision='1', ontology_revision='expense@1',
        concept='expense_line', source_fingerprint=request['sources'][0]['structure_fingerprint'],
        bindings={'line_no': {'source_field': 'number'},
                  'city': {'source_field': 'city'},
                  'amount': {'source_field': 'amount', 'transform': 'decimal'}})
    line_preview = wb.intake.submit_proposal(s_line.id, line, s_line.revision, wb.ctx)
    assert [i.entity_type for i in line_preview.instances] == ['ExpenseLine']
    assert [i['entity_type'] for i in wb.intake.view(s_std.id, wb.ctx)['preview']['instances']] \
        == ['ExpenseStandard']


def test_proposal_outside_the_task_target_is_rejected(tmp_path):
    wb, s = setup(tmp_path, target={'ontology_id': 'expense', 'concept': 'expense_standard'})
    with pytest.raises(ValueError):
        wb.intake.submit_proposal(s.id, standard_proposal(wb, s, concept='expense_line'),
                                 s.revision, wb.ctx)


def test_task_without_target_defaults_to_the_builtin_procurement(tmp_path):
    wb, s = setup(tmp_path)
    request = wb.intake.inference_request(s.id, wb.ctx)
    assert request['allowed_target']['ontology_id'] == 'procurement'
    assert request['allowed_target']['concept'] == 'PurchaseDocument'
    assert wb.intake.view(s.id, wb.ctx)['ontology']['id'] == 'procurement'


def test_unknown_target_is_rejected_at_start(tmp_path):
    data = Path(__file__).resolve().parents[2] / 'dataagent-data'
    wb = Workbench(tmp_path, layer_client=LayerClient(data))
    args = {'goal': '接入', 'sources': [{'source_id': 'f', 'kind': 'file', 'locator_ref': 'x.csv'}]}
    with pytest.raises(ValueError):
        invoke(wb, 'intake_start', {**args, 'target': {'ontology_id': 'nope'}})
    with pytest.raises(ValueError):
        invoke(wb, 'intake_start', {**args,
                                     'target': {'ontology_id': 'procurement', 'concept': 'nope'}})


def test_http_start_rejects_a_non_string_concept_with_422(tmp_path):
    """The HTTP target payload goes through the tool input contract (StartTarget)."""
    data = Path(__file__).resolve().parents[2] / 'dataagent-data'
    wb = Workbench(tmp_path, layer_client=LayerClient(data))
    client = TestClient(create_app(wb))
    headers = {'x-dataagent-token': wb.token}
    args = {'goal': '接入费用数据',
            'sources': [{'source_id': 'rows', 'kind': 'file', 'locator_ref': 'rows.csv'}]}
    response = client.post('/api/sessions', headers=headers,
                           json={**args, 'target': {'ontology_id': 'expense',
                                                    'concept': ['expense_standard']}})
    assert response.status_code == 422, response.text
    assert response.json()['error'] == 'invalid_input'
    # A well-formed target is still accepted and pinned like the tool path.
    wb.ontology.register(multi_concept_ontology(), wb.ctx)
    (tmp_path / 'rows.csv').write_text('number,city,amount\nR1,北京,500\n')
    created = client.post('/api/sessions', headers=headers,
                           json={**args, 'target': {'ontology_id': 'expense',
                                                    'concept': 'expense_standard'}})
    assert created.status_code == 200, created.text
    session = wb.intake.advance(created.json()['session_id'], wb.ctx)
    assert wb.intake.inference_request(session.id, wb.ctx)[ \
        'allowed_target']['concept'] == 'expense_standard'
