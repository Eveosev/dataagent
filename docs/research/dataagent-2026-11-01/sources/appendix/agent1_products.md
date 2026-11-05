# DataAgent 产品模块边界证据：对外暴露的能力单元与接口契约

调研范围：2026 年主流 DataAgent / Analytics Agent 产品**对外暴露的能力单元与接口**（不是营销功能列表）。
访问日期：**2026-11-01**（Asia/Shanghai）。抓取正文与链接保存在 `sources/`，索引 `sources/source-index.json`。
证据分级：**D=官方文档（事实）｜M=厂商博客/营销（自报）｜U=用户抱怨（用户报告）｜I=本文归纳（推断）**。
失败与未核项单列在 §7，不并入结论。

---

## 1. 一张表：产品 × 能力单元

能力单元沿用任务给定的八分法：**接入 / 语义 / 检索 / 问数 / 分析 / 交付 / 治理 / 反馈**。
符号：✓ 显式提供并写入官方接口文档；部分 = 有但受限或只覆盖子路径；— 未见官方接口级证据。
括号内为证据等级；"D 26-10" 表示该行结论来自 2026-10-31 抓取成功的官方页（本日重取失败，见 §7）。

| 产品（版本/入口） | 接入 | 语义 | 检索 | 问数 | 分析 | 交付 | 治理 | 反馈 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Snowflake Cortex Analyst**（`/api/v2/cortex/analyst/message`；官方建议迁 Cortex Agents） | 部分（仅 Semantic View 覆盖的 Snowflake 表）(D) | ✓ Semantic Views YAML：tables/dimensions/facts/metrics/relationships/verified_queries (D) | ✓ 多语义模型自动选择 + Cortex Search 值检索，响应回传 `cortex_search_retrieval` (D) | ✓ 仅生成 SQL，不执行 (D) | — （文档明示不做"business insights"）(D) | 部分（`text`/`sql`/`suggestion` 三类内容块，无图表工具）(D) | ✓ RBAC/角色 `CORTEX_ANALYST_USER` (D) | ✓ VQ 仓库 + `verified_query_used` 溯源 + evaluations (D) |
| **Snowflake Cortex Agents**（`agent:run` + Snowflake 托管 MCP） | ✓ 工具化：Analyst/Search/Python 沙箱/Data to Chart/自定义 SP·UDF/skills/MCP connectors/agent toolsets/web search (D) | ✓ 引用 Semantic View 作为工具资源 (D) | ✓ Cortex Search（可动态调 filters/列/条数）(D) | ✓ 经 Analyst 工具 (D) | ✓ Python 沙箱 + 多步 plan→tool→reflect (D) | ✓ Data to Chart + thread 状态 (D) | ✓ 每工具执行上下文 + 角色权限；MCP 每工具单独授权 (D) | ✓ feedback REST + threads/logs/evals (D) |
| **Databricks Genie**（`/api/2.0/genie/spaces`） | ✓ UC 表/metric view + 会话内 CSV/Excel/PDF (D) | ✓ knowledge store（表描述/join 关系/SQL 表达式）+ 示例 SQL + 单一 text instruction (D) | ✓ 自动筛列/示例检索 + entity matching（≤120 列 ×1,024 值 ×127 字符）(D) | ✓ SQL + 结果表 + 图表 (D) | 部分（Agent mode 多步探索）(D) | 部分（结果表/图表/文件；非报表编译器）(D) | ✓ 终端用户 UC 身份 + 作者嵌入 warehouse 凭证 (D) | ✓ monitor/benchmarks（≤500 题）+ trusted assets 产生 verified answer (D) |
| **Google Conversational Analytics API**（`geminidataanalytics.googleapis.com` v1/v1beta） | ✓ BigQuery 表/图、Looker Explore、Data Studio、AlloyDB/Cloud SQL/Spanner (D) | 部分（authored context：表列 description/synonyms/tags/sample values + system instruction；无独立可导出 spec）(D) | ✓ `example_queries` 语义匹配 → 直接复用并回 `matched_query`(D) | ✓ SQL + 图表消息流 (D) | 部分（reasoning engine 用 SQL/Python；明示不支持预测/相关/异常检测）(D) | ✓ 流式 text/data/chart + citations；A2A 跨 agent 传 SQL 与图表 (D) | ✓ IAM 角色 + 数据库源按调用者凭证（"table selection isn't a security setting"）(D) | — 未见官方反馈/评测接口 (D) |
| **Looker Conversational Analytics** | ✓ 单个 Explore 或 agent ≤5 Explores；dashboard agent (D) | ✓ LookML 为 source of truth + agent instructions（glossary/persona/关键与排除字段）(D) | 部分（LookML 字段/值域；无独立检索器接口）(D) | ✓ agent 选字段/过滤/limit，Looker 编译执行 (D) | ✓ Advanced Analytics 执行 Python（dashboard agent 不支持）(D) | ✓ 表/图 + iframe 嵌入（private/signed）+ 触发式工作流（Preview）(D) | ✓ 沿用 LookML join/聚合/数据权限；分享 agent ≠ 授数据权 (D) | 部分（System Activity 查看 query/feedback，Preview，需用户同意）(D) |
| **Microsoft Fabric data agent** | ✓ ≤5 数据源：lakehouse/warehouse/Power BI 语义模型/KQL DB/mirrored DB/ontology/Graph (D) | ✓ 语义模型 + ontology + instructions + example queries（无独立 YAML spec）(D) | 部分（按问题在源与表间路由）(D) | ✓ NL2SQL / NL2DAX / NL2KQL 三工具 (D) | — （明示不触发 notebook/异常检测等写或动作流）(D) | 部分（会话回答；**≤25 行 ×25 列**）(D) | ✓ 只读 + 调用者凭证 + Purview DLP/RAI 校验 (D) | — 未见官方反馈接口 (D) |
| **Power BI Copilot**（含 Fabric IQ） | 部分（同一语义模型；Q&A 引擎须启用）(D) | ✓ 语义模型 + AI data schema + AI instructions + **verified answers（trigger phrases→visual）** (D) | 部分（Q&A 语言 schema/同义词）(D) | ✓ 既有度量 + 临时 DAX (D) | 部分（Fabric IQ 多步推理）(D) | ✓ 视觉/表/DAX 查询三视图 + 报告页与叙述视觉 (D) | ✓ 语义模型 RLS + 容量/区域/租户开关 (D) | 部分（Fabric IQ 展示推理步骤与 DAX，但不返回 verified answers）(D) |
| **ThoughtSpot Spotter 3**（+AgentQL） | ✓ 连接器 + Model（TML）(D) | ✓ TML Model + AI context + instructions + business terms/记忆源 (D) | ✓ 关系型 token 检索（search tokens）(D) | ✓ AgentQL→QGen→SQL（数据库特定确定性编译）(D) | ✓ Python（预测/回归）、Research 模式 (D) | ✓ 回答卡/Liveboard/嵌入 (D) | ✓ AgentQL 继承模型 RLS/CLS (D) | ✓ 反馈→memory sources，TML `nls_feedback` 可版本化 (D) |
| **dbt（Wizard / Explore / Copilot / MCP）** | ✓ dbt 项目 + 仓库/元数据 + MCP 客户端 (D) | ✓ `semantic_model` YAML（entities/dimensions/metrics/agg_time_dimension）(D) | ✓ Discovery/语义检索（`get_related_models`、lineage 有界查询）(D) | ✓ `text_to_sql`、`execute_sql`、`get_metrics_compiled_sql`（MCP 工具）(D) | 部分（Copilot/Insights 生成 SQL 与解释；非通用 Python 分析）(D) | 部分（生成/校验模型与查询；Explore 面向只读用户）(D) | ✓ 项目权限 + 计划类型限制 Discovery/SL API (D) | 部分（Wizard 审阅/验证流程；未见统一回归门禁）(D) |
| **Cube（Core / Cloud + Agent）** | ✓ 任意 SQL 源；dbt 集成 (D) | ✓ 模型即代码 YAML/JS：cubes/views/joins/measures/dimensions + AI context + access policies (D) | 部分（view groups/语义查询路由；无独立检索 API）(D) | ✓ REST `/load`、SQL API（Postgres 协议）、GraphQL、DAX (D) | ✓ Chat API + Workbook/Dashboard agent + skills + scheduled tasks (D) | ✓ Chat API/iframe/React SDK/仪表板导出 (D) | ✓ RLS + member-level security + JWT security context (D) | ✓ evals（对照 ground truth 跑分）+ memories 隔离 (D) |
| **Wren AI（OSS / Cloud）** | ✓ PostgreSQL/MySQL/SQL Server 等连接器 + dbt (D) | ✓ MDL YAML 项目（models/relationships/views/cubes/knowledge）(D) | ✓ question-SQL pairs 知识库 + memory system (D) | ✓ `wren serve mcp` 暴露 `run_sql`/`dry_run`/`dry_plan`/`query_cube`/`get_mdl` (D) | 部分（query_cube 预聚合；分析深度未核到）(D) | 部分（GenBI app / SDK：langchain/pydantic/wasm）(D) | ✓ 只读开关、`--no-connect` 纯转译模式 (D) | 部分（question-SQL pairs 作为学习入口；未核到评测接口）(D) |
| **阿里 Quick BI 智能小Q** | 部分（Quick BI 数据集/仪表板/Excel 即席）(D 26-10) | 部分（数据集字段/聚合/知识/维值预配置）(D 26-10) | — | ✓ 小Q问数 Agent (D 26-10) | ✓ 小Q解读（异常/趋势/洞察报告）(D 26-10) | ✓ 小Q报告、小Q搭建（仪表板）(D 26-10) | 部分（Agent 权限与数据授权分开管理）(D 26-10) | 部分（点赞点踩/用例处理；未核到接口）(D 26-10) |
| **数势 SwiftAgent / 网易有数 ChatBI / 观远 ChatBI** | 未核实 | 未核实 | 未核实 | 未核实 | 未核实 | 未核实 | 未核实 | 未核实 |

