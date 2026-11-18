#!/usr/bin/env python3
"""把正式轮（rNNN）的主指标写成任务基线，或回滚到上一份基线。

用法（在 09-benchmark 目录）：
    python3 tools/set_baseline.py --round r001-2026-11-18 --tasks B02,B03,B16,B17
    python3 tools/set_baseline.py --revert --tasks B02,B03,B16,B17
    python3 tools/set_baseline.py --revert --round r001-2026-11-18

写入前逐任务校验：
- `rounds/<round-id>.json` 若存在，必须包含该任务的槽位，且 `run_dir` 指向本次 run；
- `tasks/<task>/history/runs/<round-id>/run.json` 存在，`status=scored`，task_id / run_id 一致；
- 同目录 `scorecard.json` 存在，task_id / run_id 一致，主指标至少在一个 split 有值。

写入内容：
- `tasks/<task>/history/baseline.json`：当前基线指针（run_id）与主指标快照；
- `registry.json`：该任务的 `baseline_run`。

写入前把旧 `baseline.json` 与旧 `registry.baseline_run` 存到
`tasks/<task>/history/baseline.prev.json`；`--revert` 用它恢复，只保留一级快照，
回滚后删除。探索轮（`x`）只用于调参，拒绝写基线。

裁定（是否该换基线、block 是否通过）由人负责；本工具只校验可追溯性并落账，
不替代 `README.md` §5 的裁定表。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROUND_ID = re.compile(r"^(?P<prefix>[rx])(?P<number>[0-9]{3})-(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})$")
TASK_ID = re.compile(r"^B(0[1-9]|1[0-9]|20)$")
SPLITS = ("unseen_acceptance", "regression", "development")
SNAPSHOT_NAME = "baseline.prev.json"
EMPTY_BASELINE_NOTE = "尚无基线；首次 r 轮次完成后由裁定人写入"


class BaselineError(Exception):
    """可直接展示给调用方的校验失败。"""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def read_json(path: Path, label: str) -> dict:
    if not path.exists():
        raise BaselineError(f"{label} 不存在：{path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BaselineError(f"{label} 读取失败：{exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BaselineError(f"{label} 不是合法 JSON（{exc.msg}，行 {exc.lineno}）：{path}") from exc
    if not isinstance(data, dict):
        raise BaselineError(f"{label} 顶层应为对象：{path}")
    return data


def write_json(path: Path, obj) -> None:
    """先写临时文件再原子替换，避免中断留下半个 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_round(value: str, *, writing: bool) -> str:
    rid = value.strip()
    match = ROUND_ID.fullmatch(rid)
    if not match:
        raise BaselineError(f"轮次 id 格式应为 rNNN-YYYY-MM-DD 或 xNNN-YYYY-MM-DD：{value!r}")
    try:
        datetime.strptime(match["date"], "%Y-%m-%d")
    except ValueError as exc:
        raise BaselineError(f"轮次日期不合法：{rid}") from exc
    if writing and match["prefix"] != "r":
        raise BaselineError(f"{rid} 是探索轮（x）；探索轮不建基线（README §3），请用正式轮 rNNN")
    return rid


def parse_tasks(value: str) -> list[str]:
    tasks: list[str] = []
    for chunk in value.split(","):
        tid = chunk.strip().upper()
        if not tid:
            continue
        if not TASK_ID.fullmatch(tid):
            raise BaselineError(f"任务 id 格式应为 B01–B20：{chunk.strip()!r}")
        if tid not in tasks:
            tasks.append(tid)
    if not tasks:
        raise BaselineError("--tasks 为空；示例：--tasks B02,B03,B16,B17")
    return tasks


