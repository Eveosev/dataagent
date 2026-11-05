"""空基线：什么也不输出，用来确认指标下限与 missing 行为。

`status=ok` + 空 output 是合法产出（不是失败），因此空白答案会被判 0 分；
adapter 名字会写进 run.json，避免和真实模型混淆。
"""
from __future__ import annotations

import time

NAME = "empty"


def run_case(case: dict, env: dict, cfg: dict) -> dict:
    started = time.time()
    return {
        "case_id": case["case_id"],
        "status": "ok",
        "output": {},
        "tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": int((time.time() - started) * 1000),
        "error": None,
    }
