"""B2: the application egress gate follows the shared enforcement mode."""

from __future__ import annotations

from dataagent_runtime.enforcement import EnforcementConfig
from dataagent_runtime.runtime import Runtime

from dataagent_application.helpers import gate_inference_request

GATED = {
    "statement": "SECRET-RULE amount is below 5000",
    "fields": [{"field_id": "amount", "value_type": "number"}],
}


def _runtime(tmp_path, mode):
    return Runtime.create(
        workspace_root=tmp_path,
        data_root=tmp_path / "data",
        enforcement=EnforcementConfig(mode=mode),
    )


def test_enforce_strips_content_without_an_egress_decision(tmp_path):
    rt = _runtime(tmp_path, "enforce")
    request, issues, allowed = gate_inference_request(
        rt, dict(GATED), None, destination={"model_ref": "model:local", "deployment": "local"}
    )
    assert not allowed
    assert "SECRET-RULE" not in str(request)
    assert "fields" not in request
    assert any(i.code == "da12.egress_required" for i in issues)
    assert any("EgressDecision" in i.message for i in issues)


def test_warn_passes_content_with_a_warning(tmp_path):
    rt = _runtime(tmp_path, "warn")
    request, issues, allowed = gate_inference_request(
        rt, dict(GATED), None, destination={"model_ref": "model:local", "deployment": "local"}
    )
    assert allowed
    assert request["statement"] == GATED["statement"]
    assert any(i.code == "da12.egress_required" for i in issues)


def test_off_disables_the_gate(tmp_path):
    rt = _runtime(tmp_path, "off")
    request, issues, allowed = gate_inference_request(
        rt, dict(GATED), None, destination={"model_ref": "model:local", "deployment": "local"}
    )
    assert allowed
    assert request["statement"] == GATED["statement"]
    assert issues == []
