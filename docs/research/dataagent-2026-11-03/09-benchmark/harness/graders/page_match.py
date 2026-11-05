"""B03 证据定位 F1（页级）。

金标需要 expected.pages（字段 → 页码），现有数据没有页级标注，返回 None 记 missing。
"""
from __future__ import annotations

from .common import missing


def grade(case: dict, output: dict, cfg: dict) -> dict:
    expected = case.get("expected") or {}
    gold = expected.get("pages")
    if not isinstance(gold, dict) or not gold:
        return missing("evidence_page_f1", "金标无 pages（字段级页码标注缺失）")
    pred = output.get("pages") if isinstance(output.get("pages"), dict) else {}
    tp = sum(1 for f, p in gold.items() if str(pred.get(f)) == str(p))
    fp = max(len(pred) - tp, 0)
    fn = len(gold) - tp
    num, den = 2 * tp, 2 * tp + fp + fn
    return {"metric": "evidence_page_f1", "value": num / den if den else 0.0, "numerator": num, "denominator": den, "judgeable": True, "notes": None}
