# DataAgent 外部调研 · 2026-10-31

研究顺序：竞品与应用现实 → 模块技术与语义层 → 跨行业扩展与合作 → AgentOS/Mint 兼容方向。数据、产品、benchmark 均未在本轮实际接入或运行。

| 文档 | 主要内容 |
| --- | --- |
| [00 · 综合报告](00-synthesis.md) | 当前现状、落地难点、八模块候选地图、通用/升级/新建部分、领域合作和建设判断 |
| [01 · 竞品与采用](01-competitors-and-adoption.md) | 十一个代表产品：Snowflake、Genie、Looker、Fabric、ThoughtSpot、Hex、Julius、ChatGPT、Quick BI、FineChatBI、dbt AI |
| [02 · 语义层与 ontology](02-semantic-layer-and-ontology.md) | dbt/MetricFlow、Cube、Wren、Apache Ossie、目录/对象模型、join/SCD/复合键、转换损失、版本与漂移 |
| [03 · 模块技术](03-module-technologies.md) | 八模块的外部库、代码机制、I/O、边界与评测；四条公开 issue |
| [04 · X 观点与案例](04-user-voices-and-cases.md) | X 原文/回复，LangChain/Hex、LinkedIn、Ramp，证据等级与应用需求 |
| [05 · dbt AI 补充](05-dbt-ai-addendum.md) | 修正产品覆盖缺口；Wizard/Explore、Copilot/Insights、MCP 的行为、状态、检索机制与凭据边界 |

与前轮的关系：复用 [2026-10-30 研究](../dataagent-2026-10-30/00-synthesis-and-recommendations.md)已经固定的开源/benchmark 资料；本轮重新研究商业产品、深化模块与语义技术，并增加用户观点及具名部署。前轮目录里存在其他汇编，不能据其标题推定本轮已复核其全部主张。

后续深化：[DataAgent 自适应检索专题](../dataagent-retrieval-2026-10-31/README.md)讨论固定 table→column→value 链的限制、值/列/规则等多入口、按证据选择下一步，以及产品、论文、源码中的具体实现。

模块规划草稿：[DataAgent 模块能力草案](../dataagent-2026-11-01/00-module-capability-draft.md)基于新的 Brainstorm 文档，规划狭义/广义 DataAgent 的一级和二级能力，并标出 AgentOS 复用边界。

源码、官方正文、访问失败、版本 pin 和部分 HTML 缓存保存在 [sources](sources/)。主要来源账本：

- [竞品来源及访问记录](sources/competitors-source-index.json)
- [dbt AI 增补来源](sources/dbt-ai-source-index.json)：八份官方文档正文及哈希、产品页浏览器笔记与 HTTP 失败记录。
- [语义来源及校验摘要](sources/semantics-source-manifest.json)、[固定版本](sources/semantics-version-pins.json)
- [模块代码读取记录](sources/modules-raw-manifest.json)、[Toolbox 固定代码记录](sources/modules-toolbox-selected-manifest.json)、[发现阶段/API 失败记录](sources/modules-code-manifest.json)、[公开 issue](sources/modules-issues-manifest.json)
- [X/案例读取笔记与出处](sources/users-source-notes.json)：动态页面主要由浏览器直接阅读，详情记录在 04；不声称拥有其全量原样离线副本。

证据原则：源码静态行为、官方文档、客户自述、厂商宣称、个人观点、研究建议分开；不把采用量当准确率，不把草案当稳定发布，不把查询执行成功当业务正确，不做无统一条件的排行榜。
