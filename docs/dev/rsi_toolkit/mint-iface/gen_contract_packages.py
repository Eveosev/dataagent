#!/usr/bin/env python3
"""把 rsi_toolkit 的冻结契约（contracts/*.json）生成为可 `mint publish` 的契约包。

为什么需要生成器：8 个 `rsi-iface-*` 契约包必须是同一形状（mint.toml + README + schema
+ skills/<name>/SKILL.md），逐个手写必然漂移。本脚本用一张表描述全部包，只允许
"表里没有的东西不存在"。

实测基线（2026-10-28，本机 `mint 0.1.11`）：

  * `kind = "iface"` 被发布的 mint 0.1.11 直接拒绝：
    `unknown variant 'iface', expected one of core, host, plugin, overlay, bundle,
     skill, mcp, preset, template, app, agent`
  * 线上已发布的 10 个 `agentcpm/iface-*@0.1.0` 实际是 `kind = "bundle"`，
    靠 `provides.interfaces` 表达"我是契约包"。`mint info` 能看到
    `provide {"interfaces":["tool"],"skills":["iface-tool"]}`。
  * `kind = "bundle"` 要求包内至少有一个 skills/ commands/ agents/ hooks/
    .mcp.json，所以契约包用 `skills/<同名>/SKILL.md` 作为载荷。

用法：
    python3 gen_contract_packages.py --out /tmp/rsi-iface --scope your-scope
    python3 gen_contract_packages.py --out /tmp/rsi-iface --scope your-scope --version 0.1.0
    python3 gen_contract_packages.py --out /tmp/rsi-iface --check   # 只自检不落盘
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACTS = REPO_ROOT / "apps" / "plugins" / "rsi-toolkit" / "contracts"

LICENSE = "AGPL-3.0-only"
REPOSITORY = "https://codehub.devcloud.cn-north-4.huaweicloud.com/5a5fe37f080d4dcdab39d8b3ea837bb1/agent-os.git"

# ---------------------------------------------------------------------------
# 契约包表：新增一个 iface 就在这里加一行。
# schema=None 表示"契约还没写"，生成器会跳过并报 UNRESOLVED，避免发出空壳包。
# ---------------------------------------------------------------------------
PACKAGES = [
    {
        "iface": "rsi-host",
        "pkg": "rsi-iface-host",
        "schema": "host.v1.json",
        "schema_id": "urn:rsi:host:v1",
        "title": "rsi.host/v1 同步执行边界",
        "summary": "Host.capabilities() / Host.execute(request, cancel_event) 的请求与结果形状。"
                   "执行 ID 必须先持久化再调用；未知结果不得重放。",
        "traits": [
            "capabilities() -> dict（至少 fresh_session / assets 声明 supported|unsupported|unverified）",
            "execute(request, cancel_event) -> dict（同步；终态五选一，含 result_unknown）",
        ],
        "consumers": [
            "service/control/controller.py::_execute",
            "service/connectors/mint/host.py::MintHost",
            "service/connectors/agentcpm/host.py::PilotDeckHost",
            "service/connectors/common/host.py::Host（Protocol，仅形状）",
        ],
    },
    {
        "iface": "rsi-trace",
        "pkg": "rsi-iface-trace",
        "schema": "rsi.trace.v1.json",
        "schema_id": "urn:rsi:trace:v1",
        "title": "rsi.trace/v1 执行轨迹",
        "summary": "宿主中立的轨迹记录。采集模式与覆盖率必须声明真实观测范围；"
                   "拿不到的字段留在 extensions，不猜。",
        "traits": [
            "无 trait：纯数据契约，由 rsi-kernel 的 trace-ingest 消费",
            "status ∈ complete|truncated|missing_tail|unsupported 必须如实上报",
        ],
        "consumers": [
            "service/rsi/cli.py::trace-ingest",
            "service/toolkit/m0_legacy.py::body_to_trace",
            "service/learning.py::LearningService.ingest",
        ],
    },
    {
        "iface": "rsi-experience",
        "pkg": "rsi-iface-experience",
        "schema": "rsi.experience.v1.json",
        "schema_id": "urn:rsi:experience:v1",
        "title": "rsi.experience/v1 经验修订",
        "summary": "一条经验的某个修订。experience_id 跨编辑稳定；content_hash 覆盖单次修订；"
                   "semantic_key 只用于去重。",
        "traits": [
            "state ∈ draft|eligible|validated|quarantined|retired",
            "support 必须区分独立支持与重放（重放不增加 support）",
        ],
        "consumers": [
            "service/rsi/experience.py::ExperienceService",
            "service/rsi/store.py（experience / experience_revision / experience_support）",
        ],
    },
    {
        "iface": "rsi-evaluator",
        "pkg": "rsi-iface-evaluator",
        "schema": "rsi.evaluator.v1.json",
        "schema_id": "urn:rsi:evaluator:v1",
        "title": "rsi.evaluator/v1 评测器身份与资格",
        "summary": "评测器必须带预注册的资格结论才能支撑晋级。缺失或未计分的数据必须可见。",
        "traits": [
            "kind ∈ program|rubric|composite",
            "qualification 未通过时不得进入发布决策",
        ],
        "consumers": [
            "service/rsi/evaluation.py（Exact/Contains/JSONFields/Rubric/Composite）",
            "service/rsi/judge.py::LLMJudge",
            "service/rsi/components.py::Registry（evaluator 组件类）",
        ],
    },
    {
        "iface": "rsi-recall",
        "pkg": "rsi-iface-recall",
        "schema": "rsi.recall.v1.json",
        "schema_id": "urn:rsi:recall:v1",
        "title": "rsi.recall/v1 召回请求与响应",
        "summary": "本地召回契约。BM25 只是排序信号；接受与否看 query coverage 与词法得分。",
        "traits": [
            "request：project_id / target_id / query / policy 必填",
            "response：backend ∈ lexical|agentic|lexical-fallback 必须如实上报",
        ],
        "consumers": [
            "service/rsi/runtime.py::RuntimeService.recall",
            "service/rsi/policy.py::Selector / injection_block",
            "plugins/mint/rsi-runtime（MCP 端点 /mcp/runtime）",
        ],
    },
    {
        "iface": "rsi-component",
        "pkg": "rsi-iface-component",
        "schema": "rsi.component.v1.json",
        "schema_id": "urn:rsi:component:v1",
        "title": "rsi.component/v1 组件清单",
        "summary": "组件必须声明 trust 与 isolation。worker 只是故障隔离，不是安全边界；"
                   "untrusted 必须 sandboxed-worker。",
        "traits": [
            "kind ∈ harness_adapter|evaluator|learner|recall_backend|exporter",
            "isolation ∈ in-process|worker|sandboxed-worker（in-process 仅限 first-party）",
            "conformance.result=pass 是 Registry.load() 的前置条件",
        ],
        "consumers": [
            "service/rsi/components.py::Manifest / Registry / ConformanceRunner",
            "service/rsi/worker.py（JSONL 子进程协议）",
            "service/examples/rsi_components/echo（外部示例包）",
        ],
    },
    # ---- 以下 2 个契约尚无 schema：先生成器跳过，见设计文档 §5.3 ----
    {
        "iface": "rsi-experiment",
        "pkg": "rsi-iface-experiment",
        "schema": None,
        "schema_id": "urn:rsi:experiment:v1",
        "title": "rsi.experiment/v1 实验编排（待编写 schema）",
        "summary": "run / status / cancel / review 的控制面契约。目前只有 Python 方法面"
                   "（Controller.run/status/cancel/review）与 MCP 工具面，没有机器可读 schema。",
        "traits": [
            "run(target_id, learner, settings) -> run_id（立即返回）",
            "status(run_id, cursor) -> 终态/部分执行/分数/事件 ID/next_cursor",
            "cancel / review 与 run 共用 agent 凭据；target 注册后不可变",
        ],
        "consumers": ["service/control/controller.py（run/status/cancel/review）"],
    },
    {
        "iface": "rsi-release",
        "pkg": "rsi-iface-release",
        "schema": None,
        "schema_id": "urn:rsi:release:v1",
        "title": "rsi.release/v1 审批与发布台账（待编写 schema）",
        "summary": "approve / apply / rollback 的一次性引用语义：引用绑定 target、run、候选、"
                   "当前哈希与操作，有期限、一次性，apply 前重查哈希与路径约束。",
        "traits": [
            "approve(run_id, expected_current_hash) -> approval_ref（有期限、一次性）",
            "apply(run_id, approval_ref, expected_current_hash) -> release（原子替换单文件）",
            "approve_rollback / rollback 使用同一规则恢复先前版本",
            "release.loaded 恒为 unverified（文件落地 ≠ 宿主已加载）",
        ],
        "consumers": ["service/control/controller.py（approve/apply/rollback）"],
    },
]

SKILL_TEMPLATE = """# {pkg}