> 表内判断口径：✓ 只表示厂商在官方文档中给出了该能力单元的**接口或配置对象**，不表示效果达标；"部分"通常意味着只能通过整体对话接口间接获得、或仅覆盖部分数据源/路径。

---

## 2. 逐产品证据卡

### 2.1 Snowflake Cortex Analyst
- **能力单元拆法**：语义（Semantic Views）→ 问数（text-to-SQL）→ 交付（内容块）。**不执行 SQL、不做业务洞察**：官方原文 "Cortex Analyst is limited to answering questions that can be resolved with SQL. It does not generate insights for broader business-related queries"（D）。
- **接口形态**：`POST /api/v2/cortex/analyst/message`；请求必须提供 `semantic_model_file` / `semantic_model`（内联 YAML）/ `semantic_models[]` / `semantic_view` 之一；响应内容块类型仅 `text | sql | suggestion`，带 `confidence.verified_query_used`、`warnings`、`response_metadata.model_names|cortex_search_retrieval|question_category`；支持 SSE `stream`（D）。
- **官方限制**：多轮无上一轮**结果**访问（"doesn't have access to results from previous SQL queries"）；长对话易失效需重开；SQL-only；模型按区域可用性，跨区需 cross-region inference；计费按消息数（仅 200 计入）（D）。
- **可插拔**：语义层**不可替换**（Semantic Views 或 stage 上的 legacy YAML）；执行引擎固定 Snowflake warehouse；模型由 Snowflake 选（文档：运行时"selects the best combination of models"，用户不可指定）（D/I）。
- **失败模式**：把 follow-up 指代（"第二个产品"）解析错；口径类问题被归到 `suggestion` 而非 SQL；VQ 写错会**拉低**准确率（D 原文 "Invalid or inaccurate queries can negatively impact ... accuracy"）。

