"""B04 unknown 保持率：金标 unknown 的情形是否被如实判为 unknown。

只在金标为 unknown 的用例上计分（其他用例返回 None，不进分母），
避免“多报 unknown”刷高，也避免“少报 unknown”被稀释。
"""
from __future__ import annotations

from .common import missing, result
from .rule_choice_match import normalize_label


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = normalize_label((case.get("expected") or {}).get("value"))
    if gold != "unknown":
        return missing("unknown_retention", "金标非 unknown，不计入分母")
    pred = normalize_label(output.get("label"))
    hit = int(pred == "unknown")
    return result("unknown_retention", float(hit), hit, 1, None if hit else f"pred={pred}")
