---
doc_id: index
title: 广义 DataAgent 文档集
---
# 广义 DataAgent 文档集

> 状态：草稿 v0.3（2026-11-17；00–07 成套；各篇决策已拍：P1 不提 agent-kernel PR，其余按推荐）。
> 输入：[附B 原始诉求](<附B 原始诉求.md>)。
> 读法：先读 00 的统一词汇，再按编号顺序读；只想知道接下来做什么，直接读分期路线、PRD、MVP 实施文档。
> 本文档集以本地 Markdown 为源（docs/dataagent），用 bigproj publish 发布到飞书。

## 1. 文档清单

<!-- bigproj:doc-list begin -->
| 编号 | 文档 | 回答什么 | 状态 | 飞书 |
|---|---|---|---|---|
| 00 | 00 术语与总览 | 广义 DataAgent 是什么、统一词汇与编号、由哪几层组成、核心对象怎么流转、和 Mint / iface 怎么分工、核心与领域怎么分界 | 草稿 v0.4（整体设计；已与飞书总规划 r1147 比对；并入 Palantir、Genie 借鉴与 11-16 已拍事项；待拍 Q1–Q3） | [链接](https://modelbest.feishu.cn/wiki/OMWewQAaNi5inNklmnAcx2Panwh) |
| 01 | 01 多源接入与本体的 iface 依赖与分工 | 在 Mint 上完成多源接入和 ontology 接入，要哪些 iface 支持、还缺哪些功能、哪些归业务侧、哪些要核心包加机制 | 草稿 v0.2（读码梳理，未运行；缺口转为 PR 清单见 03 §8；待拍 Q1–Q3） | [链接](https://modelbest.feishu.cn/wiki/XMMywweq2i7ioGkxSqicDclTnyd) |
| 02 | 02 借鉴 Palantir Ontology 与 Databricks Genie | Palantir 和 Databricks 怎么用本体、定义、技能、目录把「自然语言问数」做可信；DataAgent 照着改什么、落在哪一期 | 草稿 v0.3（调研；外部资料 2026-11-16 访问，已独立复核；待拍事项已并入 05、06） | [链接](https://modelbest.feishu.cn/wiki/HshywkjmEiCv9vkEs1Dcr4lOnRh) |
| 03 | 03 平台方案与 iface 共建 | 现有实现怎么按 iface 族重组（平台层）；我们怎么参与完善 iface（PR 清单与规矩）；分几步做、每步怎么验收 | 草稿 v0.2（设计；并入 11-16 已拍「我们承担完善 iface 职责」；未实施；待拍 Q1–Q6） | [链接](https://modelbest.feishu.cn/wiki/Ld3jwNrhDiHOiNkr90xcBl2NnHg) |
| 04 | 04 验收方法与数据 | 真实业务数据拿不到、审核场景没有对错真值时，怎么验收；用哪些数据；怎么防止方案过拟合到令才 | 草稿 v0.1（设计；依据 11-16 已拍事项与令才 Computer Use 数据集评估；待拍 Q1–Q2） | [链接](https://modelbest.feishu.cn/wiki/EZH9wwCYYi97A0kA78ncHpiZnTc) |
| 05 | 05 分期路线与 MVP 范围 | P1 到 P6 各交付什么；一期（MVP）做什么不做什么；用哪些用例验收 | 草稿 v0.1（P1、P2 日期为承诺，P3 起为估计；待拍 Q1–Q4） | [链接](https://modelbest.feishu.cn/wiki/OLZ5wCEEki24Y1kwRTHcqT1lnMg) |
| 06 | 06 PRD | P1（多源数据接入）与 P2（本体的实现、打通、可视化）改什么、为什么改；每个目标怎么验收 | 草稿 v0.1（P1、P2 细到验收命令；P3–P6 见 05；待拍 Q1–Q11） | [链接](https://modelbest.feishu.cn/wiki/SXeGwwK9Zi9VyzkpHYycsPcMnUc) |
| 07 | 07 MVP 实施文档 | P1（多源数据接入）的任务清单：每个任务改哪些文件、跑什么命令、怎么验收、怎么回滚，谁来做 | 草稿 v0.2（37 张任务卡，W1–W2；已按独立复核修正命令、范围与依赖；crew 调用方式待 payne 提供后补进 §0.4） | [链接](https://modelbest.feishu.cn/wiki/QkPrw4kegiVZdZkHtJHcLIEinVg) |
| 附B | 附B 原始诉求 | 提需求时的原话 | 已有 | [链接](https://modelbest.feishu.cn/wiki/TsWkwjM5HiESY9k5oeocbqmrnff) |
<!-- bigproj:doc-list end -->

## 2. 诉求 → 产出对照

| 原始诉求 | 落在 |
|---|---|
| 2026-11-16：把 DataAgent 放进 agentcpm-os，依托 agent-kernel（iface、Mint） | 平台依赖文档集《01 架构与依赖》；本集 [00 术语与总览](<00 术语与总览.md>) |
| 2026-11-16：在 AgentCPM / Mint 下完成多源接入和 ontology 接入，要哪些 iface 支持、还缺哪些功能、业务侧与核心包怎么分 | [01 多源接入与本体的 iface 依赖与分工](<01 多源接入与本体的 iface 依赖与分工.md>) |
| 2026-11-16：当前实现都按 iface 包重构，给方案；iface 由我们参与完善、提 PR | [03 平台方案与 iface 共建](<03 平台方案与 iface 共建.md>) |
| 2026-11-16：参照之前的全局设计，给整体设计 | [00 术语与总览](<00 术语与总览.md>) |
| 2026-11-16：结合 Palantir Ontology 与 Databricks Genie 的 NL2SQL 设计做借鉴 | [02 借鉴 Palantir Ontology 与 Databricks Genie](<02 借鉴 Palantir Ontology 与 Databricks Genie.md>)；落到 00 §5、§6，05 的 P3、P4，06 的 P2 |
| 2026-11-16：防止过拟合到令才；真实数据拿不到、没有真值时怎么验收 | [04 验收方法与数据](<04 验收方法与数据.md>)；00 §12 |
| 2026-11-16：完整 PRD；P1 验收多源数据接入，P2 本体的实现、打通和可视化，其他阶段丰富（附B 原话里的「03 的 P1」指当时的旧编号，现为 05、06） | [05 分期路线与 MVP 范围](<05 分期路线与 MVP 范围.md>)、[06 PRD](<06 PRD.md>) |
| 2026-11-16：标准的 PRD、设计方案、任务清单维护在飞书；任务由本地 crew 执行 | [07 MVP 实施文档](<07 MVP 实施文档.md>)；飞书工作表「功能拆解」、开发看板「开发交付」「发版里程碑」 |

## 3. 盘点材料（不发布到飞书）

调研摘录、脚本、决策副本放在同级目录 dataagent-盘点材料/；正文里的「出处」可以指向它。

## 4. 给 AI 任务的执行入口

1. 先读本文件与 00，再读 PRD 与 MVP 实施文档。
2. 代码事实以 <仓库>@<分支>@<提交号> 为准；接手时先 fetch，核对提交号和行号有没有漂移。
3. 与规范或已拍的裁决冲突时，以规范和裁决为准，并提醒用户。
4. 决策只认裁决清单：https://modelbest.feishu.cn/wiki/Ah8MwzzwliTB8FkWXUlcHiwVnpd?table=tbl6DLj1IhjkG5qY
5. 有评论的篇不要整篇重发。
