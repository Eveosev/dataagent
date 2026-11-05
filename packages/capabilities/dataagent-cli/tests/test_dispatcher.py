"""Dispatcher functional tests for `dataagent/cli` bin (12 W3/W4).

stdlib only (unittest + subprocess): builds a temporary Mint project layout
with fake layer `.venv` interpreters and exercises dispatch, mint.lock
pinning, environment scrubbing, `link`, and the exit-code contract.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "bin" / "dataagent"

FAKE_PYTHON = """#!/bin/sh
printf '%s\\n' "$@" > "$DATAAGENT_FAKE_ARGS"
printf '%s\\n' "$0" > "$DATAAGENT_FAKE_CWD"
env | sort | grep -v '^_' > "$DATAAGENT_FAKE_ENV"
"""


def _make_layer(project: Path, pkg: str, version: str, *, venv: bool = True) -> Path:
    layer = project / ".mint" / "packages" / "dataagent" / f"{pkg}@{version}"
    (layer / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
    py = layer / ".venv" / "bin" / "python"
    py.write_text(FAKE_PYTHON, encoding="utf-8")
    py.chmod(0o755)
    return layer


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        self.out = self.project / "out"
        self.out.mkdir()
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.project.as_posix(),
            "DATAAGENT_FAKE_ARGS": str(self.out / "args"),
            "DATAAGENT_FAKE_CWD": str(self.out / "cwd"),
            "DATAAGENT_FAKE_ENV": str(self.out / "env"),
            "DATAAGENT_HOST_SUBJECT_REF": "user:alice",
            "DATAAGENT_HOST_PURPOSE": "monthly_report",
            "MINT_MODEL_API_KEY": "secret-token",
        }

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *argv, cwd=None):
        return subprocess.run(
            [str(BIN), *argv],
            capture_output=True,
            text=True,
            env=self.env,
            cwd=str(cwd or self.project),
        )

    def test_dispatch_data_layer(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = (self.out / "args").read_text().splitlines()
        self.assertEqual(args[0], "-m")
        self.assertEqual(args[1], "dataagent_data.interfaces.cli")
        self.assertEqual(args[2], "list")
        self.assertIn(f"data-layer@0.1.0", (self.out / "cwd").read_text())

    def test_env_scrub_keeps_whitelist_and_dataagent(self):
        _make_layer(self.project, "application-layer", "0.1.0")
        result = self._run("app", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        env = (self.out / "env").read_text()
        self.assertNotIn("MINT_MODEL_API_KEY", env)
        self.assertNotIn("secret-token", env)
        self.assertIn("DATAAGENT_HOST_SUBJECT_REF=user:alice", env)
        self.assertIn("DATAAGENT_HOST_PURPOSE=monthly_report", env)

    def test_mint_lock_pins_version(self):
        _make_layer(self.project, "governance-layer", "0.1.0")
        _make_layer(self.project, "governance-layer", "0.2.0")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/governance-layer"\n'
            'version = "0.1.0"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("gov", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("governance-layer@0.1.0", (self.out / "cwd").read_text())

    def test_without_lock_highest_version_wins(self):
        _make_layer(self.project, "governance-layer", "0.1.0")
        _make_layer(self.project, "governance-layer", "0.2.0")
        result = self._run("gov", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("governance-layer@0.2.0", (self.out / "cwd").read_text())

    def test_missing_package_exits_3(self):
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("no installed dataagent packages", result.stderr)

    def test_missing_venv_exits_3(self):
        layer = _make_layer(self.project, "data-layer", "0.1.0")
        (layer / ".venv" / "bin" / "python").unlink()
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("dataagent setup", result.stderr)

    def test_unknown_layer_is_usage_error(self):
        result = self._run("nolayer", "list")
        self.assertEqual(result.returncode, 2)

    def test_link_creates_stable_launcher(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        result = self._run("link")
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.project / "dataagent"
        self.assertTrue(target.exists())
        self.assertTrue(os.access(target, os.X_OK))
        # the generated launcher dispatches on its own
        result = subprocess.run(
            ["./dataagent", "data", "list"],
            capture_output=True,
            text=True,
            env=self.env,
            cwd=str(self.project),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.out / "args").read_text().splitlines()[2], "list")

    def test_link_refuses_foreign_file(self):
        (self.project / "dataagent").write_text("not a launcher\n", encoding="utf-8")
        result = self._run("link")
        self.assertEqual(result.returncode, 2)
        self.assertIn("refusing to overwrite", result.stderr)

    def test_doctor_missing_everything_exits_3(self):
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("MISSING", result.stderr)

    def test_help_exits_2(self):
        result = self._run()
        self.assertEqual(result.returncode, 2)
        result = self._run("--help")
        self.assertEqual(result.returncode, 2)
        self.assertIn("dataagent <layer>", result.stderr)



    def test_doctor_all_layers_present_exits_0(self):
        for pkg in ("data-layer", "application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("venv     data-layer: ok", result.stdout)
        self.assertIn("data_root:", result.stdout)


if __name__ == "__main__":
    unittest.main()
