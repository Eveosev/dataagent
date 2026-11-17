"""Resolve user-selected connection references with host-owned settings.

The connection manifest contains logical credential names only (``file:``,
``env:`` or ``keychain:``). This process validates and forwards them; the
probing subprocess resolves the values (see ``dataagent_runtime.policy.secrets``).
"""
import json
import os
from pathlib import Path

from dataagent_runtime.policy.secrets import InvalidSecretRef, validate_ref

_SECRET_OPTIONS = {'token', 'password', 'secret', 'api_key', 'apikey', 'authorization'}


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


def _credential_options(entry):
    options = entry.get('credential_options', {})
    if not isinstance(options, dict):
        raise ValueError('configured source credential options are invalid')
    if any(name.lower() in _SECRET_OPTIONS for name in options if isinstance(name, str)):
        raise ValueError('source credentials must use logical references, not literal options')
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
        return selection.model_copy(update={
            'locator_ref': entry['locator'],
            'options': entry.get('options', {}),
            'requested_scope': entry.get('scope', {}),
        }), {
            'credential_refs': _credential_refs(entry),
            'credential_options': _credential_options(entry),
            'allowed_origins': entry.get('allowed_origins'),
        }