### 2.2 Snowflake Cortex Agents + Snowflake 托管 MCP
- **能力单元拆法**：这是"通用 agent 运行时"拆法——Agent = model + tools + instructions；工具集：Cortex Analyst、Cortex Search、Analytical search（Preview）、Code execution（Python 沙箱）、Data to Chart、Custom tools（SP/UDF）、Agent skills、MCP connectors、**Agent toolsets（引用其他 agent 继承其工具，实现组合）**、Web search（D）。
- **接口形态**：`agent:run` REST + Threads REST + Feedback REST；托管 MCP server 用 `CREATE MCP SERVER ... FROM SPECIFICATION $$ ... $$` 声明 `tools[{name,type,identifier,config}]`，工具类型枚举 `CORTEX_AGENT_RUN | CODING_AGENT | CORTEX_SEARCH_SERVICE_QUERY | CORTEX_ANALYST_MESSAGE | GENERIC`，支持 `readOnlyHint/destructiveHint/idempotentHint/openWorldHint` 注解（D）。
- **官方限制**：**每 MCP server ≤50 工具**；工具响应 **250 KB 截断**（generic 与 SQL execution）；`SYSTEM_EXECUTE_SQL` 的 `read_only` 默认 true；注解只是"client-facing hints, not security controls"；不支持 dynamic client registration；递归调用有上限（D）。
- **可插拔**：模型可选 `auto` 或指定；工具可换（含三方 MCP）；**但官方明确警告**：把 `SYSTEM_EXECUTE_SQL` 和 agent 暴露在同一 server，会让客户端"bypass the agent's semantic views, verified queries, and orchestration"（D）——这是模块边界最好的官方注脚。
- **失败模式**：工具越多 tool-selection 越差（官方原文 "Higher tool counts can degrade tool-s..."）；agent 无工具时只能凭模型常识答；MCP 与 PrivateLink/SaaS 客户端的 OAuth 与网络策略坑（D）。

### 2.3 Databricks Genie（Agents）
- **能力单元拆法**：数据（UC 表/metric view）→ 语义（knowledge store + 示例 + instructions）→ 生成（SQL）→ 结果（表/图）→ 治理（UC + warehouse）→ 质量（benchmarks/trusted assets）。
- **接口形态**：`POST /api/2.0/genie/spaces` 创建，`serialized_space` 为 **JSON 字符串**（`version:2`），内含 `data_sources.tables|metric_views`、`config.sample_questions`、`instructions.text_instructions|example_question_sqls|sql_functions|join_specs|sql_snippets.{filters,expressions,measures}`、`benchmarks.questions`；**所有 ID 必须是 32 位小写 hex 且数组需预排序**，否则拒收（D）。
- **官方限制**：每 agent **100 条 instruction**、**200 条 knowledge store snippet**、**仅 1 条 text instruction**；单字符串 25,000 字符；数组 10,000 项；**200,000 会话上限**；轮询 1–5 秒、10 分钟封顶（D）。
- **可插拔**：语义层限定 UC（含 metric views），执行限定 SQL warehouse（作者凭证）；模型不开放（D/I）。
- **失败模式**：作者未测试时"correct API integration 也会返回错误结果"（D 原文）；上传文件走独立存储/保留策略；Chat 与 Agent 模式准确率口径不同（D）。

### 2.4 Google BigQuery / Conversational Analytics API（原 Data Agents）
- **能力单元拆法**：数据源（BQ/Looker/DB）→ authored context（结构化字段 + system instruction + example queries）→ reasoning engine（SQL/Python/图表工具）→ 消息流（text/data/chart + citations）→ 多 agent（A2A）。
- **接口形态**：`v1beta/.../dataAgents:createSync`、`v1/...:chat`、`QueryData`；Python SDK；**stateful vs stateless** 双模式，`published_context`（持久）与 `inline_context`（单次）（D）。`example_queries[]` 元素为 `{naturalLanguageQuestion, sqlQuery, parameters[{name,dataType,description}]}`，占位符用 `{state}` / `@state`（D）。
- **官方限制（全部为硬数字）**：Looker 源 **5,000 行/查询**；AlloyDB/Cloud SQL/Spanner **1,000 行**；BigQuery **500 GB 扫描**；**8,192 输出 token**；`DataResult` **3,000,000 字节截断**；校验失败最多**重试 3 次**（权限错误不重试）；chat **30 QPM**（每次算 8 quota 单位）；不支持预测/高级统计（相关、异常检测）；不支持 BigQuery flexible column names；struct 可能失败；**一次只能查一个 Explore**（D，页脚 "Last updated 2026-10-26 UTC"）。
- **可插拔**：数据源可插拔度高（BQ/Looker/DB 多后端）；**语义层是"authored context"而非可导出 spec**（部分）；模型不开放（D/I）。
- **失败模式**：官方自述"table selection isn't a security setting"——限表不构成越权防护；大结果集降低推理准确率并触发 `MAX_TOKENS`；图表 tooltip 部分支持（D）。

### 2.5 Looker Conversational Analytics
- **能力单元拆法**：LookML（语义/权限）→ Explore/agent（≤5 Explores）→ 编译执行 → 结果 → 嵌入/触发式交付。
- **接口形态**：agent 配置对象含 Data（≤5 Explores）、**Instructions（自由文本：关键字段、排除字段、过滤分组、persona）**、**Verified queries**、Advanced options（Advanced Analytics / Show thinking / Show debug）（D）。**Verified query 的"答案"是 Explore URL，不是 SQL**——官方："Answer: Paste the URL of the Explore that captures the correct query or visualization"（D）。
- **官方限制**：VQ **仅对 Explore data agent 生效**，直接对话与 dashboard agent 不可用；VQ **不支持自定义字段与 pivot**；数量无硬限但"建议 30–50 对"；分享 agent 不授予 Explore 权限（D）。
- **可插拔**：语义层固定 LookML；执行引擎固定 Looker（SQL 由 Looker 编译，agent 只选字段/过滤/排序/limit）；模型固定 Gemini（D/I）。
- **失败模式**：dashboard agent 无 Advanced Analytics；触发式/定时工作流仍 Preview；用户反馈监控需用户同意分享（D）。

