---
doc_id: dataagent-fde-harness-review
title: 19 DataAgent 现状与 FDE Harness 选路
answers: 已有哪些可用资产，哪些仍在试验，FDE Harness 应在哪里建设，怎样验证这次分工
status: 现状已核对，立项建议待裁决
feishu_node: YTJXw46qjiNdMTkRWlrcNydnnhh
feishu_obj: GPH7dDxfRouxPoxqemIcX7PenPW
date: 2026-11-25
---
# 19 DataAgent 现状与 FDE Harness 选路

**多源数据接入是 FDE Harness 的验收目标之一。建议首轮在 DataAgent 原仓实现 Harness 入口，沿用现有接入代码、样例和验收标准。** 用户从熟悉的宿主发起委托。DataAgent 完成来源探查、映射、冲突核对与保存，Harness 把这些能力接进现场工作，并向经办人呈现需要判断的差异和可以核验的结果。

## 1. 当前究竟交了什么

11 月 25 日核对了 GitHub 主线、开发分支、本地工作树和已有评审。飞书中的项目阶段为 MVP 实施。开发交付视图当日有 94 行，其中 73 行标为已完成、2 行进行中、19 行未开始。其中 T53 就同时有 P1 全量任务和 M1 评审任务。产品验收应查对应目标和签署记录。下表的 M1 指 DataAgent 多源接入里程碑。Harness 草稿另设 M0–M3。[开发交付视图](https://modelbest.feishu.cn/wiki/FDIPwTuQci1FY7kiQ6GccbG8nDe?table=tbl3i9VGaRruX7b5&view=vewlcx9Npd)

| 资产与位置 | 目前能拿到什么 | 证据与边界 |
|---|---|---|
| DataAgent 主线 `67d3aabe` | 文件（含扫描 PDF、Word）、SQLite、分页 REST 接入。可核对跨源冲突、纠正映射、部分保存、复用已核映射，并完成本体发现、发布及查询的主路径 | 11 月 19 日独立评审结论为“可验收”。最终复跑覆盖 11 个包、5 个安装产物验收阶段。浏览器主路径 78 项通过，恢复路径 1 项通过，两处提交各连续跑两次，无重试后才通过的项目。P1 全量门槛、真人 TUI、GUI 指定场景、真实客户识别质量和多租户仍缺相应证据。见[独立评审](https://github.com/Eveosev/dataagent/blob/67d3aabebf0c17966e5edbcc9b77aa704dc25852/docs/research/dataagent-2026-11-03/16-local-ingestion-workflow-build/r1-review.md) §0、§2。 |
| 数据能力设计与评测 | 总目录有 18 个模块、141 个能力组、458 项原子能力。早期 S0 切片登记了 51 项，分布为数据 32、应用 13、治理 6。主线评测目录包含 B01–B17 的任务、样本账本、基线与工具 | 458 是规划规模。51 是该切片的注册数。[S0 阶段报告](https://github.com/Eveosev/dataagent/blob/67d3aabebf0c17966e5edbcc9b77aa704dc25852/docs/research/dataagent-2026-11-03/archive/11-s0-stage-report.md) 区分完整与部分实现。[评测趋势](https://github.com/Eveosev/dataagent/blob/67d3aabebf0c17966e5edbcc9b77aa704dc25852/docs/research/dataagent-2026-11-03/09-benchmark/monitor/trend.md) 的已记录轮次为 1/17 已评分、3/17 有基线。现有评测资产适合继续做回归。 |
| FDE Skill，GitHub `feat/fde-skill-npm@9fe92175`，本地同名分支 `15b4e30c` | 可安装到 Codex、Claude Code、ZCode、dsh。包含现场探查、工程交付与运维指引，制度原文核对、表格样本比较脚本，以及制度与门店示例 | 本次在本地提交复跑，安装器 10 项、Python 脚本 11 项通过。证明安装与辅助脚本的被测行为。跨宿主完成首单、客户授权下执行以及次单交接仍须场景验收。 |
| FDE 工程原型，本地 `feat/09-fde-architecture@18c91523`、`feat/09b-fde-tool-loop@c8606489` | 前者含能力发现、工作流编译、评估器和工作台；后者在其上增加工具调用循环和范围控制。可提取测试夹具、结果核对方法和失败样例 | 两者相对主线分别多 15、17 个提交，后者包含前者。其运行时、服务端和界面走独立产品路线。尚无这些分支与当前宿主 Skill 或新 Harness 整体通过验收的记录。 |
| FDE Harness 草稿，宿主的 `projects/fdeharness/` | 四份本地工作稿：产品需求、架构、UI 方案 A（离线 HTML，回答导出为文件）、UI 方案 B（临时本地工作台，回答直接写回）。PRD 以宿主内单一 Skill 为入口，CLI 与可选的标准输入输出工具服务（stdio MCP）共用核心 | 该目录尚未登记为子项目。四篇均为设计材料。PRD 提议用可重置 ERP 和一个客户授权沙箱验证报销辅助填报。A 符合草稿现行的无 HTTP 约定，B 要修改 D02。建议首单先用宿主对话，需要批量核对时再用 A。是否引入 B 由实际核对成本决定。 |

一次接入的证据可以逐步回查。评审样例把文件、SQLite 和 REST 送进同一流程，得到 10 个有业务键的对象和 3 个缺键候选。预览发现 4 个对象有冲突，阻止整批保存。选择部分保存后，6 个无问题对象落库，其余保留来源和待处理原因。再次导入结构相同的样本可复用已确认映射。这组结果是 Harness 验收多源接入时可直接沿用的数据侧证据。还需用同一批输入从宿主入口走一遍，核对经办人看到的冲突、保存结果及其来源。实现与验收入口见主线 `67d3aabe` 的 `scripts/acceptance/sources.py:509` 和独立评审 §3。

## 2. 已有材料如何查

| 想回答的问题 | 查哪里 | 如何使用 |
|---|---|---|
| 为什么立 DataAgent，P1、P2 到哪里 | [原始诉求](<附B 原始诉求.md>)、[分期路线](<05 分期路线与 MVP 范围.md>)、[PRD](<06 PRD.md>)、[实施清单](<07 MVP 实施文档.md>) | 00–08 是数据接入与平台工程文档集。P1 是多源接入，P2 是本体实现、打通与可视化，P3–P6 是后续路线。阶段、承诺和范围继续按原项目管理。 |
| 具体哪个包干什么 | 主线 `packages/capabilities/` 共 13 个目录 | `contracts/runtime` 提供契约与执行基础，`data/ocr` 处理数据与识别，`ontology/workbench` 提供本体与人工核对，`application/governance/operations` 承载应用、治理与受控动作，`cli/s0/intake` 提供入口和组合，`scenarios` 提供场景测试。名称均省略 `dataagent-`。 |
| 单轮请求、反问、交接如何工作 | 本地 `15b4e30c` 的 13–15、18 篇，以及 `docs/dataagent-盘点材料/FDE Agent 实施任务清单.md` | 13 是综合 PRD，14 是详细设计，15 是实施顺序，18 描述 11 种输入情境。09–10 保留早期路线和现场调研，11–12 是并列评审稿，16–17 与 HTML 原型保留交互设计依据。09–18 尚未进入此次核对的 GitHub 主线。 |
| 去哪找原始证据和旧版本 | [研究目录](https://github.com/Eveosev/dataagent/blob/67d3aabebf0c17966e5edbcc9b77aa704dc25852/docs/research/dataagent-2026-11-03/README.md)、[文档状态](https://github.com/Eveosev/dataagent/blob/67d3aabebf0c17966e5edbcc9b77aa704dc25852/docs/STATUS.md)、各篇同名评审目录 | 组件实施记录、生成工具、Catalog、benchmark 各有独立入口。历史设计和冻结快照保留原路径。当前工作区还有 B01–B15 的本地运行产物，正文引用汇总，原始样本和运行目录继续留在原处。 |
| 飞书上原来已有哪几篇 | [DataAgent 文档集](https://modelbest.feishu.cn/wiki/WCXwwJIatirPtXkCF8gcV7x9nme) | 更新前已核对线上首页、原始诉求及发布记录。00–08 保留原有页面。首页与附B 承接这次盘点和项目选路的原话。 |

FDE Skill 的入口、安装器与样例可按开发分支的固定提交查看。[Skill 源码与用例](https://github.com/Eveosev/dataagent/tree/9fe921750d71a2c311bcb6547f5822906041fa50/packages/capabilities/dataagent-fde)

## 3. 同一个验收目标，代码放在哪里

[原始诉求](<附B 原始诉求.md>)将 P1 定为多源接入，P2 定为本体的实现、打通和可视化。“先帮我办”和“我教你，以后替我办”说明了用户怎样在现场使用这些能力。例如，经办人让 Agent 接入一批资料，首先要看到哪些来源读进来了、哪里有冲突、哪些结果已经保存。若委托还包括后续办理，再核验写入、回读与交接。一个只要求接入的委托可以在数据结果核对后结束。

现有实现同时探索了数据工作台、自带对话循环的原型、宿主 Skill 三种入口。判断哪一项偏离目标，可以拿同一个冲突样例逐步核对：哪个入口能指出冲突来自哪份材料，让经办人作一次决定，最后返回正确的保存结果？若一项建设只增加一个界面或运行环节，现有验收仍能完整通过，先把它留在原型里。

| 路线 | 何时值得做 | 当前取舍 |
|---|---|---|
| A. 单列 FDE Harness 子项目 | 有独立维护人、发布节奏，或另一个业务场景已在复用同一套 Harness，且与 DataAgent 之间的输入输出已稳定 | 可单独维护产品路线，并以固定版本装配 DataAgent。跨仓发布需要额外维护版本配对和集成回归。 |
| B. 在 DataAgent 原仓推进 Harness（推荐首轮） | 首条需要贯通的链路就是多源接入，代码、样例及验收脚本已在同一仓 | 用现有 Skill 和数据能力跑同一个案例。接入缺陷修在数据包，宿主调用、业务澄清和结果交付放在 Harness 模块。两个模块可以在同一提交上联测。 |

产品上，Harness 包含多源接入及其他现场能力。工程上，目录归属和发布节奏可以独立决定。现阶段已经有明确的接入验收基线，跨仓版本管理的收益还缺少现场证据。因此先在原仓跑通，后续若独立交付的收益明确，再评估正式单列。立项以裁决清单为准。

## 4. 积木选择

| 处理方式 | 选择与基线 | 首次接入检查 |
|---|---|---|
| 沿用数据能力 | 以 DataAgent `67d3aabe` 的源码与安装产物为基线。仓内 `dataagent/preset-intake`、`dataagent/workbench`、`dataagent/data-layer`、`dataagent/operations` 清单版本均为 `0.1.0`。接入配方仍使用本地路径依赖 | 用两份样本经过既有入口，核对来源、映射冲突、纠正后结果和再次导入。首次试点按固定提交装配，包上架状态另行查询。 |
| 继承 Skill 和可重复检查 | 优先评估已推远端的 `9fe92175`。将 `fde-engineer` 作为入口候选，沿用 `policy_source.py` 原文定位与 `sample_check.py` 样本比对 | 在干净的首宿主安装，给出旧示范与新文件，请用户澄清一个会改变结果的条件，再用独立期望样本比较。首轮在原仓指定单一维护位置。 |
| 适配受控动作 | 主线已有动作网关、业务键回读、回执和中断恢复。现有授权模型与 Harness 草稿的逐次批准记录需要逐项映射 | 对同一动作分别模拟成功、结果未知、授权过期。结果未知时先回读；缺对应批准、无法核验或作用范围变更时交回用户。 |
| 从原型择取 | 对 `18c91523` 的评估器、编译产物和测试样例逐件比对。自带模型循环、浏览器工作台、服务端整套装配继续作为原型保留 | 每项候选先在宿主原生入口跑一个原型已有的失败用例；只迁能改善业务结果或故障定位的部分。 |
| 宿主及其他团队 | 11 月 25 日在线查到 `heizijian/ocr@0.1.0`（文档识别）和 `wujiahe/tool-connectors@0.4.8`（工具发现与回执）。已有 DataAgent OCR 和动作回读先服务首例，遇到覆盖缺口时再与包作者核对 | 上游已更新至 `agent-kernel@fab322f99dffec62428758f3d22c8272527bfe47`。工具契约见 `kernel/iface/src/tool.rs:150`。M1 的原评审基于 `ae6c3d5`，对新基线的运行兼容性待独立验证。 |

**代码取证位置**（路径相对 DataAgent 仓库）。主线 `67d3aabe` 下，`packages/capabilities/dataagent-intake/mint.toml:12` 列装配依赖，`packages/capabilities/dataagent-workbench/src/dataagent_workbench/ontology_discovery.py:317` 校验本体提案，`packages/capabilities/dataagent-operations/src/dataagent_operations/action_gateway.py:38` 处理动作，`packages/capabilities/dataagent-operations/src/dataagent_operations/reconciliation.py:33` 判定回读结果。Skill 分支 `9fe92175` 下，`packages/capabilities/dataagent-fde/skills/fde-engineer/scripts/policy_source.py:83` 核对证据，旁边的 `sample_check.py:55` 比较输出。原型 `18c91523` 的 `packages/capabilities/dataagent-fde/src/dataagent_fde/evaluator.py:102` 是评估器，`c8606489` 的同包 `harness/loop.py:256` 是独立对话循环。

## 5. 首轮怎样验

1. **先从宿主验多源接入。** 复用 M1 的文件、SQLite、分页 REST 样本和既有断言。经办人通过 Skill 发起接入，核对 4 个冲突对象及其来源，明确选择部分保存后，核对落库的 6 个对象和待处置项。再次导入时，检查已确认映射是否复用、未解决的缺口是否仍可见。把宿主结果与同一数据集走原入口的结果对照，记录首次出现差异的位置。原有 P1 全量验收仍按 [PRD](<06 PRD.md>) 执行。
2. **把扩展环节放进相应的委托。** 若委托还包括报销辅助填报，在可重置沙箱模拟“草稿已保存，回执丢失”，按业务键回读，目标系统应只有一条草稿。若委托还包括“以后替我办”，再换人、换材料，检查上次的处理步骤能否复用，哪些规则和批准需要重新确认。
3. **凭第二个场景判断是否拆项目。** 用门店日报等其他业务记录哪些宿主调用、澄清和交付步骤可以直接复用，哪些仍依赖 DataAgent 内部实现。以这份记录和实际的维护、发布需求复议项目归属。

## 待拍决策

| 编号 | 决策 | 选项 A | 选项 B | 推荐 | 影响 |
|---|---|---|---|---|---|
| Q1 | FDE 工作按哪个子项目交付 | 单列 FDE Harness 子项目，按版本装配 DataAgent | 首轮在 DataAgent 原仓推进，单独组织 Harness 模块 | B。先让宿主入口通过现有多源接入样例，再依据其他场景的复用情况与独立发布需求复议 | 两种组织方式共用多源接入验收标准。决策只影响维护归属和集成方式。 |
