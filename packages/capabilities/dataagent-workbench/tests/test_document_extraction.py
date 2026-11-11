from pathlib import Path
import shutil

import pytest

from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.service_tools import invoke


def make_pdf_intake(tmp_path, allowed_model_fields=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    packages = Path(__file__).resolve().parents[2]
    shutil.copyfile(packages/'dataagent-scenarios/fixtures/intake/invoice.pdf', tmp_path/'invoice.pdf')
    wb = Workbench(tmp_path, layer_client=LayerClient(packages/'dataagent-data'),
                   allowed_model_fields=allowed_model_fields)
    task = invoke(wb, 'intake_start', {'goal': '接入发票', 'sources': [
        {'source_id': 'pdf', 'kind': 'file', 'locator_ref': 'invoice.pdf'}
    ]}).data
    session = wb.intake.advance(task['session_id'], wb.ctx)
    return wb, session


def test_extracts_verified_pdf_quote_with_original_anchor(tmp_path):
    wb, session = make_pdf_intake(tmp_path)
    request = wb.intake.inference_request(session.id, wb.ctx)
    assert 'INV-001' in request['sources'][0]['document_excerpts'][0]['text']
    result = invoke(wb, 'intake_extract', {
        'session_id': session.id, 'source_id': 'pdf', 'expected_revision': session.revision,
        'fields': [{'row': 0, 'name': 'number_from_text', 'page': 1, 'quote': 'INV-001'}],
    }).data
    view = wb.intake.view(session.id, wb.ctx)
    profile = view['profiles'][0]
    assert profile['records'][0]['number_from_text'] == 'INV-001'
    anchor = profile['anchors']['0.number_from_text'][0]
    assert anchor['source_revision'] == profile['source_revision']
    span = anchor['selector']
    text = profile['metadata']['pages'][0]['text']
    assert text[span['char_start']:span['char_end']] == 'INV-001'
    assert result['expected_revision'] == view['session']['revision']


def test_extract_rejects_invented_quote_and_restricted_pdf_text(tmp_path):
    wb, session = make_pdf_intake(tmp_path/'unrestricted')
    args = {'session_id': session.id, 'source_id': 'pdf', 'expected_revision': session.revision,
            'fields': [{'row': 0, 'name': 'derived', 'page': 1, 'quote': 'INV-999'}]}
    with pytest.raises(ValueError):
        invoke(wb, 'intake_extract', args)
    assert wb.sessions.get(session.id, wb.ctx).revision == session.revision

    restricted, task = make_pdf_intake(tmp_path/'restricted', {'pdf': ['number']})
    observed = restricted.intake.inference_request(task.id, restricted.ctx)
    assert 'document_excerpts' not in observed['sources'][0]
    args.update(session_id=task.id, expected_revision=task.revision)
    args['fields'][0]['quote'] = 'INV-001'
    with pytest.raises(PermissionError):
        invoke(restricted, 'intake_extract', args)
