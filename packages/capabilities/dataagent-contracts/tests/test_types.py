from __future__ import annotations

import json

import pytest

from pydantic import TypeAdapter

from dataagent_contracts.core import (
    Assessment,
    CapabilityResult,
    CORE_TYPES,
    CONCRETE_TYPES,
    GENERIC_TYPES,
)
from dataagent_contracts.core.refs import Selector
from dataagent_contracts.core.semantics import TimeRange

from samples import sample_instances


def test_type_inventory_is_frozen_at_37():
    assert len(CONCRETE_TYPES) == 35
    assert len(GENERIC_TYPES) == 2
    assert len(CORE_TYPES) == 37
    assert len(set(CORE_TYPES)) == 37


def test_every_core_type_has_a_sample():
    samples = sample_instances()
    assert set(samples) == set(CORE_TYPES)


@pytest.mark.parametrize("name", CORE_TYPES)
def test_roundtrip(name: str):
    instance = sample_instances()[name]
    payload = instance.model_dump_json()
    if name == "CapabilityResult":
        restored = CapabilityResult[dict].model_validate_json(payload)
    elif name == "Assessment":
        restored = Assessment[str].model_validate_json(payload)
    else:
        restored = type(instance).model_validate_json(payload)
    assert restored == instance
    # The JSON must not leak the internal "<id>@<revision>" object form.
    data = json.loads(payload)
    if name == "VersionedRef":
        assert data == "rule:12@r2"
    if name == "ComputedResult":
        assert data["target_ref"] == "metric:1@r1"
    if name == "SemanticDraft":
        assert data["sources"][0]["selector"]["kind"] == "pdf_text_span"
        assert data["effective_time"]["from"]


def test_selector_roundtrip_all_variants():
    from dataagent_contracts.core import (
        ExcelCellSelector,
        JsonPointerSelector,
        PdfBBoxSelector,
        PdfTextSpanSelector,
        RecordKeySelector,
        TextSpanSelector,
    )

    adapter = TypeAdapter(Selector)
    variants = [
        PdfBBoxSelector(page=1, bbox=(0, 0, 10, 10)),
        PdfTextSpanSelector(page=1, char_start=0, char_end=2),
        TextSpanSelector(unit_ref="unit:1", char_start=0, char_end=2),
        JsonPointerSelector(pointer="/a/b"),
        ExcelCellSelector(sheet="Sheet1", range="A1:C3"),
        RecordKeySelector(keys={"id": 1}, field="v"),
    ]
    for variant in variants:
        payload = adapter.dump_json(variant)
        assert adapter.validate_json(payload) == variant


def test_time_range_serializes_from_key():
    value = TimeRange(**{"from": "2026-01-01T00:00:00Z", "to": "2026-02-01T00:00:00Z"})
    assert json.loads(value.model_dump_json()) == {
        "from": "2026-01-01T00:00:00Z",
        "to": "2026-02-01T00:00:00Z",
        "extensions": None,
    }
