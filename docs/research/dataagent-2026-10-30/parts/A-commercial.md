# 商业 Data Agent / 语义层 + NL2SQL 实现形态调研（截至 2026-10-30）

> 方法说明：本次环境无 web_search（无 API key），全部结论来自直连官方文档/官网（curl/web_fetch，2026-10 抓取）。**未能访问任何第三方评测榜单（BIRD / Spider2.0 / 公开 leaderboard）**，因此本文所有「准确率」相关内容均为**官方宣称的评测机制**，不含可核对的公开分数；凡未抓到原文的写「未核实（2026-10 环境无搜索）」。

## 1. 执行摘要

2025–2026 年商业 Data Agent 已收敛为三种可辨识形态：**语义层优先**（Snowflake Semantic Views、dbt、AtScale、Cube、Kyligence）、**catalog + agent 生成式**（Databricks Genie、Fabric data agent、BigQuery data agents）、**BI 内嵌 Copilot**（Power BI Copilot、ThoughtSpot Spotter、Sigma Assistant）。共同趋势有四点：语义资产从「BI 模型」升格为「数据库内一等对象（YAML/DDL 可版本化）」，并被 Agent 直接消费；召回从「表/字段」细化到**值级**（实体匹配、格式采样），且与行级/列级权限强耦合；建模自动化停在「建议 + 人工确认」（PK/FK 自动成 join、点赞反推指标）；准确率治理从「宣称一个数字」转为**内置 benchmark 包**（gold SQL 对比 / LLM judge）。公开定价仍少见，多为 credit 或按席位，Databricks 是少数公开 Genie 计费节奏的厂商。对 MintHub 而言，语义层应当是可打包、可版本化、可被外部 Agent 消费的资产，而非某个 App 的内部配置。

## 2. 厂商对比大表

