"""给定用例，产出「完美输出」——只用于打通链路与校准 grader。

这不是被测系统：`env.adapter=oracle`、`env.model=null` 会如实写进 run.json，
出分不能当模型能力，只能当「judge 口径自检」。
"""
from __future__ import annotations

import json
import pathlib
import time

NAME = "oracle"


def _map(task_id: str, expected: dict) -> dict:
    if task_id == "B01":
        return {"answer": expected.get("answer")}
    if task_id == "B02":
        return {"text": expected.get("text"), "blocks": expected.get("blocks") or [], "tables": expected.get("tables") or []}
    if task_id == "B03":
        out = {"json": expected.get("value")} if "value" in expected else {"entities": expected.get("entities") or []}
        if expected.get("spans"):
            out["spans"] = expected["spans"]
        if expected.get("pages"):
            out["pages"] = expected["pages"]
        return out
    if task_id == "B04":
        return {"label": expected.get("value")}
    if task_id == "B16":
        return {"pairs": expected.get("pairs") or []}
    if task_id == "B17":
        if "fields" in expected:
            return {
                "mappings": [
                    {
                        "source_field": item.get("source_field") or item.get("source"),
                        "target_field": item.get("target_field", item.get("target")),
                    }
                    for item in expected.get("fields") or []
                ]
            }
        return {
            "source_field": expected.get("source_field"),
            "target_field": expected.get("target_field"),
        }
    return {}


def run_case(case: dict, env: dict, cfg: dict) -> dict:
    started = time.time()
    task_id = env.get("task_id") or case.get("task_id")
    dataset = pathlib.Path(cfg["dataset_dir"])
    gold_path = dataset / "expected" / f"{case['case_id']}.json"
    if not gold_path.exists():
        return {"case_id": case["case_id"], "status": "failed", "output": None,
                "error": "expected 不存在", "latency_ms": 0}
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    output = _map(task_id, gold.get("expected") or {})
    return {
        "case_id": case["case_id"],
        "status": "ok",
        "output": output,
        "tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": int((time.time() - started) * 1000),
        "error": None,
    }
