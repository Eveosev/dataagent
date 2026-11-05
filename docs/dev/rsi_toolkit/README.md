# RSI Toolkit Plugin 设计与交付入口

日期：2026-10-27。产品源码和宿主接入实现位于 [apps/plugins/rsi-toolkit](../../../apps/plugins/rsi-toolkit/README.md)。本目录保留设计、原始交付要求和过程记录；最终验收状态、真实实验结果及缺项见[进度](progress.md)与各实现报告。

正式交付：commit `a9e536fc1bba53d287e6d75cce32600b0daadffc`，Python 436 项与 Node 16 项测试通过。云端源码、安装包、证据、短片与校验和见[最终交付索引](https://modelbest.feishu.cn/docx/CWQ3dKJ0xoui54xKn4BcpL4xncC)；逐项范围见[验收](../../../apps/plugins/rsi-toolkit/docs/design/acceptance.md)，附件与云端下载校验见[归档记录](cloud-artifacts.md)。

## 目标与原始验收要求

RSI Toolkit 固定模型权重，通过实际任务比较项目 Skill 候选，保留冻结用例、原始轨迹、独立评分和版本谱系，并由操作者审批发布与回滚。PilotDeck 和 Mint 使用同一控制服务与判决逻辑；AgentOS 当前交付宿主契约。

原始要求为 **2026-10-27 08:00 Asia/Shanghai** 前交付，10:00 测试与提交。下表记录验收目标，不代表各项已通过。

| 交付层 | 验收目标 | 验收依据 |
| --- | --- | --- |
| 共用服务 | 持久化实验、冻结提案/选择/审计、鉴权及恢复 | 自动测试、负例、重启与未知执行记录 |
| PilotDeck | 真实宿主与模型完成 baseline、candidate、review、publish、rollback | 原始轨迹、项目 Skill 哈希、外部新会话 smoke 与影像 |
| Mint | 本地包和 bridge 实际调用 MCP，CLI/Core 执行候选与资产切换 | 版本探针、安装文件、NDJSON、独立验分和新会话证据 |
| AgentOS | `rsi.host/v1` 契约、schema 与 conformance fixture | 契约测试；真实 Kernel 接通另列 |
| Benchmark | SQL、账本、workflow 与生命周期负例；记录专业任务差距 | 冻结用例、verifier、逐题结果与来源许可 |
| 可复用材料 | 独立启动与安装命令、测试清单、截图、短视频和文档索引 | 干净环境复跑及完整证据路径 |

`full pass` 要求全部 P0 验收通过；仍有 P0 缺项时应标记 `partial deliverable` 并列明缺项。插件调用成功、任务闭环、分数变化与统计证据分别报告。小样本保持 `NEEDS_REVIEW` / `insufficient`。

## 当前结构与行为

| 产品位置 | 职责 |
| --- | --- |
| `service/control/`、`service/toolkit/` | 单一控制服务、CLI、模型客户端、鉴权与发布 |
| `service/harness/`、`service/benchmarks/` | 导入学习器/存储、公开任务与独立 verifier |
| `service/connectors/common/`、`agentcpm/`、`mint/` | Host 契约、暂存、PilotDeck Gateway、Mint CLI/Core 与 Seatbelt 包装器 |
| `plugins/pilotdeck/`、`plugins/mint/`、`assets/skills/` | 宿主包、安装程序、MCP bridge 与共用 Skill 源 |
| `contracts/`、`conformance/`、`samples/` | schema、宿主与隔离探针、可分发样例 |

1. `rsi-toolkit serve` 在 loopback 启动单个 ASGI 服务，提供 control MCP、可选 runtime MCP、HTTP API 和进程 readiness。一个进程持有一个外部 `state_dir`；readiness 不证明宿主或 provider 已接通。
2. agent、operator、runtime 使用三个不同凭据。Runtime 只允许 scope 内的 recall，未配置时关闭 runtime MCP。launcher 将 token 授权给该配置中的全部 target；独立授权域应使用独立服务、配置和 token。被测工程不安装 control 工具。
3. 当前控制入口支持 Default 与 OPRO。提案只消费 construct 任务/反馈；select 结果在 audit 前固定，平分及 audit 回退保留基线。原始提案与解析后的完整 Skill 分别留存；未知执行持久化为 `result_unknown`，不自动重放。
4. 发布为操作者审批后原子替换一个登记的项目 Skill 文件，绑定 target、版本、当前哈希及一次性 approval；回滚使用相同规则。Release 保持 `loaded="unverified"`，外部原生新会话 smoke 作为单独证据，不自动改写该字段。
5. PilotDeck 插件使用项目 `.pilotdeck/plugins/`；执行依赖 Gateway WS 1.2 的会话、提交与取消能力，普通 adapter 不提供 OS 隔离。Mint CLI 0.1.10 / Core 0.1.6 使用已实现的官方 SDK stdio-to-HTTP bridge，安装到初始化并显式建立信任的工程；未向 MintHub 发布。
6. `mint-seatbelt` 提供实测 macOS 包装器：精确子环境、全新工区、外层 Seatbelt、单一 loopback 模型代理。测量限于 macOS 27.0 build 26A428 / Core 0.1.6；路径/硬链接、系统策略导入及同用户进程限制见隔离说明。普通 Mint 暂存约束不等于 OS sandbox，`isolation="verified"` 是可信操作者的部署声明。
7. AgentOS 当前只有契约、schema 与 fixture，无真实 Kernel 执行。保留的 console/Docker/dev/UI 入口属于 legacy；可选 UI 尚未连接新控制 API。

## 文档索引

- [IFace v2 设计](../../superpowers/specs/2026-10-28-rsi-iface-v2-design.md)（现行）：架构、兼容策略、契约声明、分发路线、M0-pre 到 M6 门禁；[首批实施计划](../../superpowers/plans/2026-10-28-rsi-iface-v2-m0-m1.md)；入口见 [iface-review/README.md](iface-review/README.md)。
- [RSI Toolkit 设计文档（插件产品视角）](../../architecture/rsi-toolkit-design.md)：把 RSI 定位为可插拔的任务级自进化插件；覆盖平台/任务/资产模型、L0–L4 能力分级、自进化闭环与生态结合，工程映射见附录。
- [IFace 两方案评审](2026-10-28-iface-plans-review.md)（过期，v2 的评审依据）：两份 IFace 拆分方案的评审结论与已确认决策。附录：[首批包设计与分发](iface-review/A-first-batch-packages.md)、[通用能力契约草案](iface-review/B-capability-contracts.md)、[阶段与门禁](iface-review/C-phases-and-gates.md)、[核验证据](iface-review/D-verification-evidence.md)。
- [iface 拆分与 MintHub 发布方案（方案 A，过期，被 v2 替代）](2026-10-28-iface-modularization-and-minthub.md)：五条决策（拆契约不拆进程、13 个能力模块、五类发布形态、`<iface>.data` 命名、继续用 MintHost）、发布顺序与 M0–M5 验收门。
- [Mint 平台笔记](2026-10-28-mint-platform-notes.md)（过期，基于 CLI 0.1.11）：四层架构、11 种包类型、单元/OCI、loop 契约、发布流程与错误码、**文档与已发布 CLI 0.1.11 的 7 处差异**、可复制的实测命令。
- [取舍说明](2026-10-28-iface-plan-rationale.md)（过期，随方案 A 被替代）：v1→v3 更正记录、与[并行方案 B](../../superpowers/specs/2026-10-28-rsi-iface-modularization-design.md) 的分工与三处采纳、完整风险登记、未决问题、反模式。
- [契约包生成器与发布脚本](mint-iface/README.md)（过期，现行为 `packages/agent-kernel/scripts/sync-iface-packages.sh`、`publish-iface-mint-hub.sh`）：`mint pack` 6/6 通过；发布脚本默认 dry-run。
- [通用插件总体方案](../../superpowers/specs/2026-10-27-pluggable-rsi-toolkit-design.md)：面向 MintHub 的双模式交付、trace/组件/经验/评测/召回契约、本地 SQLite+CAS 存储与默认 RecallPolicy、Agentic Recall 与策略自优化、Mint CLI 验收及 M0–M5 里程碑；已按评审补齐契约；里程碑已被 v2 的 M0-pre–M6 替代。
- [Mint CLI 驱动 RSI 的真实迭代结果](mint-rsi-iteration-results-2026-10-27.md)：Job-Bench、WorkBuddy 的候选、评分、失败和恢复；[复现入口](../../../apps/plugins/rsi-toolkit/docs/benchmarks/mint-rsi-iteration-runbook.md)。
- [插件目录与接入架构](../../../apps/plugins/rsi-toolkit/docs/design/plugin-architecture.md)：实际目录、单服务、两条调用链、发布与隔离边界。
- [产品 README](../../../apps/plugins/rsi-toolkit/README.md)：当前启动、安装、配置与复现入口。
- [控制与宿主契约](../../../apps/plugins/rsi-toolkit/contracts/README.md)：执行、鉴权、提案、发布及持久化语义。
- [隔离证据与限制](../../../apps/plugins/rsi-toolkit/conformance/isolation/README.md)：具体测量环境、探针与边界。
- [进度](progress.md)、[核心实现报告](../../../apps/plugins/rsi-toolkit/docs/design/core-report.md)、[Mint 接入报告](../../../apps/plugins/rsi-toolkit/docs/design/mint-report.md)：过程、实测与待验收项。
- [可插拔与双模式经验学习可行性调研](2026-10-27-pluggable-plugin-and-experience-feasibility.md)：跨 harness 插件、用户数据集/评测兜底、经验召回与多轨迹 Skill 晋升的代码级判定。
- [宿主 Hooks 与适配复核](2026-10-27-host-hooks-and-adapter-review.md)：Claude Code、Codex、DeepSeek Harness 的 hook 与结构化历史证据，以及早期可行性判断的修正。
- [架构与接口设计](../../../apps/plugins/rsi-toolkit/docs/design/design.md)：早期方案比较及设计依据，当前实现以产品契约和源码为准。
- [Benchmark 调研与差距](../../../apps/plugins/rsi-toolkit/docs/design/benchmark-gap-analysis.md)：PenguinHarness、Harness2、现有覆盖与专业任务差距。
- [交付安排](../../../apps/plugins/rsi-toolkit/docs/design/delivery-plan.md)：原始时间节点、验收、飞书与影像要求。
- [Legacy 入口说明](../../../apps/plugins/rsi-toolkit/docs/LEGACY.md)：保留代码与新控制保证的范围。
- [飞书过程文档](https://modelbest.feishu.cn/docx/ChoXdLBeXorjGyxUK75cWylPn4d)：过程材料索引。

自动测试、宿主原生探针和真实模型实验按各自证据解读；本页不汇总最终实验成绩。
