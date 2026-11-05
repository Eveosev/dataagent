## 3. 市场地图：四种形态，正在互相渗透

> 本节基于 2026-10 直连官方文档的抓取（41 条来源见 [A-commercial.md](parts/A-commercial.md)）与开源仓库实测（[B-opensource.md](parts/B-opensource.md)）。凡厂商自述、无第三方复现的，标"宣称"。

### 3.1 四种形态

**A. 语义层优先**（Snowflake Semantic Views、dbt、AtScale、Cube、Kyligence）
Agent 只做"业务术语 → 指标/维度"的解析，SQL 由语义层编译。口径唯一、聚合正确、可审计、跨工具复用；代价是建模重人力，且对语义层没覆盖的探索型问题几乎无解。

**B. Catalog + Agent 生成式**（Databricks Genie、Fabric data agent、BigQuery data agents）
元数据 RAG + few-shot + 执行验证，模型直接写 SQL/DAX/KQL。接入快、覆盖长尾；代价是非确定性，必须靠反馈与 benchmark 闭环维持质量。

**C. BI 内嵌 Copilot**（Power BI Copilot、ThoughtSpot Spotter、Sigma Assistant、Tableau Agent）
复用既有 BI 语义模型与权限，在报表里加问答。分发零成本、天然继承 RLS；上限被 BI 模型质量锁死，输出形态受宿主限制。

**D. Ontology 平台**（Palantir 一枝独秀）
object/link/action/function/interface 类型齐备，带 **ontology 分支 + 提案评审**——这是目前最接近"语义层 PR 流程"的实现，也是我们做版本化评审时最值得抄的交互。

现实中的赢家是 **A+B 混合**：语义层兜住"必须对"的核心指标，生成式兜住长尾，再用 benchmark 与反馈把长尾沉淀回语义层。Databricks 的 knowledge mining（从点赞/下载反推指标与 join 建议）就是这条沉淀通道；Snowflake 的 Autopilot 支持上传 YAML/Tableau/PBI 文件做迁移，说明企业不会从零建模。

### 3.2 关键事实（只列会改变产品决策的）

| 事实 | 出处 | 对我们的含义 |
|---|---|---|
| Databricks 的语义层不在 UC 里，而在 **Agent 级 knowledge store**（≤200 片段、≤100 指令），明确"不写回 UC" | Genie Agents 文档 | 语义层可以"轻"到跟着 Agent 走；但这也意味着它不可复用、不可治理——正是我们的机会 |
| Databricks 值级召回：entity matching 支持至多 **120 列 × 1024 个 distinct 值**；**带行过滤/列掩码的表禁止开启** | 同上 | 值召回与权限强耦合，必须在编译期而非查询期判断 |
| Databricks 内建 benchmark：每 Agent **≤500 题**，Chat 模式比对结果集（5000 行、4 位有效数字容差），Agent 模式交 LLM judge | Genie monitor 文档 | 评测要成为交付物的一部分，不是上线后补的 |
| Fabric data agent 已 GA，但输出**上限 25 行 × 25 列**、不可换模型、暂不支持非英文、不支持非结构化文件 | Microsoft Learn | "对话式洞察"与"取数工具"是两个产品；我们做后者 |
| Snowflake 语义视图是 **schema 级对象**，可 `SELECT` 直查，可作为 listing/Marketplace 商品共享 | Snowflake 文档 | 语义层"可分发"已被验证；MintHub 可以把 ontology pack 做成商品 |
| Snowflake CoWork 内置代码执行、文档生成（PDF/Word/PPT/HTML）、skills、MCP connectors | Snowflake 文档 | "交付物生成"是刚需，不是附加项 |
| Palantir ontology 有**分支 + 提案评审**，value type 有版本 | Palantir 文档 | 版本化的正确形态是"分支 + 提案 + 合并"，不是"改完即生效" |
| Sigma 是唯一明确**双向 MCP**（既 client 又 server）的 BI | Sigma 官网（宣称） | DataAgent 也应双向：既被外部 agent 调用，也能调用外部工具 |
| Snowflake 文档明确列出 Cortex Analyst 的限制：多轮上下文能力有限、**无法访问上一次 SQL 的查询结果** | Snowflake 文档 | 单轮问答是当前商业产品的普遍水位；"连续追问 + 复用中间结果"是差异化空间 |
| Databricks Genie Code 2026-07-08 起按量计费；Genie One/Agents 免费至 2027-01-31 | Databricks 文档 | 云厂商在用"免费"换入口，纯 SaaS 问数没有定价空间 |

### 3.3 开源格局：八成工作量有现成件，两个关键件没有

