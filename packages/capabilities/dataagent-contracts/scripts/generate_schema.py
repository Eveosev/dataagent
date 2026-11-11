#!/usr/bin/env python3
"""Generate JSON Schema for every S0 core type.

Deterministic: sorted keys, stable file names, digest index. ``--check`` fails
when the committed output differs from a fresh generation (CI gate G3).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dataagent_contracts import core  # noqa: E402
from dataagent_contracts import environment, intake, ontology, workflow  # noqa: E402
from dataagent_contracts.core import (  # noqa: E402
    EMBEDDED_TYPES,
    CORE_TYPES,
    Selector,
)
from dataagent_contracts.core.vocab import (  # noqa: E402
    OPEN_NAMESPACE_PATTERN,
    AccessOutcome,
    Aggregation,
    CapabilityStatus,
    CompletenessExtent,
    EgressOutcome,
    EvidenceType,
    FieldValueStatus,
    LifecycleStatus,
    Severity,
    SplitRole,
    StandardErrorCode,
    TraceEventType,
    Verdict,
)

OUT = ROOT / "schema" / "generated"

# Generics are exported with a representative binding; consumers substitute.
GENERIC_BINDINGS: dict[str, Any] = {
    "CapabilityResult": core.CapabilityResult[dict[str, Any]],
    "Assessment": core.Assessment[str],
}

ENUM_TYPES = (
    CapabilityStatus,
    StandardErrorCode,
    Severity,
    CompletenessExtent,
    FieldValueStatus,
    Aggregation,
    EvidenceType,
    TraceEventType,
    Verdict,
    SplitRole,
    LifecycleStatus,
    AccessOutcome,
    EgressOutcome,
)


def _dump(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "$id": f"dataagent-contracts/0.1/core/{name}",
        "$comment": f"generated from dataagent_contracts.core:{name}; do not edit",
        **schema,
    }


def build() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in CORE_TYPES:
        if name in GENERIC_BINDINGS:
            schema = GENERIC_BINDINGS[name].model_json_schema(mode="serialization")
        elif name == "Selector":
            schema = TypeAdapter(Selector).json_schema(mode="serialization")
        else:
            model = getattr(core, name)
            assert isinstance(model, type) and issubclass(model, BaseModel), name
            schema = model.model_json_schema(mode="serialization")
        out[name] = _dump(name, schema)
    for name in EMBEDDED_TYPES:
        model = getattr(core, name)
        out[name] = _dump(name, model.model_json_schema(mode="serialization"))
    open_enums = {Aggregation, EvidenceType, TraceEventType}
    for enum_type in ENUM_TYPES:
        if enum_type in open_enums:
            schema = {
                "title": enum_type.__name__,
                "anyOf": [
                    {"type": "string", "enum": [m.value for m in enum_type]},
                    {
                        "type": "string",
                        "description": "Dotted namespaced extension value",
                        "pattern": OPEN_NAMESPACE_PATTERN.pattern
                    },
                ],
            }
        else:
            schema = {
                "title": enum_type.__name__,
                "type": "string",
                "enum": [m.value for m in enum_type],
            }
        out[enum_type.__name__] = _dump(enum_type.__name__, schema)
    for module in (environment, intake, ontology, workflow):
        namespace = module.__name__.rsplit('.', 1)[-1]
        for name, model in sorted(vars(module).items()):
            if not isinstance(model, type) or not issubclass(model, BaseModel):
                continue
            if model.__module__ != module.__name__:
                continue
            out[f'{namespace}.{name}'] = {
                '$id': f'dataagent-contracts/0.1/{namespace}/{name}',
                '$comment': f'generated from {module.__name__}:{name}; do not edit',
                **model.model_json_schema(mode='serialization'),
            }
    return out


def render(schemas: dict[str, dict[str, Any]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in sorted(schemas):
        files[f"{name}.json"] = json.dumps(
            schemas[name], ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
    index = {
        "package": "dataagent-contracts",
        "version": "0.1.0",
        "core_type_count": len(CORE_TYPES),
        "concrete_type_count": len(CORE_TYPES) - len(GENERIC_BINDINGS),
        "files": {
            f"{name}.json": "sha256:" + hashlib.sha256(files[f"{name}.json"].encode()).hexdigest()
            for name in sorted(schemas)
        },
    }
    files["index.json"] = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return files


def check(files: dict[str, str]) -> list[str]:
    problems = []
    existing = {p.name for p in OUT.glob("*.json")}
    expected = set(files)
    for missing in sorted(expected - existing):
        problems.append(f"missing generated schema: {missing}")
    for extra in sorted(existing - expected):
        problems.append(f"stale generated schema: {extra}")
    for name, content in sorted(files.items()):
        path = OUT / name
        if path.exists() and path.read_text(encoding="utf-8") != content:
            problems.append(f"out of date: {name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed schema is current")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write generated schema to this directory instead of schema/generated",
    )
    args = parser.parse_args()

    files = render(build())
    if args.check:
        problems = check(files)
        if problems:
            for problem in problems:
                print(problem, file=sys.stderr)
            return 1
        print(f"schema OK: {len(files) - 1} files")
        return 0

    out = args.out or OUT
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} files to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
