"""HTTP routes for source dispositions and partial save (B1).

The service layer already implemented both; these tests pin the HTTP
contract: dispositions ride the same local token as every other /api
route, blank reasons and stale revisions are rejected, the next proposal
after a disposition clears the issue, and /review passes allow_partial
and reason through so only unblocked objects are released.
"""
from fastapi.testclient import TestClient

from dataagent_contracts.intake import SourceSelection
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app
from test_disposition_tools import blank_page_profile, proposal_for_source
from test_intake_repairs import StubProbeClient, csv_profile, start
from test_partial_save import conflict_and_keyless_setup


def _client(wb):
    return TestClient(create_app(wb)), {'x-dataagent-token': wb.token}


def _dispose_body(wb, sid, **overrides):
    body = {'expected_revision': wb.sessions.get(sid, wb.ctx).revision,
            'action': 'partition_not_applicable', 'source_id': 'doc',
            'partition': 2, 'reason': '第 2 页为空白页，用户确认无需补录'}
    body.update(overrides)
    return body


def _blank_page_session(tmp_path):
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'doc': blank_page_profile()})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='doc', kind='file', locator_ref='mixed.pdf')]).session_id, wb.ctx)
    return wb, session


def test_dispositions_route_requires_the_local_token(tmp_path):
    wb = Workbench(tmp_path)
    client = TestClient(create_app(wb))
    assert client.post('/api/sessions/any/dispositions',
                       json={}).status_code == 401


def test_http_disposition_rejects_blank_reason_without_writing(tmp_path):
    wb, session = _blank_page_session(tmp_path)
    client, h = _client(wb)
    rejected = client.post(f'/api/sessions/{session.id}/dispositions', headers=h,
                           json=_dispose_body(wb, session.id, reason=' \t '))
    assert rejected.status_code == 422
    assert rejected.json()['error'] == 'invalid_input'
    assert '处置原因不能为空' in rejected.json()['detail']
    assert not wb.store.query('disposition', wb.scope)


def test_http_disposition_rejects_stale_revision(tmp_path):
    wb, session = _blank_page_session(tmp_path)
    client, h = _client(wb)
    stale = client.post(f'/api/sessions/{session.id}/dispositions', headers=h,
                        json=_dispose_body(wb, session.id, expected_revision='0'))
    assert stale.status_code == 409
    assert stale.json()['error'] == 'version_conflict'
    assert not wb.store.query('disposition', wb.scope)


def test_http_partition_disposition_clears_incomplete_source_after_reproposal(tmp_path):
    wb, session = _blank_page_session(tmp_path)
    preview = wb.intake.submit_proposal(session.id, proposal_for_source(wb, session, 'doc'),
                                        session.revision, wb.ctx)
    assert any(issue['code'] == 'ontology.incomplete_source' for issue in preview.issues)
    client, h = _client(wb)
    posted = client.post(f'/api/sessions/{session.id}/dispositions', headers=h,
                         json=_dispose_body(wb, session.id))
    assert posted.status_code == 200, posted.text
    result = posted.json()
    assert result['entry']['partition'] == 2
    assert result['entry']['reason'].startswith('第 2 页')
    assert result['entry']['subject_ref'] == wb.subject
    assert result['disposition_ref'].startswith(session.id + '@')
    assert wb.sessions.get(session.id, wb.ctx).phase == 'needs_input'

    disposed = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(disposed.id, proposal_for_source(wb, disposed, 'doc'),
                                        disposed.revision, wb.ctx)
    assert not any(issue['code'] == 'ontology.incomplete_source'
                   for issue in preview.issues)