| 产品 | 形态/入口 | 语义层 | 探查建模自动化 | NL2SQL 评测 | 分析预测 | 治理 | 定价 | 关键时间 |
|---|---|---|---|---|---|---|---|---|
| Databricks Genie（One / Agents / Code） | 聊天 + 嵌入 + Conversation API + 移动端 | Agent 级 knowledge store（≤200 片段）+ UC 函数；**不写回 UC** | PK/FK 自动成 join；点赞/下载反推指标与 join 建议 | 内置 benchmark ≤500 题，结果集比对或 LLM judge；无公开分数 | 结果表/可视化/CSV；预测需自建 | UC 权限；行过滤/掩码表禁用实体匹配 | Genie Code 按量计费（2026-07-08 起）；One/Agents 免费至 2027-01-31 | 2026 年 Genie Spaces 更名 Genie Agents；Genie One 账户级 |
| Snowflake（Semantic Views / Cortex Analyst / CoWork） | SQL 对象 + REST API + CoWork 应用 + 移动端 | **Schema 级对象**，YAML 规范，逻辑表/fact/metric/dimension/关系 | Autopilot AI 向导，可上传 YAML / Tableau / Power BI 文件；Studio 内 CoCo 对话式编辑 | 未核实公开分数；走 Analyst REST API | CoWork 内置代码执行工具、文档生成（PDF/Word/PPT/HTML） | 对象级权限、listing 共享、Marketplace | credit 计费（单价未核实） | Snowflake Intelligence 已更名 **Snowflake CoWork** |
| Microsoft Fabric data agent | 聊天 + M365 Copilot + Copilot Studio/Foundry 调用 | 复用 Power BI 语义模型 / lakehouse / ontology 源 | 选表 + 指令 + 示例查询（每源≤100 条）；无自动 join 发现 | 官方称跨公共/私有数据集评测，无数字 | 只读；输出≤25 行×25 列 | 用户身份 + Purview DLP/审计；RLS/CLS 生效；Git + 部署管道 | 含于 F2/P1 容量 | data agent **GA**；独立 Power BI agent 仍 Preview |
| Google BigQuery conversational analytics | 聊天 + data agent | 自建 data agent（数据源+元数据+指令） | Agent 自动生成数据源定义与元数据，再人工调 | 未核实 | 图表/探索 | 继承 BigQuery 权限 | 未核实 | data agent + verified queries（原 golden queries） |
| ThoughtSpot Spotter 系列 | 聊天 / Liveboard / Slack / Teams / 嵌入 | Spotter semantics + context layer（RAG 检索排序）+ memory | SpotterModel：原始数据分钟级成模型 | 官方称「关系型搜索」高准确率；有 benchmark 平台，无公开数字 | SpotIQ 预测/异常检测 | 行级安全、memory 权限 | 未核实 | Spotter Agent（Spotter 2）新 agent 平台 |
| Tableau（Semantics / Agent / Pulse） | BI 内 Copilot + 语义层 | Tableau Semantics 并入 Salesforce Data 360，含 agent enrichment | 未核实 | 未核实 | Pulse 指标监测（细节未核实） | 继承 Salesforce/Tableau 权限 | 打包在 Tableau+ | Tableau Semantics 属 Tableau Next |
| Qlik Answers | 助手 + 自定义 skills | 未核实 | 未核实 | 未核实 | 无（偏知识/决策辅助） | 未核实 | 未核实 | 主打「小时级上线」 |
| AWS Quick（原 QuickSight） | 聊天 + 仪表板内 agent | 复用 QuickSight 语义模型 | 未核实 | 未核实 | agentic analysis + what-if 场景 | 继承 IAM/Q 权限 | 按用户/容量 | 更名 Quick，内置 research/automation agent |
| Palantir（Ontology / AIP） | 应用 + AIP Logic / Chatbot Studio | **Ontology**：object/link/action/function/interface 类型 | Ontology 建模为主，AI 辅助有限 | AIP Evals 做评测，无公开分数 | 函数/Python/模型编排 | 分支 + 提案评审、项目级权限 | 平台授权（未核实） | AIP Agent Studio 更名 Chatbot Studio |
| AtScale | 语义层中间件 + 任意 LLM/BI | 通用语义层，问题先落到「唯一指标」再生成 SQL | Semantic Model Copilot 辅助建模 | 官方称 NL→语义层「最可靠」，无数字 | 交给下游 BI | 继承仓库权限；Snowflake Native App | 未核实 | 为 Snowflake Semantic Views 提供 XMLA 端点（厂商宣称） |
| Cube | 语义层 + 嵌入式分析 | 中心语义模型（含预聚合） | Workbook/Dashboard Agent 对话式建查询 | 未核实 | 工作簿 + 图表 | 多租户、权限继承 | 未核实 | 定位「agentic analytics platform」 |
| dbt Labs | 语义层 + API + **dbt MCP Server** | YAML 定义 metric/semantic model，版本受控、带血缘 | 手工建模为主 | 未核实 | MetricFlow 查询改写/缓存 | Git 版本化 + 权限 | 按席位/模型（未核实） | 主打 ADLC + dbt Insights |
| Kyligence | 指标平台 + AI Copilot | 统一语义层（Zen） | 低代码建指标 + 预置指标模板 | 未核实 | Excel 探索、AI 洞察 | 未核实 | 未核实 | Zen 低代码指标平台 |
| Sigma | 工作簿 + Assistant + Agents | 依赖仓库内语义模型 | 未核实 | 未核实 | 回写仓库、阈值监控触发工作流 | 继承仓库安全 + 不可变审计 | 未核实 | **双向 MCP client/server** |
| Dataiku | Agent 全生命周期平台 | 复用其数据/模型资产 | 未核实 | 未核实 | 全代码 + 模型 | 成本/质量/风险管控 | 未核实 | 主打企业级 agent 治理 |

未核实、故不入表：SAP Joule for Analytics、Oracle、C3 AI、Starburst、Dremio、Alteryx、Omni、Hex（本次均未抓到可引用原文）。

## 3. 分厂商要点

