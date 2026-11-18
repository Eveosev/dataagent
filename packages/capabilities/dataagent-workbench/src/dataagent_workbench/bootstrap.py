"""Trusted local-owner composition; transports cannot replace its authority."""
import hashlib
import os
import secrets
import json
from pathlib import Path
from uuid import uuid4
from dataagent_contracts.core import CallContext
from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
from .session_service import SessionService


class Workbench:
    def __init__(self, workspace, *, layer_client=None, allowed_model_fields=None):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace/'.dataagent'
        self.root.mkdir(parents=True,exist_ok=True)
        runtime = self.root/'runtime'
        runtime.mkdir(exist_ok=True)
        # Browser authentication lives only in the HTTP process, never in agent-readable files.
        self.token = secrets.token_urlsafe(32)
        (runtime/'workbench.token').unlink(missing_ok=True)
        self.scope = 'workspace:'+hashlib.sha256(str(self.workspace).encode()).hexdigest()[:24]
        self.subject = 'local-owner:'+str(os.getuid())
        self.authorization = 'local-owner:'+hashlib.sha256((self.scope+self.subject).encode()).hexdigest()[:24]
        self.store = SqliteWorkbenchStore(self.root/'db/workbench.sqlite3')
        self.layer_client=layer_client
        policy=self.root/'model-context.json'
        self.allowed_model_fields=(allowed_model_fields if allowed_model_fields is not None
            else json.loads(policy.read_text()) if policy.is_file() else None)
        from dataagent_ontology.service import OntologyService
        from dataagent_ontology.registry import load_definition
        self.ontology=OntologyService(self.store,scope=self.scope,subject=self.subject,authorization=self.authorization)
        # The builtin procurement ontology stays registered as the default
        # mapping target for tasks that do not name one.
        self.definition=load_definition(Path(__file__).parent/'ontologies/procurement.json')
        self.ontology.register(self.definition,self.ctx)
        # Read lazily: a host may swap the builtin and register its new revision.
        self.sessions = SessionService(self.store,self.scope,self.subject,self.authorization,
            default_target=lambda:self.definition)
        from .intake_service import IntakeService
        self.intake=IntakeService(self)
        from .ontology_discovery import DiscoveryService
        self.discovery = DiscoveryService(self)

    @property
    def ctx(self):
        return CallContext(request_id=uuid4().hex,scope_ref=self.scope,
            subject_ref=self.subject,purpose='local_intake',authorization_ref=self.authorization)
