from __future__ import annotations

import json
from pathlib import Path

from dataagent_data.registry import (
    list_operations,
    load_catalog,
    registry_errors,
    validate_registry,
)


def test_32_operations_registered():
    specs = list_operations()
    assert len(specs) == 32
    assert len({s.operation for s in specs}) == 32
    assert len({s.capability_id for s in specs}) == 32


def test_registry_matches_catalog_exactly():
    catalog = load_catalog()
    assert catalog["counts"]["atoms"] == 32
    assert catalog["counts"]["by_family"] == {"骨干": 9, "判定族": 14, "计算族": 9}
    assert registry_errors(catalog) == []
    validate_registry(catalog)


def test_snapshot_matches_authoritative_catalog():
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "export_catalog_snapshot.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_unknown_operation_is_unsupported(runtime, ctx):
    from dataagent_data.invoke import invoke

    result = invoke("no_such_operation", {}, ctx, runtime=runtime)
    assert result.status.value == "failed"
    assert result.issues[0].code == "unsupported"


def test_authorization_ref_is_required(runtime):
    from dataagent_data.invoke import invoke

    result = invoke(
        "parse_delimited_file",
        {},
        {"request_id": "r", "scope_ref": "s", "authorization_ref": " "},
        runtime=runtime,
    )
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"


def test_invalid_input_is_structured(runtime, ctx):
    from dataagent_data.invoke import invoke

    result = invoke("parse_delimited_file", {"nope": 1}, ctx, runtime=runtime)
    assert result.status.value == "failed"
    assert result.issues[0].code == "invalid_input"
    assert result.issues[0].target


def test_every_operation_has_a_negative_input_case(runtime, ctx):
    """G1/W2: each of the 32 atoms must reject malformed input structurally."""
    from dataagent_data.invoke import invoke
    from dataagent_data.registry import list_operations

    for spec in list_operations():
        result = invoke(spec.operation, {}, ctx, runtime=runtime)
        assert result.status.value == "failed", spec.operation
        assert result.issues, spec.operation
        assert result.issues[0].code == "invalid_input", spec.operation
        assert result.execution_ref is not None, spec.operation


S0_IO_MODELS = {
    "parse_regular_excel": ("ParseRegularExcelInput", "ParseRegularExcelOutput"),
    "extract_irregular_excel": ("ExtractIrregularExcelInput", "ExtractIrregularExcelOutput"),
    "parse_delimited_file": ("ParseDelimitedInput", "ParseDelimitedOutput"),
    "parse_json_records": ("ParseJsonRecordsInput", "ParseJsonRecordsOutput"),
    "parse_text_pdf": ("ParseTextPdfInput", "ParseTextPdfOutput"),
    "inspect_workbook_calc_state": ("InspectWorkbookCalcStateInput", "InspectWorkbookCalcStateOutput"),
    "ocr_pdf": ("OcrPdfInput", "OcrPdfOutput"),
    "ocr_image": ("OcrImageInput", "OcrImageOutput"),
    "detect_workbook_regions": ("DetectWorkbookRegionsInput", "DetectWorkbookRegionsOutput"),
    "extract_fields_to_schema": ("ExtractFieldsInput", "ExtractFieldsOutput"),
    "anchor_extracted_values": ("AnchorExtractedValuesInput", "AnchorExtractedValuesOutput"),
    "register_extraction_schema_version": ("RegisterExtractionSchemaInput", "ExtractionSchemaRef"),
    "recover_headers": ("RecoverHeadersInput", "RecoverHeadersOutput"),
    "expand_merged_cells": ("ExpandMergedCellsInput", "ExpandMergedCellsOutput"),
    "classify_table_rows": ("ClassifyTableRowsInput", "ClassifyTableRowsOutput"),
    "profile_table_structure": ("ProfileTableStructureInput", "ProfileTableStructureOutput"),
    "infer_field_types": ("InferFieldTypesInput", "InferFieldTypesOutput"),
    "segment_document": ("SegmentDocumentInput", "SegmentDocumentOutput"),
    "maintain_source_anchors": ("MaintainSourceAnchorsInput", "AnchorMaintenanceOutput"),
    "assess_automatic_decidability": ("AssessDecidabilityInput", "Assessment"),
    "identify_evidence_or_human_gaps": ("IdentifyGapsInput", "GapPlan"),
    "mark_automation_coverage": ("MarkCoverageInput", "CoverageMap"),
    "resolve_decidability_cache": ("ResolveDecidabilityCacheInput", "CacheResolution"),
    "define_rule_applicability": ("DefineApplicabilityInput", "ApplicabilityDraft"),
    "define_rule_preconditions": ("DefinePreconditionsInput", "DefinePreconditionsOutput"),
    "normalize_precondition_references": ("NormalizePreconditionsInput", "NormalizePreconditionsOutput"),
    "resolve_unknown_applicability": ("ResolveUnknownApplicabilityInput", "Assessment"),
    "define_metric_formula": ("DefineMetricInput", "DefineMetricOutput"),
    "define_business_rules": ("DefineBusinessRulesInput", "DefineBusinessRulesOutput"),
    "append_task_event": ("AppendTaskEventInput", "TraceEventRef"),
    "append_invocation_record": ("AppendInvocationRecordInput", "TraceEventRef"),
    "append_user_correction": ("AppendUserCorrectionInput", "CorrectionRef"),
}


def test_implemented_atoms_match_frozen_s0_io_manifest():
    """05 §6 item 1: the 32 implemented atoms keep the frozen type names."""

    specs = {spec.operation: spec for spec in list_operations()}
    assert set(specs) == set(S0_IO_MODELS)
    actual = {}
    for operation, spec in specs.items():
        output_name = spec.output_model.__name__
        if output_name.startswith("Assessment["):
            output_name = "Assessment"
        actual[operation] = (spec.input_model.__name__, output_name)
    assert actual == S0_IO_MODELS


# Markers that show a handler persists something through the runtime. The MCP
# annotation test only verifies totals; this static guard catches the bug type
# that slipped through twice: a persistent handler still declared read-only
# (Round 4.2 P1).
PERSISTENCE_MARKERS = (
    "register_file_ref(",
    "store_table(",
    "store_document_blocks(",
    "content.put(",
    ".versions.save",
    ".traces.append(",
)


def test_persistent_handlers_are_declared_as_writes():
    import inspect

    persisting = []
    for spec in list_operations():
        source = inspect.getsource(spec.handler)
        hits = [marker for marker in PERSISTENCE_MARKERS if marker in source]
        if hits:
            persisting.append((spec.operation, spec.writes, hits))

    assert persisting, "the marker scan found no persistence at all"
    offenders = [
        (operation, hits) for operation, writes, hits in persisting if writes is not True
    ]
    assert not offenders, f"persistent handlers declared read-only: {offenders}"
    # 21 handlers write inline; the three trace atoms delegate to a helper.
    assert len(persisting) == 21
