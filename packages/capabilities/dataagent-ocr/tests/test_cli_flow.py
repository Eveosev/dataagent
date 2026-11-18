"""End-to-end CLI flow: configure → verify (test call) → pinned → use → re-selection rules."""

from __future__ import annotations

import io
import json
import os
import stat
from pathlib import Path

import pytest

from dataagent_contracts.core import EgressDecision
from dataagent_ocr import load_active_engine
from dataagent_ocr.cli import main
from dataagent_ocr.probe import PROBE_LINES, render_probe
from dataagent_ocr.profiles import ProfileStore, sha256_hex


def run(capsys, monkeypatch, *argv, stdin: str = ""):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out)


def configure(capsys, monkeypatch, server, profile="vl", model="qwen-vl-ocr", key=None):
    return run(
        capsys,
        monkeypatch,
        "configure-openai",
        "--profile", profile,
        "--base-url", server.base_url,
        "--model", model,
        "--deployment", "vendor_api",
        "--api-key-stdin",
        stdin=(key or server.api_key) + "\n",
    )


def test_configure_verify_pin_status(capsys, monkeypatch, fake_openai, data_root, home):
    code, out = configure(capsys, monkeypatch, fake_openai)
    assert code == 0 and out["profile"]["profile"] == "vl@r1"
    assert fake_openai.api_key not in json.dumps(out)
    secrets_root = home / ".dataagent" / "secrets"
    key_file = secrets_root / "ocr" / "ocr-vl.key"
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(secrets_root.stat().st_mode) == 0o700
    assert (secrets_root / ".gitignore").read_text() == "*\n"
    assert not (data_root / "secrets").exists()

    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl")
    assert code == 0, out
    assert out["pinned"]["reason"] == "initial_setup"
    assert out["verification"]["fixtures"][0]["score"] == 1.0
    assert any("sample from the user's own documents" in w for w in out["warnings"])

    code, out = run(capsys, monkeypatch, "status")
    assert code == 0 and out["active"]["profile"]["model"] == "qwen-vl-ocr"
    assert out["active"]["quality"]["status"] == "insufficient"
    assert fake_openai.api_key not in json.dumps(out)


def test_pinned_engine_matches_data_layer_protocol(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai)
    run(capsys, monkeypatch, "verify", "--profile", "vl")
    engine = load_active_engine(data_root)
    blocks = engine.recognize(render_probe().image, lang=None)
    assert [b.text for b in blocks] == PROBE_LINES
    assert all(isinstance(b.confidence, float) for b in blocks)
    assert engine.engine_ref == "openai_compat:qwen-vl-ocr"
    assert engine.engine_version.startswith("vl@r1:")
    usage = (data_root / "ocr" / "quality" / "usage.jsonl").read_text().splitlines()
    assert json.loads(usage[-1])["confidence_source"] == "logprobs"


def test_failed_verification_does_not_pin(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai)
    fake_openai.mode = "garbage"
    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl")
    assert code == 1 and "pinned" not in out
    code, out = run(capsys, monkeypatch, "status")
    assert code == 3 and out["error"]["code"] == "ocr.not_configured"


def test_switch_requires_user_request_or_degraded_quality(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai)
    run(capsys, monkeypatch, "verify", "--profile", "vl")
    configure(capsys, monkeypatch, fake_openai, profile="vl2", model="other-vl")
    before = len(fake_openai.requests)

    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl2")
    assert code == 3 and out["error"]["code"] == "ocr.switch_refused"
    assert len(fake_openai.requests) == before  # refused before any test call

    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl2", "--reason", "quality_degraded")
    assert code == 3 and "not degraded" in out["error"]["message"]

    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl2", "--reason", "user_request")
    assert code == 3 and "instruction" in out["error"]["message"]

    code, out = run(
        capsys, monkeypatch, "verify", "--profile", "vl2", "--reason", "user_request",
        "--user-instruction", "把 OCR 模型换成 other-vl",
    )
    assert code == 0 and out["pinned"]["reason"] == "user_request"
    assert out["pinned"]["previous"] == "vl@r1" and out["pinned"]["evidence"] == "把 OCR 模型换成 other-vl"


def test_changing_model_of_pinned_profile_is_a_switch(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai)
    run(capsys, monkeypatch, "verify", "--profile", "vl")
    configure(capsys, monkeypatch, fake_openai, model="bigger-vl")  # same profile id, new revision
    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl")
    assert code == 3 and out["error"]["code"] == "ocr.switch_refused"


