"""Structured model call boundary (08 §4.3 egress hook)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InferencePort(Protocol):
    """Two-phase inference boundary; S0 only ships ``agent_provided``."""

    def infer(self, request: dict[str, Any]) -> dict[str, Any]: ...
