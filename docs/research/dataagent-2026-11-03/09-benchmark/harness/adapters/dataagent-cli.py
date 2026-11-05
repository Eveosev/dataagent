"""dataagent CLI 适配器：把统一入参翻译成一次 CLI 调用。

约定（与 harness/README.md §2 一致）：

    dataagent run --case <case.json> --out <run_dir>/artifacts/<case_id> --config <cfg.json>

CLI 必须把结果写到 `<out>/result.json`，适配器读回来作为 `output`。
CLI 不存在、超时、退出码非 0、result.json 缺失，都返回明确的 failed，不伪造成功。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import time

NAME = "dataagent-cli"


def run_case(case: dict, env: dict, cfg: dict) -> dict:
    started = time.time()
    timeout = float((cfg.get("run") or {}).get("timeout_s") or 1800)
    run_dir = pathlib.Path(cfg["run_dir"])
    out_dir = run_dir / "artifacts" / case["case_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = run_dir / "adapter.config.json"
    if not cfg_path.exists():
        cfg_path.write_text(json.dumps({"env": env}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cmd = list(cfg.get("cli") or ["dataagent", "run"]) + [
        "--case", str(case["_path"]),
        "--out", str(out_dir),
        "--config", str(cfg_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"case_id": case["case_id"], "status": "failed", "output": None,
                "error": f"CLI 不存在: {cmd[0]}", "latency_ms": int((time.time() - started) * 1000)}
    except subprocess.TimeoutExpired:
        return {"case_id": case["case_id"], "status": "timeout", "output": None,
                "error": f"超时 {timeout}s", "latency_ms": int((time.time() - started) * 1000)}
    result_path = out_dir / "result.json"
    if proc.returncode != 0 or not result_path.exists():
        tail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
        return {"case_id": case["case_id"], "status": "failed", "output": None,
                "error": f"exit={proc.returncode} {tail[0][:200]}", "latency_ms": int((time.time() - started) * 1000)}
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    usage = payload.get("usage") or {}
    return {
        "case_id": case["case_id"],
        "status": "ok",
        "output": payload.get("output") or payload,
        "tokens": usage.get("tokens") or 0,
        "cost_usd": float(usage.get("cost_usd") or 0.0),
        "latency_ms": int((time.time() - started) * 1000),
        "error": None,
    }