def test_degraded_quality_allows_switch(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai)
    run(capsys, monkeypatch, "verify", "--profile", "vl")
    for _ in range(3):
        code, out = run(capsys, monkeypatch, "feedback", "--kind", "wrong_digits", "--document", "inv-1")
    assert out["quality"]["status"] == "degraded"
    code, out = run(capsys, monkeypatch, "quality")
    assert "do not switch without the user's approval" in out["next"]
    configure(capsys, monkeypatch, fake_openai, profile="vl2", model="other-vl")
    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl2", "--reason", "quality_degraded")
    assert code == 0 and out["pinned"]["reason"] == "quality_degraded"
    assert out["pinned"]["evidence"].startswith("qv-")


def test_key_rotation_keeps_pin(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai)
    run(capsys, monkeypatch, "verify", "--profile", "vl")
    fake_openai.api_key = "sk-rotated-456"
    with pytest.raises(Exception):
        load_active_engine(data_root).recognize(render_probe().image)
    code, out = run(capsys, monkeypatch, "set-key", "--profile", "vl", "--api-key-stdin", stdin="sk-rotated-456\n")
    assert code == 0 and out["created_revision"] is False  # same reference, same revision
    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl")
    assert code == 0 and out["pinned"]["reason"] == "reverify"


def test_wrong_key_needs_input_not_switch(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai, key="sk-bad")
    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl")
    assert code == 3 and out["error"]["code"] == "ocr.credentials"
    assert "sk-bad" not in json.dumps(out)


def test_tampered_profile_breaks_pin(capsys, monkeypatch, fake_openai, data_root):
    configure(capsys, monkeypatch, fake_openai)
    run(capsys, monkeypatch, "verify", "--profile", "vl")
    path = data_root / "ocr" / "profiles" / "vl" / "r1.json"
    data = json.loads(path.read_text())
    data["openai_compat"]["model"] = "swapped"
    path.write_text(json.dumps(data))
    code, out = run(capsys, monkeypatch, "status")
    assert code == 3 and out["error"]["code"] == "ocr.pin_mismatch"


def test_user_sample_needs_egress_decision_under_enforce(capsys, monkeypatch, fake_openai, data_root, tmp_path):
    configure(capsys, monkeypatch, fake_openai)
    sample = tmp_path / "invoice.png"
    sample.write_bytes(render_probe().image)
    expect = tmp_path / "invoice.txt"
    expect.write_text("\n".join(PROBE_LINES))
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    before = len(fake_openai.requests)
    code, out = run(capsys, monkeypatch, "verify", "--profile", "vl", "--sample", str(sample), "--expect", str(expect))
    assert code == 3 and out["error"]["code"] == "ocr.egress_required"
    assert len(fake_openai.requests) == before

    from dataagent_runtime.adapters.sqlite import SqliteDatabase, SqliteDecisionStore

    digest = sha256_hex(sample.read_bytes())
    store = SqliteDecisionStore(SqliteDatabase(data_root / "db" / "decisions.sqlite3"))
    store.save_egress(
        EgressDecision.model_validate(
            {
                "decision_id": "egr-1",
                "content_refs": [{"id": "sample", "revision": f"sha256:{digest}"}],
                "destination": {"model_ref": "openai_compat:qwen-vl-ocr", "deployment": "vendor_api"},
                "decision": "allow",
                "access_decision_ref": "acc-1",
            }
        )
    )
    code, out = run(
        capsys, monkeypatch, "verify", "--profile", "vl", "--sample", str(sample), "--expect", str(expect),
        "--egress-decision-ref", "egr-1",
    )
    assert code == 0, out
    assert [f["fixture"] for f in out["verification"]["fixtures"]] == ["builtin:probe-v1", "sample:invoice.png"]


def test_local_deployment_needs_no_egress(capsys, monkeypatch, fake_openai, data_root, tmp_path):
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    run(
        capsys, monkeypatch, "configure-openai", "--profile", "local", "--base-url", fake_openai.base_url,
        "--model", "qwen-vl-ocr", "--api-key-stdin", stdin=fake_openai.api_key + "\n",
    )
    store = ProfileStore(data_root)
    assert store.get("local").openai_compat.deployment == "local"  # 127.0.0.1 → local
    sample = tmp_path / "s.png"
    sample.write_bytes(render_probe().image)
    expect = tmp_path / "s.txt"
    expect.write_text("\n".join(PROBE_LINES))
    code, out = run(capsys, monkeypatch, "verify", "--profile", "local", "--sample", str(sample), "--expect", str(expect))
    assert code == 0, out
