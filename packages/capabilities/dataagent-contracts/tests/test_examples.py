from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataagent_contracts.core import (
    Assessment,
    CapabilityResult,
    ComputedResult,
    ExtractedRecordRef,
    SemanticDraft,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "s0"

CASES = {
    "extraction-partial.json": lambda p: CapabilityResult[ExtractedRecordRef].model_validate(p),
    "assessment-unknown.json": lambda p: Assessment[str].model_validate(p),
    "computed-result.json": lambda p: ComputedResult.model_validate(p),
    "needs-input.json": lambda p: CapabilityResult[dict].model_validate(p),
    "semantic-draft-rule.json": lambda p: SemanticDraft.model_validate(p),
}


@pytest.mark.parametrize("filename", sorted(CASES))
def test_example_validates(filename: str):
    payload = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
    instance = CASES[filename](payload)
    assert instance is not None


def test_unknown_verdict_stays_unknown():
    payload = json.loads((EXAMPLES / "assessment-unknown.json").read_text())
    assessment = Assessment[str].model_validate(payload)
    assert assessment.verdict == "unknown"


def test_needs_input_example_carries_inference_request():
    payload = json.loads((EXAMPLES / "needs-input.json").read_text())
    result = CapabilityResult[dict].model_validate(payload)
    assert result.status.value == "needs_input"
    assert result.issues[0].inference_request["kind"] == "field_extraction"
