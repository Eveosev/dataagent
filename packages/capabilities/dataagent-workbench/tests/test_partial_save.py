"""Partial save, conflict values, tool schema and correction inheritance (FDE-3/4/5)."""
import json
from decimal import Decimal

import pytest

from dataagent_contracts.ontology import MappingSpec, ReviewDecision
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.intake_service import PreviewBlocked
from dataagent_workbench.interfaces.mcp_server import handle
from dataagent_workbench.service_tools import invoke
from dataagent_workbench.tool_schema import MODELS
from dataagent_workbench.view_service import ViewService
from test_intake_repairs import StubProbeClient, csv_profile, start

BINDINGS = {'number': {'source_field': 'number'},
            'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'},
            'currency': {'source_field': 'currency'}}


def proposals_for(wb, session):
    request = wb.intake.inference_request(session.id, wb.ctx)
    return {source['source_id']: MappingSpec(
        id='candidate', revision='1', ontology_revision='procurement@1',
        source_fingerprint=source['structure_fingerprint'], bindings=BINDINGS)
        for source in request['sources']}


def conflict_and_keyless_setup(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({
        'a': csv_profile('a', [
            {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'},
            {'number': 'INV-2', 'amount_minor': '20000', 'currency': 'CNY'},
            {'amount_minor': '30000', 'currency': 'CNY'},
        ]),
        'b': csv_profile('b', [
            {'number': 'INV-2', 'amount_minor': '99900', 'currency': 'CNY'},
            {'number': 'INV-3', 'amount_minor': '40000', 'currency': 'CNY'},
        ]),
    })
    session = wb.intake.advance(start(wb, [
        _selection('a', 'a.csv'), _selection('b', 'b.csv')]).session_id, wb.ctx)
    preview = wb.intake.submit_source_proposals(
        session.id, proposals_for(wb, session), session.revision, wb.ctx)
    return wb, session.id, preview


def _selection(source_id, locator):
    from dataagent_contracts.intake import SourceSelection
    return SourceSelection(source_id=source_id, kind='file', locator_ref=locator)


def _apply(wb, session_id, preview, **kwargs):
    session = wb.sessions.get(session_id, wb.ctx)
    return wb.intake.apply(session_id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='mapping'),
        session.revision, wb.ctx, **kwargs)


def test_default_save_is_still_blocked_and_names_conflicts(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    with pytest.raises(PreviewBlocked) as blocked:
        _apply(wb, session_id, preview)
    assert str(blocked.value) == 'preview contains unresolved issues'
    assert any(issue['object'] == 'INV-2' and issue['target'] == 'amount'
               for issue in blocked.value.issues)
    assert wb.sessions.get(session_id, wb.ctx).phase == 'preview'


def test_partial_save_saves_clean_objects_and_lists_suspended_and_keyless(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    result = invoke(wb, 'mapping_apply', {
        'session_id': session_id,
        'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
        'decision': {'preview_ref': preview.id + '@' + preview.revision,
                     'target_scope': 'mapping'},
        'allow_partial': True,
        'reason': '先保存可确认的单据，冲突和缺键记录挂起',
    }).data

    assert result['partial'] is True
    assert {item['object'] for item in result['saved']} == {'INV-1', 'INV-3'}
    suspended, = result['suspended']
    assert suspended['object'] == 'INV-2'
    assert {reason['code'] for reason in suspended['reasons']} >= {'ontology.conflicting_values'}
    unidentified, = result['unidentified_records']
    assert unidentified['reason'] == '缺少单据号，无法确定对象'
    assert unidentified['sources'][0]['source_id'] == 'a'
    assert result['release_ref'].startswith('release:')
    assert result['subject_ref'] == wb.subject and result['recorded_at']
    assert result['reason'] == '先保存可确认的单据，冲突和缺键记录挂起'

    status = wb.sessions.get(session_id, wb.ctx)
    assert status.phase == 'saved'
    assert status.selected_versions['release'] == result['release_ref']
    current_id, current_revision = status.selected_versions['preview'].rsplit('@', 1)
    stored = wb.store.get('preview', current_id, current_revision, scope=wb.scope)['body']
    audit, = stored['partial_save']
    assert audit['reason'] == result['reason']
    assert audit['subject_ref'] == wb.subject
    assert {item['object'] for item in audit['saved']} == {'INV-1', 'INV-3'}
    assert stored['review_state'] == 'partially_published'
    assert stored['suspended'][0]['object'] == 'INV-2'
    assert stored['unidentified_records'][0]['entity_id'] == unidentified['entity_id']

    # The release only carries the saved objects: no fact has the suspended
    # object as its subject.
    suspended_ids = {item['entity_id'] for item in result['suspended']}
    saved_ids = {item['entity_id'] for item in result['saved']}
    subjects = {role['value'] for fact in wb.store.query('fact', wb.scope)
                for role in fact['body']['role_bindings']
                if role['role'] == 'subject' and role['value_type'] == 'reference'}
    assert saved_ids <= subjects
    assert not suspended_ids & subjects

    reviews = [row for row in wb.store.query('review', wb.scope)
               if row['body'].get('partial_save')]
    assert reviews and reviews[0]['body']['subject_ref'] == wb.subject
    assert reviews[0]['body']['recorded_at']


def test_partial_save_without_issues_falls_back_to_a_full_save(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'a': csv_profile('a', [
        {'number': 'INV-1', 'amount_minor': '10000', 'currency': 'CNY'}])})
    session = wb.intake.advance(start(wb, [_selection('a', 'a.csv')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(
        session.id, proposals_for(wb, session)['a'], session.revision, wb.ctx)
    result = invoke(wb, 'mapping_apply', {
        'session_id': session.id,
        'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
        'decision': {'preview_ref': preview.id + '@' + preview.revision,
                     'target_scope': 'mapping'},
        'allow_partial': True,
    }).data
    assert not result.get('partial')
    assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'


def test_instance_correction_error_names_entity_id_and_schema_is_explicit(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    entity = preview.instances[0].id
    session = wb.sessions.get(session_id, wb.ctx)
    with pytest.raises(ValueError, match='entity_id, not entity'):
        wb.intake.apply(session_id, ReviewDecision(
            preview_ref=preview.id + '@' + preview.revision, target_scope='instance',
            changes={'entity': entity, 'property': 'amount', 'value': '1', 'reason': 'x'}),
            session.revision, wb.ctx)

    schema = MODELS['mapping_apply'].model_json_schema()
    decision = schema['properties']['decision']
    assert 'oneOf' in decision
    serialized = json.dumps(schema, ensure_ascii=False)
    assert 'entity_id' in serialized and 'entity/property/value/reason' not in serialized
    assert 'allow_partial' in schema['properties']

    response = handle(wb, {'method': 'tools/call', 'params': {
        'name': 'mapping_apply', 'arguments': {
            'session_id': session_id,
            'expected_revision': wb.sessions.get(session_id, wb.ctx).revision,
            'decision': {'preview_ref': preview.id + '@' + preview.revision,
                         'target_scope': 'instance',
                         'changes': {'entity': entity, 'property': 'amount',
                                     'value': '1', 'reason': 'x'}}}}})
    payload = json.loads(response['content'][0]['text'])
    assert response['isError'] is True
    assert 'entity_id' in payload['detail']


def test_conflict_values_and_sources_reach_preview_and_object_page(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    summary = invoke(wb, 'mapping_preview', {'session_id': session_id}).data
    conflict, = [item for item in summary['conflicts'] if item['field'] == 'amount']
    assert conflict['object'] == 'INV-2'
    values = {item['source_id']: item['value'] for item in conflict['values']}
    assert {key: Decimal(str(value)) for key, value in values.items()} == {
        'a': Decimal('200'), 'b': Decimal('999')}
    assert {item['source_name'] for item in conflict['values']} == {'a.csv', 'b.csv'}
    assert all(item['locations'] for item in conflict['values'])
    issue = next(item for item in summary['issues']
                 if item['object'] == 'INV-2' and item['target'] == 'amount')
    assert {item['source_id'] for item in issue['values']} == {'a', 'b'}

    page = ViewService(wb).object_page(session_id, wb.ctx)
    object_ = next(item for item in page['objects'] if item['values'].get('number') == 'INV-2')
    assert object_['conflicts'][0]['field'] == 'amount'
    assert {item['source_id'] for item in object_['conflicts'][0]['values']} == {'a', 'b'}
    assert page['conflicts']


def test_inherit_old_task_corrections_on_the_same_source_revision(tmp_path):
    wb = Workbench(tmp_path)
    profiles = {
        'a': csv_profile('a', [{'number': 'INV-1', 'amount_minor': '10000',
                                'currency': 'CNY'}]),
        'b': csv_profile('b', [{'number': 'INV-1', 'amount_minor': '20000',
                                'currency': 'CNY'}]),
    }
    wb.layer_client = StubProbeClient(profiles)

    first = wb.intake.advance(start(wb, [_selection('a', 'a.csv'), _selection('b', 'b.csv')],
                                    'g1').session_id, wb.ctx)
    preview = wb.intake.submit_source_proposals(
        first.id, proposals_for(wb, first), first.revision, wb.ctx)
    first = wb.sessions.get(first.id, wb.ctx)
    entity = preview.instances[0].id
    wb.intake.apply(first.id, ReviewDecision(
        preview_ref=preview.id + '@' + preview.revision, target_scope='instance',
        changes={'entity_id': entity, 'property': 'amount', 'value': '150.00',
                 'reason': '按发票原件核对'}), first.revision, wb.ctx)
    first = wb.sessions.get(first.id, wb.ctx)
    wb.intake.revalidate(first.id, first.revision, wb.ctx)
    first = wb.sessions.get(first.id, wb.ctx)
    wb.intake.apply(first.id, ReviewDecision(
        preview_ref=first.selected_versions['preview'], target_scope='mapping'),
        first.revision, wb.ctx)
    assert wb.sessions.get(first.id, wb.ctx).phase == 'saved'

    second = wb.intake.advance(start(wb, [_selection('a', 'a.csv'), _selection('b', 'b.csv')],
                                    'g2').session_id, wb.ctx)
    # Reusing the saved mapping recreates the conflict; the previous task's
    # correction is offered as an explicit inheritance.
    second = wb.sessions.get(second.id, wb.ctx)
    assert second.phase == 'preview'
    hint = wb.intake.view(second.id, wb.ctx)['inheritance']
    assert hint['count'] == 1
    assert hint['message'] == '旧任务有 1 处纠正，可继承'
    assert hint['corrections'][0]['property'] == 'amount'

    result = invoke(wb, 'intake_inherit', {
        'session_id': second.id, 'expected_revision': second.revision}).data
    assert result['inherited_count'] == 1
    assert result['inherited'][0]['value'] == '150.00' or result['inherited'][0]['value'] == 150.0
    current = wb.intake.view(second.id, wb.ctx)
    instance, = current['preview']['instances']
    assert instance['values']['amount'] == '150.00'
    assert not any(issue['code'] == 'ontology.conflicting_values'
                   for issue in current['preview']['issues'])
    assert current['inheritance'] is None

    current = wb.sessions.get(second.id, wb.ctx)
    wb.intake.apply(second.id, ReviewDecision(
        preview_ref=current.selected_versions['preview'], target_scope='mapping'),
        current.revision, wb.ctx)
    assert wb.sessions.get(second.id, wb.ctx).phase == 'saved'
