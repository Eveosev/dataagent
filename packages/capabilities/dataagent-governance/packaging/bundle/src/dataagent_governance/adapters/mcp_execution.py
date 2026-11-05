"""MCP client execution adapter skeleton (stage 2, DA11.4)."""

from __future__ import annotations

from typing import Any

from dataagent_governance.runtime.errors import dependency_unavailable


class McpExecutionAdapter:
    """Raises until stage 2 wires real MCP client transports."""

    def run(self, bundle_ref: str, operation: str, payload: dict[str, Any]) -> Any:
        raise dependency_unavailable(
            "MCP execution of external bundles arrives in stage 2 (DA11.4); "
            "S0 acceptance runs on deliveries supplied by the caller",
            action="pass deliveries explicitly, or wait for the stage-2 adapter",
        )
