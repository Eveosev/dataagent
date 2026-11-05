"""B08：预测与优化建模。

来源：ORLM-Bench 合集（chenyitian-shanshu/ORLMBenchmark）五个子集：
- OptiBench、NL4OPT：线性/整数规划的自然语言题 → 建模答案
- OptMATH_Bench_166：数学优化题
- MAMO_EasyLP / MAMO_ComplexLP：线性规划建模
另预留 context-is-key（季节性/约束型时序预测），数据到位后追加。

用例形状：业务问题 → 目标函数与约束（模型）。判分看模型结构与最优值是否一致；本机无求解器时退化为结构匹配。
"""
from __future__ import annotations

import hashlib
import json

SUBSETS = {
    "OptiBench.jsonl": "optibench",
    "NL4OPT.jsonl": "nl4opt",
    "OptMATH_Bench_166.jsonl": "optmath",
    "MAMO_EasyLP_fixed.jsonl": "mamo_easy",
    "MAMO_ComplexLP_fixed.jsonl": "mamo_complex",
    "IndustryOR_fixed.json": "industryor",
    "IndustryOR_fixedV2.json": "industryor_v2",
}


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
    ctx.source("orlm-bench")
    n = 0
    per = {}
    for fname, slug in SUBSETS.items():
        path = ctx.raw_path("orlm-bench", fname)
        if not path.exists():
            continue
        rows = _rows(path)
        per[slug] = len(rows)
        for row_no, rec in enumerate(rows):
            q = rec.get("en_question") or rec.get("question")
            a = rec.get("en_answer") or rec.get("answer")
            if not q:
                continue
            # 确定性地只保留约 20%，给预测类用例留出权重；其余留作后续扩展
            if int(hashlib.sha1(f"{fname}:{row_no}".encode()).hexdigest()[:8], 16) % 5:
                continue
            n += 1
            ref = ctx.fixture(f"orlm-{slug}-{n:04d}.md", q)
            ctx.add(
                source="orlm",
                seq=n,
                inputs=[{"kind": "question", "ref": ref, "digest": None}],
                expected={"kind": "model_answer", "answer": a},
                evidence=[ref],
                tags=["orlm", slug],
                gold={
                    "source": "chenyitian-shanshu/ORLMBenchmark",
                    "subset": fname,
                    "question": q,
                    "answer": a,
                },
                split_key=f"orlm:{fname}:{n}",
            )

    n += _context_is_key(ctx, n)

    return {
        "policy": "ORLM 五子集按 20% 确定性抽样 + context-is-key 时序预测全量；split 按子集 + 序号哈希。抽样保留在 manifest.build.available。",
        "extra": {
            "coverage": {
                "covered_metrics": ["formulation_exact_match", "constraint_coverage"],
                "missing_metrics": ["optimality_gap", "constraint_satisfaction_rate"],
                "note": "最优值需运行求解器；本机无 LP/MIP 求解器，先按结构匹配判分；约束满足率需在 grader 里按 constraint_min/max 复核",
            },
            "counts": per,
        },
    }


def _context_is_key(ctx, start: int) -> int:
    base = ctx.raw_path("context-is-key")
    files = sorted((base / "data").glob("test-*.parquet")) or sorted((base / "data").glob("*.parquet"))
    if not files:
        ctx.notes.append("context-is-key 尚未下载")
        return 0
    import pyarrow.parquet as pq

    ctx.source("context-is-key")
    rows = pq.read_table(files[0]).to_pylist()
    n = 0
    for rec in rows:
        scenario = rec.get("scenario") or ""
        past = rec.get("past_time")
        future = rec.get("future_time")
        if not scenario or not future:
            continue
        n += 1
        doc = (
            f"# {rec.get('name')}（seed {rec.get('seed')}）\n\n"
            f"## 背景\n\n{rec.get('background') or ''}\n\n"
            f"## 情景\n\n{scenario}\n\n"
            f"## 约束\n\n{rec.get('constraints') or '无'}\n\n"
            f"## 季节周期\n\n{rec.get('seasonal_period')}\n\n"
            f"## 历史序列（past_time）\n\n```json\n{json.dumps(past, ensure_ascii=False)[:200000]}\n```\n"
        )
        ref = ctx.fixture(f"cik-{rec.get('name')}-{rec.get('seed')}.md", doc)
        ctx.add(
            source="cik",
            seq=start + n,
            inputs=[{"kind": "series", "ref": ref, "digest": None}],
            expected={
                "kind": "forecast",
                "future": future,
                "constraint_min": rec.get("constraint_min"),
                "constraint_max": rec.get("constraint_max"),
                "region_of_interest": rec.get("region_of_interest"),
                "metric_scaling": rec.get("metric_scaling"),
            },
            evidence=[ref],
            tags=["context-is-key", str(rec.get("name") or "unknown"), "forecast"],
            gold={
                "source": "ServiceNow/context-is-key",
                "name": rec.get("name"),
                "seed": rec.get("seed"),
                "background": rec.get("background"),
                "scenario": scenario,
                "constraints": rec.get("constraints"),
                "seasonal_period": rec.get("seasonal_period"),
                "past_time": past,
                "future_time": future,
                "constraint_min": rec.get("constraint_min"),
                "constraint_max": rec.get("constraint_max"),
            },
            split_key=f"cik:{rec.get('name')}:{rec.get('seed')}",
        )
    return n
