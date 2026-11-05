"""W4.2 acceptance for DA02.12.3: an anchor must substantiate its value.

`anchor_extracted_values` receives already-extracted records and is specified as
returning "可核验匹配与未定位项" (01-data-layer, DA02.12.3). A field whose
anchor exists but whose anchored text does not contain the value must therefore
be downgraded, never left as ``extracted``.
"""

from __future__ import annotations

from conftest import build_pdf, call, file_ref

from dataagent_contracts.core import (
    AssetRef,
    ExtractedRecordRef,
    FieldValue,
    SourceAnchor,
    VersionedRef,
)


def _document(workspace, runtime, ctx, lines, name="doc.pdf"):
    build_pdf(workspace / name, lines)
    parsed = call("parse_text_pdf", {"file_ref": file_ref(workspace, name)}, ctx, runtime)
    assert parsed.status.value == "ok", parsed.issues
    return parsed.data.document


def _content_of(runtime, document) -> str:
    return runtime.content.get_json(document.blocks_ref)["pages"][0]["text"]


def _anchor(document, page_text: str, needle: str) -> SourceAnchor:
    start = page_text.index(needle)
    return SourceAnchor(
        source_ref=document.original_ref.id,
        source_revision=document.original_ref.revision,
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": start + len(needle),
        },
    )


def _record(document, fields: list[FieldValue]) -> ExtractedRecordRef:
    return ExtractedRecordRef(
        asset=AssetRef(
            id="rec:value-check",
            kind="extracted_record",
            scope_ref="tenant:test",
            revision="r1",
            resolver="store",
            locator="rec/value-check",
        ),
        document_ref=document.original_ref,
        target_schema_ref=VersionedRef(id="xschema:test", revision="v1"),
        fields=fields,
    )


def _anchor_call(runtime, ctx, record, document):
    return call(
        "anchor_extracted_values",
        {"record": record, "document_ref": document},
        ctx,
        runtime,
    )


def test_anchor_extracted_values_rejects_value_absent_from_anchor(runtime, ctx, workspace):
    from dataagent_contracts.core import (
        AssetRef,
        ExtractedRecordRef,
        FieldValue,
        SourceAnchor,
        VersionedRef,
    )

    build_pdf(workspace / "policy.pdf", ["1. Scope", "Amount: 5800 CNY"])
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    assert parsed.status.value == "ok", parsed.issues
    document = parsed.data.document
    content = runtime.content.get_json(document.blocks_ref)
    page_text = content["pages"][0]["text"]
    start = page_text.index("Scope")
    anchor = SourceAnchor(
        source_ref=document.original_ref.id,
        source_revision=document.original_ref.revision,
        selector={
            "kind": "pdf_text_span",
            "page": 1,
            "char_start": start,
            "char_end": start + len("Scope"),
        },
    )
    asset = AssetRef(
        id="rec:value-check",
        kind="extracted_record",
        scope_ref="tenant:test",
        revision="r1",
        resolver="store",
        locator="rec/value-check",
    )
    record = ExtractedRecordRef(
        asset=asset,
        document_ref=document.original_ref,
        target_schema_ref=VersionedRef(id="xschema:test", revision="v1"),
        fields=[
            FieldValue(
                field_id="amount",
                status="extracted",
                value=999,
                value_type="money",
                evidence=[anchor],
            )
        ],
    )

    result = call(
        "anchor_extracted_values",
        {"record": record, "document_ref": document},
        ctx,
        runtime,
    )
    field = result.data.record.fields[0]
    assert field.status.value != "extracted", (
        "value 999 has no support in the anchored text 'Scope'"
    )
    assert field.value in (None, 0) or field.status.value == "conflict"
    assert "amount" in result.data.unlocated or any(
        issue.code == "da02.anchor_not_found" for issue in result.issues
    )


def test_anchor_extracted_values_numeric_relocation_is_whole_token(runtime, ctx, workspace):
    """999 must not be relocated onto the 1999 token."""

    document = _document(workspace, runtime, ctx, ["1. Scope", "Amount: 1999 CNY"])
    page_text = _content_of(runtime, document)
    record = _record(
        document,
        [
            FieldValue(
                field_id="amount",
                status="extracted",
                value=999,
                value_type="money",
                evidence=[_anchor(document, page_text, "Scope")],
            )
        ],
    )
    result = _anchor_call(runtime, ctx, record, document)
    field = result.data.record.fields[0]
    assert field.status.value == "missing", page_text
    assert field.value is None
    assert "amount" in result.data.unlocated
    assert any(issue.code == "da02.anchor_not_found" for issue in result.issues)


def test_anchor_extracted_values_keeps_only_supporting_anchors(runtime, ctx, workspace):
    document = _document(workspace, runtime, ctx, ["1. Scope", "Amount: 5800 CNY"])
    page_text = _content_of(runtime, document)
    record = _record(
        document,
        [
            FieldValue(
                field_id="amount",
                status="extracted",
                value=5800,
                value_type="money",
                evidence=[
                    _anchor(document, page_text, "Scope"),
                    _anchor(document, page_text, "Amount: 5800 CNY"),
                ],
            )
        ],
    )
    result = _anchor_call(runtime, ctx, record, document)
    field = result.data.record.fields[0]
    assert field.status.value == "extracted"
    assert len(field.evidence) == 1
    span = page_text[field.evidence[0].selector.char_start : field.evidence[0].selector.char_end]
    assert "5800" in span


def test_anchor_extracted_values_accepts_thousands_separator(runtime, ctx, workspace):
    document = _document(workspace, runtime, ctx, ["Total: 5,800.00 CNY"])
    page_text = _content_of(runtime, document)
    record = _record(
        document,
        [
            FieldValue(
                field_id="total",
                status="extracted",
                value=5800,
                value_type="money",
                evidence=[_anchor(document, page_text, "5,800.00")],
            )
        ],
    )
    result = _anchor_call(runtime, ctx, record, document)
    field = result.data.record.fields[0]
    assert field.status.value == "extracted", [issue.message for issue in result.issues]
    assert field.value == 5800


def test_anchor_extracted_values_rejects_cross_document_record(runtime, ctx, workspace):
    document = _document(workspace, runtime, ctx, ["1. Scope", "Amount: 5800 CNY"])
    page_text = _content_of(runtime, document)
    record = _record(
        document,
        [
            FieldValue(
                field_id="amount",
                status="extracted",
                value=5800,
                value_type="money",
                evidence=[_anchor(document, page_text, "5800")],
            )
        ],
    )
    foreign = record.model_copy(
        update={"document_ref": VersionedRef(id="file:other", revision="sha256:other")}
    )
    result = _anchor_call(runtime, ctx, foreign, document)
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.issues[0].target == "record.document_ref"
