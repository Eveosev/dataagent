---
doc_id: dataagent-fde-harness-review
title: 19 DataAgent 现状与 FDE Harness 选路
answers: 已有哪些可用资产，哪些仍在试验，FDE Harness 应在哪里建设，怎样验证这次分工
status: 现状已核对，立项建议待裁决
date: 2026-11-25
---
# 19 DataAgent 现状与 FDE Harness 选路

**建议把 FDE Harness 单列为交付产品，把 DataAgent 作为随产品提供、按需调用的第一套数据能力。** DataAgent 的多源接入、本体映射与查询继续在原仓维护。Harness 接受“帮我办一件事”或“照这个示范以后替我办”的委托，负责问清会改变结果的业务条件、调用能力、交付可核验的结果，并让下一位经办人接得住。

## 1. 当前究竟交了什么

11 月 25 日核对了 GitHub 主线、开发分支、本地工作树和已有评审。下面的 M1 专指 **DataAgent 多源接入里程碑**。Harness 草稿中的 M0–M3 是另一组里程碑。

| 资产与位置 | 目前能拿到什么 | 证据与边界 |
|---|---|---|
| DataAgent 主线 `67d3aabe` | 文件（含扫描 PDF、Word）、SQLite、分页 REST 接入。可核对跨源冲突、纠正映射、部分保存、复用已核映射，并完成本体发现、发布及查询的主路径 | 11 月 19 日独立评审结论为“可验收”。最终复跑覆盖 11 个包、5 个安装产物验收阶段。浏览器主路径 78 项通过，恢复路径 1 项通过，两处提交各连续跑两次，无重试后才通过的项目。P1 全量门槛、真人 TUI、GUI 指定场景、真实客户识别质量和多租户仍缺相应证据。见[独立评审](../research/dataagent-2026-11-03/16-local-ingestion-workflow-build/r1-review.md) §0、§2。 |
| 数据能力设计与评测 | 总目录有 18 个模块、141 个能力组、458 项原子能力。早期 S0 切片登记了 51 项，分布为数据 32、应用 13、治理 6。主线评测目录包含 B01–B17 的任务、样本账本、基线与工具 | 458 是规划规模。51 是该切片的注册数。[S0 阶段报告](../research/dataagent-2026-11-03/archive/11-s0-stage-report.md) 区分完整与部分实现。[评测趋势](../research/dataagent-2026-11-03/09-benchmark/monitor/trend.md) 的已记录轮次为 1/17 已评分、3/17 有基线。现有评测资产适合继续做回归。 |
| FDE Skill，GitHub `feat/fde-skill-npm@9fe92175`，本地同名分支 `15b4e30c` | 可安装到 Codex、Claude Code、ZCode、dsh。包含现场探查、工程交付与运维指引，制度原文核对、表格样本比较脚本，以及制度与门店示例 | 本次在本地提交复跑，安装器 10 项、Python 脚本 11 项通过。证明安装与辅助脚本的被测行为。跨宿主完成首单、客户授权下执行以及次单交接仍须场景验收。 |
| FDE 工程原型，本地 `feat/09-fde-architecture@18c91523`、`feat/09b-fde-tool-loop@c8606489` | 前者含能力发现、工作流编译、评估器和工作台；后者在其上增加工具调用循环和范围控制。可提取测试夹具、结果核对方法和失败样例 | 两者相对主线分别多 15、17 个提交，后者包含前者。其运行时、服务端和界面走独立产品路线。尚无这些分支与当前宿主 Skill 或新 Harness 整体通过验收的记录。 |
| FDE Harness 草稿，宿主的 `projects/fdeharness/` | 已有产品需求与架构设计两篇。定义了单一 Skill、等价 CLI 与可选 stdio MCP、按阶段取证，以及探查、沙箱交付、再次复用三段能力 | 该目录当前只有两篇 Markdown，workspace 的项目登记里还没有它。草稿标明技术选型待试点、未做 POC。报销辅助填报是首期试点，两轨分别为可重置 ERP 和客户授权沙箱。 |

## 2. 已有材料如何查

