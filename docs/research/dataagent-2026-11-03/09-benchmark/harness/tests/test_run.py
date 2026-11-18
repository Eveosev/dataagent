#!/usr/bin/env python3
"""run.py 自测：new_round 生成的待跑骨架可续跑，已跑过的目录仍拒绝。

运行：uv run --offline --with pytest python -m pytest -q harness/tests
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE.parent.parent
REAL_HARNESS = BENCH / "harness"
NEW_ROUND = BENCH / "tools" / "new_round.py"
ROUND = "r001-2026-11-18"
TASK_DIR = "tasks/B01-irregular-table"


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = load_module(REAL_HARNESS / "run.py", "bench_run_under_test")


def write_skeleton(run_dir: pathlib.Path, status: str = "pending") -> None:
    """按 new_round.py 的形状写一份最小骨架。"""
    run = {
        "run_id": ROUND,
        "round_id": ROUND,
        "task_id": "B01",
        "status": status,
        "env": {"adapter": "oracle", "model": None},
        "dataset_ref": {"revision": "v0.2", "splits": ["development", "regression", "unseen_acceptance"]},
        "samples": {"total": 0, "scored": 0, "missing": []},
        "started_at": "2026-11-18T00:00:00+08:00",
        "finished_at": None,
        "cost": None,
        "artifacts": [],
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "scorecard.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "artifacts").mkdir(exist_ok=True)


class TestPendingSkeleton(unittest.TestCase):
    """is_pending_skeleton 的判定口径。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="run-skeleton-")
        self.run_dir = pathlib.Path(self._tmp.name) / ROUND
        write_skeleton(self.run_dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_new_round_skeleton_is_recognized(self):
        self.assertTrue(RUN.is_pending_skeleton(self.run_dir))

    def test_scored_run_dir_is_not_skeleton(self):
        write_skeleton(self.run_dir, status="scored")
        self.assertFalse(RUN.is_pending_skeleton(self.run_dir))

    def test_pending_status_with_predictions_is_not_skeleton(self):
        (self.run_dir / "predictions.jsonl").write_text('{"case_id": "B01-x-001", "output": {}}\n', encoding="utf-8")
        self.assertFalse(RUN.is_pending_skeleton(self.run_dir))

    def test_pending_status_with_artifact_file_is_not_skeleton(self):
        (self.run_dir / "artifacts" / "B01-x-001.json").write_text("{}\n", encoding="utf-8")
        self.assertFalse(RUN.is_pending_skeleton(self.run_dir))

    def test_unknown_extra_file_is_not_skeleton(self):
        (self.run_dir / "notes.txt").write_text("hand edit\n", encoding="utf-8")
        self.assertFalse(RUN.is_pending_skeleton(self.run_dir))

    def test_corrupt_run_json_is_not_skeleton(self):
        (self.run_dir / "run.json").write_text("{not json\n", encoding="utf-8")
        self.assertFalse(RUN.is_pending_skeleton(self.run_dir))


class TestNewRoundSkeletonRun(unittest.TestCase):
    """端到端：new_round 骨架被 run.py 接受；跑完后再跑必须拒绝。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="run-e2e-")
        self.bench = pathlib.Path(self._tmp.name) / "bench"
        self._build_bench()
        self._call_new_round()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _build_bench(self) -> None:
        self.bench.mkdir()
        (self.bench / "rounds").mkdir()
        shutil.copytree(
            REAL_HARNESS,
            self.bench / "harness",
            ignore=shutil.ignore_patterns("config.local.json", "__pycache__"),
        )
        registry = {
            "version": "test",
            "date": "2026-11-18",
            "tasks": [
                {
                    "id": "B01",
                    "slug": "irregular-table",
                    "path": TASK_DIR,
                    "gate_tier": "block",
                    "in_ci": True,
                    "status": "collecting",
                    "primary_metric": "downstream_qa_accuracy",
                }
            ],
            "rounds": [],
        }
        (self.bench / "registry.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

        src = BENCH / TASK_DIR
        dst = self.bench / TASK_DIR
        (dst / "dataset" / "cases").mkdir(parents=True)
        (dst / "history").mkdir()
        shutil.copy2(src / "task.json", dst / "task.json")
        shutil.copy2(src / "dataset" / "manifest.json", dst / "dataset" / "manifest.json")
        shutil.copy2(src / "history" / "baseline.json", dst / "history" / "baseline.json")
        for split in ("development", "regression", "unseen_acceptance"):
            (dst / "dataset" / "cases" / split).mkdir()
            (dst / "dataset" / "expected").mkdir(exist_ok=True)
        case = "B01-mimo-0001"
        shutil.copy2(src / "dataset" / "cases" / "development" / f"{case}.json",
                     dst / "dataset" / "cases" / "development" / f"{case}.json")
        shutil.copy2(src / "dataset" / "expected" / f"{case}.json",
                     dst / "dataset" / "expected" / f"{case}.json")

    def _call_new_round(self) -> None:
        module = load_module(NEW_ROUND, "bench_new_round_under_test")
        module.BASE = self.bench
        argv = [
            "new_round.py", "--label", "selftest", "--date", "2026-11-18",
            "--model", "test-model", "--kernel", "agent-kernel@test",
        ]
        old_argv = sys.argv
        sys.argv = argv
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = module.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(rc, 0)
        run_dir = self.bench / TASK_DIR / "history" / "runs" / ROUND
        self.assertEqual(json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["status"], "pending")
        self.assertTrue((run_dir / "scorecard.json").exists())

    def _run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable, "-I", str(self.bench / "harness" / "run.py"),
                "--task", "B01", "--adapter", "oracle", "--round-id", ROUND,
                "--split", "development", "--limit", "1",
            ],
            capture_output=True, text=True,
        )

    def test_skeleton_can_run_and_is_overwritten(self):
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr[-800:])
        run_dir = self.bench / TASK_DIR / "history" / "runs" / ROUND
        run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["status"], "scored")
        self.assertEqual(run["samples"], {"total": 1, "scored": 1, "missing": []})
        self.assertTrue((run_dir / "predictions.jsonl").exists())
        card = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))
        self.assertEqual(card["run_id"], ROUND)
        self.assertEqual(card["split_scores"]["development"]["count"], 1)

    def test_previously_run_dir_is_still_rejected(self):
        first = self._run()
        self.assertEqual(first.returncode, 0, first.stderr[-800:])
        second = self._run()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("run 目录已存在且非空", second.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
