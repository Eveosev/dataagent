from pathlib import Path
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from dataagent_contracts.ontology import FieldBinding,MappingSpec,ReviewDecision
from dataagent_runtime.ports.workbench_store import VersionConflict
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.view_service import ViewService
from dataagent_workbench.interfaces.http_api import create_app
from test_proposal_loop import setup,proposal


def page(wb,session_id):
    return ViewService(wb).object_page(session_id,wb.ctx)


def preview_body(wb,session):
    preview_id,revision=session.selected_versions['preview'].rsplit('@',1)
    return wb.store.get('preview',preview_id,revision,scope=wb.scope)['body']


def fact_values(body,relation):
    return [str(role['value']) for fact in body.get('facts',[]) if fact.get('relation')==relation
            for role in fact.get('role_bindings',[]) if role.get('role')=='value']


def test_object_page_shows_values_and_source_positions(tmp_path):
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    body=page(wb,s.id)
    assert [o['id'] for o in body['objects']]==[p.instances[0].id]
    assert body['objects'][0]['values']=={'number':'INV-1','amount':'1260','currency':'CNY'}
    evidence=body['objects'][0]['evidence']
    assert evidence['amount'][0]['source_id']=='f'
    assert evidence['amount'][0]['selector']['keys']['row']==2
    assert evidence['number'][0]['selector']['field']=='number'
    assert body['mapping_revision'].endswith('@1')
    assert body['ontology_revision']=='procurement@1'
    assert body['ontology_draft'] is None
    assert body['sources'] and body['sources'][0]['source_id']=='f'
    assert 'currency' not in body['objects'][0]['unresolved']


def test_three_modification_scopes_from_object_page(tmp_path):
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    entity=p.instances[0].id
    # 当前值纠正：更新本对象候选结果并重验约束。
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',changes={
        'entity_id':entity,'property':'amount','value':'1250','reason':'用户核对'}),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.revalidate(s.id,s.revision,wb.ctx)
    corrected=page(wb,s.id)
    assert corrected['objects'][0]['values']['amount']=='1250'
    assert corrected['corrections']==[{'decision_ref':corrected['corrections'][0]['decision_ref'],
        'entity_id':entity,'property':'amount','value':'1250','reason':'用户核对'}]
    # 本体草案：只登记草案，正式本体不换修订。
    s=wb.sessions.get(s.id,wb.ctx)
    draft={'property':'issuer_type','value_type':'string','reason':'补充开票方类型'}
    wb.intake.apply(s.id,ReviewDecision(preview_ref=s.selected_versions['preview'],
        target_scope='ontology',changes=draft),s.revision,wb.ctx)
    drafted=page(wb,s.id)
    assert drafted['ontology_draft']==draft
    assert drafted['ontology_revision']=='procurement@1'
    assert 'issuer_type' not in drafted['ontology']['properties']
    assert wb.store.current('ontology','procurement',scope=wb.scope)['revision']=='1'
    # 映射修订：新 MappingSpec 修订重跑同类输入；网页纠正随新预览保留。
    s=wb.sessions.get(s.id,wb.ctx)
    from dataagent_contracts.ontology import FieldBinding
    revised=proposal(s,wb).model_copy(update={'bindings':{**proposal(s,wb).bindings,
        'amount':FieldBinding(source_field='amount_minor',transform='integer')}})
    wb.intake.submit_proposal(s.id,revised,s.revision,wb.ctx)
    remapped=page(wb,s.id)
    assert remapped['mapping_revision'].endswith('@2')
    assert remapped['objects'][0]['values']['amount']=='1250'
    assert [correction['property'] for correction in remapped['corrections']]==['amount']


