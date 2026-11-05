"""Round 4: document-unit anchors, anchor maintenance and JSON pointer roots.

Covers the residual gaps of 06 §14 item 1:

* non-PDF ``text_span`` anchors are relative to the *unit* body and survive an
  end-to-end ``segment_document`` -> ``extract_fields_to_schema`` round trip;
* a fabricated unit reference still fails closed;
* ``maintain_source_anchors`` cannot "verify" an anchor without a document;
* ``records_path`` follows RFC 6901 for the root and the empty key.
"""

from __future__ import annotations

import json

from conftest import build_pdf, call, file_ref, write_file

from dataagent_data.adapters.ocr.engine import OcrBlock


def _image_document(runtime, ctx, workspace):
    class FakeEngine:
        engine_ref = "fake"
        engine_version = "1.0"

        def recognize(self, image_bytes, *, lang=None):
            return [
                OcrBlock(
                    text="1. Scope", bbox=[10, 10, 80, 20], confidence=0.95
                ),
                OcrBlock(
                    text="Claims above 5000 CNY require department head approval.",
                    bbox=[10, 25, 400, 35],
                    confidence=0.95,
                ),
            ]

    runtime.ocr_engine = FakeEngine()
    write_file(workspace, "policy.png", b"\x89PNG\r\n\x1a\nfake")
    result = call(
        "ocr_image", {"file_ref": file_ref(workspace, "policy.png")}, ctx, runtime
    )
    assert result.status.value == "ok", result.issues
    return result.data.document


def test_segment_document_persists_unit_body_for_text_span(runtime, ctx, workspace):
    document = _image_document(runtime, ctx, workspace)
    segmented = call("segment_document", {"document_ref": document}, ctx, runtime)
    assert segmented.status.value == "ok", segmented.issues
    units = segmented.data.units
    assert units

    for unit in units:
        unit_text = runtime.content.get_text(unit.content_ref)
        anchor = unit.anchors[0]
        assert anchor.selector.kind == "text_span"
        assert anchor.selector.unit_ref == unit.content_ref
        assert anchor.selector.char_start == 0
        assert anchor.selector.char_end == len(unit_text)

    text = runtime.content.get_text(units[0].content_ref)
    assert "Claims above 5000 CNY" in text


def test_extract_fields_resolves_text_span_against_unit_body(runtime, ctx, workspace):
    document = _image_document(runtime, ctx, workspace)
    segmented = call("segment_document", {"document_ref": document}, ctx, runtime)
    unit = segmented.data.units[0]
    unit_text = runtime.content.get_text(unit.content_ref)
    start = unit_text.index("Claims above")
    end = start + len("Claims above 5000 CNY require department head approval.")

    extracted = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "amount",
                    "path": "/amount",
                    "value_type": "money",
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 5000,
                    "value_type": "money",
                    "anchors": [
                        {
                            "source_ref": document.original_ref.id,
                            "source_revision": document.original_ref.revision,
                            "selector": {
                                "kind": "text_span",
                                "unit_ref": unit.content_ref,
                                "char_start": start,
                                "char_end": end,
                            },
                        }
                    ],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert extracted.status.value == "ok", extracted.issues
    field = extracted.data.record.fields[0]
    assert field.status.value == "extracted"
    assert field.value == 5000

    # DA02.12.3 re-checks the persisted evidence anchors; a unit-body anchor
    # must resolve there too (not "unit body unavailable").
    anchored = call(
        "anchor_extracted_values",
        {"record": extracted.data.record, "document_ref": document},
        ctx,
        runtime,
    )
    assert anchored.status.value == "ok", anchored.issues
    assert anchored.data.unlocated == []
    assert anchored.data.mappings[0].status == "anchored"
    assert anchored.data.mappings[0].anchors[0].selector.unit_ref == unit.content_ref


