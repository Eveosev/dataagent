"""MCP entry for the governance layer, built on the shared runtime skeleton."""

from __future__ import annotations

from dataagent_runtime.interfaces.mcp_server import serve

from dataagent_governance import __version__
from dataagent_governance.registry import validate_registry


def _invoke(operation, payload, context):
    from dataagent_governance.runtime import default_runtime
    from dataagent_runtime.invoke import invoke

    return invoke(operation, payload, context, runtime=default_runtime())


def _list_operations():
    from dataagent_runtime.registry import list_operations

    from dataagent_governance.registry import load_operations

    load_operations()
    return list_operations()


def main() -> int:
    return serve(
        server_name="dataagent-governance",
        server_version=__version__,
        list_operations=_list_operations,
        invoke=_invoke,
        validate=validate_registry,
    )


if __name__ == "__main__":
    raise SystemExit(main())
