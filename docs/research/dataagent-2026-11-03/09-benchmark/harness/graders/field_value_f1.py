"""B03 值 F1：字段级抽取的精确率/召回/F1。

金标：expected.value（嵌套 JSON）或 expected.fields（已展平）；产出取
output.json / output.fields / output.value / output.data。
口径：
- 两边都展平成「路径 → 叶子」；
- 金标为 null 的路径：产出缺省或 null 记命中（确实没有值）；
- 产出多出的路径记 FP；值不同记 FP+FN。
"""
from __future__ import annotations

from .common import flatten, missing, norm_text, result, values_equal


def _pred_payload(output: dict) -> dict:
    for key in ("json", "fields", "value", "data", "result"):
        value = output.get(key)
        if isinstance(value, dict):
            return value
    if isinstance(output.get("entities"), list):
        return {}
    return {}


def grade(case: dict, output: dict, cfg: dict) -> dict:
    expected = case.get("expected") or {}
    gold = expected.get("fields")
    if not isinstance(gold, dict):
        value = expected.get("value")
        gold = flatten(value) if isinstance(value, dict) else None
    if not gold:
        return missing("value_f1", "金标无结构化字段", 0)
    pred = _pred_payload(output)
    if not pred:
        return result("value_f1", 0.0, 0, len(gold), "产出无 JSON 字段")
    pred = flatten(pred)
    tp = fp = fn = 0
    for path, want in gold.items():
        have = pred.get(path)
        if want is None or norm_text(want) == "":
            if path not in pred or have is None or norm_text(have) == "":
                tp += 1
            else:
                fp += 1
            continue
        if values_equal(have, want):
            tp += 1
        else:
            fn += 1
            if path in pred:
                fp += 1
    for path in pred:
        if path not in gold:
            fp += 1
    num = 2 * tp
    den = 2 * tp + fp + fn
    f1 = num / den if den else 0.0
    return result("value_f1", f1, num, den, f"tp={tp} fp={fp} fn={fn}")
