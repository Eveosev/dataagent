"""Round 4 contract tightening (06 §14 item 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dataagent_contracts.core import (
    AcceptanceReport,
    Aggregation,
    CapabilityResult,
    CapabilityStatus,
    DocumentUnitRef,
    FieldValue,
    Issue,
    JsonPointerSelector,
    LifecycleStatus,
    RuleDefinition,
    SchemaRef,
    SemanticDraft,
    Severity,
    Verdict,
    VersionedRef,
    validate_acceptance_report,
)

from samples import anchor, asset, completeness, sample_instances

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema" / "generated"


def test_open_enum_accepts_dotted_namespace_and_rejects_colon():
    assert Aggregation("acme.weighted_mean").value == "acme.weighted_mean"
    with pytest.raises(ValueError):
        Aggregation("acme:weighted_mean")
    with pytest.raises(ValueError):
        Aggregation("weighted_mean")
    with pytest.raises(ValueError):
        Aggregation("Acme.weighted_mean")


def test_open_enum_extension_cache_is_bounded():
    for index in range(200):
        Aggregation(f"acme.v{index}")
    cache = Aggregation.__dict__.get("_open_cache")
    assert cache is not None
    assert len(cache) <= 128


def test_extension_keys_must_be_dotted_namespaces():
    from dataagent_contracts.core import CallContext

    base = {
        "request_id": "req",
        "scope_ref": "scope",
        "authorization_ref": "policy",
    }
    assert CallContext.model_validate({**base, "extensions": {"app.voucher": 1}}).extensions
    with pytest.raises(ValidationError):
        CallContext.model_validate({**base, "extensions": {"app": 1}})
    with pytest.raises(ValidationError):
        CallContext.model_validate({**base, "extensions": {"app:vendor": 1}})


def test_issue_code_is_standard_or_dotted():
    issue = Issue(code="da02.anchor_not_found", severity=Severity.warning, message="m", retryable=False)
    assert issue.code == "da02.anchor_not_found"
    with pytest.raises(ValidationError):
        Issue(code="anchor_not_found", severity=Severity.warning, message="m", retryable=False)
    with pytest.raises(ValidationError):
        Issue(code="da02:anchor", severity=Severity.warning, message="m", retryable=False)


@pytest.mark.parametrize(
    ("type_name", "field"),
    [
        ("Issue", "severity"),
        ("Issue", "retryable"),
        ("FieldValue", "value_type"),
        ("SchemaRef", "inference_basis"),
        ("RuleDefinition", "combination"),
        ("SemanticDraft", "status"),
    ],
)
def test_required_fields_have_no_default(type_name, field):
    payload = sample_instances()[type_name].model_dump(mode="json")
    payload.pop(field)
    model = {
        "Issue": Issue,
        "FieldValue": FieldValue,
        "SchemaRef": SchemaRef,
        "RuleDefinition": RuleDefinition,
        "SemanticDraft": SemanticDraft,
    }[type_name]
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_failed_result_requires_an_issue():
    with pytest.raises(ValidationError, match="failed result requires"):
        CapabilityResult[dict](status=CapabilityStatus.failed, data=None, issues=[])


def test_extracted_field_requires_a_value():
    with pytest.raises(ValidationError, match="non-null value"):
        FieldValue(
            field_id="amount",
            status="extracted",
            value=None,
            value_type="number",
            evidence=[anchor()],
        )


def test_acceptance_helper_checks_criteria_and_samples():
    samples = sample_instances()
    report = samples["AcceptanceReport"]
    assert isinstance(report, AcceptanceReport)
    criteria = samples["CriteriaRef"]
    evaluation_set = samples["EvaluationSetRef"]
    validate_acceptance_report(report, criteria=criteria, evaluation_set=evaluation_set)

    draft_criteria = criteria.model_copy(update={"status": LifecycleStatus.draft})
    with pytest.raises(ValueError, match="active criteria"):
        validate_acceptance_report(
            report, criteria=draft_criteria, evaluation_set=evaluation_set
        )

    unfrozen = evaluation_set.model_copy(update={"frozen": False})
    with pytest.raises(ValueError, match="frozen"):
        validate_acceptance_report(report, criteria=criteria, evaluation_set=unfrozen)

    missing_unseen = evaluation_set.model_copy(
        update={"counts": {"development": 5}}
    )
    with pytest.raises(ValueError, match="unseen_acceptance"):
        validate_acceptance_report(
            report, criteria=criteria, evaluation_set=missing_unseen
        )

    # Criteria and the sample set are mandatory: checking only one side leaves
    # the other half of the acceptance contract unverified (r5-plan item 6).
    with pytest.raises(TypeError):
        validate_acceptance_report(report)
    with pytest.raises(TypeError):
        validate_acceptance_report(report, criteria=criteria)


def test_versioned_ref_parser_matches_pattern():
    assert VersionedRef.model_validate("x@r1") == VersionedRef(id="x", revision="r1")
    for bad in ("x", "x@r1@r2", "x @r1", "@r1", "x@"):
        with pytest.raises(ValueError):
            VersionedRef.model_validate(bad)
    # Object form must obey the same constraint, otherwise it serializes to a
    # string that cannot be parsed back (r5-plan item 6).
    with pytest.raises(ValueError, match="must not contain"):
        VersionedRef(id="a@b", revision="r1")
    with pytest.raises(ValueError, match="must not contain"):
        VersionedRef(id="a", revision="r@1")
    with pytest.raises(ValueError, match="must not contain"):
        VersionedRef(id="a b", revision="r1")


def test_schema_has_id_and_open_enum_anyof():
    aggregation = json.loads((SCHEMA / "Aggregation.json").read_text())
    assert aggregation["$id"] == "dataagent-contracts/0.1/core/Aggregation"
    assert "anyOf" in aggregation
    patterns = [entry.get("pattern") for entry in aggregation["anyOf"]]
    assert any(pattern and "\\." in pattern for pattern in patterns)
    issue = json.loads((SCHEMA / "Issue.json").read_text())
    assert issue["$id"] == "dataagent-contracts/0.1/core/Issue"
    assert "severity" in issue["required"]
    assert "retryable" in issue["required"]


def test_examples_validate_against_generated_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    mapping = {
        "assessment-unknown.json": "Assessment",
        "computed-result.json": "ComputedResult",
        "extraction-partial.json": "CapabilityResult",
        "needs-input.json": "CapabilityResult",
        "semantic-draft-rule.json": "SemanticDraft",
    }
    examples = ROOT / "examples" / "s0"
    for filename, schema_name in mapping.items():
        schema = json.loads((SCHEMA / f"{schema_name}.json").read_text())
        instance = json.loads((examples / filename).read_text())
        jsonschema.Draft202012Validator(schema).validate(instance)


def test_completeness_fixture_is_used():
    # Keep samples.py imports exercised so this file fails loudly if fixtures drift.
    assert completeness().declared_scope
    assert asset().kind == "file"
    assert Verdict.pass_.value == "pass"


def test_json_pointer_selector_supports_rfc6901_empty_root():
    # RFC 6901: "" is the whole document, "/" is the empty key. The old
    # contract rewrote "" to "/" and could not express the root at all.
    assert JsonPointerSelector(pointer="").pointer == ""
    assert JsonPointerSelector(pointer="/").pointer == "/"
    assert JsonPointerSelector(pointer="/a~1b/m~0n/0").pointer == "/a~1b/m~0n/0"
    for bad in ("a", "a/b", "~1"):
        with pytest.raises(ValidationError):
            JsonPointerSelector(pointer=bad)


def test_generated_selector_schema_accepts_root_and_empty_key():
    import re

    schema = json.loads((SCHEMA / "Selector.json").read_text())
    defs = schema["$defs"]
    refs = {entry["$ref"].rsplit("/", 1)[-1] for entry in schema["oneOf"]}
    assert {"JsonPointerSelector", "TextSpanSelector"} <= refs
    pattern = defs["JsonPointerSelector"]["properties"]["pointer"]["pattern"]
    assert re.fullmatch(pattern, "")
    assert re.fullmatch(pattern, "/")
    assert re.fullmatch(pattern, "/rows/0")
    assert not re.fullmatch(pattern, "a")
    assert defs["TextSpanSelector"]["properties"]["unit_ref"]["minLength"] == 1


def _document_unit(unit_type: str) -> DocumentUnitRef:
    return DocumentUnitRef(
        asset=asset("document_unit", "asset:unit"),
        parent_document_ref=VersionedRef(id="doc:1", revision="r1"),
        unit_type=unit_type,
        ordinal_path="1",
        content_ref="sha256:" + "0" * 64,
        anchors=[anchor()],
    )


def test_document_unit_type_uses_dotted_namespaces():
    for allowed in ("chapter", "section", "clause", "item", "table", "paragraph"):
        assert _document_unit(allowed).unit_type == allowed
    assert _document_unit("acme.clause").unit_type == "acme.clause"
    for rejected in ("acme:clause", "clause:", "acme.Clause", "acme", "acme..clause"):
        with pytest.raises(ValidationError):
            _document_unit(rejected)