def test_concurrent_chat_and_page_changes_reject_stale_decision_and_keep_draft(tmp_path):
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    entity=p.instances[0].id
    s=wb.sessions.get(s.id,wb.ctx)
    baseline=s.revision
    wb.intake.save_draft(s.id,{'bindings':p.mapping.model_dump(mode='json')['bindings'],
        'selected_field':'amount'},baseline,wb.ctx)
    # 页面保存草稿后，聊天一侧（Agent 工具同一任务）基于最新修订提交了决定。
    current=wb.sessions.get(s.id,wb.ctx).revision
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',changes={
        'entity_id':entity,'property':'currency','value':'USD','reason':'页面外修改'}),current,wb.ctx)
    # 页面以编辑开始时的基准修订提交，过期决定被拒绝，已保存的用户草稿仍在。
    with pytest.raises(VersionConflict):
        wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',changes={
            'entity_id':entity,'property':'amount','value':'1250','reason':'页面核对'}),baseline,wb.ctx)
    assert wb.store.current('ui_draft',s.id,scope=wb.scope)['body']['selected_field']=='amount'
    # 重新载入最新修订后页面可以再提交。
    fresh=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=fresh.selected_versions['preview'],
        target_scope='instance',
        changes={'entity_id':entity,'property':'amount','value':'1250','reason':'页面核对'}),fresh.revision,wb.ctx)


def test_object_page_restores_after_service_restart(tmp_path):
    wb,s=setup(tmp_path)
    partial=MappingSpec(id='candidate',revision='1',ontology_revision='procurement@1',
        source_fingerprint=wb.intake.inference_request(s.id,wb.ctx)['sources'][0]['structure_fingerprint'],
        bindings={'number':{'source_field':'number'},'amount':{'source_field':'amount_minor','transform':'minor_to_major'}})
    wb.intake.submit_proposal(s.id,partial,s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.save_draft(s.id,{'bindings':partial.model_dump(mode='json')['bindings'],
        'selected_field':'amount'},s.revision,wb.ctx)
    # 服务重启：同一工作区上新建 Workbench。
    data=Path(__file__).resolve().parents[2]/'dataagent-data'
    restarted=Workbench(tmp_path,layer_client=LayerClient(data))
    body=ViewService(restarted).object_page(s.id,restarted.ctx)
    assert [src['source_id'] for src in body['sources']]==['f']
    assert body['objects'][0]['values']['number']=='INV-1'
    assert 'currency' in body['objects'][0]['unresolved']
    assert any(i['code']=='ontology.required_binding_missing' for i in body['issues'])
    assert restarted.intake.view(s.id,restarted.ctx)['draft']['selected_field']=='amount'


def test_http_object_page_endpoint_and_stale_review(tmp_path):
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    client=TestClient(create_app(wb));h={'x-dataagent-token':wb.token}
    body=client.get(f'/api/sessions/{s.id}/objects',headers=h)
    assert body.status_code==200,body.text
    assert body.json()['objects'][0]['values']['amount']=='1260'
    assert body.json()['objects'][0]['evidence']['amount'][0]['selector']['keys']['row']==2
    stale=wb.sessions.get(s.id,wb.ctx).revision
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',changes={
        'entity_id':p.instances[0].id,'property':'amount','value':'1250','reason':'聊天侧修改'}),stale,wb.ctx)
    rejected=client.post(f'/api/sessions/{s.id}/review',headers=h,json={'expected_revision':stale,
        'decision':{'preview_ref':p.id+'@1','target_scope':'instance','changes':{
            'entity_id':p.instances[0].id,'property':'amount','value':'1240','reason':'页面修改'},'decision':'save'}})
    assert rejected.status_code==409
    assert client.get(f'/api/sessions/{s.id}/objects',headers=h).status_code==200


def corrected_amount(tmp_path):
    """One preview with a retained amount correction, ready for a mapping revision."""
    wb,s=setup(tmp_path);p=wb.intake.submit_proposal(s.id,proposal(s,wb),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=p.id+'@1',target_scope='instance',changes={
        'entity_id':p.instances[0].id,'property':'amount','value':'1250','reason':'用户核对'}),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.revalidate(s.id,s.revision,wb.ctx)
    return wb,wb.sessions.get(s.id,wb.ctx),p.instances[0].id


