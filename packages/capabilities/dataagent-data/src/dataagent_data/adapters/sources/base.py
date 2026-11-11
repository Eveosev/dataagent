"""Snapshot and scalar encoding shared by the read-only adapters."""
import base64
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import UUID
from dataagent_contracts.intake import SourceObservation


def json_value(value):
    if isinstance(value, (date, datetime, time)): return value.isoformat()
    if isinstance(value, (Decimal, UUID)): return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)): return base64.b64encode(bytes(value)).decode('ascii')
    if isinstance(value, dict): return {str(k):json_value(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [json_value(v) for v in value]
    return value


def typed_key(field, value):
    return {'field':field,'type':type(value).__name__,'value':json_value(value)}


def digest(value):
    return hashlib.sha256(json.dumps(json_value(value),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def snapshot(workspace, payload):
    root=Path(workspace).resolve()
    store=root/'.dataagent'/'content'
    # A workspace cannot redirect the controlled content store through symlinks.
    for path in [root/'.dataagent',store]:
        if path.is_symlink(): raise PermissionError('content store must not be a symlink')
    store.mkdir(parents=True,exist_ok=True)
    data=json.dumps(json_value(payload),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    sha=hashlib.sha256(data).hexdigest();target=store/(sha+'.json')
    if target.is_symlink(): raise PermissionError('snapshot must not be a symlink')
    # Content-addressed publication never follows a pre-existing target.
    try:
        with target.open('xb') as stream: stream.write(data)
    except FileExistsError:
        if target.read_bytes()!=data: raise ValueError('snapshot digest collision')
    return 'sha256:'+sha,str(target.relative_to(root))


class ReadOnlySource:
    def __init__(self, selection, *, workspace, credentials=None, allowed_origins=None):
        self.selection=selection;self.workspace=workspace;self.credentials=credentials;self.allowed_origins=allowed_origins

    def changes(self, ctx, *, cursor=None):
        return SourceObservation(source_id=self.selection.source_id,source_revision='unsupported',kind=self.selection.kind,
            metadata={'status':'unsupported','capability':'changes','reason':'provider has no supported change feed'})
