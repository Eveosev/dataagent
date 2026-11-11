"""Resolve user-selected connection references with host-owned settings."""
import json
import os
from pathlib import Path


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
        credentials = dict(entry.get('credential_options', {}))
        for name, variable in entry.get('credential_env', {}).items():
            value = os.environ.get(variable)
            if value is None:
                raise ValueError('configured source credential unavailable')
            credentials[name] = value
        return selection.model_copy(update={
            'locator_ref': entry['locator'],
            'options': entry.get('options', {}),
            'requested_scope': entry.get('scope', {}),
        }), {'credentials': credentials, 'allowed_origins': entry.get('allowed_origins')}
