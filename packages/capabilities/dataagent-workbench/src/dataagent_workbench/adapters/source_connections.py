"""Resolve user-selected connection references with host-owned settings.

The connection manifest contains logical credential names only (``env:``,
``keychain:`` or ``file:``). This process validates and forwards the names.
For ``env:`` the child inherits the host-injected environment and resolves the
value itself; ``file:`` and ``keychain:`` are resolved by the child as well
(see ``dataagent_runtime.policy.secrets``). No credential value enters stdin.
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
        refs[name] = ref
    legacy = entry.get('credential_env', {})
    if not isinstance(legacy, dict):
        raise ValueError('configured source credential references are invalid')
    for name, variable in legacy.items():
        if not isinstance(name, str) or not name or not isinstance(variable, str):
            raise ValueError('configured source credential references are invalid')
        try:
            refs[name] = validate_ref(f'env:{variable}')
        except InvalidSecretRef:
            raise ValueError('configured source credential must use a logical name') from None
    return refs


_SSLMODES = {'disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full'}


def _credential_options(entry, kind):
    options = entry.get('credential_options', {})
    if not isinstance(options, dict):
        raise ValueError('configured source credential options are invalid')
    if any(_is_secret_key(name) for name in options if isinstance(name, str)):
        raise ValueError('source credentials must use logical references, not literal options')
    validate_forwarded(options, 'credential_options')
    allowed = {'rest': {'auth', 'user'}, 'postgres': {'user', 'sslmode'}}[kind]
    for name, value in options.items():
        if not isinstance(name, str) or name not in allowed:
            raise ValueError(f'unsupported {kind} credential option')
        if not isinstance(value, str) or not value:
            raise ValueError(f'unsupported {kind} credential option value')
    if kind == 'rest' and 'auth' in options and options['auth'] not in {'bearer', 'basic'}:
        raise ValueError('REST credential_options.auth must be bearer or basic')
    if kind == 'postgres' and 'sslmode' in options and options['sslmode'] not in _SSLMODES:
        raise ValueError('unsupported PostgreSQL sslmode')
    return dict(options)


def _validate_credential_shape(kind, refs, options):
    if kind == 'rest':
        if not refs and not options:
            return
        auth = options.get('auth')
        if auth not in {'bearer', 'basic'}:
            raise ValueError('REST credentials require auth bearer or basic')
        if auth == 'bearer':
            if set(refs) - {'token'} or set(options) - {'auth'}:
                raise ValueError('bearer authentication accepts only a token reference')
            if 'token' not in refs:
                raise ValueError('bearer authentication requires a token reference')
        else:
            if set(refs) - {'user', 'password'} or set(options) - {'auth', 'user'}:
                raise ValueError('basic authentication accepts only user and password')
            if 'password' not in refs:
                raise ValueError('basic authentication requires a password reference')
            if not options.get('user') and 'user' not in refs:
                raise ValueError('basic authentication requires a user')
    else:
        if set(refs) - {'user', 'password'}:
            raise ValueError('PostgreSQL credentials accept only user and password')


class SourceConnections:
    def __init__(self):
        path = os.environ.get('DATAAGENT_SOURCE_CONNECTIONS')
        if not path:
            self.entries = {}
            return
        try:
            self.entries = json.loads(Path(path).read_text())
        except FileNotFoundError:
            # A default manifest path may not exist yet; local sources still work.
            self.entries = {}

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
        refs = _credential_refs(entry)
        credential_options = _credential_options(entry, selection.kind)
        _validate_credential_shape(selection.kind, refs, credential_options)
        return selection.model_copy(update={
            'locator_ref': locator,
            'options': options,
            'requested_scope': scope,
            'credential_binding_ref': None,
        }), {
            'credential_refs': refs,
            'credential_options': credential_options,
            'allowed_origins': entry.get('allowed_origins'),
        }