def test_mapping_revision_reports_retained_correction_and_adoption(tmp_path):
    wb,s,entity=corrected_amount(tmp_path)
    # A correction alone is not a conflict: the mapping has not changed.
    assert page(wb,s.id)['correction_views']==[]
    revised=proposal(s,wb).model_copy(update={'bindings':{**proposal(s,wb).bindings,
        'amount':FieldBinding(source_field='amount_minor',transform='integer')}})
    wb.intake.submit_proposal(s.id,revised,s.revision,wb.ctx)
    body=page(wb,s.id)
    # F2 retention stays: the corrected value is still the preview value.
    assert body['objects'][0]['values']['amount']=='1250'
    views=body['correction_views']
    assert len(views)==1
    assert views[0]['entity_id']==entity and views[0]['property']=='amount'
    assert Decimal(str(views[0]['value']))==Decimal('1250')
    assert Decimal(str(views[0]['mapping_value']))==Decimal('126000')
    assert views[0]['mapping_changed'] is True
    assert views[0]['mapping_revision'].endswith('@2')
    # The read-only preview endpoint exposes the same comparison.
    client=TestClient(create_app(wb));h={'x-dataagent-token':wb.token}
    preview=client.get(f'/api/sessions/{s.id}/view',headers=h)
    assert preview.status_code==200,preview.text
    assert preview.json()['correction_views'][0]['property']=='amount'
    # Adoption replaces the retained correction with one explicit decision and
    # rebuilds facts, so the old value cannot be published next to the new one.
    s=wb.sessions.get(s.id,wb.ctx)
    adopted_response=client.post(f'/api/sessions/{s.id}/corrections/adopt',headers=h,json={
        'expected_revision':s.revision,'entity_id':entity,'property':'amount'})
    assert adopted_response.status_code==200,adopted_response.text
    assert adopted_response.json()['mapping_value']=='126000'
    s=wb.sessions.get(s.id,wb.ctx)
    adopted=page(wb,s.id)
    assert adopted['objects'][0]['values']['amount']=='126000'
    assert adopted['correction_views']==[]
    assert [c['value'] for c in adopted['corrections']]==['126000']
    assert fact_values(preview_body(wb,s),'amount')==['126000']
    # Saving publishes the same single fact, not both historical decisions.
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=s.selected_versions['preview'],
        target_scope='mapping'),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    assert s.phase=='saved'
    saved=preview_body(wb,s)
    assert saved['review_state']=='published'
    assert fact_values(saved,'amount')==['126000']
    release_ref=s.selected_versions.get('release')
    assert release_ref
    release_id,release_revision=release_ref.rsplit('@',1)
    release=wb.store.get('release',release_id,release_revision,scope=wb.scope)
    assert release['body']['digest']==saved['digest']


def test_mapping_revision_for_another_property_keeps_correction_unflagged(tmp_path):
    wb,s,_=corrected_amount(tmp_path)
    # The mapping revision changed, but amount's source value did not.
    revised=proposal(s,wb).model_copy(update={'bindings':{**proposal(s,wb).bindings,
        'issuer':FieldBinding(source_field='number',transform='identity')}})
    wb.intake.submit_proposal(s.id,revised,s.revision,wb.ctx)
    body=page(wb,s.id)
    assert body['mapping_revision'].endswith('@2')
    assert body['objects'][0]['values']['amount']=='1250'
    assert body['correction_views']==[]


def test_adoption_keeps_only_latest_fact_for_repeated_corrections(tmp_path):
    wb,s,entity=corrected_amount(tmp_path)
    # Two live corrections for one property reproduce the duplicate facts that
    # adoption used to leave behind (1250 survives next to 126000).
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.apply(s.id,ReviewDecision(preview_ref=s.selected_versions['preview'],
        target_scope='instance',changes={'entity_id':entity,'property':'amount','value':'126000',
        'reason':'第二次纠正'}),s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    wb.intake.revalidate(s.id,s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    assert fact_values(preview_body(wb,s),'amount')==['1250','126000']
    revised=proposal(s,wb).model_copy(update={'bindings':{**proposal(s,wb).bindings,
        'amount':FieldBinding(source_field='amount_minor',transform='integer')}})
    wb.intake.submit_proposal(s.id,revised,s.revision,wb.ctx)
    s=wb.sessions.get(s.id,wb.ctx)
    client=TestClient(create_app(wb));h={'x-dataagent-token':wb.token}
    response=client.post(f'/api/sessions/{s.id}/corrections/adopt',headers=h,json={
        'expected_revision':s.revision,'entity_id':entity,'property':'amount'})
    assert response.status_code==200,response.text
    s=wb.sessions.get(s.id,wb.ctx)
    body=preview_body(wb,s)
    assert fact_values(body,'amount')==['126000']
    assert [c['value'] for c in body['corrections']]==['126000']
    assert body['review_state']=='unreviewed'
