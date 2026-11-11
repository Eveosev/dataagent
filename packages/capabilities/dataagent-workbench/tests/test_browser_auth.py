from urllib.parse import urlsplit,parse_qs
from fastapi.testclient import TestClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app


def test_browser_credential_is_not_a_workspace_file_and_restart_binds_same_owner(tmp_path):
    first=Workbench(tmp_path);second=Workbench(tmp_path)
    assert first.token!=second.token
    assert first.authorization==second.authorization
    assert not (tmp_path/'.dataagent/runtime/workbench.token').exists()
    assert all(first.token not in p.read_text(errors='ignore') for p in (tmp_path/'.dataagent').rglob('*') if p.is_file())


def test_browser_launch_exchanges_nonce_once_without_returning_credential(tmp_path,monkeypatch):
    wb=Workbench(tmp_path);opened=[]
    monkeypatch.setattr('webbrowser.open',lambda url:opened.append(url))
    client=TestClient(create_app(wb))
    launch=client.post('/local/open',json={})
    assert launch.status_code==200
    assert wb.token not in launch.text
    nonce=parse_qs(urlsplit(opened[0]).fragment)['nonce'][0]
    exchange=client.post('/api/auth',json={'nonce':nonce})
    assert exchange.status_code==200
    assert wb.token not in exchange.text
    assert 'HttpOnly' in exchange.headers['set-cookie']
    assert client.get('/api/identity').status_code==200
    assert client.post('/api/auth',json={'nonce':nonce}).status_code==401
    attacker=TestClient(create_app(wb))
    assert attacker.post('/local/open',headers={'origin':'https://evil.example'},json={}).status_code==403
