import os
from pathlib import Path
import pytest
from dataagent_contracts.intake import SourceSelection
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
