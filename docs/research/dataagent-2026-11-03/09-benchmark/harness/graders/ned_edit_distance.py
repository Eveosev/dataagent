"""B02 文本 NED：1 - 编辑距离 / 最长长度，方向 lower 表示值越小越好。

金标文本 = expected.text（按阅读顺序拼接的块文本）。产出优先取 text，其次拼 blocks。
"""
from __future__ import annotations

from .common import edit_distance, norm_text, prediction_text, result


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = norm_text((case.get("expected") or {}).get("text") or "")
    if not gold:
        return result("text_ned", None, None, 0, "金标无 text")
    pred = norm_text(prediction_text(output))
    if not pred:
        return result("text_ned", 1.0, len(gold), len(gold), "产出无文本，按全错计")
    dist = edit_distance(pred, gold)
    denom = max(len(pred), len(gold))
    return result("text_ned", dist / denom if denom else 0.0, dist, denom)
