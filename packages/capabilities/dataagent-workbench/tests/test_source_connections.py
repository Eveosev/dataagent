import json
from pathlib import Path
import sqlite3

import pytest
from dataagent_contracts.intake import SourceSelection
from dataagent_contracts.ontology import ReviewDecision

from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.adapters.source_connections import SourceConnections
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.service_tools import invoke


def test_sqlite_intake_retains_primary_key_evidence(tmp_path):
    with sqlite3.connect(tmp_path / 'invoice.db') as conn:
        conn.executescript(
            "CREATE TABLE invoice (number TEXT PRIMARY KEY, amount INTEGER, currency TEXT);"
            "INSERT INTO invoice VALUES ('DB-1', 1260, 'CNY');"
        )
    package = Path(__file__).resolve().parents[2] / 'dataagent-data'
    wb = Workbench(tmp_path, layer_client=LayerClient(package))
    started = invoke(wb, 'intake_start', {
        'goal': '接入发票数据库',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'invoice.db'}],
    }).data
    session = wb.intake.advance(started['session_id'], wb.ctx)
    profile, = wb.intake.view(session.id, wb.ctx)['profiles']
    assert profile['records'] == [{'number': 'DB-1', 'amount': 1260, 'currency': 'CNY'}]
    assert profile['anchors']['0.amount'][0]['selector']['keys'] == {'table': 'invoice', 'primary_key': {'number': 'DB-1'}}


