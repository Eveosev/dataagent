"""Dispatcher functional tests for `dataagent/cli` bin (12 W3/W4).

stdlib only (unittest + subprocess): builds a temporary Mint project layout
with fake layer `.venv` interpreters and exercises dispatch, mint.lock
pinning, environment scrubbing, `link`, and the exit-code contract.
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

    # r9-review D16 regression set: the equivalent legal TOML
    # representations the r9 line-based parser reclassified as "no pin"
    # (bypassing the lock) or as unreadable (rejecting a legal pin).
    # Every case below is accepted by stdlib tomllib and by the real
    # Mint (0.1.26) lock parser; each must resolve to the same pin.

    _R9_FIELDS = (
        'kind = "bundle"\nsource = "path+file:///fixture"\n'
        'integrity = "h1:fixture"\ncksum = ""\n'
    )

    def test_quoted_header_pin_uses_pin(self):
        """r9-review D16: `[["package"]]` is the same table array as
        `[[package]]` — r9 ignored its pin and executed the highest
        installed version."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[["package"]]\nname = "dataagent/data-layer"\n'
            'version = "0.1.0"\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_literal_header_pin_uses_pin(self):
        """r9-review D16: `[['package']]` quoted-with-literal-quotes table
        header is the same package array."""

        self._prep_other_layers()
        self._pin_matrix(
            "v = 1\n\n[['package']]\nname = 'dataagent/data-layer'\n"
            "version = '0.1.0'\n" + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_escaped_header_pin_uses_pin(self):
        """r9-review D16: `[["pack\\u0061ge"]]` decodes to the same table
        name as `[[package]]`."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[["pack\\u0061ge"]]\nname = "dataagent/data-layer"\n'
            'version = "0.1.0"\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_spaced_header_pin_uses_pin(self):
        """r9-review D16: whitespace inside the header brackets is legal
        TOML and addresses the same table."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[ package ]]\nname = "dataagent/data-layer"\n'
            'version = "0.1.0"\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_escaped_name_key_pin_uses_pin(self):
        """r9-review D16: `\"\\u006eame\" = …` is the `name` key with an
        escaped quoted form — r9 read it as no pin and bypassed."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\n"\\u006eame" = "dataagent/data-layer"\n'
            'version = "0.1.0"\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_escaped_version_key_pin_uses_pin(self):
        """r9-review D16: `\"vers\\u0069on\" = …` is the `version` key —
        r9 could not read it and rejected the installed, legally pinned
        version (exit 3)."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            '"vers\\u0069on" = "0.1.0"\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_single_line_triple_quote_pin_uses_pin(self):
        """r9-review D16: `\"\"\"0.1.0\"\"\"` single-line multi-line strings
        are the same value."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = """dataagent/data-layer"""\n'
            'version = """0.1.0"""\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_multiline_name_pin_uses_pin(self):
        """r9-review D16: a multi-line basic string value spans lines —
        r9's one-line scanner rejected it (exit 3)."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = """\ndataagent/data-layer"""\n'
            'version = "0.1.0"\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_multiline_version_pin_uses_pin(self):
        """r9-review D16: multi-line basic string version."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = """\n0.1.0"""\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_multiline_literal_pin_uses_pin(self):
        """r9-review D16: multi-line literal (`'''…'''`) name and
        version, with the leading-newline trim."""

        self._prep_other_layers()
        self._pin_matrix(
            "v = 1\n\n[[package]]\nname = '''\ndataagent/data-layer'''\n"
            "version = '''\n0.1.0'''\n" + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_multiline_continuation_pin_uses_pin(self):
        """r9-review D16: a `\\`-continuation inside a multi-line basic
        string trims the newline and the next line's indentation."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[[package]]\nname = """dataagent/\\\n  data-layer"""\n'
            'version = "0.1.0"\n' + self._R9_FIELDS,
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_inline_package_array_pin_uses_pin(self):
        """r9-review D16: `package = [{name = …, version = …}]` defines
        the same top-level package array as `[[package]]` — r9 read it
        as no pin and bypassed the lock."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\npackage = [{name = "dataagent/data-layer", '
            'version = "0.1.0", kind = "bundle", '
            'source = "path+file:///fixture", integrity = "h1:fixture", '
            'cksum = ""}]\n',
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_inline_package_array_multiline_uses_pin(self):
        """r9-review D16: the inline package array may span lines and
        carry comments like any TOML array."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\npackage = [\n  { name = "dataagent/data-layer",\n'
            '    version = "0.1.0", kind = "bundle" }, # entry\n]\n',
            "0.1.0", ("0.1.0", "0.2.0"),
        )

    def test_quoted_header_missing_pin_exits_3(self):
        """r9-review D16 (regression control): a quoted-header pin that
        is not installed must fail closed — r9 exited 0 and executed
        0.2.0 where r8 exited 3 (fail-open regression)."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[["package"]]\nname = "dataagent/data-layer"\n'
            'version = "0.9.9"\n' + self._R9_FIELDS,
            "0.9.9", ("0.1.0", "0.2.0"),
        )

    def test_inline_package_array_missing_pin_exits_3(self):
        """r9-review D16 + r5-review D13: an inline-array pin that is not
        installed fails closed — the inline form is never a bypass."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\npackage = [{name = "dataagent/data-layer", '
            'version = "0.9.9", kind = "bundle"}]\n',
            "0.9.9", ("0.1.0", "0.2.0"),
        )

    def test_escaped_header_missing_pin_exits_3(self):
        """r9-review D16 + D13: an escaped-header pin that is not
        installed fails closed."""

        self._prep_other_layers()
        self._pin_matrix(
            'v = 1\n\n[["pack\\u0061ge"]]\nname = "dataagent/data-layer"\n'
            'version = "0.9.9"\n' + self._R9_FIELDS,
            "0.9.9", ("0.1.0", "0.2.0"),
        )

    def test_duplicate_key_lock_fails_closed(self):
        """r10: a lock with a duplicated key inside an entry is not valid
        TOML (tomllib rejects it) — like every unparseable lock it must
        fail closed, never resolve to "no pin"."""

        _make_layer(self.project, "data-layer", "0.2.0")
        (self.project / "mint.lock").write_text(
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0.1.0"\nkind = "bundle"\nkind = "bundle"\n',
            encoding="utf-8",
        )
        result = self._run("data", "list")
        self.assertEqual(result.returncode, 3)
        self.assertIn("without a readable version", result.stderr)
        self.assertFalse((self.out / "args").exists())

    def test_real_mint_lock_escaped_and_inline_forms(self):
        """r10: a real-Mint-shaped lock (v/resolver/[core], requires
        edges, artifacts sub-table) whose data-layer entry uses the
        equivalent escaped-header/escaped-key/multi-line forms still
        pins from its own entry."""

        lock = (
            'v = 1\nresolver = "backtracking-v1"\n'
            'generated_at = "2026-11-06T00:00:00Z"\n\n'
            "[core]\nversion = \"0.1.43\"\nflavor = \"std\"\n\n"
            '[[package]]\nname = "dataagent/preset-s0"\nversion = "0.1.0"\n'
            'kind = "preset"\nsource = "path+file:///fixture"\n'
            'integrity = "h1:fixture"\ncksum = ""\n'
            'deps = [\n    "dataagent/data-layer",\n]\n\n'
            "[[package.requires]]\nname = \"dataagent/data-layer\"\nreq = \"^0.1.0\"\n\n"
            '[["package"]]\n"\\u006eame" = """\ndataagent/data-layer"""\n'
            '"vers\\u0069on" = """0.1.0"""\nkind = "bundle"\n'
            'source = "path+file:///fixture"\nintegrity = "h1:fixture"\ncksum = ""\n'
            "[package.artifacts.any]\nfile = \"data-layer.mint.tar.zst\"\n"
            'sha256 = "abc"\nsize = 5666\n'
        )
        self._prep_other_layers()
        self._pin_matrix(lock, "0.1.0", ("0.1.0", "0.2.0"))