### 2.6 Microsoft Fabric data agent
- **能力单元拆法**：源（≤5）→ 选表 → instructions → 工具路由（NL2SQL/NL2DAX/NL2KQL）→ 只读执行 → 会话回答。
- **接口形态**：Fabric 中的 artifact（创建/发布/分享），可被 M365 Copilot、Copilot Studio、Azure AI Foundry、Teams 及外部 orchestrator 调用（D）。**未见独立的 data agent REST/OpenAPI 或 MCP 端点文档**（本轮未核到，见 §7）。
- **官方限制**：**≤25 行 × ≤25 列**；**仅英语**（"doesn't currently support non-English languages"）；严格**只读**，不生成 create/update/delete；不触发 notebook/异常检测；不接受裸文件（须先入表）；DLP/RAI 策略可能拦截查询（D）。
- **可插拔**：查询引擎按源类型路由（SQL/DAX/KQL 三套），语义靠 Power BI 语义模型或 ontology；底层模型为 Azure OpenAI Assistant（不可换）（D/I）。
- **失败模式**：历史消息会污染后续结果（"previous chat history can influence subsequent responses"，官方建议新开会话）；高基数时序需用户自带时间过滤（D）。

### 2.7 Power BI Copilot（含 Fabric IQ）
- **能力单元拆法**：语义模型（度量/关系/业务定义）→ Q&A 引擎 → 问数/总结/建页 → 视觉/表/DAX。
- **接口形态**：全部在语义模型内配置（`Prep data for AI`）：**AI data schema、AI instructions、verified answers（trigger phrases 绑定到某个 visual，存回语义模型）、Approved for Copilot 标记**（D）。Fabric IQ 额外回传**推理步骤 + 生成的 DAX 查询 + 数据表**，可切换 visual/table/DAX 视图（D）。
- **官方限制**：需启用 Q&A；Fabric IQ 只在 Power BI 服务查看态可用；**开启 Fabric IQ 时不返回 verified answers**（功能互斥，D 原文 "When Fabric IQ is enabled, Copilot doesn't return verified answers"）；区域/租户开关/容量 SKU（trial 不支持）（D）。
- **可插拔**：语义层与 DAX 引擎均不可替换；模型不可选（D/I）。
- **失败模式**：verified answer 只覆盖"绑定了视觉"的问题；ad hoc DAX 与既有度量口径可能分叉（I）。

### 2.8 ThoughtSpot Spotter（3 / Agent / Classic）
- **能力单元拆法**：Model（TML）→ AI context/instructions/business terms/memory → 关系型检索 tokens → AgentQL（语义查询）→ QGen（确定性编译）→ 结果；复杂分析走 Python；Research 模式做调查。
- **接口形态**：**TML**（可导出/导入的 flat file，覆盖 Model/Answer/Liveboard/Connection/coaching；`obj_id` 为跨 Org 稳定标识，供 CI/CD）；**REST API v2 + Embed SDK + AgentQL(JS)**；**memory 的 TML 规格**：`nls_feedback[].{type: BUSINESS_TERM, access: GLOBAL, feedback_phrase, parent_question, search_tokens, formula_info{name,expression}, rating: UPVOTE}`（D）。
- **官方限制**（Spotter limitations 页）：**不支持 parameters**（只能用替换了参数值的公式）；**不能用自然语言改图表配置**（颜色/坐标轴/标签）；不支持 tonality/叙事风格/why-coaching；Spotter Classic 不支持 "Why did sales go down"、不能自动选模型、用公历而非自定义财年（D）。
- **可插拔**：TML 让语义与记忆可版本化、可迁移；但 QGen 是自研数据库特定编译器，不可替换；模型不可换（D/I）。
- **失败模式**：跨模型/跨数据源问题归到"选模型"这一步由用户承担（Classic/Agent）；参数化场景直接失效（D）。

### 2.9 dbt（Wizard / Explore / Copilot / MCP）
- **能力单元拆法**：项目与元数据（模型、source、exposure、semantic_model）→ 语义（`semantic_model` YAML：entities{type: primary|foreign|unique|natural}、dimensions、metrics、`agg_time_dimension`）→ 编译（MetricFlow / Fusion）→ 消费（GraphQL/JDBC/BI/agent）。
- **接口形态**：**MCP server**（本机/远程）暴露工具：`execute_sql`、`get_metrics_compiled_sql`、`get_lineage`（有界 type/depth/direction）、`get_node_details`、`get_related_models`（语义检索）、`get_model_health`、`text_to_sql`、`compile`/`run`、job 系列、`fusion.compile_sql`/`get_column_lineage`（D）；**Semantic Layer GraphQL API**（`/api/graphql`，需 token + `environmentId`，`metricsPaginated`/`dimensionsPaginated`）（D）。
- **官方限制**：`text_to_sql` 是**唯一依赖 AI 开关**的工具——管理员关 AI 后该工具从远程 server 消失，其余工具仍可用；Discovery/Semantic Layer API 受**计划类型**限制；MCP 客户端可改模型/数据，官方警告"Proceed only if you trust the client"（D）。
- **可插拔**：本清单中"语义层可移植性"最好的一档——语义与指标在 Git 里，编译产物可由多个前端消费；但编译内核是 MetricFlow，换引擎要重写 spec（D/I）。
- **失败模式**：`execute_sql` 直连仓库，绕过语义与权限模型的风险由调用方承担（I，基于工具语义推断）；GraphQL 不支持 `ref`（须写全限定表名），宏内计算须前移到指标定义（D）。

