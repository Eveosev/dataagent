from __future__ import annotations

import contextlib
import io
import json
import sys

from pydantic import BaseModel

from dataagent_contracts.core import CapabilityResult, CapabilityStatus
from dataagent_runtime import get_spec, list_operations, operation, reset_registry
from dataagent_runtime.interfaces import cli, mcp_server


class PingInput(BaseModel):
    value: int


class PingOutput(BaseModel):
    value: int


def _register():
    reset_registry()

    @operation("TEST.2.1", input_model=PingInput, output_model=PingOutput, description="ping")
    def ping(input_obj, ctx, runtime):  # noqa: ANN001
        return PingOutput(value=input_obj.value + 1)


def _invoke(operation, payload, context):
    spec = get_spec(operation)
    data = spec.handler(PingInput.model_validate(payload), None, None)
    return CapabilityResult[dict](status=CapabilityStatus.ok, data=data.model_dump())


def test_mcp_tools_list_and_call():
    _register()
    response = mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        server_name="runtime-test",
        server_version="0.1.0",
        list_operations=list_operations,
        invoke=_invoke,
    )
    tools = response["result"]["tools"]
    assert [t["name"] for t in tools] == ["ping"]
    assert "context" in tools[0]["inputSchema"]["required"]

    call = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "ping",
            "arguments": {
                "value": 41,
                "context": {
                    "request_id": "r",
                    "scope_ref": "s",
                    "authorization_ref": "a",
                },
            },
        },
    }
    response = mcp_server.handle(
        call,
        server_name="runtime-test",
        server_version="0.1.0",
        list_operations=list_operations,
        invoke=_invoke,
    )
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["status"] == "ok"
    assert body["data"]["value"] == 42
    assert not response["result"]["isError"]


def test_mcp_missing_context_is_error():
    call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "ping", "arguments": {"value": 1}},
    }
    response = mcp_server.handle(
        call,
        server_name="t",
        server_version="0",
        list_operations=list_operations,
        invoke=_invoke,
    )
    assert response["result"]["isError"]
    assert "CallContext is required" in response["result"]["content"][0]["text"]


def test_cli_end_to_end():
    _register()
    body = json.dumps(
        {
            "input": {"value": 1},
            "context": {"request_id": "r", "scope_ref": "s", "authorization_ref": "a"},
        }
    )
    stdin = sys.stdin
    sys.stdin = io.StringIO(body)
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["ping"], list_operations=list_operations, invoke=_invoke)
    finally:
        sys.stdin = stdin
    assert code == 0
    assert json.loads(out.getvalue())["data"]["value"] == 2


def test_cli_list(capsys):
    _register()
    code = cli.main(
        ["--list"], list_operations=list_operations, invoke=_invoke
    )
    assert code == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed[0]["operation"] == "ping"
