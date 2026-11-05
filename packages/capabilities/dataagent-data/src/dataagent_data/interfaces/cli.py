"""CLI entrypoint for the data layer.

Unified argv mode (12-unified-cli-research §5.3) — ``list``, ``run <op>``
with ``--input-file`` / ``--set`` / ``--set-json`` / ``--file`` / ``--ref`` /
``--proposal-file`` / ``--authorize`` / ``--detail``, summary JSON on
stdout and the full result under ``<data_root>/results/`` — plus the legacy
stdin mode (``<op>`` alone, JSON body on stdin) for the existing
black-box acceptance flows.
"""

from __future__ import annotations

from dataagent_data.invoke import invoke
from dataagent_data.registry import list_operations, validate_registry
from dataagent_data.runtime import default_runtime
from dataagent_runtime.interfaces.unified import LayerHooks, main as unified_main

USAGE = """usage: python -m dataagent_data.interfaces.cli list
       python -m dataagent_data.interfaces.cli run <op> [--input-file F] [--set k=v] ...
       python -m dataagent_data.interfaces.cli <op> --help
       python -m dataagent_data.interfaces.cli <operation>        (legacy: JSON on stdin)
       python -m dataagent_data.interfaces.cli --list             (legacy: JSON list)
"""


def _make_file_ref(runtime, path: str) -> dict:
    """FileRef from the file's bytes (12 §5.3 ``--file``)."""

    from dataagent_data.helpers import file_ref

    return file_ref(runtime, path).model_dump(mode="json")


def main(argv: list[str] | None = None) -> int:
    hooks = LayerHooks(
        layer="data",
        list_operations=list_operations,
        invoke=invoke,
        validate=validate_registry,
        runtime_factory=default_runtime,
        make_file_ref=_make_file_ref,
        program="dataagent-data",
        usage=USAGE,
    )
    return unified_main(argv, hooks=hooks)


if __name__ == "__main__":
    raise SystemExit(main())
