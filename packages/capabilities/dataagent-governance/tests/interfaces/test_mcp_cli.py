"""Black-box MCP/CLI entry tests (08 §10.1)."""

from __future__ import annotations

import io
import json
import contextlib
import sys
from pathlib import Path

from dataagent_runtime.interfaces import mcp_server

from dataagent_governance import __version__
from dataagent_governance.registry import load_operations, validate_registry
from dataagent_governance.runtime import GovernanceRuntime


def _list_operations():
    load_operations()
    from dataagent_runtime.registry import list_operations

    return list_operations()


def _invoke(operation, payload, context):
    from dataagent_runtime.invoke import invoke

    return invoke(operation, payload, context, runtime=_RUNTIME)


_RUNTIME: GovernanceRuntime | None = None


def _runtime(rt):  # noqa: ANN001
    global _RUNTIME
    _RUNTIME = rt


def _handle(message, rt):
    _runtime(rt)
    return mcp_server.handle(
        message,
        server_name="dataagent-governance",
        server_version=__version__,
        list_operations=_list_operations,
        invoke=_invoke,
    )


def test_tools_list_exposes_exactly_the_six_s0_operations(rt):
    response = _handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, rt)
    tools = response["result"]["tools"]
    assert sorted(t["name"] for t in tools) == [
        "check_access_scope",
        "check_model_context_egress",
        "check_result_grain_and_merge",
        "draft_acceptance_criteria",
        "evaluate_business_acceptance",
        "isolate_acceptance_samples",
    ]
    assert all("context" in t["inputSchema"]["required"] for t in tools)


def test_tools_call_roundtrip(rt):
    response = _handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "check_access_scope",
                "arguments": {
                    "resource_ref": "table:orders@r1",
                    "context": {
                        "request_id": "req:1",
                        "scope_ref": "tenant:demo",
                        "authorization_ref": "seed",
                        "subject_ref": "user:alice",
                        "purpose": "monthly_report",
                    },
                },
            },
        },
        rt,
    )
    assert not response["result"]["isError"]
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["status"] == "ok"
    assert body["data"]["decision"]["decision"] == "allow"


def test_tools_call_business_deny_is_not_transport_error(rt):
    response = _handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "check_access_scope",
                "arguments": {
                    "resource_ref": "doc:unknown@r1",
                    "context": {
                        "request_id": "req:1",
                        "scope_ref": "tenant:demo",
                        "authorization_ref": "seed",
                        "subject_ref": "user:alice",
                        "purpose": "monthly_report",
                    },
                },
            },
        },
        rt,
    )
    assert not response["result"]["isError"]  # indeterminate is a business conclusion
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["data"]["decision"]["decision"] == "indeterminate"


def test_cli_confirm_criteria_management_entry(rt, monkeypatch, capsys, tmp_path):
    from dataagent_governance.interfaces import cli

    monkeypatch.setenv("DATAAGENT_CONFIRMERS", "user:boss")
    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    from dataagent_runtime.invoke import invoke

    drafted = invoke(
        "draft_acceptance_criteria",
        {
            "delivery_target": "t",
            "proposal": {
                "owner_ref": "user:alice",
                "family": "judgment",
                "expected_outputs": "x",
                "evidence_requirements": ["rule:a"],
                "unknown_policy": "count_as_fail",
                "thresholds": {"pass_rate": 0.9},
            },
        },
        {
            "request_id": "r",
            "scope_ref": "s",
            "authorization_ref": "seed",
            "subject_ref": "user:alice",
            "purpose": "monthly_report",
        },
        runtime=rt,
    )
    ref = drafted.data.criteria
    payload = rt.versions.get("criteria", ref.id, ref.revision)
    from dataagent_governance.evaluation.criteria_samples import _digest

    body = {
        "criteria_id": ref.id,
        "criteria_revision": ref.revision,
        "confirmation": {
            "confirmation_id": "conf:cli-1",
            "criteria_id": ref.id,
            "criteria_revision": ref.revision,
            "criteria_digest": _digest(payload),
            "confirmer_ref": "user:boss",
            "confirmed_at": "2026-11-04T12:00:00Z",
            "authority_ref": "tenant:owner",
        },
    }
    stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(body))
    try:
        code = cli.main(["confirm-criteria"])
    finally:
        sys.stdin = stdin
    assert code == 0
    activated = json.loads(capsys.readouterr().out)
    assert activated["status"] == "active"
    assert activated["confirmation_ref"] == "conf:cli-1"


def test_cli_confirm_criteria_rejects_unauthorized_confirmer(rt, monkeypatch, capsys):
    from dataagent_governance.interfaces import cli

    monkeypatch.setenv("DATAAGENT_CONFIRMERS", "user:boss")
    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    body = {
        "criteria_id": "criteria:none",
        "criteria_revision": "r1",
        "confirmation": {
            "confirmation_id": "conf:x",
            "criteria_id": "criteria:none",
            "criteria_revision": "r1",
            "criteria_digest": "sha256:" + "0" * 64,
            "confirmer_ref": "user:mallory",
            "confirmed_at": "2026-11-04T12:00:00Z",
            "authority_ref": "tenant:owner",
        },
    }
    stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(body))
    try:
        code = cli.main(["confirm-criteria"])
    finally:
        sys.stdin = stdin
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "failed"


def test_cli_list(rt, monkeypatch, capsys):
    from dataagent_governance.interfaces import cli

    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    code = cli.main(["--list"])
    assert code == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed) == 6


