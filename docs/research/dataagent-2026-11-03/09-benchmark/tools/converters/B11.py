"""B11：动作执行与策略遵从〔FDE〕。

来源：
- τ²-bench（sierra-research/tau2-bench）：retail / airline / telecom 三域任务，含用户场景、政策文档与评测断言。
- CRMArena-Pro（Salesforce/CRMArenaPro）：b2c / b2b 任务，含 query、answer、reward_metric 与必填业务知识。

用例形状：用户场景 + 政策/业务知识 → 期望动作序列与断言。判定看环境最终状态与断言，而不仅是文本。
"""
from __future__ import annotations

import json

TAU_DOMAINS = ("retail", "airline", "telecom")


def build(ctx) -> dict:
    counts = {"tau2": _tau2(ctx), "crmarena": _crmarena(ctx)}
    return {
        "policy": "τ² 三域全量；CRMArena 取 b2c/b2b 非交互集，按题号哈希抽样。split 按域 + 题号哈希。",
        "extra": {
            "coverage": {
                "covered_metrics": ["pass_k_stability", "approval_trigger_accuracy"],
                "partial_metrics": ["violation_rate", "missed_refusal_rate"],
                "note": "违规与漏拒需环境侧动作日志与策略断言；τ² 的 evaluation_criteria 提供断言，CRMArena 只给最终答案",
            },
            "counts": counts,
        },
    }


def _tau2(ctx) -> int:
    base = ctx.raw_path("tau2-bench", "data", "tau2", "domains")
    if not base.exists():
        ctx.notes.append("τ²-bench 数据目录不存在")
        return 0
    ctx.source("tau2-bench")
    n = 0
    for domain in TAU_DOMAINS:
        tasks_file = base / domain / "tasks.json"
        if not tasks_file.exists():
            ctx.notes.append(f"缺少 {domain}/tasks.json")
            continue
        policy = base / domain / "policy.md"
        policy_ref = None
        if policy.exists():
            policy_ref = ctx.fixture(f"tau2-{domain}-policy.md", policy.read_text(encoding="utf-8"))
        tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
        for rec in tasks:
            n += 1
            scenario = rec.get("user_scenario") or {}
            instructions = scenario.get("instructions") or {}
            scenario_text = (
                f"# τ² {domain} 任务 {rec.get('id')}\n\n"
                f"## 用户画像\n\n{scenario.get('persona') or ''}\n\n"
                f"## 来电缘由\n\n{instructions.get('reason_for_call') or ''}\n\n"
                f"## 已知信息\n\n{instructions.get('known_info') or ''}\n\n"
                f"## 未知信息\n\n{instructions.get('unknown_info') or ''}\n\n"
                f"## 任务指令\n\n{instructions.get('task_instructions') or ''}\n"
            )
            scenario_ref = ctx.fixture(f"tau2-{domain}-{rec.get('id')}.md", scenario_text)
            inputs = [{"kind": "scenario", "ref": scenario_ref, "digest": None}]
            if policy_ref:
                inputs.append({"kind": "doc", "ref": policy_ref, "digest": None})
            criteria = rec.get("evaluation_criteria") or {}
            ctx.add(
                source="tau2",
                seq=n,
                inputs=inputs,
                expected={
                    "kind": "trajectory",
                    "actions": [a.get("name") for a in (criteria.get("actions") or [])],
                    "communicate": criteria.get("communicate_info") or criteria.get("nl_assertions"),
                    "reward_basis": criteria.get("reward_basis"),
                },
                evidence=[f"{scenario_ref}#任务指令"] + ([f"{policy_ref}#政策"] if policy_ref else []),
                tags=["tau2", domain, f"reward:{criteria.get('reward_basis') or 'unknown'}"],
                gold={"source": "sierra-research/tau2-bench", "domain": domain, "task": rec},
                split_key=f"tau2:{domain}:{rec.get('id')}",
            )
    return n


def _crmarena(ctx) -> int:
    if not ctx.raw_path("crmarena-pro").exists():
        ctx.notes.append("CRMArena-Pro 未下载")
        return 0
    ctx.source("crmarena-pro")
    n = 0
    for name in ("tasks_b2c.json", "tasks_b2b.json"):
        path = ctx.raw_path("crmarena-pro", name)
        if not path.exists():
            continue
        tasks = json.loads(path.read_text(encoding="utf-8"))
        for rec in tasks:
            n += 1
            meta = rec.get("metadata") or {}
            doc = (
                f"# CRMArena {name[:-5]} / {rec.get('task')} / idx {rec.get('idx')}\n\n"
                f"## 必填业务知识\n\n{meta.get('required') or ''}\n\n"
                f"## 可选领域知识\n\n{meta.get('optional') or ''}\n\n"
                f"## 用户画像\n\n{rec.get('persona') or ''}\n\n"
                f"## 问题\n\n{rec.get('query') or ''}\n"
            )
            ref = ctx.fixture(f"crm-{name[:-5]}-{rec.get('idx')}.md", doc)
            ctx.add(
                source="crm",
                seq=n,
                inputs=[{"kind": "case", "ref": ref, "digest": None}],
                expected={
                    "kind": "answer",
                    "answer": rec.get("answer"),
                    "reward_metric": rec.get("reward_metric"),
                    "task": rec.get("task"),
                },
                evidence=[f"{ref}#必填业务知识"],
                tags=["crmarena", name[:-5], rec.get("task") or "unknown", rec.get("reward_metric") or "unknown"],
                gold={"source": "Salesforce/CRMArenaPro", "raw": rec},
                split_key=f"crmarena:{name}:{rec.get('idx')}",
            )
    return n
