"""Resolve user-selected connection references with host-owned settings.

The connection manifest contains logical credential names only (``env:``,
``keychain:`` or ``file:``). This process validates and forwards the names. For
``env:`` the child inherits the environment and resolves the value itself; for
``file:`` and ``keychain:`` the child resolves the named value as well (see
``dataagent_runtime.policy.secrets``). No credential value enters stdin.

A manifest is looked up in this order: an explicit
``DATAAGENT_SOURCE_CONNECTIONS`` passed through by the host, the workspace root
``source-connections.json``, then ``.dataagent/source-connections.json``. The
workspace root wins when both workspace locations exist, with a warning on
stderr; this keeps the packaged defaults from overriding the user's file.

The installed MCP descriptor carries the legacy default
(``.dataagent/source-connections.json``) together with
``DATAAGENT_SOURCE_CONNECTIONS_DEFAULT=1``. That marks the value as the
packaged default, not an explicit host setting, so it cannot shadow the
workspace root file.
"""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlsplit

from dataagent_runtime.policy.secrets import (
    InvalidSecretRef,
    SecretError,
    SecretUnavailable,
    resolve,
    validate_ref,
)

MANIFEST_ENV = 'DATAAGENT_SOURCE_CONNECTIONS'
MANIFEST_DEFAULT_ENV = 'DATAAGENT_SOURCE_CONNECTIONS_DEFAULT'
WORKSPACE_MANIFEST = 'source-connections.json'
DATAAGENT_MANIFEST = '.dataagent/source-connections.json'

_SECRET_OPTIONS = {'token', 'password', 'secret', 'api_key', 'apikey', 'authorization'}
_SECRET_KEYS = _SECRET_OPTIONS | {
    'credential', 'credentials', 'credential_refs', 'credential_options',
    'auth_token', 'access_token', 'refresh_token', 'client_secret', 'private_key',
}
_HEADER_KEYS = {'header', 'headers', 'http_header', 'http_headers', 'request_headers'}
_SECRET_FRAGMENTS = ('token', 'secret', 'password', 'apikey', 'api_key',
                     'authorization', 'credential', 'private_key', 'cookie')
_AUTH_VALUE = re.compile(r'^\s*(?:Bearer|Basic)\s+\S+', re.IGNORECASE)
_ENTRY_FIELDS = {
    'kind', 'label', 'locator', 'options', 'scope', 'allowed_origins',
    'credential_refs', 'credential_env', 'credential_options',
}


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


def _validate_entry(name, entry):
    if not isinstance(entry, dict):
        raise ValueError(f'connection manifest entry {name} must be an object')
    unknown = set(entry) - _ENTRY_FIELDS
    if unknown:
        raise ValueError(
            f'connection manifest entry {name} contains unsupported fields; '
            'credentials must use credential_refs'
        )


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


def workspace_root(workspace=None):
    """The workspace a manifest lookup belongs to."""

    if workspace is not None:
        return Path(workspace).expanduser().resolve()
    configured = os.environ.get('DATAAGENT_WORKSPACE')
    return Path(configured).expanduser().resolve() if configured else Path.cwd()


def locate_manifest(workspace=None):
    """Return ``(path, origin, warning)`` for the connection manifest.

    Resolution order: an explicit ``DATAAGENT_SOURCE_CONNECTIONS`` (the host
    passes the user's setting through), the workspace root file, then the
    packaged default under ``.dataagent``. A descriptor-provided default
    (``DATAAGENT_SOURCE_CONNECTIONS_DEFAULT=1`` or the legacy relative path)
    is not an explicit setting. When both workspace locations exist the
    workspace root file is used and a warning is emitted.
    """

    explicit = os.environ.get(MANIFEST_ENV)
    is_default_path = bool(explicit) and Path(explicit).expanduser() == Path(DATAAGENT_MANIFEST)
    # A descriptor marks its fallback as a default; ``0`` opts out. A custom
    # path is always explicit, even if it inherits the marker.
    packaged_default = is_default_path and os.environ.get(MANIFEST_DEFAULT_ENV, '1') != '0'
    if explicit and not packaged_default:
        return Path(explicit).expanduser(), 'explicit', None
    root = workspace_root(workspace)
    preferred = root / WORKSPACE_MANIFEST
    fallback = root / DATAAGENT_MANIFEST
    if preferred.is_file():
        warning = None
        if fallback.is_file():
            warning = (f'connection manifests {preferred} and {fallback} both exist; '
                       f'using the workspace root manifest {preferred}')
        return preferred, 'workspace', warning
    return fallback, 'dataagent', None


def _repair_command(ref, status):
    """A copy-paste repair hint; it never contains the credential value."""

    kind, _, rest = ref.partition(':')
    if kind == 'env':
        return f'export {rest}=<value> in the shell that starts the workbench, then restart it'
    if kind == 'file':
        if status == 'permission':
            return f'chmod 700 .dataagent/secrets && chmod 600 .dataagent/secrets/{rest}.key'
        return ("mkdir -p .dataagent/secrets && chmod 700 .dataagent/secrets && "
                f"printf '%s' '<value>' > .dataagent/secrets/{rest}.key && "
                f"chmod 600 .dataagent/secrets/{rest}.key")
    if kind == 'keychain':
        service, _, account = rest.partition('/')
        return f"security add-generic-password -s {service} -a {account} -w '<value>'"
    return 'use env:<VAR>, keychain:<service>/<account> or file:<name>'


