"""T11a / R1: S0 review X1 and X2 reproduction inputs, as assertions.

Rewritten from ``docs/research/dataagent-2026-11-03/08-governance-layer-build/
r41-repro/runtime/runtime_probe.py``:

- X1 (host authority): the probe's R6 forged ``subject_ref`` on the wire and
  the absent-subject recheck. Both must now be rejected: ``arguments.context``
  is a hint, host ``_meta`` keys are the iface ``session_id`` / ``call_id`` /
  ``turn``, and a missing subject fails closed instead of skipping the check.
- X2 (recheck scope): the probe's R1 typo in ``resource_fields`` and R2
  ``str`` / ``dict`` field types. All three used to register successfully and
  silently disable the access recheck; registration must reject them.

Control calls keep the probe's original shape: a decision for
``table:public`` must not authorize reading ``table:secret``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel

from dataagent_contracts.core import (
    AccessDecision,
    AccessOutcome,
    CallContext,
    VersionedRef,
)
from dataagent_runtime import (
    get_spec,
    invoke as shared_invoke,
    operation,
    reset_registry,
)
from dataagent_runtime.enforcement import EnforcementConfig, access_recheck
from dataagent_runtime.interfaces import mcp_server
from dataagent_runtime.policy.context import (
    ContextResolutionError,
    resolve_context,
    workspace_scope,
)
from dataagent_runtime.runtime import Runtime
from dataagent_runtime.types import CallMeta, ContextSource

FUTURE = "2030-01-01T00:00:00Z"
RESOURCE = VersionedRef(id="table:secret", revision="r1")
PUBLIC = VersionedRef(id="table:public", revision="r1")


class ReadInput(BaseModel):
    source: VersionedRef


class ReadOutput(BaseModel):
    value: str


class PlainInput(BaseModel):
    x: int = 0


class WhoOutput(BaseModel):
    subject: str
    purpose: str
    scope: str
    session: str
    call: str


@pytest.fixture(autouse=True)
def clean_host_channels(monkeypatch):
    """Keep every test's host channels empty unless the test sets them."""

    for key in (
        "DATAAGENT_HOST_SUBJECT_REF",
        "DATAAGENT_HOST_PURPOSE",
        "DATAAGENT_CONTEXT_RESOLVER",
        "DATAAGENT_AUTHORIZATION_REF",
        "AGENTCPM_TOOL_BROKER_SESSION",
        "AGENTCPM_TOOL_BROKER_TURN",
        "DATAAGENT_WORKSPACE",
        "DATAAGENT_SCOPE_REF",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture()
def ops():
    reset_registry()

    @operation(
        "T11A.1",
        input_model=ReadInput,
        output_model=ReadOutput,
        description="read one resource",
        resource_fields=("source",),
    )
    def t11a_read(input_obj, ctx, runtime):  # noqa: ANN001
        return ReadOutput(value=str(input_obj.source))

    @operation(
        "T11A.2",
        input_model=PlainInput,
        output_model=WhoOutput,
        description="report the executing identity",
    )
    def t11a_whoami(input_obj, ctx, runtime):  # noqa: ANN001
        return WhoOutput(
            subject=str(ctx.subject_ref),
            purpose=str(ctx.purpose),
            scope=ctx.scope_ref,
            session=str(ctx.kernel_session_id),
            call=str(ctx.kernel_call_id),
        )

    yield

    reset_registry()


def _runtime(
    tmp_path,
    *,
    host_subject_ref: str | None = None,
    host_purpose: str | None = None,
    mode: str = "enforce",
    kernel_guard_declared: bool = False,
) -> Runtime:
    return Runtime.create(
        workspace_root=tmp_path / "ws",
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(
            mode=mode, kernel_guard_declared=kernel_guard_declared
        ),
        host_subject_ref=host_subject_ref,
        host_purpose=host_purpose,
    )


def _decision(
    *,
    decision_id: str = "ad:1",
    subject: str = "user:alice",
    purpose: str = "report",
    resource: VersionedRef = RESOURCE,
    decision: AccessOutcome = AccessOutcome.allow,
) -> AccessDecision:
    return AccessDecision(
        decision_id=decision_id,
        policy_ref=VersionedRef(id="policy:tenant", revision="r1"),
        subject_ref=subject,
        resource_ref=resource,
        purpose=purpose,
        decision=decision,
        valid_until=FUTURE,
    )


def _forged_context(**overrides: Any) -> CallContext:
    values: dict[str, Any] = dict(
        request_id="req:forged",
        scope_ref="tenant:other",
        authorization_ref="ad:1",
        subject_ref="user:admin",
        purpose="exfil",
    )
    values.update(overrides)
    return CallContext(**values)


# --- X1: caller identity is never authority --------------------------------- #


def test_x1_forged_arguments_context_is_rejected(ops, tmp_path):
    """Probe R6: forged subject/scope used to authorize a decision for admin.

    With no host channel the resolver falls back to ``local-owner``, so a
    decision minted for ``user:admin`` no longer matches and the read is
    denied before the handler runs.
    """

    rt = _runtime(tmp_path)  # deliberately no host authority
    rt.decisions.save_access(_decision(subject="user:admin", purpose="exfil"))
    result = shared_invoke(
        "t11a_read",
        {"source": "table:secret@r1"},
        _forged_context(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "subject mismatch" in result.issues[0].message
    assert "local-owner" in result.issues[0].message


def test_x1_local_fallback_does_not_look_like_a_kernel_call(ops, tmp_path):
    """A synthetic local session must not trigger the guard-only kernel path."""

    rt = _runtime(tmp_path, host_subject_ref="user:alice", host_purpose="report",
                  kernel_guard_declared=True)
    rt.decisions.save_access(_decision(subject="user:bob"))
    result = shared_invoke(
        "t11a_read",
        {"source": "table:secret@r1"},
        _forged_context(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "subject mismatch" in result.issues[0].message


def test_x1_missing_subject_no_longer_skips_the_check(ops, tmp_path):
    """Probe R6 variant: a None subject used to make the recheck skip."""

    rt = _runtime(tmp_path)
    ctx = _forged_context(subject_ref=None)
    outcome = access_recheck(ctx, lambda ref: _decision(subject="user:bob"), [RESOURCE])
    assert not outcome.ok
    assert outcome.issue is not None
    assert "subject_ref is missing" in outcome.issue.message

    result = shared_invoke(
        "t11a_read",
        {"source": "table:secret@r1"},
        ctx,
        runtime=rt,
        resolver=lambda ref: _decision(subject="user:bob"),
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"


def test_x1_mcp_arguments_context_only_reports_local_owner(ops, tmp_path):
    """The MCP wire's ``arguments.context`` cannot set the handler's subject."""

    rt = _runtime(tmp_path)
    rt.decisions.save_access(_decision(subject="user:admin", purpose="exfil"))

    def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = mcp_server.handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            server_name="t11a",
            server_version="0.1.0",
            list_operations=lambda: [get_spec("t11a_read"), get_spec("t11a_whoami")],
            invoke=lambda op, payload, context: shared_invoke(
                op, payload, context, runtime=rt, resolver=rt.decisions.get_access
            ),
        )
        assert response is not None
        return response["result"]

    denied = call(
        "t11a_read",
        {
            "source": "table:secret@r1",
            "context": {
                "request_id": "req:args",
                "scope_ref": "tenant:other",
                "authorization_ref": "ad:1",
                "subject_ref": "user:admin",
                "purpose": "exfil",
            },
        },
    )
    body = denied["content"][0]["text"]
    assert denied["isError"]
    assert "da12.access_denied" in body

    allowed = call(
        "t11a_whoami",
        {
            "context": {
                "request_id": "req:args",
                "authorization_ref": "ad:1",
                "subject_ref": "user:admin",
                "purpose": "exfil",
            }
        },
    )
    assert not allowed["isError"]
    who = json.loads(allowed["content"][0]["text"])["data"]
    assert who["subject"].startswith("local-owner:")
    assert who["purpose"] == "local_owner"
    assert who["scope"].startswith("workspace:")


def test_x1_host_meta_callmeta_uses_iface_names(ops, tmp_path):
    """``_meta`` reads session_id/call_id/turn; invented keys are ignored."""

    rt = _runtime(tmp_path)
    resolved = resolve_context(
        host_meta={
            "session_id": "ks-1",
            "call_id": "kc-1",
            "turn": 3,
            # Invented spellings must not be read as CallMeta.
            "kernel_session_id": "evil-session",
            "kernel_call_id": "evil-call",
        },
        argument_context={"subject_ref": "user:admin", "purpose": "exfil"},
        runtime=rt,
        environ={},
    )
    assert resolved.source is ContextSource.HOST_META
    assert resolved.meta == CallMeta(session_id="ks-1", call_id="kc-1", turn=3)
    assert resolved.context.kernel_session_id == "ks-1"
    assert resolved.context.kernel_call_id == "kc-1"
    assert resolved.context.subject_ref.startswith("local-owner:")
    assert resolved.context.purpose == "local_owner"
    assert resolved.context.scope_ref == workspace_scope(rt.workspace_root)
    assert "subject_ref" in resolved.hints_ignored
    assert "purpose" in resolved.hints_ignored

    invented_only = resolve_context(
        host_meta={"kernel_session_id": "evil-session", "kernel_call_id": "evil-call"},
        runtime=rt,
        environ={},
    )
    assert invented_only.context.kernel_session_id != "evil-session"
    assert invented_only.context.kernel_call_id != "evil-call"


def test_x1_tool_schema_keeps_callmeta_out_and_context_optional(ops):
    """CallMeta is transport, not a tool parameter (iface doc comment)."""

    tool = mcp_server.tools_payload(lambda: [get_spec("t11a_whoami")])[0]
    schema = tool["inputSchema"]
    assert not {"session_id", "call_id", "turn"} & set(schema["properties"])
    assert "context" in schema["properties"]
    assert "context" not in schema.get("required", [])


def test_x1_mcp_meta_callmeta_reaches_the_handler(ops, tmp_path):
    """End to end: CallMeta from ``_meta`` is visible to a no-resource handler."""

    rt = _runtime(tmp_path)
    response = mcp_server.handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "t11a_whoami",
                "arguments": {"context": {"subject_ref": "user:admin"}},
                "_meta": {"session_id": "ks-9", "call_id": "kc-9", "turn": 4},
            },
        },
        server_name="t11a",
        server_version="0.1.0",
        list_operations=lambda: [get_spec("t11a_whoami")],
        invoke=lambda op, payload, context: shared_invoke(
            op, payload, context, runtime=rt, resolver=rt.decisions.get_access
        ),
    )
    assert response is not None
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["status"] == "ok"
    assert body["data"]["session"] == "ks-9"
    assert body["data"]["call"] == "kc-9"
    assert body["data"]["subject"].startswith("local-owner:")


def test_x1_host_meta_session_does_not_drop_runtime_authority(ops, tmp_path):
    """A CallMeta-only ``_meta`` must not hide the runtime's host authority."""

    rt = _runtime(tmp_path, host_subject_ref="user:alice", host_purpose="report")
    rt.decisions.save_access(_decision(subject="user:alice", purpose="report"))
    response = mcp_server.handle(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "t11a_whoami",
                "arguments": {},
                "_meta": {"session_id": "ks-7", "call_id": "kc-7", "turn": 2},
            },
        },
        server_name="t11a",
        server_version="0.1.0",
        list_operations=lambda: [get_spec("t11a_whoami")],
        invoke=lambda op, payload, context: shared_invoke(
            op, payload, context, runtime=rt, resolver=rt.decisions.get_access
        ),
    )
    assert response is not None
    body = json.loads(response["result"]["content"][0]["text"])
    assert body["status"] == "ok"
    assert body["data"]["subject"] == "user:alice"
    assert body["data"]["purpose"] == "report"
    assert body["data"]["session"] == "ks-7"
    assert body["data"]["call"] == "kc-7"


