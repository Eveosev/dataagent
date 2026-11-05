from __future__ import annotations

from conftest import build_pdf, call, file_ref


def parsed_pdf(runtime, ctx, workspace):
    build_pdf(
        workspace / "policy.pdf",
        [
            "1. Scope",
            "This policy applies to all expense claims.",
            "2. Approval",
            "Claims above 5000 CNY require department head approval.",
            "Amount: 5800 CNY",
        ],
    )
    result = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    assert result.status.value == "ok", result.issues
    content = runtime.content.get_json(result.data.document.blocks_ref)
    return result.data.document, content


def test_segment_document_with_anchors(runtime, ctx, workspace):
    document, content = parsed_pdf(runtime, ctx, workspace)
    result = call("segment_document", {"document_ref": document}, ctx, runtime)
    assert result.status.value == "ok", result.issues
    assert len(result.data.units) >= 2
    for unit in result.data.units:
        assert unit.anchors
        anchor = unit.anchors[0]
        assert anchor.selector.kind == "pdf_text_span"
        page_text = content["pages"][anchor.selector.page - 1]["text"]
        assert anchor.selector.char_end <= len(page_text)
    assert result.data.units[0].parent_document_ref == document.original_ref


def test_maintain_anchors_detects_drift(runtime, ctx, workspace):
    document, content = parsed_pdf(runtime, ctx, workspace)
    segment = call("segment_document", {"document_ref": document}, ctx, runtime)
    anchors = [unit.anchors[0] for unit in segment.data.units]
    drift = call(
        "maintain_source_anchors",
        {"anchors": anchors, "current_revision": "sha256:new"},
        ctx,
        runtime,
    )
    assert drift.status.value == "ok"
    assert all(item.status == "expired" for item in drift.data.anchors)

    # A remap is only meaningful when the payload being verified is the one
    # declared current. Reuse the same blocks under the new revision so this
    # fixture exercises the supported path; the tampered-revision case is
    # covered in test_round4_unit_anchors.py.
    current_document = document.model_copy(
        update={
            "original_ref": document.original_ref.model_copy(
                update={"revision": "sha256:new"}
            )
        }
    )
    # The remap fixture reuses the parsed blocks under a new revision; that
    # binding must be registered so load_document_content accepts it
    # (reviewer F1).
    from dataagent_data.preparation.documents import register_document_blocks

    register_document_blocks(runtime, current_document)
    remapped = call(
        "maintain_source_anchors",
        {
            "anchors": anchors,
            "current_revision": "sha256:new",
            "revision_map": {anchors[0].source_revision: "sha256:new"},
            "document_ref": current_document,
        },
        ctx,
        runtime,
    )
    statuses = {item.status for item in remapped.data.anchors}
    assert "remapped" in statuses


def make_schema():
    from dataagent_contracts.core import FieldSpec

    return [
        FieldSpec(field_id="amount", name="Amount", path="/amount", value_type="money", unit="CNY"),
        FieldSpec(field_id="approver", name="Approver", path="/approver", value_type="string"),
    ]


def valid_anchor(content, document, needle="5800"):
    page_text = content["pages"][0]["text"]
    start = page_text.index(needle)
    return {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": start + len(needle),
        },
    }


def test_extract_fields_two_phase(runtime, ctx, workspace):
    document, content = parsed_pdf(runtime, ctx, workspace)
    fields = make_schema()
    first = call(
        "extract_fields_to_schema",
        {"document_ref": document, "fields": fields},
        ctx,
        runtime,
    )
    assert first.status.value == "needs_input"
    assert first.issues[0].inference_request["kind"] == "field_extraction"
    assert first.data.candidate_spans

    second = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": fields,
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 5800,
                    "value_type": "money",
                    "unit": "CNY",
                    "confidence": {"score": 0.96, "method": "agent-structured"},
                    "anchors": [valid_anchor(content, document)],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert second.status.value == "partial", second.issues
    record = second.data.record
    by_id = {field.field_id: field for field in record.fields}
    assert by_id["amount"].status.value == "extracted"
    assert by_id["amount"].evidence
    assert by_id["approver"].status.value == "missing"
    assert any(issue.code == "da02.field_missing" for issue in second.issues)


