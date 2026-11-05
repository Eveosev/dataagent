"""Manifest tests for `dataagent/cli` (12 W3, r8-review D17).

`[artifacts]` must be parseable by real Mint: `layout` is a required
field of the Artifacts section (no serde default) — a table that is
present but incomplete is not the same as an absent table. r8 shipped
`bin` without `layout`, so `mint lock` failed manifest parsing for the
CLI and for every preset that depends on it.

stdlib only (unittest + tomllib + subprocess): the real-Mint test
initializes a throwaway Mint project and adds the repo packages by
path, which is the exact install chain the design promises. It skips
when `mint` or the offline core is unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]          # packages/capabilities/dataagent-cli
CAPABILITIES = PKG.parent                          # packages/capabilities
PRESET = CAPABILITIES / "dataagent-s0"

VALID_LAYOUTS = {"any", "target", "flavor-target"}


def _mint_binary() -> str | None:
    found = shutil.which("mint")
    if found:
        return found
    candidate = Path.home() / ".mint" / "bin" / "mint"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


class ManifestTests(unittest.TestCase):
    def test_artifacts_section_is_complete(self):
        """r8-review D17: `[artifacts]` must carry the required `layout`
        field (plus `bin`) or real Mint rejects the manifest with
        `missing field layout` before anything is installed."""

        manifest = tomllib.loads((PKG / "mint.toml").read_text(encoding="utf-8"))
        artifacts = manifest.get("artifacts")
        self.assertIsInstance(artifacts, dict, "mint.toml must declare [artifacts]")
        self.assertIn("layout", artifacts)
        self.assertIn(artifacts["layout"], VALID_LAYOUTS)
        self.assertEqual(artifacts["bin"], "dataagent")
        # the dispatcher is a platform-independent POSIX sh script
        self.assertEqual(artifacts["layout"], "any")

    def test_no_python_dependency_declared(self):
        manifest = tomllib.loads((PKG / "mint.toml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["package"]["kind"], "bundle")
        self.assertEqual(manifest.get("metadata", {}).get("runtime", {}).get("requires"), [])
        self.assertFalse((PKG / ".mcp.json").exists())


@unittest.skipUnless(_mint_binary(), "mint binary not available")
class RealMintInstallTests(unittest.TestCase):
    """The full chain a user runs: `mint init` + `mint add` by path.

    r8-review D17 proved the failure mode with `mint lock --dry-run` on
    a fresh project (exit 1, `missing field layout` at manifest parse);
    with a complete `[artifacts]` the same project instead resolves and
    installs every package, including `dataagent/cli` and (via the
    preset) all three layers.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="cli-manifest-")
        self.project = Path(self._tmp.name)
        self.mint = _mint_binary()
        # a temp project inherits no user trust entries of its own; the
        # add below is what a user would run for a path dependency
        init = subprocess.run(
            [self.mint, "init", "--name", "cli-manifest-test", "--offline", "-y"],
            cwd=self.project, capture_output=True, text=True, timeout=120,
        )
        if init.returncode != 0:
            self.skipTest(f"mint init --offline unavailable: {init.stderr[:200]}")

    def tearDown(self):
        self._tmp.cleanup()

    def test_preset_add_installs_cli_package(self):
        """`mint add <dataagent-s0 path>` installs the preset, its three
        layer bundles, and the CLI dispatcher — the whole manifest chain
        parses (r8 failed here with `missing field layout`)."""

        result = subprocess.run(
            [self.mint, "add", str(PRESET), "--offline", "-y"],
            cwd=self.project, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.project / ".mint" / "packages" / "dataagent"
        for pkg in ("preset-s0", "cli", "data-layer", "application-layer",
                    "governance-layer"):
            self.assertTrue(
                (installed / f"{pkg}@0.1.0").is_dir(),
                f"mint add did not install dataagent/{pkg}",
            )
        self.assertTrue(
            (installed / "cli@0.1.0" / "bin" / "dataagent").is_file(),
            "installed CLI package must ship bin/dataagent",
        )

    def test_lock_dry_run_reparses_cli_manifest(self):
        """`mint lock --dry-run --offline` after the add re-parses every
        manifest in the graph without touching the project (r8's probe
        exit-1 input)."""

        add = subprocess.run(
            [self.mint, "add", str(PRESET), "--offline", "-y"],
            cwd=self.project, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        lock = subprocess.run(
            [self.mint, "lock", "--dry-run", "--offline", "-y"],
            cwd=self.project, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(lock.returncode, 0, lock.stderr)
        self.assertIn("dataagent/cli", (self.project / "mint.lock").read_text())


if __name__ == "__main__":
    unittest.main()
