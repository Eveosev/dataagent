#!/usr/bin/env python3
"""set_baseline.py 自测：写入、回滚、缺 scorecard 时拒绝。

用临时目录里的假 run 验证，不碰真实 tasks/ 与 registry.json。
运行：uv run --offline --with pytest pytest -q tools/tests harness/tests -k baseline
     或 python3 -I tools/tests/test_set_baseline.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "set_baseline.py"
ROUND = "r001-2026-11-18"
ROUND2 = "r002-2026-11-18"
TASKS = {
    "B02": {"slug": "doc-parse-ocr", "metric": "text_ned", "direction": "lower", "tier": "block"},
    "B03": {"slug": "field-extraction-anchor", "metric": "value_f1", "direction": "higher", "tier": "block"},
    "B16": {"slug": "multi-source-alignment", "metric": "entity_pair_f1", "direction": "higher", "tier": "warn"},
    "B17": {"slug": "schema-matching", "metric": "mapping_top1", "direction": "higher", "tier": "warn"},
}
SPLIT_COUNTS = {"development": 30, "regression": 20, "unseen_acceptance": 10}


class BaselineCase(unittest.TestCase):
    """每个用例一份独立的最小 benchmark 目录。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="set-baseline-")
        self.base = Path(self._tmp.name)
        self.registry = {
            "version": "v0.3",
            "date": "2026-11-18",
            "tasks": [
                {
                    "id": tid,
                    "slug": spec["slug"],
                    "title": tid,
                    "path": f"tasks/{tid}-{spec['slug']}",
                    "primary_metric": spec["metric"],
                    "gate_tier": spec["tier"],
                    "in_ci": True,
                    "status": "collecting",
                    "baseline_run": None,
                    "last_run": None,
                }
                for tid, spec in TASKS.items()
            ],
            "rounds": [],
        }
        for tid, spec in TASKS.items():
            self._write_task(tid, spec)
        self.write_registry()
        for tid in TASKS:
            self.add_run(tid, ROUND)
        self.add_round(ROUND)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ---- 假数据 -------------------------------------------------------------

    def task_dir(self, tid: str) -> Path:
        return self.base / f"tasks/{tid}-{TASKS[tid]['slug']}"

    def _write_task(self, tid: str, spec: dict) -> None:
        tdir = self.base / f"tasks/{tid}-{spec['slug']}"
        (tdir / "history" / "runs").mkdir(parents=True)
        task = {
            "id": tid,
            "slug": spec["slug"],
            "title": tid,
            "plan_row": int(tid[1:]),
            "catalog_atoms": ["DA01.1.1"],
            "slice": "S0",
            "unit": "case",
            "graders": [spec["metric"]],
            "metrics": [
                {
                    "id": spec["metric"],
                    "label": spec["metric"],
                    "direction": spec["direction"],
                    "primary": True,
                    "unit": "ratio",
                    "aggregation": "mean_over_cases",
                    "grader": spec["metric"],
                    "threshold_status": "pending_baseline",
                }
            ],
            "gate": {"tier": spec["tier"], "in_ci": True, "blocking_metrics": [spec["metric"]]},
            "status": "collecting",
        }
        self.dump(tdir / "task.json", task)
        self.dump(
            tdir / "history" / "baseline.json",
            {
                "task_id": tid,
                "run_id": None,
                "updated": None,
                "metrics": {},
                "note": "尚无基线；首次 r 轮次完成后由裁定人写入",
            },
        )

    def add_run(
        self,
        tid: str,
        rid: str,
        *,
        values: dict[str, float | None] | None = None,
        status: str = "scored",
        verdict: str = "pass",
    ) -> Path:
        spec = TASKS[tid]
        values = values or {"development": 0.2, "regression": 0.4, "unseen_acceptance": 0.6}
        run_dir = self.task_dir(tid) / "history" / "runs" / rid
        run_dir.mkdir(parents=True, exist_ok=True)
        self.dump(
            run_dir / "run.json",
            {
                "run_id": rid,
                "round_id": rid,
                "task_id": tid,
                "status": status,
                "env": {"adapter": "dataagent-cli", "model": "test-model"},
                "dataset_ref": {"revision": "v0.9", "splits": list(SPLIT_COUNTS)},
                "samples": {"total": sum(SPLIT_COUNTS.values()), "scored": sum(SPLIT_COUNTS.values()), "missing": []},
                "started_at": "2026-11-18T10:00:00+08:00",
                "finished_at": "2026-11-18T10:05:00+08:00",
                "cost": None,
                "artifacts": [],
            },
        )
        split_scores = {}
        for split, count in SPLIT_COUNTS.items():
            value = values.get(split)
            metrics = {}
            if count and value is not None:
                metrics[spec["metric"]] = {
                    "value": value,
                    "numerator": round(value * count, 6),
                    "denominator": count,
                    "judgeable": count,
                    "missing": 0,
                }
            split_scores[split] = {"count": count, "metrics": metrics}
        self.dump(
            run_dir / "scorecard.json",
            {
                "run_id": rid,
                "task_id": tid,
                "baseline_run": None,
                "split_scores": split_scores,
                "deltas": {},
                "verdict": verdict,
                "gate": {"tier": spec["tier"], "decision": "release", "blockers": []},
            },
        )
        return run_dir

    def add_round(self, rid: str) -> None:
        slots = {
            tid: {
                "run_dir": f"tasks/{tid}-{TASKS[tid]['slug']}/history/runs/{rid}",
                "status": "scored",
                "verdict": "pass",
                "gate": None,
            }
            for tid in TASKS
        }
        self.dump(
            self.base / "rounds" / f"{rid}.json",
            {
                "round_id": rid,
                "label": "baseline",
                "created": "2026-11-18T10:00:00+08:00",
                "env": {"adapter": "dataagent-cli", "model": "test-model", "agent_kernel": "agent-kernel@test"},
                "tasks": slots,
                "aggregate": {"gate": "pending", "blockers": [], "notes": None},
            },
        )

    # ---- 读写辅助 -----------------------------------------------------------

    @staticmethod
    def dump(path: Path, obj) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def write_registry(self) -> None:
        self.dump(self.base / "registry.json", self.registry)

    def registry_task(self, tid: str) -> dict:
        return next(t for t in self.load(self.base / "registry.json")["tasks"] if t["id"] == tid)

    def baseline(self, tid: str) -> dict:
        return self.load(self.task_dir(tid) / "history/baseline.json")

    def snapshot_path(self, tid: str) -> Path:
        return self.task_dir(tid) / "history/baseline.prev.json"

    def run_tool(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-I", str(TOOL), "--base", str(self.base), *args],
            capture_output=True,
            text=True,
        )

    # ---- 写入 ---------------------------------------------------------------

    def test_baseline_write_uses_unseen_acceptance_and_updates_registry(self) -> None:
        proc = self.run_tool("--round", ROUND, "--tasks", "B02")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        baseline = self.baseline("B02")
        self.assertEqual(baseline["run_id"], ROUND)
        self.assertEqual(baseline["task_id"], "B02")
        self.assertEqual(baseline["dataset_revision"], "v0.9")
        self.assertEqual(baseline["gate_tier"], "block")
        self.assertEqual(baseline["verdict"], "pass")
        metric = baseline["metrics"]["text_ned"]
        self.assertEqual(metric["value"], 0.6)
        self.assertEqual(metric["split"], "unseen_acceptance")
        self.assertEqual(metric["numerator"], 6)
        self.assertEqual(metric["denominator"], 10)
        self.assertEqual(metric["direction"], "lower")
        self.assertIn("06 Q10", baseline["note"])
        self.assertEqual(self.registry_task("B02")["baseline_run"], ROUND)
        self.assertIsNone(self.registry_task("B03")["baseline_run"])
        snapshot = self.load(self.snapshot_path("B02"))
        self.assertIsNone(snapshot["baseline"]["run_id"])
        self.assertIsNone(snapshot["registry_baseline_run"])
        self.assertEqual(snapshot["new_run"], ROUND)
        self.assertIn("unseen_acceptance", proc.stdout)

    def test_baseline_write_all_four_tasks(self) -> None:
        proc = self.run_tool("--round", ROUND, "--tasks", "B02,B03,B16,B17")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for tid, spec in TASKS.items():
            baseline = self.baseline(tid)
            self.assertEqual(baseline["run_id"], ROUND, tid)
            self.assertEqual(baseline["metrics"][spec["metric"]]["value"], 0.6, tid)
            self.assertEqual(self.registry_task(tid)["baseline_run"], ROUND, tid)
            self.assertTrue(self.snapshot_path(tid).exists(), tid)
        self.assertIn("已写入 4 个基线", proc.stdout)

    def test_baseline_repeat_write_keeps_initial_snapshot(self) -> None:
        original = self.baseline("B02")
        first = self.run_tool("--round", ROUND, "--tasks", "B02")
        self.assertEqual(first.returncode, 0, first.stderr)
        snapshot = self.load(self.snapshot_path("B02"))
        self.assertIsNone(snapshot["baseline"]["run_id"])

        second = self.run_tool("--round", ROUND, "--tasks", "B02")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("保留原快照", second.stdout)
        self.assertEqual(self.load(self.snapshot_path("B02")), snapshot)

        proc = self.run_tool("--revert", "--tasks", "B02")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.baseline("B02"), original)
        self.assertIsNone(self.registry_task("B02")["baseline_run"])
        self.assertFalse(self.snapshot_path("B02").exists())

    def test_baseline_refuses_missing_scorecard_without_partial_write(self) -> None:
        (self.task_dir("B03") / "history" / "runs" / ROUND / "scorecard.json").unlink()
        proc = self.run_tool("--round", ROUND, "--tasks", "B02,B03,B16,B17")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("scorecard.json", proc.stderr)
        self.assertIn("未写入任何基线", proc.stderr)
        for tid in TASKS:
            self.assertIsNone(self.baseline(tid)["run_id"], tid)
            self.assertIsNone(self.registry_task(tid)["baseline_run"], tid)
            self.assertFalse(self.snapshot_path(tid).exists(), tid)

    def test_baseline_refuses_run_not_scored(self) -> None:
        self.add_run("B16", ROUND, status="running")
        proc = self.run_tool("--round", ROUND, "--tasks", "B16")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("status='running'", proc.stderr)
        self.assertIn("status=scored", proc.stderr)
        self.assertIsNone(self.baseline("B16")["run_id"])
        self.assertIsNone(self.registry_task("B16")["baseline_run"])

    def test_baseline_refuses_exploration_round(self) -> None:
        proc = self.run_tool("--round", "x001-2026-11-18", "--tasks", "B02")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("探索轮", proc.stderr)
        self.assertIsNone(self.baseline("B02")["run_id"])

    def test_baseline_accepts_zero_score(self) -> None:
        self.add_run(
            "B02",
            ROUND,
            values={"development": 0.0, "regression": 0.0, "unseen_acceptance": 0.0},
        )
        proc = self.run_tool("--round", ROUND, "--tasks", "B02")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        metric = self.baseline("B02")["metrics"]["text_ned"]
        self.assertEqual(metric["value"], 0.0)
        self.assertEqual(metric["split"], "unseen_acceptance")

    def test_baseline_refuses_round_slot_mismatch(self) -> None:
        round_path = self.base / "rounds" / f"{ROUND}.json"
        round_obj = self.load(round_path)
        round_obj["tasks"]["B02"]["run_dir"] = "tasks/B02-doc-parse-ocr/history/runs/r999-2026-11-18"
        self.dump(round_path, round_obj)
        proc = self.run_tool("--round", ROUND, "--tasks", "B02")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("run_dir", proc.stderr)
        self.assertIsNone(self.baseline("B02")["run_id"])

    def test_baseline_refuses_missing_primary_score(self) -> None:
        self.add_run(
            "B17",
            ROUND,
            values={"development": None, "regression": None, "unseen_acceptance": None},
        )
        proc = self.run_tool("--round", ROUND, "--tasks", "B17")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("mapping_top1", proc.stderr)
        self.assertIn("都没有分数", proc.stderr)
        self.assertIsNone(self.baseline("B17")["run_id"])

    # ---- 回滚 ---------------------------------------------------------------

    def test_baseline_revert_restores_empty_baseline(self) -> None:
        original = self.baseline("B02")
        self.assertEqual(self.run_tool("--round", ROUND, "--tasks", "B02").returncode, 0)
        proc = self.run_tool("--revert", "--tasks", "B02")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.baseline("B02"), original)
        self.assertIsNone(self.registry_task("B02")["baseline_run"])
        self.assertFalse(self.snapshot_path("B02").exists())
        self.assertIn("r001-2026-11-18 -> null", proc.stdout)
        again = self.run_tool("--revert", "--tasks", "B02")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("无可回滚", again.stderr)

    def test_baseline_revert_restores_previous_baseline(self) -> None:
        for tid in TASKS:
            self.add_run(tid, ROUND2, values={"development": 0.3, "regression": 0.3, "unseen_acceptance": 0.4})
        self.add_round(ROUND2)
        self.assertEqual(self.run_tool("--round", ROUND, "--tasks", "B02").returncode, 0)
        first = self.baseline("B02")
        self.assertEqual(self.run_tool("--round", ROUND2, "--tasks", "B02").returncode, 0)
        self.assertEqual(self.baseline("B02")["run_id"], ROUND2)
        proc = self.run_tool("--revert", "--round", ROUND2, "--tasks", "B02")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.baseline("B02"), first)
        self.assertEqual(self.registry_task("B02")["baseline_run"], ROUND)
        self.assertFalse(self.snapshot_path("B02").exists())

    def test_baseline_revert_round_filter_skips_other_round_snapshots(self) -> None:
        for tid in TASKS:
            self.add_run(tid, ROUND2, values={"development": 0.3, "regression": 0.3, "unseen_acceptance": 0.4})
        self.add_round(ROUND2)
        self.assertEqual(self.run_tool("--round", ROUND, "--tasks", "B02").returncode, 0)
        self.assertEqual(self.run_tool("--round", ROUND2, "--tasks", "B02").returncode, 0)
        wrong = self.run_tool("--revert", "--round", ROUND)
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("没有找到", wrong.stderr)
        self.assertEqual(self.baseline("B02")["run_id"], ROUND2)
        right = self.run_tool("--revert", "--round", ROUND2)
        self.assertEqual(right.returncode, 0, right.stderr)
        self.assertEqual(self.baseline("B02")["run_id"], ROUND)

    def test_baseline_warns_but_writes_when_verdict_pending(self) -> None:
        self.add_run("B03", ROUND, verdict="pending")
        proc = self.run_tool("--round", ROUND, "--tasks", "B03")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("verdict=pending", proc.stdout)
        self.assertEqual(self.baseline("B03")["run_id"], ROUND)

    def test_baseline_revert_all_snapshots_without_tasks(self) -> None:
        self.assertEqual(self.run_tool("--round", ROUND, "--tasks", "B02,B03").returncode, 0)
        proc = self.run_tool("--revert")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for tid in ("B02", "B03"):
            self.assertIsNone(self.baseline(tid)["run_id"], tid)
            self.assertIsNone(self.registry_task(tid)["baseline_run"], tid)
            self.assertFalse(self.snapshot_path(tid).exists(), tid)
        self.assertIn("已回滚 2 个基线", proc.stdout)

    def test_baseline_help(self) -> None:
        proc = self.run_tool("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("set_baseline.py", proc.stdout)
        self.assertIn("--revert", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
