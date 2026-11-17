"""Sources phase: file, SQLite and REST, plus PostgreSQL when a locator is given.

The REST fixture requires ``Authorization: Bearer <token>``. Its token is a
sentinel injected through the connection manifest's logical name
(``file:rest-token``), never written to the manifest or the report. After the
phase the temporary workspace (except ``.dataagent/secrets/``), the output
directory, Mint session logs and the report are scanned for the sentinel; any
hit fails the phase.
"""

import json
import os
from pathlib import Path
import time

from .common import call_workbench, loopback, remove_not_verified

SENTINEL = 'T14-SENTINEL-5f0c9a7d2b8e4c61'
WRONG_TOKEN = 'T14-WRONG-2a7e4c9b6d1f8035'
_CREDENTIAL_KEYS = {
    'token', 'password', 'secret', 'credentials', 'credential_refs',
    'credential_options', 'credential_binding_ref', 'authorization',
}


def _assert_no_credentials(value, path='intake'):
    """Reject credential fields and sentinel values in agent-visible output."""

    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _CREDENTIAL_KEYS:
                raise AssertionError(f'credential field {path}.{key} leaked into output')
            _assert_no_credentials(item, f'{path}.{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_credentials(item, f'{path}[{index}]')
    elif isinstance(value, str):
        for label, secret in (('sentinel', SENTINEL), ('wrong token', WRONG_TOKEN)):
            if secret in value:
                raise AssertionError(f'{label} leaked into output at {path}')


def _read_contains(path, needles):
    overlap = max((len(needle) for needle in needles), default=1) - 1
    tail = b''
    try:
        with path.open('rb') as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    return False
                data = tail + chunk
                if any(needle in data for needle in needles):
                    return True
                tail = data[-overlap:] if overlap else b''
    except OSError as exc:
        raise RuntimeError(f'credential scan could not read {path}: {exc}') from None


def _mint_log_roots(project):
    """Where Mint keeps session logs.

    Mint writes project-session logs under ``<project>/.mint/logs`` (already
    covered by the project walk); ``MINT_HOME/logs`` is the other location.
    """

    mint_home = os.environ.get('MINT_HOME')
    return [project / '.mint/logs',
            (Path(mint_home).expanduser() if mint_home else Path.home() / '.mint') / 'logs']


def _scan_for_credentials(project, output, report, *, extra_roots=(), since=0.0):
    """Fail when a sentinel appears outside ``.dataagent/secrets/`` or the report."""

    needles = [SENTINEL.encode(), WRONG_TOKEN.encode()]
    secrets_dir = (project / '.dataagent/secrets').resolve()
    hits = []
    roots = [(project, False), (output, False)]
    roots.extend((root, True) for root in extra_roots)
    for root, fresh_only in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob('*')
        for path in paths:
            if not path.is_file():
                continue
            try:
                resolved = path.resolve()
                if resolved == secrets_dir or secrets_dir in resolved.parents:
                    continue
                if fresh_only and since and path.stat().st_mtime < since - 2:
                    continue
            except OSError as exc:
                raise RuntimeError(f'credential scan could not inspect {path}: {exc}') from None
            if _read_contains(resolved, needles):
                hits.append(str(path))
    rendered = json.dumps(report, ensure_ascii=False)
    for label, secret in (('sentinel', SENTINEL), ('wrong token', WRONG_TOKEN)):
        if secret in rendered:
            hits.append(f'report:{label}')
    if hits:
        raise RuntimeError('credential sentinel leaked into: ' + ', '.join(hits[:5]))


def verify_sources(project, postgres_locator, postgres_user):
    import sqlite3

    from dataagent_runtime.policy.secrets import store_file_secret
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI()
    with sqlite3.connect(project/'invoice.db') as db:
        db.execute('CREATE TABLE invoice (number TEXT PRIMARY KEY, amount INTEGER, currency TEXT)')
        db.execute("INSERT INTO invoice VALUES ('INV-003', 1260, 'CNY')")
    (project/'invoice.csv').write_text('number,amount_minor,currency\nINV-003,126000,CNY\n')

    token_ref = store_file_secret(project/'.dataagent', 'rest-token', SENTINEL)
    wrong_ref = store_file_secret(project/'.dataagent', 'rest-token-wrong', WRONG_TOKEN)
    reads = {'first': 0, 'second': 0, 'unauthorized': 0}

    def authorized(request):
        if request.headers.get('authorization') == f'Bearer {SENTINEL}':
            return True
        reads['unauthorized'] += 1
        return False

    @app.get('/invoices')
    def invoices(request: Request):
        if not authorized(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        reads['first'] += 1
        return {'version': 'fixture-1', 'items': [{'code': 'INV-003', 'amount': '1260.00', 'currency': 'CNY'}],
                'next': '/invoices-more'}

    @app.get('/invoices-more')
    def invoices_more(request: Request):
        if not authorized(request):
            return JSONResponse({'error': 'unauthorized'}, status_code=401)
        reads['second'] += 1
        if reads['second'] == 1:
            return JSONResponse({}, status_code=429)
        return {'version': 'fixture-1', 'items': [], 'next': None}

    with loopback(app) as url:
        config = project/'source-connections.json'
        connections = {
            'accounting': {
                'kind': 'rest', 'locator': url+'/invoices', 'allowed_origins': [url],
                'options': {'records_path': '/items', 'keys': ['/code'], 'source_version_path': '/version',
                            'pagination': {'next_path': '/next'}},
                'credential_options': {'auth': 'bearer'},
                'credential_refs': {'token': token_ref},
            },
        }
        if postgres_locator:
            connections['ledger'] = {
                'kind': 'postgres', 'locator': postgres_locator, 'scope': {'tables': ['invoice']},
                'credential_options': {'user': postgres_user},
            }
        config.write_text(json.dumps(connections))
        env = {**os.environ, 'DATAAGENT_SOURCE_CONNECTIONS': str(config)}
        inputs = [('file', 'invoice.csv'), ('sqlite', 'invoice.db')]
        if postgres_locator:
            inputs.append(('postgres', 'ledger'))
        inputs.append(('rest', 'accounting'))
        args = {'session_id': call_workbench(project, 'intake_start', {
            'goal': '从多种来源核对同一张合成发票',
            'sources': [{'source_id': kind, 'kind': kind, 'locator_ref': locator} for kind, locator in inputs],
        }, env=env)['session_id']}
        partial = call_workbench(project, 'intake_advance', args, env=env)
        rest = next(source for source in partial['sources'] if source['source_id'] == 'rest')
        assert rest['coverage'] == 'partial' and partial['next_actions'] == ['retry_probe']
        assert rest['gaps'] == [{'partition': 2, 'code': 'rate_limited'}]
        inference = call_workbench(project, 'intake_inference', args, env=env)
        _assert_no_credentials(inference, 'intake_inference')
        observed = call_workbench(project, 'intake_advance', args, env=env)
        assert reads == {'first': 1, 'second': 2, 'unauthorized': 0}
        expected = {kind for kind, _ in inputs}
        assert {source['source_id'] for source in observed['sources']} == expected
        assert all(source['coverage'] == 'full' for source in observed['sources'])
        if postgres_locator:
            assert next(source for source in observed['sources']
                        if source['source_id'] == 'postgres')['samples'][0]['posted_on'] == '2026-11-11'
        proposals = {}
        for source in observed['sources']:
            kind = source['source_id']
            proposals[kind] = {
                **observed['proposal_template'], 'source_fingerprint': source['structure_fingerprint'],
                'bindings': {
                    'number': {'source_field': '/code' if kind == 'rest' else 'number'},
                    'currency': {'source_field': '/currency' if kind == 'rest' else 'currency'},
                    'amount': {'source_field': 'amount_minor' if kind == 'file' else '/amount' if kind == 'rest' else 'amount',
                               'transform': 'minor_to_major' if kind == 'file' else 'decimal'},
                },
            }
        preview = call_workbench(project, 'intake_propose_sources', {
            **args, 'proposals': proposals, 'expected_revision': observed['expected_revision'],
        }, env=env)
        assert preview['instance_count'] == 1 and preview['issues'] == []
        call_workbench(project, 'mapping_apply', {
            **args, 'expected_revision': preview['session_revision'],
            'decision': {'preview_ref': preview['preview_ref'], 'target_scope': 'mapping'},
        }, env=env)
        status = call_workbench(project, 'intake_status', args, env=env)
        assert status['phase'] == 'saved'
        _assert_no_credentials(status, 'intake_status')

        bad_config = project/'source-connections-wrong.json'
        bad_config.write_text(json.dumps({'accounting-bad': {
            'kind': 'rest', 'locator': url+'/invoices', 'allowed_origins': [url],
            'options': connections['accounting']['options'],
            'credential_options': {'auth': 'bearer'},
            'credential_refs': {'token': wrong_ref},
        }}))
        bad_env = {**os.environ, 'DATAAGENT_SOURCE_CONNECTIONS': str(bad_config)}
        bad = call_workbench(project, 'intake_advance', {'session_id': call_workbench(project, 'intake_start', {
            'goal': '用错误凭据核对同一张合成发票',
            'sources': [{'source_id': 'rest-bad', 'kind': 'rest', 'locator_ref': 'accounting-bad'}],
        }, env=bad_env)['session_id']}, env=bad_env)
        bad_source, = bad['sources']
        assert bad_source['gaps'] == [{'partition': 1, 'code': 'authentication_failed'}]
        assert reads['unauthorized'] >= 1
        _assert_no_credentials(bad, 'intake_advance (wrong token)')
    return {'session': status, 'sources': observed['sources'], 'instance_count': preview['instance_count'],
            'rest_partial': rest, 'rest_requests': reads, 'postgres_included': bool(postgres_locator)}


def apply(report, project, args, context):
    started = time.time()
    report['sources'] = verify_sources(project, args.postgres_locator, args.postgres_user)
    _scan_for_credentials(project, args.output, report,
                          extra_roots=_mint_log_roots(project), since=started)
    remove_not_verified(report, 'file processing')