def test_fabricated_unit_ref_is_missing_not_accepted(runtime, ctx, workspace):
    document = _image_document(runtime, ctx, workspace)
    extracted = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "amount",
                    "path": "/amount",
                    "value_type": "money",
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 5000,
                    "value_type": "money",
                    "anchors": [
                        {
                            "source_ref": document.original_ref.id,
                            "source_revision": document.original_ref.revision,
                            "selector": {
                                "kind": "text_span",
                                "unit_ref": "sha256:" + "0" * 64,
                                "char_start": 0,
                                "char_end": 4,
                            },
                        }
                    ],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert extracted.data.record.fields[0].status.value == "missing"
    codes = {issue.code for issue in extracted.issues}
    assert codes & {"da02.anchor_not_found", "da02.anchor_value_mismatch"}, codes


def test_maintain_anchors_requires_a_document(runtime, ctx, workspace):
    build_pdf(workspace / "policy.pdf", ["Claims above 5000 CNY require approval."])
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    segmented = call("segment_document", {"document_ref": document}, ctx, runtime)
    anchor = segmented.data.units[0].anchors[0]
    result = call(
        "maintain_source_anchors",
        {"anchors": [anchor], "current_revision": anchor.source_revision},
        ctx,
        runtime,
    )
    assert result.data.anchors[0].status == "unresolved"
    assert "document_ref" in result.data.anchors[0].reason


def _record_with_anchor(document, anchor, value=5000):
    from dataagent_contracts.core import (
        AssetRef,
        ExtractedRecordRef,
        FieldValue,
        VersionedRef,
    )

    return ExtractedRecordRef(
        asset=AssetRef(
            id="asset:record",
            kind="extracted_record",
            scope_ref="tenant:test/project:p1",
            revision="r1",
            resolver="local",
            locator="record.json",
        ),
        document_ref=document.original_ref,
        target_schema_ref=VersionedRef(id="xschema:record", revision="r1"),
        fields=[
            FieldValue(
                field_id="amount",
                status="extracted",
                value=value,
                value_type="money",
                evidence=[anchor],
            )
        ],
    )


def test_document_asset_id_is_not_a_unit(runtime, ctx, workspace):
    """The whole-document digest must not be accepted as a unit reference."""

    document = _image_document(runtime, ctx, workspace)
    content = runtime.content.get_json(document.blocks_ref)
    from dataagent_data.contracts.layer import DocumentContent

    full_text = DocumentContent.model_validate(content).full_text
    start = full_text.index("Claims above")
    end = start + len("Claims above 5000 CNY require department head approval.")
    bad_anchor = {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "text_span",
            "unit_ref": document.asset.id,
            "char_start": start,
            "char_end": end,
        },
    }

    extracted = call(
        "extract_fields_to_schema",
        {
            "document_ref": document,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "amount",
                    "path": "/amount",
                    "value_type": "money",
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 5000,
                    "value_type": "money",
                    "anchors": [bad_anchor],
                }
            ],
        },
        ctx,
        runtime,
    )
    field = extracted.data.record.fields[0]
    assert field.status.value == "missing"
    assert field.value is None
    assert "da02.anchor_not_found" in {issue.code for issue in extracted.issues}

    # DA02.12.3 must also refuse to re-anchor against the document digest.
    from dataagent_contracts.core import SourceAnchor

    record = _record_with_anchor(
        document, SourceAnchor.model_validate(bad_anchor), value=9999
    )
    anchored = call(
        "anchor_extracted_values",
        {"record": record, "document_ref": document},
        ctx,
        runtime,
    )
    assert anchored.data.unlocated == ["amount"]
    assert anchored.data.mappings[0].status == "missing"
    assert anchored.data.record.fields[0].status.value == "missing"
    assert "da02.anchor_not_found" in {issue.code for issue in anchored.issues}


