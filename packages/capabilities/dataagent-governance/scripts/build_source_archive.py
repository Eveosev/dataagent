#!/usr/bin/env python3
"""Rebuild the deterministic source archive (reviewer r24 B9, tester r28 B9).

The AgentOS root is not a git repository, so ``packaging/source-ref.toml``
anchors this package's source in a byte-reproducible tar instead: the archive
contains the three vendored source trees (contracts / runtime / governance),
the bundle's ``pyproject.toml``, the authoritative Catalog and the 08 build
plan, plus the archive's own ``MANIFEST.sha256`` (per-file digests).

Reproducibility (the same tree always yields the same digest):

* tar entries are ordered depth-first, files of a directory before its
  subdirectories, everything sorted by name;
* every entry carries ``mtime=2026-11-05T00:00:00Z``, ``uid=gid=0``,
  ``mode=0644``, PAX format, no directory entries;
* the gzip stream carries ``mtime=0`` and compresslevel 9.

``MANIFEST.sha256`` covers the 67 content files (not itself: a file cannot
contain its own digest). The sibling ``packaging/source-archive/MANIFEST.sha256``
adds one self line whose digest is that of the covered manifest content.

Modes:

* default — rebuild the archive, the manifests and the ``[source_archive]``
  digest in ``packaging/source-ref.toml``;
* ``--check`` — rebuild in memory only and fail if the declared digest or the
  per-file manifest does not match the current tree (the reproducibility gate).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import re
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
CONTRACTS = HERE.parent / "dataagent-contracts"
RUNTIME = HERE.parent / "dataagent-runtime"
ARCHIVE_DIR = HERE / "packaging" / "source-archive"
SOURCE_REF = HERE / "packaging" / "source-ref.toml"

ARCHIVE_NAME = "governance-source-20261105"
FIXED_MTIME = 1762291200  # 2026-11-05T00:00:00Z

# Inputs mirror the ``[source_archive].inputs`` list in source-ref.toml.
INPUT_FILES = {
    "08-governance-layer-build-plan.md": ROOT
    / "docs/research/dataagent-2026-11-03/08-governance-layer-build-plan.md",
    "atomic-capability-catalog.json": ROOT
    / "docs/research/dataagent-2026-11-03/catalog/atomic-capability-catalog.json",
    "pyproject.toml": HERE / "packaging" / "bundle" / "pyproject.toml",
}
INPUT_DIRS = {
    "src/dataagent_contracts": CONTRACTS / "src" / "dataagent_contracts",
    "src/dataagent_governance": HERE / "src" / "dataagent_governance",
    "src/dataagent_runtime": RUNTIME / "src" / "dataagent_runtime",
}

_CONTENT_MANIFEST = ARCHIVE_DIR / f"{ARCHIVE_NAME}.MANIFEST.sha256"
_ALL_MANIFEST = ARCHIVE_DIR / "MANIFEST.sha256"
_TARBALL = ARCHIVE_DIR / f"{ARCHIVE_NAME}.tar.gz"


def _die(message: str) -> "SystemExit":
    return SystemExit(f"build_source_archive: {message}")


def _walk_files(base: Path, prefix: str) -> list[tuple[str, Path]]:
    """Depth-first, files of a directory before its sorted subdirectories."""

    entries = sorted(base.iterdir(), key=lambda p: p.name)
    files = [(prefix + p.name, p) for p in entries if p.is_file()]
    for entry in entries:
        if entry.is_dir() and entry.name != "__pycache__":
            files.extend(_walk_files(entry, prefix + entry.name + "/"))
    return files


def collect() -> list[tuple[str, bytes]]:
    """The archive payload as ``(member name, content)`` in final order.

    Top-level inputs merge in sorted order (files and source trees by name);
    inside a source tree the walk order (files before subdirectories) is kept.
    """

    groups: list[list[tuple[str, Path | None]]] = []
    for name, path in INPUT_FILES.items():
        if not path.is_file():
            raise _die(
                f"input {name} is missing: {path}"
                + ("; run scripts/build_bundle.py first" if name == "pyproject.toml" else "")
            )
        groups.append([(name, path)])
    for name, path in INPUT_DIRS.items():
        if not path.is_dir():
            raise _die(f"input directory {name} is missing: {path}")
        groups.append(_walk_files(path, name + "/"))
    # The archive's own manifest joins the top-level files in sorted order.
    groups.append([("MANIFEST.sha256", None)])
    groups.sort(key=lambda group: group[0][0])
    members = [item for group in groups for item in group]

    content: dict[str, bytes] = {}
    for name, path in members:
        if path is not None:
            content[name] = path.read_bytes()
    # The manifest covers every file except itself; entries sorted by name.
    lines = "".join(
        f"{hashlib.sha256(blob).hexdigest()}  {name}\n"
        for name, blob in sorted(content.items())
    ).encode()
    content["MANIFEST.sha256"] = lines
    return [(name, content[name]) for name, _ in members]


def build_bytes(members: list[tuple[str, bytes]]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for name, blob in members:
            info = tarfile.TarInfo(f"{ARCHIVE_NAME}/{name}")
            info.size = len(blob)
            info.mtime = FIXED_MTIME
            info.mode = 0o644
            info.type = tarfile.REGTYPE
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tf.addfile(info, io.BytesIO(blob))
    packed = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", fileobj=packed, compresslevel=9, mtime=0
    ) as gz:
        gz.write(raw.getvalue())
    return packed.getvalue()


def declared_digest() -> str | None:
    match = re.search(
        r"(?ms)^\[source_archive\]$.*?^sha256 = \"([0-9a-f]{64})\"$", SOURCE_REF.read_text()
    )
    return match.group(1) if match else None


def update_source_ref(digest: str, files: int) -> None:
    text = SOURCE_REF.read_text()
    text, count = re.subn(
        r'(?ms)(^\[source_archive\]$.*?)^sha256 = "[0-9a-f]{64}"',
        rf'\1sha256 = "{digest}"',
        text,
    )
    if count != 1:
        raise _die("could not update [source_archive].sha256 in source-ref.toml")
    text, count = re.subn(
        r"(?ms)(^\[source_archive\]$.*?)^files = \d+",
        rf"\g<1>files = {files}",
        text,
    )
    if count != 1:
        raise _die("could not update [source_archive].files in source-ref.toml")
    SOURCE_REF.write_text(text)


def check() -> int:
    members = collect()
    digest = hashlib.sha256(build_bytes(members)).hexdigest()
    declared = declared_digest()
    problems: list[str] = []
    if declared is None:
        problems.append("source-ref.toml declares no [source_archive] digest")
    elif declared != digest:
        problems.append(
            f"declared digest {declared} does not match the current tree "
            f"(rebuilt {digest}); rebuild the archive and update source-ref.toml"
        )
    if _CONTENT_MANIFEST.is_file():
        recorded = {}
        for line in _CONTENT_MANIFEST.read_text().splitlines():
            digest_, _, path = line.partition("  ")
            recorded[path.strip()] = digest_
        for name, blob in members:
            if name == "MANIFEST.sha256":
                continue
            if recorded.get(name) != hashlib.sha256(blob).hexdigest():
                problems.append(f"manifest digest mismatch for {name}")
    else:
        problems.append(f"content manifest is missing: {_CONTENT_MANIFEST}")
    if problems:
        for problem in problems:
            print("FAIL", problem, file=sys.stderr)
        return 1
    print(f"source archive reproducible from the current tree: {digest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = parser.parse_args()
    if args.check:
        return check()

    members = collect()
    blob = build_bytes(members)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    _TARBALL.write_bytes(blob)
    manifest = dict(members)["MANIFEST.sha256"]
    _CONTENT_MANIFEST.write_bytes(manifest)
    files = len(members) - 1  # everything the manifest covers
    # The all-files manifest adds one self line whose digest is the digest of
    # the manifest content it covers (a file cannot contain its own digest).
    _ALL_MANIFEST.write_bytes(
        manifest
        + f"{hashlib.sha256(manifest).hexdigest()}  MANIFEST.sha256\n".encode()
    )
    digest = hashlib.sha256(blob).hexdigest()
    update_source_ref(digest, files)
    print(f"wrote {_TARBALL.name} ({files} content files)")
    print(f"sha256 {digest}")
    print(f"updated {SOURCE_REF.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