def test_extract_fields_rejects_fabricated_anchor(runtime, ctx, workspace):
    document, content = parsed_pdf(runtime, ctx, workspace)
    fields = make_schema()
    fabricated = valid_anchor(content, document)
    fabricated["selector"]["char_start"] = 10000
    fabricated["selector"]["char_end"] = 10005
    result = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": fields,
            "proposal": [
                {"field_id": "amount", "value": 5800, "anchors": [fabricated]}
            ],
        },
        ctx,
        runtime,
    )
    by_id = {field.field_id: field for field in result.data.record.fields}
    assert by_id["amount"].status.value == "missing"
    assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)


def test_extract_fields_no_anchor_is_missing(runtime, ctx, workspace):
    document, content = parsed_pdf(runtime, ctx, workspace)
    result = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": make_schema(),
            "proposal": [{"field_id": "amount", "value": 5800, "anchors": []}],
        },
        ctx,
        runtime,
    )
    by_id = {field.field_id: field for field in result.data.record.fields}
    assert by_id["amount"].status.value == "missing"
    assert any(issue.code == "da02.unanchored_value" for issue in result.issues)


def test_anchor_extracted_values_locates_and_marks_missing(runtime, ctx, workspace):
    from dataagent_contracts.core import (
        AssetRef,
        ExtractedRecordRef,
        FieldValue,
        SourceAnchor,
        VersionedRef,
    )

    document, content = parsed_pdf(runtime, ctx, workspace)
    bad_anchor = SourceAnchor(
        source_ref="file:policy",
        source_revision="sha256:aa11",
        selector={"kind": "pdf_text_span", "page": 99, "char_start": 0, "char_end": 1},
    )
    asset = AssetRef(
        id="rec:test",
        kind="extracted_record",
        scope_ref="tenant:test",
        revision="r1",
        resolver="store",
        locator="rec/test",
    )
    record = ExtractedRecordRef(
        asset=asset,
        document_ref=document.original_ref,
        target_schema_ref=VersionedRef(id="xschema:test", revision="v1"),
        fields=[
            FieldValue(
                field_id="amount",
                status="extracted",
                value=5800,
                value_type="money",
                evidence=[bad_anchor],
            ),
            FieldValue(
                field_id="ghost",
                status="extracted",
                value="does-not-exist-anywhere",
                value_type="string",
                evidence=[bad_anchor],
            ),
        ],
    )
    result = call(
        "anchor_extracted_values",
        {"record": record, "document_ref": document},
        ctx,
        runtime,
    )
    assert result.status.value == "partial"
    assert "ghost" in result.data.unlocated
    by_id = {field.field_id: field for field in result.data.record.fields}
    assert by_id["amount"].status.value == "extracted"
    assert by_id["amount"].evidence[0].selector.page == 1
    assert by_id["ghost"].status.value == "missing"


def test_register_extraction_schema_is_idempotent_and_versioned(runtime, ctx, workspace):
    fields = [field.model_dump(mode="json") for field in make_schema()]
    first = call(
        "register_extraction_schema_version",
        {"fields": fields, "document_type": "expense"},
        ctx,
        runtime,
    )
    assert first.status.value == "ok"
    assert first.data.revision == "r1"
    second = call(
        "register_extraction_schema_version",
        {"fields": fields, "document_type": "expense"},
        ctx,
        runtime,
    )
    assert second.data.revision == "r1"
    assert second.issues and second.issues[0].code == "da02.schema_version_idempotent"

    changed = [dict(item) for item in fields]
    changed[0]["name"] = "Claim amount"
    third = call(
        "register_extraction_schema_version",
        {"fields": changed, "document_type": "expense"},
        ctx,
        runtime,
    )
    assert third.data.revision == "r2"

    conflict = call(
        "register_extraction_schema_version",
        {"fields": changed, "expected_revision": "r1"},
        ctx,
        runtime,
    )
    assert conflict.status.value == "failed"
    assert conflict.issues[0].code == "version_conflict"


def test_extract_rejects_anchor_that_does_not_contain_value(runtime, ctx, workspace):
    document, content = parsed_pdf(runtime, ctx, workspace)
    result = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": make_schema(),
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 999,
                    "anchors": [valid_anchor(content, document)],
                }
            ],
        },
        ctx,
        runtime,
    )
    by_id = {field.field_id: field for field in result.data.record.fields}
    assert by_id["amount"].status.value == "missing"
    assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)
    assert "does not contain" in result.issues[0].message
