"""Data-layer gate re-run under enforcement (08 §4.3, §10.2 item 3).

Every one of the 32 data-layer atoms is invoked through the DA12.1 access
recheck composed in ``dataagent_scenarios.gate``: with a covering decision
the call reaches the data-layer handler; with a bogus authorization it is
denied before any read happens. Representative atoms are also executed end
to end under ``enforce``.
"""

from __future__ import annotations

import hashlib

import pytest
from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    CallContext,
    VersionedRef,
)
from dataagent_data.registry import list_operations as data_operations
from dataagent_runtime.enforcement import EnforcementConfig, access_recheck

from dataagent_scenarios.gate import RESOURCE_FIELDS, enforce_data_invoke

ENFORCE = EnforcementConfig(mode="enforce")


@pytest.fixture()
def governance(tmp_path):
    from dataagent_governance.runtime import GovernanceRuntime

    rt = GovernanceRuntime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / ".dataagent",
        enforcement=ENFORCE,
        host_subject_ref="user:alice",
        host_purpose="monthly_report",
    )
    from dataagent_governance.contracts import PolicyDocument, PolicyRule

    rt.policy.save(
        PolicyDocument(
            policy_id="tenant:default",
            revision="r1",
            rules=[
                PolicyRule(
                    rule_id="allow-s0-files",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["file"],
                    purposes=["monthly_report"],
                ),
                PolicyRule(
                    rule_id="allow-s0-docs",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["doc"],
                    purposes=["monthly_report"],
                ),
                PolicyRule(
                    rule_id="allow-s0-tables",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["table"],
                    purposes=["monthly_report"],
                ),
                PolicyRule(
                    rule_id="allow-s0-profiles",
                    effect="allow",
                    subjects=["user:alice"],
                    resources=["profile"],
                    purposes=["monthly_report"],
                ),
            ],
        )
    )
    return rt


@pytest.fixture()
def data(tmp_path):
    from dataagent_data.runtime import create as create_data_runtime

    # same data_root as the governance runtime: the S0 composition shares
    # the decisions store (08 §2), so AccessDecisions minted by governance
    # resolve on the data layer's own product path
    rt = create_data_runtime(
        workspace_root=tmp_path, data_root=tmp_path / ".dataagent"
    )
    (tmp_path / "orders.csv").write_bytes(
        b"order_id,region,amount\no1,north,100\no2,south,200\n"
    )
    return rt


def _ctx(**over):
    base = {
        "request_id": "req:1",
        "scope_ref": "tenant:demo",
        "authorization_ref": "seed",
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }
    base.update(over)
    return CallContext(**base)


def _file_ref(workspace, name):
    payload = (workspace / name).read_bytes()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return {
        "id": f"file:{digest[7:23]}",
        "kind": "file",
        "scope_ref": "tenant:demo",
        "revision": digest,
        "resolver": "workspace",
        "locator": name,
        "digest": digest,
        "media_type": "application/octet-stream",
        "filename": name,
        "size_bytes": len(payload),
        "content_digest": digest,
    }


def _mint_decision(governance, resource: str) -> str:
    from dataagent_runtime.invoke import invoke as gov_invoke

    result = gov_invoke(
        "check_access_scope",
        {"resource_ref": resource},
        _ctx(),
        runtime=governance,
    )
    assert result.status == "ok" and result.data.decision.decision == "allow"
    return result.data.decision.decision_id


def _gate_payload(operation: str, workspace, table, profile=None) -> dict:
    """A payload carrying the operation's input resources.

    File readers get the real CSV; table operations get the really parsed
    table; the profile branch gets a really profiled table (B1); document
    operations a document ref. Operations that read no data-layer resource
    get an empty payload — the recheck still has to resolve the
    authorization for them.
    """

    fields = {
        "file_ref": _file_ref(workspace, "orders.csv"),
        "table_ref": table,
        "document_ref": {"id": "doc:orders", "revision": "r1", "kind": "document"},
        "workbook_ref": {"id": "wb:orders", "revision": "r1", "kind": "workbook"},
    }
    if profile is not None:
        fields["profile_ref"] = profile
    payload = {
        name: fields[name]
        for name in RESOURCE_FIELDS.get(operation, ())
        if name in fields
    }
    if operation == "infer_field_types" and profile is not None:
        # the op takes one branch per call: drive the profile branch here
        # (B1); the table branch is covered by the table-reading atoms
        payload.pop("table_ref", None)
    return payload