def load_registry(base: Path) -> tuple[dict, dict[str, dict]]:
    registry = read_json(base / "registry.json", "registry.json")
    entries = registry.get("tasks")
    if not isinstance(entries, list):
        raise BaselineError("registry.json 缺少 tasks 数组")
    by_id: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise BaselineError("registry.json 的 tasks 里有非对象条目")
        tid = entry.get("id")
        if not isinstance(tid, str) or not TASK_ID.fullmatch(tid):
            raise BaselineError(f"registry.json 里有非法任务 id：{tid!r}")
        if tid in by_id:
            raise BaselineError(f"registry.json 里任务 {tid} 重复")
        by_id[tid] = entry
    return registry, by_id


def entry_for(by_id: dict[str, dict], tid: str) -> dict:
    entry = by_id.get(tid)
    if entry is None:
        raise BaselineError(f"registry.json 里没有任务 {tid}")
    return entry


def task_rel(entry: dict) -> str:
    """registry.path 是相对 09-benchmark 的路径，如 tasks/B02-doc-parse-ocr。"""
    return str(entry.get("path") or "").replace("\\", "/").strip("/")


def load_round(base: Path, rid: str) -> tuple[dict | None, list[str]]:
    """轮次索引可以缺省（过渡期），存在时校验结构与槽位。"""
    path = base / "rounds" / f"{rid}.json"
    if not path.exists():
        return None, [f"未找到 rounds/{rid}.json；只按 run 目录校验（正式轮建议先跑 tools/new_round.py）"]
    data = read_json(path, f"rounds/{rid}.json")
    if data.get("round_id") != rid:
        raise BaselineError(f"rounds/{rid}.json 的 round_id={data.get('round_id')!r} 与文件名不符")
    slots = data.get("tasks")
    if not isinstance(slots, dict):
        raise BaselineError(f"rounds/{rid}.json 缺少 tasks 槽位对象")
    return data, []


def check_round_slot(round_obj: dict | None, rid: str, tid: str, run_rel: str) -> None:
    if round_obj is None:
        return
    slot = (round_obj.get("tasks") or {}).get(tid)
    if not isinstance(slot, dict):
        raise BaselineError(f"rounds/{rid}.json 没有 {tid} 的槽位")
    slot_dir = str(slot.get("run_dir") or "").replace("\\", "/").strip("/")
    if slot_dir and slot_dir != run_rel:
        raise BaselineError(
            f"rounds/{rid}.json 的 {tid} 槽位 run_dir={slot_dir}，与本次 run 目录 {run_rel} 不一致"
        )


def primary_metric(task: dict, where: str) -> dict:
    metrics = task.get("metrics")
    if not isinstance(metrics, list):
        raise BaselineError(f"{where} 缺少 metrics 数组")
    primaries = [m for m in metrics if isinstance(m, dict) and m.get("primary")]
    if len(primaries) != 1:
        raise BaselineError(f"{where} 必须恰有一个 primary 指标（实际 {len(primaries)}）")
    metric = primaries[0]
    if not metric.get("id"):
        raise BaselineError(f"{where} 的 primary 指标没有 id")
    return metric


def split_count(slot) -> int:
    """容忍脏数据：count 缺失或非整数时按 0 处理。"""
    if not isinstance(slot, dict):
        return 0
    count = slot.get("count")
    try:
        return int(count or 0)
    except (TypeError, ValueError):
        return 0


