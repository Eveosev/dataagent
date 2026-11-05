# DataAgent 模块能力规划 · 2026-11-01

> 状态：过期。模块与原子能力以 [`../dataagent-2026-11-03/00-pluggable-dataagent.md`](../dataagent-2026-11-03/00-pluggable-dataagent.md) 与总 Catalog 为准；本目录仅作历史草案与调研依据。

本目录保存基于当前 DataAgent Brainstorm 的模块能力规划。飞书文档仍处于早期讨论阶段；这里的一级/二级能力拆分是调研与规划输入，不代表最终架构或已批准的产品范围。

当前讨论稿为 [02 · 原子能力简稿](02-atomic-capabilities-revised.md)：按数据层、执行应用层、评测和治理层整理，并增加“模块—能力组—具体能力”的三级拆分。三级拆分及血缘能力已同步飞书并回读核对（revision 508）。00/01 和对应 DOCX/XLSX 保留为历史草案与调研依据。

本地后续讨论将 DA06 泛化为“语义查询与计算计划”，与 DA07 组合支持 SQL、业务 API/MCP、函数和表达式计算。之后又补充了：第〇章共享对象；语义冷启动与冲突识别（DA03.9–10）；任务上下文与经验验证晋升（DA04.5–6）；澄清问题、文档信息抽取、持续改进度量、变更计划、配置调优与跨租户沉淀；广义扩展模块 DA13 数据建模与物化、DA14 持续运行与监控；以及“业务记忆与自进化”“插件、领域包与 Preset”两章。2026-11-01 已将原子能力定义（层次总表、DA01–DA14 能力表及 DA06/DA07/DA10 标题与简介）同步飞书并回读核对（revision 530）；第〇章共享对象、第四章汇总表、第五/六章及“对话纠正”等说明文字仅保留在本地。

| 文档 | 内容 |
| --- | --- |
| [00 · 模块能力草案](00-module-capability-draft.md) | 第一版草案：狭义 / 广义 DataAgent 的边界、12 个一级模块、72 个二级能力、AgentOS 复用边界 |
| [01 · 模块化能力拆分调研报告](01-module-capability-report.md) | 正式调研稿：15 个一级模块、92 项二级能力、30 项 P0、9 项核心自研、广义扩展/补充判定、路线图与验收门 |
| [01 · 报告 DOCX](01-module-capability-report.docx) | 同一报告的排版版本，便于评审与分发 |
| [01 · 能力矩阵 XLSX](01-module-capability-matrix.xlsx) | 92 项能力的可筛选矩阵（优先级/闸门/供给/验收/批次/护城河） |
| [02 · 原子能力简稿](02-atomic-capabilities-revised.md) | 三层、三级能力划分 + 广义扩展；共享对象、语义冷启动、任务记忆与自进化、插件/领域包/Preset 组织与伙伴接入路径 |

调研报告相对草案的主要变化（以下为 01 报告的编号，与 02 中的 DA13/DA14 含义不同）：

1. 新增 **DA13 运行态、成本与可观测**、**DA14 资产图与血缘** 两个横向契约模块；
2. 新增 **DA15 建模、转换与调度**，补上“无数据库时如何构建数据库”的缺位；
3. 补入 **DA06.7 认证查询库（VQ）**，并把 P0 收敛为 30 项、首批 21 项；
4. 把“广义”从功能清单改写为三次相变（资产化 / 写入 / 运行态），逐项判定扩展与补充。

来源：[当前 DataAgent Brainstorm](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)；参考：[Agent OS 应用组件整体规划](../../official/agent-os-application-components.md)。

本地 source cache：[Feishu 读取快照](sources/current-feishu-dataagent.md)，读取日期 2026-11-01，document revision 272。本轮六份补充调研备忘录与矩阵生成脚本见 [sources/appendix](sources/appendix/)。
