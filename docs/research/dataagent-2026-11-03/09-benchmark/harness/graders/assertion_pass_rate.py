"""B02 断言通过率：对结构/内容断言逐条判定。

断言形状（gold expected.assertions）：
  {"path": "blocks[0].category", "op": "eq|contains|gte|lte", "value": "title"}
当前 OmniDocBench 金标没有断言字段，返回 None 记 missing；接入自建断言集后即可用。
"""
from __future__ import annotations

import re

from .common import missing, norm_text, parse_number, result


def _walk(obj, path: str):
    cur = obj
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            idx = int(part[1:-1])
            if not isinstance(cur, list) or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
    return cur


def _check(actual, op: str, want) -> bool:
    if op == "eq":
        if isinstance(want, (int, float)):
            num = parse_number(actual)
            return num is not None and abs(num - float(want)) < 1e-9
        return norm_text(actual) == norm_text(want)
    if op == "contains":
        return norm_text(want) in norm_text(actual)
    num, target = parse_number(actual), parse_number(want)
    if num is None or target is None:
        return False
    return num >= target if op == "gte" else num <= target


def grade(case: dict, output: dict, cfg: dict) -> dict:
    assertions = (case.get("expected") or {}).get("assertions") or []
    if not assertions:
        return missing("assertion_pass_rate", "金标无 assertions 字段，待自建断言集")
    passed = 0
    for item in assertions:
        if not isinstance(item, dict):
            continue
        actual = _walk(output, str(item.get("path") or ""))
        if _check(actual, str(item.get("op") or "eq"), item.get("value")):
            passed += 1
    total = len(assertions)
    return result("assertion_pass_rate", passed / total, passed, total)
