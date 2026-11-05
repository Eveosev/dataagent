"""B13：记忆召回与跨会话追溯。

来源：
- MemoryAgentBench（ai-hyz/MemoryAgentBench）：Accurate Retrieval / Long Range Understanding /
  Conflict Resolution / Test Time Learning 四类，每行一段长上下文 + 多问题 + 多组可接受答案。
- LongMemEval（xiaowu0162/longmemeval-cleaned）：跨会话历史问答，含 answer 与 question_type。

用例形状：长上下文（落 fixtures）+ 问题 → 可接受答案集合。判分看命中任一别名与是否需要澄清。
"""
from __future__ import annotations

import json

CATS = {
    "Accurate_Retrieval": "accurate_retrieval",
    "Long_Range_Understanding": "long_range",
    "Conflict_Resolution": "conflict_resolution",
    "Test_Time_Learning": "test_time_learning",
}


def build(ctx) -> dict:
    ctx.source("memoryagentbench")
    n = 0
    per_cat = {}
    for name, slug in CATS.items():
        path = ctx.raw_path("memoryagentbench", "data", f"{name}-00000-of-00001.parquet")
        if not path.exists():
            ctx.notes.append(f"缺少 {name}")
            continue
        import pyarrow.parquet as pq

        rows = pq.read_table(path).to_pylist()
        per_cat[slug] = 0
        for i, row in enumerate(rows):
            context = row.get("context") or ""
            questions = row.get("questions") or []
            answers = row.get("answers") or []
            if not context or not questions:
                continue
            n += 1
            per_cat[slug] += 1
            meta = row.get("metadata") or {}
            ref = ctx.fixture(f"mab-{slug}-{i:03d}.md", context)
            ctx.add(
                source="mab",
                seq=n,
                inputs=[{"kind": "memory", "ref": ref, "digest": None}],
                expected={
                    "kind": "qa_set",
                    "questions": questions,
                    "answers": answers,
                    "qa_pair_ids": meta.get("qa_pair_ids"),
                },
                evidence=[ref],
                tags=["memoryagentbench", slug, f"q:{len(questions)}"],
                gold={
                    "source": "ai-hyz/MemoryAgentBench",
                    "category": name,
                    "questions": questions,
                    "answers": answers,
                    "qa_pair_ids": meta.get("qa_pair_ids"),
                    "context_chars": len(context),
                },
                split_key=f"mab:{name}:{i}",
            )

    n += _longmemeval(ctx, n)
    return {
        "policy": "MemoryAgentBench 全量（按 context 行）；LongMemEval 用 cleaned 版，取 oracle + s 两档。split 按行哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["answer_recall", "conflict_detection"],
                "missing_metrics": ["provenance_accuracy", "clarification_rate"],
                "note": "溯源与澄清率需要 harness 记录引用片段与追问动作",
            },
            "counts": per_cat,
        },
    }


def _longmemeval(ctx, start: int) -> int:
    base = ctx.raw_path("longmemeval-cleaned")
    if not base.exists():
        base = ctx.raw_path("longmemeval")
    files = sorted(base.glob("longmemeval_*.json"))
    if not files:
        ctx.notes.append("LongMemEval 尚未下载")
        return 0
    ctx.source("longmemeval-cleaned" if (ctx.raw_path("longmemeval-cleaned")).exists() else "longmemeval")
    n = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("data") or []
        for rec in items:
            question = rec.get("question")
            history = rec.get("history") or rec.get("haystack_sessions") or []
            if not question:
                continue
            n += 1
            ref = ctx.fixture(
                f"lme-{path.stem}-{rec.get('question_id') or n}.md",
                json.dumps(history, ensure_ascii=False)[:400000],
            )
            ctx.add(
                source="lme",
                seq=start + n,
                inputs=[{"kind": "memory", "ref": ref, "digest": None}],
                expected={
                    "kind": "answer",
                    "answer": rec.get("answer"),
                    "question_type": rec.get("question_type"),
                },
                evidence=[ref],
                tags=["longmemeval", path.stem, str(rec.get("question_type") or "unknown")],
                gold={"source": "xiaowu0162/longmemeval", "raw": rec},
                split_key=f"lme:{rec.get('question_id')}",
            )
    return n
