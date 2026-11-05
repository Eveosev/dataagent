"""B04：制度 → 规则 → 可判定性与适用范围。

来源：
- DeonticBench（gydou/DeonticBench）：5 个域 × {whole, hard}，含 statutes 原文、question、label、reference_prolog。
- RuleArena（skyriver-2000/RuleArena）：95 条规则 / 816 题，规则选择与应用。

用例形状：statutes（制度原文，落 fixtures） + question + facts → label。
证据：从 statutes 抽出的章节标题；从 reference_prolog 抽出的规则谓词，供 rule_choice_match 判分。
"""
from __future__ import annotations

import re

import pyarrow.parquet as pq

# 只取二分类域：airline 与 sara_numeric 的 label 是数值答案（计数题），
# 与 rule_selection_accuracy 的分类口径不兼容，未入库（见 NOTES「数据构建」）。
DOMAINS = ["housing", "sara_binary", "uscis-aao"]
LABEL_MAP = {"yes": "yes", "no": "no", "1": "yes", "0": "no", "accepted": "yes", "dismissed": "no"}


def _sections(statutes: str) -> list[str]:
    return [s.strip("# \n") for s in re.findall(r"===\s*([^=]+?)\s*===", statutes or "")]


def _predicates(prolog: str, limit: int = 40) -> list[str]:
    seen = []
    for name in re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*\(", prolog or "", flags=re.M):
        if name not in seen:
            seen.append(name)
    return seen[:limit]


def build(ctx) -> dict:
    ctx.source("deonticbench")
    seq = 0
    counts = {"deonticbench": 0}

    for domain in DOMAINS:
        whole = ctx.raw_path("deonticbench", domain, "whole-00000-of-00001.parquet")
        hard = ctx.raw_path("deonticbench", domain, "hard-00000-of-00001.parquet")
        if not whole.exists():
            ctx.notes.append(f"缺少 {domain}/whole parquet")
            continue
        # hard 是 whole 的子集，只用来打标签，避免同一行重复入库
        hard_ids = set(pq.read_table(hard).column("id").to_pylist()) if hard.exists() else set()
        for row in pq.read_table(whole).to_pylist():
            subset = "hard" if row.get("id") in hard_ids else "whole"
            raw_label = row.get("label")
            label = LABEL_MAP.get(str(raw_label).strip().lower())
            if label is None:
                continue
            seq += 1
            statutes = row.get("statutes") or ""
            prolog = row.get("reference_prolog") or ""
            facts = row.get("text") or ""
            question = row.get("question") or ""

            case_doc = (
                f"# {domain} / {subset}\n\n"
                f"## 制度原文\n\n{statutes}\n\n"
                f"## 事实\n\n{facts}\n\n"
                f"## 问题\n\n{question}\n"
            )
            ref = ctx.fixture(f"{domain}-{subset}-{seq:04d}.md", case_doc)

            ctx.add(
                source="deon",
                seq=seq,
                inputs=[{"kind": "doc", "ref": ref, "digest": None}],
                expected={"kind": "label", "value": label, "raw_label": raw_label, "question": question},
                evidence=[f"{ref}#制度原文"] + [f"statute:{s}" for s in _sections(statutes)[:4]],
                tags=[domain, subset, "deontic", "zh" if _has_cjk(statutes) else "en"],
                split_key=f"deontic:{row.get('id')}",
                gold={
                    "source": "gydou/DeonticBench",
                    "row_id": row.get("id"),
                    "expect_label": label,
                    "raw_label": raw_label,
                    "rule_predicates": _predicates(prolog),
                    "reference_prolog": prolog[:20000],
                },
            )
            counts["deonticbench"] += 1

    return {
        "policy": "只取二分类域（housing / sara_binary / uscis-aao）的 whole 集，hard 作为标签复用不重复入库；label 统一归一到 yes/no（原始值记在 gold.raw_label）；split 按行 id 哈希 60/20/20。statutes 与事实合并为单份 fixtures 文档。",
        "extra": {
            "coverage": {
                "covered_metrics": ["rule_selection_accuracy"],
                "missing_metrics": [
                    "condition_direction_consistency",
                    "decidability_accuracy",
                    "unknown_retention",
                ],
                "note": "airline 与 sara_numeric 的 label 是数值答案，不适用于分类指标，未入库；二分类域没有 unknown 标签，unknown_retention 需自建歧义用例；方向一致性与三分类需自建配对/标注。",
            },
            "counts": counts,
        },
    }


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text[:2000])
