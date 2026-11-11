"""Atomic outbox reservation and the only API write dispatch boundary."""

from datetime import datetime, timezone

from dataagent_contracts.workflow import ActionReceipt, ActionRecord

from .adapters.playwright_browser import PlaywrightBrowser
from .bindings import digest
from .planner import at, matches, validate_parameters
from .reconciliation import classify, effect_record
from .store import LeaseLost


class ActionGateway:
    def __init__(self, store):
        self.store = store

    def _check(self, db, run_id, token, workflow_revision, step_id=None):
        self.store.check_lease(db, run_id, token)
        run = self.store.run(db, run_id)
        if not self.store.authorized(db):
            raise LeaseLost("workflow authorization was revoked")
        if run.workflow_revision != workflow_revision or (step_id is not None and run.current_step != step_id):
            raise LeaseLost("workflow control point or revision changed")
        if run.state not in {"active", "unknown"}:
            raise LeaseLost(f"workflow cannot dispatch from state {run.state!r}")
        return run

    @staticmethod
    def _receipt(action, source, record, response=None, observation_ref=None):
        action.state = "applied"
        action.message = None
        action.receipt = ActionReceipt(
            id=f"receipt:{action.id}", source=source, observed_at=datetime.now(timezone.utc),
            record=record, response=response, observation_ref=observation_ref,
        )

    def execute(self, run, step, token, client, snapshot, arguments):
        operation = client.environment.operations[step.operation_id]
        effect = operation.effect
        action_id = digest([client.environment.identity, effect.action, run.business_key])
        with self.store.transaction() as db:
            self._check(db, run.id, token, run.workflow_revision, step.id)
            linked = self.store.linked_action(db, run.id, step.id)
            prior = self.store.action(db, linked) if linked else None

        if linked is not None and linked != action_id:
            raise ValueError("revised step changes a reserved business action")
        if prior is not None and prior[0].state in {"in_flight", "unknown", "partial"}:
            return self._reconcile(run, step, token, client, snapshot, action_id)
        if prior is not None and prior[0].state == "applied":
            return prior[0]

        record = effect_record(client, snapshot, effect, run.business_key)
        if effect.business_key_field:
            arguments["body"][effect.business_key_field] = run.business_key
        if effect.request_key_field:
            arguments["body"][effect.request_key_field] = action_id
        if effect.record_id_parameter:
            if record is None:
                raise ValueError("no record exists for the scoped business key")
            arguments["path"][effect.record_id_parameter] = at(record, effect.record_id_pointer)
        validate_parameters(arguments, snapshot.capabilities[step.operation_id], operation)
        action = ActionRecord(
            id=action_id, operation_id=step.operation_id, action=effect.action, business_key=run.business_key,
            parameters_digest=digest([step.operation_id, arguments]), state="reserved",
        )
        existing = classify(effect, arguments, record)
        with self.store.transaction() as db:
            self._check(db, run.id, token, run.workflow_revision, step.id)
            action = self.store.reserve(db, run, step.id, action, arguments)
            if action.state == "applied":
                return action
            if action.state in {"reserved", "not_applied"}:
                if existing == "applied":
                    self._receipt(action, "preexisting", record)
                    self.store.save_action(db, action)
                    return action
                if existing == "partial":
                    action.state = "partial"
                    action.message = "existing record partially matches the business action"
                    self.store.save_action(db, action)
                    return action
                if (effect.before and not matches(effect.before, record)) or (not effect.before and record is not None):
                    action.state = "not_applied"
                    action.message = "business precondition does not hold"
                    self.store.save_action(db, action)
                    return action
                action.state = "in_flight"
                action.dispatch_count += 1
                action.message = None
                self.store.save_action(db, action)
                self.store.set_dispatch_owner(db, action.id, run.id, token)
                dispatch = True
            else:
                dispatch = False
        if dispatch:
            result = self._dispatch(run, step, token, client, action_id)
            if result.state == "unknown":
                return result
        return self._reconcile(run, step, token, client, snapshot, action_id)

    def _dispatch(self, run, step, token, client, action_id):
        # Commit in_flight first. Keep this separate lock across dispatch so that
        # a revocation or lease takeover and the start of HTTP dispatch are ordered.
        with self.store.transaction() as db:
            self._check(db, run.id, token, run.workflow_revision, step.id)
            if self.store.linked_action(db, run.id, step.id) != action_id:
                raise LeaseLost("workflow no longer owns the reserved dispatch")
            action, arguments, _ = self.store.action(db, action_id)
            if action.state != "in_flight":
                return action
            owner = self.store.dispatch_owner(db, action_id)
            if (owner["owner_run"], owner["owner_token"]) != (run.id, token):
                raise LeaseLost("workflow worker does not own the in-flight action")
            try:
                response = client._dispatch(action.operation_id, arguments)
            except ValueError as exc:
                action.state = "unknown"
                action.message = str(exc)
                self.store.save_action(db, action)
            else:
                self.store.save_action(db, action, response=response)
            self.store.set_dispatch_owner(db, action.id)
            return action

    def _reconcile(self, run, step, token, client, snapshot, action_id):
        with self.store.transaction() as db:
            self._check(db, run.id, token, run.workflow_revision, step.id)
            action, arguments, response = self.store.action(db, action_id)
            if action.state == "applied" or self.store.dispatch_pending(db, action_id):
                return action
        effect = client.environment.operations[step.operation_id].effect
        try:
            record = effect_record(client, snapshot, effect, run.business_key)
            state = classify(effect, arguments, record)
        except ValueError:
            record, state = None, "unknown"
        observation = None
        if state == "unknown" and effect.browser_lookup_page:
            try:
                observation = PlaywrightBrowser(client.environment, self.store.path.parent).observe(
                    snapshot.environment_id, effect.browser_lookup_page, run.scope_ref,
                    business_key=run.business_key,
                )
            except ValueError:
                pass
            if observation and matches(effect.applied, observation.record_evidence):
                record, state = observation.record_evidence, "applied"
        with self.store.transaction() as db:
            self._check(db, run.id, token, run.workflow_revision, step.id)
            latest, _, latest_response = self.store.action(db, action_id)
            if latest.state in {"applied", "not_applied"} or latest.dispatch_count != action.dispatch_count:
                return latest
            if observation is not None:
                self.store.put(db, "web-observation", observation)
            if state == "applied":
                observed_response = latest_response if latest_response is not None else response
                if observation is not None:
                    self._receipt(latest, "browser_reconciliation", record, observed_response, observation.id)
                else:
                    source = "response" if observed_response is not None else "reconciliation"
                    self._receipt(latest, source, record, observed_response)
            else:
                latest.state = state
                latest.message = f"business-key query returned outcome {state}"
            self.store.save_action(db, latest)
            return latest
