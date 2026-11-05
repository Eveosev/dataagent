"""B01 行保留率：静默丢行为 0。

金标 row_count 来自 expected.row_count（数据行数，不含表头）。产出 rows 或 row_count
不足即扣分；超出不奖励（保留率封顶 1.0）。
"""
from __future__ import annotations

from .common import missing, result


def _pred_rows(output: dict):
    value = output.get("rows")
    if isinstance(value, list):
        return len(value)
    if isinstance(output.get("row_count"), int):
        return int(output["row_count"])
    table = output.get("table")
    if isinstance(table, dict):
        rows = table.get("rows")
        if isinstance(rows, list):
            return len(rows)
    return None


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = (case.get("expected") or {}).get("row_count")
    if not isinstance(gold, int) or gold <= 0:
        return missing("row_retention", "金标无 row_count：需结构标注后启用")
    pred = _pred_rows(output)
    if pred is None:
        return result("row_retention", 0.0, 0, gold, "产出无 rows/row_count")
    kept = min(pred, gold)
    return result("row_retention", kept / gold, kept, gold, None if pred >= gold else f"漏 {gold - pred} 行")
