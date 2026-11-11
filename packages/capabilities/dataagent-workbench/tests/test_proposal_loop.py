from pathlib import Path
import pytest
from dataagent_contracts.intake import SourceSelection,WorkSpec
from dataagent_contracts.ontology import MappingSpec,ReviewDecision
from dataagent_runtime.ports.workbench_store import VersionConflict
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.adapters.layer_client import LayerClient


def setup(tmp_path,**kwargs):
    data=Path(__file__).resolve().parents[2]/'dataagent-data'
    wb=Workbench(tmp_path,layer_client=LayerClient(data),**kwargs)
    (tmp_path/'invoice.csv').write_text('number,amount_minor,currency\nINV-1,126000,CNY\n')
    goal=WorkSpec(id='g',goal='接入采购单',acceptance_criteria=['来源可核对'],authorization_ref=wb.authorization)
    handle=wb.sessions.start([SourceSelection(source_id='f',kind='file',locator_ref='invoice.csv')],goal,wb.ctx)
    return wb,wb.intake.advance(handle.session_id,wb.ctx)


def proposal(session,wb):
    request=wb.intake.inference_request(session.id,wb.ctx)
    return MappingSpec(id='candidate',revision='1',ontology_revision='procurement@1',
        source_fingerprint=request['sources'][0]['structure_fingerprint'],bindings={
        'number':{'source_field':'number'},'amount':{'source_field':'amount_minor','transform':'minor_to_major'},
        'currency':{'source_field':'currency'}})


def test_agent_proposal_is_validated_before_apply(tmp_path):
    wb,s=setup(tmp_path)
    assert s.phase=='needs_input'
    p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    assert p.instances[0].values['amount']==1260
    current=wb.sessions.get(s.id,wb.ctx)
    assert current.phase=='preview'
    assert not wb.store.query('release',wb.scope)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='mapping'),current.revision,wb.ctx)
    assert wb.sessions.get(s.id,wb.ctx).phase=='saved'
    assert wb.store.query('release',wb.scope)
    assert wb.store.current('job',current.job_ref,scope=wb.scope)['body']['state']=='completed'


def test_expired_preview_cannot_confirm_changed_mapping(tmp_path):
    wb,s=setup(tmp_path);m=proposal(s,wb)
    first=wb.intake.submit_proposal(s.id,m,s.revision,wb.ctx)
    old=wb.sessions.get(s.id,wb.ctx)
    wb.intake.submit_proposal(s.id,m,old.revision,wb.ctx)
    with pytest.raises(VersionConflict):
        wb.intake.apply(s.id,ReviewDecision(preview_ref=first.id+'@1',target_scope='mapping'),old.revision,wb.ctx)
    assert not wb.store.query('release',wb.scope)


def test_ui_correction_is_visible_to_agent(tmp_path):
    wb,s=setup(tmp_path)
    p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',changes={
        'entity_id':p.instances[0].id,'property':'amount','value':'1250','reason':'用户核对'}),s.revision,wb.ctx)
    updated=wb.intake.view(s.id,wb.ctx)
    assert updated['preview']['instances'][0]['values']['amount']=='1250'
    assert updated['preview']['review_state']=='needs_revalidation'


def test_known_source_reuses_mapping(tmp_path):
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    current=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='mapping'),current.revision,wb.ctx)
    goal=WorkSpec(id='g2',goal='再接入',acceptance_criteria=['来源可核对'],authorization_ref=wb.authorization)
    h=wb.sessions.start([SourceSelection(source_id='f2',kind='file',locator_ref='invoice.csv')],goal,wb.ctx)
    reused=wb.intake.advance(h.session_id,wb.ctx)
    assert reused.phase=='preview'
    assert wb.intake.view(reused.id,wb.ctx)['mapping_reused']


def test_disallowed_context_is_not_in_inference_request(tmp_path):
    wb,s=setup(tmp_path,allowed_model_fields={'f':['number']})
    request=wb.intake.inference_request(s.id,wb.ctx)
    assert request['sources'][0]['samples']==[{'number':'INV-1'}]
    assert 'amount_minor' not in request['sources'][0]['fields']
    assert '126000' not in str(request)


def test_mcp_advance_returns_valid_needs_input_and_filters_context(tmp_path):
    from dataagent_workbench.service_tools import invoke
    wb,s=setup(tmp_path,allowed_model_fields={'f':['number']})
    result=invoke(wb,'intake_inference',{'session_id':s.id})
    assert result.status.value=='needs_input'
    assert result.issues[0].inference_request['sources'][0]['samples']==[{'number':'INV-1'}]
    with pytest.raises(ValueError):
        invoke(wb,'intake_status',{'session_id':s.id,'subject_ref':'forged'})


def test_corrected_instance_revalidates_with_manual_evidence_then_saves(tmp_path):
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',changes={
        'entity_id':p.instances[0].id,'property':'amount','value':'1250','reason':'用户核对'}),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    revised=wb.intake.revalidate(s.id,s.revision,wb.ctx)
    assert revised.instances[0].values['amount']=='1250'
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=revised.id+'@'+revised.revision,target_scope='mapping'),s.revision,wb.ctx)
    assert wb.sessions.get(s.id,wb.ctx).phase=='saved'
    manual=[a for a in wb.store.query('assertion',wb.scope) if a['body']['extractor_version']=='user_correction']
    assert manual
    assert manual[0]['body']['source_anchors'][0]['source_ref']!= 'f'


def test_pending_draft_prevents_approval_of_older_mapping(tmp_path):
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    draft={**p.mapping.model_dump(mode='json')['bindings'],'amount':{'source_field':'amount_minor','transform':'identity'}}
    wb.intake.save_draft(s.id,{'bindings':draft},s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    with pytest.raises(VersionConflict):
        wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='mapping'),s.revision,wb.ctx)
    assert not wb.store.query('release',wb.scope)


def test_published_intake_rejects_further_writes_even_with_latest_revision(tmp_path):
    wb, initial = setup(tmp_path)
    mapping = proposal(initial, wb)
    preview = wb.intake.submit_proposal(initial.id, mapping, initial.revision, wb.ctx)
    active = wb.sessions.get(initial.id, wb.ctx)
    wb.intake.apply(initial.id, ReviewDecision(
        preview_ref=f'{preview.id}@{preview.revision}', target_scope='mapping'
    ), active.revision, wb.ctx)
    published = wb.sessions.get(initial.id, wb.ctx)
    release_ref = published.selected_versions['release']

    with pytest.raises(VersionConflict, match='saved'):
        wb.intake.submit_proposal(initial.id, mapping, published.revision, wb.ctx)
    with pytest.raises(VersionConflict, match='saved'):
        wb.intake.save_draft(initial.id, {'bindings': {}}, published.revision, wb.ctx)
    with pytest.raises(VersionConflict, match='saved'):
        wb.intake.apply(initial.id, ReviewDecision(
            preview_ref=published.selected_versions['preview'], target_scope='instance',
            changes={'entity_id': preview.instances[0].id, 'property': 'amount',
                     'value': '99', 'reason': 'late request'},
        ), published.revision, wb.ctx)

    current = wb.sessions.get(initial.id, wb.ctx)
    assert current.phase == 'saved'
    assert current.revision == published.revision
    assert current.selected_versions['release'] == release_ref
    assert wb.intake.view(initial.id, wb.ctx)['preview']['review_state'] == 'published'
