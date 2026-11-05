"""B01 表头单元格正确率。

金标来源：expected.headers（按行优先的表头单元格列表）。外部数据集（MiMoTable /
RealHiTBench）只发布问答答案，不含表头结构，因此缺失时返回 None，记入 missing。
"""
from __future__ import annotations

from .common import missing, norm_cell, result


def _pred_headers(output: dict) -> list:
    for key in ("headers", "header", "header_rows"):
        value = output.get(key)
        if isinstance(value, list) and value:
            if all(isinstance(x, list) for x in value):
                return [cell for row in value for cell in row]
            return list(value)
    table = output.get("table")
    if isinstance(table, dict):
        return _pred_headers(table)
    return []


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = (case.get("expected") or {}).get("headers")
    if not gold:
        return missing("header_cell_accuracy", "金标无 headers：外部集只发布问答答案，表头结构待补")
    gold = [g for g in gold]
    pred = _pred_headers(output)
    if not pred:
        return result("header_cell_accuracy", 0.0, 0, len(gold), "产出无 headers 字段")
    hit = sum(1 for i, g in enumerate(gold) if i < len(pred) and norm_cell(pred[i]) == norm_cell(g))
    return result("header_cell_accuracy", hit / len(gold), hit, len(gold))
