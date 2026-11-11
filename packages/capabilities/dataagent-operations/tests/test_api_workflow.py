from copy import deepcopy

import pytest

from conftest import approve, start


def test_discovery_does_not_execute_write_actions(configured, business):
    from dataagent_operations.service import OperationsService
    db, config = configured
    snapshot = OperationsService(db, config).discover("test-orders")
    create = snapshot.capabilities["orders_create_draft"]
    assert create.request_schema["properties"]["data"]["required"] == ["supplier", "total", "currency"]
    assert create.verification == "described"
    assert create.authorized
    assert snapshot.capabilities["orders_query_records"].verification == "observed"
    assert not snapshot.capabilities["expenses_create_draft"].authorized
    assert business[1].get("/api/orders/records").json()["total"] == 0


def test_approval_wait_survives_restart(ready, configured, business):
    from dataagent_operations.service import OperationsService
    service, _, proposal = ready
    run = start(service, proposal)
    waiting = service.advance(run.id)
    assert waiting.state == "waiting"
    assert waiting.wait_ref
    assert waiting.outputs["observe"]["native_status"] == "AWAITING_REVIEW"
    record = approve(business)
    db, config = configured
    restarted = OperationsService(db, config)
    complete = restarted.advance(run.id)
    assert complete.state == "completed"
    assert complete.outputs["verify"]["id"] == record["id"]
    assert complete.outputs["verify"]["status"] == "approved"
    assert complete.receipt_refs == waiting.receipt_refs
    assert restarted.waits(run.id)[0].state == "consumed"


def test_unvalidated_workflow_cannot_start(ready, workflow_spec, business):
    service, snapshot, _ = ready
    draft = service.draft("purchase", snapshot.id)
    invalid = deepcopy(workflow_spec)
    invalid["nodes"][3]["operation_id"] = "expenses_create_draft"
    report = service.submit_proposal(draft.id, invalid)
    assert not report.valid
    with pytest.raises(ValueError):
        service.start(report.id, "po-invalid", {"supplier": "Paper Ltd", "amount": "87.50"})
    assert business[1].get("/api/orders/records").json()["total"] == 0


def test_unvalidated_parameters_cannot_start(ready, workflow_spec, business):
    service, snapshot, _ = ready
    draft = service.draft("purchase", snapshot.id)
    invalid = deepcopy(workflow_spec)
    invalid["nodes"][3]["parameters"]["body"]["data"] = {"supplier": "Paper Ltd", "total": "87.50"}
    report = service.submit_proposal(draft.id, invalid)
    assert not report.valid
    assert any("currency" in issue for issue in report.issues)
    assert business[1].get("/api/orders/records").json()["total"] == 0


def test_environment_drift_invalidates_validated_proposal(ready, business):
    service, _, proposal = ready
    response = business[2].post("/config", headers={"x-admin-token": "evaluation-only"}, json={
        "domain": "orders", "required_field": {"name": "org_unit", "label": "Unit", "type": "string"},
    })
    assert response.status_code == 200, response.text
    with pytest.raises(ValueError, match="environment"):
        start(service, proposal)
    assert business[1].get("/api/orders/records").json()["total"] == 0


def test_human_node_consumes_validated_input(ready, workflow_spec):
    service, snapshot, _ = ready
    draft = service.draft("purchase", snapshot.id)
    spec = deepcopy(workflow_spec)
    spec["nodes"][1]["condition"]["one_of"] = ["USD"]
    proposal = service.submit_proposal(draft.id, spec)
    run = start(service, proposal)
    pending = service.advance(run.id)
    assert pending.state == "needs_input"
    with pytest.raises(ValueError):
        service.control(run.id, "provide_input", {"confirmation": False})
    assert service.control(run.id, "provide_input", {"confirmation": True}).outputs["ask"] == {"confirmation": True}
    assert service.advance(run.id).state == "waiting"


def test_invalid_resolved_input_is_rejected_before_run_start(ready, business):
    service, _, proposal = ready
    with pytest.raises(ValueError, match="supplier"):
        service.start(proposal.id, "po-invalid", {"supplier": "", "amount": "87.50"})
    assert business[1].get("/api/orders/records").json()["total"] == 0


