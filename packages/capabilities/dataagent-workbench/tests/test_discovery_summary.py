"""Discovery evidence as a structural summary, with on-demand detail.

The model-facing result keeps table/document structure (columns, types,
candidate keys, relationship candidates, section titles, clause inventory)
but moves samples and clause text behind ``detail_table`` / ``detail_section``.
The result file itself stays complete for the web and for a single explicit
read.
"""
from __future__ import annotations

import json

import pytest

from dataagent_workbench.ontology_discovery import (
    discovery_detail, evidence_summary,
)
from dataagent_workbench.service_tools import invoke, result_summary
from test_discovery_documents import (
    document_allowed, document_sources, document_workspace, start, workbench,
)


def _all_sections(sections):
    for section in sections or []:
        yield section
        yield from _all_sections(section.get('sections') or [])


def _request(wb, session_id):
    invoke(wb, 'intake_advance', {'session_id': session_id})
    return invoke(wb, 'intake_inference', {'session_id': session_id}).data


def test_default_summary_keeps_structure_and_drops_samples_and_clause_text():
    import tempfile
    from pathlib import Path
    tmp_path = Path(tempfile.mkdtemp(prefix='v2-summary-'))
    document_workspace(tmp_path)
    wb = workbench(tmp_path, allowed=document_allowed())
    full = _request(wb, start(wb, document_sources()))
    summary = evidence_summary(full)

    assert summary['catalog']['summary'] is True
    assert summary['evidence_summary']['summary'] is True
    tables = {table['name']: table for table in summary['catalog']['tables']}
    assert set(tables) == {'table:1', '明细', 'departments'}
    standard = tables['table:1']
    assert set(standard['columns']) == {'城市等级', '职级', '费用类型', '限额', '币种'}
    assert standard['columns']['限额']['type'] == 'integer'
    assert standard['columns']['限额']['samples_included'] is False
    assert standard['columns']['限额']['sample_count'] == 3
    assert 'samples' not in standard['columns']['限额']
    # Candidate keys and relationship candidates survive the summary.
    assert ['限额'] in standard['keys']
    assert ['城市等级', '职级', '费用类型'] in standard['identity_keys']
    assert summary['catalog']['relationships'] == full['catalog']['relationships']
    assert summary['catalog']['relationships'], 'fixture must carry a candidate relation'

    document = summary['catalog']['documents'][0]
    assert document['clause_count'] == 3
    assert [clause['ref'] for clause in document['clauses']] == [
        clause['ref'] for clause in full['catalog']['documents'][0]['clauses']]
    assert all('text' not in clause for clause in document['clauses'])
    assert document['clause_text_included'] is False
    assert any(section.get('title') == '总则'
               for section in _all_sections(document['sections']))

    # The full catalog (what the result file carries) still has both payloads.
    full_tables = {table['name']: table for table in full['catalog']['tables']}
    assert full_tables['table:1']['columns']['限额']['samples']
    assert full['catalog']['documents'][0]['clauses'][0]['text'].startswith('第一条')
    assert all('text' not in clause
               for doc in summary['catalog']['documents']
               for clause in doc['clauses'])
    assert all('samples' not in column
               for table in summary['catalog']['tables']
               for column in table['columns'].values())


def test_result_file_stays_complete_while_the_inline_result_is_the_summary():
    import tempfile
    from pathlib import Path
    tmp_path = Path(tempfile.mkdtemp(prefix='v2-summary-'))
    document_workspace(tmp_path)
    wb = workbench(tmp_path, allowed=document_allowed())
    sid = start(wb, document_sources())
    invoke(wb, 'intake_advance', {'session_id': sid})
    result = invoke(wb, 'intake_inference', {'session_id': sid})
    returned = result_summary(wb, result)
    assert returned['summary'] is True
    assert returned['result']['catalog']['summary'] is True

    stored = json.loads((wb.workspace / returned['result_path']).read_text())
    assert stored['status'] == result.status.value
    assert stored['data']['kind'] == 'ontology_discovery'
    stored_tables = {table['name']: table for table in stored['data']['catalog']['tables']}
    assert stored_tables['table:1']['columns']['限额']['samples'] == ['400', '200', '350']
    assert stored['data']['catalog']['documents'][0]['clauses'][0]['text']


def test_detail_table_returns_samples_only_for_the_named_table():
    import tempfile
    from pathlib import Path
    tmp_path = Path(tempfile.mkdtemp(prefix='v2-summary-'))
    document_workspace(tmp_path)
    wb = workbench(tmp_path, allowed=document_allowed())
    sid = start(wb, document_sources())
    invoke(wb, 'intake_advance', {'session_id': sid})
    result = invoke(wb, 'intake_inference',
                    {'session_id': sid, 'detail_table': 'table:1'})
    detail = result.data['_discovery_detail']
    assert detail['kind'] == 'table'
    assert detail['table']['name'] == 'table:1'
    assert detail['table']['columns']['限额']['samples'] == ['400', '200', '350']
    summary = result_summary(wb, result)
    assert summary['result']['details'] == detail
    tables = {table['name']: table for table in summary['result']['catalog']['tables']}
    assert 'samples' not in tables['table:1']['columns']['限额']
    stored = json.loads((wb.workspace / summary['result_path']).read_text())
    assert '_discovery_detail' not in stored['data']
    stored_tables = {table['name']: table for table in stored['data']['catalog']['tables']}
    assert stored_tables['table:1']['columns']['限额']['samples'] == ['400', '200', '350']