### 2.10 Cube（Core / Cloud + Agent）
- **能力单元拆法**：模型即代码（YAML/JS：cubes、views、joins、measures、dimensions、pre-aggregations、access policies）→ 多协议服务（REST/SQL/GraphQL/DAX）→ Agent 层（rules、certified queries、skills、memories、multi-agent、evals、BYOM）→ 交付（Chat API/iframe/React SDK/dashboards）。
- **接口形态**：`POST /load`（REST JSON：measures/dimensions/filters/timeDimensions/limit/totals）、**SQL API（Postgres 协议）**、GraphQL、DAX；**Chat API**（流式会话）；**MCP server**（托管 HTTPS + OAuth）；**agent 配置即仓库文件**：`agents/certified_queries/*.md`（frontmatter `description`/`user_request` + 正文 SQL）、`rules`、`skills`、`memories`（D）。
- **官方限制**：SQL API 限定 Postgres 方言与支持命令集；React Embed SDK 仍 **public preview**（"The API may change"）；certified queries **不限制** agent 只跑这些（可改写或新生成）；缓存与租户隔离需按文档自行约束（D）。
- **可插拔**：**最强**：语义层开源（Apache 2.0）、模型可换（BYOM：Anthropic/OpenAI/Bedrock/Azure/custom OpenAI-compatible）、执行下推到 warehouse、多协议与 MCP 并存（D）。
- **失败模式**：多协议意味着"同一问题可有四种查询写法"，语义与权限要在模型层一次写对，否则各协议行为分叉（I）；语义查询能力强但依赖预聚合，冷启动/回填是关键运维点（I）。

### 2.11 Wren AI
- **能力单元拆法**：连接器 → MDL（`wren_project.yml` + `models/*/metadata.yml` + relationships/views/cubes + `knowledge/`）→ 编译（`wren context build`）→ 执行/服务（MCP、SDK、GenBI app）。
- **接口形态**：`wren serve mcp`（stdio/http）暴露 **Query 工具**（`run_sql`、`dry_run`、`dry_plan`、`query_cube`）与 **Schema 工具**（`get_mdl`、`list_models`、`describe_model`）及业务知识工具；`--no-connect` 得到"纯转译、不接触数据库"的 server；SDK：`wren-langchain`、`wren-pydantic`、`wren-core-wasm`；支持 dbt 集成与 OSI（D）。
- **官方限制**：需连接数据库才能用执行类工具（除 `--no-connect`）；工具按只读/全权模式区分（文档：`--read-only` 之外默认只读语义）（D，具体默认值待核）。
- **可插拔**：MDL 与引擎分离（core/ibis-server），可换数据源、可换客户端；模型供应商可配（未逐项核到）（D/I）。
- **失败模式**：MCP 客户端直接 `run_sql` 会绕过 MDL 语义（与 Snowflake 同构的问题）；question-SQL pairs 质量差会污染生成（I）。

### 2.12 阿里 Quick BI 智能小Q（部分证据，2026-10-31 抓取）
- **能力单元拆法**：统一入口做**意图路由**，分派给 4 个 Agent：小Q问数、小Q解读、小Q报告、小Q搭建（"集问数、报告、解读、搭建、搜索等多Agent于一体，基于用户意图识别，自动规划相应专家Agent执行操作"）（D，阿里云帮助中心）。
- **接口形态/商业边界**：4 个 Agent **属增值模块需额外购买**；买"问数"可用"问数+解读"；**仅高级版/专业版可增购**，个人版不支持（D）。
- **未核**：公开 OpenAPI/语义模型 spec/verified query 形态、行数与语言限制（见 §7）。

---

## 3. 接口契约对比

### 3.1 语义模型 spec：四种世界观

| 形态 | 代表 | 定义载体 | 可版本化 | 与执行引擎耦合 |
| --- | --- | --- | --- | --- |
| **对象化 DDL**（数据库对象） | Snowflake Semantic Views | `CREATE SEMANTIC VIEW` + YAML 规格；`tables/dimensions/facts/metrics/relationships/verified_queries`，可 `access_modifier` 控制可见性 | 中（对象 + stage 文件） | 强耦合 Snowflake |
| **文件即模型（Git 内）** | dbt `semantic_model`、Cube YAML/JS、Wren MDL | `semantic_model:` 块（entities/dimensions/metrics/agg_time_dimension）；Cube `cubes/views/joins`；Wren `wren_project.yml + models/*/metadata.yml` | 强（PR/CI） | 弱耦合（可下推多仓库） |
| **BI 建模语言** | Looker LookML、ThoughtSpot TML | LookML（view/explore/join/access_grant）；TML（Model/Answer/Liveboard/coaching，`obj_id` 稳定标识） | 强（TML 可导入导出、跨 Org） | 强耦合自家引擎 |
| **上下文包（无独立 spec）** | BigQuery CA API、Fabric、Power BI Copilot | 表/列 `description`/`synonyms`/`tags`/`sample values` + `system_instruction` + `example_queries`；Power BI 的 AI schema/instructions/verified answers 存在语义模型里 | 部分（Power BI 随模型；BQ 随 agent 配置） | 弱（可跨 BQ/Looker/DB），但不可移植 |

```yaml
# Snowflake：一个语义视图既是模型也是 VQ 仓库（官方 VQR 文档示例，节选）
name: Sales Data
tables:
  - name: sales_data
    base_table: {database: sales, schema: public, table: sd_data}
    dimensions:
      - {name: state, expr: d_state, data_type: TEXT, sample_values: ["CA", "IL"]}
    time_dimensions:
      - {name: sale_timestamp, expr: dt, data_type: TIMESTAMP}
    measures:
      - {name: profit, expr: amt - cst, default_aggregation: sum}
verified_queries:
  - name: "California profit"
    question: "What was the profit from California last month?"
    verified_at: 1714497970
    verified_by: Jane Doe
    use_as_onboarding_question: true
    sql: "SELECT sum(profit) FROM __sales_data WHERE state = 'CA' AND ..."
```

