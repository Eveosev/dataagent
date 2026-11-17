"""MCP entry skeleton: stdlib NDJSON JSON-RPC (initialize/tools/list/tools/call).

Layer packages provide their registry and invoke; this module owns the wire
protocol so all three layers behave identically.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from dataagent_contracts.core import CallContext, CapabilityStatus

from dataagent_runtime.policy.context import (
    ContextResolutionError,
    resolve_context,
)

PROTOCOL_VERSION = "2024-11-05"
CONTEXT_SCHEMA = {
    "type": "object",
    "description": (
        "Optional caller hint: request_id, authorization_ref, task_ref. "
        "The host _meta channel and the host environment "
        "are authoritative; subject, purpose, scope and kernel call "
        "identity are resolved by the runtime, never taken from here."
    ),
    "properties": {
        "request_id": {"type": "string"},
        "authorization_ref": {"type": "string"},
        "requester_ref": {"type": "string"},
        "task_ref": {"type": "string", "description": "'<id>@<revision>'"},
        "expected_revision": {"type": "string"},
    },
    "required": [],
}


def tools_payload(
    list_operations: Callable[[], list[Any]],
) -> list[dict[str, Any]]:
    tools = []
    for spec in list_operations():
        schema = spec.input_model.model_json_schema(mode="validation")
        schema.setdefault("properties", {})["context"] = CONTEXT_SCHEMA
        # R1: ``context`` is optional. The resolver falls back to the host
        # _meta -> host environment -> local-owner chain, so a client that
        # has no context can still call; authority never comes from here.
        schema["required"] = [
            name for name in schema.get("required", []) if name != "context"
        ]
        tools.append(
            {
                "name": spec.operation,
                "description": f"[{spec.capability_id}] {spec.description}",
                "inputSchema": schema,
                "annotations": {
                    "title": f"{spec.capability_id} {spec.operation}",
                    "readOnlyHint": not spec.writes,
                    "destructiveHint": spec.destructive,
                    "idempotentHint": True if not spec.writes else bool(spec.idempotent),
                    "openWorldHint": False,
                },
            }
        )
    return tools


def _ok(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _context(params: dict[str, Any], arguments: dict[str, Any]) -> CallContext | None:
    """Compatibility seam: the resolved ``CallContext`` for a tools/call.

    Kept for callers/tests that only need the context object; authority is
    resolved by :func:`dataagent_runtime.policy.context.resolve_context`,
    with ``_meta`` first, then the host environment, then local-owner.
    ``arguments.context`` is a hint only. ``None`` is returned only on the
    legacy rollback path when no context was supplied at all.
    """

    try:
        return resolve_context(
            host_meta=params.get("_meta"),
            argument_context=arguments.get("context"),
        ).context
    except ContextResolutionError:
        return None


def _failure_payload(message: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "issues": [
            {
                "code": "invalid_input",
                "severity": "error",
                "message": message,
                "retryable": False,
            }
        ],
    }


def handle(
    message: dict[str, Any],
    *,
    server_name: str,
    server_version: str,
    list_operations: Callable[[], list[Any]],
    invoke: Callable[[str, dict[str, Any] | None, Any], Any],
) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return _ok(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": server_name, "version": server_version},
            },
        )
    if method in {"notifications/initialized", "initialized"}:
        return None
    if method == "ping":
        return _ok(request_id, {})
    if method == "tools/list":
        return _ok(request_id, {"tools": tools_payload(list_operations)})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error(request_id, -32602, "tools/call requires name and arguments")
        try:
            context = resolve_context(
                host_meta=params.get("_meta"),
                argument_context=arguments.get("context"),
            )
        except ContextResolutionError as exc:
            return _ok(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                _failure_payload(f"context resolution failed: {exc}"),
                                ensure_ascii=False,
                            ),
                        }
                    ],
                    "isError": True,
                },
            )
        payload = {key: value for key, value in arguments.items() if key != "context"}
        result = invoke(name, payload, context)
        return _ok(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result.model_dump(mode="json"), ensure_ascii=False),
                    }
                ],
                "isError": result.status is CapabilityStatus.failed,
            },
        )
    return _error(request_id, -32601, f"method not found: {method}")


def serve(
    *,
    server_name: str,
    server_version: str,
    list_operations: Callable[[], list[Any]],
    invoke: Callable[[str, dict[str, Any] | None, Any], Any],
    validate: Callable[[], None] | None = None,
) -> int:
    if validate is not None:
        try:
            validate()
        except Exception as exc:  # noqa: BLE001 - fail fast, but on stderr
            print(f"{server_name}: startup validation failed: {exc}", file=sys.stderr)
            return 1
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(_error(None, -32700, f"parse error: {exc.msg}"), ensure_ascii=False),
                flush=True,
            )
            continue
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            print(
                json.dumps(_error(None, -32600, "invalid request"), ensure_ascii=False),
                flush=True,
            )
            continue
        try:
            response = handle(
                message,
                server_name=server_name,
                server_version=server_version,
                list_operations=list_operations,
                invoke=invoke,
            )
        except Exception as exc:  # noqa: BLE001 - a bad call must not kill the server
            response = _error(message.get("id"), -32603, f"internal error: {type(exc).__name__}")
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0
