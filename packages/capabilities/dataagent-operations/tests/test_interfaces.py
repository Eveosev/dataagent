import json
import os
import subprocess
import sys


def test_mcp_stdio_discovers_only_through_trusted_authorization(configured, tmp_path):
    db, config = configured
    configuration = tmp_path / "config.json"
    configuration.write_text(json.dumps(config))
    environment = os.environ | {
        "DATAAGENT_OPERATIONS_CONFIG": str(configuration),
        "DATAAGENT_OPERATIONS_DB": str(db),
    }
    context = {"request_id": "discovery", "scope_ref": "finance", "authorization_ref": "local-grant"}
    messages = [
        {"id": 1, "method": "tools/list"},
        {"id": 2, "method": "tools/call", "params": {
            "name": "environment_discover", "arguments": {"environment_id": "test-orders", "context": context},
        }},
        {"id": 3, "method": "tools/call", "params": {
            "name": "environment_discover", "arguments": {"environment_id": "test-orders", "context": context},
            "_meta": {"context": context | {"authorization_ref": "other-grant"}},
        }},
    ]
    result = subprocess.run(
        [sys.executable, "-m", "dataagent_operations", "mcp"], env=environment, text=True,
        input="".join(json.dumps({"jsonrpc": "2.0", **message}) + "\n" for message in messages),
        capture_output=True, check=True, timeout=15,
    )
    tools, discovery, denied = [json.loads(line)["result"] for line in result.stdout.splitlines()]
    names = {tool["name"] for tool in tools["tools"]}
    assert {"workflow_start", "workflow_advance", "workflow_actions", "workflow_waits"} <= names
    assert "revoke" not in names
    observed = json.loads(discovery["content"][0]["text"])
    assert observed["status"] == "ok"
    assert observed["data"]["scope_ref"] == "finance"
    assert json.loads(denied["content"][0]["text"])["issues"][0]["code"] == "unauthorized"

    cli = subprocess.run(
        [sys.executable, "-m", "dataagent_operations", "call", "environment_discover"], env=environment,
        input=json.dumps({"environment_id": "test-orders"}), text=True, capture_output=True, check=True, timeout=15,
    )
    assert json.loads(cli.stdout)["data"]["capabilities"]["orders_query_records"]["verification"] == "observed"
