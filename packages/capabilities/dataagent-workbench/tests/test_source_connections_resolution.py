"""Manifest lookup order and the doctor connection report (FDE-1).

The workspace root file is the documented location; the packaged
``.dataagent`` default must never silently shadow it. Credential checks report
only whether a logical reference resolves, never the resolved value.
"""

import json
import os
from pathlib import Path

import pytest

from dataagent_workbench.adapters.source_connections import (
    SourceConnections,
    credential_status,
    doctor_report,
    locate_manifest,
)

SENTINEL = 'G1-SENTINEL-0f4c9a2d7e61'


def _manifest(path, name='accounting', **entry):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({name: {
        'kind': 'rest',
        'locator': 'http://127.0.0.1:9999/invoices',
        **entry,
    }}))
    return path


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv('DATAAGENT_SOURCE_CONNECTIONS', raising=False)
    monkeypatch.delenv('DATAAGENT_SOURCE_CONNECTIONS_DEFAULT', raising=False)
    monkeypatch.delenv('DATAAGENT_WORKSPACE', raising=False)


def test_explicit_environment_variable_wins(tmp_path, monkeypatch):
    root = _manifest(tmp_path / 'source-connections.json', 'workspace')
    _manifest(tmp_path / '.dataagent/source-connections.json', 'packaged')
    explicit = _manifest(tmp_path / 'elsewhere.json', 'explicit')
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(explicit))

    connections = SourceConnections(tmp_path)

    assert [item['id'] for item in connections.list()] == ['explicit']
    assert locate_manifest(tmp_path)[1] == 'explicit'
    assert root.is_file()


def test_packaged_default_environ_does_not_shadow_workspace_root(tmp_path, monkeypatch):
    """The installed MCP descriptor may name the legacy default; that value is
    a default, not an explicit override of the workspace root file (FDE-1)."""
    _manifest(tmp_path / 'source-connections.json', 'workspace')
    _manifest(tmp_path / '.dataagent/source-connections.json', 'packaged')
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', '.dataagent/source-connections.json')

    connections = SourceConnections(tmp_path)

    assert [item['id'] for item in connections.list()] == ['workspace']


def test_packaged_default_marker_does_not_demote_a_custom_path(tmp_path, monkeypatch):
    _manifest(tmp_path / 'source-connections.json', 'workspace')
    custom = _manifest(tmp_path / 'custom.json', 'custom')
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(custom))
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS_DEFAULT', '1')

    connections = SourceConnections(tmp_path)

    assert [item['id'] for item in connections.list()] == ['custom']


def test_packaged_default_marker_is_not_an_explicit_setting(tmp_path, monkeypatch):
    _manifest(tmp_path / 'source-connections.json', 'workspace')
    _manifest(tmp_path / '.dataagent/source-connections.json', 'packaged')
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', '.dataagent/source-connections.json')
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS_DEFAULT', '1')

    connections = SourceConnections(tmp_path)

    assert [item['id'] for item in connections.list()] == ['workspace']


def test_workspace_root_wins_over_packaged_default_with_warning(tmp_path, capsys):
    _manifest(tmp_path / 'source-connections.json', 'workspace')
    _manifest(tmp_path / '.dataagent/source-connections.json', 'packaged')

    connections = SourceConnections(tmp_path)

    assert [item['id'] for item in connections.list()] == ['workspace']
    warning = capsys.readouterr().err
    assert 'both exist' in warning
    assert 'workspace root manifest' in warning


def test_packaged_default_is_the_last_resort(tmp_path):
    _manifest(tmp_path / '.dataagent/source-connections.json', 'packaged')

    connections = SourceConnections(tmp_path)

    assert [item['id'] for item in connections.list()] == ['packaged']
    assert connections.origin == 'dataagent'


def test_missing_manifests_leave_connections_empty(tmp_path):
    connections = SourceConnections(tmp_path)

    assert connections.list() == []
    path, origin, warning = locate_manifest(tmp_path)
    assert path == tmp_path / '.dataagent/source-connections.json'
    assert origin == 'dataagent'
    assert warning is None


