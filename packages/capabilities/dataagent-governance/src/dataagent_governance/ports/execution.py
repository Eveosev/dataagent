"""Execution port (stage 2, DA11.4 regression over MCP clients)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExecutionPort(Protocol):
    """Pull up a bundle under test through an MCP client adapter.

    S0 does not implement this: candidates and baselines must run on the same
    frozen samples (08 §6). The local adapter raises
    ``dependency_unavailable`` until stage 2.
    """

    def run(self, bundle_ref: str, operation: str, payload: dict[str, Any]) -> Any: ...
