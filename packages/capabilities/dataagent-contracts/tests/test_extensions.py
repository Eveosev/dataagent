"""P1-7: the explicit, optional ``extensions`` map on core models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dataagent_contracts.core import CallContext, VersionedRef

from samples import sample_instances


def test_extensions_roundtrip():
    instance = sample_instances()["CallContext"].model_copy(
        update={"extensions": {"acme.tier": {"tier": "gold"}}}
    )
    payload = instance.model_dump_json()
    restored = CallContext.model_validate_json(payload)
    assert restored == instance
    assert restored.extensions == {"acme.tier": {"tier": "gold"}}


def test_unknown_top_level_field_still_rejected():
    base = sample_instances()["CallContext"].model_dump()
    with pytest.raises(ValidationError):
        CallContext.model_validate({**base, "vendor_extension": 1})


def test_versioned_ref_has_no_extensions():
    ref = VersionedRef(id="a", revision="r1")
    assert "extensions" not in ref.model_dump()
    assert ref.model_dump_json() == '"a@r1"'


def test_every_core_model_exposes_extensions_except_versioned_ref():
    for name, instance in sample_instances().items():
        if name == "VersionedRef":
            continue
        assert "extensions" in type(instance).model_fields, name
