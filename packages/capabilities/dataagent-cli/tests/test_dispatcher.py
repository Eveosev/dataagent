"""Dispatcher functional tests for `dataagent/cli` bin (12 W3/W4).

stdlib only (unittest + subprocess): builds a temporary Mint project layout
with fake layer `.venv` interpreters and exercises dispatch, version
resolution, environment scrubbing, `link`, and the exit-code contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "bin" / "dataagent"

FAKE_PYTHON = """#!/bin/sh
if [ "$1" = "-c" ]; then
    case $2 in
        *policy*)
            # doctor policy probe (r5-review D14): configured iff the
            # marker file exists, otherwise the "no policy" exit code.
            [ -f "$DATAAGENT_FAKE_POLICY" ] && exit 0
            exit 1
            ;;
    esac
    exit 0
fi
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
            "DATAAGENT_FAKE_POLICY": str(self.out / "policy"),
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

    def test_dispatch_workbench_and_ops(self):
        for layer, pkg, module in [('workbench','workbench','dataagent_workbench'), ('ops','operations','dataagent_operations')]:
            _make_layer(self.project, pkg, '0.1.0')
            result = self._run(layer, 'status')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.out / 'args').read_text().splitlines()[1], module+'.interfaces.cli')

    def test_workbench_only_doctor_does_not_require_uninstalled_layers(self):
        _make_layer(self.project, 'workbench', '0.1.0')
        result = self._run('doctor')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('local-owner', result.stdout)

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

    def test_single_installed_version_is_used_without_reading_lock(self):
        """r11: mint.lock is not parsed. Mint prunes installed versions that
        differ from the lock, so the single installed directory is used even
        when a lock names another (uninstalled) version."""

        _make_layer(self.project, "governance-layer", "0.1.0")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/governance-layer"\n'
            'version = "0.9.9"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("gov", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("governance-layer@0.1.0", (self.out / "cwd").read_text())

    def test_unparseable_lock_is_ignored(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        (self.project / "mint.lock").write_text("not = [valid toml\n", encoding="utf-8")
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_multiple_installed_versions_exit_3(self):
        """Several installed versions mean the project is out of sync with
        its lock: fail closed, execute nothing, point at `mint sync`."""

        _make_layer(self.project, "governance-layer", "0.1.0")
        _make_layer(self.project, "governance-layer", "0.2.0")
        result = self._run("gov", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("2 installed versions", result.stderr)
        self.assertIn("mint sync", result.stderr)
        self.assertFalse((self.out / "args").exists())

    def test_layer_not_installed_exits_3(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        result = self._run("gov", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("dataagent/governance-layer is not installed", result.stderr)


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
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("venv     data-layer: ok", result.stdout)
        self.assertIn("policy:   configured", result.stdout)
        self.assertIn("data_root:", result.stdout)

    def test_doctor_missing_policy_exits_3(self):
        """r5-review D14: a missing policy is a failing doctor check.

        Packages, venvs and data_root are fine, but no policy is applied —
        doctor used to print "policy: none" and still exit 0, while the
        next --authorize call would exit 3.
        """

        for pkg in ("data-layer", "application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("policy:   none", result.stderr)
        self.assertIn("gov policy apply", result.stderr)

    def test_doctor_multiple_versions_exits_3(self):
        for pkg in ("data-layer", "application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        _make_layer(self.project, "data-layer", "0.2.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("data-layer: 2 installed versions (run: mint sync)", result.stderr)
        self.assertIn("venv     application-layer: ok", result.stdout)

    def test_doctor_multiple_governance_versions_skips_policy_probe(self):
        for pkg in ("data-layer", "application-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        _make_layer(self.project, "governance-layer", "0.1.0")
        _make_layer(self.project, "governance-layer", "0.2.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("policy:   governance layer unavailable", result.stderr)



if __name__ == "__main__":
    unittest.main()
