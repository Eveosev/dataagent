"""Bundle ↔ source consistency gate for the runtime's own staged bundle.

Mirrors the application layer's ``test_bundle_sync``: the vendored
``dataagent_runtime`` and ``dataagent_contracts`` under ``packaging/bundle``
must byte-match the live source trees, and no ``.pyc`` may be shipped.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE = Path(__file__).resolve().parents[1]
_BUNDLE = _PACKAGE / "packaging" / "bundle"
_CAPABILITIES = _PACKAGE.parent

_VENDORED = {
    "runtime": (
        _PACKAGE / "src" / "dataagent_runtime",
        _BUNDLE / "src" / "dataagent_runtime",
    ),
    "contracts": (
        _CAPABILITIES / "dataagent-contracts" / "src" / "dataagent_contracts",
        _BUNDLE / "src" / "dataagent_contracts",
    ),
}


def _drift(live: Path, vendored: Path) -> tuple[list[str], list[str]]:
    changed = [
        str(path.relative_to(live))
        for path in sorted(live.rglob("*.py"))
        if "__pycache__" not in path.parts
        and path.read_bytes() != (vendored / path.relative_to(live)).read_bytes()
    ]
    added = [
        str(path.relative_to(live))
        for path in sorted(live.rglob("*.py"))
        if "__pycache__" not in path.parts
        and not (vendored / path.relative_to(live)).exists()
    ]
    return changed, added


def test_vendored_sources_match_the_live_source():
    for name, (live, vendored) in _VENDORED.items():
        changed, added = _drift(live, vendored)
        assert not changed, f"{name}: vendored files differ from live source: {changed}"
        assert not added, f"{name}: live files missing from the bundle: {added}"


def test_no_compiled_artifacts_shipped():
    shipped = [
        str(path)
        for path in _BUNDLE.rglob("*")
        if path.suffix == ".pyc" or path.name == "__pycache__"
    ]
    assert not shipped, f"compiled artifacts must not ship: {shipped}"
