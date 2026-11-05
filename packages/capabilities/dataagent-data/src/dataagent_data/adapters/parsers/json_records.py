"""JSON / JSONL parsing that preserves nested records."""

from __future__ import annotations

import json
from typing import Any

from dataagent_data.adapters.parsers.excel import infer_scalar_type
from dataagent_runtime.errors import invalid_input


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _records(value: Any, records_path: str | None) -> list[Any]:
    # RFC 6901: "" is the whole document and "/" selects the "" key.
    if records_path not in (None, ""):
        if not records_path.startswith("/"):
            raise invalid_input(
                f"records_path must be empty or start with '/': {records_path!r}"
            )
        current = value
        for raw in records_path.split("/")[1:]:
            token = _unescape(raw)
            if isinstance(current, dict):
                if token not in current:
                    raise invalid_input(f"records_path not found: {records_path}")
                current = current[token]
            elif isinstance(current, list):
                try:
                    index = int(token)
                except ValueError as exc:
                    raise invalid_input(
                        f"records_path array token is not an index: {token!r}"
                    ) from exc
                if index < 0 or index >= len(current):
                    raise invalid_input(f"records_path index out of range: {index}")
                current = current[index]
            else:
                raise invalid_input(f"records_path cannot descend into {type(current).__name__}")
        value = current
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    raise invalid_input("JSON root must be an object, an array, or records_path must select one")


def _paths(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(value, dict):
        if not value:
            out.append((prefix or "/", "object"))
        for key, item in value.items():
            out.extend(_paths(item, f"{prefix}/{_escape(str(key))}"))
    elif isinstance(value, list):
        out.append((prefix or "/", "array"))
    else:
        out.append((prefix or "/", infer_scalar_type(value)))
    return out


def parse_json_records(
    payload: bytes,
    *,
    fmt: str = "auto",
    records_path: str | None = None,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    try:
        text = payload.decode(encoding)
    except UnicodeDecodeError as exc:
        raise invalid_input(f"cannot decode JSON as {encoding}: {exc.reason}") from exc

    bad_records: list[dict[str, Any]] = []
    records: list[Any] = []
    detected = fmt
    if fmt in {"auto", "jsonl"}:
        lines = [line for line in text.splitlines() if line.strip()]
        if fmt == "jsonl" or (fmt == "auto" and len(lines) > 1 and lines[0].lstrip().startswith(("{", "["))):
            # JSONL: one JSON value per line. A single-line JSON document is
            # parsed below instead, so try whole-document first in auto mode.
            if fmt == "jsonl":
                detected = "jsonl"
                for number, line in enumerate(lines, start=1):
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        bad_records.append({"line": number, "reason": exc.msg})
            else:
                detected = "json"
    if not records:
        try:
            document = json.loads(text)
            detected = "json"
            records = _records(document, records_path)
        except json.JSONDecodeError:
            if fmt == "json" or not lines:
                try:
                    raise
                except json.JSONDecodeError as exc:
                    raise invalid_input(f"invalid JSON: {exc.msg} at line {exc.lineno}") from exc
            detected = "jsonl"
            for number, line in enumerate(lines, start=1):
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    bad_records.append({"line": number, "reason": exc.msg})

    nested: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            bad_records.append({"record": repr(record)[:80], "reason": "not_an_object"})
            continue
        nested.extend({"path": path, "value_type": kind} for path, kind in _paths(record))

    # Union of paths; a later record may add fields.
    fields: dict[str, str] = {}
    for item in nested:
        fields[item["path"]] = item["value_type"]
    if not records:
        raise invalid_input("no JSON records found")
    return {
        "records": records,
        "record_count": len(records),
        "bad_records": bad_records,
        "fields": [{"path": path, "value_type": kind} for path, kind in fields.items()],
        "format": detected,
    }
