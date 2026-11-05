"""05-contracts.md §6 S0 acceptance, one test per item.

Item 1 needs an auditable manifest: the 51 required atoms, their family and
their primary input/output types. The contracts package cannot import the
capability implementations (see ``test_dependency.py``), so the manifest is
frozen here; the data package asserts the same names against its registry in
``tests/test_registry.py``.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from dataagent_contracts.core import (
    AcceptanceReport,
    Aggregation,
    CapabilityResult,
    CapabilityStatus,
    CORE_TYPES,
    FieldValue,
    Issue,
    StandardErrorCode,
    validate_acceptance_report,
)

from samples import anchor, completeness, sample_instances

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "dataagent_contracts"
SCHEMA = ROOT / "schema" / "generated"
EXAMPLES = ROOT / "examples" / "s0"

# id -> (operation, family, primary input type, primary output type)
S0_MANIFEST: dict[str, tuple[str, str, str, str]] = {
    "DA01.4.1": ("parse_regular_excel", "骨干", "ParseRegularExcelInput", "ParseRegularExcelOutput"),
    "DA01.4.2": ("extract_irregular_excel", "计算族", "ExtractIrregularExcelInput", "ExtractIrregularExcelOutput"),
    "DA01.4.3": ("parse_delimited_file", "骨干", "ParseDelimitedInput", "ParseDelimitedOutput"),
    "DA01.4.4": ("parse_json_records", "骨干", "ParseJsonRecordsInput", "ParseJsonRecordsOutput"),
    "DA01.4.5": ("parse_text_pdf", "骨干", "ParseTextPdfInput", "ParseTextPdfOutput"),
    "DA01.4.6": ("inspect_workbook_calc_state", "计算族", "InspectWorkbookCalcStateInput", "InspectWorkbookCalcStateOutput"),
    "DA01.5.1": ("ocr_pdf", "骨干", "OcrPdfInput", "OcrPdfOutput"),
    "DA01.5.2": ("ocr_image", "骨干", "OcrImageInput", "OcrImageOutput"),
    "DA02.1.1": ("detect_workbook_regions", "计算族", "DetectWorkbookRegionsInput", "DetectWorkbookRegionsOutput"),
    "DA02.12.1": ("extract_fields_to_schema", "判定族", "ExtractFieldsInput", "ExtractFieldsOutput"),
    "DA02.12.3": ("anchor_extracted_values", "判定族", "AnchorExtractedValuesInput", "AnchorExtractedValuesOutput"),
    "DA02.12.4": ("register_extraction_schema_version", "判定族", "RegisterExtractionSchemaInput", "ExtractionSchemaRef"),
    "DA02.2.1": ("recover_headers", "计算族", "RecoverHeadersInput", "RecoverHeadersOutput"),
    "DA02.2.2": ("expand_merged_cells", "计算族", "ExpandMergedCellsInput", "ExpandMergedCellsOutput"),
    "DA02.2.3": ("classify_table_rows", "计算族", "ClassifyTableRowsInput", "ClassifyTableRowsOutput"),
    "DA02.4.1": ("profile_table_structure", "计算族", "ProfileTableStructureInput", "ProfileTableStructureOutput"),
    "DA02.4.3": ("infer_field_types", "计算族", "InferFieldTypesInput", "InferFieldTypesOutput"),
    "DA02.8.1": ("segment_document", "判定族", "SegmentDocumentInput", "SegmentDocumentOutput"),
    "DA02.8.2": ("maintain_source_anchors", "判定族", "MaintainSourceAnchorsInput", "AnchorMaintenanceOutput"),
    "DA03.15.1": ("assess_automatic_decidability", "判定族", "AssessDecidabilityInput", "Assessment"),
    "DA03.15.2": ("identify_evidence_or_human_gaps", "判定族", "IdentifyGapsInput", "GapPlan"),
    "DA03.15.3": ("mark_automation_coverage", "判定族", "MarkCoverageInput", "CoverageMap"),
    "DA03.15.4": ("resolve_decidability_cache", "判定族", "ResolveDecidabilityCacheInput", "CacheResolution"),
    "DA03.16.1": ("define_rule_applicability", "判定族", "DefineApplicabilityInput", "ApplicabilityDraft"),
    "DA03.16.2": ("define_rule_preconditions", "判定族", "DefinePreconditionsInput", "DefinePreconditionsOutput"),
    "DA03.16.3": ("normalize_precondition_references", "判定族", "NormalizePreconditionsInput", "NormalizePreconditionsOutput"),
    "DA03.16.4": ("resolve_unknown_applicability", "判定族", "ResolveUnknownApplicabilityInput", "Assessment"),
    "DA03.4.1": ("define_metric_formula", "计算族", "DefineMetricInput", "DefineMetricOutput"),
    "DA03.4.3": ("define_business_rules", "判定族", "DefineBusinessRulesInput", "DefineBusinessRulesOutput"),
    "DA04.1.1": ("append_task_event", "骨干", "AppendTaskEventInput", "TraceEventRef"),
    "DA04.1.2": ("append_invocation_record", "骨干", "AppendInvocationRecordInput", "TraceEventRef"),
    "DA04.1.3": ("append_user_correction", "骨干", "AppendUserCorrectionInput", "CorrectionRef"),
    "DA06.1.1": ("bind_metrics_and_dimensions", "计算族", "BindMetricsAndDimensionsInput", "BindMetricsAndDimensionsOutput"),
    "DA06.1.2": ("parse_time_and_filters", "计算族", "ParseTimeAndFiltersInput", "ParseTimeAndFiltersOutput"),
    "DA06.1.3": ("identify_calculation_ambiguities", "计算族", "IdentifyCalculationAmbiguitiesInput", "IdentifyCalculationAmbiguitiesOutput"),
    "DA06.1.4": ("generate_clarification_questions", "计算族", "GenerateClarificationQuestionsInput", "GenerateClarificationQuestionsOutput"),
    "DA06.3.1": ("generate_single_table_sql", "计算族", "GenerateSingleTableSqlInput", "GenerateSingleTableSqlOutput"),
    "DA06.3.5": ("generate_function_expressions", "骨干", "GenerateFunctionExpressionsInput", "GenerateFunctionExpressionsOutput"),
    "DA07.1.3": ("execute_duckdb_sql", "计算族", "ExecuteDuckdbSqlInput", "ExecuteDuckdbSqlOutput"),
    "DA07.10.1": ("acquire_and_align_engine", "骨干", "AcquireAndAlignEngineInput", "AcquireAndAlignEngineOutput"),
    "DA07.5.1": ("evaluate_scalar_expression", "骨干", "EvaluateScalarInput", "EvaluateScalarOutput"),
    "DA07.5.2": ("evaluate_table_expression", "骨干", "EvaluateTableInput", "EvaluateTableOutput"),
    "DA10.1.1": ("build_result_workbook", "计算族", "BuildResultWorkbookInput", "BuildResultWorkbookOutput"),
    "DA10.3.1": ("compose_document_report", "骨干", "ComposeDocumentReportInput", "ComposeDocumentReportOutput"),
    "DA10.3.3": ("export_report_format", "骨干", "ExportReportFormatInput", "ExportReportFormatOutput"),
    "DA11.2.3": ("check_result_grain_and_merge", "计算族", "TableRef", "GrainMergeReport"),
    "DA11.5.1": ("draft_acceptance_criteria", "骨干", "TaskContextRef", "AcceptanceCriteriaDraft"),
    "DA11.5.5": ("evaluate_business_acceptance", "骨干", "AcceptanceReport", "AcceptanceReport"),
    "DA11.5.6": ("isolate_acceptance_samples", "骨干", "EvaluationSetRef", "EvaluationSetRef"),
    "DA12.1.1": ("check_access_scope", "骨干", "AccessRequest", "AccessDecision"),
    "DA12.1.4": ("check_model_context_egress", "骨干", "EgressRequest", "EgressDecision"),
}

# Types owned by a capability layer rather than ``core``. They are listed
# explicitly so an inert string cannot masquerade as a resolved type.
LAYER_TYPES = frozenset(
    {
        # S0 data-layer implementation models
        "ParseRegularExcelInput", "ParseRegularExcelOutput",
        "ExtractIrregularExcelInput", "ExtractIrregularExcelOutput",
        "ParseDelimitedInput", "ParseDelimitedOutput",
        "ParseJsonRecordsInput", "ParseJsonRecordsOutput",
        "ParseTextPdfInput", "ParseTextPdfOutput",
        "InspectWorkbookCalcStateInput", "InspectWorkbookCalcStateOutput",
        "OcrPdfInput", "OcrPdfOutput", "OcrImageInput", "OcrImageOutput",
        "DetectWorkbookRegionsInput", "DetectWorkbookRegionsOutput",
        "ExtractFieldsInput", "ExtractFieldsOutput",
        "AnchorExtractedValuesInput", "AnchorExtractedValuesOutput",
        "RegisterExtractionSchemaInput", "ExtractionSchemaRef",
        "RecoverHeadersInput", "RecoverHeadersOutput",
        "ExpandMergedCellsInput", "ExpandMergedCellsOutput",
        "ClassifyTableRowsInput", "ClassifyTableRowsOutput",
        "ProfileTableStructureInput", "ProfileTableStructureOutput",
        "InferFieldTypesInput", "InferFieldTypesOutput",
        "SegmentDocumentInput", "SegmentDocumentOutput",
        "MaintainSourceAnchorsInput", "AnchorMaintenanceOutput",
        "AssessDecidabilityInput", "IdentifyGapsInput", "MarkCoverageInput",
        "ResolveDecidabilityCacheInput", "GapPlan", "CoverageMap", "CacheResolution",
        "DefineApplicabilityInput", "ApplicabilityDraft",
        "DefinePreconditionsInput", "DefinePreconditionsOutput",
        "NormalizePreconditionsInput", "NormalizePreconditionsOutput",
        "ResolveUnknownApplicabilityInput",
        "DefineMetricInput", "DefineMetricOutput",
        "DefineBusinessRulesInput", "DefineBusinessRulesOutput",
        "AppendTaskEventInput", "AppendInvocationRecordInput",
        "AppendUserCorrectionInput",
        # S0 application-layer IO models (implemented output shapes, r19 fix).
        "BindMetricsAndDimensionsInput", "BindMetricsAndDimensionsOutput",
        "ParseTimeAndFiltersInput", "ParseTimeAndFiltersOutput",
        "IdentifyCalculationAmbiguitiesInput", "IdentifyCalculationAmbiguitiesOutput",
        "GenerateClarificationQuestionsInput", "GenerateClarificationQuestionsOutput",
        "GenerateSingleTableSqlInput", "GenerateSingleTableSqlOutput",
        "GenerateFunctionExpressionsInput", "GenerateFunctionExpressionsOutput",
        "ExecuteDuckdbSqlInput", "ExecuteDuckdbSqlOutput",
        "AcquireAndAlignEngineInput", "AcquireAndAlignEngineOutput",
        "EvaluateScalarInput", "EvaluateScalarOutput",
        "EvaluateTableInput", "EvaluateTableOutput",
        "BuildResultWorkbookInput", "BuildResultWorkbookOutput",
        "ComposeDocumentReportInput", "ComposeDocumentReportOutput",
        "ExportReportFormatInput", "ExportReportFormatOutput",
        # S1/S2 layer types named by the remaining S0 atoms.
        "RequirementSpec", "Ambiguity", "ClarificationQuestion",
        "ExecutableSpec",
        "EngineBinding", "ArtifactRef", "ReportDraft",
        "GrainMergeReport", "AcceptanceCriteriaDraft", "AccessRequest",
        "EgressRequest",
    }
)

RESOLVED_TYPES = set(CORE_TYPES) | set(LAYER_TYPES)

# Plaintext credential field names that must never appear in core models.
_CREDENTIAL_FIELDS = frozenset(
    {
        "password", "passwd", "secret", "client_secret", "api_key", "apikey",
        "access_token", "refresh_token", "private_key", "credential",
        "credentials", "plaintext_password",
    }
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CN_MOBILE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def test_item1_s0_manifest_resolves_to_core_or_layer_types():
    assert len(S0_MANIFEST) == 51
    assert len({entry[0] for entry in S0_MANIFEST.values()}) == 51
    families = [entry[1] for entry in S0_MANIFEST.values()]
    assert (families.count("骨干"), families.count("判定族"), families.count("计算族")) == (
        20,
        14,
        17,
    )
    for atom_id, (operation, family, input_type, output_type) in S0_MANIFEST.items():
        assert operation, atom_id
        assert family in {"骨干", "判定族", "计算族"}, atom_id
        for type_name in (input_type, output_type):
            base = type_name.split("[", 1)[0]
            assert base in RESOLVED_TYPES, (atom_id, type_name)


def test_item2_schema_and_examples_validate():
    jsonschema = pytest.importorskip("jsonschema")
    mapping = {
        "assessment-unknown.json": "Assessment",
        "computed-result.json": "ComputedResult",
        "extraction-partial.json": "CapabilityResult",
        "needs-input.json": "CapabilityResult",
        "semantic-draft-rule.json": "SemanticDraft",
    }
    assert {p.name for p in EXAMPLES.glob("*.json")} == set(mapping)
    for filename, schema_name in mapping.items():
        schema = json.loads((SCHEMA / f"{schema_name}.json").read_text(encoding="utf-8"))
        instance = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(instance)
    assert len(list(SCHEMA.glob("*.json"))) == 69  # 68 schemas + index.json


def test_item3_envelope_constraints():
    with pytest.raises(ValidationError, match="failed result requires"):
        CapabilityResult[dict](status=CapabilityStatus.failed, data=None, issues=[])
    with pytest.raises(ValidationError, match="non-null value"):
        FieldValue(
            field_id="amount",
            status="extracted",
            value=None,
            value_type="number",
            evidence=[anchor()],
        )
    samples = sample_instances()
    report = samples["AcceptanceReport"]
    assert isinstance(report, AcceptanceReport)
    validate_acceptance_report(
        report,
        criteria=samples["CriteriaRef"],
        evaluation_set=samples["EvaluationSetRef"],
    )
    with pytest.raises(ValueError, match="unseen_acceptance"):
        validate_acceptance_report(
            report,
            criteria=samples["CriteriaRef"],
            evaluation_set=samples["EvaluationSetRef"].model_copy(
                update={"counts": {"development": 1}}
            ),
        )


def test_item4_enum_closure_and_open_namespace():
    with pytest.raises(ValueError):
        StandardErrorCode("acme.not_a_code")
    assert Aggregation("acme.weighted_mean").value == "acme.weighted_mean"
    with pytest.raises(ValueError):
        Aggregation("acme:weighted_mean")
    with pytest.raises(ValueError):
        Aggregation("weighted_mean")


def test_item5_dependency_direction():
    allowed = {"pydantic", "typing_extensions", "dataagent_contracts"}
    stdlib = set(__import__("sys").stdlib_module_names)
    offenders = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
        bad = roots - allowed - stdlib
        if bad:
            offenders.append((str(path.relative_to(SRC)), sorted(bad)))
    assert not offenders, offenders
    for path in SRC.rglob("*.py"):
        assert "dataagent_data" not in path.read_text(encoding="utf-8"), path


def test_item6_no_plaintext_credentials_or_real_customer_data():
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id.lower() in _CREDENTIAL_FIELDS:
                    offenders.append(f"{path.name}:{node.lineno}:{node.target.id}")
    assert not offenders, f"plaintext credential fields: {offenders}"

    for path in list(EXAMPLES.glob("*.json")) + [ROOT / "tests" / "samples.py"]:
        text = path.read_text(encoding="utf-8")
        for match in _EMAIL.finditer(text):
            assert match.group(0).endswith("@example.com"), (path.name, match.group(0))
        assert not _CN_MOBILE.search(text), (path.name, _CN_MOBILE.search(text))


def test_item7_generality_families_and_extensions():
    jsonschema = pytest.importorskip("jsonschema")
    cases = {
        "semantic-draft-rule.json": ("SemanticDraft", "判定族"),
        "computed-result.json": ("ComputedResult", "计算族"),
    }
    for filename, (schema_name, _family) in cases.items():
        schema = json.loads((SCHEMA / f"{schema_name}.json").read_text(encoding="utf-8"))
        instance = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(instance)
        # Application-specific data may only live under ``extensions``; a new
        # top-level field must fail rather than silently extend the core type.
        extended = dict(instance, app_specific_field={"vendor": "acme"})
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(extended)
