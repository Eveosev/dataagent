#!/usr/bin/env python3
"""开一次新的评测轮次（round）：建立 rounds/<round-id>.json 与每个任务的 run 骨架。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/new_round.py \
        --label baseline --model deepseek-v4.1 --kernel agent-kernel@f0fa521
    python3 -I .../new_round.py --label hint-tune --prefix x   # 临时轮次，不进趋势对比

轮次 id 规则：rNNN-YYYY-MM-DD（正式轮）或 xNNN-YYYY-MM-DD（临时轮）。
已存在的轮次不会被覆盖；--dry-run 只打印将要创建的内容。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SPLITS = ("development", "regression", "unseen_acceptance")
ROUND_ID = re.compile(r"^([rx])([0-9]{3})-([0-9]{4}-[0-9]{2}-[0-9]{2})$")


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_round_id(prefix: str, date: str) -> str:
    nums = []
    for p in (BASE / "rounds").glob("*.json"):
        m = ROUND_ID.match(p.stem)
        if m and m.group(1) == prefix and m.group(3) == date:
            nums.append(int(m.group(2)))
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}-{date}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, help="轮次标签，如 baseline / hint-tune / model-swap")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--prefix", default="r", choices=["r", "x"], help="r=正式轮，x=临时轮")
    ap.add_argument("--model", default=None)
    ap.add_argument("--kernel", default=None, help="agent-kernel 版本，如 agent-kernel@f0fa521")
    ap.add_argument("--adapter", default=None, help="默认取 harness/config.default.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    registry = json.loads((BASE / "registry.json").read_text(encoding="utf-8"))
    cfg = json.loads((BASE / "harness" / "config.default.json").read_text(encoding="utf-8"))
    adapter = args.adapter or cfg["adapters"]["default"]

    round_id = next_round_id(args.prefix, args.date)
    rpath = BASE / "rounds" / f"{round_id}.json"
    if rpath.exists():
        print(f"ERROR {rpath} 已存在", file=sys.stderr)
        return 1

    slots = {}
    for t in registry["tasks"]:
        task_dir = BASE / t["path"]
        run_dir = task_dir / "history" / "runs" / round_id
        slots[t["id"]] = {
            "run_dir": f"{t['path']}/history/runs/{round_id}",
            "status": "pending",
            "verdict": "pending",
            "gate": None,
        }
        if args.dry_run:
            continue
        run = {
            "run_id": round_id,
            "round_id": round_id,
            "task_id": t["id"],
            "status": "pending",
            "env": {
                "adapter": adapter,
                "model": args.model,
                "agent_kernel": args.kernel,
                "dataagent": cfg["env"].get("dataagent"),
                "harness": cfg["env"].get("harness"),
            },
            "dataset_ref": {
                "revision": json.loads((task_dir / "dataset" / "manifest.json").read_text(encoding="utf-8"))["revision"],
                "splits": list(SPLITS),
            },
            "samples": {"total": 0, "scored": 0, "missing": []},
            "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "finished_at": None,
            "cost": None,
            "artifacts": [],
        }
        dump(run_dir / "run.json", run)
        card = {
            "run_id": round_id,
            "task_id": t["id"],
            "baseline_run": json.loads(
                (task_dir / "history" / "baseline.json").read_text(encoding="utf-8")
            )["run_id"],
            "split_scores": {s: {"count": 0, "metrics": {}} for s in SPLITS},
            "deltas": {},
            "verdict": "pending",
            "gate": {"tier": t["gate_tier"], "decision": "pending", "blockers": []},
            "notes": None,
        }
        dump(run_dir / "scorecard.json", card)

    round_obj = {
        "round_id": round_id,
        "label": args.label,
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "env": {
            "adapter": adapter,
            "model": args.model,
            "agent_kernel": args.kernel,
            "dataagent": cfg["env"].get("dataagent"),
            "harness": cfg["env"].get("harness"),
        },
        "tasks": slots,
        "aggregate": {"gate": "pending", "blockers": [], "notes": None},
    }

    if args.dry_run:
        print(json.dumps({"round_id": round_id, "slots": len(slots)}, ensure_ascii=False))
        print("dry-run：未写文件")
        return 0

    dump(rpath, round_obj)
    registry["rounds"] = sorted(set(registry.get("rounds", [])) | {round_id})
    run_by_task = {tid: slot["run_dir"] for tid, slot in slots.items()}
    for t in registry["tasks"]:
        if t["id"] in run_by_task:
            t["last_run"] = round_id
    dump(BASE / "registry.json", registry)

    print(f"已创建 rounds/{round_id}.json")
    print(f"  {len(slots)} 个 run 骨架：tasks/*/history/runs/{round_id}/")
    print("下一步：填 case → 跑 harness → 写 scorecard.json → 裁定 baseline → python3 tools/report.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
