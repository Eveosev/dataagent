import asyncio
from copy import deepcopy
import json
import socket
import threading
import time

from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import pytest
import uvicorn

from dataagent_scenarios.business_system import DEFAULT_CONFIG, create_admin_app, create_app


class EvaluationClient:
    def __init__(self, app):
        self.app = app

    def post(self, path, **options):
        async def request():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://evaluation-only") as client:
                return await client.post(path, **options)
        return asyncio.run(request())


@pytest.fixture
def dispatch_fault():
    return {"reject_once": False, "proof": False}


@pytest.fixture
def business(tmp_path, dispatch_fault):
    config = deepcopy(DEFAULT_CONFIG)
    config["domains"]["orders"]["collection_field"] = "records"
    config["domains"]["orders"]["pagination"] = "cursor"
    db = tmp_path / "business.sqlite3"
    app = create_app(db, config)
    manager = EvaluationClient(create_admin_app(db, token="evaluation-only"))

    @app.get('/ui/observer-probe', include_in_schema=False)
    def browser_probe():
        return HTMLResponse('<img src="/unapproved-effect">'
                            '<table><tbody><tr><td>po-work</td>'
                            '<td><span hidden>waiting_approval</span></td></tr></tbody></table>')

    @app.get('/unapproved-effect', include_in_schema=False)
    def unapproved_effect():
        dispatch_fault['unapproved_read'] = True
        return JSONResponse({})

    @app.middleware("http")
    async def interrupt_before_write(request, call_next):
        if (dispatch_fault.get("lookup_unavailable") and request.method == "GET"
                and request.url.path == "/api/orders/records" and "business_key" in request.query_params):
            return JSONResponse({"detail": "local lookup unavailable"}, status_code=503)
        if request.url.path.endswith("/submit") and dispatch_fault["reject_once"]:
            dispatch_fault["reject_once"] = False
            dispatch_fault["known_not_applied"] = True
            return JSONResponse({"detail": "Local fault before dispatch"}, status_code=503)
        reply = await call_next(request)
        if (
            dispatch_fault["proof"] and dispatch_fault.get("known_not_applied")
            and request.url.path == "/api/orders/records" and request.method == "GET"
        ):
            payload = json.loads(b"".join([chunk async for chunk in reply.body_iterator]))
            for record in payload["records"]:
                record["dispatch_proof"] = "definitively_not_applied"
            return JSONResponse(payload, status_code=reply.status_code)
        return reply
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", ws="none"))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    try:
        url = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=url, trust_env=False) as public:
            yield url, public, manager
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()


@pytest.fixture
def configured(business, tmp_path):
    url, _, _ = business
    root = "/api/orders/records"
    query = "orders_query_records"
    key_lookup = {"lookup_operation": query, "collection_pointer": "/records"}
    return tmp_path / "operations.sqlite3", {
        "scope_ref": "finance",
        "authorization_ref": "local-grant",
        "work_specs": [{
            "id": "purchase", "revision": "1", "goal": "Submit and track this purchase order",
            "acceptance_criteria": ["An actual purchase order is approved"],
            "authorization_ref": "local-grant",
        }],
        "environments": {
            "test-orders": {
                "base_url": url, "tenant": "finance", "business_key_prefix": "po-",
                "operations": {
                    query: {"method": "GET", "path": root, "business_key_parameter": "business_key"},
                    "orders_create_draft": {
                        "method": "POST", "path": root, "effect": {
                            **key_lookup, "action": "create-order",
                            "business_key_field": "business_key",
                            "applied": {"pointer": "/status", "one_of": ["draft", "waiting_approval", "approved", "rejected"]},
                            "match_fields": {"/data": "/data"},
                        },
                    },
                    "orders_submit_record": {
                        "method": "POST", "path": root + "/{record_id}/submit", "effect": {
                            **key_lookup, "action": "submit-order",
                            "record_id_parameter": "record_id", "request_key_field": "request_key",
                            "remote_idempotency": True,
                            "before": {"pointer": "/status", "one_of": ["draft"]},
                            "applied": {"pointer": "/status", "one_of": ["waiting_approval", "approved", "rejected"]},
                        },
                    },
                    "orders_query_status": {
                        "method": "GET", "path": root + "/{record_id}/status",
                        "record_lookup": query, "collection_pointer": "/records", "record_id_parameter": "record_id",
                    },
                },
            },
        },
    }


@pytest.fixture
def workflow_spec():
    return {
        "entry": "prepare",
        "input_schema": {
            "type": "object", "required": ["supplier", "amount"], "additionalProperties": False,
            "properties": {"supplier": {"type": "string"}, "amount": {"type": "string"}},
        },
        "nodes": [
            {"id": "prepare", "kind": "transform", "assign": {"data": {
                "supplier": {"$ref": "/inputs/supplier"}, "total": {"$ref": "/inputs/amount"}, "currency": "CNY",
            }}, "next": "decide"},
            {"id": "decide", "kind": "decide", "condition": {
                "pointer": "/steps/prepare/data/currency", "one_of": ["CNY"],
            }, "next": "create", "otherwise": "ask"},
            {"id": "ask", "kind": "human", "prompt": "Confirm purchasing currency", "input_schema": {
                "type": "object", "required": ["confirmation"], "properties": {"confirmation": {"const": True}},
            }, "next": "create"},
            {"id": "create", "kind": "act", "operation_id": "orders_create_draft", "parameters": {
                "body": {"data": {"$ref": "/steps/prepare/data"}},
            }, "next": "submit"},
            {"id": "submit", "kind": "act", "operation_id": "orders_submit_record", "next": "observe"},
            {"id": "observe", "kind": "observe", "operation_id": "orders_query_status", "next": "approval"},
            {"id": "approval", "kind": "wait", "operation_id": "orders_query_status", "condition": {
                "pointer": "/response/status", "one_of": ["approved", "rejected"],
            }, "next": "verify"},
            {"id": "verify", "kind": "verify", "operation_id": "orders_query_status", "condition": {
                "pointer": "/response/status", "one_of": ["approved"],
            }, "criteria": [0]},
        ],
    }


@pytest.fixture
def ready(configured, workflow_spec):
    from dataagent_operations.service import OperationsService
    db, config = configured
    service = OperationsService(db, config, request_timeout=0.2)
    snapshot = service.discover("test-orders")
    draft = service.draft("purchase", snapshot.id)
    proposal = service.submit_proposal(draft.id, workflow_spec)
    assert proposal.valid, proposal.issues
    return service, snapshot, proposal


def start(service, proposal, business_key="po-work"):
    return service.start(proposal.id, business_key, {"supplier": "Paper Ltd", "amount": "87.50"})


def approve(business, key="po-work"):
    _, public, manager = business
    record = public.get("/api/orders/records", params={"business_key": key}).json()["records"][0]
    assert record["status"] == "waiting_approval"
    result = manager.post("/approval", headers={"x-admin-token": "evaluation-only"}, json={
        "domain": "orders", "record_id": record["id"], "outcome": "approved",
    })
    assert result.status_code == 200, result.text
    return record
