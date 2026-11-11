"""Public environment and workflow services with trusted host configuration."""

from uuid import uuid4

from pydantic import ValidationError

from dataagent_contracts.environment import EnvironmentSnapshot, UIObservation
from dataagent_contracts.intake import WorkSpec
from dataagent_contracts.workflow import WorkflowDraft, WorkflowRun, WorkflowSpec, WorkflowValidationReport

from .action_gateway import ActionGateway
from .adapters.api import ApiClient
from .bindings import HostConfig, digest, encode
from .discovery import discover, schema_revision
from .planner import same, validate_spec, validate_start_bindings, validate_value
from .runner import WorkflowRunner, finish_step
from .store import AuthorityRevoked, OperationsStore


class EnvironmentService:
    def __init__(self, path, config, *, request_timeout=5.0):
        if request_timeout <= 0:
            raise ValueError("request timeout must be positive")
        self.config = HostConfig.model_validate(config)
        self.store = OperationsStore(path, self.config.scope_ref, self.config.authorization_ref)
        self.request_timeout = request_timeout

    def _client(self, environment_id):
        environment = self.config.environments.get(environment_id)
        if environment is None:
            raise ValueError("environment is outside trusted host configuration")
        return ApiClient(environment, self.request_timeout)

    def _check_authority(self, db):
        if not self.store.authorized(db):
            raise AuthorityRevoked("workflow authorization was revoked")

    def _fresh(self, snapshot):
        client = self._client(snapshot.environment_id)
        if schema_revision(client.description(), client.environment) != snapshot.revision:
            raise ValueError("validated environment revision has changed; discover and validate a new workflow")

    def discover(self, environment_id):
        with self.store.transaction() as db:
            self._check_authority(db)
        client = self._client(environment_id)
        snapshot = discover(client, environment_id, self.config.scope_ref, self.config.authorization_ref)
        with self.store.transaction() as db:
            self._check_authority(db)
            self.store.put(db, "snapshot", snapshot)
        return snapshot

    def observe_web(self, environment_id, page_ref):
        from .adapters.playwright_browser import PlaywrightBrowser
        environment = self.config.environments.get(environment_id)
        if environment is None:
            raise ValueError("environment is outside trusted host configuration")
        with self.store.transaction() as db:
            self._check_authority(db)
        observation = PlaywrightBrowser(environment, self.store.path.parent).observe(
            environment_id, page_ref, self.config.scope_ref,
        )
        with self.store.transaction() as db:
            self._check_authority(db)
            self.store.put(db, "web-observation", observation)
        return observation

    def web_observation(self, observation_id):
        with self.store.transaction() as db:
            self._check_authority(db)
            return self.store.get(db, "web-observation", observation_id, UIObservation)


