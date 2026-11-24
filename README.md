# DataAgent

DataAgent / FDE Agent 的能力包、方案与实施记录。狭义 DataAgent 完成单次问答或分析；广义 DataAgent 持续建设并运行数据工作（语义、ontology、质量、评测资产）；FDE Agent 在此之上增加有副作用的动作及其契约、委托审批与交付。当前设计与实施以 [`docs/research/dataagent-2026-11-03/`](docs/research/dataagent-2026-11-03/README.md) 为准，飞书为发布副本。

在 AgentOS 宿主中挂载于 `domains/dataagent/`；工作约定见 [AGENTS.md](AGENTS.md)。

## 在对话里试用制度提取

要在其他项目里使用同一份 Skill，可用 npm 从本仓库的开发分支安装到 Codex 或 Claude Code，见[安装命令与试用方法](packages/capabilities/dataagent-fde/安装说明.md)。

用 Codex 打开本项目，新建对话，输入“帮我提取 `packages/capabilities/dataagent-fde/examples/reimbursement` 里的费用制度，沿用上次的表”。如需试用历史格式，将[上次提取结果](packages/capabilities/dataagent-fde/examples/上次提取结果.md)一起提供。目录里有两份演示原件，等助手询问版本后，回复“用 11 月版，只看差旅”。应收到带条号的差旅凭证、通勤排除和紧急抢修例外。也可以直接指定自己的附件。[Skill 入口](packages/capabilities/dataagent-fde/skills/fde-engineer/SKILL.md)

## 布局

```text
packages/capabilities/dataagent-*/   能力包（见下表）
docs/research/dataagent-2026-11-03/  当前设计、方案、实施与评审记录、Catalog、tools/build.py
docs/research/dataagent-*/           调研与历史版本
docs/research/fde-agent-2026-11-02/  FDE Agent 基础模块
docs/design/dataagent-*-v0.1/        历史设计
workspace/                           本地运行数据（忽略）；benchmark 原始数据在 workspace/benchmark-data/
```

## 能力包

| 包 | 类型 | 内容 | 方案 |
| --- | --- | --- | --- |
| `dataagent-contracts` | Python 库 | 第 0 层契约类型（pydantic）与生成的 JSON Schema | 05 |
| `dataagent-runtime` | Python 库 | 三层共用运行时：`invoke`、注册表、存储端口与适配器、`InferencePort`、DA12.1 复检钩子 | 08 §2 |
| `dataagent-data` | Mint bundle | 数据层 S0 32 项原子；MCP 与 CLI 入口 | 06 |
| `dataagent-application` | Mint bundle | 执行应用层 S0 13 项原子 | 07 |
| `dataagent-governance` | Mint bundle | 评测与治理层 S0 6 项原子 | 08 |
| `dataagent-cli` | Mint 静态包 | 统一 `dataagent` CLI 分发器 | 12 |
| `dataagent-ocr` | Python 库 + CLI + SKILL | OCR 提供方：OpenAI 兼容端点、隔离 venv 本地引擎、自定义 worker；测试调用与固定、质量监测与重选 | 13 |
| `dataagent-s0` | Mint preset | 组合三个 bundle 与 CLI 的 S0 工作区 | 08 §8 |
| `dataagent-scenarios` | 仅测试 | 跨层链路与端到端场景测试 | 08 §8 |

## 设计（Pluggable DataAgent）

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

## 实施方案与记录

