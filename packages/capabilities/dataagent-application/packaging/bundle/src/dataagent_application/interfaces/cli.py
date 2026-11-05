"""CLI entrypoint for the application layer.

Unified argv mode (12-unified-cli-research §5.3) — ``list``, ``run <op>``
with ``--input-file`` / ``--set`` / ``--set-json`` / ``--ref`` /
``--proposal-file`` / ``--authorize`` / ``--detail``, summary JSON on
stdout and the full result under ``<data_root>/results/`` — plus the legacy
stdin mode (``<op>`` alone, JSON body on stdin) for the existing
black-box acceptance flows.
"""

from __future__ import annotations

from dataagent_runtime.interfaces.unified import LayerHooks, main as unified_main

from dataagent_application.registry import list_operations, validate_registry
from dataagent_application.interfaces.mcp_server import _invoke

USAGE = """usage: python -m dataagent_application.interfaces.cli list
       python -m dataagent_application.interfaces.cli run <op> [--input-file F] [--set k=v] ...
       python -m dataagent_application.interfaces.cli <op> --help
       python -m dataagent_application.interfaces.cli <operation>        (legacy: JSON on stdin)
       python -m dataagent_application.interfaces.cli --list            (legacy: JSON list)
"""


def _runtime_factory():
    from dataagent_runtime.runtime import default_runtime

    return default_runtime()


def main(argv: list[str] | None = None) -> int:
    hooks = LayerHooks(
        layer="app",
        list_operations=list_operations,
        invoke=_invoke,
        validate=validate_registry,
        runtime_factory=_runtime_factory,
        program="dataagent-application",
        usage=USAGE,
    )
    return unified_main(argv, hooks=hooks)


if __name__ == "__main__":
    raise SystemExit(main())
