from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from conftest import approve, start


def test_success_without_receipt_is_reconciled(ready, configured, business):
    from dataagent_operations.service import OperationsService
    service, _, proposal = ready
    response = business[2].post("/faults", headers={"x-admin-token": "evaluation-only"}, json={
        "lose_next_submit_response": True, "response_delay_seconds": 0.65,
    })
    assert response.status_code == 200
    run = start(service, proposal)
    unknown = service.advance(run.id)
    assert unknown.state == "unknown"
    assert unknown.unknown_action_ref
    db, config = configured
    restarted = OperationsService(db, config)
    recovered = restarted.advance(run.id)
    assert recovered.state == "waiting"
    assert restarted.actions(run.id)[-1].receipt.source == "reconciliation"
    assert restarted.actions(run.id)[-1].dispatch_count == 1
    assert business[1].get("/api/orders/records").json()["total"] == 1


def test_revoked_authority_blocks_next_action(ready, business):
    service, _, proposal = ready
    run = start(service, proposal)
    service.advance(run.id, max_steps=3)
    service.revoke()
    blocked = service.advance(run.id)
    assert blocked.state == "revoked"
    records = business[1].get("/api/orders/records").json()["records"]
    assert [record["status"] for record in records] == ["draft"]
    assert len(service.actions(run.id)) == 1


def test_completed_steps_are_not_replayed(ready, configured, business):
    from dataagent_operations.service import OperationsService
    service, _, proposal = ready
    run = start(service, proposal)
    assert service.advance(run.id).state == "waiting"
    approve(business)
    db, config = configured
    restarted = OperationsService(db, config)
    assert restarted.advance(run.id).state == "completed"
    assert restarted.advance(run.id).state == "completed"
    actions = restarted.actions(run.id)
    assert [action.dispatch_count for action in actions] == [1, 1]


def test_atomic_reservation_blocks_duplicate_workers_and_runs(ready, configured, business):
    from dataagent_operations.service import OperationsService
    service, _, proposal = ready
    first = start(service, proposal)
    second = start(service, proposal)
    db, config = configured
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda run: OperationsService(db, config).advance(run.id), [first, second]))
    assert any(run.state == "waiting" for run in results)
    for run in (first, second):
        assert service.advance(run.id).state == "waiting"
        assert [action.dispatch_count for action in service.actions(run.id)] == [1, 1]
    assert business[1].get("/api/orders/records").json()["total"] == 1


def test_replan_keeps_goal_and_completed_receipts(ready, workflow_spec, business):
    service, snapshot, initial = ready
    run = start(service, initial)
    waiting = service.advance(run.id)
    draft = service.draft("purchase", snapshot.id, run_id=run.id)
    modified = deepcopy(workflow_spec)
    modified["nodes"][-2]["next"] = "collect_observation"
    modified["nodes"].append({
        "id": "collect_observation", "kind": "transform", "next": "verify",
        "assign": {"observed_status": {"$ref": "/steps/approval/status"}},
    })
    report = service.submit_proposal(draft.id, modified)
    assert report.valid, report.issues
    updated = service.start(report.id, "po-work", {"supplier": "Paper Ltd", "amount": "87.50"})
    assert updated.id == run.id
    assert updated.work_spec == waiting.work_spec
    assert updated.receipt_refs == waiting.receipt_refs
    assert updated.workflow_revision != waiting.workflow_revision
    approve(business)
    completed = service.advance(run.id)
    assert completed.state == "completed"
    assert completed.outputs["collect_observation"] == {"observed_status": "approved"}


def test_replan_cannot_change_completed_step(ready, workflow_spec):
    service, snapshot, initial = ready
    run = start(service, initial)
    service.advance(run.id)
    draft = service.draft("purchase", snapshot.id, run_id=run.id)
    modified = deepcopy(workflow_spec)
    modified["nodes"][0]["assign"]["data"]["currency"] = "EUR"
    report = service.submit_proposal(draft.id, modified)
    assert not report.valid


