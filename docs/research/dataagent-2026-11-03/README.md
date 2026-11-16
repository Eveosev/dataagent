---
version: 1
date: 2026-11-11
status: 当前入口
---

# DataAgent 核心导读

DataAgent 将文件、数据库、API 和业务系统的观察映射到有版本的 Ontology。每个实例保留来源证据，用户可以核对原值、转换和映射范围。FDE Agent 在同一任务上发现业务动作，生成并验证工作流，保存实际回执并支持对账与恢复。

| 阅读入口 | 内容 |
| --- | --- |
| [总规划](00-pluggable-dataagent.md) | DataAgent 的范围、分层、能力目录和 FDE 扩展 |
| [共享契约](05-contracts.md) | 跨层类型、来源引用、调用封套和版本规则 |
| [当前落地方案](16-local-ingestion-workflow-build-plan.md) | 本地组件、Ontology 工作台、业务系统探查与执行 |
| [实施与验收记录](16-local-ingestion-workflow-build/README.md) | 当前进度、测试数据、验收场景和结果证据 |

## 当前交付路径

| 阶段 | 验收重点 |
| --- | --- |
| M1 文件接入 | 本地装包，从 Mint TUI／GUI 接入 PDF 和表格，查看证据、纠正映射、保存和复用 |
| M2 数据库与 API | 探查结构、键、样本和分页，将不同来源对齐到同一对象 |
| M3 API 工作流 | 在本地 OA／CRM 发现动作，生成并执行报销流程，验证回执、等待和恢复 |
| M4 Web Computer Use | 根据实际页面形成和修订步骤，组合 API 与 UI，验证未知结果对账和独立装包 |

每个阶段在安装后的组件上验收。MintHub 分发安排在本地功能验收之后。实现状态和实际通过范围见实施与验收记录。

## 按需查阅

- [Ontology 与交互设计](design/14-ontology-workbench-plan.md)及[映射交互细节](design/15-ontology-mapping-experience-plan.md)。
- [分层文档、飞书副本、组件方案与历史记录索引](archive/README.md)。
- [原子能力 Catalog](catalog/atomic-capability-catalog.json)。

## 生成与同步


```bash
python3 -I docs/research/dataagent-2026-11-03/tools/build.py                      # 快照 → 00–04 与 catalog/
python3 -I docs/research/dataagent-2026-11-03/tools/to_feishu.py                  # 05 → feishu/05-contracts.md
python3 -I docs/research/dataagent-2026-11-03/tools/sync_feishu.py prepare layers # 01–04 → feishu/ 片段与 plan.json
```

- `build.py`：精确匹配替换并断言次数；校验总规划 18 / 141 / 458、各层原子 165 / 126 / 73 / 94、原子一一对应且有 operation 与源码文件、S0 原子 51 项；正文不得含版本标签、指向本文档的链接或飞书标记。00–04 与 `catalog/` 为生成物，不手改。
- 版本只写在文首 frontmatter；飞书以文首 yaml 代码块表示。
- 总 Catalog 多维表格由 `catalog/atomic-capability-catalog.json` 写入（`catalog/feishu-base.json` 记录 base 与表）。
- 飞书有新修改时：先比对线上与本地，合并后再推送。