def credential_status(ref, data_root):
    """Classify one logical reference without returning its value.

    Returns ``(status, repair)`` where status is ``ok``, ``missing``,
    ``permission`` or ``invalid``. The resolved value is read only to prove it
    exists and is never stored, logged or included in the result.
    """

    try:
        validate_ref(ref)
    except InvalidSecretRef:
        return 'invalid', _repair_command(ref, 'invalid')
    try:
        resolve(ref, data_root)
    except SecretUnavailable as exc:
        message = str(exc)
        action = getattr(exc, 'action', None) or ''
        permission = action.startswith('chmod') or 'other users' in message
        status = 'permission' if permission else 'missing'
        return status, action if action.startswith('chmod') else _repair_command(ref, status)
    except PermissionError:
        return 'permission', _repair_command(ref, 'permission')
    except (SecretError, OSError):
        return 'missing', _repair_command(ref, 'missing')
    return 'ok', None


def _entry_credential_refs(entry):
    """Logical references in one entry, plus a shape error when malformed."""

    refs = {}
    configured = entry.get('credential_refs', {})
    if not isinstance(configured, dict):
        return refs, 'credential_refs must be an object'
    for name, ref in configured.items():
        refs[str(name)] = ref
    legacy = entry.get('credential_env', {})
    if not isinstance(legacy, dict):
        return refs, 'credential_env must be an object'
    for name, variable in legacy.items():
        if not isinstance(variable, str) or not variable:
            refs[str(name)] = variable
        else:
            refs.setdefault(str(name), f'env:{variable}')
    return refs, None


def doctor_report(workspace=None, data_root=None):
    """Return ``(lines, failed)`` for ``dataagent doctor``.

    Every configured connection is listed with its name, kind and manifest
    path; each credential reference is reported as resolvable, missing,
    permission-denied or invalid. Values are never read into the output.
    """

    root = workspace_root(workspace)
    data_root = Path(data_root).expanduser() if data_root else root / '.dataagent'
    path, origin, warning = locate_manifest(root)
    lines = []
    if warning:
        lines.append('connection: warning: ' + warning)
    labels = {'explicit': MANIFEST_ENV, 'workspace': 'workspace root',
              'dataagent': '.dataagent'}
    if not path.is_file():
        if origin == 'explicit':
            lines.append(f'connections: MISSING manifest {path} (from {MANIFEST_ENV})')
            return lines, True
        candidates = root / WORKSPACE_MANIFEST
        lines.append(f'connections: none (looked for {candidates} and {root / DATAAGENT_MANIFEST})')
        return lines, False
    lines.append(f'connections: {path} ({labels.get(origin, origin)})')
    try:
        entries = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        lines.append(f'connections: manifest cannot be read ({type(exc).__name__})')
        return lines, True
    if not isinstance(entries, dict):
        lines.append('connections: manifest must be an object')
        return lines, True
    if not entries:
        lines.append('connections: none configured')
        return lines, False
    failed = False
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            lines.append(f'connection {name}: invalid entry (must be an object)')
            failed = True
            continue
        kind = entry.get('kind')
        if not isinstance(kind, str) or not kind:
            lines.append(f'connection {name}: invalid entry (missing kind)')
            failed = True
            continue
        lines.append(f'connection {name}: {kind} ({path})')
        refs, shape_error = _entry_credential_refs(entry)
        if shape_error:
            lines.append(f'  credentials: invalid ({shape_error})')
            failed = True
        if not refs:
            lines.append('  credentials: none')
            continue
        for label, ref in refs.items():
            if not isinstance(ref, str):
                lines.append(f'  credential {label}: invalid (not a logical name); '
                             f'repair: {_repair_command("", "invalid")}')
                failed = True
                continue
            status, repair = credential_status(ref, data_root)
            # A malformed entry is never echoed: it may hold a plaintext secret.
            shown = ref if status != 'invalid' else '<invalid>'
            if status == 'ok':
                lines.append(f'  credential {label} ({shown}): resolvable（可解析）')
            else:
                status_labels = {'missing': '缺失', 'permission': '权限不对', 'invalid': '无效'}
                lines.append(f'  credential {label} ({shown}): {status}'
                             f'（{status_labels.get(status, status)}）; repair: {repair}')
                failed = True
    return lines, failed


class SourceConnections:
    def __init__(self, workspace=None):
        self.path, self.origin, self.warning = locate_manifest(workspace)
        if self.warning:
            print(f'dataagent-workbench: warning: {self.warning}', file=sys.stderr)
        try:
            self.entries = json.loads(self.path.read_text())
        except FileNotFoundError:
            # A default manifest path may not exist yet; local sources still work.
            self.entries = {}
        except ValueError:
            raise ValueError(f'connection manifest {self.path} is not valid JSON') from None
        except OSError as exc:
            raise ValueError(
                f'connection manifest {self.path} cannot be read ({type(exc).__name__})'
            ) from None
        if not isinstance(self.entries, dict):
            raise ValueError('connection manifest must be an object')
        for name, entry in self.entries.items():
            _validate_entry(name, entry)

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