def test_cli_unified_list_one_line_per_operation(rt, monkeypatch, capsys):
    from dataagent_governance.interfaces import cli

    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    code = cli.main(["list"])
    assert code == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 6
    assert lines[0] == "check_result_grain_and_merge\tDA11.2.3\trecheck=yes\ttwo_phase=no"
    assert any(
        line == "draft_acceptance_criteria\tDA11.5.1\trecheck=no\ttwo_phase=yes"
        for line in lines
    )


def test_cli_unified_run_check_access_scope(rt, monkeypatch, capsys, tmp_path):
    from dataagent_governance.interfaces import cli

    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    code = cli.main(
        ["run", "check_access_scope", "--set-json", 'resource_ref={"id":"table:orders","revision":"r1"}']
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "ok"
    assert Path(summary["result_path"]).exists()


def test_cli_policy_apply(rt, monkeypatch, capsys, tmp_path):
    from dataagent_governance.interfaces import cli

    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(
        json.dumps(
            {
                "policy_id": "tenant:default",
                "revision": "r1",
                "rules": [
                    {
                        "rule_id": "allow-all",
                        "effect": "allow",
                        "subjects": ["*"],
                        "resources": ["*"],
                        "actions": ["read"],
                        "purposes": ["*"],
                    }
                ],
                "egress_rules": [],
            }
        ),
        encoding="utf-8",
    )
    code = cli.main(["policy", "apply", str(policy_file)])
    assert code == 0
    handle = json.loads(capsys.readouterr().out)
    assert handle.startswith("tenant:default@")
    applied = rt.policy.load(None)
    assert applied.rules[0].rule_id == "allow-all"

    missing = tmp_path / "nope.json"
    assert cli.main(["policy", "apply", str(missing)]) == 2


def test_cli_confirm_accepts_file(rt, monkeypatch, capsys, tmp_path):
    from dataagent_governance.interfaces import cli

    monkeypatch.setenv("DATAAGENT_CONFIRMERS", "user:boss")
    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    from dataagent_runtime.invoke import invoke

    drafted = invoke(
        "draft_acceptance_criteria",
        {
            "delivery_target": "t",
            "proposal": {
                "owner_ref": "user:alice",
                "family": "judgment",
                "expected_outputs": "x",
                "evidence_requirements": ["rule:a"],
                "unknown_policy": "count_as_fail",
                "thresholds": {"pass_rate": 0.9},
            },
        },
        {
            "request_id": "r",
            "scope_ref": "s",
            "authorization_ref": "seed",
            "subject_ref": "user:alice",
            "purpose": "monthly_report",
        },
        runtime=rt,
    )
    ref = drafted.data.criteria
    payload = rt.versions.get("criteria", ref.id, ref.revision)
    from dataagent_governance.evaluation.criteria_samples import _digest

    body = {
        "criteria_id": ref.id,
        "criteria_revision": ref.revision,
        "confirmation": {
            "confirmation_id": "conf:file-1",
            "criteria_id": ref.id,
            "criteria_revision": ref.revision,
            "criteria_digest": _digest(payload),
            "confirmer_ref": "user:boss",
            "confirmed_at": "2026-11-04T12:00:00Z",
            "authority_ref": "tenant:owner",
        },
    }
    confirm_file = tmp_path / "confirm.json"
    confirm_file.write_text(json.dumps(body), encoding="utf-8")
    code = cli.main(["confirm", str(confirm_file)])
    assert code == 0
    activated = json.loads(capsys.readouterr().out)
    assert activated["status"] == "active"
    assert activated["confirmation_ref"] == "conf:file-1"
    assert cli.main(["confirm", str(tmp_path / "nope.json")]) == 2


def test_cli_confirm_invalid_confirmation_is_usage_error(rt, monkeypatch, capsys, tmp_path):
    """r2-review D9: an invalid confirmation payload is a schema error
    (exit 2 on stderr, no pydantic traceback), not an uncaught exception."""

    from dataagent_governance.interfaces import cli

    monkeypatch.setenv("DATAAGENT_CONFIRMERS", "user:boss")
    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    bad = tmp_path / "bad-confirm.json"
    bad.write_text(
        json.dumps(
            {
                "criteria_id": "criteria:x",
                "criteria_revision": "r1",
                # missing criteria_digest / authority_ref inside "confirmation"
                "confirmation": {
                    "confirmation_id": "conf:bad",
                    "criteria_id": "criteria:x",
                    "criteria_revision": "r1",
                    "confirmer_ref": "user:boss",
                    "confirmed_at": "2026-11-04T12:00:00Z",
                },
            }
        ),
        encoding="utf-8",
    )
    code = cli.main(["confirm", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert "invalid confirmation record" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


def test_cli_confirm_missing_criteria_id_is_usage_error(rt, monkeypatch, capsys, tmp_path):
    """Same class as D9: a body without ``criteria_id`` exits 2, not KeyError."""

    from dataagent_governance.interfaces import cli

    monkeypatch.setenv("DATAAGENT_CONFIRMERS", "user:boss")
    monkeypatch.setattr(
        "dataagent_governance.interfaces.cli.default_runtime", lambda: rt
    )
    bad = tmp_path / "no-id-confirm.json"
    bad.write_text(
        json.dumps(
            {
                # no top-level criteria_id; the inner confirmation is valid
                "criteria_revision": "r1",
                "confirmation": {
                    "confirmation_id": "conf:bad",
                    "criteria_id": "criteria:x",
                    "criteria_revision": "r1",
                    "criteria_digest": "sha256:" + "0" * 64,
                    "confirmer_ref": "user:boss",
                    "confirmed_at": "2026-11-04T12:00:00Z",
                    "authority_ref": "tenant:owner",
                },
            }
        ),
        encoding="utf-8",
    )
    code = cli.main(["confirm", str(bad)])
    captured = capsys.readouterr()
    assert code == 2
    assert "missing required field" in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""