def _covering_decision_for(payload: dict, decisions: dict[str, str]) -> str:
    from dataagent_scenarios.gate import _as_ref

    for value in payload.values():
        ref = _as_ref(value)
        if ref is None:
            continue
        for kind in ("file", "doc", "table", "profile"):
            if ref.id.startswith(f"{kind}:"):
                return decisions[kind]
    return decisions["file"]


def test_all_32_data_atoms_pass_the_recheck_with_a_covering_decision(
    governance, data, tmp_path
):
    """§10.2: enforce 模式下数据层 32 个原子全部经过复检.

    Every atom is actually invoked through the composed gate: with a
    covering decision the call reaches the data layer (business result,
    never ``da12.access_denied``); with a bogus authorization it is denied
    before any handler runs.
    """

    # a really parsed table backs the table-reading atoms
    from dataagent_data.invoke import invoke as data_layer_invoke

    parsed = data_layer_invoke(
        "parse_delimited_file",
        {"file_ref": _file_ref(tmp_path, "orders.csv")},
        _ctx(),
        runtime=data,
    )
    assert parsed.status.value == "ok", parsed.issues
    table = parsed.data.table.model_dump(mode="json")

    # a really profiled table backs the profile-reading branch (B1)
    profiled = data_layer_invoke(
        "profile_table_structure",
        {"table_ref": table},
        _ctx(),
        runtime=data,
    )
    assert profiled.status.value == "ok", profiled.issues
    profile = profiled.data.profile.model_dump(mode="json")

    decisions = {
        "file": _mint_decision(governance, "file@*"),
        "doc": _mint_decision(governance, "doc@*"),
        "table": _mint_decision(governance, "table@*"),
        "profile": _mint_decision(governance, "profile@*"),
    }

    ops = [
        spec
        for spec in data_operations()
        if spec.source_file.startswith("src/dataagent_data/")
    ]
    assert len(ops) == 32
    for spec in ops:
        payload = _gate_payload(spec.operation, tmp_path, table, profile)
        authorized = enforce_data_invoke(
            spec.operation,
            payload,
            _ctx(authorization_ref=_covering_decision_for(payload, decisions)),
            runtime=data,
            resolver=governance.access_resolver,
            enforcement=ENFORCE,
        )
        assert authorized.status.value in {"ok", "needs_input", "failed"}, (
            f"{spec.capability_id} {spec.operation}: {authorized.status}"
        )
        assert not any(
            issue.code == "da12.access_denied" for issue in authorized.issues
        ), f"{spec.capability_id} {spec.operation}: denied under a covering decision"

        # the same call with someone else's authorization never reaches the
        # data layer: the gate denies it first
        denied = enforce_data_invoke(
            spec.operation,
            payload,
            _ctx(authorization_ref="ad:someone-elses"),
            runtime=data,
            resolver=governance.access_resolver,
            enforcement=ENFORCE,
        )
        assert denied.status.value == "failed", spec.operation
        assert denied.issues[0].code == "da12.access_denied", spec.operation


def test_recheck_rejects_without_decision(governance):
    outcome = access_recheck(
        _ctx(),
        lambda ref: None,
        [VersionedRef(id="file:orders", revision="r1")],
        config=ENFORCE,
    )
    assert not outcome.ok
    assert outcome.issue.code == "da12.access_denied"


