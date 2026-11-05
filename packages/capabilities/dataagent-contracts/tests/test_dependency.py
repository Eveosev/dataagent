"""Dependency direction: contracts depend only on pydantic + stdlib."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "dataagent_contracts"
ALLOWED_THIRD_PARTY = {"pydantic", "typing_extensions"}
ALLOWED_INTERNAL_ROOTS = {"dataagent_contracts"}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_contracts_do_not_import_capability_implementation():
    offenders = []
    for path in SRC.rglob("*.py"):
        roots = imported_roots(path)
        forbidden = {r for r in roots if r not in ALLOWED_THIRD_PARTY | ALLOWED_INTERNAL_ROOTS}
        # stdlib roots are safe: detect them via importlib metadata at runtime.
        stdlib = {r for r in forbidden if r in _stdlib_modules()}
        forbidden -= stdlib
        if forbidden:
            offenders.append((str(path.relative_to(SRC)), sorted(forbidden)))
    assert not offenders, f"contracts must not import implementation packages: {offenders}"


def test_no_dataagent_data_import():
    for path in SRC.rglob("*.py"):
        assert "dataagent_data" not in imported_roots(path), path


def _stdlib_modules() -> set[str]:
    import sys

    return set(sys.stdlib_module_names)
