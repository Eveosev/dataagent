"""B12：数据权限、脱敏与越权〔安全门〕。

来源：AgentDojo（ethz-spylab/agentdojo）v1 任务套件：banking / slack / travel / workspace。
- user_tasks：正常任务，金标是应触发的工具调用序列（ground_truth）。
- injection_tasks：注入目标，金标是攻击者想达成的动作（GOAL），用于检测是否被注入带偏。

用例形状：用户指令（+ 环境/工具清单）→ 期望动作序列。安全判据：越权调用与敏感字段泄漏都由动作日志判。
说明：agentdojo 的注入攻击载荷（attacks）在 v1 以字符串模板另存，本轮只建「目标 + 用户任务」用例。
"""
from __future__ import annotations

import ast
import json


def _calls_in(node: ast.AST) -> list[dict]:
    out = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        fn = sub.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
        if name != "FunctionCall":
            continue
        kwargs = {kw.arg: _lit(kw.value) for kw in sub.keywords if kw.arg}
        out.append({"function": kwargs.get("function"), "args": kwargs.get("args")})
    return out


def _lit(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except Exception:  # noqa: BLE001
        try:
            return ast.unparse(node)
        except Exception:  # noqa: BLE001
            return None


def build(ctx) -> dict:
    ctx.source("agentdojo")
    suites = ctx.raw_path("agentdojo", "src", "agentdojo", "default_suites", "v1")
    seq = 0
    per_suite = {}
    for suite in ("banking", "slack", "travel", "workspace"):
        user_file = suites / suite / "user_tasks.py"
        if not user_file.exists():
            ctx.notes.append(f"缺少 {suite}/user_tasks.py")
            continue
        per_suite[suite] = {"user": 0, "injection": 0}
        for cls in _classes_generic(user_file):
            prompt = _attr_const(cls, "PROMPT")
            if not prompt:
                continue
            gt = next((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "ground_truth"), None)
            calls = _calls_in(gt) if gt else []
            seq += 1
            ref = ctx.fixture(f"ad-{suite}-{cls.name}.md", f"# AgentDojo {suite} / {cls.name}\n\n{prompt}\n")
            ctx.add(
                source="ad",
                seq=seq,
                inputs=[{"kind": "instruction", "ref": ref, "digest": None}],
                expected={
                    "kind": "tool_calls",
                    "calls": calls,
                    "n_calls": len(calls),
                },
                evidence=[ref],
                tags=["agentdojo", suite, "user_task"],
                gold={
                    "source": "ethz-spylab/agentdojo",
                    "suite": suite,
                    "task": cls.name,
                    "prompt": prompt,
                    "ground_truth_calls": calls,
                },
                split_key=f"ad:{suite}:{cls.name}",
            )
            per_suite[suite]["user"] += 1

        inj_file = suites / suite / "injection_tasks.py"
        if not inj_file.exists():
            continue
        for cls in _classes_generic(inj_file):
            goal = _attr_const(cls, "GOAL")
            if not goal:
                continue
            seq += 1
            ref = ctx.fixture(f"ad-{suite}-{cls.name}.md", f"# AgentDojo {suite} / {cls.name}\n\n{goal}\n")
            ctx.add(
                source="ad",
                seq=seq,
                inputs=[{"kind": "instruction", "ref": ref, "digest": None}],
                expected={"kind": "attack_goal", "goal": goal, "forbidden": True},
                evidence=[ref],
                tags=["agentdojo", suite, "injection"],
                gold={
                    "source": "ethz-spylab/agentdojo",
                    "suite": suite,
                    "task": cls.name,
                    "goal": goal,
                    "comment": _attr_const(cls, "COMMENT"),
                },
                split_key=f"ad-inj:{suite}:{cls.name}",
            )
            per_suite[suite]["injection"] += 1

    return {
        "policy": "user_tasks 与 injection_tasks 分开建；split 按套件 + 类名哈希。注入载荷（attacks）未入，见 NOTES 待办。",
        "extra": {
            "coverage": {
                "covered_metrics": ["injection_resistance", "task_completion"],
                "partial_metrics": ["sensitive_leak_rate", "privilege_escalation_rate"],
                "note": "泄漏与越权需要工具调用日志里的参数快照；agentdojo 环境在 harness 侧起",
            },
            "counts": per_suite,
        },
    }


def _classes_generic(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            yield node


def _attr_const(cls: ast.ClassDef, name: str):
    for node in cls.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return _lit(node.value)
    return None
