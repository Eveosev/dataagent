"""MCP entry for the data layer, built on the shared runtime skeleton (W1b).

The wire protocol (NDJSON JSON-RPC, initialize/tools/list/tools/call, the
CallContext precedence of review B7) is owned by
``dataagent_runtime.interfaces.mcp_server``; the application and governance
layers already delegate there. This module only wires the data layer's
registry and invoke, and keeps ``_tools`` / ``CONTEXT_SCHEMA`` reachable for
the black-box tests.
"""

from __future__ import annotations

from typing import Any

from dataagent_runtime.interfaces.mcp_server import (
    CONTEXT_SCHEMA,
    serve,
    tools_payload,
)

from dataagent_data import __version__
from dataagent_data.invoke import invoke
from dataagent_data.registry import list_operations, validate_registry

__all__ = ["CONTEXT_SCHEMA", "_tools", "main"]


def _tools() -> list[dict[str, Any]]:
    """The tools payload (kept as a module seam for the black-box tests)."""

    return tools_payload(list_operations)


def main() -> int:
    return serve(
        server_name="dataagent-data",
        server_version=__version__,
        list_operations=list_operations,
        invoke=invoke,
        validate=validate_registry,
    )


if __name__ == "__main__":
    raise SystemExit(main())
