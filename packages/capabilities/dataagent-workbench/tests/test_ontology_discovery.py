import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from dataagent_runtime.ports.workbench_store import VersionConflict
from dataagent_workbench.adapters.layer_client import LayerClient
from dataagent_workbench.bootstrap import Workbench
from dataagent_workbench.interfaces.http_api import create_app
from dataagent_workbench.service_tools import invoke


@pytest.fixture
def discovery(tmp_path):
    with sqlite3.connect(tmp_path / 'sales.db') as conn:
        sql = Path(__file__).resolve().parents[2] / 'dataagent-scenarios/fixtures/intake/sales-discovery.sql'
        conn.executescript(sql.read_text())
        conn.executescript("""
            ALTER TABLE party ADD COLUMN secret TEXT DEFAULT 'secret-marker';
            CREATE TABLE legacy_party AS SELECT party_no FROM party;
            CREATE UNIQUE INDEX legacy_party_no ON legacy_party (party_no);
        """)
    wb = Workbench(tmp_path, layer_client=LayerClient(Path(__file__).resolve().parents[2] / 'dataagent-data'),
                   allowed_model_fields={'db': ['party_no', 'nm', 'book', 'doc_no', 'seq', 'cents']})
    session_id = invoke(wb, 'intake_start', {
        'goal': '发现销售单据的业务对象',
        'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'sales.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': session_id}).data
    return wb, session_id, request


def proposal(request):
    return {
        'source_revision': request['source_revision'],
        'entities': [
            {'table': 'doc_hdr', 'name': 'SalesOrder', 'grain': '每个账簿内的一份销售单',
             'identity': ['book', 'doc_no'], 'properties': []},
            {'table': 'doc_line', 'name': 'SalesOrderLine', 'grain': '销售单的一条明细',
             'identity': ['book', 'doc_no', 'seq'],
             'properties': [{'column': 'cents', 'name': 'amountInCents'}]},
        ],
        'relationships': [{
            'evidence_id': next(x['id'] for x in request['catalog']['relationships'] if x['origin'] == 'declared'),
            'name': 'belongsToOrder',
        }],
    }


def test_discovery_proposal_and_browser_review(discovery):
    wb, sid, request = discovery
    assert request['kind'] == 'ontology_discovery'
    assert request['goal'] == '发现销售单据的业务对象'
    assert 'allowed_target' not in request
    assert 'secret' not in json.dumps(request)
    candidates = request['catalog']['relationships']
    foreign_key, = [item for item in candidates if item['origin'] == 'declared']
    assert foreign_key['source_columns'] == foreign_key['target_columns'] == ['book', 'doc_no']
    assert foreign_key['matched_rows'] == 3
    alternatives = [item for item in candidates if item['source_table'] == 'doc_hdr']
    assert {item['target_table'] for item in alternatives} == {'party', 'legacy_party'}
    assert all(item['ambiguous'] and item['matched_rows'] == 2 for item in alternatives)
    args = {'session_id': sid, 'expected_revision': request['expected_revision'], 'proposal': proposal(request)}
    draft = invoke(wb, 'ontology_discovery_propose', args).data
    assert draft['state'] == 'pending'
    assert draft['unresolved_tables'] == ['legacy_party', 'party']
    assert {item['target_table'] for item in draft['unresolved_relationships']} == {'legacy_party', 'party'}
    with pytest.raises(VersionConflict):
        invoke(wb, 'ontology_discovery_propose', args)
    client = TestClient(create_app(wb), headers={'x-dataagent-token': wb.token})
    path = f'/api/sessions/{sid}'
    view = client.get(path + '/view').json()
    assert view['discovery']['draft'] == draft
    review = {'expected_revision': view['session']['revision'], 'draft_ref': draft['ref'], 'decision': 'approve'}
    assert client.post(path + '/discovery/review', json=review).json()['state'] == 'approved'
    assert client.post(path + '/discovery/review', json=review).status_code == 409
    assert client.get(path + '/view').json()['discovery']['draft']['state'] == 'approved'


@pytest.mark.parametrize(('change', 'message'), [
    (lambda p: p['entities'][0].update(table='fabricated'), 'unknown table'),
    (lambda p: p['entities'][0].update(identity=['party_no']), 'observed key'),
    (lambda p: p['entities'][1]['properties'][0].update(column='secret'), 'unknown column'),
    (lambda p: p['relationships'][0].update(evidence_id='invented'), 'unknown relationship'),
    (lambda p: p.update(source_revision='obsolete'), 'source observation changed'),
])
def test_discovery_rejects_unanchored_proposal(discovery, change, message):
    wb, sid, request = discovery
    candidate = proposal(request)
    change(candidate)
    with pytest.raises((ValueError, VersionConflict), match=message):
        invoke(wb, 'ontology_discovery_propose', {
            'session_id': sid, 'expected_revision': request['expected_revision'], 'proposal': candidate,
        })


def test_discovery_identity_rejects_observed_null_key(discovery):
    wb, _, _ = discovery
    with sqlite3.connect(wb.workspace / 'sales.db') as conn:
        conn.execute('INSERT INTO legacy_party VALUES (NULL)')
    sid = invoke(wb, 'intake_start', {
        'goal': '检查客户标识', 'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'sales.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': sid}).data
    with pytest.raises(ValueError, match='observed key'):
        invoke(wb, 'ontology_discovery_propose', {
            'session_id': sid, 'expected_revision': request['expected_revision'],
            'proposal': {
                'source_revision': request['source_revision'],
                'entities': [{'table': 'legacy_party', 'name': 'Customer', 'grain': '每个客户一行',
                              'identity': ['party_no']}],
            },
        })


def test_discovery_does_not_treat_encoded_blobs_as_text_key_matches(discovery):
    wb, _, _ = discovery
    with sqlite3.connect(wb.workspace / 'blobs.db') as conn:
        conn.executescript("""
            CREATE TABLE parent (party_no TEXT UNIQUE);
            CREATE TABLE child (party_no TEXT);
            INSERT INTO parent VALUES (X'6162'), (X'6364');
            INSERT INTO child VALUES ('YWI='), ('Y2Q=');
        """)
    sid = invoke(wb, 'intake_start', {
        'goal': '发现关联', 'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'blobs.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': sid}).data
    parent = next(table for table in request['catalog']['tables'] if table['name'] == 'parent')
    assert parent['columns']['party_no']['samples'] == []
    assert request['catalog']['relationships'] == []


def test_discovery_guides_user_when_database_has_no_tables(discovery):
    wb, _, _ = discovery
    with sqlite3.connect(wb.workspace / 'empty.db'):
        pass
    sid = invoke(wb, 'intake_start', {
        'goal': '发现实体', 'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'empty.db'}],
    }).data['session_id']
    result = invoke(wb, 'intake_advance', {'session_id': sid})
    assert result.data['catalog']['tables'] == []
    assert result.issues[0].code == 'intake.discovery_no_tables'


def test_discovery_preserves_sqlite_identifier_and_generated_key_semantics(discovery):
    wb, _, _ = discovery
    with sqlite3.connect(wb.workspace / 'generated.db') as conn:
        conn.executescript("""
            CREATE TABLE "Ä" (nm TEXT, party_no TEXT GENERATED ALWAYS AS (lower(nm)) STORED UNIQUE);
            CREATE TABLE "ä" (party_no TEXT PRIMARY KEY);
            CREATE TABLE child (party_no TEXT, FOREIGN KEY (PARTY_NO) REFERENCES "Ä"(PARTY_NO));
            INSERT INTO "Ä" (nm) VALUES ('Acme');
            INSERT INTO "ä" VALUES ('elsewhere');
            INSERT INTO child VALUES ('acme');
        """)
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    sid = invoke(wb, 'intake_start', {
        'goal': '核对 SQLite 生成列外键', 'mode': 'ontology_discovery',
        'sources': [{'source_id': 'db', 'kind': 'sqlite', 'locator_ref': 'generated.db'}],
    }).data['session_id']
    request = invoke(wb, 'intake_advance', {'session_id': sid}).data
    link, = request['catalog']['relationships']
    assert link['target_table'] == 'Ä' and link['target_columns'] == ['party_no']
    assert link['origin'] == 'declared' and link['matched_rows'] == 1