def test_work_spec_can_pin_required_verification(configured, workflow_spec):
    from dataagent_operations.service import OperationsService
    db, config = configured
    config["work_specs"][0]["constraints"] = {"workflow_verification": [{
        "operation_id": "orders_query_status", "condition": {
            "pointer": "/response/status", "one_of": ["approved"],
        }, "criteria": [0],
    }]}
    service = OperationsService(db, config)
    draft = service.draft("purchase", service.discover("test-orders").id)
    modified = deepcopy(workflow_spec)
    modified["nodes"][-1]["condition"]["one_of"] = ["draft"]
    assert not service.submit_proposal(draft.id, modified).valid
    assert service.submit_proposal(draft.id, workflow_spec).valid


def test_rejected_approval_fails_business_verification(ready, business):
    service, _, proposal = ready
    run = start(service, proposal)
    waiting = service.advance(run.id)
    assert waiting.state == "waiting"
    record = waiting.outputs["observe"]
    response = business[2].post("/approval", headers={"x-admin-token": "evaluation-only"}, json={
        "domain": "orders", "record_id": record["id"], "outcome": "rejected",
    })
    assert response.status_code == 200
    failed = service.advance(run.id)
    assert failed.state == "failed"
    assert failed.outputs["verify"]["native_status"] == "REJECTED"


def test_cancel_records_wait_cancellation(ready):
    service, _, proposal = ready
    run = start(service, proposal)
    waiting = service.advance(run.id)
    assert waiting.state == "waiting"
    paused = service.control(run.id, "pause")
    assert paused.wait_ref == waiting.wait_ref
    assert service.advance(run.id).state == "paused"
    assert service.control(run.id, "resume").state == "active"
    cancelled = service.control(run.id, "cancel")
    assert cancelled.state == "cancelled"
    assert cancelled.wait_ref is None
    assert service.waits(run.id)[0].state == "cancelled"


def test_workbench_goal_is_pinned_and_wrong_grant_is_refused(configured, workflow_spec, tmp_path):
    from dataagent_operations.service import OperationsService
    from dataagent_runtime.adapters.workbench_sqlite import SqliteWorkbenchStore
    from dataagent_runtime.ports.workbench_store import ChangeSet, Write

    db, config = configured
    source = SqliteWorkbenchStore(tmp_path / "workbench.sqlite3")
    goal = config["work_specs"].pop()
    source.commit(ChangeSet(writes=[Write("goal", "stored-goal", "finance", goal)]))
    service = OperationsService(db, config, workbench_store=source)
    snapshot = service.discover("test-orders")
    draft = service.draft("stored-goal@1", snapshot.id)
    assert draft.work_spec.id == "stored-goal"
    assert draft.work_spec.goal == goal["goal"]
    proposal = service.submit_proposal(draft.id, workflow_spec)
    assert proposal.valid
    changed = {**goal, "revision": "2", "goal": "New goal", "authorization_ref": "different-grant"}
    source.commit(ChangeSet(writes=[Write("goal", "stored-goal", "finance", changed, expected_revision="1")]))
    with pytest.raises(ValueError, match="WorkSpec"):
        start(service, proposal)


def test_mismatched_lookup_collection_blocks_proposal(configured, workflow_spec, business):
    from dataagent_operations.service import OperationsService
    db, config = configured
    operations = config["environments"]["test-orders"]["operations"]
    operations["orders_create_draft"]["effect"]["collection_pointer"] = "/unknown_collection"
    service = OperationsService(db, config)
    snapshot = service.discover("test-orders")
    assert snapshot.capabilities["orders_query_records"].verification == "observed"
    draft = service.draft("purchase", snapshot.id)
    report = service.submit_proposal(draft.id, workflow_spec)
    assert not report.valid
    assert any("/unknown_collection" in issue for issue in report.issues)
    assert business[1].get("/api/orders/records").json()["total"] == 0