class WorkflowService(EnvironmentService):
    def __init__(self, path, config, *, workbench_store=None, request_timeout=5.0, lease_seconds=30.0):
        if request_timeout >= lease_seconds:
            raise ValueError("request timeout must be shorter than the workflow lease")
        super().__init__(path, config, request_timeout=request_timeout)
        self.workbench_store = workbench_store
        self.gateway = ActionGateway(self.store)
        self.runner = WorkflowRunner(self.store, self.gateway, lease_seconds)

    def _work(self, work_spec_id):
        work_spec_id, _, requested_revision = work_spec_id.partition("@")
        configured = next((work for work in self.config.work_specs if work.id == work_spec_id), None)
        if configured is not None:
            if requested_revision in {"", configured.revision}:
                return configured.model_copy(deep=True)
            raise ValueError("configured WorkSpec revision has changed")
        if self.workbench_store is not None:
            row = self.workbench_store.current("goal", work_spec_id, scope=self.config.scope_ref)
            if row is not None and requested_revision in {"", row["revision"]}:
                work = WorkSpec.model_validate({**row["body"], "id": row["id"], "revision": row["revision"]})
                if work.authorization_ref == self.config.authorization_ref:
                    return work
        raise ValueError("WorkSpec is outside the trusted scope and authorization")

    def draft(self, work_spec_id, snapshot_id, run_id=None):
        work = self._work(work_spec_id)
        with self.store.transaction() as db:
            self._check_authority(db)
            snapshot = self.store.get(db, "snapshot", snapshot_id, EnvironmentSnapshot)
            environment = self._client(snapshot.environment_id).environment
            run = self.store.run(db, run_id) if run_id else None
            if run:
                self._check_replan_run(db, run, work, snapshot)
            request = {
                "kind": "replan_workflow" if run else "draft_workflow",
                "goal": work.goal,
                "acceptance_criteria": work.acceptance_criteria,
                "work_spec": work.model_dump(mode="json"),
                "environment": snapshot.model_dump(mode="json"),
                "effect_policies": {
                    name: policy.effect.model_dump(mode="json")
                    for name, policy in environment.operations.items() if policy.effect is not None
                },
                "response_schema": WorkflowSpec.model_json_schema(),
            }
            if run:
                request["current_run"] = run.model_dump(mode="json")
                previous = self.store.get(db, "proposal", run.workflow_revision, WorkflowValidationReport)
                request["previous_spec"] = previous.spec.model_dump(mode="json")
            result = WorkflowDraft(
                id=uuid4().hex, work_spec=work, snapshot_id=snapshot_id, scope_ref=self.config.scope_ref,
                run_id=run_id, run_revision=run.revision if run else None, inference_request=request,
            )
            self.store.put(db, "draft", result)
        return result

    def _check_replan_run(self, db, run, work, snapshot):
        if run.work_spec != work:
            raise ValueError("a workflow replan must preserve the pinned WorkSpec and its acceptance criteria")
        original = self.store.get(db, "snapshot", run.snapshot_id, EnvironmentSnapshot)
        if (
            snapshot.environment_id != original.environment_id
            or snapshot.environment_identity != original.environment_identity
        ):
            raise ValueError("a workflow replan must preserve the business environment")
        if run.state not in {"active", "waiting", "needs_input", "paused", "unknown", "replan_required", "failed"}:
            raise ValueError(f"workflow in state {run.state!r} cannot be replanned")
        if self.store.current_lease(db, run.id):
            raise ValueError("wait for the current workflow worker to release its lease")

    def _check_replan_spec(self, db, run, spec):
        previous = self.store.get(db, "proposal", run.workflow_revision, WorkflowValidationReport)
        prior_nodes = {step.id: step for step in previous.spec.nodes}
        next_nodes = {step.id: step for step in spec.nodes}
        if previous.spec.entry != spec.entry or run.current_step not in next_nodes:
            raise ValueError("replan must preserve the entry and current control point")
        for step_id in run.completed:
            if prior_nodes[step_id] != next_nodes.get(step_id):
                raise ValueError(f"replan changes completed step {step_id!r}")
        if self.store.linked_action(db, run.id, run.current_step) and prior_nodes[run.current_step] != next_nodes[run.current_step]:
            raise ValueError("replan changes a step with a reserved action")

    def submit_proposal(self, draft_id, spec):
        with self.store.transaction() as db:
            self._check_authority(db)
            draft = self.store.get(db, "draft", draft_id, WorkflowDraft)
            snapshot = self.store.get(db, "snapshot", draft.snapshot_id, EnvironmentSnapshot)
            report = WorkflowValidationReport(id=uuid4().hex, draft_id=draft.id, spec_digest=digest(spec), valid=False)
            try:
                report.spec = WorkflowSpec.model_validate(spec)
                validate_spec(report.spec, draft.work_spec, snapshot, self._client(snapshot.environment_id).environment)
                if self._work(draft.work_spec.id) != draft.work_spec:
                    raise ValueError("pinned WorkSpec has changed")
                if draft.run_id:
                    run = self.store.run(db, draft.run_id)
                    self._check_replan_run(db, run, draft.work_spec, snapshot)
                    if run.revision != draft.run_revision:
                        raise ValueError("workflow progressed after the replan draft")
                    self._check_replan_spec(db, run, report.spec)
                report.valid = True
                report.validated_steps = [node.id for node in report.spec.nodes]
                report.unobserved_steps = report.validated_steps.copy()
            except ValidationError as exc:
                report.issues = [
                    f"{'/'.join(map(str, err['loc']))}: {err['msg']}"
                    for err in exc.errors(include_input=False)
                ]
            except ValueError as exc:
                report.issues = [str(exc)]
            self.store.put(db, "proposal", report)
            return report

    def start(self, proposal_id, business_key, inputs):
        with self.store.transaction() as db:
            self._check_authority(db)
            proposal = self.store.get(db, "proposal", proposal_id, WorkflowValidationReport)
            if not proposal.valid or proposal.spec is None:
                raise ValueError("workflow start requires a validated proposal")
            draft = self.store.get(db, "draft", proposal.draft_id, WorkflowDraft)
            snapshot = self.store.get(db, "snapshot", draft.snapshot_id, EnvironmentSnapshot)
        self._fresh(snapshot)
        environment = self._client(snapshot.environment_id).environment
        if (
            not isinstance(business_key, str) or not 1 <= len(business_key) <= 256
            or not business_key.startswith(environment.business_key_prefix)
            or not business_key.strip() or any(ord(ch) < 32 for ch in business_key)
        ):
            raise ValueError("business key is outside the trusted environment scope")
        encode(inputs)
        validate_value(inputs, proposal.spec.input_schema)
        validate_start_bindings(proposal.spec, inputs, business_key, snapshot, environment)
        with self.store.transaction() as db:
            self._check_authority(db)
            if self._work(draft.work_spec.id) != draft.work_spec:
                raise ValueError("pinned WorkSpec has changed")
            if draft.run_id:
                run = self.store.run(db, draft.run_id)
                self._check_replan_run(db, run, draft.work_spec, snapshot)
                if run.revision != draft.run_revision:
                    raise ValueError("workflow progressed after the replan draft")
                if run.business_key != business_key or not same(run.inputs, inputs):
                    raise ValueError("replan must preserve the business key and starting inputs")
                self._check_replan_spec(db, run, proposal.spec)
                run.workflow_revision = proposal.id
                run.snapshot_id = snapshot.id
                if run.state in {"replan_required", "failed"}:
                    run.state = "active"
                self.store.update_run(db, run)
                return run
            run_id = uuid4().hex
            run = WorkflowRun(
                id=run_id, workflow_revision=proposal.id, work_spec=draft.work_spec, snapshot_id=snapshot.id,
                scope_ref=self.config.scope_ref, business_key=business_key, inputs=inputs,
                current_step=proposal.spec.entry, job_ref=f"workflow-run:{run_id}",
            )
            self.store.put(db, "run", run)
            return run

    def advance(self, run_id, max_steps=100):
        if not 1 <= max_steps <= 100:
            raise ValueError("max_steps must be between 1 and 100")
        run, token = self.runner.claim(run_id)
        if token is None:
            return run
        try:
            with self.store.transaction() as db:
                proposal = self.store.get(db, "proposal", run.workflow_revision, WorkflowValidationReport)
                snapshot = self.store.get(db, "snapshot", run.snapshot_id, EnvironmentSnapshot)
            client = self._client(snapshot.environment_id)
        except BaseException:
            with self.store.transaction() as db:
                self.store.release(db, run_id, token)
            raise
        return self.runner.advance(run, proposal.spec, token, client, snapshot, max_steps)

    def status(self, run_id):
        with self.store.transaction() as db:
            return self.store.run(db, run_id)

    def actions(self, run_id):
        with self.store.transaction() as db:
            self.store.run(db, run_id)
            return self.store.actions(db, run_id)

    def waits(self, run_id):
        with self.store.transaction() as db:
            self.store.run(db, run_id)
            return self.store.waits(db, run_id)

    def revoke(self):
        with self.store.transaction() as db:
            self.store.revoke(db)

    def control(self, run_id, command, values=None):
        with self.store.transaction() as db:
            run = self.store.run(db, run_id)
            self._check_authority(db)
            if command != "provide_input" and values is not None:
                raise ValueError("values are used only by provide_input")
            if command == "pause" and run.state in {"active", "waiting", "unknown"}:
                self.runner.preserve_pending_action(db, run)
                run.state = "paused"
            elif command == "resume" and run.state == "paused":
                run.state = "unknown" if run.unknown_action_ref else "active"
            elif command == "cancel" and run.state in {"active", "paused", "waiting", "needs_input", "unknown", "replan_required"}:
                if run.wait_ref:
                    wait = next(wait for wait in self.store.waits(db, run.id) if wait.id == run.wait_ref)
                    self.store.put_wait(db, wait.model_copy(update={"state": "cancelled"}))
                    run.wait_ref = None
                self.runner.preserve_pending_action(db, run)
                run.state = "cancelled"
            elif command == "provide_input" and run.state == "needs_input":
                proposal = self.store.get(db, "proposal", run.workflow_revision, WorkflowValidationReport)
                step = next(step for step in proposal.spec.nodes if step.id == run.current_step)
                encode(values)
                validate_value(values, step.input_schema)
                finish_step(run, step, values)
            else:
                raise ValueError(f"command {command!r} is unavailable in state {run.state!r}")
            db.execute("DELETE FROM ops_leases WHERE run_id=?", (run_id,))
            self.store.update_run(db, run)
            return run


OperationsService = WorkflowService
