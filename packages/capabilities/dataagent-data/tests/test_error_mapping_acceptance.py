"""W2.5: client input errors must map to invalid_input, not execution_unknown."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from conftest import call


def test_invalid_trace_event_type_is_invalid_input(runtime, ctx):
    result = call(
        "append_task_event",
        {
            "task_ref": "task:e@r1",
            "event_id": "evt:bad",
            "event_type": "not_a_trace_event",
            "actor_ref": "agent:1",
            "payload": {},
        },
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_invalid_rule_combination_is_invalid_input(runtime, ctx):
    anchor = {
        "source_ref": "file:policy",
        "source_revision": "sha256:aa11",
        "selector": {"kind": "pdf_text_span", "page": 1, "char_start": 0, "char_end": 5},
    }
    result = call(
        "define_business_rules",
        {
            "statement": "x",
            "proposal": {
                "conditions": [
                    {"condition_id": "c1", "text": "t", "anchors": [anchor]}
                ],
                "combination": "all(c9)",
            },
        },
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


class _BoomInput(BaseModel):
    pass


def test_unexpected_exception_maps_to_execution_unknown(runtime, ctx, monkeypatch):
    """W6.2 black-box gap: unexpected handler errors stay non-retryable."""

    import importlib

    invoke_module = importlib.import_module("dataagent_runtime.invoke")
    from dataagent_data.registry import OperationSpec

    def boom(data, context, rt):
        raise RuntimeError("boom")

    spec = OperationSpec(
        operation="boom",
        capability_id="DA99.0.0",
        source_file="src/dataagent_data/boom.py",
        input_model=_BoomInput,
        output_model=_BoomInput,
        handler=boom,
    )
    monkeypatch.setattr(
        invoke_module, "get_spec", lambda name: spec if name == "boom" else None
    )
    result = invoke_module.invoke("boom", {}, ctx, runtime=runtime)
    assert result.status.value == "failed"
    assert result.issues[0].code == "execution_unknown"
    assert result.issues[0].retryable is False


def test_pdf_library_failure_maps_to_execution_unknown(runtime, ctx, workspace, monkeypatch):
    import pdfplumber

    from conftest import file_ref, write_file

    write_file(workspace, "doc.pdf", b"%PDF-1.4\n%fake\n")

    def boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("pdfplumber exploded")

    monkeypatch.setattr(pdfplumber, "open", boom)
    result = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "doc.pdf")},
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "execution_unknown"


def test_corrupt_pdf_maps_to_invalid_input(runtime, ctx, workspace):
    from conftest import file_ref, write_file

    write_file(workspace, "broken.pdf", b"this is not a pdf at all")
    result = call(
        "parse_text_pdf",
        {"file_ref": file_ref(workspace, "broken.pdf")},
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def _decidability_call(runtime, ctx, requirement_ref: str, *, expected_revision=None):
    context = ctx
    if expected_revision is not None:
        context = ctx.model_copy(update={"expected_revision": expected_revision})
    # Persist the cited evidence so the auto verdict has a resolvable basis
    # (round 17: fabricated basis refs downgrade to needs_evidence).
    runtime.versions.save("evidence", "ev:1", {"note": "test evidence fixture"})
    return call(
        "assess_automatic_decidability",
        {
            "requirement_ref": requirement_ref,
            "statement": "check amount",
            "proposal": {
                "verdict": "auto",
                "basis_refs": ["ev:1"],
                "dependency_refs": [],
                "unknowns": [],
                "next_actions": [],
            },
        },
        context,
        runtime,
    )


@pytest.mark.parametrize(
    "requirement_ref", ["a@b@c", "@", "a@", "@b", "a b@r1", "   "]
)
def test_malformed_requirement_ref_is_invalid_input(runtime, ctx, requirement_ref):
    """Round 4.2 P2: a malformed caller ref is input, not execution_unknown."""

    result = _decidability_call(runtime, ctx, requirement_ref)
    assert result.status.value == "failed", requirement_ref
    assert result.issues[0].code == "invalid_input", requirement_ref
    assert result.issues[0].target == "requirement_ref", requirement_ref


def test_blank_expected_revision_is_invalid_input(runtime, ctx):
    result = _decidability_call(runtime, ctx, "rule:1", expected_revision="")
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.issues[0].target == "context.expected_revision"


def test_well_formed_requirement_refs_still_work(runtime, ctx):
    inline = _decidability_call(runtime, ctx, "rule:1@r1")
    assert inline.status.value == "ok", inline.issues
    assert str(inline.data.target_ref) == "rule:1@r1"

    from_context = _decidability_call(runtime, ctx, "rule:1", expected_revision="r1")
    assert from_context.status.value == "ok", from_context.issues
    assert str(from_context.data.target_ref) == "rule:1@r1"

    missing = _decidability_call(runtime, ctx, "rule:1")
    assert missing.status.value == "needs_input"
    assert missing.issues[0].code == "da03.requirement_revision_required"
