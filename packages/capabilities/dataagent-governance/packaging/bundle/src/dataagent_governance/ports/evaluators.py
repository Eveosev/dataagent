"""Evaluator port (08 §5.3: deterministic comparators)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EvaluatorPort(Protocol):
    """Compare a delivery against gold expectations deterministically.

    Model-assisted scoring does not enter S0 (08 §5.3).
    """

    def compare(self, criteria: dict[str, Any], case: dict[str, Any], delivery: dict[str, Any]) -> Any: ...
