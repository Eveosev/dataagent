"""DA12.1 access recheck on the data layer's product path (08 §4.3, §10.2, W1d).

The 22 resource-reading atoms are rechecked by the shared ``invoke`` before
their handlers run; the mode comes from the trusted host
(``DATAAGENT_ENFORCEMENT_MODE``), the decisions from the shared
``data_root/db/decisions.sqlite3``.
"""

from __future__ import annotations

import hashlib

import pytest
from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    VersionedRef,
)

from dataagent_data.runtime import create as create_runtime
from dataagent_runtime.enforcement import EnforcementConfig


@pytest.fixture()
def workspace(tmp_path):
    path = tmp_path / "workspace"
    path.mkdir()
    (path / "orders.csv").write_bytes(
        b"order_id,region,amount\no1,north,100\no2,south,200\n"
    )
    return path


def _ctx(authorization: str = "policy:test-read") -> dict:
    return {
        "request_id": "req:gate",
        "scope_ref": "tenant:test/project:p1",
        "authorization_ref": authorization,
        "subject_ref": "user:alice",
        "purpose": "monthly_report",
    }


def _file_ref(workspace, name: str) -> dict:
    payload = (workspace / name).read_bytes()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return {
        "id": f"file:{digest[7:23]}",
        "kind": "file",
        "scope_ref": "tenant:test/project:p1",
        "revision": digest,
        "resolver": "workspace",
        "locator": name,
        "digest": digest,
        "media_type": "text/csv",
        "filename": name,
        "size_bytes": len(payload),
        "content_digest": digest,
    }


def _decision(decision_id: str, *, resource: str = "file@*") -> AccessDecision:
    return AccessDecision(
        decision_id=decision_id,
        policy_ref=VersionedRef(id="policy:tenant", revision="r1"),
        subject_ref="user:alice",
        resource_ref=VersionedRef(id=resource.split("@")[0], revision="*"),
        purpose="monthly_report",
        decision=AccessOutcome.allow,
        valid_until="2030-01-01T00:00:00Z",
    )


def _call(runtime, payload, context):
    from dataagent_data.invoke import invoke

    return invoke("parse_delimited_file", payload, context, runtime=runtime)


def test_runtime_carries_enforcement_and_resolver(workspace, tmp_path):
    runtime = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    assert hasattr(runtime, "enforcement")
    assert runtime.enforcement.mode == "warn"
    assert hasattr(runtime, "access_resolver")
    runtime.decisions.save_access(_decision("ad:1"))
    assert runtime.access_resolver("ad:1") is not None
    assert runtime.access_resolver("ad:none") is None


def test_decisions_are_shared_through_data_root(workspace, tmp_path):
    # two runtimes on the same data_root resolve each other's decisions:
    # the governance layer mints into the same file
    first = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    first.decisions.save_access(_decision("ad:shared"))
    second = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    assert second.access_resolver("ad:shared") is not None


def test_enforce_mode_comes_from_env(workspace, tmp_path, monkeypatch):
    monkeypatch.setenv("DATAAGENT_ENFORCEMENT_MODE", "enforce")
    runtime = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    assert runtime.enforcement.mode == "enforce"


def test_default_warn_keeps_reads_running_with_a_warning(workspace, tmp_path):
    runtime = create_runtime(workspace_root=workspace, data_root=tmp_path / "data")
    result = _call(runtime, {"file_ref": _file_ref(workspace, "orders.csv")}, _ctx())
    assert result.status.value == "ok"
    assert result.data.row_count == 2
    assert any(i.code == "da12.access_denied" for i in result.issues)
    assert all(i.severity.value == "warning" for i in result.issues)


def test_off_mode_skips_the_recheck(workspace, tmp_path):
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    result = _call(runtime, {"file_ref": _file_ref(workspace, "orders.csv")}, _ctx())
    assert result.status.value == "ok"
    assert result.issues == []


def test_enforce_denies_unresolvable_authorization(workspace, tmp_path):
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    result = _call(runtime, {"file_ref": _file_ref(workspace, "orders.csv")}, _ctx())
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"
    # denied before any read: no table was produced
    assert result.data is None


def test_enforce_allows_with_a_covering_decision(workspace, tmp_path):
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    runtime.decisions.save_access(_decision("ad:cover"))
    result = _call(
        runtime, {"file_ref": _file_ref(workspace, "orders.csv")}, _ctx("ad:cover")
    )
    assert result.status.value == "ok", result.issues
    assert result.data.row_count == 2
    assert result.issues == []


