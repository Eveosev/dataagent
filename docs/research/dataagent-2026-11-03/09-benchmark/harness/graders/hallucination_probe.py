"""B03 编造率：金标为 null 的字段被填了值。

只统计“金标明确为 null/空”的路径；若该用例没有 null 字段则返回 None（不进分母）。
"""
from __future__ import annotations

from .common import flatten, missing, norm_text, result


def grade(case: dict, output: dict, cfg: dict) -> dict:
    expected = case.get("expected") or {}
    gold = expected.get("fields")
    if not isinstance(gold, dict):
        value = expected.get("value")
        gold = flatten(value) if isinstance(value, dict) else {}
    null_paths = [p for p, v in gold.items() if v is None or norm_text(v) == ""]
    if not null_paths:
        return missing("hallucination_rate", "该用例无 null 字段")
    pred = output.get("json") or output.get("fields") or output.get("value") or output.get("data") or {}
    pred = flatten(pred) if isinstance(pred, dict) else {}
    filled = [p for p in null_paths if p in pred and pred[p] is not None and norm_text(pred[p]) != ""]
    return result("hallucination_rate", len(filled) / len(null_paths), len(filled), len(null_paths), None if not filled else f"编造 {len(filled)} 个字段")
