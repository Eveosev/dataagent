# AgentOS package workspace

AgentOS 负责 Kernel 接口契约、能力包的组合、应用包的适配和安装后验证。PilotDeck、StaffDeck 等产品的业务源码保留在各自独立仓库；本目录只保存它们接入 AgentOS 所需的包清单、构建约定、适配器和一致性验证。

## 文档索引

| 文档 | 内容 | 来源 |
| --- | --- | --- |
| [Agent OS 应用组件整体规划](docs/official/agent-os-application-components.md) | 原文抄录；覆盖 20 个通用技术方向、24 个业务方向及 10 条完整链路 | [飞书原文](https://modelbest.feishu.cn/wiki/CJkhwwhBRinSwSk26NTc4mZKns4) |
| [文档状态](docs/STATUS.md) | `docs/` 下各文档的现行 / 证据 / 过期 / 无用标记、替代关系与待修链接 | — |

### DataAgent 与 FDE Agent

狭义 DataAgent 完成单次问答或分析；广义 DataAgent 持续建设并运行数据工作（语义、ontology、质量、评测资产）；FDE Agent 在此之上增加有副作用的动作及其契约、委托审批与交付。当前设计与实施以 [`docs/research/dataagent-2026-11-03/`](docs/research/dataagent-2026-11-03/README.md) 为准，飞书为发布副本。

**设计（Pluggable DataAgent）**

| 文档 | 内容 | 飞书 |
| --- | --- | --- |
| [目录与同步说明](docs/research/dataagent-2026-11-03/README.md) | 文件表、生成与同步命令、冻结位置、修订项 | — |
| [总规划](docs/research/dataagent-2026-11-03/00-pluggable-dataagent.md) | 定义、平台对接待决 P1–P7、跨层契约、18 个模块 / 141 个能力组 / 458 项原子、切片 S0–S2、唯一归属 | [总规划](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c) |
| [数据层](docs/research/dataagent-2026-11-03/01-data-layer.md) | DA01–DA04、DA13 | [数据层](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) |
| [执行应用层](docs/research/dataagent-2026-11-03/02-application-layer.md) | DA05–DA10 | [执行应用层](https://modelbest.feishu.cn/docx/ReDXdJzLWoihZDxqaO0clUxInKf) |
| [评测与治理层](docs/research/dataagent-2026-11-03/03-governance-layer.md) | DA11–DA12 | [评测与治理层](https://modelbest.feishu.cn/docx/QwN4dFvdroH7X3xI3Eycnkbon3b) |
| [持续运行与 FDE 交付](docs/research/dataagent-2026-11-03/04-operations-fde-layer.md) | DA14–DA18（FDE 扩展） | [持续运行与 FDE 交付](https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke) |
| [dataagent-contracts](docs/research/dataagent-2026-11-03/05-contracts.md) | 第 0 层应用级能力协议：内核映射、准入与版本规则、S0 类型与字段 | [契约](https://modelbest.feishu.cn/docx/VavsdOWFeoLBFrxOt9JcjAsInDe) |
| [总 Catalog](docs/research/dataagent-2026-11-03/catalog/atomic-capability-catalog.json) | 458 项原子的编号、operation、源码文件、切片、S0 闭环族 | [多维表格](https://modelbest.feishu.cn/base/AjY0bNRutawmZ0s62MZcUSmQn4f) |
| [FDE Agent 六个基础模块](docs/research/fde-agent-2026-11-02/README.md) | 环境接入、动作本体、动作契约、委托与审批、现场上下文、证据与验收 | — |

**实施方案与记录**

| 文档 | 内容 |
| --- | --- |
| [数据层建设方案](docs/research/dataagent-2026-11-03/06-data-layer-build-plan.md) | S0 数据层 32 项与契约包 core；§12 为实施与评审记录索引；附录 A 内核组件事件接口提案（[飞书](https://modelbest.feishu.cn/docx/NvOsd04lAoZk60xY2Kpc4SrYnwf)） |
| [数据层实施记录](docs/research/dataagent-2026-11-03/06-data-layer-build/) | 各轮修复（`rN-fixes.md`）、评审（`rN-review.md`）、优化方案（`rN-plan.md`） |
| [执行应用层建设方案](docs/research/dataagent-2026-11-03/07-application-layer-build-plan.md) | 执行应用层非 FDE 110 项：S0 13 项、按需 90 项、S1 7 项 |
| [执行应用层实施记录](docs/research/dataagent-2026-11-03/07-application-layer-build/) | 评审（`rN-review.md`）与修复记录、复现脚本 |
| [评测与治理层建设方案](docs/research/dataagent-2026-11-03/08-governance-layer-build-plan.md) | 评测与治理层非 FDE 54 项：S0 6 项；运行时访问复检与外发检查；S0 Preset |
| [评测与治理层实施记录](docs/research/dataagent-2026-11-03/08-governance-layer-build/) | 评审与修复记录、复现脚本；含 `dataagent-runtime`、S0 组合与跨包共性问题 |
| [07/08 可行性评审](docs/research/dataagent-2026-11-03/07-08-feasibility-review-2026-11-04.md) | 07、08 方案的技术可行性与 S0 接缝缺口 |
| [W0 接缝规格](docs/research/dataagent-2026-11-03/w0-seam-specifications.md) | S0 跨层接缝（codec、表与文档引用等）六项规格与两族样例 |
| [能力效果监控与 Benchmark](docs/research/dataagent-2026-11-03/09-benchmark-plan.md) | 需长期监控的 15 个核心模块、参考 benchmark、监控指标 |
| [评测任务目录](docs/research/dataagent-2026-11-03/09-benchmark/README.md) | 任务卡、评测集账本、轮次与基线、门槛与趋势看板、校验工具 |
| [S0 阶段报告](docs/research/dataagent-2026-11-03/11-s0-stage-report.md) | 整体进展与阻断项；Mint 本地安装与端到端测试流程；51 个 S0 原子的测试方法 |
| [Mint 内 Agent 的 DataAgent CLI 调研](docs/research/dataagent-2026-11-03/12-unified-cli-research.md) | Agent 自装与经 `dataagent` CLI 调用能力：Mint 机制、通道对比、包与命令设计、对 Mint 的诉求 |

**调研**

| 文档 | 内容 |
| --- | --- |
| [DataAgent 调研与 MintHub 落地方案 · 2026-10-30](docs/research/dataagent-2026-10-30/README.md) | 市场地图、能力拆解、benchmark 与评测、MintHub bundle/preset/app 设计、路线图 |
| [DataAgent 竞品与模块技术调研 · 2026-10-31](docs/research/dataagent-landscape-2026-10-31/README.md) | 十一个代表产品、dbt AI 增补、dbt/Ossie 语义层、八模块技术、X 与部署案例、应用难点与建设判断 |
| [自适应检索调研 · 2026-10-31](docs/research/dataagent-retrieval-2026-10-31/README.md) | 检索充分性与停止、行业实践、方法与论文、代码模式 |
| [线上 Pluggable DataAgent 评估 · 2026-11-02](docs/research/dataagent-2026-11-02/online-r1024-review.md) | 飞书 r1024 的优劣势、问题清单与修订 R1–R8 |

**历史版本**（不作为当前基线）

| 文档 | 内容 | 被替代为 |
| --- | --- | --- |
| [DataAgent 模块能力草案 · 2026-11-01](docs/research/dataagent-2026-11-01/00-module-capability-draft.md) | 狭义/广义 DataAgent 边界、12 个一级模块、72 个二级能力 | 总规划 |
| [DataAgent 原子能力简稿 · 2026-11-01](docs/research/dataagent-2026-11-01/02-atomic-capabilities-revised.md) | 三级能力划分：规整/不规则 Excel、分类检索、多后端 sql_execute、血缘 | 总规划 |
| [Pluggable DataAgent 本地 spec · 2026-11-02](docs/research/dataagent-2026-11-02/spec/) | 基于 r953 的本地实现设计与决策 D1–D12 | 01–05、06–08 |
| [DataAgent 数据层接口与代码结构草案 · v0.1](docs/design/dataagent-data-layer-v0.1/README.md) | 51 个能力组、160 项原子（基线 r1022） | 数据层 |
| [DataAgent 分层设计总导航 · v0.1](docs/design/dataagent-design-v0.1/README.md) | 18 个模块、434 项原子（基线 r1022） | 总规划与 01–04 |
| [v0.2 冻结](docs/research/dataagent-2026-11-02/sources/freeze-v0.2-2026-11-03/) | 飞书六篇导出、总 Catalog 全部记录、`manifest.json` | — |

## 目录约定

```text
packages/
├── agent-kernel/                 # Kernel 源码仓库（独立 git clone）；iface 契约的权威源与分发件都在这里
│   ├── kernel/iface/src/         #   ← 契约权威源（canonical，随 kernel master 演进）
│   └── packages/iface-*/         #   ← 10 个 iface 分发包（0.1.2，由 scripts/sync-iface-packages.sh 生成）
├── kernel-iface/                 # ⚠ 0.1.0 历史冻结快照，已过时；勿作对比基线（见下节）
├── capabilities/                 # 可被多个应用复用的能力包
│   └── dataagent-*/              #   DataAgent S0 能力包（见下表）
└── applications/
    ├── pilotdeck/                 # PilotDeck 的 AgentOS/Mint 应用包脚手架
    └── staffdeck/                 # StaffDeck 的 AgentOS/Mint 应用包脚手架

integrations/                     # AgentOS 侧适配器，不复制产品源码
├── pilotdeck/
└── staffdeck/

conformance/applications/         # 安装、启动、协议和生命周期验证
├── pilotdeck/
└── staffdeck/

compatibility/                    # Kernel、Mint、应用包的兼容矩阵
workspace/projects.yaml           # 外部仓库路径、revision 和接入状态

apps/plugins/                      # 现有独立插件工作区（保持原位）
└── rsi-toolkit/
```

应用包目录里的 `mint.toml` 目前表示应用工程/组装入口的脚手架。经过真实构建和一致性验证后，才把产物作为 Mint 的 `kind = "app"` 发行。这里不存放用户凭据、模型 Key、会话数据或外部产品源码副本。

`apps/plugins/` 保留现有插件项目的独立边界；它不等同于 `packages/applications/` 中面向用户交付的 PilotDeck/StaffDeck 应用包。

### DataAgent 能力包（`packages/capabilities/`）

| 包 | 类型 | 内容 | 方案 |
| --- | --- | --- | --- |
| `dataagent-contracts` | Python 库 | 第 0 层契约类型（pydantic）与生成的 JSON Schema | 05 |
| `dataagent-runtime` | Python 库 | 三层共用运行时：`invoke`、注册表、存储端口与适配器、`InferencePort`、DA12.1 复检钩子 | 08 §2 |
| `dataagent-data` | Mint bundle | 数据层 S0 32 项原子；MCP 与 CLI 入口 | 06 |
| `dataagent-application` | Mint bundle | 执行应用层 S0 13 项原子 | 07 |
| `dataagent-governance` | Mint bundle | 评测与治理层 S0 6 项原子 | 08 |
| `dataagent-s0` | Mint preset | 组合三个 bundle 的 S0 工作区 | 08 §8 |
| `dataagent-scenarios` | 仅测试 | 跨层链路与端到端场景测试 | 08 §8 |

## iface 契约：位置与对比流程

Kernel 接口契约不再以 `packages/kernel-iface/` 为准，权威位置已迁到 agent-kernel 仓库内：

| 位置 | 角色 | 状态 |
| --- | --- | --- |
| `packages/agent-kernel/kernel/iface/src/` | 契约**权威源**（canonical），随 kernel `master` 演进 | 现行，唯一可引用基线 |
| `packages/agent-kernel/packages/iface-*` | 10 个 iface **分发包**（`iface-types/session/store/policy/extension/tool/model/context/loop/env`），由权威源逐文件生成 | 现行，0.1.2 |
| [`packages/kernel-iface/`](packages/kernel-iface/DEPRECATED.md) | 0.1.0 **历史冻结快照**，同步至 kernel `d950766`（2026-10-29）；已标记废弃 | 已过时，勿作对比基线 |
| Mint Hub `agentcpm/iface-*@0.1.0` | 线上制品 | 早于上述两者内容，引用前先核 digest |

### 每次与 mint / iface 对比前：先确认并拉取 agent-kernel 更新

`packages/agent-kernel` 是独立 git 仓库（origin 为 `agent-kernel.git`），本目录不在其版本控制内，也不会自动跟随上游。因此**任何与 Mint（`agentcpm/iface-*` 制品、Mint CLI）或 iface 契约的对比、取证、结论输出之前**，必须先做下面三步；否则结论会基于过期源码：

```bash
cd packages/agent-kernel
git fetch origin --prune                                  # 1. 取回远端最新
test "$(git rev-list --count HEAD..@{u})" -eq 0 || git pull --ff-only   # 2. 落后则快进拉取（工作区脏时先处理脏文件，不要强拉）
bash scripts/sync-iface-packages.sh --check                # 3. 确认 packages/iface-* 与 kernel/iface/src 一致
```

- 第 2 步 `rev-list --count` 输出 `0` 表示已是最新；非 `0` 必须先 `git pull --ff-only` 再开始对比。
- 第 3 步失败说明分发件与权威源漂移，此时以 `kernel/iface/src` 为准，不要引用 `packages/iface-*` 的旧字节。
- 对比结论中应记录实际使用的 revision（`git rev-parse HEAD`），便于之后复核。

当前外部仓库状态见 [`workspace/projects.yaml`](workspace/projects.yaml)。
