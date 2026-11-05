"""B06：召回检索与检索充分性。

来源：BRIGHT（xlangai/BRIGHT）：11 个领域共 1,398 条推理型查询，每条带金标文档 id。
文档正文在 documents/*.parquet（188,002 篇），用例只存查询与 gold id，正文按 id 现查，避免把大语料复制进库。

用例形状：查询 → 相关文档 id 集合。判分 Recall@k / nDCG@10 需要检索器返回 id 序列。
"""
from __future__ import annotations

import json
import pathlib


def build(ctx) -> dict:
    ctx.source("bright")
    base = ctx.raw_path("bright")
    domains = sorted((base / "Gemini-1.0_reason").glob("*.parquet"))
    if not domains:
        ctx.notes.append("BRIGHT 查询 parquet 不存在")
        return {"policy": "", "extra": {}}

    import pyarrow.parquet as pq

    n = 0
    per_domain = {}
    for path in domains:
        domain = path.stem.replace("-00000-of-00001", "")
        table = pq.read_table(path, columns=[c for c in ("query", "id", "gold_ids", "gold_ids_long", "gold_answer", "excluded_ids") if c in pq.read_schema(path).names])
        rows = table.to_pylist()
        per_domain[domain] = len(rows)
        for rec in rows:
            query = rec.get("query") or ""
            if not query:
                continue
            n += 1
            ref = ctx.fixture(f"bright-{domain}-{n:04d}.txt", query)
            ctx.add(
                source="bright",
                seq=n,
                inputs=[{"kind": "query", "ref": ref, "digest": None}],
                expected={
                    "kind": "retrieval",
                    "gold_ids": rec.get("gold_ids") or [],
                    "gold_ids_long": rec.get("gold_ids_long") or [],
                    "gold_answer": rec.get("gold_answer"),
                    "excluded_ids": rec.get("excluded_ids") or [],
                },
                evidence=[ctx.bench("bright", "documents", f"{domain}-00000-of-00001.parquet")],
                tags=["bright", domain],
                gold={
                    "source": "xlangai/BRIGHT",
                    "query_id": rec.get("id"),
                    "query": query,
                    "gold_ids": rec.get("gold_ids"),
                    "gold_answer": rec.get("gold_answer"),
                    "corpus": f"documents/{domain}-00000-of-00001.parquet",
                },
                split_key=f"bright:{rec.get('id')}",
            )

    return {
        "policy": "全部查询入库；语料不进 docs，只登记 corpus 路径。split 按 query id 哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["recall_at_k", "ndcg_at_10"],
                "missing_metrics": ["miss_on_stop_rate", "redundant_step_rate"],
                "note": "停止时机与多余步数需检索轨迹；先由 harness 记录 step 序列再补",
            },
            "domains": per_domain,
        },
    }
