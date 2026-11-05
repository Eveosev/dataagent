"""Data-layer operation registry on the shared runtime registry (W1b).

The shared ``dataagent_runtime.registry`` holds the registrations and the
consistency gate; this module owns what is specific to the data layer: the
list of operation modules to import, the packaged catalog snapshot and the
32-atom pin. The duplicated ``dataagent_data/runtime/registry.py`` is gone.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

from dataagent_runtime.registry import (
    OperationSpec,
    operation,
    register,
    reset_registry,
)

BUILTIN_MODULES = (
    "dataagent_data.ingestion.files",
    "dataagent_data.ingestion.ocr",
    "dataagent_data.preparation.regions",
    "dataagent_data.preparation.structure",
    "dataagent_data.preparation.profiles",
    "dataagent_data.preparation.documents",
    "dataagent_data.preparation.extraction",
    "dataagent_data.semantics.metrics_rules",
    "dataagent_data.semantics.decidability",
    "dataagent_data.semantics.applicability",
    "dataagent_data.memory.traces",
)

EXPECTED_ATOMS = 32

# Wheel-safe: the snapshot ships inside the package, not at the repo root.
DEFAULT_CATALOG = Path(__file__).resolve().parent / "catalog-snapshot.json"

_LOADED = False


def load_operations() -> None:
    global _LOADED
    if _LOADED:
        return
    for module in BUILTIN_MODULES:
        importlib.import_module(module)
    _LOADED = True


def list_operations() -> list[OperationSpec]:
    from dataagent_runtime import registry as shared

    load_operations()
    return shared.list_operations()


def get_spec(name: str) -> OperationSpec | None:
    from dataagent_runtime import registry as shared

    load_operations()
    return shared.get_spec(name)


def load_catalog(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    catalog_path = Path(path or os.environ.get("DATAAGENT_CATALOG_SNAPSHOT") or DEFAULT_CATALOG)
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def registry_errors(catalog: dict[str, Any] | None = None) -> list[str]:
    from dataagent_runtime import registry as shared

    load_operations()
    catalog = catalog or load_catalog()
    return shared.registry_errors(catalog, expected_atoms=EXPECTED_ATOMS)


def validate_registry(catalog: dict[str, Any] | None = None) -> None:
    errors = registry_errors(catalog)
    if errors:
        raise RuntimeError("registry/catalog consistency failed:\n" + "\n".join(errors))


__all__ = [
    "BUILTIN_MODULES",
    "DEFAULT_CATALOG",
    "EXPECTED_ATOMS",
    "OperationSpec",
    "operation",
    "register",
    "reset_registry",
    "load_operations",
    "list_operations",
    "get_spec",
    "load_catalog",
    "registry_errors",
    "validate_registry",
]