```yaml
# dbt：语义模型是"图上的节点"，连接键是一等公民（官方示例结构）
semantic_model:
  name: orders
  agg_time_dimension: ordered_at
  entities: [{name: order, type: primary}, {name: customer, type: foreign}]
  dimensions: [{name: order_date, type: time}]
  metrics: [{name: order_total, agg: sum, expr: amount}]
```

> 关键差异（I）：**只有 Snowflake / dbt / Cube / Wren / Looker / ThoughtSpot 把语义写成可 diff 的文本对象**；BigQuery CA API、Fabric、Power BI 把语义拆成"上下文字段 + 示例 + 指令"，好处是能跨源，坏处是无法把语义资产从一个产品搬到另一个产品。

### 3.2 verified query：四种契约，差别在"答案是什么"和"如何被引用"

| 产品 | 存储位置 | 一条 VQ 的字段 | 命中后的可观测证据 |
| --- | --- | --- | --- |
| **Snowflake** | 语义模型 `verified_queries[]` | `name / question / sql / verified_at / verified_by / use_as_onboarding_question`；**SQL 必须使用逻辑表列名**（`__sales_data` 前缀） | 响应 `confidence.verified_query_used{name,question,sql,verified_at,verified_by}` |
| **Looker** | data agent 配置 | `Question` + `Answer = Explore URL`（不是 SQL） | Show thinking / Show debug |
| **BigQuery CA API** | agent `example_queries[]` 或 `inline_context` | `naturalLanguageQuestion` / `sqlQuery` / `parameters[{name,dataType,description}]`，占位 `{x}` ↔ `@x` | 响应出现 `matched_query` 对象；可能被引用（citation） |
| **Cube** | 仓库 `agents/certified_queries/*.md` | frontmatter `description`、`user_request` + 正文 SQL | 文档声明 agent 可"直接使用/改写/忽略"，**不保证命中** |
| **Databricks Genie** | 示例 SQL（trusted asset）+ 参数化示例 | SQL + 问题标题 + 参数（comment 说明取值范围） | 命中时返回 **verified answer**；agent 用户可改参数重跑 |
| **dbt** | `semantic_model` 之下的指标 + MCP `get_metrics_compiled_sql` | 指标名/维度/filter，无独立 VQ 对象 | 编译后 SQL 与 lineage |

> 契约层最重要的一点（I）：**只有 Snowflake 与 BigQuery 把"用了哪条 verified query"写进响应体**（`verified_query_used` / `matched_query`）。这让"是否命中受控路径"变成可断言、可回归的字段，而不只是 UI 上的解释。

### 3.3 受控查询编译器：谁在生成 SQL，谁在保证确定性

| 编译器 | 输入 | 输出 | 保证边界 |
| --- | --- | --- | --- |
| **Looker** | agent 选定的 fields/filters/sorts/limit | Looker 生成并执行 SQL | join/聚合/access grant 由 LookML 强制；agent 不写 SQL |
| **ThoughtSpot AgentQL → QGen** | 语义查询（TML 模型之上） | 数据库特定的确定性 SQL | "interpret intent probabilistically and return deterministic results"；继承 RLS/CLS |
| **Cube** | REST JSON / GraphQL / MDL 语义查询 | 下推到仓库的 SQL（含预聚合改写） | 访问策略在模型层，查询改写可审计 |
| **dbt MetricFlow** | 指标 + 维度 + 时间粒度 | 编译 SQL（GraphQL `get_metrics_compiled_sql`） | 指标口径在 YAML；join 由 entity 图推导 |
| **Snowflake** | NL + 语义视图 | **只返回 SQL 文本**，由调用方执行 | 不做编译期保证，靠语义视图 + VQ + 评测闭环 |
| **BigQuery CA API** | NL + context | agent 内部生成并执行，返回 data/chart | 失败最多重试 3 次；硬行数/字节/token 上限 |

> 分界线（I）：**"受控编译器"产品把不确定性限制在"选哪个字段/哪个模型"，SQL 结构由平台生成；"开放生成"产品（Snowflake Analyst、Fabric、Genie）把不确定性留在 SQL 文本本身，再用 VQ/示例子句/评测去收敛。** 这两类的验收方式不同：前者验"语义选择"，后者验"SQL 正确性"。

---

## 4. 官方明示限制汇总（可直接引用）

| 维度 | 数值/条款 | 产品 |
| --- | --- | --- |
| 结果行数 | 25 行 × 25 列 | Fabric data agent |
| 结果行数 | 5,000 行（Looker 源）／1,000 行（AlloyDB/Cloud SQL/Spanner） | BigQuery CA API |
| 扫描量 | 500 GB bytes processed | BigQuery CA API |
| 输出长度 | 8,192 token；`DataResult` 3,000,000 字节截断 | BigQuery CA API |
| 语言 | 仅英语 | Fabric data agent |
| 只读 | 仅生成读查询，不 create/update/delete | Fabric；Snowflake MCP `read_only` 默认 true |
| 数据源数 | ≤5（Fabric）；≤5 Explores（Looker agent）；≤5 语义模型可并列（Snowflake `semantic_models[]`，无硬上限文档） | Fabric / Looker / Snowflake |
| 配置对象上限 | 100 instruction、200 knowledge snippet、1 text instruction、200,000 会话 | Databricks Genie |
| 工具上限 | 50 工具/MCP server；250 KB 响应截断 | Snowflake 托管 MCP |
| 会话/上下文 | 无上一轮结果访问；长对话需重置 | Snowflake Analyst |
| 功能互斥 | Fabric IQ 开启时不返回 verified answers | Power BI |
| 不支持 | parameters（Spotter）；预测/相关/异常检测（CA API）；自定义字段与 pivot 的 VQ（Looker）；flexible column names（CA API） | 多家 |
| 速率 | chat 30 QPM；每 chat 计 8 quota unit；DB 源 50 QPM | BigQuery CA API |