**Databricks（Genie 家族）**
- 已从单一 Genie Space 拆成三件套：面向业务用户的 Genie One、面向数据团队的 Genie Agents（原 Genie Spaces）、面向开发的 Genie Code，三者共用 Unity Catalog 底座 [来源](https://docs.databricks.com/aws/en/genie/)。
- 语义层不在 UC 里，而在 **Agent 级 knowledge store**：表/列描述、同义词、join 关系、SQL 表达式（measure/filter/field），上限 200 条片段、100 条指令，且明确「不影响 UC 元数据」[来源](https://docs.databricks.com/aws/en/genie-agents/tune-quality)。
- 建模自动化已落地一半：读取 UC 主外键**自动存成 join 关系**，并从作者点赞/下载行为中反推可新增的指标与 join 建议 [来源](https://docs.databricks.com/aws/en/genie-agents/tune-quality)。
- 值级召回做得最细：format assistance 采样代表值、entity matching 支持至多 120 列 ×1024 个 distinct 值；**带行过滤或列掩码的表禁止开启**，这是一条重要的治理约束 [来源](https://docs.databricks.com/aws/en/genie-agents/tune-quality)。
- 评测内建为产品能力：每 Agent ≤500 题，Chat 模式比对结果集（5000 行、4 位有效数字容差），Agent 模式交给 LLM judge [来源](https://docs.databricks.com/aws/en/genie-agents/monitor)。
- 计费：Genie Code 自 2026-07-08 起按量计费（含每用户月度免费额度），Genie One/Agents 免费至 2027-01-31（服务主体除外）[来源](https://docs.databricks.com/aws/en/genie/)。

**Snowflake（Semantic Views → Cortex → CoWork）**
- 语义层是**数据库对象**：CREATE SEMANTIC VIEW，逻辑表 + fact/metric/dimension + 关系，可被 SELECT 直接查询，也被 Cortex Agents/Analyst 当工具消费 [来源](https://docs.snowflake.com/en/user-guide/views-semantic/overview)。
- 建模型有两条自动化路径：Autopilot AI 向导（还能直接上传 YAML、Tableau 文件、Power BI 文件做迁移），以及 Semantic Studio 里 CoCo 的对话式编辑 [来源](https://docs.snowflake.com/en/user-guide/views-semantic/overview)。
- 语义视图可作为 listing/Marketplace 商品共享，等于「语义层可分发」[来源](https://docs.snowflake.com/en/user-guide/views-semantic/overview)。
- Snowflake Intelligence 已更名 **Snowflake CoWork**：开箱即用的 agentic 应用，含 data agents、code execution 工具、文档生成（PDF/Word/PPT/HTML，可上传模板）、skills、iOS 客户端、extended thinking 与 agentic exploration 两种推理档 [来源](https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-cowork)。

**Microsoft（Fabric data agent / Power BI Copilot）**
- Fabric data agent 已 **GA**，最多接 5 个源（lakehouse、warehouse、KQL、Power BI 语义模型、**ontology**、Graph），按源类型分别走 NL2SQL / NL2DAX / NL2KQL [来源](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)。
- 治理分层写得很明确：组织意图 > 角色意图 > 开发者意图 > 用户意图，逐级覆盖；只读、用调用者身份取 schema、Purview DLP/审计/eDiscovery 生效 [来源](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)。
- ALM 是差异化：配置可 Git 版本化，可用部署管道在 dev/test/prod 间迁移 [来源](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)。
- 硬限制：回答上限 25 行 × 25 列、每源 ≤100 条示例查询、不可换模型、暂不支持非英文、不支持非结构化文件——说明它被定位成「对话式洞察」而非取数工具 [来源](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)。
- Power BI 侧：报表内 Copilot 面板已 GA，独立全屏 Power BI agent 仍为 Preview [来源](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-introduction)。

**Google Cloud（BigQuery conversational analytics）**
- 形态是「创建 data agent」：agent 自动定义数据源与元数据，再由人补 context/instructions 与 verified queries（旧称 golden queries）[来源](https://docs.cloud.google.com/bigquery/docs/conversational-analytics)。
- 官方建议先接受 agent 自动生成的定义再微调，等于把「探查」交给模型、把「校准」留给人 [来源](https://docs.cloud.google.com/bigquery/docs/conversational-analytics)。

**ThoughtSpot（Spotter 家族）**
- 已按任务拆分：Spotter（问答）、SpotterModel（原始数据分钟级成模型）、SpotterViz（自动搭 Liveboard）、SpotterCode（IDE 内）[来源](https://docs.thoughtspot.com/cloud/latest/)。
- Spotter Agent（Spotter 2）跑在新 agent 平台上；底下是关系型搜索 + context layer（检索与排序走 RAG）+ 可从 Liveboard/对话沉淀的 memory [来源](https://docs.thoughtspot.com/cloud/latest/spotter.html)、[来源](https://docs.thoughtspot.com/cloud/latest/)。
- 官方宣称「内置 benchmark 平台」用于持续校准，未给出公开准确率数字 [来源](https://docs.thoughtspot.com/cloud/latest/)。

**Salesforce / Tableau**
- Tableau Semantics 定位为「AI 注入的语义层」，并入 Data 360，强调 agent enrichment 与受治理的复用模型/指标，属 Tableau Next 与 Tableau+ 打包 [来源](https://www.tableau.com/products/tableau-semantics)。
- Tableau Agent / Pulse 的具体能力与 GA 状态：未核实（官网页面本次未抓取成功）。

**Qlik / AWS**
- Qlik Answers 是「agentic AI 助手」，强调自定义 skills、agentic reasoning 拆解复杂问题、小时级上线；未见数据探查或语义层细节 [来源](https://www.qlik.com/us/products/qlik-answers)。
- QuickSight 已更名 **Quick**，主打内置 research/automation agent、对话式探索、what-if 场景与 40+ 应用集成 [来源](https://aws.amazon.com/quicksight/)；QuickSight Q 的独立能力与计价未核实。

**Palantir（Ontology / AIP）**
- Ontology 是比「语义层」更重的本体：object/link/action/function/interface 类型齐备，且有 **Ontology 分支 + 提案评审**机制，是本文所见最接近「语义层 PR 流程」的实现 [来源](https://www.palantir.com/docs/foundry/ontology/overview/)。
- Agent 侧工具链为 AIP Logic、AIP Chatbot Studio（原 AIP Agent Studio）、AIP Evals，全部构建在 Ontology 之上，并有 ontology-augmented generation 与语义检索 [来源](https://www.palantir.com/docs/foundry/aip/overview/)。

**语义层独立厂商（AtScale / Cube / dbt / Kyligence）**
- AtScale：自然语言问题先解析成**唯一指标**再生成 SQL，Semantic Model Copilot 用 AI 协助建模；以 Snowflake Native App（SPCS）交付，并为 Snowflake Semantic Views 提供 XMLA 端点（厂商宣称）[来源](https://www.atscale.com/)。
- Cube：自我定位「建立在语义层之上的 agentic analytics 平台」，Analytics Chat / Workbook Agent / Dashboard Agent 全部对同一语义模型取数，靠预聚合与缓存做亚秒响应 [来源](https://cube.dev/)。
- dbt：指标即代码（YAML）、版本受控且带血缘，MetricFlow 负责查询改写与缓存，并提供 **dbt MCP Server** 供外部 agent 消费 [来源](https://www.getdbt.com/product/semantic-layer)。
- Kyligence：Zen 低代码指标平台 + AI Copilot + 统一语义层，指标可推给任意 BI/SaaS [来源](https://www.kyligence.io/)。

**两处值得记录的旁证**
- 开放标准：`github.com/open-semantic-interchange` 组织确实存在，但**实测该组织下无公开仓库**（2026-10-30），OSI 规范文本与采用情况未核实 [来源](https://github.com/open-semantic-interchange)。
- Sigma 是唯一明确宣称**双向 MCP**（既作 client 又作 server）的 BI 厂商，agent 动作可回写仓库并留不可变审计 [来源](https://www.sigmacomputing.com/product/ai)。

## 4. 三条典型架构路线

**A. 语义层优先（Snowflake / dbt / AtScale / Cube / Kyligence）**
Agent 只负责「业务术语 → 指标/维度」的解析，SQL 由语义层编译。优点：口径唯一、聚合正确、可审计、跨工具复用，且语义层本身可被任意 agent 当 API 消费。缺点：建模是重人力前置投入；对「语义层没覆盖的探索型问题」几乎无解；语义层与物理表的漂移需要额外治理。

**B. Catalog + Agent 生成式（Databricks Genie / Fabric data agent / BigQuery data agents）**
以元数据 RAG + few-shot 示例 + 执行验证为核心，模型直接写 SQL/DAX/KQL。优点：接入快、覆盖面广、能回答长尾问题；Databricks 还内置了值级召回与 benchmark。缺点：非确定性明显（官方文档自己承认）、必须靠人工反馈和 benchmark 闭环维持质量；Fabric 的 25 行上限说明这条路线的产品化边界仍在「洞察」而非「取数」。

**C. BI 内嵌 Copilot（Power BI Copilot / Spotter / Sigma Assistant / Tableau Agent）**
复用既有 BI 语义模型与权限体系，在报表/工作簿里加一层问答。优点：分发零成本、天然继承 RLS、用户已在场。缺点：上限被 BI 语义模型质量锁死；输出形态受宿主限制；跨源问题难处理。

现实中的赢家是 **A+B 混合**：用语义层兜住「必须对」的核心指标，用生成式兜住长尾，再用 benchmark 与反馈把长尾逐步沉淀回语义层（Genie 的 knowledge mining 就是这条沉淀通道）。

## 5. 对 MintHub DataAgent 的启示

1. **语义层要成为一等包资产**：单独一个 kind（如 `semantic-model`），YAML 为源、Git 语义的版本与 diff，并保留「分支 + 提案评审」形态（Palantir 的 ontology branching 是最接近的参照）[来源](https://www.palantir.com/docs/foundry/ontology/overview/)。
2. **必须能导入既有资产**：Snowflake Autopilot 支持上传 YAML / Tableau / Power BI 文件做迁移，说明企业不会从零建模；MintHub 的导入器应把 Tableau/PBI/dbt 三处作为首批目标 [来源](https://docs.snowflake.com/en/user-guide/views-semantic/overview)。
3. **召回做成三层且权限感知**：表/字段（元数据 RAG）→ 值（entity matching / 格式采样）→ 指标（先解析到指标再生成 SQL）。Databricks 在带行过滤/掩码的表上直接禁用实体匹配，这条约束应在编译期而非查询期实现 [来源](https://docs.databricks.com/aws/en/genie-agents/tune-quality)。
4. **建模自动化只做「建议 + 人工确认」**：PK/FK 自动成 join、从点赞与导出反推指标，最后落成待审提案——这是目前唯一被验证可持续的自动化水位 [来源](https://docs.databricks.com/aws/en/genie-agents/tune-quality)。
5. **benchmark 包是交付物的一部分**：问题集 + gold SQL + 判定规则（结果集比对、有效数字容差、LLM judge 兜底 agent 模式）应随 App/Preset 一起打包，作为回归测试跑 [来源](https://docs.databricks.com/aws/en/genie-agents/monitor)。
6. **即席文件不能是二等公民**：Genie 支持本地 CSV/Excel 与 UC 数据混答，Fabric 明确要求先入表——前者体验更好，后者治理更稳；MintHub 可两者并存（探查期直读、生产期入湖）[来源](https://docs.databricks.com/aws/en/genie-agents/)。
7. **function 与语义层解耦**：预测/统计/表格操作应声明为 tool（可指向 Python 执行或仓库侧函数），语义层只管口径；Snowflake CoWork 把代码执行与文档生成都做成 agent 工具，说明「交付物生成」是刚需而非附加项 [来源](https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-cowork)。
8. **MCP 双向是差异化窗口**：Sigma 已同时做 client 与 server，Databricks 的 MCP 连接器仍是 Beta——MintHub 的 `mcp` kind 天然适配，应让语义层既「可被外部 agent 调用」又「能调用外部工具」[来源](https://www.sigmacomputing.com/product/ai)、[来源](https://docs.databricks.com/aws/en/genie-agents/)。
