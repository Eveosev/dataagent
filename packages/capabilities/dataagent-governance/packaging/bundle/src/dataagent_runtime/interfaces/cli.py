"""CLI skeleton: argv operation + stdin JSON, stdout CapabilityResult."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from dataagent_contracts.core import CapabilityStatus

USAGE = """usage: python -m <package>.interfaces.cli <operation>
       python -m <package>.interfaces.cli --list

stdin: {"input": {...}, "context": {...}} or {"...input fields...", "context": {...}}
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
    invoke: Callable[[str, dict[str, Any] | None, dict[str, Any]], Any],
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
    if context is None:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "issues": [
                        {
                            "code": "invalid_input",
                            "severity": "error",
                            "message": "CallContext is required in the 'context' field",
                            "retryable": False,
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 1
    result = invoke(operation, payload, context)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    return 1 if result.status is CapabilityStatus.failed else 0
