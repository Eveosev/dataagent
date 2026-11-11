"""Execute typed workflow nodes and durably commit each control point."""

from .adapters.api import ApiError
from .discovery import schema_revision
from .planner import at, matches, resolve, validate_parameters, validate_value
from .reconciliation import query_record
from .store import LeaseLost
from .waits import record_wait

ADVANCEABLE = {"active", "waiting", "unknown"}


def finish_step(run, step, output, *, next_step=None):
    run.outputs[step.id] = output
    run.completed.append(step.id)
    run.current_step = next_step or step.next
    run.state = "completed" if run.current_step is None else "active"
    run.message = None


class WorkflowRunner:
    def __init__(self, store, gateway, lease_seconds):
        self.store = store
        self.gateway = gateway
        self.lease_seconds = lease_seconds

    def preserve_pending_action(self, db, run):
        action_id = self.store.linked_action(db, run.id, run.current_step)
        if action_id:
            action, _, _ = self.store.action(db, action_id)
            run.unknown_action_ref = action_id if action.state in {"in_flight", "partial", "unknown"} else None
            if action.receipt and action.receipt.id not in run.receipt_refs:
                run.receipt_refs.append(action.receipt.id)

    def claim(self, run_id):
        with self.store.transaction() as db:
            run = self.store.run(db, run_id)
            if run.state not in ADVANCEABLE:
                return run, None
            if not self.store.authorized(db):
                self.preserve_pending_action(db, run)
                run.state = "revoked"
                run.message = "workflow authorization was revoked"
                self.store.update_run(db, run)
                return run, None
            return run, self.store.claim(db, run_id, self.lease_seconds)

    def advance(self, run, spec, token, client, snapshot, max_steps):
        nodes = {step.id: step for step in spec.nodes}
        try:
            try:
                drift = schema_revision(client.description(), client.environment) != snapshot.revision
            except ApiError as exc:
                return self._set_state(run, token, run.state, str(exc))
            if drift:
                return self._set_state(run, token, "replan_required", "validated environment revision has changed")
            for _ in range(max_steps):
                with self.store.transaction() as db:
                    self.store.renew(db, run.id, token, self.lease_seconds)
                    run = self.store.run(db, run.id)
                    if not self.store.authorized(db):
                        self.preserve_pending_action(db, run)
                        run.state = "revoked"
                        run.message = "workflow authorization was revoked"
                        self.store.update_run(db, run)
                        return run
                step = nodes[run.current_step]
                try:
                    run = self._step(run, step, token, client, snapshot)
                except LeaseLost:
                    raise
                except ApiError as exc:
                    return self._set_state(run, token, run.state, str(exc))
                except ValueError as exc:
                    return self._set_state(run, token, "failed", str(exc))
                if run.state != "active":
                    break
            return run
        except LeaseLost:
            with self.store.transaction() as db:
                return self.store.run(db, run.id)
        finally:
            with self.store.transaction() as db:
                self.store.release(db, run.id, token)

    def _set_state(self, run, token, state, message):
        with self.store.transaction() as db:
            run = self._check(db, run, token)
            run.state = state
            run.message = message
            self.store.update_run(db, run)
            return run

    def _check(self, db, run, token):
        self.store.check_lease(db, run.id, token)
        current = self.store.run(db, run.id)
        if current.revision != run.revision:
            raise LeaseLost("workflow run changed")
        return current

    def _step(self, run, step, token, client, snapshot):
        context = {"inputs": run.inputs, "steps": run.outputs, "business_key": run.business_key}
        next_step = None
        action = None
        output = None
        if step.kind == "transform":
            output = resolve(step.assign, context)
        elif step.kind == "decide":
            output = matches(step.condition, context)
            next_step = step.next if output else step.otherwise
        elif step.kind != "human":
            arguments = resolve(step.parameters.model_dump(mode="json", exclude={"extensions"}), context)
            if step.kind == "act":
                if schema_revision(client.description(), client.environment) != snapshot.revision:
                    return self._set_state(run, token, "replan_required", "validated environment revision has changed")
                action = self.gateway.execute(run, step, token, client, snapshot, arguments)
                if action.receipt:
                    output = action.receipt.record
            else:
                output = self._read(run, step, client, snapshot, arguments)
        with self.store.transaction() as db:
            run = self._check(db, run, token)
            if not self.store.authorized(db):
                self.preserve_pending_action(db, run)
                run.state = "revoked"
                run.message = "workflow authorization was revoked"
            elif step.kind == "human":
                run.state = "needs_input"
                run.message = step.prompt
            elif action and action.state != "applied":
                run.state = "unknown" if action.state in {"in_flight", "unknown", "partial"} else "active"
                run.unknown_action_ref = action.id if run.state == "unknown" else None
                run.message = action.message or "business action is already in flight"
                if action.state == "not_applied" and action.message == "business precondition does not hold":
                    run.state = "failed"
                elif action.state == "not_applied":
                    # Resume the original outbox row on the next explicit advance.
                    run.state = "unknown"
                    run.unknown_action_ref = action.id
            elif step.kind == "wait" and not matches(step.condition, {"response": output}):
                run.state = "waiting"
                run.wait_ref = record_wait(self.store, db, run, step.id, output, "waiting")
            elif step.kind == "verify" and not matches(step.condition, {"response": output}):
                run.outputs[step.id] = output
                run.state = "failed"
                run.message = "observed business state does not satisfy the acceptance condition"
            else:
                if action:
                    if action.receipt.id not in run.receipt_refs:
                        run.receipt_refs.append(action.receipt.id)
                    run.unknown_action_ref = None
                if step.kind == "wait":
                    record_wait(self.store, db, run, step.id, output, "consumed")
                    run.wait_ref = None
                finish_step(run, step, output, next_step=next_step)
            self.store.update_run(db, run)
            return run

    @staticmethod
    def _read(run, step, client, snapshot, arguments):
        policy = client.environment.operations[step.operation_id]
        if policy.business_key_parameter:
            arguments["query"][policy.business_key_parameter] = run.business_key
        if policy.record_lookup:
            record = query_record(
                client, snapshot, policy.record_lookup, policy.collection_pointer,
                run.business_key, policy.record_key_pointer,
            )
            if record is None:
                raise ValueError("no record exists for the scoped business key")
            record_id = at(record, policy.record_id_pointer)
            arguments["path"][policy.record_id_parameter] = record_id
        observation = snapshot.capabilities[step.operation_id]
        validate_parameters(arguments, observation, policy)
        response = client.read(step.operation_id, arguments)
        if observation.response_schema is not None:
            validate_value(response, observation.response_schema)
        if policy.record_lookup and (
            at(response, policy.record_id_pointer) != record_id
            or at(response, policy.record_key_pointer) != run.business_key
        ):
            raise ValueError("status response does not identify the scoped business record")
        return response
