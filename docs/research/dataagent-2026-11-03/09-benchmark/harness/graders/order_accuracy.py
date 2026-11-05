"""B02 阅读顺序准确率：块级 Kendall tau。

金标 blocks 每块有 text 与 order；产出 blocks 按阅读顺序排列（或自带 order 字段）。
按归一文本匹配块，计算产出顺序相对金标顺序的逆序对比例：
accuracy = 1 - inversions / C(n, 2)；匹配块 < 2 时不可判。
"""
from __future__ import annotations

from .common import missing, norm_text, result


def _gold_order(expected: dict) -> list[str]:
    blocks = expected.get("blocks") or []
    pairs = [(b.get("order"), norm_text(b.get("text"))) for b in blocks if isinstance(b, dict)]
    pairs = [(o, t) for o, t in pairs if t]
    pairs.sort(key=lambda x: (x[0] is None, x[0]))
    seen, out = set(), []
    for _, text in pairs:
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _pred_order(output: dict) -> list[str]:
    blocks = output.get("blocks")
    if not isinstance(blocks, list):
        return []
    items = [(b.get("order"), norm_text(b.get("text"))) for b in blocks if isinstance(b, dict)]
    items = [(o, t) for o, t in items if t]
    if any(o is not None for o, _ in items):
        items.sort(key=lambda x: (x[0] is None, x[0]))
    seen, out = set(), []
    for _, text in items:
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = _gold_order(case.get("expected") or {})
    pred = _pred_order(output)
    if len(gold) < 2:
        return missing("reading_order_accuracy", "金标块不足 2 个")
    rank = {text: i for i, text in enumerate(pred)}
    seq = [rank[t] for t in gold if t in rank]
    if len(seq) < 2:
        return missing("reading_order_accuracy", "产出与金标无可匹配块")
    inv = sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j])
    total = len(seq) * (len(seq) - 1) / 2
    acc = 1 - inv / total
    return result("reading_order_accuracy", acc, round(acc * total, 6), int(total), f"匹配 {len(seq)}/{len(gold)} 块")
