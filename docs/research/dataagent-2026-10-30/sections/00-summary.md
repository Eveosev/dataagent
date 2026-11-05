# DataAgent 调研与 MintHub 落地方案

**日期**：2026-10-30　**时区**：Asia/Shanghai　**状态**：调研完成，方案待评审；未实施、未发布
**范围**：市场/竞品/开源/benchmark/标准/中国市场，以及"DataAgent 作为 MintHub bundle / preset / app"的产品与工程方案
**证据**：7 个并行子 Agent 分工调研 + 主 Agent 交叉核对；所有关键事实附来源链接，无法核实的显式标注

---

## 1. 一页结论

**市场已经给出答案：Data Agent 的竞争，不在"能不能写对 SQL"，而在"有没有一套可维护的语义资产 + 能不能把模糊问题问清楚 + 交付物能不能被信任"。**

十条结论：

1. **单轮 NL2SQL 已商品化。** BIRD Test 榜首 83.40%（AT&T AskData，2026-10-22），人类 Test 基准 72.37%（Dev 92.96%）；华为 82.39、腾讯 82.28、京东（4B 模型）76.19。Test 上机器已越过人类平均线，靠的不是更大的模型，是"更多候选 + 更好的选择器 + schema 压缩"。
2. **真正的差距在交互与企业系统能力。** BIRD-Interact（ICLR 2026 Oral）600 个交互式任务，SOTA 16.33%；Spider 2.0-Snow 同一 547 题，Spider-Agent+o1-preview 23.58%、Genloop Sentinel v2 Pro 96.70%——4 倍差距来自 scaffold（元数据检索、方言、长上下文、执行反馈），不是基座模型。**分数不可跨 harness 比较。**
3. **商业产品收敛到四种形态**：语义层优先（Snowflake/dbt/AtScale/Cube）、catalog + 生成式（Databricks Genie/Fabric/BigQuery）、BI 内嵌 Copilot（Power BI/Spotter/Sigma）、Ontology 平台（Palantir）。赢家是 **A+B 混合**：语义层兜住"必须对"，生成式兜住长尾，再用反馈把长尾沉淀回语义层。
4. **语义层正在从"BI 的内部配置"变成"可分发的一等资产"。** Snowflake 的 Semantic View 是 schema 级对象、可当 listing 共享；Palantir 有 ontology 分支 + 提案评审；dbt 的指标即代码。**这正是 MintHub 的机会：把 ontology 做成可版本化、可评审、可安装的包。**
5. **开源能覆盖约八成工作量，但三个关键件没有现成实现**：产品级 join/关系发现、语义层 diff→影响面→召回重排、开源 RLS DSL。这三个必须自研，也正好是差异化所在。
6. **标准用 Apache Ossie，不要自造。** OSI 已更名 Apache Ossie（2026-06 进 ASF 孵化），0.1.1 已被 dbt 1.12 原生解析；0.2.0.dev0 新增 ontology + mapping。**锁 0.1.1 落盘、按 0.2.0 语义思考**，否则 dbt 互通立刻断。
7. **中国市场的最锋利空档：文件即席分析 → 一键升格为受治理指标。** 所有厂商都把 Excel 当"又一个 connector"，没人把文件里的临时口径沉淀回指标层。这同时命中"口径治理"与"Excel 文化"两个中国特有痛点。
8. **MintHub 形态：`bundle`（能力入口，含 `.mcp.json` + Skill + 资产）+ `preset`（精确锁组合），后期再上 `app`。** `plugin` 要求 wasm/native/js，装不下常驻进程；`kind=mcp` 今天内核零消费。三条硬约束：**工具命名即权限**（`get_/list_/search_` 自动放行）、**MCP 单请求 60s 超时**（必须 job 化）、**升级不迁用户数据**（迁移自己实现）。
9. **产品架构一句话：一个 ontology，两个物理适配器（DuckDB 处理文件 / MCP 连接企业库），三层上下文（画像 → 候选 ≤30 列 → M-Schema 子集），澄清做成显式协议。**
10. **最大风险不是技术，是 ontology 维护成本与准确率预期管理。** 客户会拿 BIRD 83% 要求"什么都答"；能不能把"域内 80%+、域外拒答/澄清"的边界说清楚，决定产品生死。

### 如果只做三件事

