"""Dispatcher functional tests for `dataagent/cli` bin (12 W3/W4).

stdlib only (unittest + subprocess): builds a temporary Mint project layout
with fake layer `.venv` interpreters and exercises dispatch, version
resolution, environment scrubbing, `link`, and the exit-code contract.
"""

from __future__ import annotations

import json
import os
import shutil
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
        *DATAAGENT_OCR_DOCTOR_PROBE*)
            # doctor / setup OCR probe (07 §2.3 T20): the pin is configured
            # iff the marker file exists, otherwise the "none" hint + rc 1;
            # the remote marker makes it report a remote provider (rc 3).
            if [ -f "$DATAAGENT_FAKE_OCR_REMOTE" ]; then
                echo "ocr:      openai_compat fake-model is remote — the data layer does not use remote OCR before the egress gate (T15); scanned-document probes need a local engine" >&2
                exit 3
            fi
            if [ -f "$DATAAGENT_FAKE_OCR" ]; then
                printf 'ocr:      openai_compat fake-model version=fake@r1:abc123456789 verification=ocrv-fake\\n'
                exit 0
            fi
            echo "ocr:      none (run: dataagent setup --ocr-root <verified ocr dir>)" >&2
            exit 1
            ;;
        *DATAAGENT_CONNECTIONS_DOCTOR_PROBE*)
            if [ -f "$DATAAGENT_FAKE_CONNECTIONS_BAD" ]; then
                echo "connections: fake manifest (fake)"
                echo "  credential token (env:FAKE_TOKEN): missing; repair: export FAKE_TOKEN=<value>"
                exit 1
            fi
            echo "connections: none (fake)"
            exit 0
            ;;
        *DATAAGENT_WORKBENCH_SERVICE_DOCTOR_PROBE*)
            echo "service:  none for this workspace"
            exit 0
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
            "DATAAGENT_FAKE_OCR": str(self.out / "ocr"),
            "DATAAGENT_FAKE_OCR_REMOTE": str(self.out / "ocr-remote"),
            "DATAAGENT_FAKE_CONNECTIONS_BAD": str(self.out / "connections-bad"),
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

    def _fake_uv(self):
        """Put a no-op uv shim first on PATH so setup_cmd runs offline."""
        bin_dir = self.out / "bin"
        bin_dir.mkdir(exist_ok=True)
        shim = bin_dir / "uv"
        shim.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        shim.chmod(0o755)
        self.env["PATH"] = f"{bin_dir}:{self.env['PATH']}"
        return shim

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
        self.assertIn("请在 Mint 项目目录执行", result.stderr)
        self.assertIn("dataagent/preset-intake", result.stderr)
        self.assertNotIn("preset-s0", result.stderr)

    def test_workbench_list_and_stop_dispatch(self):
        """FDE-16/FDE-17: both workbench subcommands reach the layer CLI."""
        _make_layer(self.project, "workbench", "0.1.0")
        for command in ("list", "stop"):
            result = self._run("workbench", command)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = (self.out / "args").read_text().splitlines()
            self.assertEqual(args[1], "dataagent_workbench.interfaces.cli")
            self.assertEqual(args[2], command)

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
        (self.out / "ocr").write_text("", encoding="utf-8")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("venv     data-layer: ok", result.stdout)
        self.assertIn("policy:   configured", result.stdout)
        self.assertIn("data_root:", result.stdout)
        self.assertIn("ocr:      openai_compat fake-model version=fake@r1:", result.stdout)

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

    def test_doctor_missing_ocr_is_a_failing_check(self):
        """07 §2.3 T20: OCR is the data layer's explicit dependency. A missing
        engine is reported with the configuration item and never as ok (same
        fail-closed reading as the policy check, r5-review D14)."""
        _make_layer(self.project, "data-layer", "0.1.0")
        _make_layer(self.project, "workbench", "0.1.0")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("ocr:      none", result.stderr)
        self.assertIn("dataagent setup --ocr-root", result.stderr)
        self.assertNotIn("ocr:      openai_compat", result.stdout)

    def test_doctor_remote_ocr_is_a_failing_check(self):
        """07 §2.3 T20 (调度方 11-18 补充): a remote OCR provider must not be
        reported as ok — the data layer refuses remote OCR until the egress
        gate lands (T15), so scanned-document probes would not work; doctor
        says so explicitly."""
        _make_layer(self.project, "data-layer", "0.1.0")
        _make_layer(self.project, "workbench", "0.1.0")
        (self.out / "ocr-remote").write_text("", encoding="utf-8")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 3)
        self.assertIn("remote OCR before the egress gate (T15)", result.stderr)
        self.assertIn("scanned-document probes need a local engine", result.stderr)
        self.assertNotIn("version=", result.stdout)  # never reported as ok

    def test_setup_ocr_root_accepts_remote_pin_with_warning(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        _make_layer(self.project, "workbench", "0.1.0")
        self._fake_uv()
        (self.out / "ocr-remote").write_text("", encoding="utf-8")
        source = self.project / "ocr-src"
        source.mkdir()
        (source / "active.json").write_text('{"profile_id": "fake"}\n', encoding="utf-8")
        result = self._run("setup", "--ocr-root", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / ".dataagent" / "ocr" / "active.json").is_file())
        self.assertIn("remote OCR before the egress gate (T15)", result.stderr)
        # doctor then reports the limitation instead of ok
        doctor = self._run("doctor")
        self.assertEqual(doctor.returncode, 3)
        self.assertIn("scanned-document probes need a local engine", doctor.stderr)

    def test_doctor_without_data_layer_skips_ocr_check(self):
        _make_layer(self.project, "workbench", "0.1.0")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("ocr:", result.stdout + result.stderr)

    def test_doctor_connection_check_failure_exits_3(self):
        """FDE-1: an unresolvable credential makes doctor fail with a repair hint."""
        _make_layer(self.project, "workbench", "0.1.0")
        result = self._run("doctor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("connections: none (fake)", result.stdout)
        self.assertIn("service:  none for this workspace", result.stdout)

        (self.out / "connections-bad").write_text("", encoding="utf-8")
        failed = self._run("doctor")
        self.assertEqual(failed.returncode, 3, failed.stdout + failed.stderr)
        self.assertIn("credential token (env:FAKE_TOKEN): missing", failed.stderr)
        self.assertIn("repair: export FAKE_TOKEN=<value>", failed.stderr)

    def test_setup_ocr_root_installs_verified_directory(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        _make_layer(self.project, "workbench", "0.1.0")
        self._fake_uv()
        (self.out / "ocr").write_text("", encoding="utf-8")  # probe validates
        source = self.project / "ocr-src"
        source.mkdir()
        (source / "active.json").write_text('{"profile_id": "fake"}\n', encoding="utf-8")
        (source / "profiles").mkdir()
        result = self._run("setup", "--ocr-root", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.project / ".dataagent" / "ocr"
        self.assertEqual(
            (installed / "active.json").read_text(encoding="utf-8"),
            '{"profile_id": "fake"}\n',
        )
        self.assertIn("setup: ocr configured from", result.stdout)
        # re-running with the same source is idempotent
        again = self._run("setup", "--ocr-root", str(source))
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("setup: ocr already configured at", again.stdout)

    def test_setup_ocr_root_rejects_directory_without_pin(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        _make_layer(self.project, "workbench", "0.1.0")
        self._fake_uv()
        source = self.project / "ocr-src"
        source.mkdir()
        result = self._run("setup", "--ocr-root", str(source))
        self.assertEqual(result.returncode, 3)
        self.assertIn("not a verified OCR directory", result.stderr)
        self.assertFalse((self.project / ".dataagent" / "ocr").exists())

    def test_setup_ocr_root_refuses_to_replace_a_different_pin(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        _make_layer(self.project, "workbench", "0.1.0")
        self._fake_uv()
        source = self.project / "ocr-src"
        source.mkdir()
        (source / "active.json").write_text('{"profile_id": "new"}\n', encoding="utf-8")
        existing = self.project / ".dataagent" / "ocr"
        existing.mkdir(parents=True)
        (existing / "active.json").write_text('{"profile_id": "old"}\n', encoding="utf-8")
        result = self._run("setup", "--ocr-root", str(source))
        self.assertEqual(result.returncode, 3)
        self.assertIn("different OCR configuration", result.stderr)
        # the existing pin is untouched
        self.assertEqual(
            (existing / "active.json").read_text(encoding="utf-8"),
            '{"profile_id": "old"}\n',
        )



    def test_run_dispatches_case_to_data_layer_bench(self):
        """07 T30: `run --case` executes the benchmark entry point from the
        data layer, preserving every adapter flag."""
        _make_layer(self.project, "data-layer", "0.1.0")
        result = self._run(
            "run",
            "--case",
            "case.json",
            "--out",
            "out/B02-od-0005",
            "--config",
            "cfg.json",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = (self.out / "args").read_text().splitlines()
        self.assertEqual(args[0], "-m")
        self.assertEqual(args[1], "dataagent_runtime.interfaces.bench")
        self.assertEqual(
            args[2:],
            [
                "--case",
                "case.json",
                "--out",
                "out/B02-od-0005",
                "--config",
                "cfg.json",
            ],
        )

    def test_run_uses_sibling_bundle_without_mint(self):
        """The build/local install product has sibling package directories;
        `run` must use them when the project has no .mint tree (T30)."""
        bundle = self.project / "bundle"
        (bundle / "cli" / "bin").mkdir(parents=True)
        copied = bundle / "cli" / "bin" / "dataagent"
        shutil.copy2(BIN, copied)
        layer = bundle / "data-layer"
        (layer / ".venv" / "bin").mkdir(parents=True)
        py = layer / ".venv" / "bin" / "python"
        py.write_text(FAKE_PYTHON, encoding="utf-8")
        py.chmod(0o755)
        result = subprocess.run(
            [str(copied), "run", "--case", "case.json", "--out", "out", "--config", "cfg.json"],
            capture_output=True,
            text=True,
            env=self.env,
            cwd=str(self.out),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = (self.out / "args").read_text().splitlines()
        self.assertEqual(args[1], "dataagent_runtime.interfaces.bench")
        self.assertIn("bundle/data-layer", (self.out / "cwd").read_text())

    def test_run_without_data_layer_exits_3(self):
        result = self._run("run", "--case", "case.json", "--out", "out")
        self.assertEqual(result.returncode, 3)
        self.assertIn("dataagent/data-layer is not installed", result.stderr)
        self.assertFalse((self.out / "args").exists())

    def test_run_auto_syncs_a_bundle_without_venv(self):
        """build/local ships a frozen lock but not a .venv; first use installs
        it instead of failing with the layer command's "run setup" error."""
        layer = _make_layer(self.project, "data-layer", "0.1.0")
        (layer / ".venv" / "bin" / "python").unlink()
        bin_dir = self.out / "bin"
        bin_dir.mkdir()
        fake_python = self.out / "fake-python"
        fake_python.write_text(FAKE_PYTHON, encoding="utf-8")
        fake_python.chmod(0o755)
        uv_log = self.out / "uv-log"
        shim = bin_dir / "uv"
        shim.write_text(
            "#!/bin/sh\n"
            'printf "%s\\n" "$@" > "$DATAAGENT_FAKE_UV_LOG"\n'
            "mkdir -p .venv/bin\n"
            'cp "$DATAAGENT_FAKE_PYTHON" .venv/bin/python\n'
            "chmod +x .venv/bin/python\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)
        self.env["PATH"] = f"{bin_dir}:{self.env['PATH']}"
        self.env["DATAAGENT_FAKE_PYTHON"] = str(fake_python)
        self.env["DATAAGENT_FAKE_UV_LOG"] = str(uv_log)
        result = self._run("run", "--case", "case.json", "--out", "out")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(uv_log.read_text().splitlines(), ["sync", "--frozen"])
        self.assertEqual(
            (self.out / "args").read_text().splitlines()[1],
            "dataagent_runtime.interfaces.bench",
        )

    def test_run_keeps_ocr_root_after_environment_scrub(self):
        _make_layer(self.project, "data-layer", "0.1.0")
        self.env["OCR_ROOT"] = "/tmp/verified-ocr"
        result = self._run("run", "--case", "case.json", "--out", "out")
        self.assertEqual(result.returncode, 0, result.stderr)
        env = (self.out / "env").read_text()
        self.assertIn("OCR_ROOT=/tmp/verified-ocr", env)
        self.assertIn("DATAAGENT_OCR_ROOT=/tmp/verified-ocr", env)
        self.assertNotIn("MINT_MODEL_API_KEY", env)
        self.assertNotIn("secret-token", env)


if __name__ == "__main__":
    unittest.main()
