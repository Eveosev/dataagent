#!/usr/bin/env python3
"""Export the 32 S0 data-layer atoms from the authoritative Catalog.

The runtime must not read the research docs (they are not shipped in the
bundle). This script freezes the subset into
``src/dataagent_data/catalog-snapshot.json`` (shipped inside the package) and
``--check`` verifies the snapshot against the repository source (gate G2).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]
AUTHORITATIVE = REPO / "docs" / "research" / "dataagent-2026-11-03" / "catalog" / "atomic-capability-catalog.json"
SNAPSHOT = PACKAGE / "src" / "dataagent_data" / "catalog-snapshot.json"
MIRROR = PACKAGE / "packaging" / "catalog-snapshot.json"


def build() -> dict:
    source = json.loads(AUTHORITATIVE.read_text(encoding="utf-8"))
    atoms = [
        {
            "id": atom["id"],
            "operation": atom["operation"],
            "source_file": atom["source_file"],
            "name": atom["name"],
            "group": atom["group"],
            "group_name": atom["group_name"],
            "s0_family": atom["s0_family"],
        }
        for atom in source["atoms"]
        if atom["layer"] == "01-data-layer.md" and atom.get("s0_family")
    ]
    if len(atoms) != 32:
        raise SystemExit(f"expected 32 S0 data atoms, found {len(atoms)}")
    atoms.sort(key=lambda item: item["id"])
    by_family: dict[str, int] = {}
    for atom in atoms:
        by_family[atom["s0_family"]] = by_family.get(atom["s0_family"], 0) + 1
    payload = {
        "version": "0.1.0",
        "generated_from": "docs/research/dataagent-2026-11-03/catalog/atomic-capability-catalog.json",
        "source_sha256": hashlib.sha256(AUTHORITATIVE.read_bytes()).hexdigest(),
        "counts": {"atoms": len(atoms), "by_family": by_family},
        "atoms": atoms,
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = build()
    text = json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        for path in (SNAPSHOT, MIRROR):
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"catalog snapshot is out of date: {path}", file=sys.stderr)
                return 1
        print("catalog snapshot OK: 32 atoms")
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(text, encoding="utf-8")
    MIRROR.parent.mkdir(parents=True, exist_ok=True)
    MIRROR.write_text(text, encoding="utf-8")
    print(f"wrote {SNAPSHOT} and {MIRROR} ({expected['counts']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
