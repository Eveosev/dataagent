#!/usr/bin/env python3
"""Stage a self-contained Mint bundle.

The in-repo project depends on ``dataagent-contracts`` and (W1b) on
``dataagent-runtime`` by path. A Mint bundle is extracted as one directory,
so the dependencies must be vendored: the staged project ships
``src/dataagent_data``, ``src/dataagent_contracts`` and ``src/dataagent_runtime``
and drops the path sources. Third-party dependencies are read from the
repository ``pyproject.toml`` so the bundle cannot silently fall behind it.
``uv lock`` is regenerated for the staged project.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CONTRACTS = HERE.parent / "dataagent-contracts"
RUNTIME = HERE.parent / "dataagent-runtime"
DEFAULT_OUT = HERE / "packaging" / "bundle"

PYPROJECT = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dataagent-data"
version = "0.1.0"
description = "DataAgent data layer: S0 capability atoms (32) for judgment and compute flows"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.11,<3.14"
authors = [{ name = "AgentOS DataAgent" }]
dependencies = [
{dependencies}
]

[project.optional-dependencies]
ocr = ["rapidocr-onnxruntime>=1.3,<2"]
dev = ["pytest>=8"]

[tool.hatch.build.targets.wheel]
packages = ["src/dataagent_data", "src/dataagent_runtime", "src/dataagent_contracts"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
pythonpath = ["src"]
"""

_REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def dependency_name(requirement: str) -> str:
    """Return the normalized project name of a PEP 508 requirement."""
    match = _REQUIREMENT_NAME.match(requirement.strip())
    if match is None:
        raise ValueError(f"invalid dependency requirement: {requirement!r}")
    return match.group(0).lower().replace("_", "-").replace(".", "-")


def bundle_dependencies(project: Path = HERE / "pyproject.toml") -> list[str]:
    """Third-party dependencies from ``[project].dependencies``, in order.

    ``dataagent-*`` entries are path dependencies vendored under ``src/``
    (or added by the caller after staging); they must not stay in the staged
    project, where ``../dataagent-*`` does not exist.
    """
    data = tomllib.loads(project.read_text(encoding="utf-8"))
    return [
        requirement
        for requirement in data["project"]["dependencies"]
        if not dependency_name(requirement).startswith("dataagent-")
    ]


def render_pyproject(dependencies: list[str]) -> str:
    rendered = "\n".join(f"  {json.dumps(requirement)}," for requirement in dependencies)
    return PYPROJECT.replace("{dependencies}", rendered)


def stage(out: Path) -> None:
    if out.exists():
        if out.name != "bundle" or out.parent.name != "packaging":
            raise SystemExit(f"refusing to remove unexpected path: {out}")
        shutil.rmtree(out)
    (out / "src").mkdir(parents=True)
    (out / "packaging").mkdir()
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(HERE / "src" / "dataagent_data", out / "src" / "dataagent_data", ignore=ignore)
    shutil.copytree(
        CONTRACTS / "src" / "dataagent_contracts",
        out / "src" / "dataagent_contracts",
        ignore=ignore,
    )
    shutil.copytree(
        RUNTIME / "src" / "dataagent_runtime",
        out / "src" / "dataagent_runtime",
        ignore=ignore,
    )
    shutil.copy2(HERE / "packaging" / "catalog-snapshot.json", out / "packaging" / "catalog-snapshot.json")
    shutil.copy2(HERE / "packaging" / "source-ref.toml", out / "packaging" / "source-ref.toml")
    for name in ("mint.toml", ".mcp.json", "README.md"):
        shutil.copy2(HERE / name, out / name)
    shutil.copytree(HERE / "skills", out / "skills", ignore=ignore)
    (out / "pyproject.toml").write_text(
        render_pyproject(bundle_dependencies()), encoding="utf-8"
    )
    (out / ".gitignore").write_text(".venv/\n__pycache__/\n*.pyc\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--no-lock", action="store_true")
    args = parser.parse_args()
    stage(args.out)
    print(f"staged {args.out}")
    if not args.no_lock:
        result = subprocess.run(
            ["uv", "lock", "--project", str(args.out)],
            text=True,
        )
        if result.returncode != 0:
            print("uv lock failed", file=sys.stderr)
            return result.returncode
        print("wrote uv.lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
