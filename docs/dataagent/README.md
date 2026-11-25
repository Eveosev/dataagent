---
doc_id: index
title: 广义 DataAgent 文档集
---
# 广义 DataAgent 文档集

11 月 25 日盘点：[DataAgent 现状与 FDE Harness 选路](19-DataAgent现状与FDE-Harness选路.md)。查主线已交付范围、FDE 分支、复用边界和待裁决的项目归属，从这篇进入。

> 当前阶段为 MVP 实施。00–08 记录数据接入与平台工程。多源接入 M1 已获独立评审「可验收」结论。多源接入是 FDE Harness 的验收目标之一，P1 全量验收按原 PRD 跟踪。
> 输入：[附B 原始诉求](<附B 原始诉求.md>)。
> 读法：先读 00 的统一词汇，再按编号顺序读；只想知道接下来做什么，直接读分期路线、PRD、MVP 实施文档。
> 本文档集以本地 Markdown 为源（docs/dataagent），用 bigproj publish 发布到飞书。

## 1. 文档清单

<!-- bigproj:doc-list begin -->
| 编号 | 文档 | 回答什么 | 状态 | 飞书 |
|---|---|---|---|---|
| 00 | 00 术语与总览 | 广义 DataAgent 是什么、统一词汇与编号、由哪几层组成、核心对象怎么流转、和 Mint / iface 怎么分工、核心与领域怎么分界 | 草稿 v0.5（整体设计；已与飞书总规划 r1147 比对；并入 Palantir、Genie 借鉴与 11-16、11-17 已拍事项） | [链接](https://modelbest.feishu.cn/wiki/OMWewQAaNi5inNklmnAcx2Panwh) |
| 01 | 01 多源接入与本体的 iface 依赖与分工 | 在 Mint 上完成多源接入和 ontology 接入，要哪些 iface 支持、还缺哪些功能、哪些归业务侧、哪些要核心包加机制 | 草稿 v0.4（读码梳理，未运行；缺口转为 PR 设计见 03 §8，P1 不提；11-17 决策已拍；11-18 按 agent-kernel@ae6c3d5 更新 §6 的 B3、B7、B8，完整缺口与贡献清单见 08） | [链接](https://modelbest.feishu.cn/wiki/XMMywweq2i7ioGkxSqicDclTnyd) |
| 02 | 02 借鉴 Palantir Ontology 与 Databricks Genie | Palantir 和 Databricks 怎么用本体、定义、技能、目录把「自然语言问数」做可信；DataAgent 照着改什么、落在哪一期 | 草稿 v0.3（调研；外部资料 2026-11-16 访问，已独立复核；待拍事项已并入 05、06，11-17 已按推荐拍板） | [链接](https://modelbest.feishu.cn/wiki/HshywkjmEiCv9vkEs1Dcr4lOnRh) |
| 03 | 03 平台方案与 iface 共建 | 现有实现怎么按 iface 族重组（平台层）；我们怎么参与完善 iface（PR 清单与规矩）；分几步做、每步怎么验收 | 草稿 v0.4（设计；并入 11-16 已拍「我们承担完善 iface 职责」与 11-17 已拍「P1 不提 agent-kernel PR」；11-18 按 agent-kernel@ae6c3d5 改写 §8.3 的 PR-7、PR-8，补后台结果推回会话的设计摘要；未实施） | [链接](https://modelbest.feishu.cn/wiki/Ld3jwNrhDiHOiNkr90xcBl2NnHg) |
| 04 | 04 验收方法与数据 | 真实业务数据拿不到、审核场景没有对错真值时，怎么验收；用哪些数据；怎么防止方案过拟合到令才 | 草稿 v0.2（设计；依据 11-16 已拍事项与令才 Computer Use 数据集评估；11-17 决策已拍） | [链接](https://modelbest.feishu.cn/wiki/EZH9wwCYYi97A0kA78ncHpiZnTc) |
| 05 | 05 分期路线与 MVP 范围 | P1 到 P6 各交付什么；一期（MVP）做什么不做什么；用哪些用例验收 | 草稿 v0.2（P1、P2 日期为承诺，P3 起为估计；11-17 决策已拍：P1 不提 agent-kernel PR） | [链接](https://modelbest.feishu.cn/wiki/OLZ5wCEEki24Y1kwRTHcqT1lnMg) |
| 06 | 06 PRD | P1（多源数据接入）与 P2（本体的实现、打通、可视化）改什么、为什么改；每个目标怎么验收 | 草稿 v0.2（P1、P2 细到验收命令；P3–P6 见 05；11-17 决策已拍：P1 不提 agent-kernel PR；PostgreSQL 移出 P1 验收（Q12）；其余按推荐） | [链接](https://modelbest.feishu.cn/wiki/SXeGwwK9Zi9VyzkpHYycsPcMnUc) |
| 07 | 07 MVP 实施文档 | P1（多源数据接入）的任务清单：每个任务改哪些文件、跑什么命令、怎么验收、怎么回滚，谁来做 | 草稿 v0.5（11-18 最小 MVP 调整：M1 单独里程碑，16 张卡暂缓，新增 T11c、T26、T26b，共 40 张任务卡；11-17 已拍：P1 不提 agent-kernel PR，T40–T43 暂缓；执行方为 Mac 上的 Claude Code + crew，payne 只做确认、凭据、真人环节与验收签字） | [链接](https://modelbest.feishu.cn/wiki/QkPrw4kegiVZdZkHtJHcLIEinVg) |
| 08 | 08 iface 协议缺口与贡献 | DataAgent 用到的 iface 协议哪里不够；哪些我们可以贡献、贡献什么、找谁 | 草稿 v0.1（2026-11-18；条目以飞书「iface 贡献清单」表为准） | [链接](https://modelbest.feishu.cn/wiki/RW30wDtqsi8WM0ksq1Wc3hG8nuf) |
| 19 | 19 DataAgent 现状与 FDE Harness 选路 | 已有哪些可用资产，哪些仍在试验，FDE Harness 应在哪里建设，怎样验证这次分工 | 现状已核对，立项建议待裁决 | [链接](https://modelbest.feishu.cn/wiki/YTJXw46qjiNdMTkRWlrcNydnnhh) |
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
