"""``Runtime`` composition: access resolver, shared decision store, env wiring (W1d)."""

from __future__ import annotations

import pytest

from dataagent_contracts.core import AccessDecision, AccessOutcome, VersionedRef
from dataagent_runtime.enforcement import EnforcementConfig, enforcement_from_env
from dataagent_runtime.runtime import Runtime


def _decision(decision_id: str = "ad:1") -> AccessDecision:
    return AccessDecision(
        decision_id=decision_id,
        policy_ref=VersionedRef(id="policy:tenant", revision="r1"),
        subject_ref="user:alice",
        resource_ref=VersionedRef(id="table:orders", revision="r1"),
        purpose="report",
        decision=AccessOutcome.allow,
        valid_until="2030-01-01T00:00:00Z",
    )


def test_access_resolver_reads_the_decision_store(tmp_path):
    rt = Runtime.create(workspace_root=tmp_path, data_root=tmp_path / "data")
    assert rt.access_resolver("ad:1") is None
    rt.decisions.save_access(_decision())
    resolved = rt.access_resolver("ad:1")
    assert resolved is not None and resolved.decision is AccessOutcome.allow


def test_decisions_live_in_a_shared_file_not_the_layer_db(tmp_path):
    rt = Runtime.create(workspace_root=tmp_path, data_root=tmp_path / "data")
    rt.decisions.save_access(_decision())
    assert (tmp_path / "data" / "db" / "decisions.sqlite3").is_file()
    # two runtimes on the same data_root resolve each other's decisions
    other = Runtime.create(workspace_root=tmp_path, data_root=tmp_path / "data")
    assert other.access_resolver("ad:1") is not None


def test_enforcement_from_env(monkeypatch):
    assert enforcement_from_env().mode == "warn"
    assert enforcement_from_env(EnforcementConfig(mode="off")).mode == "off"
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    assert enforcement_from_env().mode == "enforce"
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "  ENFORCE ")
    assert enforcement_from_env().mode == "enforce"
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "nonsense")
    assert enforcement_from_env().mode == "warn"
    monkeypatch.delenv("DATAAGENT_ENFORCEMENT_MODE")
    assert enforcement_from_env(None).mode == "warn"


def test_create_reads_enforcement_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    rt = Runtime.create(workspace_root=tmp_path, data_root=tmp_path / "data")
    assert rt.enforcement.mode == "enforce"
    monkeypatch.delenv("DATAAGENT_ENFORCEMENT_MODE")
    rt = Runtime.create(workspace_root=tmp_path, data_root=tmp_path / "data2")
    assert rt.enforcement.mode == "warn"
    rt = Runtime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / "data3",
        enforcement=EnforcementConfig(mode="off"),
    )
    assert rt.enforcement.mode == "off"