| 层 | 代表项目 | 事实 | 我们的用法 |
|---|---|---|---|
| 语义层 | WrenAI（18.0k★，core Apache-2.0）、Cube（21.1k★）、MetricFlow（1.9k★）、Apache Ossie（2.6k★） | WrenAI 的 MDL `schema_version=5`，`models/relationships/views/cubes + knowledge/` 双层，未声明列 = 列级不可见 | **抄 MDL 的结构与版本策略**；对外用 Ossie 做互操作 |
| Agent 编排 | DB-GPT（20.2k★，MIT） | agent + AWEL DAG + skills + 沙箱，流程可声明、可落盘 | 学"三条显式 DAG"，不要一个万能 chat loop |
| 连接器 | MCP Toolbox（16.8k★，Apache-2.0）、DBHub（3.8k★，MIT） | Toolbox 一份 `tools.yaml` 覆盖 20+ 库、带连接池/IAM/OTel；DBHub 默认 2 工具仅 1.4k tokens，Toolbox 28 工具 19k tokens | 用 Toolbox 做长尾库；**工具面必须收敛** |
| 执行 | DuckDB（42.7k★，MIT）、Polars、Arrow | 本地零运维直读 CSV/Parquet/Postgres | 文件即席分析的首选执行层 |
| SQL 解析 | sqlglot（9.7k★，MIT） | 20+ 方言解析/转写/列级血缘 | 方言归一与 dry-plan 必用 |
| 剖析 | DataProfiler、ydata-profiling、GX、soda-core | 列统计/实体识别/契约断言成熟 | 直接复用，别自研 |
| **join 发现** | Metanome（197★，2025-06 停更）、HPI IND 算法集（13★，2019 停更） | **没有产品级实现**，语义层里的 join 全靠手写 | **自研**（见 4.1.2） |
| **语义层版本化 + 召回** | WrenAI 最接近（Git Sync + knowledge + LanceDB） | 但**没有** MDL diff → 影响面 → 召回重排 | **自研** |
| **行级/列级权限** | 无开源 RLS DSL | MCP 生态只有只读/限行/超时/authorized parameters | **自研**，且下推到数据库 |

许可证雷区（打包前必须过法务）：Chat2DB 5.3+ 禁"对外提供服务/白标/OEM"；SuperSonic 衍生分发需商业授权；WrenAI 预留 AGPL 模块；Lightdash/PandasAI 有 `ee/` 目录；DBCopilot 无 LICENSE。**参考设计可以，复制代码不行。**

### 3.4 三个不该做的判断

1. **不做通用 ChatBI 前端**。红海，且被云厂商免费化（腾讯云 BI 促销 9.9 元/年，Quick BI 三档订阅）。
2. **不追 NL2SQL 准确率军备竞赛**。BIRD 公开榜 Test 已到 83.40%（人类 Test 72.37%），边际收益递减；真正的差距在 harness（Spider 2.0 同题 23.58% vs 96.70%）和交互（BIRD-Interact 16.33%）。
3. **不自研 OLAP 引擎/不微调基座模型（前期）**。DuckDB + 现成模型足够；把预算放在 ontology 生命周期与评测上。

### 3.5 我们的位置：和谁像、和谁不像

| 对手 | 像在哪 | 不像在哪 | 打法 |
|---|---|---|---|
| **WrenAI**（最接近） | 开源 GenBI、MDL 语义层、MCP、22+ 连接器、Git 化上下文 | 它服务"你已有的 agent"（Claude Code/Cursor），我们是一个可安装的产品；它没有中国部署/国产方言/口径审批；RLS 属商业版 | 不拼引擎，拼"版本化治理 + 中国交付 + 行业包"；它的 MDL 结构可借鉴，代码不复制（AGPL 预留） |
| **Databricks / Snowflake** | 语义层 + agent + 内建评测 | 绑定自家平台与数据；跨库/跨文件/离线不行；按云计费 | 做"云外与混合"：客户的 ERP、Excel、国产库、私有化 |
| **国内 BI**（帆软/观远/SmartBI/Quick BI） | 渠道、报表、指标平台 | 问数体验与"文件→受治理指标"闭环弱；口径争议仍靠人 | 补位而非替代：以 MCP/Skill 被它们集成，或做经营分析会场景 |
| **Palantir** | ontology 分支、提案评审、动作类型 | 重、贵、绑定 Foundry；无轻量本地形态 | 抄交互（分支+提案），用开源与低价切入 |
| **DB-GPT / SuperSonic / Chat2DB** | 开源框架、中文 NL2SQL、连接器 | 是框架/客户端，不是可交付产品；缺治理与评测 | 做"最后一公里"：交付、评测、行业包；社区版可互操作 |

一句话定位：**开源的、可私有化的、以版本化 ontology 为核心的 DataAgent 交付件——不是又一个 ChatBI，也不是又一个语义层引擎。**
