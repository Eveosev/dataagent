"""Operation registry and Catalog consistency gate (06 §4.1, shared).

Each layer package registers its own operations with the ``operation``
decorator and validates them against its catalog snapshot at startup. The
runtime itself ships zero operations.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Type

from pydantic import BaseModel

IMPLEMENTATION_REF = "dataagent-runtime/0.1.0"

DEFAULT_CATALOG_ENV = "DATAAGENT_CATALOG_SNAPSHOT"


@dataclass(frozen=True)
class OperationSpec:
    operation: str
    capability_id: str
    source_file: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    handler: Callable[..., Any]
    writes: bool = False
    description: str = ""
    idempotent: bool | None = None
    destructive: bool = False
    # Names of input-model fields that hold resource references read by this
    # operation. The access recheck (08 §4.3) resolves them against the
    # AccessDecision before the handler runs.
    resource_fields: tuple[str, ...] = ()


_SPECS: dict[str, OperationSpec] = {}
_LOADED = False


def operation(
    capability_id: str,
    *,
    input_model: Type[BaseModel],
    output_model: Type[BaseModel],
    writes: bool = False,
    description: str = "",
    idempotent: bool | None = None,
    destructive: bool = False,
    resource_fields: tuple[str, ...] = (),
):
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        module = fn.__module__
        source_file = "src/" + module.replace(".", "/") + ".py"
        spec = OperationSpec(
            operation=fn.__name__,
            capability_id=capability_id,
            source_file=source_file,
            input_model=input_model,
            output_model=output_model,
            handler=fn,
            writes=writes,
            description=description,
            idempotent=idempotent,
            destructive=destructive,
            resource_fields=tuple(resource_fields),
        )
        existing = _SPECS.get(spec.operation)
        if existing is not None and existing != spec:
            raise RuntimeError(f"duplicate operation registration: {spec.operation}")
        _SPECS[spec.operation] = spec
        return fn

    return decorator


def register(spec: OperationSpec) -> None:
    existing = _SPECS.get(spec.operation)
    if existing is not None and existing != spec:
        raise RuntimeError(f"duplicate operation registration: {spec.operation}")
    _SPECS[spec.operation] = spec


def load_operations() -> None:
    """No built-ins: each layer package imports its operation modules."""

    global _LOADED
    _LOADED = True


def list_operations() -> list[OperationSpec]:
    load_operations()
    return sorted(_SPECS.values(), key=lambda spec: (spec.capability_id, spec.operation))


def get_spec(name: str) -> OperationSpec | None:
    load_operations()
    return _SPECS.get(name)


def reset_registry() -> None:
    """Test helper: clear registrations before re-importing modules."""

    global _LOADED
    _SPECS.clear()
    _LOADED = False


def load_catalog(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    catalog_path = Path(path or os.environ.get(DEFAULT_CATALOG_ENV))
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def registry_errors(
    catalog: dict[str, Any] | None = None,
    *,
    expected_atoms: int | None = None,
) -> list[str]:
    """Consistency between registered operations and a catalog snapshot.

    ``expected_atoms`` pins the snapshot size (each layer knows its S0 count).
    """

    load_operations()
    if catalog is None:
        catalog = load_catalog()
    errors: list[str] = []
    atoms = catalog.get("atoms", [])
    if expected_atoms is not None and len(atoms) != expected_atoms:
        errors.append(f"catalog snapshot must contain {expected_atoms} atoms, got {len(atoms)}")
    catalog_ops = {a["operation"]: a for a in atoms}
    missing = sorted(set(catalog_ops) - set(_SPECS))
    extra = sorted(set(_SPECS) - set(catalog_ops))
    for name in missing:
        errors.append(f"catalog operation not registered: {name} ({catalog_ops[name]['id']})")
    for name in extra:
        errors.append(f"registered operation not in catalog: {name}")
    for name in sorted(set(catalog_ops) & set(_SPECS)):
        spec = _SPECS[name]
        atom = catalog_ops[name]
        if spec.capability_id != atom["id"]:
            errors.append(f"{name}: capability_id {spec.capability_id} != catalog {atom['id']}")
        if spec.source_file != atom["source_file"]:
            errors.append(f"{name}: source_file {spec.source_file} != catalog {atom['source_file']}")
    return errors


def validate_registry(
    catalog: dict[str, Any] | None = None,
    *,
    expected_atoms: int | None = None,
) -> None:
    errors = registry_errors(catalog, expected_atoms=expected_atoms)
    if errors:
        raise RuntimeError("registry/catalog consistency failed:\n" + "\n".join(errors))