---

## 5. 已知失败模式与用户抱怨（U 级须谨慎，此处仅列有文档依据者）

- **"限表≠权限"**：BigQuery CA API 原文 "Table selection isn't a security setting"；Snowflake/Genie/Wren 的 SQL 执行工具都可能绕过语义视图（D）。**这是模块边界问题，不是模型问题。**
- **历史上下文污染**：Fabric 明示上一轮 25 行截断会影响后续答案（D）；Snowflake 明示长对话需重开（D）。
- **工具膨胀降质**：Snowflake 文档写明工具数增加会降低工具选择质量（D）；Genie 用 100/200 上限强制约束（D）。
- **VQ 反噬**：写错的 verified query 会降低准确率（Snowflake D）；Cube 明确 agent 可以不使用 certified query（D）。
- **口径与统计能力缺口**：CA API 不支持预测/相关性/异常检测（D）；Spotter 不支持参数（D）；Snowflake Analyst 不做业务洞察（D）。
- **未获独立负向用户样本**：本轮未系统采集社区抱怨，**不给出失败率**（见 §7）。

---

## 6. 对"模块化拆分与优先级"的 10 条启示

1. **把"语义资产"和"语义消费"分成两个模块**：Snowflake（Semantic Views）、dbt、Cube、Wren 都把语义写成可 diff 的对象，而 BigQuery/Fabric/Power BI 只有"上下文字段 + 示例"，前者可迁移、后者只能绑定平台。
2. **verified query 必须是一等对象并带溯源字段**：只有 Snowflake（`verified_query_used`）与 BigQuery（`matched_query`）把"命中了受控路径"写进响应，其他产品只能靠 UI 解释，无法做自动回归。
3. **"受控编译器"与"开放 SQL 生成"是两种产品，不该共用一套验收**：Looker/ThoughtSpot/Cube/dbt 的不确定性在"选字段"，Snowflake/Fabric/Genie 的不确定性在 SQL 文本，后者必须配 VQ + 评测才能上线。
4. **执行引擎要独立成模块，并默认只读**：Snowflake MCP 的 `read_only: true` 默认值与 Fabric 的"严格只读"是可复用契约；一旦把裸 SQL 执行和 agent 暴露在同一入口，官方自己承认会绕过语义与 VQ。
5. **接入层按"源类型"而非"产品"抽象**：Fabric 用 NL2SQL/NL2DAX/NL2KQL 三工具覆盖三类源，BigQuery 用五个 backend；这说明接入模块的接口应是 `(source_type, query_tool)`，而不是单一 text2sql。
6. **检索模块要能返回"用了什么"**：Snowflake 回 `cortex_search_retrieval`、Genie 的 entity matching 有明确配额（120 列 ×1,024 值），说明检索结果必须结构化可审计，否则无法定位"值没匹配上"这类错误。
7. **反馈与"共享事实"要拆成两层**：Genie 原文 "behavior does not change based on user feedback alone"，ThoughtSpot 把反馈落到 memory sources/TML，Cube 用 evals 对照 ground truth——个人偏好、团队记忆、认证指标是三种不同写入路径。
8. **硬性配额是最好的模块边界说明书**：25×25 行、5,000/1,000 行、8,192 token、50 工具、100 instruction——这些数字直接划出了"会话交付""结果交付""批量导出"三种不同产品的边界。
9. **可插拔度排序（本清单）**：Cube ≈ dbt ≈ Wren（模型/引擎/模型供应商可换）> BigQuery CA API（源可换、语义不可导出）> Looker/ThoughtSpot/Fabric/Power BI（语义与引擎强绑定）> Snowflake Analyst（语义与执行均锁定 Snowflake）。
10. **优先级建议（I）**：先做"语义对象 + verified query + 只读执行 + 溯源字段"这四个可验收的最小闭环，再谈检索优化与多步分析；反过来先做 agent 编排，会把不确定性堆到最不可测的一层。

---

## 7. 未核实 / 抓取失败项（不编造）

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 数势科技 SwiftAgent | **未核实** | `https://www.swiftagent.io/` 本轮 TLS 握手失败（`UNEXPECTED_EOF_WHILE_READING`）；未取得任何官方接口文档，表中整行留空。 |
| 网易有数 ChatBI | **未核实** | `https://youdata.163.com/` 返回 0 字符正文（疑似前端渲染/拦截）；未取得能力单元或接口证据。 |
| 观远 ChatBI | **未核实** | `https://www.guandata.com/` 仅取到 2,573 字符首页营销文案，无接口/配置对象；不足以判 ✓/部分。 |
| 阿里 Quick BI 智能小Q | **部分核实（D 26-10）** | 2026-10-31 抓取 `help.aliyun.com/zh/quick-bi/user-guide/smart-q-home-page` 成功；**2026-11-01 重取 TLS 失败**。未取得 OpenAPI、语义 spec、VQ 形态、行数/语言限制。 |
| 阿里 析言 GBI | **未核实** | `https://help.aliyun.com/zh/gbi/` 本轮 TLS 失败。 |
| Fabric data agent 的 REST/MCP 端点 | **未核实** | 只确认"可被 M365 Copilot / Copilot Studio / Foundry / Teams 及外部 orchestrator 调用"，未找到独立 API reference。 |
| Databricks Agent Bricks 细节 | **部分** | `docs.databricks.com/aws/en/generative-ai/agent-bricks/` 仅取到 4,165 字符导航级文本，未取得其 agent 定义对象与限制。 |
| Power BI Copilot 的对话 REST API | **未核实** | 未找到公开的 Copilot 对话端点文档；仅有语义模型侧配置。 |
| Snowflake Analyst 结果行数上限 | **未核实** | 文档未见"结果行数"硬限（与 BigQuery/Fabric 不同），未找到可引用数值。 |
| 独立用户抱怨样本 | **未系统采集** | 本轮以官方文档为主，未做社区抽样，故不给出失败率与"普遍抱怨"排序。 |
| BigQuery CA API / Fabric / Power BI 的营销页 | 未纳入 | 只使用技术文档，避免把营销承诺当能力。 |

