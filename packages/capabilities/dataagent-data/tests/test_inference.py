from __future__ import annotations

from dataagent_data.adapters.inference import AgentProvidedInference


def test_missing_callback_is_explicit():
    from dataagent_runtime.errors import CapabilityError

    adapter = AgentProvidedInference()
    try:
        adapter.infer({"kind": "demo"})
    except CapabilityError as exc:
        assert exc.code.value == "dependency_unavailable"
    else:  # pragma: no cover
        raise AssertionError("expected dependency_unavailable")


def test_callback_result_is_returned():
    adapter = AgentProvidedInference(provider=lambda request: {"ok": request["kind"]})
    assert adapter.infer({"kind": "demo"}) == {"ok": "demo"}
