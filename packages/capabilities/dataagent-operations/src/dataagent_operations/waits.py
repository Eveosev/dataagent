"""Persist a business observation and its consumption with the workflow cursor."""

from datetime import datetime, timezone

from dataagent_contracts.workflow import WaitRecord


def record_wait(store, db, run, step_id, observation, state):
    wait = WaitRecord(
        id=f"wait:{run.id}:{step_id}", run_id=run.id, step_id=step_id,
        state=state, observation=observation, observed_at=datetime.now(timezone.utc),
    )
    store.put_wait(db, wait)
    return wait.id
