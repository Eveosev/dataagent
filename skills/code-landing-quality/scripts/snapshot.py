#!/usr/bin/env python3
"""Digest a package source tree so a review names exactly what it measured.

Usage:
  python3 snapshot.py packages/capabilities/foo [more packages ...]
  python3 snapshot.py packages/capabilities/foo --json

The digest is sha256 over sorted "relpath<TAB>sha256(file)" lines. Caches, virtual
environments, build output and local data directories are excluded, so the same
source gives the same digest on any machine. Record it in result.snapshot.

Exit codes: 0 ok, 2 bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                "node_modules", "dist", "build", ".git", ".dataagent", ".tox", ".eggs"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}
EXCLUDE_NAMES = {".DS_Store"}


def files(root: Path) -> list[Path]:
    out = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS or part.endswith(".egg-info") for part in rel.parts[:-1]):
            continue
        if path.suffix in EXCLUDE_SUFFIX or path.name in EXCLUDE_NAMES:
            continue
        out.append(path)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def tree_digest(root: Path) -> dict:
    lines = []
    for path in files(root):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{path.relative_to(root).as_posix()}\t{digest}\n")
    tree = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
    return {"package": root.name, "files": len(lines), "digest": f"sha256:{tree}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("packages", type=Path, nargs="+")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = []
    for pkg in args.packages:
        if not pkg.is_dir():
            print(f"package not found: {pkg}", file=sys.stderr)
            return 2
        out.append(tree_digest(pkg.resolve()))
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for item in out:
            print(f"{item['package']}\t{item['digest']}\t{item['files']} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
