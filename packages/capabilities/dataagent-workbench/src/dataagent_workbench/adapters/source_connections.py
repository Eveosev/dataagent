"""Resolve user-selected connection references with host-owned settings.

The connection manifest contains logical credential names only (``file:`` or
``keychain:``). This process validates and forwards them; the probing
subprocess resolves the values (see ``dataagent_runtime.policy.secrets``).
``env:`` is supported by the shared resolver for processes the host launches
directly, but not through this workbench: the host cannot yet inject a
credential into the probe child without the workbench reading its value, so
the manifest rejects that scheme until the host-side mechanism exists.
"""
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

from dataagent_runtime.policy.secrets import InvalidSecretRef, validate_ref

_SECRET_OPTIONS = {'token', 'password', 'secret', 'api_key', 'apikey', 'authorization'}
_SECRET_KEYS = _SECRET_OPTIONS | {
    'credential', 'credentials', 'credential_refs', 'credential_options',
    'auth_token', 'access_token', 'refresh_token', 'client_secret', 'private_key',
}
_HEADER_KEYS = {'header', 'headers', 'http_header', 'http_headers', 'request_headers'}
_SECRET_FRAGMENTS = ('token', 'secret', 'password', 'apikey', 'api_key',
                     'authorization', 'credential', 'private_key', 'cookie')
_AUTH_VALUE = re.compile(r'^\s*(?:Bearer|Basic)\s+\S+', re.IGNORECASE)


def _is_secret_key(name):
    normalized = str(name).strip().lower().replace('-', '_')
    return (normalized in _SECRET_KEYS or normalized in _HEADER_KEYS
            or any(fragment in normalized for fragment in _SECRET_FRAGMENTS))


def validate_forwarded(value, path):
    """Reject plaintext credentials and HTTP headers before they reach stdin."""

    if isinstance(value, dict):
        for key, item in value.items():
            if _is_secret_key(key):
                raise ValueError(f'connection manifest {path}.{key} must use credential_refs')
            validate_forwarded(item, f'{path}.{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_forwarded(item, f'{path}[{index}]')
    elif isinstance(value, str) and _AUTH_VALUE.match(value):
        raise ValueError(f'connection manifest {path} must not carry an Authorization header')


def _validate_url(value, path):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'connection manifest {path} is invalid')
    try:
        parts = urlsplit(value)
    except ValueError:
        raise ValueError(f'connection manifest {path} is invalid') from None
    if parts.username is not None or parts.password is not None:
        raise ValueError(f'connection manifest {path} must not carry credentials')
    for key, _ in parse_qsl(parts.query, keep_blank_values=True):
        if _is_secret_key(key):
            raise ValueError(f'connection manifest {path} must not carry credentials')


def _validate_origins(origins):
    if origins is None:
        return
    if not isinstance(origins, list):
        raise ValueError('connection manifest allowed_origins is invalid')
    for origin in origins:
        _validate_url(origin, 'allowed_origins')


def _credential_refs(entry):
    refs = {}
    configured = entry.get('credential_refs', {})
    if not isinstance(configured, dict):
        raise ValueError('configured source credential references are invalid')
    for name, ref in configured.items():
        if not isinstance(name, str) or not name or not isinstance(ref, str):
            raise ValueError('configured source credential references are invalid')
        try:
            validate_ref(ref)
        except InvalidSecretRef:
            raise ValueError('configured source credential must use a logical name') from None
        if ref.startswith('env:'):
            raise ValueError(
                'env: credentials require the trusted host to inject the variable '
                'into the probe process; use file: or keychain:'
            )
        refs[name] = ref
    legacy = entry.get('credential_env', {})
    if not isinstance(legacy, dict):
        raise ValueError('configured source credential references are invalid')
    if legacy:
        raise ValueError(
            'env: credentials require the trusted host to inject the variable '
            'into the probe process; use file: or keychain:'
        )
    return refs


def _credential_options(entry):
    options = entry.get('credential_options', {})
    if not isinstance(options, dict):
        raise ValueError('configured source credential options are invalid')
    if any(_is_secret_key(name) for name in options if isinstance(name, str)):
        raise ValueError('source credentials must use logical references, not literal options')
    validate_forwarded(options, 'credential_options')
    return dict(options)


class SourceConnections:
    def __init__(self):
        path = os.environ.get('DATAAGENT_SOURCE_CONNECTIONS')
        self.entries = json.loads(Path(path).read_text()) if path else {}

    def list(self):
        return [{'id': key, 'kind': entry['kind'], 'label': entry.get('label', key)}
                for key, entry in self.entries.items()]

    def resolve(self, selection):
        if selection.kind not in {'postgres', 'rest'}:
            return selection, {}
        entry = self.entries.get(selection.locator_ref)
        if not entry or entry.get('kind') != selection.kind:
            raise ValueError('select a configured source connection of this kind')
        if selection.options or selection.requested_scope:
            raise ValueError('remote source options and scope belong to host configuration')
        locator = entry.get('locator')
        _validate_url(locator, 'locator')
        options = entry.get('options') or {}
        scope = entry.get('scope') or {}
        if not isinstance(options, dict) or not isinstance(scope, dict):
            raise ValueError('connection manifest options and scope must be objects')
        validate_forwarded(options, 'options')
        validate_forwarded(scope, 'scope')
        _validate_origins(entry.get('allowed_origins'))
        return selection.model_copy(update={
            'locator_ref': locator,
            'options': options,
            'requested_scope': scope,
            'credential_binding_ref': None,
        }), {
            'credential_refs': _credential_refs(entry),
            'credential_options': _credential_options(entry),
            'allowed_origins': entry.get('allowed_origins'),
        }
