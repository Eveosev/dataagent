import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from dataagent_contracts.intake import SourceProfile, SourceSelection
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.adapters import layer_client
from dataagent_workbench.adapters.layer_client import LayerClient


def test_probe_uses_independent_data_interpreter_and_retains_anchors(tmp_path):
    wb=Workbench(tmp_path);(tmp_path/'input.csv').write_text('number,total\nINV-1,126000\n')
    data=Path(__file__).resolve().parents[2]/'dataagent-data'
    profile=LayerClient(data).probe(SourceSelection(source_id='f',kind='file',locator_ref='input.csv'),wb.ctx,tmp_path)
    assert profile.records[0]['total']=='126000'
    assert profile.anchors['0.total'][0].selector.field=='total'
    assert profile.metadata['worker_pid']!=os.getpid()
    assert 'dataagent_data' not in __import__('sys').modules


def test_missing_worker_does_not_return_empty_success(tmp_path):
    wb=Workbench(tmp_path)
    with pytest.raises(ValueError,match='data layer'):
        LayerClient(tmp_path/'missing').probe(SourceSelection(source_id='f',kind='file',locator_ref='x.csv'),wb.ctx,tmp_path)


def test_probe_passes_logical_credential_names_only(tmp_path, monkeypatch):
    sentinel='T14-SENTINEL-5f0c9a7d2b8e4c61'
    monkeypatch.setenv('T14_SENTINEL_TOKEN',sentinel)
    config=tmp_path/'connections.json'
    config.write_text(json.dumps({'accounting':{
        'kind':'rest','locator':'http://127.0.0.1:9999/invoices',
        'allowed_origins':['http://127.0.0.1:9999'],'options':{'records_path':'/items'},
        'credential_options':{'auth':'bearer'},
        'credential_refs':{'token':'env:T14_SENTINEL_TOKEN'},
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS',str(config))
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    captured={}
    def fake_run(argv,**kwargs):
        captured['input']=kwargs['input']
        captured['env']=kwargs['env']
        captured['preexec_fn']=kwargs.get('preexec_fn')
        directory=tmp_path/'.dataagent/results';directory.mkdir(parents=True)
        profile=SourceProfile(source_id='api',source_revision='sha256:'+'0'*64,kind='rest',
            records=[{'/id':1}],fields=['/id'],anchors={},total_partitions=1,
            completed_partitions=[1],metadata={'structure_fingerprint':'sha256:'+'1'*64})
        (directory/'probe-test.json').write_text(profile.model_dump_json())
        return SimpleNamespace(returncode=0,stderr='',stdout=json.dumps({'result_path':'.dataagent/results/probe-test.json'}))
    monkeypatch.setattr('dataagent_workbench.adapters.layer_client.subprocess.run',fake_run)
    wb=Workbench(tmp_path)
    profile=LayerClient(tmp_path).probe(SourceSelection(source_id='api',kind='rest',locator_ref='accounting'),wb.ctx,tmp_path)
    payload=json.loads(captured['input'])
    assert payload['credential_refs']=={'token':'env:T14_SENTINEL_TOKEN'}
    assert payload['credential_options']=={'auth':'bearer'}
    assert 'credentials' not in payload
    assert sentinel not in captured['input']
    assert captured['env'] is None
    assert callable(captured['preexec_fn'])
    assert profile.records==[{'/id':1}]


def test_probe_rejects_plaintext_in_forwarded_selection_options(tmp_path):
    wb=Workbench(tmp_path)
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    selection=SourceSelection(source_id='f',kind='file',locator_ref='x.csv',
                              options={'token':'T14-EXAMPLE'})
    with pytest.raises(ValueError,match='credential'):
        LayerClient(tmp_path).probe(selection,wb.ctx,tmp_path)


def test_probe_child_environment_drops_unrelated_variables(monkeypatch):
    monkeypatch.setattr(layer_client.os, 'environ', {
        'PATH': '/bin', 'T14_SENTINEL_TOKEN': 'sentinel', 'UNRELATED_SECRET': 'other',
    })
    layer_client._clean_child_environment({'PATH', 'T14_SENTINEL_TOKEN'})
    assert set(layer_client.os.environ) == {'PATH', 'T14_SENTINEL_TOKEN'}


def test_probe_forwards_budget_and_segment_settings(tmp_path, monkeypatch):
    monkeypatch.setenv('DATAAGENT_PROBE_ROW_BUDGET', '4000')
    monkeypatch.setenv('DATAAGENT_PROBE_SEGMENT_ROWS', '500')
    monkeypatch.setenv('DATAAGENT_PROBE_SEGMENT_PAGES', '3')
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    captured={}
    def fake_run(argv,**kwargs):
        captured['input']=json.loads(kwargs['input'])
        captured['timeout']=kwargs['timeout']
        directory=tmp_path/'.dataagent/results';directory.mkdir(parents=True)
        profile=SourceProfile(source_id='f',source_revision='sha256:'+'0'*64,kind='csv',
            records=[{'number':'INV-1'}],fields=['number'],anchors={},total_partitions=1,
            completed_partitions=[1],metadata={'structure_fingerprint':'sha256:'+'1'*64})
        (directory/'probe-test.json').write_text(profile.model_dump_json())
        return SimpleNamespace(returncode=0,stderr='',stdout=json.dumps({'result_path':'.dataagent/results/probe-test.json'}))
    monkeypatch.setattr('dataagent_workbench.adapters.layer_client.subprocess.run',fake_run)
    wb=Workbench(tmp_path)
    LayerClient(tmp_path).probe(SourceSelection(source_id='f',kind='file',locator_ref='x.csv'),
        wb.ctx,tmp_path,budget_seconds=12.5)
    assert captured['input']['budget_rows']==4000
    assert captured['input']['segment_rows']==500
    assert captured['input']['segment_pages']==3
    assert captured['input']['budget_seconds']==12.5
    assert captured['timeout']==13.0


def test_probe_failure_payload_preserves_code_for_local_sources(tmp_path, monkeypatch):
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    def fake_run(argv,**kwargs):
        return SimpleNamespace(returncode=2,stderr='',
            stdout=json.dumps({'status':'failed','error':{
                'code':'dependency_missing','detail':'python-docx is not installed',
                'retryable':False}}))
    monkeypatch.setattr('dataagent_workbench.adapters.layer_client.subprocess.run',fake_run)
    wb=Workbench(tmp_path)
    with pytest.raises(layer_client.DataLayerProbeError) as exc:
        LayerClient(tmp_path).probe(SourceSelection(source_id='f',kind='file',
            locator_ref='x.docx'),wb.ctx,tmp_path)
    assert exc.value.code=='dependency_missing'
    assert exc.value.retryable is False
    assert 'python-docx is not installed' in exc.value.detail


def test_probe_failure_payload_hides_remote_detail(tmp_path, monkeypatch):
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    def fake_run(argv,**kwargs):
        return SimpleNamespace(returncode=2,stderr='',
            stdout=json.dumps({'status':'failed','error':{
                'code':'authentication_failed','detail':'token abc at internal-host',
                'retryable':False}}))
    monkeypatch.setattr('dataagent_workbench.adapters.layer_client.subprocess.run',fake_run)
    config=tmp_path/'connections.json'
    config.write_text(json.dumps({'api':{'kind':'rest','locator':'http://127.0.0.1:9/items',
        'allowed_origins':['http://127.0.0.1:9'],'options':{}}}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS',str(config))
    wb=Workbench(tmp_path)
    with pytest.raises(layer_client.DataLayerProbeError) as exc:
        LayerClient(tmp_path).probe(SourceSelection(source_id='api',kind='rest',
            locator_ref='api'),wb.ctx,tmp_path)
    assert exc.value.code=='authentication_failed'
    assert 'internal-host' not in exc.value.detail


def test_probe_failure_without_json_still_has_a_code(tmp_path, monkeypatch):
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    monkeypatch.setattr('dataagent_workbench.adapters.layer_client.subprocess.run',
        lambda *args, **kwargs: SimpleNamespace(returncode=2,stderr='traceback',stdout=''))
    wb=Workbench(tmp_path)
    with pytest.raises(layer_client.DataLayerProbeError) as exc:
        LayerClient(tmp_path).probe(SourceSelection(source_id='f',kind='file',
            locator_ref='x.csv'),wb.ctx,tmp_path)
    assert exc.value.code=='probe_failed'


def test_probe_child_timeout_is_strictly_bounded(tmp_path, monkeypatch):
    (tmp_path / '.venv/bin').mkdir(parents=True)
    (tmp_path / '.venv/bin/python').write_text('')
    timeouts = []
    def fake_run(argv, **kwargs):
        timeouts.append(kwargs['timeout'])
        directory = tmp_path / '.dataagent/results'; directory.mkdir(parents=True, exist_ok=True)
        profile = SourceProfile(source_id='f', source_revision='sha256:' + '0' * 64,
            kind='csv', records=[{'number': 'INV-1'}], fields=['number'], anchors={},
            total_partitions=1, completed_partitions=[1],
            metadata={'structure_fingerprint': 'sha256:' + '1' * 64})
        (directory / 'probe-test.json').write_text(profile.model_dump_json())
        return SimpleNamespace(returncode=0, stderr='',
            stdout=json.dumps({'result_path': '.dataagent/results/probe-test.json'}))
    monkeypatch.setattr('dataagent_workbench.adapters.layer_client.subprocess.run', fake_run)
    wb = Workbench(tmp_path)
    client = LayerClient(tmp_path)
    selection = SourceSelection(source_id='f', kind='file', locator_ref='x.csv')
    client.probe(selection, wb.ctx, tmp_path, budget_seconds=50)
    client.probe(selection, wb.ctx, tmp_path, budget_seconds=0.05)
    assert timeouts == [50.5, 2.0]
