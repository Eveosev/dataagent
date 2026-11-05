"""MCP entrypoint for the application layer (07 §3, based on dataagent-runtime)."""

from __future__ import annotations

import sys

from dataagent_runtime.interfaces.mcp_server import serve

from dataagent_application.registry import list_operations, validate_registry


def main() -> int:
    if "--validate-only" in sys.argv:
        validate_registry()
        print(f"registry OK: {len(list_operations())} operations")
        return 0
    return serve(
        server_name="dataagent-application",
        server_version="0.1.0",
        list_operations=list_operations,
        invoke=_invoke,
        validate=validate_registry,
    )


def _invoke(operation: str, payload, context):
    from dataagent_runtime.invoke import invoke

    return invoke(operation, payload, context)


if __name__ == "__main__":
    raise SystemExit(main())
