"""Registry wiring for the governance layer (Catalog gate, 06 §4.1 rules)."""

from __future__ import annotations

from pathlib import Path

from dataagent_runtime.registry import (
    load_catalog as _load_catalog,
    registry_errors as _registry_errors,
    validate_registry as _validate,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
# Wheel-safe: the snapshot ships inside the package, not at the repo root.
DEFAULT_CATALOG = Path(__file__).resolve().parent / "catalog-snapshot.json"

BUILTIN_MODULES = (
    "dataagent_governance.governance.access",
    "dataagent_governance.evaluation.criteria_samples",
    "dataagent_governance.evaluation.computation",
)


def load_operations() -> None:
    import importlib

    for module in BUILTIN_MODULES:
        importlib.import_module(module)


def load_catalog(path=None):  # noqa: ANN001, ANN202
    return _load_catalog(path or DEFAULT_CATALOG)


def registry_errors(catalog=None) -> list[str]:  # noqa: ANN001, ANN202
    load_operations()
    return _registry_errors(catalog or load_catalog(), expected_atoms=6)


def validate_registry(catalog=None) -> None:  # noqa: ANN001, ANN202
    errors = registry_errors(catalog)
    if errors:
        raise RuntimeError("registry/catalog consistency failed:\n" + "\n".join(errors))