def test_expired_worker_cannot_dispatch_new_request(ready, business):
    service, snapshot, proposal = ready
    run = service.advance(start(service, proposal).id, max_steps=2)
    with service.store.transaction() as db:
        claim = service.store.claim(db, run.id, lease_seconds=-1)
    step = next(step for step in proposal.spec.nodes if step.id == run.current_step)
    arguments = {"path": {}, "query": {}, "body": {"data": run.outputs["prepare"]["data"]}}
    with pytest.raises(ValueError, match="lease"):
        service.gateway.execute(run, step, claim, service._client(snapshot.environment_id), snapshot, arguments)
    assert business[1].get("/api/orders/records").json()["total"] == 0


def test_lease_expiry_does_not_clear_unknown_effect(ready, configured, business):
    from dataagent_operations.service import OperationsService
    service, _, proposal = ready
    response = business[2].post("/faults", headers={"x-admin-token": "evaluation-only"}, json={
        "lose_next_submit_response": True, "response_delay_seconds": 0.65,
    })
    assert response.status_code == 200
    run = start(service, proposal)
    unknown = service.advance(run.id)
    assert unknown.state == "unknown"
    with service.store.transaction() as db:
        service.store.claim(db, run.id, lease_seconds=-1)
    db, config = configured
    restarted = OperationsService(db, config)
    assert restarted.actions(run.id)[-1].state == "unknown"
    assert restarted.advance(run.id).state == "waiting"
    assert restarted.actions(run.id)[-1].dispatch_count == 1


def test_unknown_absence_of_effect_does_not_reissue(ready, business, dispatch_fault):
    service, _, proposal = ready
    dispatch_fault["reject_once"] = True
    run = start(service, proposal)
    assert service.advance(run.id).state == "unknown"
    assert service.advance(run.id).state == "unknown"
    assert service.actions(run.id)[-1].state == "unknown"
    assert service.actions(run.id)[-1].dispatch_count == 1
    record = business[1].get("/api/orders/records").json()["records"][0]
    assert record["status"] == "draft"


def test_partial_effect_waits_without_reissuing(ready, business):
    service, _, proposal = ready
    result = business[1].post("/api/orders/records", json={
        "business_key": "po-work", "data": {"supplier": "Other Ltd", "total": "87.50", "currency": "CNY"},
    })
    assert result.status_code == 201
    run = start(service, proposal)
    assert service.advance(run.id).state == "unknown"
    assert service.advance(run.id).state == "unknown"
    action = service.actions(run.id)[0]
    assert action.state == "partial"
    assert action.dispatch_count == 0
    assert business[1].get("/api/orders/records").json()["records"][0]["data"]["supplier"] == "Other Ltd"


def test_reliable_negative_proof_can_resume_same_action(configured, workflow_spec, dispatch_fault):
    from dataagent_operations.service import OperationsService

    db, config = configured
    effect = config["environments"]["test-orders"]["operations"]["orders_submit_record"]["effect"]
    effect["definitive_not_applied"] = {"pointer": "/dispatch_proof", "one_of": ["definitively_not_applied"]}
    dispatch_fault.update(reject_once=True, proof=True)
    service = OperationsService(db, config)
    draft = service.draft("purchase", service.discover("test-orders").id)
    proposal = service.submit_proposal(draft.id, workflow_spec)
    run = start(service, proposal)
    assert service.advance(run.id).state == "unknown"
    first = service.actions(run.id)[-1]
    assert first.state == "unknown"
    assert service.advance(run.id).state == "unknown"
    assert service.actions(run.id)[-1].state == "not_applied"
    assert service.advance(run.id).state == "waiting"
    final = service.actions(run.id)[-1]
    assert final.id == first.id
    assert final.parameters_digest == first.parameters_digest
    assert final.dispatch_count == 2
    assert final.state == "applied"
