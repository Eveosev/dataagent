"""Bundle ↔ source consistency gate (tester r26 B3).

``packaging/bundle`` is the artifact Mint actually installs; a source fix
that is not re-vendored ships the old behavior (r26 shipped a bundle whose
egress gate and verdict vocabulary lagged the live source). The r22 probe
was the only place catching this drift — this test makes it a product
gate: the vendored ``dataagent_application`` (and the vendored contracts /
runtime) must byte-match the live source trees, and no ``.pyc`` may be
shipped.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE = Path(__file__).resolve().parents[1]
_BUNDLE = _PACKAGE / "packaging" / "bundle"
_CAPABILITIES = _PACKAGE.parent

_VENDORED = {
    "application": (
        _PACKAGE / "src" / "dataagent_application",
        _BUNDLE / "src" / "dataagent_application",
    ),
    "contracts": (
        _CAPABILITIES / "dataagent-contracts" / "src" / "dataagent_contracts",
        _BUNDLE / "src" / "dataagent_contracts",
    ),
    "runtime": (
        _CAPABILITIES / "dataagent-runtime" / "src" / "dataagent_runtime",
        _BUNDLE / "src" / "dataagent_runtime",
    ),
}


def _drift(live: Path, vendored: Path) -> tuple[list[str], list[str]]:
    changed = [
        str(path.relative_to(live))
        for path in sorted(live.rglob("*.py"))
        if "__pycache__" not in path.parts
        and (
            not (vendored / path.relative_to(live)).exists()
            or (vendored / path.relative_to(live)).read_bytes() != path.read_bytes()
        )
    ]
    extra = [
        str(path.relative_to(vendored))
        for path in sorted(vendored.rglob("*.py"))
        if "__pycache__" not in path.parts
        and not (live / path.relative_to(vendored)).exists()
    ]
    return changed, extra


def test_bundle_exists_and_vendoring_layout_is_intact():
    for name, (_, vendored) in _VENDORED.items():
        assert vendored.is_dir(), f"bundle does not vendor {name}: {vendored}"


def test_vendored_sources_match_the_live_source():
    for name, (live, vendored) in _VENDORED.items():
        changed, extra = _drift(live, vendored)
        assert not changed and not extra, (
            f"bundle {name} drifted from the live source "
            f"(changed: {changed[:6]}, extra: {extra[:6]}); re-vendor "
            "packaging/bundle before shipping"
        )


def test_bundle_ships_no_bytecode_cache():
    compiled = [
        str(path.relative_to(_BUNDLE))
        for path in _BUNDLE.rglob("*.pyc")
    ]
    caches = [
        str(path.relative_to(_BUNDLE))
        for path in _BUNDLE.rglob("__pycache__")
        if path.is_dir()
    ]
    assert not compiled and not caches, (
        f"bundle ships compiled artifacts ({compiled[:6]} / {caches[:6]})"
    )
