"""The Mint bundle must inherit the project's third-party dependencies."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "scripts" / "build_bundle.py"


def _builder():
    spec = importlib.util.spec_from_file_location("dataagent_data_build_bundle", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dependencies(path: Path) -> list[str]:
    return tomllib.loads(path.read_text(encoding="utf-8"))["project"]["dependencies"]


def test_bundle_dependencies_are_the_project_dependencies_without_path_sources():
    builder = _builder()
    declared = _dependencies(PACKAGE / "pyproject.toml")
    expected = [
        requirement
        for requirement in declared
        if not builder.dependency_name(requirement).startswith("dataagent-")
    ]
    assert builder.bundle_dependencies() == expected
    assert "python-docx>=1.2,<2" in expected
    assert not any(builder.dependency_name(dep).startswith("dataagent-") for dep in expected)


def test_staged_bundle_writes_every_third_party_dependency(tmp_path):
    builder = _builder()
    out = tmp_path / "bundle"
    builder.stage(out)
    staged = _dependencies(out / "pyproject.toml")
    assert staged == builder.bundle_dependencies(PACKAGE / "pyproject.toml")
    assert "python-docx>=1.2,<2" in staged
    assert not any(builder.dependency_name(dep).startswith("dataagent-") for dep in staged)
