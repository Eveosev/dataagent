"""Round 5: application-layer fields on ``Assessment`` / ``ComputedResult``.

07 §5.1 / §5.2: ``Assessment.evidence`` (structured evidence for a verdict)
and ``ComputedResult.sql_digest`` + ``ComputedResult.engine_binding`` are
additive 0.1.x fields consumed by the application layer (and later DA11 /
DA12). These tests pin the shapes without breaking older payloads.
"""

from __future__ import annotations

import pytest

from dataagent_contracts.core import (
    Assessment,
    ComputedResult,
    EngineBinding,
    EvidenceRef,
    TimeRange,
    Verdict,
    VersionedRef,
)


def _completeness() -> dict:
    return {"extent": "complete_in_declared_scope", "declared_scope": "sql execution"}


def test_assessment_accepts_structured_evidence():
    evidence = EvidenceRef(
        id="ev-amount",
        evidence_type="extracted_value",
        value=5200,
        obtained_by="da07.5.1/evaluate_scalar_expression",
    )
    assessment = Assessment[Verdict](
        assessment_id="as-1",
        target_ref=VersionedRef(id="rule-1", revision="r1"),
        verdict=Verdict.fail,
        basis_refs=["ev-amount"],
        evidence=[evidence],
    )
    assert assessment.evidence[0].value == 5200
    assert assessment.model_dump(mode="json")["evidence"][0]["evidence_type"] == "extracted_value"


def test_assessment_evidence_defaults_to_empty_and_is_backward_compatible():
    assessment = Assessment[Verdict](
        assessment_id="as-2",
        target_ref=VersionedRef(id="rule-1", revision="r1"),
        verdict=Verdict.unknown,
    )
    assert assessment.evidence == []
    # Older payloads without the field still validate.
    legacy = {
        "assessment_id": "as-3",
        "target_ref": "rule-1@r1",
        "verdict": "unknown",
    }
    assert Assessment[Verdict].model_validate(legacy).evidence == []


def test_computed_result_accepts_sql_digest_and_engine_binding():
    result = ComputedResult(
        result_id="res-1",
        target_ref=VersionedRef(id="req-1", revision="r1"),
        form="scalar",
        value=42,
        grain="day",
        evidence_refs=["ev-1"],
        completeness=_completeness(),
        sql_digest="sha256:" + "0" * 64,
        engine_binding=EngineBinding(
            engine_id="duckdb", engine_version="2.0.0", wheel_digest="sha256:" + "1" * 64
        ),
    )
    assert result.sql_digest.startswith("sha256:")
    assert result.engine_binding.engine_id == "duckdb"


def test_computed_result_engine_fields_default_to_none():
    result = ComputedResult(
        result_id="res-2",
        target_ref=VersionedRef(id="req-1", revision="r1"),
        form="table",
        table_ref=VersionedRef(id="tbl-1", revision="r1"),
        grain="row",
        evidence_refs=["ev-1"],
        time_range=TimeRange(),
        completeness=_completeness(),
    )
    assert result.sql_digest is None
    assert result.engine_binding is None
    legacy = {
        "result_id": "res-3",
        "target_ref": "req-1@r1",
        "form": "scalar",
        "value": 7,
        "grain": "row",
        "evidence_refs": ["ev-1"],
        "completeness": _completeness(),
    }
    assert ComputedResult.model_validate(legacy).engine_binding is None


def test_engine_binding_requires_version_and_id():
    with pytest.raises(ValueError):
        EngineBinding(engine_id="", engine_version="1.0.0")
    with pytest.raises(ValueError):
        EngineBinding(engine_id="duckdb", engine_version="")
