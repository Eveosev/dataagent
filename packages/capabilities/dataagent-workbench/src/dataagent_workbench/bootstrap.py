"""Trusted local-owner composition; transports cannot replace its authority."""
import hashlib
import os
import secrets
from pathlib import Path
from uuid import uuid4
from dataagent_contracts.core import CallContext
from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
from .session_service import SessionService


class Workbench:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace/'.dataagent'
        self.root.mkdir(parents=True,exist_ok=True)
        runtime = self.root/'runtime'
        runtime.mkdir(exist_ok=True)
        token_path = runtime/'workbench.token'
        try:
            fd = os.open(token_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd,'w') as f:
                f.write(secrets.token_urlsafe(32))
        self.token = token_path.read_text().strip()
        if len(self.token) < 32:
            raise ValueError('invalid local workbench credential')
        self.scope = 'workspace:'+hashlib.sha256(str(self.workspace).encode()).hexdigest()[:24]
        self.subject = 'local-owner:'+str(os.getuid())
        self.authorization = 'local-owner:'+hashlib.sha256(self.token.encode()).hexdigest()[:24]
        self.store = SqliteWorkbenchStore(self.root/'db/workbench.sqlite3')
        self.sessions = SessionService(self.store,self.scope,self.subject,self.authorization)

    @property
    def ctx(self):
        return CallContext(request_id=uuid4().hex,scope_ref=self.scope,
            subject_ref=self.subject,purpose='local_intake',authorization_ref=self.authorization)