def test_x1_host_environment_wins_over_arguments(ops, tmp_path, monkeypatch):
    """The host environment is the second channel; arguments never override it."""

    monkeypatch.setenv("DATAAGENT_HOST_SUBJECT_REF", "user:alice")
    monkeypatch.setenv("DATAAGENT_HOST_PURPOSE", "report")
    rt = _runtime(tmp_path)  # reads the injected environment in create()
    rt.decisions.save_access(_decision(subject="user:alice", purpose="report"))
    result = shared_invoke(
        "t11a_read",
        {"source": "table:secret@r1"},
        _forged_context(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "ok", result.issues

    who = shared_invoke(
        "t11a_whoami",
        {},
        _forged_context(),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert who.status == "ok"
    assert who.data.subject == "user:alice"
    assert who.data.purpose == "report"


def test_x1_scope_is_workspace_sha_and_hint_scope_is_ignored(ops, tmp_path):
    rt = _runtime(tmp_path)
    resolved = resolve_context(
        argument_context=_forged_context(scope_ref="tenant:other"),
        runtime=rt,
        environ={},
    )
    expected = workspace_scope(rt.workspace_root)
    assert resolved.context.scope_ref == expected
    assert expected.startswith("workspace:")
    assert len(expected.split(":", 1)[1]) == 24
    assert "scope_ref" in resolved.hints_ignored


def test_x1_legacy_switch_restores_old_hint_precedence(ops):
    """One-release rollback: legacy keeps the caller context as before."""

    ctx = _forged_context()
    resolved = resolve_context(
        argument_context=ctx,
        environ={"DATAAGENT_CONTEXT_RESOLVER": "legacy"},
    )
    assert resolved.source is ContextSource.LEGACY
    assert resolved.context.subject_ref == "user:admin"
    assert resolved.context.purpose == "exfil"
    assert resolved.context.scope_ref == "tenant:other"


def test_legacy_without_context_still_requires_it(ops):
    with pytest.raises(ContextResolutionError, match="CallContext is required"):
        resolve_context(environ={"DATAAGENT_CONTEXT_RESOLVER": "legacy"})


def test_x1_legacy_unified_context_is_synthesized(ops, tmp_path):
    """The old unified CLI had no context input; legacy keeps that shape."""

    resolved = resolve_context(
        runtime=_runtime(tmp_path),
        environ={"DATAAGENT_CONTEXT_RESOLVER": "legacy"},
    )
    assert resolved.source is ContextSource.LEGACY
    assert resolved.context.scope_ref == "tenant:local"
    assert resolved.context.authorization_ref == "cli:unauthorized"


def test_x1_legacy_invoke_keeps_the_old_scope(ops, tmp_path):
    """The rollback switch also keeps ``tenant:*`` until it is removed."""

    rt = _runtime(tmp_path)
    resolved = resolve_context(
        argument_context=_forged_context(),
        runtime=rt,
        environ={"DATAAGENT_CONTEXT_RESOLVER": "legacy"},
    )
    result = shared_invoke("t11a_whoami", {}, resolved, runtime=rt)
    assert result.status == "ok"
    assert result.data.scope == "tenant:other"
    assert result.data.subject == "user:admin"


def test_x1_turn_must_be_an_unsigned_integer(ops, tmp_path):
    for bad in (True, 1.5, "-1", "1.0"):
        with pytest.raises(ContextResolutionError, match="unsigned integer"):
            resolve_context(host_meta={"turn": bad}, runtime=_runtime(tmp_path), environ={})


# --- X2: resource_fields declarations are validated at registration -------- #


class VersionedInput(BaseModel):
    source: VersionedRef


class StrInput(BaseModel):
    source: str


class DictInput(BaseModel):
    sources: dict[str, VersionedRef]


class ListDictInput(BaseModel):
    sources: list[dict]


class AnyInput(BaseModel):
    source: Any


class OpaqueModel(BaseModel):
    value: str


class OpaqueInput(BaseModel):
    source: OpaqueModel


class IdRevisionOnly(BaseModel):
    id: str
    revision: str


class SetInput(BaseModel):
    sources: set[VersionedRef]


class IdRevisionInput(BaseModel):
    source: IdRevisionOnly


class AssetStrInput(BaseModel):
    asset: str
    payload: str


class AssetStrWrapper(BaseModel):
    source: AssetStrInput


def test_x2_flat_asset_without_kind_is_rejected(ops):
    """``_to_versioned_ref`` needs id/kind/revision; id+revision alone skips."""

    with pytest.raises(RuntimeError, match="does not carry"):

        @operation(
            "T11A.X2.8",
            input_model=IdRevisionInput,
            output_model=ReadOutput,
            resource_fields=("source",),
        )
        def x2_id_only(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=input_obj.source.id)


def test_x2_set_resource_field_is_rejected(ops):
    """The recheck iterates list/tuple only; a set would silently skip."""

    with pytest.raises(RuntimeError, match="does not carry"):

        @operation(
            "T11A.X2.9",
            input_model=SetInput,
            output_model=ReadOutput,
            resource_fields=("sources",),
        )
        def x2_set(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=str(input_obj.sources))


def test_x2_wrapper_with_non_asset_asset_is_rejected(ops):
    with pytest.raises(RuntimeError, match="AssetStrInput"):

        @operation(
            "T11A.X2.10",
            input_model=AssetStrWrapper,
            output_model=ReadOutput,
            resource_fields=("source",),
        )
        def x2_asset_str(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=input_obj.source.payload)


def test_x2_misspelled_resource_field_is_rejected_at_registration(ops):
    """Probe R1: ``resource_fields=('sourcee',)`` used to register and skip."""

    with pytest.raises(RuntimeError, match="sourcee"):

        @operation(
            "T11A.X2.1",
            input_model=VersionedInput,
            output_model=ReadOutput,
            resource_fields=("sourcee",),
        )
        def x2_typo(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=str(input_obj.source))


def test_x2_plain_string_resource_field_is_rejected(ops):
    """Probe R2: a ``str`` field silently produced no VersionedRef."""

    with pytest.raises(RuntimeError, match="plain str"):

        @operation(
            "T11A.X2.2",
            input_model=StrInput,
            output_model=ReadOutput,
            resource_fields=("source",),
        )
        def x2_str(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=input_obj.source)


def test_x2_dict_container_resource_field_is_rejected(ops):
    """Probe R2: a ``dict[str, VersionedRef]`` container silently skipped."""

    with pytest.raises(RuntimeError, match="dict container"):

        @operation(
            "T11A.X2.3",
            input_model=DictInput,
            output_model=ReadOutput,
            resource_fields=("sources",),
        )
        def x2_dict(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=",".join(str(v) for v in input_obj.sources.values()))


def test_x2_list_of_dict_resource_field_is_rejected(ops):
    with pytest.raises(RuntimeError, match="resource field"):

        @operation(
            "T11A.X2.4",
            input_model=ListDictInput,
            output_model=ReadOutput,
            resource_fields=("sources",),
        )
        def x2_list_dict(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=str(input_obj.sources))


def test_x2_any_resource_field_is_rejected(ops):
    """``Any`` is the duck-typed escape hatch X2 allowed; it is unverifiable."""

    with pytest.raises(RuntimeError, match="Any"):

        @operation(
            "T11A.X2.5",
            input_model=AnyInput,
            output_model=ReadOutput,
            resource_fields=("source",),
        )
        def x2_any(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=str(input_obj.source))


def test_x2_opaque_model_resource_field_is_rejected(ops):
    with pytest.raises(RuntimeError, match="does not carry"):

        @operation(
            "T11A.X2.6",
            input_model=OpaqueInput,
            output_model=ReadOutput,
            resource_fields=("source",),
        )
        def x2_opaque(input_obj, ctx, runtime):  # noqa: ANN001
            return ReadOutput(value=input_obj.source.value)


def test_x2_valid_declarations_still_register(ops):
    """Control: VersionedRef and a sequence of them remain valid declarations."""

    class GoodInput(BaseModel):
        source: VersionedRef
        sources: list[VersionedRef]
        tuple_sources: tuple[VersionedRef, ...]

    @operation(
        "T11A.X2.7",
        input_model=GoodInput,
        output_model=ReadOutput,
        resource_fields=("source", "sources", "tuple_sources"),
    )
    def x2_good(input_obj, ctx, runtime):  # noqa: ANN001
        return ReadOutput(value=str(input_obj.source))

    assert get_spec("x2_good") is not None
    assert get_spec("x2_good").resource_fields == (
        "source",
        "sources",
        "tuple_sources",
    )


def test_x2_control_uncovered_resource_is_denied(ops, tmp_path):
    """The probe's control: a decision for table:public never covers secret."""

    rt = _runtime(tmp_path, host_subject_ref="user:alice", host_purpose="report")
    rt.decisions.save_access(_decision(resource=PUBLIC))
    result = shared_invoke(
        "t11a_read",
        {"source": "table:secret@r1"},
        CallContext(
            request_id="req:control",
            scope_ref="tenant:demo",
            authorization_ref="ad:1",
            subject_ref="user:alice",
            purpose="report",
        ),
        runtime=rt,
        resolver=rt.decisions.get_access,
    )
    assert result.status == "failed"
    assert result.issues[0].code == "da12.access_denied"
    assert "does not cover input resource" in result.issues[0].message
