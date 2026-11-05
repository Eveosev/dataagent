"""Application-layer operation registry.

The shared runtime (``dataagent-runtime``) owns the registry storage; this
module only lists the operation modules to import and pins the catalog
snapshot consistency check (07 §3: "注册表启动时校验，规则同 06 §4.1").
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dataagent_runtime import get_spec  # noqa: F401 - re-export
from dataagent_runtime.registry import (
    list_operations as _runtime_list_operations,
    registry_errors as _runtime_registry_errors,
)

BUILTIN_MODULES = (
    "dataagent_application.planning.requirements",
    "dataagent_application.planning.expressions",
    "dataagent_application.execution.expressions",
    "dataagent_application.execution.engines",
    "dataagent_application.execution.sql",
    "dataagent_application.presentation.workbooks",
    "dataagent_application.presentation.reports",
)

# Wheel-safe: the snapshot ships inside the package.
DEFAULT_CATALOG = Path(__file__).resolve().parent / "catalog-snapshot.json"
CATALOG_ENV = "DATAAGENT_APPLICATION_CATALOG"

S0_ATOMS = 13


def load_operations() -> None:
    import importlib

    for module in BUILTIN_MODULES:
        importlib.import_module(module)


def list_operations():  # noqa: F811 - application-aware re-export
    load_operations()
    return _runtime_list_operations()


def load_catalog(path: str | os.PathLike[str] | None = None) -> dict:
    catalog_path = Path(path or os.environ.get(CATALOG_ENV) or DEFAULT_CATALOG)
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def registry_errors(catalog: dict | None = None) -> list[str]:
    load_operations()
    return _runtime_registry_errors(catalog, expected_atoms=S0_ATOMS)


def validate_registry() -> None:
    errors = registry_errors(load_catalog())
    if errors:
        raise RuntimeError("registry/catalog consistency failed:\n" + "\n".join(errors))