class LockDifferentialTests(unittest.TestCase):
    """r10 D16 differential regression: every lock variant here is first
    validated with stdlib tomllib (the same reference the reviews use),
    its expected pin derived from the parsed document, and then the
    dispatcher must exec exactly that version — no formatting variant
    may downgrade to "no pin" (bypass) or reject a legal pin."""

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
        }

    def tearDown(self):
        self._tmp.cleanup()

    def _differential(self, lock, installed=("0.1.0", "0.2.0")):
        import tomllib

        parsed = tomllib.loads(lock)
        packages = parsed.get("package")
        if packages is None:
            packages = []
        elif isinstance(packages, dict):
            packages = [packages]
        pin, unreadable = None, False
        for entry in packages:
            name = entry.get("name")
            if not isinstance(name, str):
                unreadable = True
                break
            if name == "dataagent/data-layer":
                version = entry.get("version")
                if not isinstance(version, str) or version == "":
                    unreadable = True
                else:
                    pin = version
                break
        for ver in installed:
            _make_layer(self.project, "data-layer", ver)
        (self.project / "mint.lock").write_text(lock, encoding="utf-8")
        result = subprocess.run(
            [str(BIN), "data", "list"],
            capture_output=True, text=True, env=self.env, cwd=str(self.project),
        )
        if unreadable:
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertFalse((self.out / "args").exists())
            return
        expected = pin if pin is not None else max(installed)
        if expected not in installed:
            # D13: a pin that is not installed fails closed, never falls
            # back to another installed version
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertFalse((self.out / "args").exists())
            return
        self.assertEqual(result.returncode, 0, result.stderr)
        cwd = (self.out / "cwd").read_text()
        self.assertIn(f"data-layer@{expected}", cwd)
        for other in installed:
            if other != expected:
                self.assertNotIn(f"data-layer@{other}", cwd)

    def test_differential_legal_equivalence_matrix(self):
        fields = (
            'kind = "bundle"\nsource = "path+file:///fixture"\n'
            'integrity = "h1:fixture"\ncksum = ""\n'
        )
        normal = (
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0.1.0"\n' + fields
        )
        variants = {
            "canonical": normal,
            "quoted_header": normal.replace("[[package]]", '[["package"]]'),
            "literal_header": normal.replace("[[package]]", "[['package']]"),
            "escaped_header": normal.replace("[[package]]", '[["pack\\u0061ge"]]'),
            "spaced_header": normal.replace("[[package]]", "[[ package ]]"),
            "header_comment": normal.replace("[[package]]", "[[package]] # note"),
            "escaped_name_key": normal.replace("name =", '"\\u006eame" ='),
            "escaped_version_key": normal.replace("version =", '"vers\\u0069on" ='),
            "triple_single_line": normal.replace('"0.1.0"', '"""0.1.0"""'),
            "multiline_name": normal.replace(
                '"dataagent/data-layer"', '"""\ndataagent/data-layer"""'),
            "multiline_version": normal.replace('"0.1.0"', '"""\n0.1.0"""'),
            "multiline_literal": (
                normal.replace('"dataagent/data-layer"', "'''\ndataagent/data-layer'''")
                .replace('"0.1.0"', "'''\n0.1.0'''")),
            "multiline_continuation": normal.replace(
                '"dataagent/data-layer"', '"""dataagent/\\\n  data-layer"""'),
            "inline_package_array": (
                'v = 1\npackage = [{name = "dataagent/data-layer", '
                'version = "0.1.0", kind = "bundle", '
                'source = "path+file:///fixture", integrity = "h1:fixture", '
                'cksum = ""}]\n'),
            "inline_package_multiline": (
                'v = 1\npackage = [\n  {name = "dataagent/data-layer",\n'
                '   version = "0.1.0", kind = "bundle"},\n]\n'),
            "escaped_values": (
                normal.replace('"dataagent/data-layer"', '"dataagent\\u002fdata-layer"')
                .replace('"0.1.0"', '"0\\u002e1.0"')),
            "crlf": normal.replace("\n", "\r\n"),
            "other_package_only": (
                'v = 1\n\n[[package]]\nname = "dataagent/other"\n'
                'version = "0.1.0"\n' + fields),
            "requires_edge_only": (
                'v = 1\n\n[[package]]\nname = "dataagent/preset-s0"\n'
                'version = "0.1.0"\n' + fields
                + '[[package.requires]]\nname = "dataagent/data-layer"\nreq = "^0.1.0"\n'),
            "empty_lock": "v = 1\n",
        }
        for name, lock in variants.items():
            with self.subTest(variant=name):
                self._differential(lock)

    def test_differential_missing_pins_fail_closed(self):
        fields = (
            'kind = "bundle"\nsource = "path+file:///fixture"\n'
            'integrity = "h1:fixture"\ncksum = ""\n'
        )
        missing = (
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0.9.9"\n' + fields
        )
        variants = {
            "canonical": missing,
            "quoted_header": missing.replace("[[package]]", '[["package"]]'),
            "escaped_header": missing.replace("[[package]]", '[["pack\\u0061ge"]]'),
            "escaped_name_key": missing.replace("name =", '"\\u006eame" ='),
            "multiline_version": missing.replace('"0.9.9"', '"""\n0.9.9"""'),
            "inline_package_array": (
                'v = 1\npackage = [{name = "dataagent/data-layer", '
                'version = "0.9.9", kind = "bundle"}]\n'),
        }
        for name, lock in variants.items():
            with self.subTest(variant=name):
                self._differential(lock, installed=("0.1.0",))

    def test_differential_invalid_locks_fail_closed(self):
        invalid = {
            "trailing_garbage": (
                'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
                'version = "0.1.0" INVALID\n'),
            "duplicate_key": (
                'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
                'version = "0.1.0"\nkind = "bundle"\nkind = "bundle"\n'),
            "value_over_table": (
                'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
                'version = "0.1.0"\nmeta.a = 1\nmeta = 2\n'),
            "declare_table_twice": (
                'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
                'version = "0.1.0"\n\n[[package]]\n[package]\nname = "x"\n'),
            "unclosed_string": (
                'v = 1\n\n[[package]]\nname = "dataagent/data-layer\n'
                'version = "0.1.0"\n'),
        }
        for name, lock in invalid.items():
            with self.subTest(variant=name):
                import tomllib
                with self.assertRaises(tomllib.TOMLDecodeError):
                    tomllib.loads(lock)
                for ver in ("0.1.0", "0.2.0"):
                    _make_layer(self.project, "data-layer", ver)
                (self.project / "mint.lock").write_text(lock, encoding="utf-8")
                (self.out / "args").unlink(missing_ok=True)
                result = subprocess.run(
                    [str(BIN), "data", "list"],
                    capture_output=True, text=True, env=self.env,
                    cwd=str(self.project),
                )
                self.assertEqual(result.returncode, 3)
                self.assertFalse((self.out / "args").exists())


