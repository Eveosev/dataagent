---
version: 5
date: 2026-11-19
status: 实施中
---

# 本地接入与工作流建设记录

| 文件 | 内容 |
| --- | --- |
| [落地方案](../16-local-ingestion-workflow-build-plan.md) | 本地组件交付、包与接口、四个里程碑、十一项实施任务及验收 |
| [计划自检](plan-review.md) | 设计覆盖、接口与依赖检查、未执行项 |
| [测试数据与验收场景清单](test-inventory.md) | 文件和动态样例、各阶段验收状态、待准备的数据与证据入口 |
| [本机离线安装与操作](local-offline-quickstart.md) | `prepare_acceptance.sh` 构建、`dataagent workbench serve/stop/list`、一次性入口、浏览器手工探查和审核 |
| [Mint 离线安装与操作](mint-offline-quickstart.md) | Mint 离线装包、OCR 安装与 doctor 期望、审批与项目沙箱、TUI/`mint gui`、保存被拦处置 |
| [离线输入测试用例](offline-input-cases.md) | 合成材料、连接与凭据、TSV/JSONL/docx、保存被拦处置、逐场景操作和通过条件 |
| [SQLite 本体发现](sqlite-ontology-discovery.md) | 发现入口、证据约束、草案审核和离线验收 |
| [离线安装与链路验收](implementation-2026-11-11.md) | 可复跑命令、真实运行引用、评审修复与待验收场景 |
| [打包桌面版 GUI 工具通道核实](gui-channel-check.md) | T02：打包版 Mint Agent 能起项目会话、能加载技能，但拿不到 DataAgent 的 MCP 工具；非 Kernel 布局的 `mint gui` 可用 |
| [Mint TUI 证据包摘要](evidence-tui.md) | T50：C-01 部分通过、C-02 通过、C-03 部分通过；缺陷清单、哨兵扫描与仓外证据包路径 |
| [M1 独立评审](r1-review.md) | T53：M1 六项能力的复跑结果、FDE 两轮审核、真实 Agent 查询抽查 L1–L4、缺陷 D1/D2（转 S2）、T50 C-01/C-03 改判条件（§7.1）、已知限制与验收结论 |

实施后按任务和轮次增加修复、评审与验收记录，并登记实际工作区、版本、输入范围与产物引用。