def test_recheck_rejects_expired_or_uncovered_or_wrong_purpose(governance):
    base = dict(
        policy_ref=VersionedRef(id="policy:p", revision="r1"),
        subject_ref="user:alice",
        purpose="monthly_report",
        decision=AccessOutcome.allow,
    )
    expired = AccessDecision(
        decision_id="ad:exp",
        resource_ref=VersionedRef(id="file", revision="*"),
        valid_until="2020-01-01T00:00:00Z",
        **base,
    )
    outcome = access_recheck(
        _ctx(authorization_ref="ad:exp"),
        lambda ref: expired,
        [VersionedRef(id="file:orders", revision="r1")],
        config=ENFORCE,
    )
    assert not outcome.ok and any("expired" in r for r in outcome.reasons)

    uncovered = AccessDecision(
        decision_id="ad:unc",
        resource_ref=VersionedRef(id="table:orders", revision="*"),
        valid_until="2030-01-01T00:00:00Z",
        **base,
    )
    outcome = access_recheck(
        _ctx(authorization_ref="ad:unc"),
        lambda ref: uncovered,
        [VersionedRef(id="file:orders", revision="r1")],
        config=ENFORCE,
    )
    assert not outcome.ok and any("does not cover" in r for r in outcome.reasons)

    wrong_purpose = AccessDecision(
        decision_id="ad:pur",
        resource_ref=VersionedRef(id="file", revision="*"),
        valid_until="2030-01-01T00:00:00Z",
        **{**base, "purpose": "fraud_scan"},
    )
    outcome = access_recheck(
        _ctx(authorization_ref="ad:pur"),
        lambda ref: wrong_purpose,
        [VersionedRef(id="file:orders", revision="r1")],
        config=ENFORCE,
    )
    assert not outcome.ok and any("purpose mismatch" in r for r in outcome.reasons)


def test_parse_delimited_file_executes_under_enforce(governance, data, tmp_path):
    """Full handler execution behind the gate: mint the decision, then parse."""

    # 1. mint an AccessDecision for the file subtree through DA12.1.1
    decision_id = _mint_decision(governance, "file@*")

    # 2. the data-layer read runs with that decision as authorization_ref
    file_ref = _file_ref(tmp_path, "orders.csv")
    result = enforce_data_invoke(
        "parse_delimited_file",
        {"file_ref": file_ref},
        _ctx(authorization_ref=decision_id),
        runtime=data,
        resolver=governance.access_resolver,
        enforcement=ENFORCE,
    )
    assert result.status.value == "ok", result.issues
    assert result.data.row_count == 2

    # 3. an unrelated authorization is rejected before any read happens:
    #    the data invoke itself fails with da12.access_denied
    denied = enforce_data_invoke(
        "parse_delimited_file",
        {"file_ref": file_ref},
        _ctx(authorization_ref="ad:someone-elses"),
        runtime=data,
        resolver=governance.access_resolver,
        enforcement=ENFORCE,
    )
    assert denied.status.value == "failed"
    assert denied.issues[0].code == "da12.access_denied"


def test_product_path_rechecks_on_the_shared_decision_store(governance, data, tmp_path):
    """The data layer's own invoke — no composed gate, no injected resolver.

    This is the path an S0 deployment actually runs (08 §10.2: the recheck
    belongs on the product path, not on a test-only gate): the runtime
    rechecks ``resource_fields`` itself and resolves the authorization from
    the shared ``data_root/db/decisions.sqlite3`` governance minted into.
    """

    from dataagent_data.invoke import invoke as data_invoke
    from dataagent_data.runtime import create as create_data_runtime

    product = create_data_runtime(
        workspace_root=tmp_path,
        data_root=tmp_path / ".dataagent",
        enforcement=ENFORCE,
    )
    decision = _mint_decision(governance, "file@*")
    payload = {"file_ref": _file_ref(tmp_path, "orders.csv")}

    allowed = data_invoke(
        "parse_delimited_file",
        payload,
        _ctx(authorization_ref=decision),
        runtime=product,
    )
    assert allowed.status.value == "ok", allowed.issues
    assert allowed.data.row_count == 2
    assert not any(i.code == "da12.access_denied" for i in allowed.issues)

    denied = data_invoke(
        "parse_delimited_file",
        payload,
        _ctx(authorization_ref="ad:someone-elses"),
        runtime=product,
    )
    assert denied.status.value == "failed"
    assert denied.issues[0].code == "da12.access_denied"


