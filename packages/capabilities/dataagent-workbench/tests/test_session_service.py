import pytest
from dataagent_contracts.intake import SourceSelection, WorkSpec
from dataagent_workbench.bootstrap import Workbench
from dataagent_runtime.ports.workbench_store import VersionConflict


def start(wb):
    return wb.sessions.start([SourceSelection(source_id='f',kind='file',locator_ref='invoice.csv')],
        WorkSpec(id='goal',goal='接入发票',acceptance_criteria=['来源可核对'],authorization_ref=wb.ctx.authorization_ref),wb.ctx)


def test_restart_retains_session_and_pending_points_to_persisted_job(tmp_path):
    wb=Workbench(tmp_path)
    handle=start(wb)
    session=Workbench(tmp_path).sessions.get(handle.session_id,wb.ctx)
    assert session.sources[0].locator_ref=='invoice.csv'
    job=wb.store.current('job',session.job_ref,scope=wb.scope)
    assert job['body']['state']=='queued'
    assert job['body']['session_id']==handle.session_id
    assert wb.sessions.events(handle.session_id,0,wb.ctx).items[0]['type']=='intake.created'


def test_concurrent_edit_returns_version_conflict(tmp_path):
    wb=Workbench(tmp_path)
    handle=start(wb)
    wb.sessions.update(handle.session_id,'1',{'phase':'probing'},wb.ctx)
    with pytest.raises(VersionConflict):
        wb.sessions.update(handle.session_id,'1',{'phase':'saved'},wb.ctx)
    assert wb.sessions.get(handle.session_id,wb.ctx).phase=='probing'


def test_forged_context_cannot_read_source_or_change_subject(tmp_path):
    wb=Workbench(tmp_path)
    handle=start(wb)
    for change in [{'subject_ref':'user:other'}, {'scope_ref':'other'}, {'authorization_ref':'invented'}]:
        with pytest.raises(PermissionError):
            wb.sessions.get(handle.session_id,wb.ctx.model_copy(update=change))


def test_untrusted_browser_cannot_read_source(tmp_path):
    from fastapi.testclient import TestClient
    from dataagent_workbench.interfaces.http_api import create_app
    wb=Workbench(tmp_path)
    handle=start(wb)
    client=TestClient(create_app(wb))
    path=f'/api/sessions/{handle.session_id}'
    assert client.get(path).status_code==401
    assert client.get(path,headers={'x-dataagent-token':wb.token,'origin':'https://evil.example'}).status_code==403
    assert client.get(path,headers={'x-dataagent-token':wb.token}).json()['id']==handle.session_id
    assert wb.token not in client.get('/health').text
