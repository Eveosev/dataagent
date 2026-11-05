"""B01 下游问答准确率。

问答对来自 MiMoTable / RealHiTBench，答案可能是数值、短词或整段自然语言。
判分口径：
1. 两边都能解析成数值 → 数值相等（容差 1e-9）；
2. 否则归一文本后完全相等；
3. 答案较长（>= 12 词）时允许“金标关键片段全包含”判对，避免措辞差异全判错；
   命中判对的比例记进 notes，便于回看口径是否过松。
"""
from __future__ import annotations

from .common import norm_text, numbers_equal, result

LONG_ANSWER_WORDS = 12


def _tokens(text: str) -> list[str]:
    return [t for t in norm_text(text).replace("\n", " ").split(" ") if t]


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = (case.get("expected") or {}).get("answer")
    if gold is None:
        return result("downstream_qa_accuracy", None, None, 0, "金标无 answer")
    pred = output.get("answer") if isinstance(output, dict) else None
    if pred is None:
        return result("downstream_qa_accuracy", 0.0, 0, 1, "产出无 answer")
    if numbers_equal(pred, gold):
        return result("downstream_qa_accuracy", 1.0, 1, 1, "数值相等")
    gp, gg = norm_text(pred), norm_text(gold)
    if gp and gp == gg:
        return result("downstream_qa_accuracy", 1.0, 1, 1, "文本相等")
    gold_tokens = _tokens(gold)
    if len(gold_tokens) >= LONG_ANSWER_WORDS:
        hit = sum(1 for t in set(gold_tokens) if t in set(_tokens(pred)))
        coverage = hit / len(set(gold_tokens))
        if coverage >= 0.9:
            return result("downstream_qa_accuracy", 1.0, 1, 1, f"长答案片段覆盖 {coverage:.2f}")
        return result("downstream_qa_accuracy", 0.0, 0, 1, f"长答案片段覆盖 {coverage:.2f}")
    return result("downstream_qa_accuracy", 0.0, 0, 1, None)
