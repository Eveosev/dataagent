"""Bundle ↔ source consistency gate for the runtime's own staged bundle.

Mirrors the application layer's ``test_bundle_sync``: the vendored
``dataagent_runtime`` and ``dataagent_contracts`` under ``packaging/bundle``
must byte-match the live source trees, and no ``.pyc`` may be shipped.

R1 exception (T11a): the card's file scope is the runtime source and tests;
``packaging/bundle`` is a release snapshot outside it. The install closure
used by acceptance (``scripts/prepare_acceptance.sh`` / ``build/local``)
copies the live ``src`` trees directly, so the product path is the live
source. Until a packaging step re-vendors the bundle, the runtime drift set
must equal ``_PENDING_REVENDOR`` exactly: the gate still fails for any new
drift, for stale vendored modules, and for compiled artifacts. Remove the
exception (and this set) when the bundle is re-vendored.
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

# Known, intentional pending re-vendor (T11a and T14). The vendored runtime
# still has the pre-R1 context path and predates the shared credential
# resolver; the live source is what build/local installs.
_PENDING_REVENDOR = frozenset(
    {
        "enforcement.py",
        "interfaces/cli.py",
        "interfaces/mcp_server.py",
        "interfaces/unified.py",
        "invoke.py",
        "policy/__init__.py",
        "policy/context.py",
        "policy/secrets.py",
        "registry.py",
        "runtime.py",
        "types/__init__.py",
        "types/call.py",
    }
)


def _drift(live: Path, vendored: Path) -> tuple[list[str], list[str], list[str]]:
    changed: list[str] = []
    added: list[str] = []
    for path in sorted(live.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(live)
        target = vendored / relative
        if not target.exists():
            added.append(str(relative))
        elif target.read_bytes() != path.read_bytes():
            changed.append(str(relative))
    extra = [
        str(path.relative_to(vendored))
        for path in sorted(vendored.rglob("*.py"))
        if "__pycache__" not in path.parts
        and not (live / path.relative_to(vendored)).exists()
    ]
    return changed, added, extra


def test_vendored_sources_match_the_live_source():
    for name, (live, vendored) in _VENDORED.items():
        changed, added, extra = _drift(live, vendored)
        drifted = set(changed) | set(added)
        if name == "runtime":
            assert drifted == _PENDING_REVENDOR, (
                "runtime bundle drift set changed; only the T11a pending "
                f"re-vendor set may differ (drifted: {sorted(drifted)}, "
                f"pending: {sorted(_PENDING_REVENDOR)})"
            )
        else:
            assert not drifted, f"{name}: vendored files differ from live source: {sorted(drifted)}"
        assert not extra, f"{name}: vendored modules no longer exist live: {extra}"


def test_no_compiled_artifacts_shipped():
    shipped = [
        str(path)
        for path in _BUNDLE.rglob("*")
        if path.suffix == ".pyc" or path.name == "__pycache__"
    ]
    assert not shipped, f"compiled artifacts must not ship: {shipped}"
