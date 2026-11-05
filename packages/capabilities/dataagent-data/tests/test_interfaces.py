from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env_for(workspace: Path, tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DATAAGENT_WORKSPACE"] = str(workspace)
    env["DATAAGENT_DATA_ROOT"] = str(tmp_path / "data")
    env["PYTHONPATH"] = str(ROOT / "src")
    return env


def file_ref(workspace: Path, name: str) -> dict:
    payload = (workspace / name).read_bytes()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return {
        "id": "file:test",
        "kind": "file",
        "scope_ref": "tenant:test",
        "revision": digest,
        "resolver": "workspace",
        "locator": name,
        "digest": digest,
        "content_digest": digest,
        "media_type": "text/csv",
        "filename": name,
        "size_bytes": len(payload),
    }


CONTEXT = {
    "request_id": "req:1",
    "scope_ref": "tenant:test",
    "authorization_ref": "policy:test",
}


def run_cli(args, stdin, workspace, tmp_path):
    return subprocess.run(
        [sys.executable, "-m", "dataagent_data.interfaces.cli", *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=env_for(workspace, tmp_path),
        cwd=str(ROOT),
    )


def run_mcp(lines, workspace, tmp_path):
    return subprocess.run(
        [sys.executable, "-m", "dataagent_data.interfaces.mcp_server"],
        input="".join(line + "\n" for line in lines),
        capture_output=True,
        text=True,
        env=env_for(workspace, tmp_path),
        cwd=str(ROOT),
    )


def test_cli_success_and_failure(workspace, tmp_path):
    (workspace / "data.csv").write_text("a,b\n1,2\n")
    body = json.dumps({"input": {"file_ref": file_ref(workspace, "data.csv")}, "context": CONTEXT})
    result = run_cli(["parse_delimited_file"], body, workspace, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["execution_ref"]["capability_id"] == "DA01.4.3"

    # 12 §5.3: an unknown operation is a usage error (exit 2), not a failed call.
    failed = run_cli(["no_such_op"], json.dumps({"input": {}, "context": CONTEXT}), workspace, tmp_path)
    assert failed.returncode == 2
    assert "unknown command or operation" in failed.stderr


def test_cli_requires_context(workspace, tmp_path):
    result = run_cli(["parse_delimited_file"], "{}", workspace, tmp_path)
    assert result.returncode == 1
    assert json.loads(result.stdout)["issues"][0]["code"] == "invalid_input"


def test_cli_list_operations(workspace, tmp_path):
    result = run_cli(["--list"], "", workspace, tmp_path)
    assert result.returncode == 0
    assert len(json.loads(result.stdout)) == 32


def test_cli_rejects_path_traversal(workspace, tmp_path):
    (workspace / "data.csv").write_text("a\n1\n")
    ref = file_ref(workspace, "data.csv")
    ref["locator"] = "../secret.txt"
    result = run_cli(
        ["parse_delimited_file"],
        json.dumps({"input": {"file_ref": ref}, "context": CONTEXT}),
        workspace,
        tmp_path,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["issues"][0]["code"] == "invalid_input"


def mcp_payloads(workspace, tmp_path):
    (workspace / "data.csv").write_text("a,b\n1,2\n")
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    listed = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    called = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "parse_delimited_file",
            "arguments": {"file_ref": file_ref(workspace, "data.csv"), "context": CONTEXT},
        },
    }
    bad = {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "missing_op", "arguments": {"context": CONTEXT}}}
    return initialize, listed, called, bad


def test_mcp_initialize_list_and_call(workspace, tmp_path):
    initialize, listed, called, _ = mcp_payloads(workspace, tmp_path)
    result = run_mcp(
        [json.dumps(initialize), json.dumps(listed), json.dumps(called)],
        workspace,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses[0]["result"]["serverInfo"]["name"] == "dataagent-data"
    assert len(responses[1]["result"]["tools"]) == 32
    tool = next(t for t in responses[1]["result"]["tools"] if t["name"] == "parse_delimited_file")
    assert "context" in tool["inputSchema"]["properties"]
    assert "file_ref" in tool["inputSchema"]["properties"]
    call_result = responses[2]["result"]
    assert call_result["isError"] is False
    body = json.loads(call_result["content"][0]["text"])
    assert body["status"] == "ok"


def test_mcp_survives_bad_json_and_returns_is_error(workspace, tmp_path):
    initialize, listed, _, bad = mcp_payloads(workspace, tmp_path)
    result = run_mcp(
        [json.dumps(initialize), "{not json", json.dumps(bad), json.dumps(listed)],
        workspace,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses[1]["error"]["code"] == -32700
    assert responses[2]["result"]["isError"] is True
    assert len(responses[3]["result"]["tools"]) == 32


def test_mcp_requires_context(workspace, tmp_path):
    result = run_mcp(
        [
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "parse_delimited_file", "arguments": {}},
                }
            )
        ],
        workspace,
        tmp_path,
    )
    response = json.loads(result.stdout.splitlines()[0])
    assert response["result"]["isError"] is True
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["issues"][0]["code"] == "invalid_input"