| 文档 | 内容 |
| --- | --- |
| [数据层建设方案](docs/research/dataagent-2026-11-03/06-data-layer-build-plan.md) | S0 数据层 32 项与契约包 core；§12 为实施与评审记录索引；附录 A 内核组件事件接口提案（[飞书](https://modelbest.feishu.cn/docx/NvOsd04lAoZk60xY2Kpc4SrYnwf)） |
| [数据层实施记录](docs/research/dataagent-2026-11-03/06-data-layer-build/) | 各轮修复（`rN-fixes.md`）、评审（`rN-review.md`）、优化方案（`rN-plan.md`） |
| [执行应用层建设方案](docs/research/dataagent-2026-11-03/07-application-layer-build-plan.md) | 执行应用层非 FDE 110 项：S0 13 项、按需 90 项、S1 7 项 |
| [执行应用层实施记录](docs/research/dataagent-2026-11-03/07-application-layer-build/) | 评审（`rN-review.md`）与修复记录、复现脚本 |
| [评测与治理层建设方案](docs/research/dataagent-2026-11-03/08-governance-layer-build-plan.md) | 评测与治理层非 FDE 54 项：S0 6 项；运行时访问复检与外发检查；S0 Preset |
| [评测与治理层实施记录](docs/research/dataagent-2026-11-03/08-governance-layer-build/) | 评审与修复记录、复现脚本；含 `dataagent-runtime`、S0 组合与跨包共性问题 |
| [07/08 可行性评审](docs/research/dataagent-2026-11-03/archive/07-08-feasibility-review-2026-11-04.md) | 07、08 方案的技术可行性与 S0 接缝缺口 |
| [W0 接缝规格](docs/research/dataagent-2026-11-03/w0-seam-specifications.md) | S0 跨层接缝（codec、表与文档引用等）六项规格与两族样例 |
| [能力效果监控与 Benchmark](docs/research/dataagent-2026-11-03/09-benchmark-plan.md) | 需长期监控的 15 个核心模块、参考 benchmark、监控指标 |
| [评测任务目录](docs/research/dataagent-2026-11-03/09-benchmark/README.md) | 任务卡、评测集账本、轮次与基线、门槛与趋势看板、校验工具 |
| [S0 阶段报告](docs/research/dataagent-2026-11-03/archive/11-s0-stage-report.md) | 整体进展与阻断项；Mint 本地安装与端到端测试流程；51 个 S0 原子的测试方法 |
| [Mint 内 Agent 的 DataAgent CLI 调研](docs/research/dataagent-2026-11-03/archive/12-unified-cli-research.md) | Agent 自装与经 `dataagent` CLI 调用能力：Mint 机制、通道对比、包与命令设计、对 Mint 的诉求 |
| [统一 CLI 建设方案](docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md) | `dataagent-cli` 实施方案与 `12-cli-build/` 记录索引 |
| [OCR 组件方案](docs/research/dataagent-2026-11-03/13-ocr-component-plan.md) | `dataagent-ocr`：提供方类型、固定与重选规则、凭据、外发、依赖型引擎安装、数据层接入；记录在 `13-ocr-build/` |

## 调研

| 文档 | 内容 |
| --- | --- |
| [DataAgent 调研与 MintHub 落地方案 · 2026-10-30](docs/research/dataagent-2026-10-30/README.md) | 市场地图、能力拆解、benchmark 与评测、MintHub bundle/preset/app 设计、路线图 |
| [DataAgent 竞品与模块技术调研 · 2026-10-31](docs/research/dataagent-landscape-2026-10-31/README.md) | 十一个代表产品、dbt AI 增补、dbt/Ossie 语义层、八模块技术、X 与部署案例、应用难点与建设判断 |
| [自适应检索调研 · 2026-10-31](docs/research/dataagent-retrieval-2026-10-31/README.md) | 检索充分性与停止、行业实践、方法与论文、代码模式 |
| [线上 Pluggable DataAgent 评估 · 2026-11-02](docs/research/dataagent-2026-11-02/online-r1024-review.md) | 飞书 r1024 的优劣势、问题清单与修订 R1–R8 |

## 历史版本（不作为当前基线）

| 文档 | 内容 | 被替代为 |
| --- | --- | --- |
| [DataAgent 模块能力草案 · 2026-11-01](docs/research/dataagent-2026-11-01/00-module-capability-draft.md) | 狭义/广义 DataAgent 边界、12 个一级模块、72 个二级能力 | 总规划 |
| [DataAgent 原子能力简稿 · 2026-11-01](docs/research/dataagent-2026-11-01/02-atomic-capabilities-revised.md) | 三级能力划分：规整/不规则 Excel、分类检索、多后端 sql_execute、血缘 | 总规划 |
| [Pluggable DataAgent 本地 spec · 2026-11-02](docs/research/dataagent-2026-11-02/spec/) | 基于 r953 的本地实现设计与决策 D1–D12 | 01–05、06–08 |
| [DataAgent 数据层接口与代码结构草案 · v0.1](docs/design/dataagent-data-layer-v0.1/README.md) | 51 个能力组、160 项原子（基线 r1022） | 数据层 |
| [DataAgent 分层设计总导航 · v0.1](docs/design/dataagent-design-v0.1/README.md) | 18 个模块、434 项原子（基线 r1022） | 总规划与 01–04 |
| [v0.2 冻结](docs/research/dataagent-2026-11-02/sources/freeze-v0.2-2026-11-03/) | 飞书六篇导出、总 Catalog 全部记录、`manifest.json` | — |
