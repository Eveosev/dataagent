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

    def test_pinned_version_missing_exits_3(self):
        """r5-review D13: a locked version that is not installed must not be
        silently replaced by another installed version."""

        _make_layer(self.project, "data-layer", "0.1.0")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0.2.0"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("pins dataagent/data-layer@0.2.0", result.stderr)
        self.assertIn("not installed", result.stderr)
        # nothing was executed: the layer process never ran
        self.assertFalse((self.out / "args").exists())

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

    def test_doctor_pinned_version_missing_exits_3(self):
        """r5-review D13 (doctor face): a locked version that is not
        installed is reported as missing, not bypassed."""

        for pkg in ("data-layer", "application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0.2.0"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("MISSING pinned 0.2.0", result.stderr)

    def test_lock_without_layer_pin_falls_back(self):
        """r6-review D16: a mint.lock that pins other layers but not this
        one is "no pin" for this layer — the installed layer resolves
        like the no-lock case, and dispatch and doctor agree."""

        for pkg in ("data-layer", "application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/governance-layer"\n'
            'version = "0.1.0"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("data-layer@0.1.0", (self.out / "cwd").read_text())
        # the layer process really ran
        self.assertEqual((self.out / "args").read_text().splitlines()[2], "list")
        # doctor resolves the same layer the same way and stays green
        result = self._run("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("package  dataagent/data-layer: ./.mint/packages/dataagent/data-layer@0.1.0",
                      result.stdout)

    def test_lock_unreadable_pin_fails_closed(self):
        """r6/r7-review D16: a lock entry for the layer without a
        readable version is a corrupt lock — fail closed (exit 3), never
        silently fall back to the highest installed version.

        (r7 briefly codified the fail-open fallback here; the r7 review
        rejected it, so the expectation is now the r6 semantics.)
        """

        _make_layer(self.project, "data-layer", "0.1.0")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("without a readable version", result.stderr)
        # nothing was executed: the layer process never ran
        self.assertFalse((self.out / "args").exists())

    def test_doctor_lock_unreadable_pin_fails_closed(self):
        """r7-review D16 (doctor face): an unreadable pin is a failing
        doctor check, and the policy probe must not run against a
        bypassed governance version."""

        for pkg in ("data-layer", "application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/governance-layer"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("LOCK unreadable", result.stderr)
        self.assertIn("governance layer unavailable", result.stderr)

    def _pin_matrix(self, lock, pin, installed):
        """Shared body for the r7-review D16 formatting matrix: legal
        TOML whitespace variants must resolve to the same pin for both
        dispatch and doctor (dispatch+doctor agree on the directory)."""

        for ver in installed:
            _make_layer(self.project, "data-layer", ver)
        (self.out / "args").unlink(missing_ok=True)
        (self.project / "mint.lock").write_text(lock, encoding="utf-8")
        result = self._run("data", "list")
        if pin in installed:
            self.assertEqual(result.returncode, 0, result.stderr)
            cwd = (self.out / "cwd").read_text()
            self.assertIn(f"data-layer@{pin}", cwd)
            for other in installed:
                if other != pin:
                    self.assertNotIn(f"data-layer@{other}", cwd)
            self.assertEqual((self.out / "args").read_text().splitlines()[2], "list")
            result = self._run("doctor")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(
                f"package  dataagent/data-layer: ./.mint/packages/dataagent/data-layer@{pin}",
                result.stdout,
            )
        else:
            self.assertEqual(result.returncode, 3)
            self.assertIn("not installed", result.stderr)
            self.assertFalse((self.out / "args").exists())
            result = self._run("doctor")
            self.assertEqual(result.returncode, 3)
            self.assertIn(f"MISSING pinned {pin}", result.stderr)

    def test_compact_pin_dual_versions_uses_pin(self):
        """r7-review D16: compact `name="…"`/`version="0.1.0"` is legal
        TOML (tomllib-equivalent) and must pin even when a higher
        version is installed — r7 silently used the highest instead."""

        for pkg in ("application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        self._pin_matrix(
            'v=1\n\n[[package]]\nname="dataagent/data-layer"\nversion="0.1.0"\nkind="bundle"\n',
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_indented_pin_dual_versions_uses_pin(self):
        """r7-review D16: indented `  name = "…"` keys are legal TOML
        and must pin even when a higher version is installed."""

        for pkg in ("application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        self._pin_matrix(
            'v = 1\n\n[[package]]\n  name = "dataagent/data-layer"\n'
            '  version = "0.1.0"\n  kind = "bundle"\n',
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_literal_pin_dual_versions_uses_pin(self):
        """r7-review D16 (TOML subset): single-quoted literal strings are
        legal TOML and resolve like basic strings."""

        for pkg in ("application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        self._pin_matrix(
            "v = 1\n\n[[package]]\nname = 'dataagent/data-layer'\n"
            "version = '0.1.0'\nkind = 'bundle'\n",
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_compact_pin_missing_exits_3(self):
        """r7-review D16 + r5-review D13: a compact-format pin that is
        not installed fails closed — r7 executed the other installed
        version (exit 0) instead."""

        for pkg in ("application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        self._pin_matrix(
            'v=1\n\n[[package]]\nname="dataagent/data-layer"\nversion="0.2.0"\nkind="bundle"\n',
            "0.2.0", ("0.1.0",),
        )

    def test_indented_pin_missing_exits_3(self):
        """r7-review D16 + r5-review D13: indented-format pin that is
        not installed fails closed for dispatch and doctor alike."""

        for pkg in ("application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")
        self._pin_matrix(
            'v = 1\n\n[[package]]\n  name = "dataagent/data-layer"\n'
            '  version = "0.2.0"\n  kind = "bundle"\n',
            "0.2.0", ("0.1.0",),
        )

    # r8-review D16 regression set: the lock is real Mint-shaped TOML —
    # table scope (`[[package.requires]]` edges are not pins), quoted
    # keys, and escaped basic strings are all legal forms that must
    # resolve to the same pin (and never bypass it).

    _PRESET_WITH_REQUIRES = (
        '[[package]]\nname = "dataagent/preset-s0"\nversion = "0.1.0"\n'
        'kind = "preset"\nsource = "path+file:///fixture"\n'
        'integrity = "h1:fixture"\ncksum = ""\n'
        'deps = ["dataagent/data-layer"]\n\n'
        '[[package.requires]]\nname = "dataagent/data-layer"\nreq = "^0.1.0"\n\n'
    )

    _REAL_ENTRY = (
        '[[package]]\nname = "dataagent/data-layer"\nversion = "0.1.0"\n'
        'kind = "bundle"\nsource = "path+file:///fixture"\n'
        'integrity = "h1:fixture"\ncksum = ""\n'
    )

    def _prep_other_layers(self):
        for pkg in ("application-layer", "governance-layer"):
            _make_layer(self.project, pkg, "0.1.0")
        (self.out / "policy").write_text("{}\n", encoding="utf-8")

    def test_nested_requires_before_real_pin_uses_pin(self):
        """r8-review D16: a `[[package.requires]]` dependency edge ahead
        of the real package entry is not a pin (it has `req`, not
        `version`) — the pin comes from the later real entry (r8 exited
        3 here, r7 executed the highest installed version)."""

        self._prep_other_layers()
        self._pin_matrix(
            "v = 1\n\n" + self._PRESET_WITH_REQUIRES + self._REAL_ENTRY,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_nested_requires_only_falls_back(self):
        """r8-review D16: a lock whose only mention of this layer is a
        requires edge has no pin for the layer — it resolves exactly
        like the no-lock case (r8 exited 3, blocking a legal lock)."""

        self._prep_other_layers()
        self._pin_matrix(
            "v = 1\n\n" + self._PRESET_WITH_REQUIRES, "0.2.0", ("0.1.0", "0.2.0"),
        )

    def test_nested_requires_after_real_pin_uses_pin(self):
        """r8-review D16: requires edges following the real package entry
        must not shadow or corrupt its pin."""

        self._prep_other_layers()
        self._pin_matrix(
            "v = 1\n\n" + self._REAL_ENTRY + self._PRESET_WITH_REQUIRES,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_real_mint_lock_shape_uses_pin(self):
        """r8-review D16: a mint.lock with the shape real Mint generates
        (`v`/`resolver`/`generated_at` headers, `[core]` tables,
        multi-line `deps` arrays, `[[package.requires]]` edges for
        registry packages, `[package.artifacts.any]` sub-tables) pins
        the layer from its `[[package]]` entry."""

        lock = (
            "# 由 mint 自动生成，请勿手改（03 §3.5）。\n"
            'v = 1\nresolver = "backtracking-v1"\n'
            'generated_at = "2026-11-06T00:00:00Z"\n\n'
            "[core]\nversion = \"0.1.43\"\nflavor = \"std\"\n\n"
            "[[package]]\nname = \"dataagent/preset-s0\"\nversion = \"0.1.0\"\n"
            "kind = \"preset\"\n"
            'source = "path+file:///fixture"\nintegrity = "h1:fixture"\ncksum = ""\n'
            "deps = [\n    \"dataagent/data-layer\",\n]\ntrust = \"T0\"\n\n"
            "[[package]]\nname = \"dataagent/data-layer\"\nversion = \"0.1.0\"\n"
            "kind = \"bundle\"\n"
            'source = "path+file:///fixture"\nintegrity = "h1:fixture"\ncksum = ""\n'
            "trust = \"T0\"\n\n"
            "[[package]]\nname = \"mint/preset-default\"\nversion = \"0.1.1\"\n"
            "kind = \"preset\"\n"
            'source = "registry+https://example.invalid/index/"\n'
            'integrity = "h1:fixture"\ncksum = "abc"\n'
            "deps = [\"mint/tui\"]\ntrust = \"T1\"\n\n"
            "[[package.requires]]\nname = \"mint/tui\"\nreq = \"^0.1.0\"\n\n"
            "[package.artifacts.any]\nfile = \"mint-preset.mint.tar.zst\"\n"
            'sha256 = "abc"\nsize = 5666\nintegrity = "h1:fixture"\n\n'
        )
        self._prep_other_layers()
        self._pin_matrix(lock, "0.1.0", ("0.1.0", "0.2.0"))

    def test_quoted_keys_pin_uses_pin(self):
        """r8-review D16: quoted keys (`"name" = …` / `"version" = …`)
        are legal TOML and the same keys — r8 read them as no pin and
        silently executed the highest installed version."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\n"name" = "dataagent/data-layer"\n'
            '"version" = "0.1.0"\nkind = "bundle"\n',
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_escaped_name_pin_uses_pin(self):
        """r8-review D16: `name = "dataagent\\u002fdata-layer"` is the
        same package name as `dataagent/data-layer` — r8 read it as no
        pin and bypassed the lock."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = "dataagent\\u002fdata-layer"\n'
            'version = "0.1.0"\nkind = "bundle"\n',
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_escaped_version_pin_uses_pin(self):
        """r8-review D16: `version = "0\\u002e1.0"` is the same version
        as `0.1.0` — r8 treated it as unreadable and rejected an
        installed, legally pinned version (exit 3)."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0\\u002e1.0"\nkind = "bundle"\n',
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_escaped_pin_missing_exits_3(self):
        """r8-review D16 + r5-review D13: an escaped-string pin that is
        not installed must fail closed — escaping is never a bypass."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = "dataagent\\u002fdata-layer"\n'
            'version = "0.2.0"\nkind = "bundle"\n',
            "0.2.0", ("0.1.0",),
        )

    def test_trailing_garbage_version_fails_closed(self):
        """r8-review D16 (negative): `version = "0.1.0" INVALID` is not
        valid TOML (tomllib rejects the line) — the value is unreadable
        and dispatch must fail closed instead of executing."""

        _make_layer(self.project, "data-layer", "0.1.0")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0.1.0" INVALID\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("without a readable version", result.stderr)
        self.assertFalse((self.out / "args").exists())
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("LOCK unreadable", result.stderr)


if __name__ == "__main__":
    unittest.main()
