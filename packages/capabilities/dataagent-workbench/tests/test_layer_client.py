import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from dataagent_contracts.intake import SourceProfile, SourceSelection
from dataagent_workbench.bootstrap import Workbench
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
    config=tmp_path/'connections.json'
    config.write_text(json.dumps({'accounting':{
        'kind':'rest','locator':'http://127.0.0.1:9999/invoices',
        'allowed_origins':['http://127.0.0.1:9999'],'options':{'records_path':'/items'},
        'credential_options':{'auth':'bearer'},
        'credential_refs':{'token':'file:rest-token'},
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS',str(config))
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    captured={}
    def fake_run(argv,**kwargs):
        captured['input']=kwargs['input']
        captured['env']=kwargs['env']
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
    assert payload['credential_refs']=={'token':'file:rest-token'}
    assert payload['credential_options']=={'auth':'bearer'}
    assert 'credentials' not in payload
    assert sentinel not in captured['input']
    assert isinstance(captured['env'],dict)
    assert 'T14_SENTINEL_TOKEN' not in captured['env']
    assert 'DATAAGENT_DATA_ROOT' not in captured['env']
    assert profile.records==[{'/id':1}]


def test_probe_rejects_plaintext_in_forwarded_selection_options(tmp_path):
    wb=Workbench(tmp_path)
    (tmp_path/'.venv/bin').mkdir(parents=True)
    (tmp_path/'.venv/bin/python').write_text('')
    selection=SourceSelection(source_id='f',kind='file',locator_ref='x.csv',
                              options={'token':'T14-EXAMPLE'})
    with pytest.raises(ValueError,match='credential'):
        LayerClient(tmp_path).probe(selection,wb.ctx,tmp_path)
