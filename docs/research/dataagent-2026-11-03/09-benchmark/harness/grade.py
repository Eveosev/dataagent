#!/usr/bin/env python3
"""把预测结果判成分数，产出符合 schema/scorecard.schema.json 的 scorecard。

用法：
  python3 -I harness/grade.py --task B01 --pred runs/x001/predictions.jsonl \
      --run-id x001-2026-11-05 --out runs/x001/scorecard.B01.json [--detail runs/x001/detail.B01.jsonl]

预测文件每行一个 JSON：{"case_id": "B01-...", "output": {...}}，
也接受 {"case_id": "...", "output_ref": "artifacts/xxx.json"}（相对 --run-dir）。

口径：value=None 记进 missing，不进分母；聚合方式取 task.json 的 metric.aggregation。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))

from graders import REGISTRY, load  # noqa: E402
from graders.common import load_output  # noqa: E402

SPLITS = ("development", "regression", "unseen_acceptance")


def load_task(task_id: str) -> tuple[dict, pathlib.Path]:
    registry = json.loads((BENCH / "registry.json").read_text(encoding="utf-8"))
    entry = next((t for t in registry["tasks"] if t["id"] == task_id), None)
    if entry is None:
        raise SystemExit(f"registry 里没有 {task_id}")
    tdir = BENCH / entry["path"]
    return json.loads((tdir / "task.json").read_text(encoding="utf-8")), tdir


def read_predictions(path: pathlib.Path) -> dict[str, dict]:
    preds = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        case_id = rec.get("case_id")
        if not case_id:
            continue
        if "output" in rec and isinstance(rec["output"], dict):
            preds[case_id] = rec["output"]
        elif "output_ref" in rec:
            preds[case_id] = {"ref": rec["output_ref"]}
        else:
            preds[case_id] = rec
    return preds


def aggregate(metric: dict, rows: list[dict]) -> dict:
    judgeable = [r for r in rows if r.get("value") is not None]
    missing_rows = [r for r in rows if r.get("value") is None]
    mode = metric.get("aggregation") or "mean_over_cases"
    if not judgeable:
        return {
            "value": None,
            "numerator": None,
            "denominator": 0,
            "judgeable": 0,
            "missing": len(missing_rows),
            "notes": (missing_rows[0].get("notes") if missing_rows else "无可判分样本"),
        }
    if mode == "pooled":
        num = sum(r.get("numerator") or 0 for r in judgeable)
        den = sum(r.get("denominator") or 0 for r in judgeable)
        value = num / den if den else None
    elif mode in {"sum"}:
        num = sum(r["value"] for r in judgeable)
        den = len(judgeable)
        value = num
    elif mode == "median_over_series":
        import statistics

        values = sorted(r["value"] for r in judgeable)
        value = statistics.median(values)
        num, den = value, 1
    else:  # mean_over_cases
        num = sum(r["value"] for r in judgeable)
        den = len(judgeable)
        value = num / den
    return {
        "value": round(value, 6) if value is not None else None,
        "numerator": round(num, 6) if isinstance(num, (int, float)) else num,
        "denominator": int(den),
        "judgeable": len(judgeable),
        "missing": len(missing_rows),
        "notes": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--pred", required=True, help="预测 jsonl")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", required=True, help="scorecard 输出路径")
    ap.add_argument("--detail", help="逐用例判分明细 jsonl")
    ap.add_argument("--run-dir", help="预测里的相对 ref 以此为根，默认取 pred 所在目录")
    ap.add_argument("--split", choices=SPLITS, help="只判某个 split")
    args = ap.parse_args()

    task, tdir = load_task(args.task)
    dataset = tdir / "dataset"
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    baseline_path = tdir / "history" / "baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {}
    pred_path = pathlib.Path(args.pred).resolve()
    run_dir = pathlib.Path(args.run_dir).resolve() if args.run_dir else pred_path.parent
    preds = read_predictions(pred_path)
    cfg = {"run_dir": str(run_dir)}

    metrics = task.get("metrics") or []
    scores: dict[str, dict] = {}
    detail_fh = open(args.detail, "w", encoding="utf-8") if args.detail else None
    missing_total = defaultdict(int)
    for split in SPLITS:
        if args.split and split != args.split:
            continue
        case_dir = dataset / "cases" / split
        cases = []
        if case_dir.exists():
            for path in sorted(case_dir.glob("*.json")):
                case = json.loads(path.read_text(encoding="utf-8"))
                exp_path = dataset / "expected" / f"{case['case_id']}.json"
                gold = json.loads(exp_path.read_text(encoding="utf-8")) if exp_path.exists() else {}
                case["gold"] = gold
                case["expected"] = gold.get("expected") or {}
                cases.append(case)
        per_metric = {m["id"]: [] for m in metrics}
        for case in cases:
            output = load_output(preds.get(case["case_id"], {}), cfg)
            for metric in metrics:
                grader = load(metric["grader"])
                try:
                    row = grader(case, output, cfg)
                except Exception as exc:  # grader 自身异常不得静默当 0
                    row = {"metric": metric["id"], "value": None, "numerator": None, "denominator": 0,
                           "judgeable": False, "notes": f"grader error: {type(exc).__name__}: {exc}"}
                per_metric[metric["id"]].append(row)
                if row.get("value") is None:
                    missing_total[metric["id"]] += 1
                if detail_fh:
                    detail_fh.write(json.dumps({"case_id": case["case_id"], "split": split, **row}, ensure_ascii=False) + "\n")
        entries = {}
        for metric in metrics:
            agg = aggregate(metric, per_metric[metric["id"]])
            entries[metric["id"]] = agg
        scores[split] = {"count": len(cases), "metrics": entries}

    if detail_fh:
        detail_fh.close()

    tier = (task.get("gate") or {}).get("tier", "warn")
    blocking = set((task.get("gate") or {}).get("blocking_metrics") or [])
    blockers = []
    for metric in metrics:
        judgeable = sum(
            (scores.get(split) or {}).get("metrics", {}).get(metric["id"], {}).get("judgeable", 0)
            for split in SPLITS
        )
        # 只有门槛指标全不可判才算 blocker；次级指标缺金标只在分数里体现
        if judgeable == 0 and metric["id"] in blocking:
            blockers.append(f"{metric['id']}: 无可判分样本（金标缺口或未实现）")
    scorecard = {
        "run_id": args.run_id,
        "task_id": args.task,
        "baseline_run": baseline.get("run_id"),
        "split_scores": {
            s: scores.get(s) or {"count": 0, "metrics": {m["id"]: {"value": None, "numerator": None, "denominator": 0, "judgeable": 0, "missing": 0, "notes": "未运行该 split"} for m in metrics}}
            for s in SPLITS
        },
        "deltas": {},
        "verdict": "pending",
        "gate": {"tier": tier, "decision": "pending", "blockers": blockers},
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{args.task} {args.run_id}  ->  {out}")
    for metric in metrics:
        row = scorecard["split_scores"]["unseen_acceptance"]["metrics"].get(metric["id"]) or \
              scorecard["split_scores"]["development"]["metrics"].get(metric["id"])
        value = row.get("value")
        shown = "n/a" if value is None else f"{value:.4f}"
        flag = "" if value is not None else "  <- missing"
        print(f"  {metric['id']:28} {shown:>8}  judgeable={row.get('judgeable')} missing={row.get('missing')}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