def test_enforce_denies_a_decision_not_covering_the_resource(workspace, tmp_path):
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    runtime.decisions.save_access(_decision("ad:other", resource="table:orders@r1"))
    result = _call(
        runtime, {"file_ref": _file_ref(workspace, "orders.csv")}, _ctx("ad:other")
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "does not cover" in result.issues[0].message


def test_enforce_denies_expired_or_wrong_purpose(workspace, tmp_path):
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    expired = _decision("ad:expired")
    expired = expired.model_copy(update={"valid_until": "2020-01-01T00:00:00Z"})
    runtime.decisions.save_access(expired)
    result = _call(
        runtime, {"file_ref": _file_ref(workspace, "orders.csv")}, _ctx("ad:expired")
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"

    wrong_purpose = _decision("ad:purpose").model_copy(update={"purpose": "fraud_scan"})
    runtime.decisions.save_access(wrong_purpose)
    result = _call(
        runtime, {"file_ref": _file_ref(workspace, "orders.csv")}, _ctx("ad:purpose")
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"


def test_non_resource_operations_are_not_gated(workspace, tmp_path):
    # record_trace reads no data-layer resource: no recheck, even in enforce
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    from dataagent_data.invoke import invoke

    result = invoke(
        "append_task_event",
        {
            "task_ref": "task:t1@r1",
            "event_id": "evt:1",
            "actor_ref": "user:alice",
            "payload": {"state": "running"},
        },
        _ctx("ad:does-not-exist"),
        runtime=runtime,
    )
    assert result.status.value == "ok", result.issues


def test_mcp_context_schema_carries_subject_and_purpose():
    from dataagent_data.interfaces.mcp_server import CONTEXT_SCHEMA

    props = CONTEXT_SCHEMA["properties"]
    assert "subject_ref" in props and "purpose" in props


# --- r28 B1: a profile asset separated from its field stats is a fabricated
# binding; the covered asset must bind the stats content actually read. ------ #


def _profile_ref(revision: str, stats: str) -> dict:
    return {
        "asset": {
            "id": "profile:allowed",
            "kind": "profile",
            "scope_ref": "tenant:test/project:p1",
            "revision": revision,
            "resolver": "local_content",
            "locator": revision,
            "digest": revision,
        },
        "dataset_ref": "table:orders",
        "field_stats_ref": stats,
        "method": "exact",
        "observed_at": "2026-11-05T00:00:00Z",
    }


def _stats(runtime, field_id: str) -> str:
    return runtime.content.put(
        {"fields": [{"field_id": field_id, "type_counts": {"number": 1}, "non_null_count": 1}]}
    )


def _infer(runtime, profile: dict, authorization: str):
    from dataagent_data.invoke import invoke

    return invoke(
        "infer_field_types", {"profile_ref": profile}, _ctx(authorization), runtime=runtime
    )


def test_enforce_denies_profile_stats_separated_from_the_asset(workspace, tmp_path):
    """r28 B1: the decision covers ``profile:allowed@<allowed>``, the payload
    points ``field_stats_ref`` at another object's content: denied before the
    handler reads anything, no forbidden field is returned."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    allowed = _stats(runtime, "amount")
    forbidden = _stats(runtime, "SECRET_FIELD")
    runtime.decisions.save_access(
        _decision("ad:profile", resource=f"profile:allowed@{allowed}").model_copy(
            update={"resource_ref": VersionedRef(id="profile:allowed", revision=allowed)}
        )
    )
    result = _infer(
        runtime, _profile_ref(allowed, forbidden), "ad:profile"
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "field_stats_ref" in result.issues[0].message
    assert result.data is None  # denied before any read: nothing leaked


def test_enforce_allows_profile_with_bound_stats(workspace, tmp_path):
    """r28 B1 control: stats equal to the asset revision is a covered read."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    allowed = _stats(runtime, "amount")
    runtime.decisions.save_access(
        _decision("ad:profile").model_copy(
            update={"resource_ref": VersionedRef(id="profile:allowed", revision="*")}
        )
    )
    result = _infer(runtime, _profile_ref(allowed, allowed), "ad:profile")
    assert result.status.value == "ok", result.issues
    assert [field.field_id for field in result.data.fields] == ["amount"]


def test_separated_stats_are_refused_even_with_the_recheck_off(workspace, tmp_path):
    """r28 B1 second line of defence: the handler itself refuses to read
    stats from an object other than the one the profile asset binds, so a
    disabled recheck cannot be used to smuggle the read through."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    allowed = _stats(runtime, "amount")
    forbidden = _stats(runtime, "SECRET_FIELD")
    result = _infer(runtime, _profile_ref(allowed, forbidden), "ad:any")
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.data is None


# --- r30 B1.1: a flat FileRef must be bound to the content it reads ---------- #


def _rebound_file_ref(workspace, allowed_name: str, secret_name: str) -> dict:
    allowed_digest = _file_digest(workspace, allowed_name)
    payload = (workspace / secret_name).read_bytes()
    secret_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    return {
        "id": "file:allowed",
        "kind": "file",
        "scope_ref": "tenant:test/project:p1",
        "revision": allowed_digest,  # the decision covers this content ...
        "resolver": "local_content",
        "locator": secret_name,  # ... but the payload reads another file
        "digest": secret_digest,
        "media_type": "text/csv",
        "filename": secret_name,
        "size_bytes": len(payload),
        "content_digest": secret_digest,
    }


def _file_digest(workspace, name: str) -> str:
    payload = (workspace / name).read_bytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def test_enforce_denies_file_rebound_to_a_covered_asset(workspace, tmp_path):
    """r30 B1.1: an authorized file asset may not read another file's bytes.

    The decision covers ``file:allowed@<allowed digest>`` while the FileRef
    (a flat AssetRef, no ``.asset`` wrapper) points ``locator`` /
    ``content_digest`` at a different file: denied before any read, the
    forbidden rows are never parsed.
    """

    (workspace / "secret.csv").write_bytes(b"name,amount\nSECRET_ROW,999\n")
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    runtime.decisions.save_access(
        _decision("ad:file").model_copy(
            update={
                "resource_ref": VersionedRef(
                    id="file:allowed", revision=_file_digest(workspace, "orders.csv")
                )
            }
        )
    )
    result = _call(
        runtime,
        {"file_ref": _rebound_file_ref(workspace, "orders.csv", "secret.csv")},
        _ctx("ad:file"),
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "content_digest" in result.issues[0].message
    assert result.data is None  # denied before any read: nothing leaked


def test_rebound_file_is_refused_even_with_the_recheck_off(workspace, tmp_path):
    """r30 B1.1 second line of defence: the handler refuses the rebound read.

    ``read_file_ref`` verifies the bytes against ``content_digest``; when the
    revision claims to be that content address, the two must agree, so a
    disabled recheck cannot smuggle the unauthorized file through.
    """

    (workspace / "secret.csv").write_bytes(b"name,amount\nSECRET_ROW,999\n")
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    result = _call(
        runtime,
        {"file_ref": _rebound_file_ref(workspace, "orders.csv", "secret.csv")},
        _ctx("ad:any"),
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.data is None


def test_registered_label_identity_cannot_read_other_bytes(workspace, tmp_path):
    """r30 B1.1: a free-form label revision is registry-bound, not unbound.

    ``rev:1`` is not a content address, so the binding runs through the
    immutable identity registry: once ``(file:policy, rev:1)`` is bound to a
    file's bytes, another file may not claim that identity.
    """

    (workspace / "c.csv").write_bytes(b"a\n1\n")
    (workspace / "d.csv").write_bytes(b"a\n2\n")
    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    owned = _file_ref(workspace, "d.csv")
    owned["id"] = "file:policy"
    owned["revision"] = "rev:1"
    first = _call(runtime, {"file_ref": owned}, _ctx("ad:any"))
    assert first.status.value == "ok", first.issues
    spoofed = _file_ref(workspace, "c.csv")
    spoofed["id"] = "file:policy"
    spoofed["revision"] = "rev:1"
    result = _call(runtime, {"file_ref": spoofed}, _ctx("ad:any"))
    assert result.status.value == "failed"
    assert "already bound to different bytes" in result.issues[0].message


# --- r30 B1.2: a self-declared resolver must not detach the content binding --- #


def _spoofed_table_ref(data_ref: str, *, revision: str) -> dict:
    return {
        "asset": {
            "id": "table:allowed",
            "kind": "table",
            "scope_ref": "tenant:test/project:p1",
            "revision": revision,
            "resolver": "workspace",  # caller-chosen: not a content resolver
            "locator": "table.json",
        },
        "schema_ref": "schema:allowed@r1",
        "data_ref": data_ref,
    }


def _table_payload(field_name: str) -> dict:
    return {
        "sheet": "",
        "columns": [
            {
                "name": field_name,
                "field_id": "c1",
                "source_path": "column:1",
                "value_type": "text",
            }
        ],
        "rows": [["SECRET"]],
        "row_meta": [],
        "merged_ranges": [],
        "source": {},
    }


def test_enforce_denies_resolver_spoofed_table_data_ref(workspace, tmp_path):
    """r30 B1.2: ``resolver="workspace"`` must not opt a table out of binding.

    The decision covers ``table:allowed@r1`` (a label revision the caller
    chose), the payload points ``data_ref`` at forbidden content: denied
    before any read.
    """

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    forbidden = runtime.content.put(_table_payload("SECRET_COLUMN"))
    runtime.decisions.save_access(
        _decision("ad:table").model_copy(
            update={"resource_ref": VersionedRef(id="table:allowed", revision="r1")}
        )
    )
    from dataagent_data.invoke import invoke

    result = invoke(
        "profile_table_structure",
        {"table_ref": _spoofed_table_ref(forbidden, revision="r1")},
        _ctx("ad:table"),
        runtime=runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "data_ref" in result.issues[0].message
    assert result.data is None


def test_resolver_spoofed_table_refused_even_with_the_recheck_off(
    workspace, tmp_path
):
    """r30 B1.2 second line of defence: ``load_table`` refuses unbound content."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    forbidden = runtime.content.put(_table_payload("SECRET_COLUMN"))
    from dataagent_data.invoke import invoke

    result = invoke(
        "profile_table_structure",
        {"table_ref": _spoofed_table_ref(forbidden, revision="r1")},
        _ctx("ad:any"),
        runtime=runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.data is None


def test_enforce_allows_workspace_table_bound_by_content(workspace, tmp_path):
    """r30 B1.2 control: bound by content, any resolver reads on."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    digest = runtime.content.put(_table_payload("amount"))
    runtime.decisions.save_access(
        _decision("ad:bound").model_copy(
            update={"resource_ref": VersionedRef(id="table:allowed", revision=digest)}
        )
    )
    from dataagent_data.invoke import invoke

    result = invoke(
        "profile_table_structure",
        {"table_ref": _spoofed_table_ref(digest, revision=digest)},
        _ctx("ad:bound"),
        runtime=runtime,
    )
    assert result.status.value == "ok", result.issues
    assert result.data.profile.asset.revision


def test_enforce_denies_resolver_spoofed_profile_stats(workspace, tmp_path):
    """r30 B1.2: the same spoof through a ProfileRef's stats pointer."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    forbidden = _stats(runtime, "SECRET_FIELD")
    runtime.decisions.save_access(
        _decision("ad:spoof").model_copy(
            update={"resource_ref": VersionedRef(id="profile:allowed", revision="r1")}
        )
    )
    spoofed = {
        "asset": {
            "id": "profile:allowed",
            "kind": "profile",
            "scope_ref": "tenant:test/project:p1",
            "revision": "r1",
            "resolver": "workspace",
            "locator": "profile.json",
        },
        "dataset_ref": "table:allowed",
        "field_stats_ref": forbidden,
        "method": "exact",
        "observed_at": "2026-11-05T00:00:00Z",
    }
    result = _infer(runtime, spoofed, "ad:spoof")
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "field_stats_ref" in result.issues[0].message
    assert result.data is None


def test_resolver_spoofed_profile_refused_even_with_the_recheck_off(
    workspace, tmp_path
):
    """r30 B1.2 second line of defence: the handler refuses unbound stats."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    forbidden = _stats(runtime, "SECRET_FIELD")
    spoofed = {
        "asset": {
            "id": "profile:allowed",
            "kind": "profile",
            "scope_ref": "tenant:test/project:p1",
            "revision": "r1",
            "resolver": "workspace",
            "locator": "profile.json",
        },
        "dataset_ref": "table:allowed",
        "field_stats_ref": forbidden,
        "method": "exact",
        "observed_at": "2026-11-05T00:00:00Z",
    }
    result = _infer(runtime, spoofed, "ad:any")
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.data is None


# --- r32-gov B1: DocumentRef blocks_ref must be the asset's bound content ---- #


def _document(runtime, marker: str):
    """A parsed document exactly as the product parse atoms build one."""

    from dataagent_contracts.core import DocumentRef
    from dataagent_data import helpers
    from dataagent_data.contracts.layer import DocumentContent, PageContent
    from dataagent_data.preparation.documents import register_document_blocks

    content = DocumentContent(
        pages=[PageContent(page=1, text=f"{marker}\nBody line for {marker}.")]
    )
    blocks_ref = runtime.content.put(content.model_dump(mode="json"))
    document = DocumentRef(
        asset=helpers.asset_for(
            blocks_ref, "document", "tenant:test/project:p1", media_type="application/pdf"
        ),
        original_ref=VersionedRef(id=f"file:{marker}", revision="sha256:" + "1" * 64),
        content_type="pdf_text",
        blocks_ref=blocks_ref,
        page_count=1,
    )
    register_document_blocks(runtime, document)
    return document


def _segment(runtime, document, authorization: str = "ad:any"):
    from dataagent_data.invoke import invoke

    return invoke(
        "segment_document",
        {"document_ref": document.model_dump(mode="json")},
        _ctx(authorization),
        runtime=runtime,
    )


def test_enforce_denies_document_blocks_rebound_to_a_covered_asset(
    workspace, tmp_path
):
    """r32-gov B1: a decision for the allowed document must bind the body read.

    The request keeps the allowed document's asset (what the decision
    covers) but swaps ``blocks_ref`` to another, already-parsed document:
    without the blocks binding the parse record alone would accept the
    triple and the handler would read the forbidden body.
    """

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    allowed = _document(runtime, "PUBLIC_DOC_HEADING")
    secret = _document(runtime, "SECRET_DOC_HEADING")
    runtime.decisions.save_access(
        _decision("ad:doc").model_copy(
            update={"resource_ref": VersionedRef(id="document", revision="*")}
        )
    )
    forged = allowed.model_copy(
        update={
            "original_ref": secret.original_ref,
            "blocks_ref": secret.blocks_ref,
            "page_count": secret.page_count,
        }
    )
    result = _segment(runtime, forged, "ad:doc")
    assert result.status.value == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "blocks_ref" in result.issues[0].message
    assert result.data is None


def test_document_blocks_rebound_refused_even_with_the_recheck_off(
    workspace, tmp_path
):
    """r32-gov B1 second line of defence: the handler refuses unbound bodies."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    allowed = _document(runtime, "PUBLIC_DOC_HEADING")
    secret = _document(runtime, "SECRET_DOC_HEADING")
    forged = allowed.model_copy(
        update={
            "original_ref": secret.original_ref,
            "blocks_ref": secret.blocks_ref,
            "page_count": secret.page_count,
        }
    )
    result = _segment(runtime, forged)
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert "not the document asset's content" in result.issues[0].message
    assert result.data is None


def test_enforce_allows_document_with_bound_blocks(workspace, tmp_path):
    """r32-gov B1 control: the unmodified allowed document still reads on."""

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="enforce"),
    )
    allowed = _document(runtime, "PUBLIC_DOC_HEADING")
    runtime.decisions.save_access(
        _decision("ad:doc2").model_copy(
            update={"resource_ref": VersionedRef(id="document", revision="*")}
        )
    )
    result = _segment(runtime, allowed, "ad:doc2")
    assert result.status.value == "ok", result.issues
    assert result.data.units


def test_unregistered_source_triple_is_still_refused(workspace, tmp_path):
    """The parse-record defence stays reachable behind the binding check.

    A document whose ``blocks_ref`` matches its own asset (so the binding
    passes) but whose ``original_ref`` was swapped never had its
    (source, blocks) triple recorded: still refused (reviewer F1).
    """

    runtime = create_runtime(
        workspace_root=workspace,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode="off"),
    )
    real = _document(runtime, "REAL_DOC")
    forged = real.model_copy(
        update={
            "original_ref": VersionedRef(
                id="file:NEVER_PARSED", revision="sha256:" + "2" * 64
            )
        }
    )
    result = _segment(runtime, forged)
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert "not bound to their source" in result.issues[0].message
