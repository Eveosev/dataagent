#!/usr/bin/env python3
"""从 rounds/ 与各任务 scorecard 生成 monitor/trend.md（迭代趋势看板）。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/report.py           # 写入 monitor/trend.md
    python3 -I .../report.py --check   # 只检查是否与产物一致，不一致退出 1（给 CI 用）

trend.md 是生成物：迭代叙事写进 tasks/<task>/NOTES.md 与 monitor/incidents/。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SPLITS = ("development", "regression", "unseen_acceptance")
TIER_ORDER = {"block": 0, "guard": 1, "warn": 2, "field": 3}


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def ordinal(round_id: str) -> tuple:
    prefix, num, date = round_id[0], int(round_id[1:4]), round_id[5:]
    return (prefix != "r", date, num)


def collect():
    registry = load(BASE / "registry.json") or {"tasks": []}
    tasks = {t["id"]: t for t in registry.get("tasks", [])}
    rounds = []
    for rpath in sorted((BASE / "rounds").glob("*.json")):
        data = load(rpath)
        if data:
            rounds.append(data)
    rounds.sort(key=lambda r: ordinal(r["round_id"]))
    return registry, tasks, rounds


def read_cards(round_obj, tasks):
    cards = {}
    for tid, slot in round_obj.get("tasks", {}).items():
        card = load(BASE / slot["run_dir"] / "scorecard.json")
        run = load(BASE / slot["run_dir"] / "run.json")
        if card:
            cards[tid] = (card, run)
    return cards


def score(card, metric: str):
    """按 unseen_acceptance → regression → development 取第一个有样本的 split。"""
    for split in ("unseen_acceptance", "regression", "development"):
        slot = (card.get("split_scores") or {}).get(split) or {}
        if not slot.get("count"):
            continue
        entry = (slot.get("metrics") or {}).get(metric) or {}
        if entry.get("value") is not None:
            return entry.get("value"), slot.get("count"), split
    return None, 0, None


def render() -> str:
    registry, tasks, rounds = collect()
    cfg = load(BASE / "monitor" / "thresholds.json") or {}
    lines = [
        "---",
        "generated_by: tools/report.py",
        "do_not_edit: true",
        "---",
        "",
        "# 迭代趋势",
        "",
        f"任务 {len(tasks)} 个，轮次 {len(rounds)} 次。本文件由 `tools/report.py` 生成，不要手改；",
        "迭代叙事写入 `tasks/<task>/NOTES.md`，告警归因写入 `monitor/incidents/`。",
        "",
        "## 轮次总览",
        "",
        "| 轮次 | 标签 | 环境 | 已评分 | block 通过 | guard 告警 | 建成基线 | 结论 |",
        "|-|-|-|-|-|-|-|-|",
    ]
    if not rounds:
        lines.append("| — | 尚未开轮 | — | 0/15 | — | — | — | 见 README §5 第 1 步 |")

    for r in rounds:
        cards = read_cards(r, tasks)
        scored = [tid for tid, (card, _) in cards.items() if card.get("verdict") in {"pass", "fail", "unknown"}]
        block_total = [tid for tid, t in tasks.items() if t.get("gate_tier") == "block" and t.get("in_ci")]
        block_ok = [tid for tid in block_total if tid in cards and cards[tid][0].get("verdict") == "pass"]
        guard_bad = [
            tid
            for tid in cards
            if tasks.get(tid, {}).get("gate_tier") == "guard"
            and cards[tid][0].get("gate", {}).get("decision") in {"hold", "warn"}
        ]
        baselined = sum(1 for t in tasks.values() if t.get("baseline_run"))
        env = r.get("env", {})
        env_str = " / ".join(
            str(x) for x in (env.get("model"), env.get("agent_kernel")) if x
        ) or "—"
        verdicts = [c.get("verdict") for c, _ in cards.values()]
        fail = verdicts.count("fail")
        if not scored:
            agg = "未评分"
        elif len(scored) < len(tasks):
            agg = f"进行中 {len(scored)}/{len(tasks)}"
        else:
            agg = r.get("aggregate", {}).get("gate") or "待裁定"
        lines.append(
            f"| {r['round_id']} | {r.get('label', '—')} | {env_str} | {len(scored)}/{len(tasks)} | "
            f"{len(block_ok)}/{len(block_total)} | {len(guard_bad)} | {baselined}/{len(tasks)} | "
            f"{agg}{'' if not fail else f'（fail {fail}）'} |"
        )

    lines += ["", "## 分任务最新值", ""]
    header = "| 任务 | 主指标 | 取值 split | 最新轮 | 基线轮 | 最新值 | 基线值 | Δ | 门槛 | verdict |"
    lines += [header, "|-|-|-|-|-|-|-|-|-|-|"]
    for tid in sorted(tasks):
        t = tasks[tid]
        task_card = load(BASE / t["path"] / "task.json") or {}
        primary = task_card.get("metrics")
        pm = next((m for m in primary or [] if m.get("primary")), None)
        if not pm:
            continue
        latest = None
        for r in reversed(rounds):
            slot = r.get("tasks", {}).get(tid)
            if not slot:
                continue
            card = load(BASE / slot["run_dir"] / "scorecard.json")
            if card and card.get("verdict") not in (None, "pending"):
                latest = (r["round_id"], card)
                break
        baseline_run = (load(BASE / t["path"] / "history" / "baseline.json") or {}).get("run_id")
        latest_val, _n, split_used = score(latest[1], pm["id"]) if latest else (None, 0, None)
        base_val = None
        if baseline_run:
            slot = next(
                (r.get("tasks", {}).get(tid) for r in rounds if r["round_id"] == baseline_run), None
            )
            if slot:
                base_card = load(BASE / slot["run_dir"] / "scorecard.json")
                if base_card:
                    base_val = score(base_card, pm["id"])[0]
        delta = None
        if latest_val is not None and base_val is not None:
            delta = latest_val - base_val
        gate = (latest[1].get("gate", {}).get("decision") if latest else None) or "pending"
        lines.append(
            f"| {tid} {t['title']} | {pm['id']} | {split_used or '—'} | {latest[0] if latest else '—'} | {baseline_run or '—'} | "
            f"{fmt(latest_val)} | {fmt(base_val)} | {fmt(delta, 4)} | {t.get('gate_tier')} | {gate} |"
        )

    lines += ["", "## 数据就绪度", ""]
    lines += [
        "| 任务 | manifest | development | regression | unseen | 原始来源 | 构建版本 |",
        "|-|-|-|-|-|-|-|",
    ]
    for tid in sorted(tasks):
        t = tasks[tid]
        m = load(BASE / t["path"] / "dataset" / "manifest.json") or {}
        splits = m.get("splits") or {}
        build = m.get("build") or {}
        counts = [str((splits.get(s) or {}).get("count", 0)) for s in ("development", "regression", "unseen_acceptance")]
        total = sum(int(c) for c in counts)
        lines.append(
            f"| {tid} | {m.get('revision', '—')}/{m.get('status', '—')} | {counts[0]} | {counts[1]} | {counts[2]} | "
            f"{len(m.get('sources') or [])} | {build.get('version', 0)}（{total} 例） |"
        )

    lines += ["", "## 门槛状态", ""]
    pending = [
        tid
        for tid, t in sorted(tasks.items())
        if any(
            m.get("threshold_status") == "pending_baseline"
            for m in (load(BASE / t["path"] / "task.json") or {}).get("metrics", [])
        )
    ]
    lines.append(f"- 仍有 `pending_baseline` 指标的任务：{', '.join(pending) if pending else '无'}")
    lines.append(f"- 绝对门槛 {len(cfg.get('absolute', []))} 条：`monitor/thresholds.json`")
    lines.append(f"- 默认相对规则：阻断 -{cfg.get('defaults', {}).get('block_drop_pp', '?')}pp / "
                 f"告警 -{cfg.get('defaults', {}).get('warn_drop_pp', '?')}pp；最少样本 "
                 f"{cfg.get('defaults', {}).get('min_samples_for_gate', '?')}")

    # 归因入口
    empties = [tid for tid, t in tasks.items() if (load(BASE / t["path"] / "history" / "baseline.json") or {}).get("run_id") is None]
    lines += ["", "## 待办", ""]
    if empties:
        lines.append(f"- 尚无基线的任务：{', '.join(sorted(empties))}")
    lines.append("- 开新轮：`python3 tools/new_round.py --label <标签>`；改完重跑本脚本")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查产物是否最新")
    args = ap.parse_args()
    text = render()
    target = BASE / "monitor" / "trend.md"
    if args.check:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != text:
            print("monitor/trend.md 过期，请运行 python3 tools/report.py", file=sys.stderr)
            return 1
        print("trend.md 最新")
        return 0
    target.write_text(text, encoding="utf-8")
    print(f"已写入 {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