| 想回答的问题 | 查哪里 | 如何使用 |
|---|---|---|
| 为什么立 DataAgent，P1、P2 到哪里 | [原始诉求](<附B 原始诉求.md>)、[分期路线](<05 分期路线与 MVP 范围.md>)、[PRD](<06 PRD.md>)、[实施清单](<07 MVP 实施文档.md>) | 00–08 是数据接入与平台工程文档集。P1 是多源接入，P2 是本体实现、打通与可视化，P3–P6 是后续路线。阶段、承诺和范围继续按原项目管理。 |
| 具体哪个包干什么 | 主线 `packages/capabilities/` 共 13 个目录 | `contracts/runtime` 提供契约与执行基础，`data/ocr` 处理数据与识别，`ontology/workbench` 提供本体与人工核对，`application/governance/operations` 承载应用、治理与受控动作，`cli/s0/intake` 提供入口和组合，`scenarios` 提供场景测试。名称均省略 `dataagent-`。 |
| 单轮请求、反问、交接如何工作 | 本地 `15b4e30c` 的 13–15、18 篇，以及 `docs/dataagent-盘点材料/FDE Agent 实施任务清单.md` | 13 是综合 PRD，14 是详细设计，15 是实施顺序，18 描述 11 种输入情境。09–10 保留早期路线和现场调研，11–12 是并列评审稿，16–17 与 HTML 原型保留交互设计依据。09–18 尚未进入此次核对的 GitHub 主线。 |
| 去哪找原始证据和旧版本 | [研究目录](../research/dataagent-2026-11-03/README.md)、[文档状态](../STATUS.md)、各篇同名评审目录 | 组件实施记录、生成工具、Catalog、benchmark 各有独立入口。历史设计和冻结快照保留原路径。当前工作区还有 B01–B15 的本地运行产物，正文引用汇总，原始样本和运行目录继续留在原处。 |
| 飞书上原来已有哪几篇 | [DataAgent 文档集](https://modelbest.feishu.cn/wiki/WCXwwJIatirPtXkCF8gcV7x9nme) | 仓内发布台账记录了首页、附B、00–08。台账上最后一次首页发布时间为 11 月 19 日。这是上次发布记录，线上后续编辑及评论以发布前对账为准。 |

飞书读者可在固定提交直接查看[独立评审原文](https://github.com/Eveosev/dataagent/blob/67d3aabebf0c17966e5edbcc9b77aa704dc25852/docs/research/dataagent-2026-11-03/16-local-ingestion-workflow-build/r1-review.md)、[评测趋势原表](https://github.com/Eveosev/dataagent/blob/67d3aabebf0c17966e5edbcc9b77aa704dc25852/docs/research/dataagent-2026-11-03/09-benchmark/monitor/trend.md)与[已推送的 FDE Skill](https://github.com/Eveosev/dataagent/tree/9fe921750d71a2c311bcb6547f5822906041fa50/packages/capabilities/dataagent-fde)。

## 3. 为什么要单列 FDE Harness

DataAgent 的验收对象是一份数据结果。比如两张表接入后，经办人能找到同一个门店、核对冲突、纠正映射，下次导入还能复用。FDE Harness 的验收对象是一项可接手的工作。比如业务专家教过一次报销草稿怎么填，换一个人和一份新材料后，系统能辨别规则是否仍适用，获准后保存一次草稿，回到目标系统核对，再把结果交给经办人。第一组能力可以支撑第二组中的若干步；即使数据映射全部正确，交接、批准和恢复仍可能失败。

| 路线 | 获得什么 | 要承担什么 |
|---|---|---|
| 在 DataAgent 原仓延伸 | 复用数据工具和测试最快，若近期唯一目标是把问数或接入做好，这是成本最低的选择 | 目前同一仓已经容纳数据工作台、自带对话循环的 FDE 原型、宿主原生 Skill 三种入口。项目若继续共用一个里程碑，数据测试通过后仍很难回答“这件现场工作交给别人能否复办”。 |
| 单列 Harness，固定版本引用 DataAgent（推荐） | 两个项目可以独立验收。数据密集型任务直接使用已有工具，文件、页面或 API 主导的任务也可走同一交付流程 | 需要维护一层适配，写清输入、结果、证据、错误和支持版本。两个项目每次升级都要跑同一个跨项目样例。首期只维护首场景实际用到的接口。 |

“包含 DataAgent”落实为产品装配和调用关系。用户从同一个 Harness 入口委托工作；数据任务由 Harness 路由到固定版本的 DataAgent；已有 DataAgent 用户仍可直接使用其原入口。领域实现与缺陷在 DataAgent 修复，Harness 持有交付记录、范围、批准与复用条件。若一个宿主原生只读任务可以直接交付，流程可以只使用宿主。

## 4. 积木选择

| 处理方式 | 选择与基线 | 首次接入检查 |
|---|---|---|
| 沿用数据能力 | 以 DataAgent `67d3aabe` 的源码与安装产物为基线。仓内 `dataagent/preset-intake`、`dataagent/workbench`、`dataagent/data-layer`、`dataagent/operations` 清单版本均为 `0.1.0`。接入配方仍使用本地路径依赖 | 用两份样本经过既有入口，核对来源、映射冲突、纠正后结果和再次导入。首次试点按固定提交装配，包上架状态另行查询。 |
| 继承 Skill 和可重复检查 | 优先评估已推远端的 `9fe92175`。将 `fde-engineer` 作为入口候选，沿用 `policy_source.py` 原文定位与 `sample_check.py` 样本比对 | 在干净的首宿主安装，给出旧示范与新文件，请用户澄清一个会改变结果的条件，再用独立期望样本比较。迁入后指定单一维护位置。 |
| 适配受控动作 | 主线已有动作网关、业务键回读、回执和中断恢复。现有授权模型与 Harness 草稿的逐次批准记录需要逐项映射 | 对同一动作分别模拟成功、结果未知、授权过期。结果未知时先回读；缺对应批准、无法核验或作用范围变更时交回用户。 |
| 从原型择取 | 对 `18c91523` 的评估器、编译产物和测试样例逐件比对。自带模型循环、浏览器工作台、服务端整套装配继续作为原型保留 | 每项候选先在宿主原生入口跑一个原型已有的失败用例；只迁能改善业务结果或故障定位的部分。 |
| 宿主及其他团队 | 会话、模型与交互沿用选定宿主；积木盘点参照平台 11 月 20 日快照。OCR 重合候选为 `heizijian/ocr@0.1.0`，已有 OCR 足以跑首样时不引入第二套 | 本次未能在线刷新 MintHub 与上游 agent-kernel，未作新的 iface 兼容性结论或平台版本承诺。新增依赖前再核对在线版本、权限和适配结果。 |

**代码取证位置**（路径相对 DataAgent 仓库）。主线 `67d3aabe` 下，`packages/capabilities/dataagent-intake/mint.toml:12` 列装配依赖，`packages/capabilities/dataagent-workbench/src/dataagent_workbench/ontology_discovery.py:317` 校验本体提案，`packages/capabilities/dataagent-operations/src/dataagent_operations/action_gateway.py:38` 处理动作，`packages/capabilities/dataagent-operations/src/dataagent_operations/reconciliation.py:33` 判定回读结果。Skill 分支 `9fe92175` 下，`packages/capabilities/dataagent-fde/skills/fde-engineer/scripts/policy_source.py:83` 核对证据，旁边的 `sample_check.py:55` 比较输出。原型 `18c91523` 的 `packages/capabilities/dataagent-fde/src/dataagent_fde/evaluator.py:102` 是评估器，`c8606489` 的同包 `harness/loop.py:256` 是独立对话循环。

## 5. 怎样判断这次分工有价值

1. **先交一份可核对的结果。** 以草稿已有的报销辅助填报为首例，给宿主旧示范、两版规则和一张新单据。先用宿主原生方式做一次，再用 Harness 做同一任务。输出草稿、所用版本、逐项来源和需要经办人决定的例外。记录完成用时、人工往返和返工次数。先做安全的本地样例，再进入草稿定义的双轨沙箱。
2. **用一个失败验证维护边界。** 在可重置沙箱中模拟“草稿已保存，回执丢失”。Harness 留下待核验事项，DataAgent 动作适配器按业务键回读。预期目标系统只有一条草稿，批准与目标匹配，重试没有重复写入。客户沙箱和业务、工程两方签署分别留证。
3. **换人再办一单。** 下一位经办人在新会话拿到新材料，复用上次确认过的步骤；旧批准失效，遇到规则或环境变化能停在具体差异处。比较第二单新增探查、重复提问与人工修订。再用分支自带的门店日报作为第二领域对照，只复用交付流程和证据检查。
4. **再决定扩多少。** 首单失败能定位到数据接入、宿主执行或交付规则中的一处，次单复用效益有记录，再增加第二宿主或连接器。DataAgent 继续按自己的 P1/P2 验收；两边只为同一跨项目样例共同负责。

## 待拍决策

| 编号 | 决策 | 选项 | 推荐 | 影响 |
|---|---|---|---|---|
| Q1 | FDE 工作按哪个子项目交付 | A. 单列 FDE Harness，按版本包含 DataAgent 能力；B. 在 DataAgent 仓继续建设 | A。先复用既有两篇草稿、Skill 入口和数据工具，以报销首单及换人复办验证边界 | 拍板后确定项目登记、仓库及依赖归属、两边的验收责任。正式状态以项目裁决清单为准。 |