def test_http_exclude_record_disposition_removes_the_header_row(tmp_path):
    profile = csv_profile('ledger', [
        {'number': 'number', 'amount_minor': 'amount_minor', 'currency': 'currency'},
        {'number': 'INV-9', 'amount_minor': '90000', 'currency': 'CNY'},
    ])
    wb = Workbench(tmp_path)
    wb.layer_client = StubProbeClient({'ledger': profile})
    session = wb.intake.advance(start(wb, [SourceSelection(
        source_id='ledger', kind='file', locator_ref='ledger.csv')]).session_id, wb.ctx)
    preview = wb.intake.submit_proposal(session.id, proposal_for_source(wb, session, 'ledger'),
                                        session.revision, wb.ctx)
    assert preview.issues
    client, h = _client(wb)
    posted = client.post(f'/api/sessions/{session.id}/dispositions', headers=h, json={
        'expected_revision': wb.sessions.get(session.id, wb.ctx).revision,
        'action': 'exclude_record', 'source_id': 'ledger', 'record': 0,
        'reason': '第 1 行是表头，不是单据'})
    assert posted.status_code == 200, posted.text
    assert posted.json()['entry']['record'] == 0
    assert posted.json()['entry']['record_values']['number'] == 'number'

    disposed = wb.sessions.get(session.id, wb.ctx)
    preview = wb.intake.submit_proposal(disposed.id, proposal_for_source(wb, disposed, 'ledger'),
                                        disposed.revision, wb.ctx)
    assert preview.issues == []
    assert [instance.values['number'] for instance in preview.instances] == ['INV-9']


def test_http_review_allow_partial_saves_only_unblocked_objects(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    client, h = _client(wb)
    decision = {'decision': {'preview_ref': preview.id + '@' + preview.revision,
                             'target_scope': 'mapping'},
                'expected_revision': wb.sessions.get(session_id, wb.ctx).revision}
    blocked = client.post(f'/api/sessions/{session_id}/review', headers=h, json=decision)
    assert blocked.status_code == 422
    assert blocked.json()['error'] == 'invalid_input'

    saved = client.post(f'/api/sessions/{session_id}/review', headers=h, json={
        **decision, 'allow_partial': True, 'reason': '先保存可确认的单据，冲突和缺键记录挂起'})
    assert saved.status_code == 200, saved.text
    # The partial-save audit is flattened to top level, matching mapping_apply.
    result = saved.json()
    assert result['partial'] is True
    assert {item['object'] for item in result['saved']} == {'INV-1', 'INV-3'}
    suspended, = result['suspended']
    assert suspended['object'] == 'INV-2'
    assert {reason['code'] for reason in suspended['reasons']} >= {'ontology.conflicting_values'}
    unidentified, = result['unidentified_records']
    assert unidentified['reason'] == '缺少单据号，无法确定对象'
    assert result['reason'] == '先保存可确认的单据，冲突和缺键记录挂起'
    assert result['subject_ref'] == wb.subject and result['recorded_at']
    assert result['release_ref'].startswith('release:')

    status = client.get(f'/api/sessions/{session_id}', headers=h).json()
    assert status['phase'] == 'saved'
    assert status['selected_versions']['release'] == result['release_ref']
    # Only the unblocked objects are released: no fact names the suspended object.
    suspended_ids = {item['entity_id'] for item in result['suspended']}
    subjects = {role['value'] for fact in wb.store.query('fact', wb.scope)
                for role in fact['body']['role_bindings']
                if role['role'] == 'subject' and role['value_type'] == 'reference'}
    assert not suspended_ids & subjects


def test_http_review_rejects_non_boolean_allow_partial_without_saving(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    client, h = _client(wb)
    decision = {'decision': {'preview_ref': preview.id + '@' + preview.revision,
                             'target_scope': 'mapping'},
                'expected_revision': wb.sessions.get(session_id, wb.ctx).revision}
    for bad in ('false', 'true', 1, 0, [True]):
        rejected = client.post(f'/api/sessions/{session_id}/review', headers=h,
                               json={**decision, 'allow_partial': bad})
        assert rejected.status_code == 422, bad
        assert rejected.json()['error'] == 'invalid_input'
    reason = client.post(f'/api/sessions/{session_id}/review', headers=h,
                         json={**decision, 'reason': 7})
    assert reason.status_code == 422
    assert not wb.store.query('release', wb.scope)
    assert wb.sessions.get(session_id, wb.ctx).phase == 'preview'


def test_http_review_and_dispositions_reject_non_object_bodies(tmp_path):
    wb, session_id, preview = conflict_and_keyless_setup(tmp_path)
    client, h = _client(wb)
    assert client.post(f'/api/sessions/{session_id}/review', headers=h,
                       json=[1, 2]).status_code == 422
    assert client.post(f'/api/sessions/{session_id}/dispositions', headers=h,
                       json=[1]).status_code == 422
    assert not wb.store.query('release', wb.scope)
    assert not wb.store.query('disposition', wb.scope)
