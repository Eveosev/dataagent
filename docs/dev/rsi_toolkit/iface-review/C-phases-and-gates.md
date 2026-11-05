---
title: 附录 C：阶段、门禁与文档修订
date: 2026-10-28
status: proposed
parent: ../2026-10-28-iface-plans-review.md
---

# 附录 C：阶段、门禁与文档修订

本附录属于 [IFace 两方案评审](../2026-10-28-iface-plans-review.md)。阶段编号统一用 M0-pre 到 M6，取代方案 A 的 M0–M6 和方案 B 的 M0–M5。

## C.1 阶段与门禁

| 阶段 | 工作 | 进入下一阶段的门 |
| --- | --- | --- |
| M0-pre 源码解耦 | 把 `rsi/__init__`、`control/__init__` 改为懒加载；把 rsi 用到的 toolkit 能力（schema loader、模型客户端、trace 归一）移到 rsi 下层，让 rsi 不再依赖 toolkit，从而断开 rsi↔toolkit 循环；toolkit 作为应用层，继续依赖 rsi；评测器和 verifier 的指纹改用显式稳定 ID，并保留旧指纹的兼容匹配表；为首批 5 个包各写一个 import-closure 测试 | 导入每个包的目标模块时，只会加载它自身和已声明的依赖；已有 qualification 在迁移前后匹配结果不变；现有回归测试全部通过 |
| M0 契约基线 | 用 `mint pull` 拉取 `agentcpm/iface-*@0.1.0`，记录 digest 和签名 keyid，作为权威基线；冻结 `iface.toml` v0；修复契约包生成器；写出 C1–C7 草案（[附录 B](B-capability-contracts.md)）；修正机器清单 | 5 个 schema 都有 fixture；每个首批包都有 `iface.toml`；没有 transport 的标为 `blocked-by-contract`；上游沟通清单已发出，不必等回复 |
| M1 首批 5 包与分发探针 | 用标准库实现 schema 子集校验器，与 jsonschema 做差分测试；迁移首批源码，原位置保留 re-export；迁移对应测试，补齐 redact 和 rsi CAS 的单元测试；在干净的 mint 工程里，用本地 scope 走通 `pull rsi-iface-data`、`add rsi-foundation` 和 `add rsi-evaluation`，再通过启动器调用 | 各包能脱离源码 checkout 安装，且不执行 pip；声称可替换的 `rsi-model-client` 和 `rsi-execution`，各有一个“同一调用方跑两个实现”的测试；依赖展开、启动器加载和卸载残留都有实测记录 |
| M2 执行组件 | 发布 `rsi-component-runner`；去掉对 `rsi.worker` 和 `RSI_ROOT` 的硬编码 | artifact、conformance、limits、kill/reap 和 sandbox 的负例全部通过 |
| M3 状态模块 | 发布 `rsi-storage`、`rsi-experience-store`、`rsi-recall-selection`、`rsi-asset-ledger`；兼容 `0001_core.sql` 的历史迁移记录；消除直接写 SQL 的代码；`Store.tx` 增加 savepoint 和锁 | 迁移、备份恢复、并发重放和故障注入测试通过；ingest 和发布的提交边界验证通过；召回由 release-set 驱动 |
| M4 宿主适配 | `MintHost` 和 `PilotDeckHost` 实现 `runtime-executor/v1` 端口，继续使用 `mint run --json` | execution ID 一致、事件完整、超时/取消/断连时返回 unknown、每次使用全新 workspace、credential proxy 正常工作，以上全部验证通过 |
| M5 应用组装与发布 | 组装 `rsi-toolkit`（控制）和 `rsi-runtime`（运行时）两个应用；在 CI 按平台构建编译型依赖目录；提供 stdio MCP 入口和 Skill；评估是否只用标准库实现 MCP | 干净工程能走通“安装、启动器、运行、MCP 调用、卸载”全流程，用户端不执行 pip；控制工程与运行时工程保持分离 |
| M6 cpmrt（可选） | cpmrt 发布正式 CLI/ACP 后，再实现 `runtime-executor/v1` 的 cpmrt 适配 | 执行和隔离验收标准与 M4 相同 |

## C.2 首批测试的迁移归属

| 包 | 迁入的现有测试 | 需补充的测试 |
| --- | --- | --- |
| `rsi-foundation` | `test_m0_contracts` | 子集校验器与 jsonschema 的差分测试；redact 单元测试；rsi CAS 单元测试 |
| `rsi-model-client` | `test_toolkit_launcher` | 替身模型的替换测试 |
| `rsi-evaluation` | `test_rsi_evaluation`、`test_rsi_judge`、`test_rsi_promotion` 中的纯函数用例 | 指纹迁移兼容测试 |
| `rsi-execution` | `test_common_host` | 两种 staging 策略的负例；替身宿主的替换测试 |

另有 10 个 rsi 测试文件直接实例化 `Store`，到 M3 再迁移。

## C.3 相关文档的修订待办

本轮先不改动：

- 在方案 A 和方案 B 的文首加上评审结论链接。
- 方案 B 改正三处：阶段编号改为本附录的编号；“7 个状态包”改为 6 个；“并行方案 B”的称呼改正。
- [机器清单](../../../architecture/rsi-toolkit-modules.toml)：
  - 修正依赖：evaluation-kit 依赖 paired-evidence，不依赖 measurement-evidence；component-runner 去掉对 measurement-evidence 的依赖；
  - 增加 contracts-runtime 和 execution-port 两个模块；
  - 增加发布包映射字段。
- 平台笔记中“mcp 为路线图”和“Python 不能用 plugin”两处，改为实测结论。
- 契约包生成器按[附录 A](A-first-batch-packages.md) A.3 修复。