class RealMintLockDifferentialTests(unittest.TestCase):
    """r10 D16 real-Mint differential regression: for representative
    lock variants the real `mint list --offline --json` (same binary the
    reviews use) must report the same pinned version that the dispatcher
    execs. Skipped when mint or its offline cores are unavailable."""

    MINT = "/Users/payne/.mint/bin/mint"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        self.out = self.project / "out"
        self.out.mkdir()
        self.exec_log = self.project / "exec.log"
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": self.project.as_posix(),
            "MINT_HOME": self.project.as_posix() + "/mint-home",
            "DATAAGENT_WORKSPACE": self.project.as_posix(),
            "DATAAGENT_DATA_ROOT": self.project.as_posix() + "/.dataagent",
            "DATAAGENT_HOST_SUBJECT_REF": "user:tester",
            "DATAAGENT_HOST_PURPOSE": "verification",
            "DATAAGENT_ENFORCEMENT_MODE": "warn",
            "DATAAGENT_PROBE_EXEC": str(self.exec_log),
        }

    # wrapper records its own path, then succeeds — the exec directory
    # is the observable, and it must survive the dispatcher env scrub
    # (DATAAGENT_* is whitelisted)
    PROBE_PYTHON = """#!/bin/sh
printf '%s\n' "$0" >> "$DATAAGENT_PROBE_EXEC"
printf 'ok\n'
"""

    def _make_probe_layer(self, version):
        layer = self.project / ".mint" / "packages" / "dataagent" / (
            "data-layer@%s" % version)
        (layer / ".venv" / "bin").mkdir(parents=True, exist_ok=True)
        py = layer / ".venv" / "bin" / "python"
        py.write_text(self.PROBE_PYTHON, encoding="utf-8")
        py.chmod(0o755)

    def tearDown(self):
        self._tmp.cleanup()

    @classmethod
    def setUpClass(cls):
        if not os.access(cls.MINT, os.X_OK):
            raise unittest.SkipTest("real mint binary not available")

    def _mint_pin(self, lock):
        (self.project / "mint.toml").write_text(
            '[package]\nname = "local/mint-diff"\nversion = "0.1.0"\n'
            'kind = "agent"\n',
            encoding="utf-8",
        )
        (self.project / "mint.lock").write_text(lock, encoding="utf-8")
        result = subprocess.run(
            [self.MINT, "list", "--offline", "--json"],
            capture_output=True, text=True, env=self.env,
            cwd=str(self.project), timeout=60,
        )
        if result.returncode != 0:
            return "mint-error"
        pins = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("event") == "list.done":
                for package in event.get("packages", []):
                    if (package.get("name") == "dataagent/data-layer"
                            and package.get("kind") == "bundle"):
                        pins.append(package["version"])
        return pins[0] if pins else None

    def test_real_mint_agrees_with_dispatcher_on_equivalent_locks(self):
        fields = (
            'kind = "bundle"\nsource = "path+file:///fixture"\n'
            'integrity = "h1:fixture"\ncksum = ""\n'
        )
        normal = (
            'v = 1\n\n[[package]]\nname = "dataagent/data-layer"\n'
            'version = "0.1.0"\n' + fields
        )
        variants = {
            "canonical": normal,
            "quoted_header": normal.replace("[[package]]", '[["package"]]'),
            "escaped_header": normal.replace("[[package]]", '[["pack\\u0061ge"]]'),
            "escaped_name_key": normal.replace("name =", '"\\u006eame" ='),
            "multiline_version": normal.replace('"0.1.0"', '"""\n0.1.0"""'),
            "inline_package_array": (
                'v = 1\npackage = [{name = "dataagent/data-layer", '
                'version = "0.1.0", kind = "bundle", '
                'source = "path+file:///fixture", integrity = "h1:fixture", '
                'cksum = ""}]\n'),
        }
        for name, lock in variants.items():
            with self.subTest(variant=name):
                mint_pin = self._mint_pin(lock)
                self.assertEqual(mint_pin, "0.1.0",
                                 f"mint does not accept {name} as pinning 0.1.0")
                for ver in ("0.1.0", "0.2.0"):
                    self._make_probe_layer(ver)
                (self.project / "mint.lock").write_text(lock, encoding="utf-8")
                result = subprocess.run(
                    [str(BIN), "data", "list"],
                    capture_output=True, text=True, env=self.env,
                    cwd=str(self.project), timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                chosen = None
                for line in self.exec_log.read_text().splitlines():
                    if "/data-layer@" in line:
                        chosen = line.split("data-layer@")[1].split("/")[0]
                self.assertEqual(chosen, mint_pin)


if __name__ == "__main__":
    unittest.main()
