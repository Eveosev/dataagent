#!/usr/bin/env python3
"""校验 09-benchmark/ 目录契约。

用法（在仓库根目录）：
    python3 -I docs/research/dataagent-2026-11-03/09-benchmark/tools/check.py
    python3 -I .../check.py --quiet

只依赖标准库。校验不通过时退出码 1，并把每条问题打印为 `ERROR <path>: <原因>`。
可用 jsonschema 时额外按 schema/ 校验；不可用时只跑内置不变量，结论中会注明。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOCS = BASE.parent
CATALOG = DOCS / "catalog" / "atomic-capability-catalog.json"
SPLITS = ("development", "regression", "unseen_acceptance")
TASK_ID = re.compile(r"^B(0[1-9]|1[0-9]|20)$")
RUN_ID = re.compile(r"^[rx][0-9]{3}-[0-9]{4}-[0-9]{2}-[0-9]{2}$")
CASE_ID = re.compile(r"^B(0[1-9]|1[0-9]|20)-[a-z0-9-]+-[0-9]{3,5}$")

errors: list[str] = []
warnings: list[str] = []


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{rel(path)}: 文件不存在")
    except json.JSONDecodeError as exc:
        errors.append(f"{rel(path)}: JSON 解析失败（{exc.msg}，行 {exc.lineno}）")
    return None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(BASE))
    except ValueError:
        return str(path)


def need(obj, keys, where: str) -> bool:
    ok = True
    for k in keys:
        if k not in obj:
            errors.append(f"{where}: 缺少字段 {k}")
            ok = False
    return ok


def validate_schemas() -> None:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        warnings.append("未安装 jsonschema，跳过 schema/ 校验（内置不变量已覆盖主路径）")
        return

    for kind, obj in _schema_targets():
        schema = load(BASE / "schema" / f"{kind}.schema.json")
        if schema is None:
            continue
        try:
            jsonschema.validate(obj, schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{kind}: schema 不通过（{exc.message}，路径 {list(exc.absolute_path)}）")


def _schema_targets():
    registry = _registry if _registry else {}
    for t in registry.get("tasks", []):
        task = load(BASE / t["path"] / "task.json")
        if task:
            yield "task", task
        manifest = load(BASE / t["path"] / "dataset" / "manifest.json")
        if manifest:
            yield "manifest", manifest
    for round_file in sorted((BASE / "rounds").glob("*.json")):
        data = load(round_file)
        for tid, slot in (data or {}).get("tasks", {}).items():
            run_dir = BASE / slot.get("run_dir", "")
            if (run_dir / "run.json").exists():
                run = load(run_dir / "run.json")
                if run:
                    yield "run", run
            if (run_dir / "scorecard.json").exists():
                card = load(run_dir / "scorecard.json")
                if card:
                    yield "scorecard", card


_registry = None


def check_registry() -> list[dict]:
    global _registry
    path = BASE / "registry.json"
    registry = load(path)
    if registry is None:
        return []
    _registry = registry
    need(registry, ["version", "date", "tasks", "rounds"], "registry.json")

    tasks = registry.get("tasks", [])
    ids = [t.get("id") for t in tasks]
    expected = [f"B{i:02d}" for i in range(1, len(tasks) + 1)]
    if ids != expected:
        errors.append(f"registry.json: 任务应自 B01 起连续编号（实际 {ids}）")

    for t in tasks:
        tid = t.get("id", "?")
        where = f"registry.json[{tid}]"
        for k in ("slug", "path", "gate_tier", "in_ci", "status", "primary_metric"):
            if k not in t:
                errors.append(f"{where}: 缺少字段 {k}")
        if not (BASE / t.get("path", "") / "task.json").exists():
            errors.append(f"{where}: 任务目录不存在 ({t.get('path')})")

    for r in registry.get("rounds", []):
        if not (BASE / "rounds" / f"{r}.json").exists():
            errors.append(f"registry.json: 轮次 {r} 无 rounds/{r}.json")
    return tasks


def check_task(t: dict) -> None:
    if not _atoms:
        return  # catalog 缺失由 main() 统一报一次
    tid = t.get("id", "?")
    tdir = BASE / t.get("path", "")
    task = load(tdir / "task.json")
    if task is None:
        return
    where = f"{t.get('path')}/task.json"
    need(task, ["id", "slug", "title", "plan_row", "catalog_atoms", "slice", "unit", "graders", "metrics", "gate", "status"], where)

    if task.get("id") != tid:
        errors.append(f"{where}: id={task.get('id')} 与 registry 的 {tid} 不一致")
    if task.get("slug") != t.get("slug"):
        errors.append(f"{where}: slug={task.get('slug')} 与 registry 的 {t.get('slug')} 不一致")
    if tdir.name != f"{tid}-{t.get('slug')}":
        errors.append(f"{where}: 目录名应为 {tid}-{t.get('slug')}，实际 {tdir.name}")

    atoms = task.get("catalog_atoms", [])
    if len(set(atoms)) != len(atoms):
        errors.append(f"{where}: catalog_atoms 有重复")
    unknown = [a for a in atoms if a not in _atoms]
    if unknown:
        errors.append(f"{where}: catalog 中不存在的原子 {unknown}")

    metrics = task.get("metrics", [])
    mids = [m.get("id") for m in metrics]
    if len(set(mids)) != len(mids):
        errors.append(f"{where}: metric id 有重复")
    if not any(m.get("primary") for m in metrics):
        errors.append(f"{where}: 必须恰有一个 primary 指标")
    if sum(1 for m in metrics if m.get("primary")) > 1:
        errors.append(f"{where}: primary 指标多于一个")
    graders = set(task.get("graders", []))
    for m in metrics:
        if m.get("grader") not in graders:
            errors.append(f"{where}: 指标 {m.get('id')} 的 grader {m.get('grader')} 不在 graders 列表")

    # 相对引用必须能解析
    for ref_field, ref in [
        ("plan_ref", task.get("plan_ref")),
        ("gate.ref", task.get("gate", {}).get("ref")),
        ("dataset.manifest_ref", task.get("dataset", {}).get("manifest_ref")),
        ("notes_ref", task.get("notes_ref")),
    ]:
        if ref and not (tdir / ref).exists():
            errors.append(f"{where}: {ref_field}={ref} 无法解析")

    gate = task.get("gate", {})
    stray = [m for m in gate.get("blocking_metrics", []) if m not in mids]
    if stray:
        errors.append(f"{where}: blocking_metrics 引用了不存在的指标 {stray}")
    if not gate.get("in_ci") and gate.get("tier") != "field":
        warnings.append(f"{where}: 不进 CI 但 tier={gate.get('tier')}，确认是否应为 field")

    # manifest
    mpath = tdir / "dataset" / "manifest.json"
    manifest = load(mpath)
    if manifest:
        mwhere = f"{t.get('path')}/dataset/manifest.json"
        need(manifest, ["dataset_id", "task_id", "revision", "status", "sources", "splits", "exposure", "fixtures"], mwhere)
        if manifest.get("task_id") != tid:
            errors.append(f"{mwhere}: task_id={manifest.get('task_id')} 与 {tid} 不一致")
        counts = {}
        for split in SPLITS:
            slot = manifest.get("splits", {}).get(split)
            if slot is None:
                errors.append(f"{mwhere}: 缺少 split {split}")
                continue
            actual = len(list((tdir / "dataset" / "cases" / split).glob("*.json")))
            counts[split] = actual
            if slot.get("count") != actual:
                errors.append(f"{mwhere}: splits.{split}.count={slot.get('count')}，cases 目录实际 {actual} 个")
            if slot.get("frozen") and actual == 0:
                errors.append(f"{mwhere}: splits.{split} 标记 frozen 但没有样本")
        if manifest.get("status") == "frozen" and not all(
            manifest.get("splits", {}).get(s, {}).get("frozen") for s in SPLITS
        ):
            errors.append(f"{mwhere}: status=frozen 但 split 未全部 frozen")

        ledger = tdir / "dataset" / manifest.get("exposure", {}).get("ledger_ref", "exposure.jsonl")
        entries = [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()] if ledger.exists() else []
        if manifest.get("exposure", {}).get("entries") != len(entries):
            errors.append(f"{mwhere}: exposure.entries={manifest.get('exposure', {}).get('entries')}，台账实际 {len(entries)} 行")
        known_cases = {
            p.stem for s in SPLITS for p in (tdir / "dataset" / "cases" / s).glob("*.json")
        }
        for i, line in enumerate(entries, 1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"{rel(ledger)}:{i}: 不是合法 JSON")
                continue
            if entry.get("split") not in SPLITS:
                errors.append(f"{rel(ledger)}:{i}: split 非法 {entry.get('split')}")
            if known_cases and entry.get("case_id") not in known_cases:
                errors.append(f"{rel(ledger)}:{i}: case_id {entry.get('case_id')} 不在 cases/ 中")
            if not RUN_ID.match(str(entry.get("run_id", ""))):
                errors.append(f"{rel(ledger)}:{i}: run_id 格式不对")

        # cases
        for split in SPLITS:
            for cpath in sorted((tdir / "dataset" / "cases" / split).glob("*.json")):
                case = load(cpath)
                if case is None:
                    continue
                cw = rel(cpath)
                need(case, ["case_id", "task_id", "split_role", "inputs", "expected", "evidence", "annotation"], cw)
                if case.get("task_id") != tid:
                    errors.append(f"{cw}: task_id 与任务不符")
                if case.get("split_role") != split:
                    errors.append(f"{cw}: split_role={case.get('split_role')} 与所在目录 {split} 不符")
                if not CASE_ID.match(str(case.get("case_id", ""))):
                    errors.append(f"{cw}: case_id 格式应为 {tid}-<name>-<序号>")
                if cpath.stem != case.get("case_id"):
                    errors.append(f"{cw}: 文件名应与 case_id 一致")
                if split == "unseen_acceptance":
                    if any(e.get("case_id") == case.get("case_id") for e in map(_try_json, entries)):
                        errors.append(f"{cw}: 已暴露样本不得留在 unseen_acceptance")

    # baseline
    baseline = load(tdir / "history" / "baseline.json")
    if baseline:
        bwhere = f"{t.get('path')}/history/baseline.json"
        run_id = baseline.get("run_id")
        if run_id is not None:
            if not RUN_ID.match(str(run_id)):
                errors.append(f"{bwhere}: run_id 格式不对")
            elif not (tdir / "history" / "runs" / str(run_id) / "scorecard.json").exists():
                errors.append(f"{bwhere}: 指向的 run {run_id} 无 scorecard.json")
    # 基线档
    if t.get("baseline_run") and not (tdir / "history" / "runs" / t["baseline_run"]).exists():
        errors.append(f"registry.json[{tid}]: baseline_run {t['baseline_run']} 无对应 run 目录")


def _try_json(line: str):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {}


def check_thresholds(tasks: list[dict]) -> None:
    path = BASE / "monitor" / "thresholds.json"
    data = load(path)
    if data is None:
        return
    need(data, ["version", "defaults", "absolute", "escalation"], "monitor/thresholds.json")
    by_id = {t["id"]: t for t in tasks}
    for i, rule in enumerate(data.get("absolute", [])):
        where = f"monitor/thresholds.json:absolute[{i}]"
        tid = rule.get("task")
        if tid not in by_id:
            errors.append(f"{where}: 未知任务 {tid}")
            continue
        task = load(BASE / by_id[tid]["path"] / "task.json") or {}
        ids = [m["id"] for m in task.get("metrics", [])]
        if rule.get("metric") not in ids:
            errors.append(f"{where}: 任务 {tid} 没有指标 {rule.get('metric')}")
        if rule.get("rule") not in {"min", "max"}:
            errors.append(f"{where}: rule 只能是 min / max")
        if rule.get("severity") not in {"block", "warn"}:
            errors.append(f"{where}: severity 只能是 block / warn")


def check_rounds() -> None:
    for rpath in sorted((BASE / "rounds").glob("*.json")):
        data = load(rpath)
        if data is None:
            continue
        where = rel(rpath)
        need(data, ["round_id", "label", "created", "env", "tasks", "aggregate"], where)
        rid = data.get("round_id", "")
        if rpath.stem != rid:
            errors.append(f"{where}: round_id={rid} 与文件名不符")
        if not RUN_ID.match(rid):
            errors.append(f"{where}: round_id 格式应为 rNNN-YYYY-MM-DD")
        slots = data.get("tasks", {})
        expected = [t.get("id") for t in (_registry or {}).get("tasks", [])] or [f"B{i:02d}" for i in range(1, 16)]
        if sorted(slots) != sorted(expected):
            errors.append(f"{where}: tasks 必须覆盖 registry 的全部任务，实际 {sorted(slots)}")
        for tid, slot in slots.items():
            run_dir = BASE / slot.get("run_dir", "")
            if not (run_dir / "run.json").exists():
                errors.append(f"{where}: {tid} 的 run.json 不存在 ({slot.get('run_dir')})")
                continue
            run = load(run_dir / "run.json")
            if run and run.get("task_id") != tid:
                errors.append(f"{rel(run_dir / 'run.json')}: task_id 与轮次槽位 {tid} 不符")
            if run and run.get("round_id") != rid:
                errors.append(f"{rel(run_dir / 'run.json')}: round_id 与 {rid} 不符")
            card = load(run_dir / "scorecard.json")
            if card is None:
                continue
            need(card, ["run_id", "task_id", "split_scores", "verdict", "gate"], rel(run_dir / "scorecard.json"))
            if card.get("run_id") != rid:
                errors.append(f"{rel(run_dir / 'scorecard.json')}: run_id 应为 {rid}")
            for split in SPLITS:
                slot_scores = card.get("split_scores", {}).get(split)
                if slot_scores is None:
                    errors.append(f"{rel(run_dir / 'scorecard.json')}: 缺少 split_scores.{split}")
            if run and run.get("status") == "scored" and card.get("verdict") == "pending":
                errors.append(f"{rel(run_dir / 'scorecard.json')}: run 已 scored 但 verdict 仍 pending")
            if (slot.get("verdict") or "pending") != (card.get("verdict") or "pending"):
                errors.append(f"{where}: {tid} verdict 与 scorecard 不一致")


def check_case_refs(tasks: list[dict]) -> None:
    """用例引用的 fixtures / bench:// 是否落地；缺失只告警（原始数据可能仍在下载）。"""
    raw_root = json.loads((BASE / "datasets.lock.json").read_text(encoding="utf-8")).get("raw_root", "")
    root = (BASE.parents[3] / raw_root) if raw_root else None
    for t in tasks:
        tid = t["id"]
        tdir = BASE / t["path"]
        missing: dict[str, int] = {}
        for p in (tdir / "dataset" / "cases").rglob("*.json"):
            case = load(p) or {}
            for inp in case.get("inputs") or []:
                ref = inp.get("ref") or ""
                if ref.startswith("bench://"):
                    if root is None:
                        missing["bench"] = missing.get("bench", 0) + 1
                        continue
                    src, _, rest = ref[len("bench://"):].partition("/")
                    target = root / tid / src / rest
                elif ref.startswith("fixtures/"):
                    target = tdir / "dataset" / ref
                else:
                    continue
                if not target.exists():
                    missing[ref.split("/")[0] if ref.startswith("fixtures/") else src] = (
                        missing.get(ref.split("/")[0] if ref.startswith("fixtures/") else src, 0) + 1
                    )
        if missing:
            warnings.append(f"{tid}: 用例引用未落地 {missing}（原始数据未下载完或路径变更）")