def test_all_resource_reading_atoms_are_declared():
    """The data layer's own registry declares the recheck resources (W1d).

    22 of the 32 atoms read an input resource and must declare it, so the
    recheck runs on the product path without the gate's shadow table.
    ``infer_field_types`` declares both its table branch and its profile
    branch (B1): the profile's field stats are the derived content of the
    profile asset.
    """

    declared = {
        spec.operation: tuple(spec.resource_fields or ())
        for spec in data_operations()
        if spec.source_file.startswith("src/dataagent_data/")
    }
    assert len(declared) == 32
    assert sum(1 for fields in declared.values() if fields) == 22
    # the gate's mapping and the declarations must agree
    for operation, fields in declared.items():
        assert fields == tuple(RESOURCE_FIELDS.get(operation, ())), operation


def test_infer_field_types_profile_branch_is_gated(governance, data, tmp_path):
    """B1: the profile branch reads governed content and must be rechecked.

    ``infer_field_types(profile_ref=...)`` reads the profile's field stats —
    the derived content of the profile asset. A decision that only covers
    the table subtree does not authorize it; a profile-subtree decision does.
    """

    from dataagent_data.invoke import invoke as data_layer_invoke

    parsed = data_layer_invoke(
        "parse_delimited_file",
        {"file_ref": _file_ref(tmp_path, "orders.csv")},
        _ctx(),
        runtime=data,
    )
    assert parsed.status.value == "ok", parsed.issues
    table = parsed.data.table.model_dump(mode="json")
    profiled = data_layer_invoke(
        "profile_table_structure",
        {"table_ref": table},
        _ctx(),
        runtime=data,
    )
    assert profiled.status.value == "ok", profiled.issues
    profile = profiled.data.profile.model_dump(mode="json")

    table_only = _mint_decision(governance, "table@*")
    denied = enforce_data_invoke(
        "infer_field_types",
        {"profile_ref": profile},
        _ctx(authorization_ref=table_only),
        runtime=data,
        resolver=governance.access_resolver,
        enforcement=ENFORCE,
    )
    assert denied.status.value == "failed"
    assert denied.issues[0].code == "da12.access_denied"

    profile_ok = _mint_decision(governance, "profile@*")
    allowed = enforce_data_invoke(
        "infer_field_types",
        {"profile_ref": profile},
        _ctx(authorization_ref=profile_ok),
        runtime=data,
        resolver=governance.access_resolver,
        enforcement=ENFORCE,
    )
    assert allowed.status.value in {"ok", "partial"}
    assert not any(i.code == "da12.access_denied" for i in allowed.issues)


def test_rebound_table_content_is_denied_under_the_covering_decision(
    governance, data, tmp_path
):
    """B1: a self-reported asset cannot be rebound to other content.

    The decision covers ``table:allowed@r1``; the payload claims that asset
    but points ``data_ref`` at another object's content digest, and the
    asset revision is not the content digest. The closure cannot be
    verified, so the read is denied before any content is fetched.
    """

    from dataagent_contracts.core import AssetRef, TableRef

    secret_payload = {
        "sheet": "private",
        "columns": [{"name": "secret", "field_id": "secret"}],
        "rows": [["SECRET-ONLY-FORBIDDEN-TABLE"]],
        "row_meta": [],
        "merged_ranges": [],
        "source": {},
    }
    secret_digest = data.content.put(secret_payload)
    rebound = TableRef(
        asset=AssetRef(
            id="table:allowed",
            kind="table",
            scope_ref="tenant:demo",
            revision="r1",
            resolver="local_content",
            locator=secret_digest,
            digest=secret_digest,
        ),
        schema_ref={"id": "schema:allowed", "revision": "r1"},
        data_ref=secret_digest,
    )
    covering = _mint_decision(governance, "table:allowed@r1")
    denied = enforce_data_invoke(
        "profile_table_structure",
        {"table_ref": rebound.model_dump(mode="json")},
        _ctx(authorization_ref=covering),
        runtime=data,
        resolver=governance.access_resolver,
        enforcement=ENFORCE,
    )
    assert denied.status.value == "failed"
    assert denied.issues[0].code == "da12.access_denied"
    assert "resource closure" in denied.issues[0].message
