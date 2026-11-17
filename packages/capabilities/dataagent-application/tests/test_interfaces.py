"""Black-box MCP and CLI entrypoints over a real subprocess (07 §11.3)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

PYTHON = os.environ.get("APP_TEST_PYTHON", sys.executable)


def _mcp(messages: list[dict], env_extra: dict | None = None) -> list[dict | None]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env_extra:
        env.update(env_extra)
    process = subprocess.run(
        [PYTHON, "-m", "dataagent_application.interfaces.mcp_server"],
        input="\n".join(json.dumps(m) for m in messages) + "\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert process.returncode == 0, process.stderr
    return [json.loads(line) for line in process.stdout.splitlines() if line.strip()]


def test_mcp_initialize_and_tools_list(tmp_path):
    responses = _mcp(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ],
        {"DATAAGENT_DATA_ROOT": str(tmp_path / "data"), "DATAAGENT_WORKSPACE": str(tmp_path)},
    )
    info = responses[0]["result"]["serverInfo"]
    assert info["name"] == "dataagent-application"
    tools = responses[1]["result"]["tools"]
    assert len(tools) == 13
    names = {t["name"] for t in tools}
    assert "evaluate_scalar_expression" in names and "export_report_format" in names


def test_mcp_tools_call_needs_input_and_ok(tmp_path):
    record = {
        "asset": {
            "id": "rec:1",
            "kind": "record",
            "scope_ref": "scope-1",
            "revision": "r1",
            "resolver": "content",
            "locator": "sha256:" + "0" * 64,
        },
        "document_ref": "doc:1@r1",
        "target_schema_ref": "schema:x@r1",
        "fields": [
            {"field_id": "amount", "status": "missing", "value_type": "number"}
        ],
    }
    spec = {
        "spec_id": "s1",
        "revision": "r1",
        "backend_kind": "expression",
        "expression_or_call": {
            "op": "le",
            "args": [{"op": "field", "field_id": "amount"}, {"op": "literal", "value": 5000}],
        },
    }
    call = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "evaluate_scalar_expression",
            "arguments": {
                "spec": spec,
                "record": record,
                "context": {"request_id": "r1", "scope_ref": "s", "authorization_ref": "a"},
            },
        },
    }
    planning_call = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "generate_function_expressions",
            "arguments": {
                "rule": {
                    "statement": "金额不超过 5000",
                    "conditions": [
                        {"condition_id": "c1", "text": "金额不超过 5000", "referenced_fields": ["amount"]}
                    ],
                    "combination": "c1",
                },
                "fields": [{"field_id": "amount", "name": "金额", "path": "amount", "value_type": "number"}],
                "context": {"request_id": "r2", "scope_ref": "s", "authorization_ref": "a"},
            },
        },
    }
    responses = _mcp(
        [call, planning_call],
        {"DATAAGENT_DATA_ROOT": str(tmp_path / "data"), "DATAAGENT_WORKSPACE": str(tmp_path)},
    )
    body = json.loads(responses[0]["result"]["content"][0]["text"])
    assert body["status"] == "ok"
    assert body["data"]["assessment"]["verdict"] == "unknown"
    needs = json.loads(responses[1]["result"]["content"][0]["text"])
    assert needs["status"] == "needs_input"
    assert needs["issues"][0]["inference_request"]["kind"] == "expression_ast"


def test_mcp_missing_context_falls_back_to_local_owner(tmp_path):
    # R1 (T11a): ``context`` is optional. With no caller hint and no host
    # authority, resolve_context supplies the local-owner subject and a
    # workspace-scoped local authorization; the operation itself reads no
    # governed resource, so the call is a normal business result rather
    # than the old "context is required" transport error.
    call = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "acquire_and_align_engine",
            "arguments": {"engine_id": "duckdb"},
        },
    }
    responses = _mcp(
        [call],
        {"DATAAGENT_DATA_ROOT": str(tmp_path / "data"), "DATAAGENT_WORKSPACE": str(tmp_path)},
    )
    assert responses[0]["result"]["isError"] is False
    body = json.loads(responses[0]["result"]["content"][0]["text"])
    assert body["status"] == "ok"
    assert body["data"]["binding"]["engine_id"] == "duckdb"


def test_cli_list_and_call(tmp_path):
    env = dict(os.environ)
    env["DATAAGENT_DATA_ROOT"] = str(tmp_path / "data")
    env["DATAAGENT_WORKSPACE"] = str(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    listing = subprocess.run(
        [PYTHON, "-m", "dataagent_application.interfaces.cli", "--list"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert listing.returncode == 0
    assert len(json.loads(listing.stdout)) == 13

    body = {
        "engine_id": "duckdb",
        "context": {"request_id": "r1", "scope_ref": "s", "authorization_ref": "a"},
    }
    called = subprocess.run(
        [PYTHON, "-m", "dataagent_application.interfaces.cli", "acquire_and_align_engine"],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert called.returncode == 0
    result = json.loads(called.stdout)
    assert result["status"] == "ok"
    assert result["data"]["binding"]["engine_id"] == "duckdb"


def test_cli_failed_operation_exits_nonzero(tmp_path):
    env = dict(os.environ)
    env["DATAAGENT_DATA_ROOT"] = str(tmp_path / "data")
    env["DATAAGENT_WORKSPACE"] = str(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    body = {
        "engine_id": "duckdb",
        "expected_version": "0.0.0-nope",
        "context": {"request_id": "r1", "scope_ref": "s", "authorization_ref": "a"},
    }
    called = subprocess.run(
        [PYTHON, "-m", "dataagent_application.interfaces.cli", "acquire_and_align_engine"],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert called.returncode == 1
    result = json.loads(called.stdout)
    assert result["status"] == "failed"
    assert result["issues"][0]["code"] == "da07.engine_version_mismatch"


def _cli(args, env_extra):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(env_extra)
    return subprocess.run(
        [PYTHON, "-m", "dataagent_application.interfaces.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def test_cli_unified_list(tmp_path):
    result = _cli(["list"], {"DATAAGENT_DATA_ROOT": str(tmp_path / "data"), "DATAAGENT_WORKSPACE": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 13
    first = lines[0].split("\t")
    assert first[1] == "DA06.1.1"
    assert first[2] == "recheck=no"
    assert first[3] == "two_phase=yes"


def test_cli_unified_run_two_phase(tmp_path):
    env = {"DATAAGENT_DATA_ROOT": str(tmp_path / "data"), "DATAAGENT_WORKSPACE": str(tmp_path)}
    result = _cli(["run", "parse_time_and_filters", "--set", "statement=last 30 days"], env)
    assert result.returncode == 0, result.stderr
    import json as _json

    summary = _json.loads(result.stdout)
    assert summary["status"] in {"ok", "needs_input", "partial"}
    assert summary["result_path"]
    from pathlib import Path

    assert Path(summary["result_path"]).exists()
    if summary["status"] == "needs_input":
        assert summary["next_command"].startswith("dataagent app run parse_time_and_filters")
