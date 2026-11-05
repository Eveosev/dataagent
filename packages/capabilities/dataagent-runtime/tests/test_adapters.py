from __future__ import annotations

import pytest

from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    EgressDecision,
    EgressOutcome,
    ModelDestination,
    VersionedRef,
)
from dataagent_runtime.adapters.local_content import LocalContentStore
from dataagent_runtime.adapters.sqlite import (
    SqliteDatabase,
    SqliteDecisionStore,
    SqliteVersionedRepository,
)
from dataagent_runtime.errors import CapabilityError


def test_content_store_roundtrip(tmp_path):
    store = LocalContentStore(tmp_path / "content")
    digest = store.put({"b": 2, "a": 1})
    assert digest.startswith("sha256:")
    assert store.exists(digest)
    assert store.get_json(digest) == {"a": 1, "b": 2}
    assert store.put({"a": 1, "b": 2}) == digest  # canonical form is stable
    with pytest.raises(FileNotFoundError):
        store.get("sha256:" + "0" * 64)


def test_versioned_repository_optimistic_concurrency(tmp_path):
    repo = SqliteVersionedRepository(SqliteDatabase(tmp_path / "db.sqlite3"))
    r1 = repo.save("policy", "p1", {"v": 1})
    assert r1 == "r1"
    r2 = repo.save("policy", "p1", {"v": 2}, expected_revision=r1)
    assert r2 == "r2"
    with pytest.raises(CapabilityError):
        repo.save("policy", "p1", {"v": 3}, expected_revision=r1)
    assert repo.current("policy", "p1") == ("r2", {"v": 2})
    assert repo.get("policy", "p1", "r1") == {"v": 1}


def test_versioned_repository_content_addressed_dedup(tmp_path):
    repo = SqliteVersionedRepository(SqliteDatabase(tmp_path / "db.sqlite3"))
    rev1, payload, existing = repo.save_content_addressed("sample", "s1", {"x": 1})
    assert not existing  # first write mints a new revision
    rev2, _, existing2 = repo.save_content_addressed("sample", "s1", {"x": 1})
    assert existing2 and rev1 == rev2  # identical content dedups to the same revision


def _access_decision(decision_id="ad:1"):
    return AccessDecision(
        decision_id=decision_id,
        policy_ref=VersionedRef(id="policy:tenant", revision="r1"),
        subject_ref="user:alice",
        resource_ref=VersionedRef(id="table:orders", revision="r1"),
        purpose="monthly_report",
        decision=AccessOutcome.allow,
        valid_until="2030-01-01T00:00:00Z",
    )


def _egress_decision(decision_id="ed:1"):
    return EgressDecision(
        decision_id=decision_id,
        content_refs=[VersionedRef(id="content:abc", revision="r1")],
        destination=ModelDestination(model_ref="model:local-llm", deployment="local"),
        decision=EgressOutcome.allow,
        access_decision_ref="ad:1",
    )


def test_decision_store_roundtrip(tmp_path):
    store = SqliteDecisionStore(SqliteDatabase(tmp_path / "db.sqlite3"))
    access = _access_decision()
    egress = _egress_decision()
    store.save_access(access)
    store.save_egress(egress)
    assert store.get_access("ad:1") == access
    assert store.get_egress("ed:1") == egress
    assert store.get_access("missing") is None
    assert store.get_egress("missing") is None