| # | 做什么 | 为什么是它 |
|---|---|---|
| 1 | **文件问数闭环**（上传 → 探查 → ontology 草案 → 问数 → 导出） | 最快验证、最少依赖、覆盖中国客户"先文件后库"的真实路径 |
| 2 | **ontology 版本化 + 评测 harness** | 没有这两样，准确率无法回归、口径无法治理，产品会停在 demo |
| 3 | **`bundle` + `preset` 打包，`get_/list_/search_` 工具面** | 决定能不能被安装、被信任、被别的 Agent 复用；也是 MintHub 的入场券 |

### 现在 / 未来 一览

| 阶段 | 时间 | 关键词 | 成功标准 |
|---|---|---|---|
| 现在 | 0–3 月 | 文件 + Postgres、30 题评测、3 家设计伙伴 | 文件 30 题 ≥80%，库 50 题 ≥70% |
| 下一步 | 3–9 月 | join 发现、语义 diff、8 个连接器、RLS、3 个行业包 | 100 表库可用，2 个付费 POC |
| 未来 | 9–18 月 | 跨源 ontology、行业市场、主动分析、Agent 间调用 | 1000 表库、300 题回归、app GA + 3 行业包 |

---

## 2. 研究范围、方法与证据等级

### 2.1 怎么做的

7 个并行子 Agent，各自负责一个面，主 Agent 做交叉核对与综合：

| 子 Agent | 负责 | 产出 |
|---|---|---|
| A | 商业厂商（Databricks/Snowflake/Microsoft/Google/ThoughtSpot/Tableau/Qlik/AWS/Palantir/AtScale/Cube/dbt/Kyligence/Sigma/Dataiku） | [A-commercial.md](parts/A-commercial.md) |
| B | 开源代码（WrenAI/DB-GPT/Cube/MetricFlow/SuperSonic/Vanna/MCP 生态/剖析/表格） | [B-opensource.md](parts/B-opensource.md) |
| C | Benchmark（BIRD/Spider 2.0/BIRD-Interact/LiveSQLBench/DABench 等） | [C-benchmarks.md](parts/C-benchmarks.md) |
| D | 学术前沿（CHESS/CHASE-SQL/Alpha-SQL/ReFoRCE/LinkAlign/SemJoin/Uber-Join/DSABench） | [D-academic.md](parts/D-academic.md) |
| E | 标准与接入（Apache Ossie/MCP 2026-07-28/dbt/Cube/Palantir/OpenLineage） | [E-standards-connectors.md](parts/E-standards-connectors.md) |
| F | 中国市场（Quick BI/FineBI/SmartBI/Kyligence/观远/国产库） | [F-china-market.md](parts/F-china-market.md) |
| G | MintHub/Kernel 能力边界（源码级） | [G-kernel-packaging.md](parts/G-kernel-packaging.md) |
| H | Ontology 载体草案（主 Agent） | [H-ontology-schema-draft.md](parts/H-ontology-schema-draft.md) |

### 2.2 证据等级

| 等级 | 含义 | 本文用法 |
|---|---|---|
| L1 | 一手规范/源码/官方文档（可复查） | 直接引用，附路径或链接 |
| L2 | 官方榜单/论文自报 | 引用但标注"自报/官方"；不同口径不混用 |
| L3 | 厂商宣称、媒体转述 | 标"宣称"，不单独作为决策依据 |
| L4 | 未核实 | 显式写"未核实"，不做推断 |

### 2.3 本次调研的局限（必须知道）

1. **本机 web_search 不可用**（无 API key），所有检索靠 `web_fetch` / `curl` / GitHub API / arXiv API 直取。搜索引擎类站点（Bing/DuckDuckGo/Google）不可达，因此**可能遗漏没有直接 URL 的新闻与评测**。
2. **部分国内站点 JS 渲染或超时**（瓴羊、火山 DataWind、华为 DataArts、百度 Sugar、数势），其产品细节标"未核实"。
3. **厂商版本与文档在快速变化**：Snowflake Intelligence 已更名 CoWork、Genie Spaces 已更名 Genie Agents、QuickSight 已更名 Quick；本文以 2026-10-30 抓取为准。
4. **平台代码存在版本落差**：bundle 的 MCP 能力在 HEAD（0.1.14）可用，0.1.11 实测拒绝；文中已标注。
5. **部分榜单分数为论文自报**，与官方 leaderboard 可能不一致（例如 D 报告写"BIRD 公开天花板 81.67%"，而官方榜 2026-10 已到 83.40%）；本文以官方榜为准，并保留论文数字作为方法参考。
