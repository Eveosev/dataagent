from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    CallContext,
    VersionedRef,
)
from dataagent_runtime import invoke, operation, reset_registry
from dataagent_runtime.enforcement import EnforcementConfig

RESOURCE = VersionedRef(id="table:orders", revision="r1")


class EchoInput(BaseModel):
    payload: str
    source: VersionedRef


class EchoOutput(BaseModel):
    payload: str


@pytest.fixture()
def registered():
    reset_registry()

    @operation(
        "TEST.1.1",
        input_model=EchoInput,
        output_model=EchoOutput,
        description="echo",
        resource_fields=("source",),
    )
    def echo(input_obj, ctx, runtime):  # noqa: ANN001
        return EchoOutput(payload=input_obj.payload)

    @operation(
        "TEST.1.2",
        input_model=TableInput,
        output_model=EchoOutput,
        description="table echo",
        resource_fields=("table",),
    )
    def table_echo(input_obj, ctx, runtime):  # noqa: ANN001
        return EchoOutput(payload=input_obj.table.data_ref)

    @operation(
        "TEST.1.3",
        input_model=ProfileInput,
        output_model=EchoOutput,
        description="profile echo",
        resource_fields=("profile_ref",),
    )
    def profile_echo(input_obj, ctx, runtime):  # noqa: ANN001
        return EchoOutput(payload=input_obj.profile_ref.field_stats_ref)

    @operation(
        "TEST.1.4",
        input_model=FileInput,
        output_model=EchoOutput,
        description="file echo",
        resource_fields=("file_ref",),
    )
    def file_echo(input_obj, ctx, runtime):  # noqa: ANN001
        return EchoOutput(payload=input_obj.file_ref.content_digest)

    @operation(
        "TEST.1.5",
        input_model=DocumentInput,
        output_model=EchoOutput,
        description="document echo",
        resource_fields=("document_ref",),
    )
    def document_echo(input_obj, ctx, runtime):  # noqa: ANN001
        return EchoOutput(payload=input_obj.document_ref.blocks_ref)

    yield
    reset_registry()


def _runtime(enforcement: EnforcementConfig, tmp_path):
    from dataagent_runtime.runtime import Runtime

    return Runtime.create(
        workspace_root=tmp_path, data_root=tmp_path / "data", enforcement=enforcement
    )


def _ctx():
    return CallContext(
        request_id="req:1",
        scope_ref="tenant:demo",
        authorization_ref="ad:1",
        subject_ref="user:alice",
        purpose="report",
    )


def _decision(**kwargs):
    base = dict(
        decision_id="ad:1",
        policy_ref=VersionedRef(id="policy:tenant", revision="r1"),
        subject_ref="user:alice",
        resource_ref=RESOURCE,
        purpose="report",
        decision=AccessOutcome.allow,
        valid_until="2030-01-01T00:00:00Z",
    )
    base.update(kwargs)
    return AccessDecision(**base)