def test_cli_accepts_flat_input_fields(workspace, tmp_path):
    (workspace / "data.csv").write_text("a\n1\n")
    body = json.dumps({"file_ref": file_ref(workspace, "data.csv"), "context": CONTEXT})
    result = run_cli(["parse_delimited_file"], body, workspace, tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "ok"


def test_mcp_reads_context_from_meta(workspace, tmp_path):
    (workspace / "data.csv").write_text("a\n1\n")
    message = {
        "jsonrpc": "2.0",
        "id": 9,
        "method": "tools/call",
        "params": {
            "name": "parse_delimited_file",
            "arguments": {"file_ref": file_ref(workspace, "data.csv")},
            "_meta": {"context": CONTEXT},
        },
    }
    result = run_mcp([json.dumps(message)], workspace, tmp_path)
    response = json.loads(result.stdout.splitlines()[0])
    assert response["result"]["isError"] is False
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["status"] == "ok"


def test_mcp_maps_bad_event_type_to_invalid_input(workspace, tmp_path):
    message = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "append_task_event",
            "arguments": {
                "task_ref": "task:x@r1",
                "event_id": "evt:bad",
                "event_type": "not_a_trace_event",
                "actor_ref": "agent:1",
                "payload": {},
                "context": CONTEXT,
            },
        },
    }
    result = run_mcp([json.dumps(message)], workspace, tmp_path)
    response = json.loads(result.stdout.splitlines()[0])
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["status"] == "failed"
    assert body["issues"][0]["code"] == "invalid_input"


def test_cli_rejects_inconsistent_catalog(workspace, tmp_path):
    snapshot = json.loads(
        (ROOT / "src" / "dataagent_data" / "catalog-snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    snapshot["atoms"] = snapshot["atoms"][:-1]
    bad = tmp_path / "bad-catalog.json"
    bad.write_text(json.dumps(snapshot), encoding="utf-8")
    env = env_for(workspace, tmp_path)
    env["DATAAGENT_CATALOG_SNAPSHOT"] = str(bad)
    result = subprocess.run(
        [sys.executable, "-m", "dataagent_data.interfaces.cli", "--list"],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    # 12 §5.3: missing environment (catalog snapshot) exits 3, not 1.
    assert result.returncode == 3
    assert "environment check failed" in result.stderr


def test_cli_unified_list(workspace, tmp_path):
    result = run_cli(["list"], "", workspace, tmp_path)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 32
    first = lines[0].split("\t")
    assert first[0] == "parse_regular_excel"
    assert first[1] == "DA01.4.1"
    assert first[2] == "recheck=yes"
    assert first[3] == "two_phase=no"


def test_cli_unified_run_with_file(workspace, tmp_path):
    (workspace / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    result = run_cli(["run", "parse_delimited_file", "--file", "data.csv"], "", workspace, tmp_path)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status"] == "ok"
    assert summary["handles"], summary
    assert Path(summary["result_path"]).exists()
    full = json.loads(Path(summary["result_path"]).read_text(encoding="utf-8"))
    assert full["status"] == "ok"


def test_cli_unified_ref_reuses_earlier_result(workspace, tmp_path):
    (workspace / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    result = run_cli(["run", "parse_delimited_file", "--file", "data.csv"], "", workspace, tmp_path)
    summary = json.loads(result.stdout)
    handle = next(h for h in summary["handles"] if h.startswith("table:"))
    result = run_cli(
        ["run", "profile_table_structure", "--ref", f"table_ref={handle}"],
        "",
        workspace,
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status"] == "ok"


def test_cli_unified_authorize_uses_latest_allow_decision(workspace, tmp_path):
    (workspace / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    env = env_for(workspace, tmp_path)
    from dataagent_contracts.core import AccessDecision, AccessOutcome
    from dataagent_runtime.adapters.sqlite import SqliteDatabase, SqliteDecisionStore

    store = SqliteDecisionStore(SqliteDatabase(Path(env["DATAAGENT_DATA_ROOT"]) / "db" / "decisions.sqlite3"))
    from datetime import datetime, timedelta, timezone

    payload = (workspace / "data.csv").read_bytes()
    file_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    store.save_access(
        AccessDecision(
            decision_id="ad:smoke",
            policy_ref={"id": "policy:default", "revision": "r1"},
            subject_ref="user:alice",
            resource_ref={"id": "file:" + file_digest[7:23], "revision": "*"},
            purpose="monthly_report",
            decision=AccessOutcome.allow,
            valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    env["DATAAGENT_HOST_SUBJECT_REF"] = "user:alice"
    env["DATAAGENT_HOST_PURPOSE"] = "monthly_report"
    result = subprocess.run(
        [sys.executable, "-m", "dataagent_data.interfaces.cli", "run", "parse_delimited_file",
         "--file", "data.csv", "--authorize"],
        input="",
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["status"] == "ok"
    codes = {issue["code"] for issue in summary["issues"]}
    assert "da12.access_denied" not in codes


def test_cli_unified_usage_errors(workspace, tmp_path):
    result = run_cli(["run", "parse_delimited_file"], "", workspace, tmp_path)
    assert result.returncode == 2
    result = run_cli(["run", "nope", "--set", "a=1"], "", workspace, tmp_path)
    assert result.returncode == 2
