#!/usr/bin/env python3
"""跑一个任务的一个 split（或全部），产出 run.json / cases.jsonl / artifacts / scorecard。

用法：
  python3 -I harness/run.py --task B02 --adapter oracle --round-id x001-2026-11-05
  python3 -I harness/run.py --task B02 --adapter empty  --round-id x002-2026-11-05 --split development
  python3 -I harness/run.py --task B02 --adapter dataagent-cli --round-id x003-2026-11-05 --limit 5

约束：
- 只写 tasks/<task>/history/runs/<round-id>/，不动 cases/expected；
- 适配器失败必须如实进 cases.jsonl 与 run.json.samples.missing，不伪造输出；
- 跑完自动调用 grade.py 写 scorecard.json，再跑 tools/check.py 可校验一致性。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE.parent
SPLITS = ("development", "regression", "unseen_acceptance")


def load_task(task_id: str) -> tuple[dict, pathlib.Path]:
    registry = json.loads((BENCH / "registry.json").read_text(encoding="utf-8"))
    entry = next((t for t in registry["tasks"] if t["id"] == task_id), None)
    if entry is None:
        raise SystemExit(f"registry 里没有 {task_id}")
    tdir = BENCH / entry["path"]
    return json.loads((tdir / "task.json").read_text(encoding="utf-8")), tdir


def load_adapter(name: str):
    path = HERE / "adapters" / f"{name}.py"
    if not path.exists():
        raise SystemExit(f"适配器不存在: {path}")
    spec = importlib.util.spec_from_file_location(f"adapter_{name.replace('-', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "run_case"):
        raise SystemExit(f"适配器 {name} 缺少 run_case()")
    return module


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--round-id", required=True, help="rNNN-YYYY-MM-DD 或 xNNN-YYYY-MM-DD")
    ap.add_argument("--split", choices=SPLITS)
    ap.add_argument("--limit", type=int, help="每个 split 最多跑多少条（调试用）")
    ap.add_argument("--config", default=str(HERE / "config.default.json"))
    args = ap.parse_args()

    task, tdir = load_task(args.task)
    dataset = tdir / "dataset"
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    adapter = load_adapter(args.adapter)

    run_id = args.round_id
    run_dir = tdir / "history" / "runs" / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise SystemExit(f"run 目录已存在且非空，换一个 round-id: {run_dir}")
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    base_cfg = json.loads(pathlib.Path(args.config).read_text(encoding="utf-8"))
    base_cfg.update({"run_dir": str(run_dir), "dataset_dir": str(dataset)})
    env = {
        "adapter": args.adapter,
        "model": None if args.adapter in {"oracle", "empty"} else base_cfg.get("env", {}).get("model"),
        "agent_kernel": base_cfg.get("env", {}).get("agent_kernel"),
        "dataagent": base_cfg.get("env", {}).get("dataagent"),
        "harness": base_cfg.get("env", {}).get("harness") or "09-benchmark@v0.1",
        "task_id": args.task,
    }

    splits = [args.split] if args.split else list(SPLITS)
    started = now()
    attempts = []
    predictions = []
    missing = []
    artifacts = []
    tokens = 0
    cost = 0.0
    total = 0

    for split in splits:
        cases = sorted((dataset / "cases" / split).glob("*.json"))
        if args.limit:
            cases = cases[: args.limit]
        for path in cases:
            total += 1
            case = json.loads(path.read_text(encoding="utf-8"))
            case["_path"] = str(path)
            result = adapter.run_case(case, env, base_cfg)
            record = {
                "case_id": case["case_id"],
                "split": split,
                "attempt": 1,
                "status": result.get("status"),
                "output_ref": None,
                "latency_ms": result.get("latency_ms"),
                "tokens": result.get("tokens") or 0,
                "cost_usd": result.get("cost_usd") or 0.0,
                "error": result.get("error"),
            }
            tokens += record["tokens"]
            cost += record["cost_usd"]
            if result.get("status") == "ok" and result.get("output") is not None:
                rel = f"artifacts/{case['case_id']}.json"
                (run_dir / rel).write_text(json.dumps(result["output"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                artifacts.append(rel)
                record["output_ref"] = rel
                predictions.append({"case_id": case["case_id"], "output": {"ref": rel}})
            else:
                missing.append(case["case_id"])
            attempts.append(record)

    (run_dir / "cases.jsonl").write_text(
        "\n".join(json.dumps(a, ensure_ascii=False) for a in attempts) + "\n", encoding="utf-8"
    )
    (run_dir / "predictions.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in predictions) + "\n", encoding="utf-8"
    )

    status = "scored" if predictions else "failed"
    run = {
        "run_id": run_id,
        "round_id": run_id,
        "task_id": args.task,
        "status": status,
        "env": env,
        "dataset_ref": {"revision": manifest.get("revision"), "splits": splits},
        "samples": {"total": total, "scored": len(predictions), "missing": missing},
        "started_at": started,
        "finished_at": now(),
        "cost": {"usd": round(cost, 6), "tokens": tokens},
        "artifacts": artifacts,
    }
    (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{args.task} {args.adapter} {run_id}: {len(predictions)}/{total} ok  ->  {run_dir}")
    if predictions:
        cmd = [sys.executable, "-I", str(HERE / "grade.py"), "--task", args.task,
               "--pred", str(run_dir / "predictions.jsonl"), "--run-id", run_id,
               "--out", str(run_dir / "scorecard.json"), "--detail", str(run_dir / "detail.jsonl")]
        if args.split:
            cmd += ["--split", args.split]
        subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