def test_workspace_environment_variable_names_the_workspace(tmp_path, monkeypatch):
    _manifest(tmp_path / 'source-connections.json', 'workspace')
    monkeypatch.setenv('DATAAGENT_WORKSPACE', str(tmp_path))

    assert [item['id'] for item in SourceConnections().list()] == ['workspace']


def test_doctor_lists_connections_and_reports_resolvable_env(tmp_path, monkeypatch):
    monkeypatch.setenv('G1_REST_TOKEN', SENTINEL)
    _manifest(tmp_path / 'source-connections.json', credential_refs={'token': 'env:G1_REST_TOKEN'})

    lines, failed = doctor_report(tmp_path)

    text = '\n'.join(lines)
    assert failed is False
    assert 'accounting' in text and 'rest' in text
    assert str(tmp_path / 'source-connections.json') in text
    assert 'credential token (env:G1_REST_TOKEN): resolvable' in text
    assert SENTINEL not in text


def test_doctor_reports_missing_env_with_repair_without_value(tmp_path, monkeypatch):
    monkeypatch.delenv('G1_MISSING_TOKEN', raising=False)
    _manifest(tmp_path / 'source-connections.json', credential_refs={'token': 'env:G1_MISSING_TOKEN'})

    lines, failed = doctor_report(tmp_path)
    text = '\n'.join(lines)

    assert failed is True
    assert 'missing' in text
    assert 'export G1_MISSING_TOKEN=<value>' in text


def test_doctor_reports_file_secret_permissions(tmp_path):
    secret_dir = tmp_path / '.dataagent/secrets'
    secret_dir.mkdir(parents=True)
    os.chmod(secret_dir, 0o700)
    secret = secret_dir / 'invoice-api.key'
    secret.write_text(SENTINEL)
    os.chmod(secret, 0o600)
    _manifest(tmp_path / 'source-connections.json', credential_refs={'token': 'file:invoice-api'})

    assert credential_status('file:invoice-api', tmp_path / '.dataagent')[0] == 'ok'
    lines, failed = doctor_report(tmp_path)
    assert failed is False
    assert SENTINEL not in '\n'.join(lines)

    os.chmod(secret, 0o644)
    status, repair = credential_status('file:invoice-api', tmp_path / '.dataagent')
    lines, failed = doctor_report(tmp_path)
    text = '\n'.join(lines)
    assert status == 'permission'
    assert 'permission' in text and 'chmod 600' in text
    assert failed is True
    assert SENTINEL not in text
    assert repair.startswith('chmod 600')


def test_doctor_reports_missing_file_secret_with_repair(tmp_path):
    _manifest(tmp_path / 'source-connections.json', credential_refs={'token': 'file:absent'})

    lines, failed = doctor_report(tmp_path)
    text = '\n'.join(lines)

    assert failed is True
    assert 'file:absent' in text and 'missing' in text
    assert '.dataagent/secrets/absent.key' in text


def test_doctor_fails_when_explicit_manifest_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv('DATAAGENT_SOURCE_CONNECTIONS', str(tmp_path / 'nope.json'))

    lines, failed = doctor_report(tmp_path)

    assert failed is True
    assert 'MISSING manifest' in '\n'.join(lines)


def test_doctor_reports_manifest_read_errors(tmp_path):
    (tmp_path / 'source-connections.json').write_text('{not json')

    lines, failed = doctor_report(tmp_path)

    assert failed is True
    assert 'cannot be read' in '\n'.join(lines)


def test_doctor_without_manifest_does_not_fail(tmp_path):
    lines, failed = doctor_report(tmp_path)

    assert failed is False
    assert 'connections: none' in '\n'.join(lines)


def test_invalid_reference_is_reported_without_reading_anything(tmp_path):
    _manifest(tmp_path / 'source-connections.json', credential_refs={'token': 'literal'})

    lines, failed = doctor_report(tmp_path)
    text = '\n'.join(lines)

    assert failed is True
    assert 'invalid' in text
    assert 'use env:<VAR>' in text
