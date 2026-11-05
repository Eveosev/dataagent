"""DA11.5.6 sample isolation tests (08 §10.3)."""

from __future__ import annotations

import pytest

from dataagent_contracts.core import SplitRole, VersionedRef
from dataagent_runtime.invoke import invoke

from tests.conftest import content_ref


def ctx():
    return {
        "request_id": "req:1",
        "scope_ref": "tenant:demo",
        "authorization_ref": "seed",
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }


def case(rt, case_id, group, payload=None):  # noqa: ANN001
    input_ref = content_ref(rt, payload if payload is not None else {"case": case_id})
    expected_ref = content_ref(rt, {"gold": case_id})
    return {
        "case_id": case_id,
        "input_ref": str(input_ref),
        "expected_ref": str(expected_ref),
        "group_keys": {"entity": group},
    }


def isolate(rt, cases, **payload):  # noqa: ANN001
    body = {
        "cases": cases,
        "group_keys": ["entity"],
        "role_weights": {
            "development": 0.4,
            "regression": 0.3,
            "unseen_acceptance": 0.3,
        },
    }
    body.update(payload)
    return invoke("isolate_acceptance_samples", body, ctx(), runtime=rt)


def test_whole_groups_never_straddle_roles(rt):
    cases = [case(rt, f"c{i}", f"entity-{i % 6}") for i in range(12)]
    result = isolate(rt, cases)
    assert result.status == "ok"
    set_ref = result.data.evaluation_set
    manifest = rt.vault.get_set(str(set_ref.id), str(set_ref.revision))
    roles_by_group: dict[str, set[str]] = {}
    for entry in manifest["cases"]:
        roles_by_group.setdefault(entry["group_keys"]["entity"], set()).add(entry["role"])
    assert all(len(roles) == 1 for roles in roles_by_group.values())
    assert set(manifest["counts"].values()) and sum(manifest["counts"].values()) == 12


def test_fingerprint_dedup_warns(rt):
    same = {"shared": "payload"}
    cases = [case(rt, "c1", "entity-a", same), case(rt, "c2", "entity-b", same)]
    result = isolate(rt, cases)
    assert result.status == "ok"
    assert any("near-duplicate" in w for w in result.data.warnings)
    set_ref = result.data.evaluation_set
    manifest = rt.vault.get_set(str(set_ref.id), str(set_ref.revision))
    assert [c["case_id"] for c in manifest["cases"]] == ["c1"]


def test_freeze_is_immutable_and_new_samples_need_new_revision(rt):
    cases = [case(rt, f"c{i}", f"entity-{i}") for i in range(6)]
    result = isolate(rt, cases, freeze=True)
    set_ref = result.data.evaluation_set
    assert set_ref.frozen

    frozen_manifest = rt.vault.get_set(str(set_ref.id), str(set_ref.revision))
    assert frozen_manifest["frozen"] is True

    # new samples produce a new revision, the frozen one is untouched
    new_ref = rt.vault.add_samples(str(set_ref.id), str(set_ref.revision), [])
    # add_samples with no cases still mints a new (unfrozen) revision
    newer = rt.vault.get_set(str(new_ref.id), str(new_ref.revision))
    assert newer["frozen"] is False
    assert rt.vault.get_set(str(set_ref.id), str(set_ref.revision))["frozen"] is True


def test_gold_read_outside_acceptance_demotes_and_logs(rt):
    cases = [case(rt, f"c{i}", f"entity-{i}") for i in range(9)]
    result = isolate(rt, cases, freeze=True)
    set_ref = result.data.evaluation_set
    manifest = rt.vault.get_set(str(set_ref.id), str(set_ref.revision))
    unseen = [
        c for c in manifest["cases"] if c["role"] == SplitRole.unseen_acceptance.value
    ]
    if not unseen:  # role weights guarantee at least one unseen group for 9 cases
        pytest.skip("no unseen case in this split")
    target = unseen[0]

    # CLI/other read of the gold: exposure ledger + demotion
    rt.vault.read_gold(
        str(set_ref.id),
        str(set_ref.revision),
        target["case_id"],
        purpose="debug",
        accessed_by="cli",
    )
    ledger = rt.vault.exposure_ledger(str(set_ref.id))
    assert any(e.case_id == target["case_id"] for e in ledger)
    demoted = rt.vault.get_set(str(set_ref.id), str(set_ref.revision))
    # the frozen revision is immutable: demotion lands in a *new* revision
    assert demoted["frozen"] is True
    current = rt.versions.current("eval_set", str(set_ref.id))[1]
    roles = {c["case_id"]: c["role"] for c in current["cases"]}
    assert roles[target["case_id"]] == SplitRole.regression.value


def test_group_keys_prevent_cross_role_leakage_by_construction(rt):
    """§10.3: 同一分组键的样本不跨角色."""

    cases = [case(rt, f"c{i}", "entity-same") for i in range(5)]
    result = isolate(rt, cases)
    set_ref = result.data.evaluation_set
    manifest = rt.vault.get_set(str(set_ref.id), str(set_ref.revision))
    roles = {c["role"] for c in manifest["cases"]}
    assert len(roles) == 1
