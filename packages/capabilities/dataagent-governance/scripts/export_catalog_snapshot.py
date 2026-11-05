#!/usr/bin/env python3
"""Export the 6 S0 governance-layer atoms from the authoritative Catalog.

The runtime must not read the research docs (they are not shipped in the
bundle). This script freezes the subset into
``src/dataagent_governance/catalog-snapshot.json`` (shipped inside the
package) and ``--check`` verifies the snapshot against the repository source
(gate G2, same rule as the data layer).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]
AUTHORITATIVE = (
    REPO / "docs" / "research" / "dataagent-2026-11-03" / "catalog" / "atomic-capability-catalog.json"
)
SNAPSHOT = PACKAGE / "src" / "dataagent_governance" / "catalog-snapshot.json"
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
        if atom["layer"] == "03-governance-layer.md" and atom.get("s0_family")
    ]
    if len(atoms) != 6:
        raise SystemExit(f"expected 6 S0 governance atoms, found {len(atoms)}")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the committed snapshot")
    args = parser.parse_args(argv)
    payload = build()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        committed = SNAPSHOT.read_text(encoding="utf-8")
        if committed != rendered:
            print(
                "catalog snapshot is stale; regenerate with "
                "scripts/export_catalog_snapshot.py",
                file=sys.stderr,
            )
            return 1
        print("catalog snapshot is up to date")
        return 0
    SNAPSHOT.write_text(rendered, encoding="utf-8")
    MIRROR.write_text(rendered, encoding="utf-8")
    print(f"wrote {len(payload['atoms'])} atoms to {SNAPSHOT} and {MIRROR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