def test_invoke_enforce_allows_with_covering_decision(registered, tmp_path):
    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(_decision())
    result = invoke(
        "echo",
        {"payload": "hi", "source": "table:orders@r1"},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok"
    assert result.data.payload == "hi"


def test_invoke_warn_proceeds_with_warning(registered, tmp_path):
    rt = _runtime(EnforcementConfig(mode="warn"), tmp_path)
    result = invoke(
        "echo",
        {"payload": "hi", "source": "table:orders@r1"},
        _ctx(),
        runtime=rt,
        resolver=lambda ref: None,
    )
    assert result.status == "ok"
    assert any(i.code == "da12.access_denied" for i in result.issues)


def test_invoke_off_skips_recheck(registered, tmp_path):
    rt = _runtime(EnforcementConfig(mode="off"), tmp_path)
    result = invoke(
        "echo",
        {"payload": "hi", "source": "table:orders@r1"},
        _ctx(),
        runtime=rt,
        resolver=lambda ref: None,
    )
    assert result.status == "ok"
    assert result.issues == []


def test_invoke_without_resolver_fails_closed_for_resource_reads(registered, tmp_path):
    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    result = invoke("echo", {"payload": "hi", "source": "table:orders@r1"}, _ctx(), runtime=rt)
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"


def test_invoke_unknown_operation(registered, tmp_path):
    rt = _runtime(EnforcementConfig(mode="off"), tmp_path)
    result = invoke("nope", {}, _ctx(), runtime=rt)
    assert result.status == "failed"
    assert result.issues[0].code == "unsupported"


def test_invoke_invalid_input(registered, tmp_path):
    rt = _runtime(EnforcementConfig(mode="off"), tmp_path)
    result = invoke("echo", {"payload": ""}, _ctx(), runtime=rt)
    assert result.status == "failed"
    assert result.issues[0].code == "invalid_input"


# --- r24: asset-to-content closure binding (B1) and host authority (B7) -------- #


from dataagent_contracts.core import AssetRef, TableRef


class TableInput(BaseModel):
    table: TableRef


def _table_ref(data_ref: str, *, digest: str | None, revision: str) -> TableRef:
    asset = AssetRef(
        id="table:orders",
        kind="table",
        scope_ref="tenant:demo",
        revision=revision,
        resolver="local_content",
        locator=data_ref,
        digest=digest,
    )
    return TableRef(
        asset=asset,
        schema_ref=VersionedRef(id="schema:orders", revision="r1"),
        data_ref=data_ref,
    )


def test_invoke_enforce_denies_content_rebound_to_a_covered_asset(registered, tmp_path):
    """B1b: a decision for table:orders must bind the content actually read.

    The payload claims ``table:orders`` but points at another object's
    content digest: the recheck fails closed before the handler runs.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(_decision())
    result = invoke(
        "table_echo",
        {"table": _table_ref("sha256:secret", digest="sha256:secret", revision="sha256:bound")},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "resource closure" in result.issues[0].message


def test_invoke_enforce_denies_revision_that_is_not_the_content(registered, tmp_path):
    """B1b: an asset revision that is not the content digest binds nothing."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(_decision())
    result = invoke(
        "table_echo",
        {"table": _table_ref("sha256:bound", digest="sha256:bound", revision="r1")},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"


def test_invoke_enforce_accepts_revision_only_binding(registered, tmp_path):
    """B1b: without an explicit digest, the revision alone names the content.

    The shared table codec's asset spelling carries ``revision=<digest>``
    and no ``digest`` field; the decision binds that revision, so the
    closure is verifiable and the read proceeds.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="table", revision="*"))
    )
    result = invoke(
        "table_echo",
        {"table": _table_ref("sha256:bound", digest=None, revision="sha256:bound")},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues


def test_host_authority_overrides_the_caller_identity(registered, tmp_path):
    """B7: the trusted host subject wins over the wire context."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.host_subject_ref = "user:alice"
    rt.host_purpose = "report"
    rt.decisions.save_access(_decision())  # minted for alice/report
    forged = _ctx().model_copy(update={"subject_ref": "user:mallory", "purpose": "exfil"})
    result = invoke(
        "echo",
        {"payload": "hi", "source": "table:orders@r1"},
        forged,
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues


def test_host_authority_env_fallback(tmp_path, monkeypatch):
    """B7: the host injects its authority through the environment."""

    from dataagent_runtime.runtime import Runtime

    monkeypatch.setenv("DATAAGENT_HOST_SUBJECT_REF", "user:host")
    monkeypatch.setenv("DATAAGENT_HOST_PURPOSE", "ops")
    rt = Runtime.create(workspace_root=tmp_path, data_root=tmp_path / "data")
    assert rt.host_subject_ref == "user:host"
    assert rt.host_purpose == "ops"


def test_meta_context_beats_arguments_context():
    """B7 (MCP): the server-supplied ``_meta`` context is authoritative."""

    from dataagent_runtime.interfaces.mcp_server import _context

    meta = _context(
        {"_meta": {"context": {"request_id": "req:meta", "scope_ref": "tenant:demo",
                               "authorization_ref": "ad:1", "subject_ref": "user:mallory"}}},
        {"context": {"request_id": "req:args", "scope_ref": "tenant:demo",
                     "authorization_ref": "ad:1", "subject_ref": "user:alice"}},
    )
    assert meta["request_id"] == "req:meta"
    assert meta["subject_ref"] == "user:mallory"
    fallback = _context(
        {},
        {"context": {"request_id": "req:args", "scope_ref": "tenant:demo",
                     "authorization_ref": "ad:1", "subject_ref": "user:alice"}},
    )
    assert fallback["request_id"] == "req:args"


# --- r28 B1: profile field_stats_ref must be the bound asset's content ------- #


class ProfileInput(BaseModel):
    profile_ref: Any


def _profile(field_stats_ref: str, *, revision: str, digest: str | None = None):
    """A ProfileRef-shaped payload (duck-typed; contracts differ per layer)."""

    class _Asset:
        def __init__(self) -> None:
            self.id = "profile:allowed"
            self.kind = "profile"
            self.revision = revision
            self.resolver = "local_content"
            self.locator = revision
            self.digest = digest

    class _Profile:
        def __init__(self) -> None:
            self.asset = _Asset()
            self.dataset_ref = "table:allowed"
            self.field_stats_ref = field_stats_ref

    return _Profile()


def test_invoke_enforce_denies_profile_stats_rebound_to_a_covered_asset(
    registered, tmp_path
):
    """r28 B1: a decision for the profile asset must bind the stats read.

    The asset names the allowed stats revision (what the decision covers)
    while ``field_stats_ref`` points at another object's content: the
    closure cannot be verified, so the recheck fails closed before the
    handler reads anything.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="profile:allowed", revision="sha256:allowed"))
    )
    result = invoke(
        "profile_echo",
        {"profile_ref": _profile("sha256:forbidden", revision="sha256:allowed")},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "field_stats_ref" in result.issues[0].message
    assert "resource closure" in result.issues[0].message


def test_invoke_enforce_accepts_profile_with_bound_stats(registered, tmp_path):
    """r28 B1 control: stats equal to the asset revision is a verifiable read."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="profile:allowed", revision="*"))
    )
    result = invoke(
        "profile_echo",
        {"profile_ref": _profile("sha256:allowed", revision="sha256:allowed")},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues


# --- r30 B1.1: flat AssetRef (FileRef) closure binding ----------------------- #


from dataagent_contracts.core import FileRef

# Full-shape content addresses: a revision binds content only when it claims
# to *be* one (``sha256:<64 hex>``).
_ALLOWED = "sha256:" + "a" * 64
_FORBIDDEN = "sha256:" + "b" * 64


class FileInput(BaseModel):
    file_ref: FileRef


def _file_ref(
    *,
    revision: str,
    content_digest: str,
    digest: str | None = None,
    resolver: str = "local_content",
    locator: str | None = None,
) -> FileRef:
    return FileRef(
        id="file:allowed",
        kind="file",
        scope_ref="tenant:demo",
        revision=revision,
        resolver=resolver,
        locator=locator if locator is not None else content_digest,
        digest=digest,
        media_type="text/csv",
        content_digest=content_digest,
    )


def test_invoke_enforce_denies_file_rebound_to_a_covered_asset(registered, tmp_path):
    """r30 B1.1: a flat FileRef must not skip the resource closure.

    The decision covers ``file:allowed@<allowed digest>`` while the payload's
    ``content_digest``/``digest`` point at another object's bytes: without the
    flat-asset branch the closure checked only wrapper refs (``.asset``) and
    the handler would read the unauthorized file. Denied before any read.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="file:allowed", revision=_ALLOWED))
    )
    result = invoke(
        "file_echo",
        {
            "file_ref": _file_ref(
                revision=_ALLOWED, content_digest=_FORBIDDEN
            )
        },
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "content_digest" in result.issues[0].message
    assert "resource closure" in result.issues[0].message
    assert result.data is None


def test_invoke_enforce_denies_file_rebound_via_locator(registered, tmp_path):
    """r30 B1.1: a content-resolved asset's locator is a content address.

    Every digest claim is self-consistent here, but the locator names another
    object's location: the content address the asset resolves through must
    be the one the revision names.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="file:allowed", revision=_ALLOWED))
    )
    result = invoke(
        "file_echo",
        {
            "file_ref": _file_ref(
                revision=_ALLOWED,
                content_digest=_ALLOWED,
                digest=_ALLOWED,
                locator="secret.csv",
            )
        },
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "locator" in result.issues[0].message


def test_invoke_enforce_accepts_file_bound_to_the_covered_revision(registered, tmp_path):
    """r30 B1.1 control: a FileRef bound to the covered content reads on."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="file:allowed", revision=_ALLOWED))
    )
    result = invoke(
        "file_echo",
        {
            "file_ref": _file_ref(
                revision=_ALLOWED, content_digest=_ALLOWED
            )
        },
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues


def test_invoke_enforce_accepts_label_revision_file_identity(registered, tmp_path):
    """r30 B1.1: a free-form label revision is an identity-registry claim.

    ``rev:1`` is not a content address, so the shared runtime has nothing to
    compare the content against; the data layer binds such an identity to its
    bytes through its immutable registry (``register_file_ref``) instead.
    The runtime therefore does not deny the closure for a label revision —
    only for a revision that claims to *be* content.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="file:allowed", revision="rev:1"))
    )
    result = invoke(
        "file_echo",
        {
            "file_ref": _file_ref(
                revision="rev:1", content_digest=_FORBIDDEN, resolver="workspace"
            )
        },
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues


# --- r30 B1.2: a self-declared resolver must not opt out of the binding ------ #


def test_invoke_enforce_denies_resolver_spoofed_table_binding(registered, tmp_path):
    """r30 B1.2: ``resolver`` is caller-chosen, so it cannot widen access.

    A TableRef claims ``resolver="workspace"`` (so the revision is a label,
    not a content address) while ``data_ref`` points at forbidden content:
    the binding still has to hold — a non-content resolver is accepted
    exactly when the asset is bound to the read content by its fields.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="table:orders", revision="r1"))
    )
    spoofed = _table_ref("sha256:forbidden", digest=None, revision="r1")
    spoofed = spoofed.model_copy(
        update={
            "asset": spoofed.asset.model_copy(update={"resolver": "workspace"})
        }
    )
    result = invoke(
        "table_echo",
        {"table": spoofed},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "data_ref" in result.issues[0].message
    assert "resource closure" in result.issues[0].message


def test_invoke_enforce_accepts_workspace_table_bound_by_content(registered, tmp_path):
    """r30 B1.2 control: a workspace-resolved table bound by content reads on."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="table:orders", revision="sha256:bound"))
    )
    bound = _table_ref("sha256:bound", digest=None, revision="sha256:bound")
    bound = bound.model_copy(
        update={"asset": bound.asset.model_copy(update={"resolver": "workspace"})}
    )
    result = invoke(
        "table_echo",
        {"table": bound},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues


def test_invoke_enforce_denies_resolver_spoofed_profile_stats(registered, tmp_path):
    """r30 B1.2: the same spoof through a ProfileRef's stats pointer."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="profile:allowed", revision="r1"))
    )
    spoofed = _profile("sha256:forbidden", revision="r1")
    spoofed.asset.resolver = "workspace"  # type: ignore[attr-defined]
    result = invoke(
        "profile_echo",
        {"profile_ref": spoofed},
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "field_stats_ref" in result.issues[0].message


# --- r32-gov B1: DocumentRef blocks_ref must be the bound asset's content ---- #


from dataagent_contracts.core import DocumentRef


class DocumentInput(BaseModel):
    document_ref: DocumentRef


def _document_ref(
    blocks_ref: str, *, revision: str, digest: str | None = None
) -> DocumentRef:
    return DocumentRef(
        asset=AssetRef(
            id="document:allowed",
            kind="document",
            scope_ref="tenant:demo",
            revision=revision,
            resolver="local_content",
            locator=revision,
            digest=digest,
        ),
        original_ref=VersionedRef(id="file:allowed", revision="sha256:" + "c" * 64),
        content_type="pdf_text",
        blocks_ref=blocks_ref,
        page_count=1,
    )


def test_invoke_enforce_denies_document_blocks_rebound_to_a_covered_asset(
    registered, tmp_path
):
    """r32-gov B1: a decision for the document asset must bind the body read.

    The asset names the allowed blocks revision (what the decision covers)
    while ``blocks_ref`` points at another, already-parsed document's body:
    the parse record alone cannot tell which asset the body belongs to, so
    the closure must fail closed before the handler reads anything.
    """

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(
            resource_ref=VersionedRef(id="document:allowed", revision="sha256:allowed")
        )
    )
    result = invoke(
        "document_echo",
        {
            "document_ref": _document_ref(
                "sha256:forbidden", revision="sha256:allowed", digest="sha256:allowed"
            )
        },
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "blocks_ref" in result.issues[0].message
    assert "resource closure" in result.issues[0].message


def test_invoke_enforce_accepts_document_with_bound_blocks(registered, tmp_path):
    """r32-gov B1 control: blocks equal to the asset revision read on."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(resource_ref=VersionedRef(id="document:allowed", revision="*"))
    )
    result = invoke(
        "document_echo",
        {
            "document_ref": _document_ref(
                "sha256:allowed", revision="sha256:allowed", digest=None
            )
        },
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues


def test_invoke_enforce_denies_document_blocks_rebound_via_digest_only(
    registered, tmp_path
):
    """r32-gov B1: a digest that disagrees with the blocks binds nothing."""

    rt = _runtime(EnforcementConfig(mode="enforce"), tmp_path)
    rt.decisions.save_access(
        _decision(
            resource_ref=VersionedRef(id="document:allowed", revision="sha256:allowed")
        )
    )
    result = invoke(
        "document_echo",
        {
            "document_ref": _document_ref(
                "sha256:allowed", revision="sha256:allowed", digest="sha256:other"
            )
        },
        _ctx(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "blocks_ref" in result.issues[0].message
