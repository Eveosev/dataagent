"""DATAAGENT_ENFORCEMENT_MODE wiring for the process entries (08 §4.3)."""

from __future__ import annotations

from dataagent_governance.runtime import GovernanceRuntime


def test_env_mode_enforce_is_applied(monkeypatch, tmp_path):
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    rt = GovernanceRuntime.create(
        workspace_root=tmp_path, data_root=tmp_path / ".dataagent"
    )
    assert rt.enforcement.mode == "enforce"


def test_env_mode_invalid_falls_back_to_default(monkeypatch, tmp_path):
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "nonsense")
    rt = GovernanceRuntime.create(
        workspace_root=tmp_path, data_root=tmp_path / ".dataagent"
    )
    assert rt.enforcement.mode == "warn"


def test_explicit_enforcement_wins_over_env(monkeypatch, tmp_path):
    from dataagent_runtime.enforcement import EnforcementConfig

    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    rt = GovernanceRuntime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / ".dataagent",
        enforcement=EnforcementConfig(mode="off"),
    )
    assert rt.enforcement.mode == "off"
