"""B07：端到端多步数据分析。

来源：
- DABstep（adyen/DABstep）：支付数据分析题，含自然语言问题、业务指南（guidelines）、上下文文件与金标答案；
  分 easy / hard 两档，hard 需要多步推理与口径判断。
- KramaBench：数据湖上的多步分析（数据到位后追加）。

用例形状：问题 + 业务指南 + 上下文文件（bench:// 引用）→ 答案。判分用精确匹配（数值容差）与 SQL/步骤轨迹。
"""
from __future__ import annotations

import json


def _rows(path):
    text = path.read_text(encoding="utf-8").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def build(ctx) -> dict:
    n = 0
    per = {}
    ctx_sources = []

    base = ctx.raw_path("dabstep")
    tasks_file = base / "data" / "tasks" / "all.jsonl"
    if tasks_file.exists():
        ctx.source("dabstep")
        ctx_sources.append("dabstep")
        rows = _rows(tasks_file)
        per["dabstep"] = len(rows)
        n += _dabstep(ctx, rows, start=n)
    else:
        ctx.notes.append("DABstep all.jsonl 尚未下载")

    n += _kramabench(ctx, n)
    return {
        "policy": "DABstep 按题目 level 分层入库；上下文文件走 bench:// 引用。split 按 task_id 哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["exact_match_accuracy"],
                "missing_metrics": ["step_efficiency", "final_report_quality"],
                "note": "步骤效率与报告质量需要轨迹与成稿；先由 harness 记录 steps 与 report",
            },
            "counts": per,
        },
    }


def _dabstep(ctx, rows, start: int) -> int:
    n = 0
    for rec in rows:
        question = rec.get("question")
        if not question:
            continue
        n += 1
        qref = ctx.fixture(f"dab-{rec.get('task_id') or n}.md", str(question))
        inputs = [{"kind": "question", "ref": qref, "digest": None}]
        for f in rec.get("context_files") or []:
            rel = f.replace("data/", "", 1) if f.startswith("data/") else f
            inputs.append({"kind": "file", "ref": ctx.bench("dabstep", "data", rel), "digest": None})
        ctx.add(
            source="dab",
            seq=start + n,
            inputs=inputs,
            expected={
                "kind": "answer",
                "question": question,
                "answer": rec.get("answer"),
                "level": rec.get("level"),
                "guidelines": rec.get("guidelines"),
            },
            evidence=[qref, ctx.bench("dabstep", "data", "context")],
            tags=["dabstep", str(rec.get("level") or "unknown")],
            gold={"source": "adyen/DABstep", "raw": rec, "task_id": rec.get("task_id")},
            split_key=f"dab:{rec.get('task_id')}",
        )
    return n


def _kramabench(ctx, start: int) -> int:
    base = ctx.raw_path("kramabench")
    if not base.exists():
        ctx.notes.append("KramaBench 尚未下载")
        return 0
    files = sorted((base / "dr-input").rglob("*.json"))
    if not files:
        files = sorted(base.rglob("*.json"))
    rows = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        items = data.values() if isinstance(data, dict) else data
        for rec in items:
            if isinstance(rec, dict) and (rec.get("query") or rec.get("question")):
                rows.append((path, rec))
    if not rows:
        ctx.notes.append("KramaBench 未解析到查询")
        return 0
    ctx.source("kramabench")
    n = 0
    for path, rec in rows:
        n += 1
        q = rec.get("query") or rec.get("question")
        kref = ctx.fixture(f"krama-{rec.get('id') or n}.md", str(q))
        domain = path.parent.name
        ctx.add(
            source="krama",
            seq=start + n,
            inputs=[{"kind": "question", "ref": kref, "digest": None}],
            expected={
                "kind": "answer",
                "answer": rec.get("answer"),
                "answer_type": rec.get("answer_type"),
                "runtime_s": rec.get("runtime"),
                "data_sources": rec.get("data_sources"),
            },
            evidence=[kref],
            tags=["kramabench", domain, str(rec.get("answer_type") or "unknown")],
            gold={"source": "mitdbg/KramaBench", "file": str(path.relative_to(base)), "raw": rec},
            split_key=f"krama:{rec.get('id') or n}",
        )
    return n