def test_unit_ref_from_another_document_is_rejected(runtime, ctx, workspace):
    document_a = _image_document(runtime, ctx, workspace)
    write_file(workspace, "policy-b.png", b"\x89PNG\r\n\x1a\nother")
    parsed_b = call(
        "ocr_image", {"file_ref": file_ref(workspace, "policy-b.png")}, ctx, runtime
    )
    document_b = parsed_b.data.document
    segmented_b = call("segment_document", {"document_ref": document_b}, ctx, runtime)
    unit_b = segmented_b.data.units[0]

    extracted = call(
        "extract_fields_to_schema",
        {
            "document_ref": document_a,
            "fields": [
                {
                    "field_id": "amount",
                    "name": "amount",
                    "path": "/amount",
                    "value_type": "money",
                }
            ],
            "proposal": [
                {
                    "field_id": "amount",
                    "value": 5000,
                    "value_type": "money",
                    "anchors": [
                        {
                            "source_ref": document_a.original_ref.id,
                            "source_revision": document_a.original_ref.revision,
                            "selector": {
                                "kind": "text_span",
                                "unit_ref": unit_b.content_ref,
                                "char_start": 0,
                                "char_end": len(
                                    runtime.content.get_text(unit_b.content_ref)
                                ),
                            },
                        }
                    ],
                }
            ],
        },
        ctx,
        runtime,
    )
    assert extracted.data.record.fields[0].status.value == "missing"
    assert "da02.anchor_not_found" in {issue.code for issue in extracted.issues}


def test_unindexed_content_blob_is_rejected(runtime, ctx, workspace):
    from dataagent_data.preparation.documents import load_document_content
    from dataagent_data.anchors import AnchorResolver, anchor_invalid_reason

    document = _image_document(runtime, ctx, workspace)
    content = load_document_content(runtime, document)
    orphan = runtime.content.put("Claims above 5000 CNY require approval.")
    anchor = {
        "source_ref": document.original_ref.id,
        "source_revision": document.original_ref.revision,
        "selector": {
            "kind": "text_span",
            "unit_ref": orphan,
            "char_start": 0,
            "char_end": 5,
        },
    }
    from dataagent_contracts.core import SourceAnchor

    reason = anchor_invalid_reason(
        AnchorResolver(content, runtime=runtime), SourceAnchor.model_validate(anchor)
    )
    assert "not persisted" in reason


def test_maintain_anchors_rejects_mismatched_document_revision(runtime, ctx, workspace):
    build_pdf(workspace / "policy.pdf", ["Claims above 5000 CNY require approval."])
    parsed = call(
        "parse_text_pdf", {"file_ref": file_ref(workspace, "policy.pdf")}, ctx, runtime
    )
    document = parsed.data.document
    segmented = call("segment_document", {"document_ref": document}, ctx, runtime)
    anchor = segmented.data.units[0].anchors[0]
    tampered = document.model_copy(
        update={
            "original_ref": document.original_ref.model_copy(
                update={"revision": "sha256:" + "0" * 64}
            )
        }
    )
    result = call(
        "maintain_source_anchors",
        {
            "anchors": [anchor],
            "current_revision": anchor.source_revision,
            "document_ref": tampered,
        },
        ctx,
        runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.data is None


def test_json_records_path_root_and_empty_key(runtime, ctx, workspace):
    document = {"": [{"a": 1}], "rows": [{"b": 2}]}
    write_file(workspace, "root.json", json.dumps(document).encode())

    empty_key = call(
        "parse_json_records",
        {"file_ref": file_ref(workspace, "root.json"), "records_path": "/"},
        ctx,
        runtime,
    )
    assert empty_key.status.value == "ok", empty_key.issues
    assert empty_key.data.batch.inline_rows == [{"a": 1}]

    root = call(
        "parse_json_records",
        {"file_ref": file_ref(workspace, "root.json"), "records_path": ""},
        ctx,
        runtime,
    )
    assert root.status.value == "ok", root.issues
    assert root.data.batch.inline_rows == [document]

    normal = call(
        "parse_json_records",
        {"file_ref": file_ref(workspace, "root.json"), "records_path": "/rows"},
        ctx,
        runtime,
    )
    assert normal.data.batch.inline_rows == [{"b": 2}]