---

## 8. 来源清单（访问日期 2026-11-01，除注明者）

**官方文档（D）**
1. Snowflake Cortex Analyst — https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst
2. Snowflake Cortex Analyst REST API — https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/rest-api
3. Snowflake Semantic Views YAML spec — https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec
4. Snowflake Verified Query Repository — https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository
5. Snowflake Cortex Agents — https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents
6. Snowflake Cortex Agents REST API — https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api
7. Snowflake-managed MCP server（含 50 工具/250KB 限制）— https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp
8. Databricks Genie Agents — https://docs.databricks.com/aws/en/genie-agents/
9. Databricks Genie concepts — https://docs.databricks.com/aws/en/genie-agents/concepts
10. Databricks Genie API（serialized_space/限额）— https://docs.databricks.com/aws/en/genie-agents/conversation-api
11. Databricks Tune Genie quality（100/200/entity matching）— https://docs.databricks.com/aws/en/genie-agents/tune-quality
12. Databricks metric views — https://docs.databricks.com/aws/en/business-semantics/metric-views
13. Databricks-provided MCPs — https://docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp
14. Conversational Analytics API overview — https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/overview
15. CA API key concepts（A2A/stateful）— https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/key-concepts
16. CA API known limitations（行数/字节/token）— https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/known-limitations
17. CA API quotas — https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/quotas
18. CA API authored context (BigQuery, `example_queries`) — https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/data-agent-authored-context-bq
19. CA API build agent over HTTP（`createSync`/`:chat`）— https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/build-agent-http
20. Looker Conversational Analytics overview（≤5 Explores）— https://cloud.google.com/looker/docs/conversational-analytics-overview
21. Looker Explore data agents（verified queries = Explore URL）— https://cloud.google.com/looker/docs/conversational-analytics-looker-data-agents
22. Fabric data agent（25×25/英语/只读/≤5 源）— https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent
23. Fabric data agent 创建 — https://learn.microsoft.com/en-us/fabric/data-science/how-to-create-data-agent
24. Power BI Copilot overview — https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-introduction
25. Power BI Copilot 问数 + Fabric IQ（不返回 verified answers）— https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-ask-data-question
26. Power BI Prep data for AI（verified answers/trigger phrases）— https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-prepare-data-ai
27. ThoughtSpot Spotter — https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter
28. ThoughtSpot Spotter limitations — https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-limitations
29. ThoughtSpot Semantic layer（Spotter semantics）— https://docs.thoughtspot.com/cloud/26.10.0.cl/semantic-layer
30. ThoughtSpot TML — https://docs.thoughtspot.com/cloud/26.10.0.cl/tml
31. ThoughtSpot TML coaching / `nls_feedback` — https://docs.thoughtspot.com/cloud/26.10.0.cl/tml-coaching
32. ThoughtSpot Business terms — https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-business-terms
33. ThoughtSpot AgentQL — https://docs.thoughtspot.com/cloud/26.10.0.cl/agentql
34. ThoughtSpot REST APIs — https://developers.thoughtspot.com/docs/rest-apis
35. dbt semantic models — https://docs.getdbt.com/docs/build/semantic-models
36. dbt MCP available tools — https://docs.getdbt.com/docs/dbt-ai/mcp-available-tools
37. dbt Semantic Layer GraphQL — https://docs.getdbt.com/docs/dbt-cloud-apis/sl-graphql
38. Cube agent config / certified queries — https://docs.cube.dev/admin/ai/certified-queries
39. Cube AI overview（rules/skills/memories/evals）— https://docs.cube.dev/admin/ai/index
40. Cube Bring Your Own Model — https://docs.cube.dev/admin/ai/bring-your-own-model
41. Cube multi-agent — https://docs.cube.dev/admin/ai/multi-agent
42. Cube MCP server — https://docs.cube.dev/docs/integrations/mcp-server
43. Cube REST JSON API query format — https://docs.cube.dev/reference/core-data-apis/rest-api/query-format
44. Cube SQL API — https://docs.cube.dev/reference/core-data-apis/sql-api/index
45. Cube Chat API — https://docs.cube.dev/reference/embed-apis/chat-api
46. Cube AI context（模型内 AI 上下文）— https://docs.cube.dev/docs/data-modeling/ai-context
47. Wren AI MDL schema — https://docs.getwren.ai/oss/reference/mdl
48. Wren AI MCP server — https://docs.getwren.ai/oss/guides/mcp
49. Wren AI architecture — https://docs.getwren.ai/oss/reference/architecture
50. Wren AI question-SQL pairs — https://docs.getwren.ai/cp/guide/knowledge/question-sql-pairs
51. 阿里云 Quick BI 智能小Q（2026-10-31 抓取成功，2026-11-01 重取 TLS 失败）— https://help.aliyun.com/zh/quick-bi/user-guide/smart-q-home-page

**抓取失败/未取到正文（不计入结论）**：`swiftagent.io`、`youdata.163.com`、`guandata.com`（仅营销页）、`help.aliyun.com/zh/gbi/`、`docs.databricks.com/.../agent-bricks/`（仅导航）、`cloud.google.com/looker/docs/conversational-analytics-api`（404）。

原始抓取物：`sources/raw-*.txt`（正文）、`sources/raw-*.html`、`sources/raw-*.links.json`、`sources/source-index.json`（状态码、字节数、时间戳）、`sources/fetch.py`（抓取脚本）。
