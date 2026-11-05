#!/usr/bin/env python3
"""Stage a self-contained Mint bundle.

The in-repo project depends on ``dataagent-contracts`` and
``dataagent-runtime`` by path. A Mint bundle is extracted as one directory, so
both dependencies must be vendored: the staged project ships
``src/dataagent_governance``, ``src/dataagent_runtime`` and
``src/dataagent_contracts`` and drops the path sources. ``uv lock`` is
regenerated for the staged project.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CONTRACTS = HERE.parent / "dataagent-contracts"
RUNTIME = HERE.parent / "dataagent-runtime"
DEFAULT_OUT = HERE / "packaging" / "bundle"

PYPROJECT = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dataagent-governance"
version = "0.1.0"
description = "DataAgent governance layer: S0 atoms (6) for access, egress, acceptance and grain checks"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.11,<3.14"
authors = [{ name = "AgentOS DataAgent" }]
dependencies = [
  "pydantic>=2.7,<3",
  "duckdb>=1.0,<2",
  "sqlglot>=25,<27",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.hatch.build.targets.wheel]
packages = [
  "src/dataagent_governance",
  "src/dataagent_runtime",
  "src/dataagent_contracts",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
pythonpath = ["src"]
"""


def stage(out: Path) -> None:
    if out.exists():
        if out.name != "bundle" or out.parent.name != "packaging":
            raise SystemExit(f"refusing to remove unexpected path: {out}")
        shutil.rmtree(out)
    (out / "src").mkdir(parents=True)
    (out / "packaging").mkdir()
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(
        HERE / "src" / "dataagent_governance",
        out / "src" / "dataagent_governance",
        ignore=ignore,
    )
    shutil.copytree(
        RUNTIME / "src" / "dataagent_runtime",
        out / "src" / "dataagent_runtime",
        ignore=ignore,
    )
    shutil.copytree(
        CONTRACTS / "src" / "dataagent_contracts",
        out / "src" / "dataagent_contracts",
        ignore=ignore,
    )
    shutil.copy2(
        HERE / "packaging" / "catalog-snapshot.json",
        out / "packaging" / "catalog-snapshot.json",
    )
    shutil.copy2(
        HERE / "packaging" / "source-ref.toml", out / "packaging" / "source-ref.toml"
    )
    for name in ("mint.toml", ".mcp.json", "README.md"):
        shutil.copy2(HERE / name, out / name)
    shutil.copytree(HERE / "skills", out / "skills", ignore=ignore)
    (out / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
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
