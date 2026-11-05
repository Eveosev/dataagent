from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InferencePort(Protocol):
    """Structured model call boundary; S0 only ships ``agent_provided``."""

    def infer(self, request: dict[str, Any]) -> dict[str, Any]: ...
