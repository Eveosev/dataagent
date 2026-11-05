"""B03 证据定位 F1（词级）。

金标需要 expected.spans（每字段的原文片段或字符区间），当前 ExtractBench/CORD/FUNSD
都没有给出证据区间，返回 None 记 missing；接入带 span 的自建标注后即可判分。
"""
from __future__ import annotations

from .common import missing


def grade(case: dict, output: dict, cfg: dict) -> dict:
    expected = case.get("expected") or {}
    if not expected.get("spans"):
        return missing("evidence_span_f1", "金标无 spans（现有一批数据集只给值，不给证据区间）")
    if not output.get("spans"):
        return {"metric": "evidence_span_f1", "value": 0.0, "numerator": 0, "denominator": len(expected["spans"]), "judgeable": True, "notes": "产出无 spans"}
    gold = {str(s.get("field")): str(s.get("text") or "") for s in expected["spans"] if isinstance(s, dict)}
    pred = {str(s.get("field")): str(s.get("text") or "") for s in output["spans"] if isinstance(s, dict)}
    tp = sum(1 for f, t in gold.items() if f in pred and t and t in pred[f])
    fp = len(pred) - tp
    fn = len(gold) - tp
    num, den = 2 * tp, 2 * tp + fp + fn
    return {"metric": "evidence_span_f1", "value": num / den if den else 0.0, "numerator": num, "denominator": den, "judgeable": True, "notes": None}
