"""CLI skeleton: argv operation + stdin JSON, stdout CapabilityResult.

The stdin body may carry ``context``; it is a hint and is resolved through
the shared context resolver (host environment, then local-owner when no
context is supplied). The old ``context is required`` behaviour remains
only under ``DATAAGENT_CONTEXT_RESOLVER=legacy``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from dataagent_contracts.core import CapabilityStatus

from dataagent_runtime.policy.context import (
    ContextResolutionError,
    resolve_context,
)

USAGE = """usage: python -m <package>.interfaces.cli <operation>
       python -m <package>.interfaces.cli --list

stdin: {"input": {...}, "context": {...}} or {"...input fields...", "context": {...}}
context is optional; the host environment, then local-owner, supplies authority
stdout: CapabilityResult JSON
exit: 0 for ok/partial/needs_input, 1 for failed, 2 for usage errors
"""


def _split_body(body: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not isinstance(body, dict):
        raise ValueError("stdin JSON must be an object")
    if isinstance(body.get("input"), dict):
        context = body.get("context")
        return body["input"], context if isinstance(context, dict) else None
    payload = dict(body)
    context = payload.pop("context", None)
    return payload, context if isinstance(context, dict) else None


def operations_json(list_operations: Callable[[], list[Any]]) -> str:
    """The legacy ``--list`` payload (one entry per registered operation)."""

    return json.dumps(
        [
            {
                "operation": spec.operation,
                "capability_id": spec.capability_id,
                "source_file": spec.source_file,
            }
            for spec in list_operations()
        ],
        ensure_ascii=False,
        indent=2,
    )


def main(
    argv: list[str] | None = None,
    *,
    list_operations: Callable[[], list[Any]],
    invoke: Callable[[str, dict[str, Any] | None, Any], Any],
    validate: Callable[[], None] | None = None,
    usage: str = USAGE,
    program: str = "dataagent",
) -> int:
    if validate is not None:
        try:
            validate()
        except Exception as exc:  # noqa: BLE001 - fail fast, matching the MCP entrypoint
            print(f"{program}: startup validation failed: {exc}", file=sys.stderr)
            return 1
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print(usage, file=sys.stderr)
        return 2
    if argv[0] in {"--list", "list"}:
        print(operations_json(list_operations))
        return 0
    operation = argv[0]
    raw = sys.stdin.read()
    try:
        body = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "issues": [
                        {"code": "invalid_input", "message": f"invalid JSON on stdin: {exc.msg}"}
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 1
    if not isinstance(body, dict):
        print(
            json.dumps(
                {
                    "status": "failed",
                    "issues": [{"code": "invalid_input", "message": "stdin JSON must be an object"}],
                },
                ensure_ascii=False,
            )
        )
        return 1
    payload, context = _split_body(body)
    try:
        resolved = resolve_context(argument_context=context)
    except ContextResolutionError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "issues": [
                        {
                            "code": "invalid_input",
                            "severity": "error",
                            "message": f"context resolution failed: {exc}",
                            "retryable": False,
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 1
    result = invoke(operation, payload, resolved)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    return 1 if result.status is CapabilityStatus.failed else 0
