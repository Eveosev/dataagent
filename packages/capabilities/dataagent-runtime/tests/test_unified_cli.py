"""Unified CLI kernel tests (12-unified-cli-build-plan W1/W4).

Covers: argv parsing per inputSchema, type coercion, handle resolution from
earlier results, the 32 KiB summary cap, exit codes 0/1/2/3, the needs_input
next-command suggestion and the egress scrub on the way out.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import BaseModel

from dataagent_contracts.core import (
    AccessDecision,
    FileRef,
    AccessOutcome,
    CapabilityResult,
    CapabilityStatus,
    Issue,
    Severity,
    VersionedRef,
)
from dataagent_runtime import get_spec, list_operations, operation, reset_registry
from dataagent_runtime.interfaces import unified
from dataagent_runtime.runtime import Runtime


class PingInput(BaseModel):
    value: int


class PingOutput(BaseModel):
    value: int


class HandleInput(BaseModel):
    table: dict


class HandleOutput(BaseModel):
    got: dict | None = None


class TwoPhaseInput(BaseModel):
    value: int
    proposal: dict | None = None


class TwoPhaseOutput(BaseModel):
    value: int


class ScalarsInput(BaseModel):
    """Fields whose inputSchema scalars are spelled via anyOf/$ref (D10)."""

    resource_ref: VersionedRef  # $ref -> $defs entry with type: string
    delimiter: str | None = None  # anyOf [string, null]
    budget_rows: int | None = None  # anyOf [integer, null]
    flag: bool | None = None  # anyOf [boolean, null]
    event_type: Literal["task_state", "note"] | None = None  # anyOf [$ref enum, null]
    note: Any = None  # anyOf [{}, null]
    sheets: list[str] | None = None  # anyOf [array, null] — not a scalar


CAPTURED: dict[str, object] = {}


def _register():
    reset_registry()

    @operation("TEST.1.1", input_model=PingInput, output_model=PingOutput, description="ping")
    def ping(input_obj, ctx, runtime):  # noqa: ANN001
        CAPTURED["context"] = ctx
        return PingOutput(value=input_obj.value + 1)

    @operation(
        "TEST.1.2",
        input_model=HandleInput,
        output_model=HandleOutput,
        description="handle",
        resource_fields=("table",),
    )
    def take_handle(input_obj, ctx, runtime):  # noqa: ANN001
        CAPTURED["payload"] = input_obj.model_dump()
        return HandleOutput(got=input_obj.table)

    @operation("TEST.1.3", input_model=TwoPhaseInput, output_model=TwoPhaseOutput, description="2p")
    def two_phase(input_obj, ctx, runtime):  # noqa: ANN001
        if input_obj.proposal is None:
            issue = Issue(
                code="da03.proposal_required",
                severity=Severity.warning,
                message="proposal required",
                retryable=False,
                suggested_action="fill the proposal",
                inference_request={
                    "kind": "metric",
                    "statement": "sum(amount)",
                    "fields": ["amount"],
                    "egress_decision_ref": None,
                },
            )
            return CapabilityResult(
                status=CapabilityStatus.needs_input, issues=[issue]
            )
        return CapabilityResult(status=CapabilityStatus.ok, data={"value": input_obj.value})

    @operation("TEST.1.4", input_model=PingInput, output_model=PingOutput, description="big")
    def big(input_obj, ctx, runtime):  # noqa: ANN001
        return PingOutput(value=input_obj.value)

    @operation(
        "TEST.1.6", input_model=ScalarsInput, output_model=PingOutput, description="scalars"
    )
    def scalars(input_obj, ctx, runtime):  # noqa: ANN001
        CAPTURED["scalars"] = input_obj.model_dump(mode="json")
        return PingOutput(value=1)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    _register()
    CAPTURED.clear()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("DATAAGENT_WORKSPACE", str(workspace))
    monkeypatch.setenv("DATAAGENT_DATA_ROOT", str(tmp_path / "root"))
    monkeypatch.delenv("DATAAGENT_HOST_SUBJECT_REF", raising=False)
    monkeypatch.delenv("DATAAGENT_HOST_PURPOSE", raising=False)
    monkeypatch.delenv("DATAAGENT_ENFORCEMENT_MODE", raising=False)
    Runtime._DEFAULT = None
    yield workspace
    Runtime._DEFAULT = None


def _hooks(**overrides):
    from dataagent_runtime.interfaces.unified import LayerHooks

    def invoke(op, payload, context):
        spec = get_spec(op)
        from dataagent_runtime.invoke import invoke as shared_invoke

        return shared_invoke(op, payload, context, runtime=Runtime.create())

    def runtime_factory():
        return Runtime.create()

    base = dict(
        layer="data",
        list_operations=list_operations,
        invoke=invoke,
        validate=lambda: None,
        runtime_factory=runtime_factory,
    )
    base.update(overrides)
    return LayerHooks(**base)


def _run_cli(argv, capsys, **overrides):
    code = unified.main(argv, hooks=_hooks(**overrides))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_list_one_line_per_operation(env, capsys):
    code, out, _ = _run_cli(["list"], capsys)
    assert code == 0
    lines = out.strip().splitlines()
    assert lines[0].startswith("ping\tTEST.1.1\trecheck=no\ttwo_phase=no")
    two_phase = [line for line in lines if line.startswith("two_phase\t")]
    assert two_phase and two_phase[0].endswith("two_phase=yes")
    recheck = [line for line in lines if line.startswith("take_handle\t")]
    assert recheck and recheck[0].split("\t")[2] == "recheck=yes"


def test_legacy_list_still_json(env, capsys):
    code, out, _ = _run_cli(["--list"], capsys)
    assert code == 0
    listed = json.loads(out)
    assert listed[0]["operation"] == "ping"


def test_op_help_flat_without_defs(env, capsys):
    code, out, _ = _run_cli(["two_phase", "--help"], capsys)
    assert code == 0
    assert "$defs" not in out
    assert "--set value=<integer>" in out
    assert "--ref <field>=<id@rev>" in out
    assert "DATAAGENT_HOST_SUBJECT_REF" in out


def test_run_with_set_type_coercion(env, capsys):
    code, out, _ = _run_cli(["run", "ping", "--set", "value=41"], capsys)
    assert code == 0
    summary = json.loads(out)
    assert summary["status"] == "ok"
    assert summary["data"]["value"] == 42
    assert summary["result_path"].endswith(".json")
    assert Path(summary["result_path"]).exists()
    assert Path(summary["result_path"]).parent.name == "results"


def test_run_set_boolean_and_unknown_field(env, capsys):
    code, _, err = _run_cli(["run", "ping", "--set", "value=true"], capsys)
    assert code == 2
    assert "not an integer" in err
    code, _, err = _run_cli(["run", "ping", "--set", "nope=1"], capsys)
    assert code == 2
    assert "not a field" in err


def test_run_set_json(env, capsys):
    code, out, _ = _run_cli(
        ["run", "take_handle", "--set-json", "table=" + json.dumps({"id": "table:t", "revision": "r1"})],
        capsys,
    )
    assert code == 0
    summary = json.loads(out)
    assert summary["data"]["got"] == {"id": "table:t", "revision": "r1"}
    assert "table:t@r1" in summary["handles"]


def test_run_set_resolves_anyof_and_ref_scalars(env, capsys):
    """r4-review D10: --set must type through anyOf/$ref, not just literal ``type``."""

    code, out, err = _run_cli(
        [
            "run",
            "scalars",
            "--set", "resource_ref=table:orders@r1",
            "--set", "delimiter=,",
            "--set", "budget_rows=10",
            "--set", "flag=yes",
            "--set", "event_type=note",
            "--set", "note=hello",
        ],
        capsys,
    )
    assert code == 0, err
    summary = json.loads(out)
    assert summary["status"] == "ok"
    payload = CAPTURED["scalars"]
    assert payload["resource_ref"] == "table:orders@r1"
    assert payload["delimiter"] == ","
    assert payload["budget_rows"] == 10
    assert payload["flag"] is True
    assert payload["event_type"] == "note"
    assert payload["note"] == "hello"


def test_run_set_ref_scalar_bad_value_is_usage_error(env, capsys):
    """A $ref string-form scalar still exits 2 on a value pydantic rejects."""

    code, _, err = _run_cli(
        ["run", "scalars", "--set", "resource_ref=missing-separator", "--set", "budget_rows=x"],
        capsys,
    )
    assert code == 2
    assert "not an integer" in err
    code, _, err = _run_cli(
        ["run", "scalars", "--set", "resource_ref=missing-separator"], capsys
    )
    assert code == 2
    assert "schema error" in err


def test_run_set_still_rejects_non_scalar_anyof(env, capsys):
    """anyOf [array, null] stays a non-scalar: use --set-json."""

    code, _, err = _run_cli(
        ["run", "scalars", "--set", "resource_ref=table:x@r1", "--set", "sheets=a,b"],
        capsys,
    )
    assert code == 2
    assert "field is not a scalar" in err


def test_op_help_resolves_scalar_kinds(env, capsys):
    """r4-review D10: anyOf/$ref scalars render as their scalar kind, not <object>."""

    code, out, _ = _run_cli(["scalars", "--help"], capsys)
    assert code == 0
    assert "--set resource_ref=<string>" in out
    assert "--set delimiter=<string>" in out
    assert "--set budget_rows=<integer>" in out
    assert "--set flag=<boolean>" in out
    assert "--set event_type=<string>" in out
    assert "--set sheets=<object>" in out
    assert "<VersionedRef>" not in out


def test_run_schema_error_is_usage(env, capsys):
    code, _, err = _run_cli(["run", "ping"], capsys)
    assert code == 2
    code, _, err = _run_cli(["run", "ping", "--set", "value=1", "--set", "value=2"], capsys)
    assert code == 0


def test_input_file_cannot_smuggle_context(env, capsys, tmp_path):
    body = tmp_path / "input.json"
    body.write_text(json.dumps({"value": 1, "context": {"subject_ref": "user:evil"}}))
    code, _, err = _run_cli(["run", "ping", "--input-file", str(body)], capsys)
    assert code == 2
    assert "context" in err


def test_failed_result_exit_1(env, capsys, monkeypatch):
    def invoke(op, payload, context):
        return CapabilityResult(
            status=CapabilityStatus.failed,
            issues=[Issue(code="invalid_input", severity=Severity.error, message="boom", retryable=False)],
        )

    code, out, _ = _run_cli(["run", "ping", "--set", "value=1"], capsys, invoke=invoke)
    assert code == 1
    summary = json.loads(out)
    assert summary["status"] == "failed"
    assert summary["issues"][0]["message"] == "boom"


def test_needs_input_emits_request_and_next_command(env, capsys):
    code, out, _ = _run_cli(["run", "two_phase", "--set", "value=5"], capsys)
    assert code == 0
    summary = json.loads(out)
    assert summary["status"] == "needs_input"
    assert summary["next_command"].startswith("dataagent data run two_phase")
    assert "--proposal-file" in summary["next_command"]
    request_path = Path(summary["result_path"]).with_suffix(".inference_request.json")
    assert request_path.exists()
    request = json.loads(request_path.read_text())
    assert request["statement"] == "sum(amount)"


def test_proposal_file_second_stage(env, capsys, tmp_path):
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps({"measure": "sum"}))
    code, out, _ = _run_cli(
        ["run", "two_phase", "--set", "value=5", "--proposal-file", str(proposal)], capsys
    )
    assert code == 0
    summary = json.loads(out)
    assert summary["data"]["value"] == 5


def test_ref_resolves_from_earlier_result(env, capsys):
    code, out, _ = _run_cli(
        ["run", "take_handle", "--set-json", "table=" + json.dumps({"id": "table:orders", "revision": "r2", "data_ref": "sha256:ab"})],
        capsys,
    )
    assert code == 0
    code, out, _ = _run_cli(["run", "take_handle", "--ref", "table=table:orders@r2"], capsys)
    assert code == 0
    summary = json.loads(out)
    assert summary["data"]["got"]["id"] == "table:orders"
    assert summary["data"]["got"]["data_ref"] == "sha256:ab"


def test_ref_unknown_handle_is_usage(env, capsys):
    code, _, err = _run_cli(["run", "take_handle", "--ref", "table=nope@r9"], capsys)
    assert code == 2
    assert "unknown" in err


def test_summary_truncated_over_32kib(env, capsys):
    def invoke(op, payload, context):
        return CapabilityResult(
            status=CapabilityStatus.ok, data={"blob": "x" * (40 * 1024)}
        )

    code, out, _ = _run_cli(["run", "ping", "--set", "value=1"], capsys, invoke=invoke)
    assert code == 0
    assert len(out.encode()) <= unified.SUMMARY_LIMIT
    summary = json.loads(out)
    assert summary["data"]["truncated"] is True


def test_detail_full_prints_whole_result(env, capsys):
    def invoke(op, payload, context):
        return CapabilityResult(status=CapabilityStatus.ok, data={"blob": "x" * (40 * 1024)})

    code, out, _ = _run_cli(
        ["run", "ping", "--set", "value=1", "--detail", "full"], capsys, invoke=invoke
    )
    assert code == 0
    assert len(out.encode()) > unified.SUMMARY_LIMIT
    assert json.loads(out)["data"]["blob"].startswith("xxx")


def test_egress_scrub_enforce_mode(env, capsys, monkeypatch):
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    Runtime._DEFAULT = None
    code, out, _ = _run_cli(["run", "two_phase", "--set", "value=5"], capsys)
    assert code == 0
    summary = json.loads(out)
    request = summary["issues"][0]["inference_request"]
    assert "statement" not in request
    assert "fields" not in request
    assert request["kind"] == "metric"


def test_egress_scrub_applies_to_detail_full(env, capsys, monkeypatch):
    """r1-review D7: ``--detail full`` is a stdout channel like the summary."""

    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    Runtime._DEFAULT = None
    code, out, _ = _run_cli(
        ["run", "two_phase", "--set", "value=5", "--detail", "full"], capsys
    )
    assert code == 0
    full = json.loads(out)
    request = full["issues"][0]["inference_request"]
    assert "statement" not in request
    assert "fields" not in request
    assert request["kind"] == "metric"


def test_needs_input_summary_clipped_under_limit(env, capsys, monkeypatch):
    """r1-review D5: the cap holds on the needs_input path too.

    An inference_request with 80×500 B samples used to blow the 32 KiB
    budget through the un-clipped ``issues`` list; now the summary is
    clipped in steps and the full record stays on disk.
    """

    monkeypatch.delenv("DATAAGENT_ENFORCEMENT_MODE", raising=False)
    Runtime._DEFAULT = None

    def invoke(op, payload, context):
        issue = Issue(
            code="da03.proposal_required",
            severity=Severity.warning,
            message="proposal required",
            retryable=False,
            suggested_action="fill it",
            inference_request={
                "kind": "metric",
                "statement": "sum(amount)",
                "samples": [{"row": i, "cell": "x" * 500} for i in range(80)],
            },
        )
        return CapabilityResult(status=CapabilityStatus.needs_input, issues=[issue])

    code, out, _ = _run_cli(["run", "two_phase", "--set", "value=5"], capsys, invoke=invoke)
    assert code == 0
    assert len(out.encode()) <= unified.SUMMARY_LIMIT
    summary = json.loads(out)
    assert summary["status"] == "needs_input"
    assert summary["next_command"]
    # The inference_request survives (clipped), and the full record is on disk.
    request = summary["issues"][0]["inference_request"]
    assert request["kind"] == "metric"
    records = sorted(Path(summary["result_path"]).parent.glob("*.inference_request.json"))
    assert records, "the un-clipped inference_request must be saved to results/"
    saved = json.loads(records[-1].read_text(encoding="utf-8"))
    assert len(saved["samples"]) == 80


def test_egress_scrub_keeps_content_with_decision(env, capsys, monkeypatch):
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    Runtime._DEFAULT = None

    def invoke(op, payload, context):
        issue = Issue(
            code="da03.proposal_required",
            severity=Severity.warning,
            message="proposal required",
            retryable=False,
            suggested_action="fill it",
            inference_request={
                "kind": "metric",
                "statement": "sum(amount)",
                "egress_decision_ref": "ed:1",
            },
        )
        return CapabilityResult(status=CapabilityStatus.needs_input, issues=[issue])

    code, out, _ = _run_cli(["run", "two_phase", "--set", "value=5"], capsys, invoke=invoke)
    summary = json.loads(out)
    assert summary["issues"][0]["inference_request"]["statement"] == "sum(amount)"


def test_authorize_fills_latest_allow_decision(env, capsys):
    runtime = Runtime.create()
    now = datetime.now(timezone.utc)
    runtime.decisions.save_access(
        AccessDecision(
            decision_id="ad:1",
            policy_ref=VersionedRef(id="policy:default", revision="r1"),
            subject_ref="user:alice",
            resource_ref=VersionedRef(id="file:*", revision="*"),
            purpose="monthly_report",
            decision=AccessOutcome.allow,
            valid_until=now + timedelta(hours=1),
        )
    )
    monkeypatch_env = {
        "DATAAGENT_HOST_SUBJECT_REF": "user:alice",
        "DATAAGENT_HOST_PURPOSE": "monthly_report",
    }
    import os

    old = {k: os.environ.get(k) for k in monkeypatch_env}
    os.environ.update(monkeypatch_env)
    try:
        code, out, _ = _run_cli(["run", "ping", "--set", "value=1", "--authorize"], capsys)
        assert code == 0
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    context = CAPTURED["context"]
    assert context.authorization_ref == "ad:1"
    assert context.subject_ref == "user:alice"


def test_authorize_without_decision_exit_3(env, capsys):
    code, _, err = _run_cli(["run", "ping", "--set", "value=1", "--authorize"], capsys)
    assert code == 3
    assert "no allow AccessDecision" in err


def test_validate_failure_is_environment_exit_3(env, capsys):
    def validate():
        raise RuntimeError("catalog snapshot missing")

    code, _, err = _run_cli(["list"], capsys, validate=validate)
    assert code == 3
    assert "catalog snapshot missing" in err


def test_unknown_operation_exit_2(env, capsys):
    code, _, err = _run_cli(["run", "nope"], capsys)
    assert code == 2
    code, _, err = _run_cli(["nope", "--set", "a=1"], capsys)
    assert code == 2


def test_file_hook_builds_file_ref(env, capsys, tmp_path):
    class WithFileInput(BaseModel):
        file_ref: FileRef

    @operation(
        "TEST.1.5", input_model=WithFileInput, output_model=PingOutput, description="file"
    )
    def with_file(input_obj, ctx, runtime):  # noqa: ANN001
        CAPTURED["file"] = input_obj.file_ref
        return PingOutput(value=1)

    target = tmp_path / "orders.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")

    def make_file_ref(runtime, path):
        import hashlib

        data = Path(path).read_bytes()
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        return FileRef(
            id="file:" + digest[7:23],
            kind="file",
            scope_ref="tenant:local",
            revision=digest,
            resolver="workspace",
            locator=str(path),
            digest=digest,
            media_type="application/octet-stream",
            filename=Path(path).name,
            size_bytes=len(data),
            content_digest=digest,
        ).model_dump(mode="json")

    code, out, _ = _run_cli(["run", "with_file", "--file", str(target)], capsys, make_file_ref=make_file_ref)
    assert code == 0
    assert CAPTURED["file"].locator == str(target)
    assert CAPTURED["file"].revision.startswith("sha256:")


def test_file_hook_missing_file_is_usage_error(env, capsys, tmp_path):
    """r2-review D8: ``--file <missing>`` is a usage error (exit 2), not a traceback."""

    class WithFileInput(BaseModel):
        file_ref: FileRef

    @operation(
        "TEST.1.5", input_model=WithFileInput, output_model=PingOutput, description="file"
    )
    def with_file(input_obj, ctx, runtime):  # noqa: ANN001
        return PingOutput(value=1)

    def make_file_ref(runtime, path):
        # Same shape as the data layer hook: reads the bytes, so a missing
        # path raises FileNotFoundError from inside the hook.
        Path(path).read_bytes()
        return FileRef(
            id="file:x",
            kind="file",
            scope_ref="tenant:local",
            revision="sha256:x",
            resolver="workspace",
            locator=str(path),
            digest="sha256:x",
            media_type="application/octet-stream",
            filename=Path(path).name,
            size_bytes=0,
            content_digest="sha256:x",
        ).model_dump(mode="json")

    missing = tmp_path / "nope.csv"
    code, out, err = _run_cli(
        ["run", "with_file", "--file", str(missing)], capsys, make_file_ref=make_file_ref
    )
    assert code == 2
    assert "usage error" in err
    assert "--file" in err
    assert str(missing) in err
    assert out == ""
    assert "Traceback" not in err
