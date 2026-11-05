"""B04 可判定性三分类准确率（decidable / needs_evidence / undecidable）。

金标需要 expected.decidability 字段。DeonticBench 只发布 yes/no/unknown 判定标签，
没有三分类的可判定性标注，因此当前数据下返回 None，记 missing——不把判定标签
硬映射成“可判定性”，避免指标名与口径不符。
"""
from __future__ import annotations

from .common import missing, norm_text, result

CLASSES = {
    "decidable": "decidable", "undecidable": "undecidable", "needs_evidence": "needs_evidence",
    "可判定": "decidable", "不可判定": "undecidable", "需补证": "needs_evidence",
}


def _class_of(value) -> str | None:
    return CLASSES.get(norm_text(value))


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = _class_of((case.get("expected") or {}).get("decidability"))
    if gold is None:
        return missing("decidability_accuracy", "金标无 decidability 三分类标注（DeonticBench 只给 yes/no/unknown）")
    pred = _class_of(output.get("decidable")) if output.get("decidable") is not None else _class_of(output.get("decidability"))
    if pred is None:
        return result("decidability_accuracy", 0.0, 0, 1, "产出无可判定性字段")
    hit = int(pred == gold)
    return result("decidability_accuracy", float(hit), hit, 1, None if hit else f"pred={pred} gold={gold}")