def test_detail_section_pages_clause_text_and_keeps_the_policy_scope():
    import tempfile
    from pathlib import Path
    tmp_path = Path(tempfile.mkdtemp(prefix='v2-summary-'))
    document_workspace(tmp_path)
    wb = workbench(tmp_path, allowed=document_allowed())
    sid = start(wb, document_sources())
    invoke(wb, 'intake_advance', {'session_id': sid})
    full = invoke(wb, 'intake_inference', {'session_id': sid}).data
    document = full['catalog']['documents'][0]
    section = next(item for item in _all_sections(document['sections'])
                   if item.get('title') == '总则')

    first = invoke(wb, 'intake_inference', {
        'session_id': sid, 'detail_section': section['ref'],
        'detail_offset': 0, 'detail_limit': 1,
    }).data['_discovery_detail']
    assert first['kind'] == 'section'
    assert first['total'] == 2 and first['count'] == 1
    assert first['has_more'] is True and first['next_offset'] == 1
    assert first['clauses'][0]['text'].startswith('第一条')

    second = invoke(wb, 'intake_inference', {
        'session_id': sid, 'detail_section': section['ref'],
        'detail_offset': 1, 'detail_limit': 1,
    }).data['_discovery_detail']
    assert second['clauses'][0]['text'].startswith('第二条')

    document_page = invoke(wb, 'intake_inference', {
        'session_id': sid, 'detail_section': document['source_id'],
        'detail_limit': 2,
    }).data['_discovery_detail']
    assert document_page['kind'] == 'document'
    assert document_page['total'] == 3 and document_page['count'] == 2
    assert document_page['has_more'] is True

    # A policy that hides clause text still cannot be bypassed: the summary
    # and the detail view are both built from the filtered catalog.
    restricted = workbench(tmp_path, allowed={'policy': ['限额']})
    restricted_sid = start(restricted, document_sources())
    invoke(restricted, 'intake_advance', {'session_id': restricted_sid})
    filtered = invoke(restricted, 'intake_inference',
                      {'session_id': restricted_sid}).data
    filtered_summary = evidence_summary(filtered)
    assert all('text' not in clause
               for doc in filtered_summary['catalog']['documents']
               for clause in doc['clauses'])
    assert all(not clause.get('text')
               for doc in filtered['catalog']['documents']
               for clause in doc.get('clauses') or [])

    with pytest.raises(ValueError, match='unknown detail_section'):
        discovery_detail(full, section='section:missing:1')
    with pytest.raises(ValueError, match='unknown detail_table'):
        discovery_detail(full, table='missing')
    with pytest.raises(ValueError, match='cannot be combined'):
        discovery_detail(full, table='table:1', section=section['ref'])


def test_detail_parameters_are_only_for_discovery_evidence():
    import tempfile
    from pathlib import Path
    from test_intake_repairs import single_setup
    wb, session = single_setup(Path(tempfile.mkdtemp(prefix='v2-mapping-')))
    with pytest.raises(ValueError, match='only available for ontology discovery'):
        invoke(wb, 'intake_inference',
               {'session_id': session.id, 'detail_table': 'table:1'})
    with pytest.raises(ValueError, match='only available for ontology discovery'):
        invoke(wb, 'intake_inference',
               {'session_id': session.id, 'detail_offset': 1})


def test_mcp_tool_response_is_the_summary_but_the_result_file_is_full():
    import tempfile
    from pathlib import Path
    from dataagent_workbench.interfaces.mcp_server import handle
    tmp_path = Path(tempfile.mkdtemp(prefix='v2-mcp-'))
    document_workspace(tmp_path)
    wb = workbench(tmp_path, allowed=document_allowed())
    sid = start(wb, document_sources())
    invoke(wb, 'intake_advance', {'session_id': sid})
    response = handle(wb, {'method': 'tools/call', 'params': {
        'name': 'intake_inference', 'arguments': {'session_id': sid}}})
    payload = json.loads(response['content'][0]['text'])
    assert response['isError'] is False
    assert payload['summary'] is True
    assert payload['result']['catalog']['summary'] is True
    assert all('samples' not in column
               for table in payload['result']['catalog']['tables']
               for column in table['columns'].values())

    stored = json.loads((wb.workspace / payload['result_path']).read_text())
    tables = {table['name']: table for table in stored['data']['catalog']['tables']}
    assert tables['table:1']['columns']['限额']['samples'] == ['400', '200', '350']

    detail = json.loads(handle(wb, {'method': 'tools/call', 'params': {
        'name': 'intake_inference',
        'arguments': {'session_id': sid, 'detail_table': 'table:1'}}}).get(
            'content')[0]['text'])
    assert detail['result']['details']['table']['columns']['限额']['samples'] == [
        '400', '200', '350']
    stored = json.loads((wb.workspace / detail['result_path']).read_text())
    assert '_discovery_detail' not in stored['data']