def test_connection_reference_cannot_override_host_configuration(tmp_path, monkeypatch):
    config = tmp_path / 'connections.json'
    config.write_text(json.dumps({'accounting': {
        'kind': 'rest', 'label': '发票 API', 'locator': 'http://127.0.0.1:9999/invoices',
        'allowed_origins': ['http://127.0.0.1:9999'], 'options': {'records_path': '/items'},
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(config))
    wb = Workbench(tmp_path, layer_client=LayerClient(tmp_path))
    for locator, options, expected in [
        ('http://127.0.0.1:9999/invoices', {}, 'configured source connection'),
        ('accounting', {'allowed_origins': ['https://example.org']}, 'host configuration'),
    ]:
        started = invoke(wb, 'intake_start', {
            'goal': '接入发票 API',
            'sources': [{'source_id': 'api', 'kind': 'rest', 'locator_ref': locator, 'options': options}],
        }).data
        session = wb.intake.advance(started['session_id'], wb.ctx)
        assert session.next_actions == ['retry_probe']
        assert expected in session.issues[0]['detail']


def test_connection_manifest_keeps_only_logical_credential_names(tmp_path, monkeypatch):
    sentinel = 'T14-SENTINEL-5f0c9a7d2b8e4c61'
    config = tmp_path / 'connections.json'
    config.write_text(json.dumps({'accounting': {
        'kind': 'rest', 'locator': 'http://127.0.0.1:9999/invoices',
        'allowed_origins': ['http://127.0.0.1:9999'], 'options': {'records_path': '/items'},
        'credential_options': {'auth': 'bearer'},
        'credential_refs': {'token': 'file:rest-token'},
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(config))
    selection = SourceSelection(source_id='api', kind='rest', locator_ref='accounting')
    resolved, options = SourceConnections().resolve(selection)
    assert resolved.locator_ref == 'http://127.0.0.1:9999/invoices'
    assert options['credential_refs'] == {'token': 'file:rest-token'}
    assert options['credential_options'] == {'auth': 'bearer'}
    assert sentinel not in json.dumps(options)


@pytest.mark.parametrize('entry', [
    {'credential_refs': {'token': 'env:T14_REST_TOKEN'}},
    {'credential_env': {'token': 'T14_REST_TOKEN'}},
])
def test_env_reference_requires_host_injection(tmp_path, monkeypatch, entry):
    config = tmp_path / 'connections.json'
    config.write_text(json.dumps({'accounting': {
        'kind': 'rest', 'locator': 'http://127.0.0.1:9999/invoices',
        'credential_options': {'auth': 'bearer'}, **entry,
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(config))
    with pytest.raises(ValueError, match='host'):
        SourceConnections().resolve(
            SourceSelection(source_id='api', kind='rest', locator_ref='accounting'))


def test_missing_manifest_keeps_local_probe_available(tmp_path, monkeypatch):
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(tmp_path / 'missing.json'))
    (tmp_path / 'input.csv').write_text('number,total\nINV-1,126000\n')
    package = Path(__file__).resolve().parents[2] / 'dataagent-data'
    wb = Workbench(tmp_path)
    profile = LayerClient(package).probe(
        SourceSelection(source_id='f', kind='file', locator_ref='input.csv'), wb.ctx, tmp_path)
    assert profile.records[0]['total'] == '126000'
    with pytest.raises(ValueError, match='configured'):
        SourceConnections().resolve(
            SourceSelection(source_id='api', kind='rest', locator_ref='accounting'))


@pytest.mark.parametrize('entry', [
    {'credential_options': {'auth': 'T14-EXAMPLE'},
     'credential_refs': {'token': 'file:rest-token'}},
    {'credential_options': {'auth': 'bearer'}},
    {'credential_options': {'auth': 'basic', 'user': 'reader'}},
])
def test_rest_credential_options_are_enumerated_and_complete(tmp_path, monkeypatch, entry):
    config = tmp_path / 'connections.json'
    config.write_text(json.dumps({'accounting': {
        'kind': 'rest', 'locator': 'http://127.0.0.1:9999/invoices', **entry,
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(config))
    with pytest.raises(ValueError):
        SourceConnections().resolve(SourceSelection(source_id='api', kind='rest', locator_ref='accounting'))


def test_postgres_credential_options_are_validated(tmp_path, monkeypatch):
    config = tmp_path / 'connections.json'
    config.write_text(json.dumps({'ledger': {
        'kind': 'postgres', 'locator': 'postgresql://127.0.0.1:5432/invoice',
        'credential_options': {'auth': 'bearer'},
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(config))
    with pytest.raises(ValueError):
        SourceConnections().resolve(SourceSelection(source_id='db', kind='postgres', locator_ref='ledger'))


@pytest.mark.parametrize('entry', [
    {'options': {'token': 'T14-EXAMPLE'}},
    {'options': {'http': {'headers': {'Authorization': 'Bearer T14-EXAMPLE'}}}},
    {'scope': {'password': 'T14-EXAMPLE'}},
    {'locator': 'http://user:pass@127.0.0.1:9999/invoices'},
    {'locator': 'http://127.0.0.1:9999/invoices?token=T14-EXAMPLE'},
])
def test_manifest_rejects_plaintext_in_forwarded_configuration(tmp_path, monkeypatch, entry):
    config = tmp_path / 'connections.json'
    config.write_text(json.dumps({'accounting': {
        'kind': 'rest', 'locator': 'http://127.0.0.1:9999/invoices', **entry,
    }}))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(config))
    with pytest.raises(ValueError):
        SourceConnections().resolve(SourceSelection(source_id='api', kind='rest', locator_ref='accounting'))


def test_connection_manifest_rejects_literal_secrets_and_bad_references(tmp_path, monkeypatch):
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(tmp_path / 'connections.json'))
    for entry in [
        {'kind': 'rest', 'locator': 'http://127.0.0.1:9999/invoices',
         'credential_options': {'token': 'literal'}},
        {'kind': 'rest', 'locator': 'http://127.0.0.1:9999/invoices',
         'credential_refs': {'token': 'literal'}},
    ]:
        (tmp_path / 'connections.json').write_text(json.dumps({'accounting': entry}))
        with pytest.raises(ValueError, match='logical'):
            SourceConnections().resolve(SourceSelection(source_id='api', kind='rest', locator_ref='accounting'))


@pytest.mark.parametrize('database_amount', [1260, 990])
def test_unifies_file_and_database_without_discarding_source_evidence(tmp_path, database_amount):
    (tmp_path / 'invoice.csv').write_text('number,amount_minor,currency,note\nDB-1,126000,CNY,scanned copy\n')
    with sqlite3.connect(tmp_path / 'invoice.db') as conn:
        conn.execute('CREATE TABLE invoice (number TEXT PRIMARY KEY, total INTEGER, currency TEXT, note TEXT)')
        conn.execute('INSERT INTO invoice VALUES (?, ?, ?, ?)', ('DB-1', database_amount, 'CNY', 'ledger'))
    package = Path(__file__).resolve().parents[2] / 'dataagent-data'
    wb = Workbench(tmp_path, layer_client=LayerClient(package))
    started = invoke(wb, 'intake_start', {'goal': '核对发票', 'sources': [
        {'source_id': 'csv', 'kind': 'file', 'locator_ref': 'invoice.csv'},
        {'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'invoice.db'},
    ]}).data
    session = wb.intake.advance(started['session_id'], wb.ctx)
    request = wb.intake.inference_request(session.id, wb.ctx)
    proposals = {
        source['source_id']: {
            **request['proposal_template'], 'source_fingerprint': source['structure_fingerprint'],
            'bindings': {'number': {'source_field': 'number'}, 'currency': {'source_field': 'currency'},
                         'amount': {'source_field': 'amount_minor', 'transform': 'minor_to_major'}
                         if source['source_id'] == 'csv' else {'source_field': 'total'}},
            'unmapped': {'note': 'extension'},
        } for source in request['sources']
    }
    invoke(wb, 'intake_propose_sources', {'session_id': session.id, 'expected_revision': session.revision,
                                         'proposals': proposals})
    preview = wb.intake.view(session.id, wb.ctx)['preview']
    instance, = preview['instances']
    assert set(preview['source_revisions']) == {'csv', 'db'}
    assert {a['source_ref'] for a in instance['source_anchors']['amount']} == {'csv', 'db'}
    assert instance['extensions']['source.unmapped_by_source'] == {
        'csv': {'note': 'scanned copy'}, 'db': {'note': 'ledger'},
    }
    amounts = [a for a in preview['assertions'] if a['relation'] == 'amount']
    assert len({a['mapping_revision'] for a in amounts}) == 2
    session = wb.sessions.get(session.id, wb.ctx)
    decision = ReviewDecision(preview_ref=preview['id']+'@1', target_scope='mapping')
    if database_amount == 1260:
        assert float(instance['values']['amount']) == 1260
        wb.intake.apply(session.id, decision, session.revision, wb.ctx)
        assert wb.sessions.get(session.id, wb.ctx).phase == 'saved'
    else:
        assert instance['values']['amount'] is None
        assert {str(a['role_bindings'][1]['value']).split('.')[0] for a in amounts} == {'990', '1260'}
        with pytest.raises(ValueError, match='unresolved'):
            wb.intake.apply(session.id, decision, session.revision, wb.ctx)
