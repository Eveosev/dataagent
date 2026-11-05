"""Observation port (stage 2, DA11.6 continuous improvement)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ObservationPort(Protocol):
    """Read trajectories, human effort and cost records."""

    def observe(self, scope_ref: str) -> dict[str, Any]: ...
