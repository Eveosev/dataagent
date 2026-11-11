from fastapi.testclient import TestClient
from dataagent_workbench.interfaces.http_api import create_app
from test_proposal_loop import setup,proposal


def test_http_uses_same_task_and_rejects_stale_draft(tmp_path):
    wb,s=setup(tmp_path);client=TestClient(create_app(wb));h={'x-dataagent-token':wb.token}
    view=client.get(f'/api/sessions/{s.id}/view',headers=h)
    assert view.status_code==200
    assert view.json()['profiles'][0]['records'][0]['amount_minor']=='126000'
    draft={'bindings':proposal(s,wb).model_dump(mode='json')['bindings'],'selected_field':'amount'}
    first=client.put(f'/api/sessions/{s.id}/draft',headers=h,json={'draft':draft,'expected_revision':s.revision})
    assert first.status_code==200,first.text
    stale=client.put(f'/api/sessions/{s.id}/draft',headers=h,json={'draft':{},'expected_revision':s.revision})
    assert stale.status_code==409
    assert client.get(f'/api/sessions/{s.id}/view',headers=h).json()['draft']['selected_field']=='amount'


def test_uploaded_file_is_scoped_and_source_read_requires_membership(tmp_path):
    from dataagent_workbench.bootstrap import Workbench
    from dataagent_workbench.adapters.layer_client import LayerClient
    from pathlib import Path
    wb=Workbench(tmp_path,layer_client=LayerClient(Path(__file__).resolve().parents[2]/'dataagent-data'))
    client=TestClient(create_app(wb));h={'x-dataagent-token':wb.token,'x-file-name':'in.csv'}
    uploaded=client.post('/api/files',headers=h,content=b'number,amount_minor,currency\nA,100,CNY\n')
    assert uploaded.status_code==200,uploaded.text
    selection=uploaded.json()
    created=client.post('/api/sessions',headers=h,json={'goal':'接入','sources':[selection]})
    sid=created.json()['session_id']
    advanced=client.post(f'/api/sessions/{sid}/advance',headers=h)
    assert advanced.status_code==200,advanced.text
    raw=client.get(f'/api/sessions/{sid}/sources/{selection["source_id"]}/raw',headers=h)
    assert b'A,100,CNY' in raw.content
    assert client.get(f'/api/sessions/{sid}/sources/not-selected/raw',headers=h).status_code==404


def test_pdf_page_preview_is_rendered_in_data_process(tmp_path):
    from dataagent_workbench.bootstrap import Workbench
    from dataagent_workbench.adapters.layer_client import LayerClient
    from pathlib import Path
    import shutil
    root=Path(__file__).resolve().parents[2]
    shutil.copy2(root/'dataagent-scenarios/fixtures/intake/invoice.pdf',tmp_path/'invoice.pdf')
    wb=Workbench(tmp_path,layer_client=LayerClient(root/'dataagent-data'))
    client=TestClient(create_app(wb));h={'x-dataagent-token':wb.token}
    created=client.post('/api/sessions',headers=h,json={'goal':'接入','sources':[{'source_id':'p','kind':'file','locator_ref':'invoice.pdf'}]})
    sid=created.json()['session_id'];client.post(f'/api/sessions/{sid}/advance',headers=h)
    image=client.get(f'/api/sessions/{sid}/sources/p/pages/1',headers=h)
    assert image.status_code==200,image.text
    assert image.content[:8]==b'\x89PNG\r\n\x1a\n'
    assert client.get(f'/api/sessions/{sid}/sources/p/pages/99',headers=h).status_code==422