`{iface}` 契约的 **使用说明**（不是实现）。机器可读形状见同包 `schema.json`
（`{schema_id}`）。

## 这个包是什么

{summary}

## 契约要点

{traits}

## 谁在消费

{consumers}

## 边界

- 本包只定义形状：不读文件系统、不启动进程、不做鉴权、不含凭据。
- 实现不在本包里。实现方见设计文档
  `docs/dev/rsi_toolkit/2026-10-28-iface-modularization-and-minthub.md`。
- 版本语义：包 SemVer 与 `schema_version` 常量**分别**演进。破坏性改动升主版本，
  且 `schema_version` 同步改为 `{iface}/vN`。
"""

README_TEMPLATE = """# {scope}/{pkg}

RSI 契约包（`provides.interfaces = ["{iface}"]`，**只定义形状，不含实现**）。

| 项 | 值 |
| --- | --- |
| interface | `{iface}` |
| schema | [`schema.json`](schema.json)（`{schema_id}`） |
| 来源 | `apps/plugins/rsi-toolkit/contracts/{schema}`（逐字节复制） |
| 许可 | {license} |
| 版本 | {version} |

## 契约摘要

{summary}

## 为什么它是 `kind = "bundle"` 而不是 `kind = "iface"`

发布的 mint 0.1.11 没有 `iface` 这个 kind（实测拒绝：
`unknown variant 'iface'`）。线上 10 个 `agentcpm/iface-*@0.1.0` 同样以
`bundle` 发布并用 `provides.interfaces` 表达契约身份，`mint info` 可见。
等 `Kind::Iface` 进入发布通道后，本目录只需把 `kind` 改回 `iface` 并去掉
`skills/` 载荷。

