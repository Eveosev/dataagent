"""B04 规则选择与应用准确率。

DeonticBench 的金标是该情形下的判定标签（yes / no / unknown）。产出取
output.label 或 output.verdict；归一后与金标比对。

说明：当前金标只发布判定标签，未发布“模型应引用哪条规则”，因此本 grader 判的是
“判定结论是否正确”；规则引用质量等自建标注接入后再单独成指标。
"""
from __future__ import annotations

from .common import norm_text, result

LABELS = {"yes": "yes", "no": "no", "unknown": "unknown", "是": "yes", "否": "no", "未知": "unknown", "不确定": "unknown"}


def normalize_label(value) -> str | None:
    text = norm_text(value)
    if text in LABELS:
        return LABELS[text]
    for key, label in LABELS.items():
        if text.startswith(key):
            return label
    return None


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = normalize_label((case.get("expected") or {}).get("value"))
    if gold is None:
        return result("rule_selection_accuracy", None, None, 0, "金标标签无法解析")
    pred = normalize_label(output.get("label") if isinstance(output, dict) else None)
    if pred is None:
        return result("rule_selection_accuracy", 0.0, 0, 1, "产出无 label/verdict")
    hit = int(pred == gold)
    return result("rule_selection_accuracy", float(hit), hit, 1, None if hit else f"pred={pred} gold={gold}")
