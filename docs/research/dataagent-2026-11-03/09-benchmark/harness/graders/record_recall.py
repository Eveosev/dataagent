"""B03 记录完整率：列表型记录（收据菜单项、表单实体）的召回。

金标 records 取 expected.value 里的第一个非空列表（如 menu），或 expected.records。
匹配口径：按 record 内的键值子集匹配——一条预测记录与金标记录至少共享
`min(2, 字段数)` 个相同字段即算命中（收据里 nm+price 足以区分）。
"""
from __future__ import annotations

from .common import missing, norm_text, result, values_equal


def _records(payload) -> list[dict]:
    if isinstance(payload, list) and payload and all(isinstance(x, dict) for x in payload):
        return payload
    if isinstance(payload, dict):
        candidates = [v for v in payload.values() if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]
        if candidates:
            return max(candidates, key=len)
    return []


def _match(a: dict, b: dict) -> bool:
    shared = [k for k in a if k in b and not isinstance(a[k], (dict, list))]
    if not shared:
        return False
    need = min(2, len(shared))
    return sum(1 for k in shared if values_equal(a[k], b[k])) >= need


def grade(case: dict, output: dict, cfg: dict) -> dict:
    expected = case.get("expected") or {}
    gold = _records(expected.get("records") or expected.get("value"))
    if not gold:
        return missing("record_completeness", "金标无列表型记录")
    pred = _records(output.get("records") or output.get("json") or output.get("value") or output.get("data"))
    if not pred:
        return result("record_completeness", 0.0, 0, len(gold), "产出无记录列表")
    used = set()
    hits = 0
    for g in gold:
        for i, p in enumerate(pred):
            if i in used:
                continue
            if _match(p, g):
                used.add(i)
                hits += 1
                break
    return result("record_completeness", hits / len(gold), hits, len(gold), None if hits == len(gold) else f"漏 {len(gold) - hits} 条")