def pick_score(card: dict, metric_id: str, where: str) -> tuple[str, dict]:
    """按 report.py 的口径取第一个有样本且有值的 split。"""
    scores = card.get("split_scores")
    if not isinstance(scores, dict):
        raise BaselineError(f"{where} 缺少 split_scores")
    for split in SPLITS:
        slot = scores.get(split)
        if split_count(slot) <= 0:
            continue
        entry = as_dict(slot.get("metrics")).get(metric_id)
        if not isinstance(entry, dict) or entry.get("value") is None:
            continue
        value = entry["value"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise BaselineError(f"{where} 的 {metric_id}.value 不是数值：{value!r}")
        return split, entry
    raise BaselineError(
        f"{where} 的主指标 {metric_id} 在 {'→'.join(SPLITS)} 都没有分数（scorecard 全空或全 null）"
    )


def load_min_samples(base: Path) -> int:
    path = base / "monitor" / "thresholds.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return int((data.get("defaults") or {}).get("min_samples_for_gate") or 0)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return 0


def baseline_metric_value(baseline: dict, metric_id: str):
    entry = as_dict(baseline.get("metrics")).get(metric_id)
    if isinstance(entry, dict):
        return entry.get("value")
    if isinstance(entry, (int, float)) and not isinstance(entry, bool):
        return entry
    return None


def empty_baseline(tid: str) -> dict:
    return {"task_id": tid, "run_id": None, "updated": None, "metrics": {}, "note": EMPTY_BASELINE_NOTE}


def build_write_plan(
    base: Path,
    rid: str,
    tid: str,
    entry: dict,
    round_obj: dict | None,
    min_samples: int,
) -> dict:
    rel = task_rel(entry)
    if not rel:
        raise BaselineError(f"registry.json[{tid}] 缺少 path")
    task_dir = base / rel
    if not task_dir.is_dir():
        raise BaselineError(f"registry.json[{tid}].path 指向的目录不存在：{task_dir}")
    where = f"{rel}/task.json"
    task = read_json(task_dir / "task.json", where)
    if task.get("id") != tid:
        raise BaselineError(f"{where} 的 id={task.get('id')!r} 与 {tid} 不一致")
    metric = primary_metric(task, where)

    run_rel = f"{rel}/history/runs/{rid}"
    check_round_slot(round_obj, rid, tid, run_rel)
    run_dir = task_dir / "history" / "runs" / rid
    run = read_json(run_dir / "run.json", f"{run_rel}/run.json")
    if run.get("task_id") != tid:
        raise BaselineError(f"{run_rel}/run.json 的 task_id={run.get('task_id')!r} 与 {tid} 不一致")
    if run.get("run_id") != rid:
        raise BaselineError(f"{run_rel}/run.json 的 run_id={run.get('run_id')!r} 与 {rid} 不一致")
    status = run.get("status")
    if status != "scored":
        raise BaselineError(f"{run_rel}/run.json 的 status={status!r}；只有 status=scored 的 run 能写基线")

    card_path = run_dir / "scorecard.json"
    card = read_json(card_path, f"{run_rel}/scorecard.json")
    if card.get("task_id") != tid:
        raise BaselineError(f"{run_rel}/scorecard.json 的 task_id={card.get('task_id')!r} 与 {tid} 不一致")
    if card.get("run_id") != rid:
        raise BaselineError(f"{run_rel}/scorecard.json 的 run_id={card.get('run_id')!r} 与 {rid} 不一致")

    split, score = pick_score(card, metric["id"], f"{run_rel}/scorecard.json")

    baseline_path = task_dir / "history" / "baseline.json"
    baseline_existed = baseline_path.exists()
    if baseline_existed:
        old_baseline = read_json(baseline_path, f"{rel}/history/baseline.json")
        if old_baseline.get("task_id") not in (None, tid):
            raise BaselineError(
                f"{rel}/history/baseline.json 的 task_id={old_baseline.get('task_id')!r} 与 {tid} 不一致"
            )
    else:
        old_baseline = empty_baseline(tid)

    warnings: list[str] = []
    old_registry_run = entry.get("baseline_run")
    if old_registry_run != old_baseline.get("run_id"):
        warnings.append(
            f"{tid}: registry.baseline_run={old_registry_run!r} 与 baseline.json.run_id="
            f"{old_baseline.get('run_id')!r} 不一致；本次以 baseline.json 为旧基线快照"
        )
    if card.get("verdict") == "pending":
        warnings.append(f"{tid}: scorecard.verdict=pending；建议先按 README §5 裁定，再写基线")
    count = split_count(as_dict(card.get("split_scores")).get(split))
    if min_samples and count < min_samples:
        warnings.append(
            f"{tid}: {split} 样本数 {count} < min_samples_for_gate={min_samples}，"
            "按 README §5 应判 unknown、不得据此换基线；本工具只提示，不阻断裁定"
        )
    old_value = baseline_metric_value(old_baseline, metric["id"])
    direction = metric.get("direction")
    new_value = score["value"]
    if old_baseline.get("run_id") and old_value is not None:
        worse = (direction == "higher" and new_value < old_value) or (
            direction == "lower" and new_value > old_value
        )
        if worse:
            warnings.append(
                f"{tid}: 主指标 {metric['id']}={new_value} 劣于上一基线 {old_value}"
                f"（{old_baseline.get('run_id')}；基线只升不降，请确认这是有意重置）"
            )

    note = f"由 tools/set_baseline.py 从 {rid} 的 scorecard 写入（split={split}）"
    if not old_baseline.get("run_id"):
        note += "；首轮只建基线（06 Q10）"
    metric_snapshot = {
        "value": new_value,
        "numerator": score.get("numerator"),
        "denominator": score.get("denominator"),
        "split": split,
    }
    if direction:
        metric_snapshot["direction"] = direction
    new_baseline = {
        "task_id": tid,
        "run_id": rid,
        "updated": now_iso(),
        "dataset_revision": as_dict(run.get("dataset_ref")).get("revision"),
        "metrics": {metric["id"]: metric_snapshot},
        "gate_tier": as_dict(card.get("gate")).get("tier") or as_dict(task.get("gate")).get("tier"),
        "verdict": card.get("verdict"),
        "note": note,
    }
    snapshot_path = task_dir / "history" / SNAPSHOT_NAME
    keep_snapshot = False
    if snapshot_path.exists():
        old_snapshot = read_json(snapshot_path, f"{rel}/history/{SNAPSHOT_NAME}")
        if not isinstance(old_snapshot, dict):
            raise BaselineError(f"{rel}/history/{SNAPSHOT_NAME} 不是 JSON 对象，拒绝覆盖；请检查或删除")
        if old_snapshot.get("task_id") not in (None, tid):
            raise BaselineError(
                f"{rel}/history/{SNAPSHOT_NAME} 的 task_id={old_snapshot.get('task_id')!r} 与 {tid} 不一致"
            )
        if not old_snapshot.get("new_run"):
            raise BaselineError(f"{rel}/history/{SNAPSHOT_NAME} 缺少 new_run，无法判断是否同一轮；请检查或删除")
        if not isinstance(old_snapshot.get("baseline"), dict) or "registry_baseline_run" not in old_snapshot:
            raise BaselineError(
                f"{rel}/history/{SNAPSHOT_NAME} 缺少 baseline/registry_baseline_run，拒绝覆盖；请检查或删除"
            )
        if old_snapshot.get("new_run") == rid:
            keep_snapshot = True
            snapshot = old_snapshot
        else:
            snapshot = None
    else:
        snapshot = None
    if snapshot is None:
        snapshot = {
            "task_id": tid,
            "taken_at": now_iso(),
            "new_run": rid,
            "baseline_existed": baseline_existed,
            "baseline": old_baseline,
            "registry_baseline_run": old_registry_run,
        }
    return {
        "task_id": tid,
        "task_dir": task_dir,
        "run_dir": run_dir,
        "metric_id": metric["id"],
        "split": split,
        "count": count,
        "value": new_value,
        "old_run": old_baseline.get("run_id"),
        "baseline_path": baseline_path,
        "baseline": new_baseline,
        "snapshot_path": snapshot_path,
        "snapshot": snapshot,
        "keep_snapshot": keep_snapshot,
        "warnings": warnings,
    }


def format_value(value) -> str:
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def cmd_write(base: Path, rid: str, task_ids: list[str]) -> int:
    registry, by_id = load_registry(base)
    round_obj, warnings = load_round(base, rid)
    min_samples = load_min_samples(base)
    plans: list[dict] = []
    errors: list[str] = []
    for tid in task_ids:
        try:
            entry = entry_for(by_id, tid)
            plan = build_write_plan(base, rid, tid, entry, round_obj, min_samples)
        except BaselineError as exc:
            errors.append(str(exc))
            continue
        plans.append(plan)
        warnings.extend(plan["warnings"])

    for warning in warnings:
        print(f"WARN  {warning}")
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        print(f"{len(errors)} 项校验不通过，未写入任何基线", file=sys.stderr)
        return 1

    for plan in plans:
        if not plan["keep_snapshot"]:
            write_json(plan["snapshot_path"], plan["snapshot"])
    for plan in plans:
        write_json(plan["baseline_path"], plan["baseline"])
    for plan in plans:
        by_id[plan["task_id"]]["baseline_run"] = rid
    write_json(base / "registry.json", registry)

    for plan in plans:
        old_run = plan["old_run"] or "null"
        suffix = "（同一轮重复写入，保留原快照）" if plan["keep_snapshot"] else ""
        print(
            f"{plan['task_id']}  {plan['metric_id']}={format_value(plan['value'])}"
            f"（{plan['split']}，n={plan['count']}）  baseline: {old_run} -> {rid}{suffix}"
        )
    print(f"已写入 {len(plans)} 个基线；回滚快照在 tasks/<task>/history/{SNAPSHOT_NAME}")
    print("下一步：python3 tools/report.py")
    return 0


def discover_snapshot_tasks(base: Path, by_id: dict[str, dict]) -> list[str]:
    found: list[str] = []
    for tid, entry in by_id.items():
        tdir = base / task_rel(entry)
        if (tdir / "history" / SNAPSHOT_NAME).exists():
            found.append(tid)
    return found


def snapshot_new_run(base: Path, tid: str, entry: dict):
    tdir = base / task_rel(entry)
    snapshot = read_json(tdir / "history" / SNAPSHOT_NAME, f"{task_rel(entry)}/history/{SNAPSHOT_NAME}")
    return snapshot.get("new_run")


def build_revert_plan(
    base: Path,
    tid: str,
    entry: dict,
    rid: str | None,
) -> dict:
    rel = task_rel(entry)
    if not rel:
        raise BaselineError(f"registry.json[{tid}] 缺少 path")
    task_dir = base / rel
    snapshot_path = task_dir / "history" / SNAPSHOT_NAME
    if not snapshot_path.exists():
        raise BaselineError(f"{rel}/history/{SNAPSHOT_NAME} 不存在，无可回滚的基线（已回滚过或从未写入）")
    snapshot = read_json(snapshot_path, f"{rel}/history/{SNAPSHOT_NAME}")
    if snapshot.get("task_id") not in (None, tid):
        raise BaselineError(f"{snapshot_path} 的 task_id={snapshot.get('task_id')!r} 与 {tid} 不一致")
    if rid and snapshot.get("new_run") != rid:
        raise BaselineError(
            f"{tid} 最后一次写基线的是 {snapshot.get('new_run')!r}，不是 --round 指定的 {rid}；"
            "去掉 --round 或确认要回滚的轮次"
        )
    baseline = snapshot.get("baseline")
    if not isinstance(baseline, dict):
        raise BaselineError(f"{snapshot_path} 缺少 baseline 对象，无法恢复")
    if "registry_baseline_run" not in snapshot:
        raise BaselineError(f"{snapshot_path} 缺少 registry_baseline_run，无法恢复 registry")
    baseline_path = task_dir / "history" / "baseline.json"
    current = read_json(baseline_path, f"{rel}/history/baseline.json") if baseline_path.exists() else {}
    return {
        "task_id": tid,
        "baseline_path": baseline_path,
        "baseline": baseline,
        "baseline_existed": bool(snapshot.get("baseline_existed", True)),
        "registry_baseline_run": snapshot["registry_baseline_run"],
        "snapshot_path": snapshot_path,
        "from_run": current.get("run_id"),
        "to_run": baseline.get("run_id"),
        "written_by": snapshot.get("new_run"),
    }


def cmd_revert(base: Path, task_ids: list[str] | None, rid: str | None) -> int:
    registry, by_id = load_registry(base)
    if task_ids is None:
        task_ids = discover_snapshot_tasks(base, by_id)
        if rid:
            task_ids = [tid for tid in task_ids if snapshot_new_run(base, tid, by_id[tid]) == rid]
        if not task_ids:
            scope = f"由 {rid} 写入的" if rid else ""
            raise BaselineError(f"没有找到{scope} history/{SNAPSHOT_NAME}，无可回滚的基线")
    plans: list[dict] = []
    errors: list[str] = []
    for tid in task_ids:
        try:
            entry = entry_for(by_id, tid)
            plans.append(build_revert_plan(base, tid, entry, rid))
        except BaselineError as exc:
            errors.append(str(exc))
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        print(f"{len(errors)} 项校验不通过，未回滚任何基线", file=sys.stderr)
        return 1

    for plan in plans:
        if plan["baseline_existed"]:
            write_json(plan["baseline_path"], plan["baseline"])
        elif plan["baseline_path"].exists():
            plan["baseline_path"].unlink()
    for plan in plans:
        by_id[plan["task_id"]]["baseline_run"] = plan["registry_baseline_run"]
    write_json(base / "registry.json", registry)
    for plan in plans:
        plan["snapshot_path"].unlink()

    for plan in plans:
        written_by = plan["written_by"] or "上一份"
        print(
            f"{plan['task_id']}  baseline: {plan['from_run'] or 'null'} -> {plan['to_run'] or 'null'}"
            f"（撤销 {written_by} 的写入，快照已删除）"
        )
    print(f"已回滚 {len(plans)} 个基线")
    print("下一步：python3 tools/report.py")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="把正式轮（rNNN）的主指标写成任务基线，或回滚到上一份基线。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 tools/set_baseline.py --round r001-2026-11-18 --tasks B02,B03,B16,B17\n"
            "  python3 tools/set_baseline.py --revert --tasks B02,B03,B16,B17\n"
            "  python3 tools/set_baseline.py --revert --round r001-2026-11-18\n"
            "\n"
            "写入前校验 run.json（status=scored）与 scorecard.json；任一任务不通过则整批不写。\n"
            "只保留一级快照，--revert 后快照删除。"
        ),
    )
    ap.add_argument("--round", help="轮次 id（rNNN-YYYY-MM-DD）；写入时必填，--revert 时用于限定回滚哪一轮")
    ap.add_argument("--tasks", help="逗号分隔的任务 id，如 B02,B03,B16,B17；写入时必填")
    ap.add_argument("--revert", action="store_true", help="恢复到上一份基线（读 history/baseline.prev.json）")
    ap.add_argument(
        "--base",
        help="基准目录，默认取本脚本上一级；测试或换目录时用",
    )
    args = ap.parse_args(argv)

    base = Path(args.base).resolve() if args.base else BASE
    try:
        if args.revert:
            task_ids = parse_tasks(args.tasks) if args.tasks else None
            rid = parse_round(args.round, writing=False) if args.round else None
            return cmd_revert(base, task_ids, rid)
        if not args.round:
            raise BaselineError("写入基线需要 --round（示例：--round r001-2026-11-18）")
        if not args.tasks:
            raise BaselineError("写入基线需要 --tasks（示例：--tasks B02,B03,B16,B17）")
        rid = parse_round(args.round, writing=True)
        return cmd_write(base, rid, parse_tasks(args.tasks))
    except BaselineError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