## 安装与消费

```sh
mint add {scope}/{pkg}@{version}
mint info {scope}/{pkg}          # 应显示 provides.interfaces
```

安装后 schema 落在 `.mint/packages/{scope}/{pkg}@{version}/schema.json`，
可直接喂给你的 JSON Schema 校验器。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
"""


def _toml(pkg: dict, scope: str, version: str) -> str:
    keywords = ["iface", "rsi", pkg["iface"].split("-", 1)[1], "contract"]
    return f"""[package]
name = "{scope}/{pkg['pkg']}"
version = "{version}"
kind = "bundle"
description = "RSI {pkg['iface']} 契约（{pkg['title']}）：只定义形状，不含实现"
license = "{LICENSE}"
repository = "{REPOSITORY}"
keywords = {json.dumps(keywords, ensure_ascii=False)}

# 发布的 mint 0.1.11 没有 Kind::Iface；用 bundle + provides.interfaces 表达契约身份。
# bundle 必须至少有一个 skills|commands|agents|hooks|.mcp.json，故带一份 SKILL.md。
[provides]
interfaces = ["{pkg['iface']}"]
skills = ["{pkg['pkg']}"]

[requires]
api = ">=0.1"
"""


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def generate(out: Path, scope: str, version: str) -> tuple[int, list[str]]:
    out.mkdir(parents=True, exist_ok=True)
    written, missing = 0, []
    for pkg in PACKAGES:
        if pkg["schema"] is None:
            missing.append(pkg["pkg"])
            continue
        source = CONTRACTS / pkg["schema"]
        if not source.is_file():
            missing.append(pkg["pkg"])
            continue

        root = out / pkg["pkg"]
        (root / "skills" / pkg["pkg"]).mkdir(parents=True, exist_ok=True)
        fields = {k: v for k, v in pkg.items() if k not in {"schema", "schema_id"}}
        (root / "mint.toml").write_text(_toml(pkg, scope, version), encoding="utf-8")
        (root / "README.md").write_text(
            README_TEMPLATE.format(
                scope=scope, version=version, license=LICENSE,
                schema=pkg["schema"], schema_id=pkg["schema_id"], **fields,
            ),
            encoding="utf-8",
        )
        shutil.copyfile(source, root / "schema.json")
        (root / "skills" / pkg["pkg"] / "SKILL.md").write_text(
            SKILL_TEMPLATE.format(
                pkg=pkg["pkg"],
                iface=pkg["iface"],
                schema_id=pkg["schema_id"],
                summary=pkg["summary"],
                traits=_bullets(pkg["traits"]),
                consumers=_bullets(pkg["consumers"]),
            ),
            encoding="utf-8",
        )
        written += 1
    return written, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="输出目录（每个包一个子目录）")
    parser.add_argument("--scope", default="local", help="MintHub scope（必须是你拥有的）")
    parser.add_argument("--version", default="0.1.0", help="包版本（SemVer）")
    parser.add_argument("--check", action="store_true", help="只检查契约源是否齐全，不落盘")
    args = parser.parse_args(argv)

    if args.check:
        missing = [p["pkg"] for p in PACKAGES if p["schema"] is None or not (CONTRACTS / p["schema"]).is_file()]
        print(f"契约源目录: {CONTRACTS}")
        for pkg in PACKAGES:
            mark = "OK " if pkg["pkg"] not in missing else "TODO"
            print(f"[{mark}] {pkg['pkg']:20s} interface={pkg['iface']:16s} schema={pkg['schema']}")
        return 0 if len(missing) <= 2 else 1

    if not args.out:
        parser.error("需要 --out（或用 --check）")

    written, missing = generate(args.out, args.scope, args.version)
    print(f"生成 {written} 个契约包 → {args.out}（scope={args.scope}, version={args.version}）")
    if missing:
        print("未生成（契约 schema 尚缺，见设计文档 §5.3）：" + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
