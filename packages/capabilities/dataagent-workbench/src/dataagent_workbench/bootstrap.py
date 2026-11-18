"""Trusted local-owner composition; transports cannot replace its authority."""
import hashlib
import os
import secrets
import json
from pathlib import Path
from uuid import uuid4
from pydantic import Field, model_validator
from dataagent_contracts.core import CallContext
from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
from .session_service import SessionService
from .tool_schema import MODELS, TOOLS, Start, StartTarget


def _install_revision_start():
    """Extend ``intake_start`` with the discovery-only revision target.

    ``tool_schema`` is the shared input surface owned by the intake tool; a
    published-ontology revision is a workbench capability.  Adding the optional
    field here keeps the shared module untouched while still advertising it in
    the MCP ``tools/list`` response and validating it on every transport.
    """
    base = MODELS.get('intake_start')
    if base is None or 'revise_ontology_id' in base.model_fields:
        return

    class RevisionStart(base):
        revise_ontology_id: str | None = Field(default=None, min_length=2,
            max_length=64, pattern=r'^[a-z][a-z0-9-]*[a-z0-9]$',
            description='修订目标：mode=ontology_discovery 时可选，必须是已注册、'
                        '未停用、发现发布的本体；补全的 ontology_id 必须与它一致')

        @model_validator(mode='after')
        def _route_revision_target(self):
            if self.revise_ontology_id is None:
                return self
            if self.mode != 'ontology_discovery':
                raise ValueError('revise_ontology_id requires ontology_discovery mode')
            if self.target is not None:
                raise ValueError('name either revise_ontology_id or target, not both')
            self.target = StartTarget(ontology_id=self.revise_ontology_id)
            return self

    MODELS['intake_start'] = RevisionStart
    for tool in TOOLS:
        if tool.get('name') == 'intake_start':
            tool['inputSchema'] = RevisionStart.model_json_schema()


_install_revision_start()


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
        # The builtin procurement ontology is registered as one workspace
        # ontology.  The pointer chooses the definition new tasks default to;
        # publishing a discovery ontology moves it, retiring clears it.
        self.definition=load_definition(Path(__file__).parent/'ontologies/procurement.json')
        self.ontology.register(self.definition,self.ctx)
        self.ontology.ensure_pointer(self.definition,self.ctx)
        # Read lazily: a host may swap the builtin and register its new revision.
        self.sessions = SessionService(self.store,self.scope,self.subject,self.authorization,
            default_target=self._default_target)
        from .intake_service import IntakeService
        from .ontology_publish import PublishService, record_source_versions
        workbench = self

        class _ObservedIntake(IntakeService):
            """Pin each source's bytes right after its profile is written.

            Intake probes sources one after another inside one advance.  Waiting
            for the whole advance would let a later source rewrite an earlier
            one before its baseline is pinned.
            """

            def _store_profile(self, session, versions, source, profile, ctx):
                session = super()._store_profile(
                    session, versions, source, profile, ctx)
                record_source_versions(workbench, session, source.source_id)
                return session

        self.intake=_ObservedIntake(self)
        from .ontology_discovery import DiscoveryService
        self.discovery = DiscoveryService(self)
        self.publisher = PublishService(self)
        # Read-only published-instance queries (D4); no state of their own.
        from .query_service import QueryService
        self.queries = QueryService(self)

    def _default_target(self):
        return self.ontology.default_definition(self.ctx)

    @property
    def ctx(self):
        return CallContext(request_id=uuid4().hex,scope_ref=self.scope,
            subject_ref=self.subject,purpose='local_intake',authorization_ref=self.authorization)