def check_graders(tasks: list[dict]) -> None:
    """task.json 引用的 grader 是否存在、是否有 grade()；未实现的只告警。"""
    gdir = BASE / "harness" / "graders"
    for t in tasks:
        task = load(BASE / t["path"] / "task.json") or {}
        for metric in task.get("metrics", []):
            name = metric.get("grader")
            if not name:
                continue
            module_name, _, function = name.partition(":")
            path = gdir / f"{module_name}.py"
            if not path.exists():
                warnings.append(f"{t['id']}: grader {name} 未实现（{metric['id']}）")
                continue
            source = path.read_text(encoding="utf-8")
            if f"def {function or 'grade'}(" not in source:
                errors.append(f"{t['id']}: grader {name} 缺少 def {function or 'grade'}()")


def main() -> int:
    op = BASE / "registry.json"
    if not op.exists():
        print(f"ERROR 找不到 {op}", file=sys.stderr)
        return 1
    tasks = check_registry()
    if not _atoms:
        errors.append(f"找不到 {rel(CATALOG)}，无法校验原子编号")
    for t in tasks:
        check_task(t)
    check_thresholds(tasks)
    check_rounds()
    check_case_refs(tasks)
    check_graders(tasks)
    validate_schemas()

    total_atoms = sum(len((load(BASE / t["path"] / "task.json") or {}).get("catalog_atoms", [])) for t in tasks)
    print(f"tasks={len(tasks)} atoms={total_atoms} rounds={len(list((BASE / 'rounds').glob('*.json')))}")
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"\n{len(errors)} 项不通过", file=sys.stderr)
        return 1
    print("OK")
    return 0


_atoms: dict[str, dict] = {}
if CATALOG.exists():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    _atoms = {a["id"]: a for a in catalog.get("atoms", [])}

if __name__ == "__main__":
    sys.exit(main())
