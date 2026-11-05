# 自适应 metadata retrieval：商业产品与具名工程实践

访问与研究截止日：2026-10-31。研究问题是：用户从值、列、指标、业务规则或既有分析出发时，系统是否允许沿不同方向发现证据，而不是固定执行“理解 query → 召回表 → 业务逻辑 → 列 → 值”。

## 1. 可以先下的结论

**已有产品和实际部署采用了非单向的组件；公开证据不足以证明某一家已提供完全开放、任意入口、可观察且有充分性保证的双向 metadata planner。** 已经可以核实的做法包括：

1. **值参与 SQL 之前的检索。** Snowflake 对问题与 sample values 做语义搜索，或对维度挂 Cortex Search；Genie 用列代表值和 distinct 值做 prompt matching。这说明值不是只能在选完表列后做一次字面替换。[S1][D1]
2. **按问题选择上下文，并能继续深入实现。** Hex 动态取 guides，按 repository description 决定下载哪个代码库，再找文件/片段；LinkedIn 提供语义搜索、分层索引导航、已知 ID 直取三种入口。[H1][H2][U1]
3. **业务规则是独立检索对象。** ThoughtSpot 将 column semantics 与按题召回的 memory/external context 区分，公开了 scope、ranking、top-K、guardrail 行为。[T1][T2]
4. **执行后仍能补证据。** Genie Inspect 会写更小 SQL 检查过滤值、日期、join 和聚合后修订原查询；Cortex Agents 明确运行 plan–tools–reflect 循环；这已经超出一次 schema recall。[D2][S2]
5. **灵活检索与硬性先决条件共存。** Ramp 的自述是失败 trace 暴露漏读 domain doc 后，强制先读相关文档再分析。业务规则、权限、指标口径的硬约束不必随检索路径自由变化。[U2]

上述第 1 点仍有重要范围限制：**“在已配置维度/列内找值”与“拿一个未知值在全企业倒查其所属列、表、指标”不是同一种能力。** 本次资料对前者有直接证据，对后者未找到上述产品的完整公开契约。

## 2. 证据怎样读

- **D：官方技术文档描述的行为或配置。** 本次读取正文，支持产品契约；没有登录租户实测，也不等于知道内部 agent prompt、每轮检索顺序、重试上限。
- **U：具名组织或工程人员的一手自述。** 支持该案例的流程；不是独立对照实验，也不能代表全部部署。
- **M：效果与愿景表述。** 例如“高质量”“根因”“更准确”不能仅凭文案当作测得结果。
- **I：本报告推断或设计含义。** 不把“系统可以从这些构件搭出某能力”写成“厂商已实现该能力”。

复用此前 [竞品报告](../dataagent-landscape-2026-10-31/01-competitors-and-adoption.md) 和 [用户与案例报告](../dataagent-landscape-2026-10-31/04-user-voices-and-cases.md) 的来源线索；新增读取官方正文并缓存。没有浏览器操作、商业租户登录或第三方代码执行。HTTP 404/连接失败仅记账，不是能力不存在的证据。

## 3. 沿具体检索问题比较

| 需要解决的问题 | 已有直接证据 | 能确认的范围与剩余缺口 |
| --- | --- | --- |
| 用户只给实体值，怎样映射列和值 | Genie prompt matching；Snowflake sample/search literal matching；ThoughtSpot indexed values + column AI Context | D：值可以影响问题解释、列和值选择。Snowflake 搜索服务绑定逻辑维度；Genie 在已加入 agent 的列内配置。未证实全库 `find_value → all owning columns/tables` 接口 |
| 已知列，反找业务指标与计算规则 | Hex reference repo 可查 metric calculations/table structures；LangChain 使用 Hex 追踪字段的 SQL、joins、transformations；LinkedIn profile 包含字段、metric usage、源码证据 | D/U：能按需深入实现。未找到独立的 `metrics_using_column(column_id)` 完整产品契约，不宜把代码搜索称为已有精确反向血缘索引 |
| 问题跨业务域，先选何种数据 | Spotter 3 cross-model relevance/confidence/clarification；Cortex Agents 在配置 Analyst/Search/custom tools 间规划 | D：可动态选语义 model 或工具。不是任意数据库表搜索；仍依赖管理员开放的资产与描述 |
| 何时加载更多 schema/知识 | Genie relevance filters；Hex guide/repo description；LinkedIn summary index→ID fetch；ThoughtSpot relevant memories/external sources | D/U：选择性加载已经存在。公开文本没有统一给出“还缺哪些列/规则”的可观察状态表示 |
| 怎样补齐必要 join 关系 | Genie PK/FK 导入及手工关系；Snowflake relationships、metric `using_relationships`；ThoughtSpot AgentQL→QGen 继承 TML joins | D：有结构化关系与编译路径。**没有足够证据证明 metadata retrieval 必然补齐未召回桥表和完整 join 闭包**；已配置语义模型中的查询编译与检索闭包要分开验收 |
| 失败或怀疑后能否补查 | Genie Inspect；Genie Agent mode 多 SQL；Cortex reflect→另一个工具/澄清/回答；Spotter Deep analysis 的迭代描述 | D：存在继续调查。仅“自动重试”不证明发生了 schema 扩张或业务规则重新检索 |
| 何时停止 | Cortex orchestration time/token limit；Genie “enough evidence”；Spotter confidence/澄清与 top-K；Ramp eval 必要证据 | 只有部分硬预算公开。top-K 是一次上下文裁剪，confidence 用于 source 选择，离线 eval 是验收：都不自动等于运行时证据充分性证明 |

## 4. Databricks Genie / Unity Catalog：列值 grounding、相关性过滤与查询后核验

**D：不是把整个 UC 原样塞进提示词。** Genie concepts 明确说会过滤 example SQL、table/column metadata、chat history，选择最相关上下文；列名和描述也做相关性选择。输入包括 UC comments、PK/FK、author knowledge store、selected-column sample values、函数、全局 instructions 和当前聊天。部分 owner/table size 默认不包含，需要 information schema。这里证实的是选择性上下文，不是已公开的任意 `search/get-schema` 工具 API。[D2]

**D：值能够参与列选择与解释。** prompt matching 官方例子是“Florida”对应存储值 `FL`，避免生成返回空集的 `ILIKE '%Florida%'`。format assistance 给代表值；entity matching 给 distinct 值列表，最多 120 列、每列 1,024 值、每值 127 字符，仅字符串列。原文明确说其帮助匹配“columns and values”。值由作者权限生成并成为共享 context，因此有 row filter/column mask 排除规则和人工 refresh 行为。它是有界、列级的值索引，不能宣传为全企业实体反查。[D1]

**D：业务规则与关系可以结构化。** knowledge store 提供 measures、filters、fields 的 SQL expressions、同义词、使用说明；PK/FK 自动保存为 join relationships，也可指定 many-to-one 等关系。通用文字指令全局生效，局部知识建议放在例题、函数或表列 metadata。作者加入表时，还会搜索其有权限查看、与已加入资产有关的热门 workspace queries，供审核后采纳；不是直接把任意历史 SQL 当真值。[D1][D3]

**D：查询不是终点。** concepts 文档的 Inspect（Public Preview）行为很具体：检查初始 SQL，写更小 SQL 验证过滤值、日期区间、join 与 aggregation；发现缺口则生成改进查询，并比较新旧版本。Agent mode 则建立/修改 research plan、执行多条 SQL、从结果调整，直到“enough evidence”形成报告。Chat mode、标准 Agent mode 与 Flash（Beta）能力和预算不同。[D2]

**事实边界：** 文档“Retries are handled automatically”没有公开错误分类、次数、每次是否重新选表或检索业务规则。Inspect 是显式开启的额外核验能力，不能当作每条 Chat 请求默认执行。UC 元数据、Genie 局部知识和运行时查询结果是不同层；Genie 局部修改不回写 UC。作者仍要选取域内资产，最多 50 个对象，官方建议开始时五张或更少；不能把这一实现写成全 UC 自主探索。[D1][D2][D4]

## 5. Snowflake：把值搜索接入 SQL，再让外层 Agent 自适应选工具

**D：literal 检索在 SQL 生成前发生。** 官方《Improve literal search》说明：回答“iced tea”销售额需要正确过滤值，`LIKE '%iced%tea%'` 可能漏 `Ice Tea` 又误取 `spiced tea`。Analyst 提供两种方案：在 semantic model 的 sample values 上语义搜索，或用 Cortex Search 搜 underlying database column 的 literals。每次只有固定大小的候选值进入 LLM，添加更多 samples 不会直接将全部值塞进上下文。[S1]

**D：按值域性质选择机制。** 文档建议约 1–10 个 distinct 值的低基数维度提供 sample values；高于 10 个或频繁变化的维度挂 Cortex Search。配置把 service 绑定到 logical dimension，可指定 `literal_column/database/schema`；该页仍称 preview，每个维度支持一个 service。它能做语义 value grounding，但流程本身仍预先知道维度，而非任意值找到未知表。该页另明确中国大陆不可用。[S1]

**D：外层 Cortex Agents 是真实的可配置编排。** overview 描述 plan→use tools→reflect；根据工具结果选择澄清、另一个工具或最终回答。工具包括 Analyst（语义 view）、Search（文档）、code、custom UDF/procedure、MCP 等。Search 可动态调整 filters、retrieved columns、result counts、per-index queries 和 time decay。可用 orchestration instruction 指定“refund 问题用 Search”“revenue 用 Analyst”，这比固定链更接近按问题选择证据。[S2][S3]

**D：指标与 join 的约束来自语义对象。** semantic view 定义 dimensions、facts、metrics、relationships；维度可标 `is_enum`，为真时过滤值限定于 `sample_values`。跨表 derived metrics、非加性维度以及多路径 metric 的 `using_relationships` 可编码业务约束，后者在本次文档标 Preview。由结构化语义提供关系，并不说明 agent 每轮 metadata recall 自动完成最小 join 闭包。[S4]

**D：公开了预算停止，但不是充分性保证。** agent orchestration 可指定 seconds/tokens，达到任一上限停止；token limit 仅算 orchestration，不包括 Analyst/Search 等工具 token。Analyst query 还可单独设 warehouse query timeout。因此要区分“预算耗尽”“工具完成”和“答案证据充分”。官方公开了前两类参数，未给出第三类的普适形式化判定。[S3]

## 6. ThoughtSpot：agentic context、跨 model 选择与受约束编译

**D：四类 context 的加载方式不同。** instructions 为每题 always；column synonyms、AI Context 等 semantics 在作用域内；memory/business logic 按题相关性取回；Slack/Confluence/SharePoint 等外部知识按相关性搜索。官方 retrieval 文档明确称 agent actively steers retrieval，流程是：scope 先过滤→按 relevance/scope/source/recency 排序→top-K 给 agent，其余记录；guardrails 不走排名，总是包含；实时日期与 freshness 实时读。[T1][T2]

**D：列和值是一个可配置语义入口。** AI Context 绑定 model column，利用 column name、description 和 indexed values 自动生成；可以写“Metoprolol 存为 MP”、默认使用 Order Date、特定过滤等。attribute indexing 让系统看见实际值。它有 400 字符上限，重新 Generate 会覆盖人工编辑，且不回写物理表。这里可以证明 value conventions 进入列解释，不能据此证明全库 value→table 反查工具。[T3]

**D：跨域 source 选择不是用户先选一张表。** Spotter 3 cross-model search（opt-in）会依据 metadata、descriptions、Liveboards/Answers 给可访问且 Spotter-enabled models 打 relevance/confidence；高置信度继续，同名 Revenue 跨 Sales/Finance 则澄清。追问可以从客户 usage 转到 tickets，保留实体/日期；可并行查询 CRM 和 Support 后综合。限制包括英语、跨 model 综合结果当前为文字摘要；多 model 手选仍标 Beta。[T4]

**D：灵活路径有语义编译边界。** AgentQL 技术文档说 agent 可选 TML tokens、AgentQL 或 Python。AgentQL 是 TML worksheet/model 列上的中间查询，由 QGen 确定性编为 SQL，继承 joins、RLS/CLS、custom calendar、column definitions。确定的是给定语义查询的编译；不能由此说自然语言解释、model 选择和所有检索步骤都确定。该文还带分期 rollout 限制。[T5]

**D/M 边界：** Deep analysis 文档描述更大 reasoning budget、multi-step plan、iterative querying/validation/cross-reference，且 anomaly 后修正 subqueries；这是官方产品行为描述，但“until grounded conclusion”“root cause”没有公开停止阈值或因果方法。context ranking 也没公开 K 值、权重、重复检索触发条件。不能把“agentic RAG”几个字当作已知完整调度算法。[T2][T6]

补充：传统 Search suggestions 甚至可推荐 out-of-scope columns，选中后扩大 data source scope；这是 UI Search 的明确行为，**不自动代表 Spotter agent 使用相同扩展策略**。[T7]

## 7. Hex：按需业务指南、代码库深入与真实使用

**D：在 broad rules 与 task context 之间分配预算。** `hex.md` workspace context 每次包含；guide library 动态按 relevance 取回，frontmatter name/description 帮助选择；guide 可 mention 既有 project，取回 guide 后 agent 可继续使用该 project。不是每题都加载全部业务知识。[H1]

**D：需要更深含义时能读实现。** reference repository 配置包括 branch/description。提交问题后，agent 先由 descriptions 判断哪些 repos 相关，再下载到 thread，定位相关 files/sections，用于 metric calculations、table structures、feature event logging。用户可直接点名 repo，也可在 guide 映射 metric/domain 到 repo。[H2]

**D：可信来源与可访问来源有分别。** Governed mode 可选择 warehouse data、semantic models、projects 的 trusted source 组合；关闭时仍优先 endorsed assets。官方明确它不是 security control，安全靠 connection permissions；semantic-models-only 路径不直接 query warehouse tables，也不取其它 project context，但可用 SQL/Python 进一步计算取回结果。它约束检索可选集，不能作为检索必然正确的证明。[H3]

**U：LangChain 的部署体现了跨层查询，而非只查模型。** 客户文章说 Hex agent 可从业务级 context 深入 dbt repo，阅读某列/指标的完整 SQL、joins、transformations 和来源；dbt 定义、semantic models、workspace guides、endorsed assets、历史项目共同供给 context。数据团队从 warnings、重复问题、错来源中维护定义/guide/endorsement。文章没有披露每题工具顺序与停止条件，也明确把正式 evals 写为后续工作。[U3]

**事实边界：** 这些证据支持“按需深入代码与业务上下文”，没有公开列级倒排索引、value search、join closure 的精确 API，也没有统一失败后扩 schema 的契约。不能把客户能追字段 SQL 等同于产品已有完备 column→metric graph。

## 8. LinkedIn：最直接的按需 context 导航工程证据

**U：公开的是内部 context 服务与工具机制。** 具名工程原文说：MCP tools 支持 asset discovery、context retrieval、index navigation；team context 可 embedding semantic search 或浏览 indexes；已知 document ID 可直接 fetch。`navigate team index` 按 repository/org/team/section 返回 summary 与 children map，agent 选择相关分支再调用；确定文档后用 `fetch team context` 取全文。已知 team/section 可从那里开始，不需要每次从根走。[U1]

**U：同一 asset ID 汇合生成资料与人审规则。** 一个 fetch 同时返回 schema/source/query-log enriched profile 与 curated guidance；profile 含 purpose、fields、join keys、representative queries。人工资料覆盖 business definitions、exceptions、required filters、grain、data-quality caveats，并用 Git PR/owner review 维护；自动刷新不覆盖人审纠正。global/team/analysis 三层可表达规则适用范围。[U1]

**U：值与查询日志是 enrichment 信号。** 默认五行脱敏 samples；selected dimensions 做近期分区或有界抽样的频率 profiling；query logs 规范化后归纳常见 join/filter，另读 Spark/Airflow/dbt/metric source。**这是离线生成 context 的材料，并不自动证明运行时提供跨库 value lookup。** 同理，index tree 递进披露是可观察导航契约，文章未公开通用 online planner 如何识别所有遗漏或决定收齐证据。[U1]

这个案例最值得复用的是“summary 发现→稳定 ID 精取＋可跳入中层＋语义搜索可替代导航＋一取合并已审核规则”；不是复制它离线 enrichment 的 nomination→collection→generation→persistence 当成新的固定在线问答流水线。

## 9. Ramp：用必要证据约束灵活调查

**U：数据资产有面向 agent 的读取形态。** Ian Macomber 介绍 Ramp 内部 BI 同时给人 React 界面，给 agent Markdown、可取 SQL 与 cached CSV；research harness 知道如何读这些资产。失败 trace 常漏 domain doc、选错表/metric/filter，所以他们把读 domain doc 设为分析前必要动作。[U2]

**U：验收约束证据，而非只有答案数字。** 其 interface×model 检查包含 metric definition、数值容差、authorization outcome、required evidence；normalized trace 记录 READ_DOMAIN_DOC/VIEW_DASHBOARD/READ_SEMANTIC_VIEW/EXECUTE_SQL 等，并快照 model/prompt/tools/code/eval corpus/knowledge hashes，便于定位缺失上下文。它支持“有条件的自由路径”：先满足业务必需证据，再允许调查，不说明所有问题必须同一工具序列。[U2]

**U：不是所有需求都靠 online retrieval。** Gong calls 上 `loss_reason/objection_type/mentioned_competitor` 被离线版本化提取为可聚合字段；观察问题后决定把什么字段提升为共享模型。这说明值、列、规则索引也可由长期需求反向塑造。[U2]

**事实边界：** 原文是从业者自述，未公开 harness 全部代码、样本量、成功率或 online stop policy。跨入口 consensus 不能排除一致地出错；必要证据必须指向经过审核的业务结果与来源。不能把作者“assume models are never wrong”当作模型不会出错的事实。

## 10. 对设计讨论最有用的分层（I）

这些材料支持把“固定流水线是否太僵硬”拆为三件事：

- **可走哪些边：** query/value/column/metric/document/project/repo 均可作为发现入口；sample matching、semantic search、summary navigation、ID fetch、代码读取和 SQL probe 是不同工具。
- **哪些证据必须齐：** scope/权限、指标定义、filter、grain、join path、time semantics 等应是任务相关的必要条件；不应仅因换了入口就略过。
- **谁决定下一步和结束：** planner 可动态选择工具；预算是硬停止；缺失定义/歧义应澄清；已完成证据检查才允许回答。最后一条是建议，不是上述产品都已公开实现的统一保证。

因此有据可依的路线是“多入口发现＋按需扩充＋结构化业务约束＋执行后补证据”，而不是把所有检索都交给一段没有可观察状态的 agent prompt。商业产品已经提供这套路线中的多个部件；全局值反查、精确 column→metric 逆向关系、必要 join 闭包和充分性停止仍需单独设计与验证。

## 11. 来源账本与读取层次

全部访问日为 **2026-10-31**。`F` 表示本轮 HTTP 取得正文并读相关章节；`R` 表示复用同日 landscape research 成功缓存，本轮读正文；都不是商业租户实测。未标正式发布日期的动态文档只按访问时版本引用。全文及访问失败保存在 [products-source-index.json](sources/products-source-index.json)，缓存仅使用 `sources/products-*`。

| ID | 来源及类型 | 本次读取与关键支持 |
| --- | --- | --- |
| D1 | [Genie tune quality](https://docs.databricks.com/aws/en/genie-agents/tune-quality)，D | R；prompt matching、值限额、安全/刷新、SQL expressions、join、knowledge mining；`products-genie-tuning.*` |
| D2 | [Genie concepts](https://docs.databricks.com/aws/en/genie-agents/concepts)，D | F；页面显示 Last updated Oct 30, 2026；relevance filtering、Inspect、Chat/Agent/Flash、自动 retries；`products-genie-concepts.*` |
| D3 | [Genie set up](https://docs.databricks.com/aws/en/genie-agents/set-up)，D | R；popular workspace query suggestions 范围与权限；`products-genie-setup.*` |
| D4 | [Genie best practices](https://docs.databricks.com/aws/en/genie-agents/best-practices)，D | F；小域、50对象上限、建议五表、instruction 分工；`products-genie-best-practices.*` |
| S1 | [Improve literal search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/cortex-analyst-search-integration)，D | F，官方 `.md` 正文；SQL前sample/search、固定候选大小、每维度service、地域/preview提示；`products-snow-search-integration.md` |
| S2 | [Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)，D | F，官方 `.md`；plan/tools/reflect、可动态调 Search 参数；`products-snow-agents.md` |
| S3 | [Manage Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage)，D | F，官方 `.md`；tool resources/descriptions、routing instructions、time/token预算与query timeout；`products-snow-manage.md` |
| S4 | [Semantic view YAML](https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec)，D | F，官方 `.md`；is_enum、dimension搜索、metrics/relationships、using_relationships preview；`products-snow-semantic-yaml.md` |
| T1 | [How Spotter uses context](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-how-spotter-uses-context.html)，D | F，版本26.10；四类context与加载方式；`products-spotter-context.*` |
| T2 | [Context retrieval and ranking](https://docs.thoughtspot.com/cloud/26.10.0.cl/context-layer-rag.html)，D | F；agent steering、scope/rank/top-K、guardrails、live facts；`products-spotter-rag.*` |
| T3 | [AI Context](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-ai-context.html)，D | F；indexed values、column scope、覆盖/字符限制；`products-spotter-ai-context.*` |
| T4 | [Cross data model search](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-cross-model.html)，D | F；Spotter3 opt-in、model ranking/confidence/clarification、并行和限制；`products-spotter-cross-model.*` |
| T5 | [AgentQL](https://docs.thoughtspot.com/cloud/26.10.0.cl/agentql.html)，D | R；tokens/AgentQL/Python选择、QGen语义编译与分期限制；`products-spotter-agentql.*` |
| T6 | [Search and Deep analysis](https://docs.thoughtspot.com/cloud/26.10.0.cl/spotter-research-mode.html)，D，效果未独立验证 | F；工具集共用、reasoning budget、迭代描述；`products-spotter-research.*` |
| T7 | [Search suggestions](https://docs.thoughtspot.com/cloud/26.10.0.cl/search-suggestion.html)，D | F；传统Search UI的out-of-scope column扩展；不外推Spotter调度；`products-spotter-search-suggestion.*` |
| H1 | [Hex Guides](https://learn.hex.tech/docs/agent-management/context-management/guides)，D | F；always hex.md、dynamic guides/frontmatter、project mentions；`products-hex-guides.*` |
| H2 | [Hex reference repositories](https://learn.hex.tech/docs/agent-management/context-management/reference-repositories)，D | F；description→repo download→files/sections；`products-hex-reference-repositories.*` |
| H3 | [Hex Governed mode](https://learn.hex.tech/docs/agent-management/governed-mode)，D | R；source scope、semantic-only、非安全边界；`products-hex-governed.*` |
| U1 | [Inside LinkedIn’s data context layer](https://www.linkedin.com/blog/engineering/infrastructure/inside-linkedins-data-context-layer-curating-trustworthy-context-for-humans-and-agents)，U | R；2026-10-09具名工程原文全文；MCP navigation/semantic search/ID fetch、generated与curated层；`products-linkedin-context.*` |
| U2 | [The Shape and Feel of the Post-AI Data Stack](https://www.iandmacomber.com/blog/post-ai-data-stack)，U | R；2026-08-30从业者原文全文；Ramp资产、domain-doc先决条件、trace/eval及离线提取；`products-ramp.*` |
| U3 | [How we built LangChain’s agent-first data stack](https://www.langchain.com/blog/agent-data-stack)，U | R；2026-07-27客户原文全文，存在厂商合作；dbt实现追踪与维护；`products-langchain-hex.*` |

补充读取但未用于主结论的全文包括 Snowflake analytical search/semantic SQL、ThoughtSpot context layer/sources、Hex context management/endorsements/models。错误链接与访问失败也保留在索引；如 UC search 猜测路径404、两个 ThoughtSpot 猜测路径404，不将这些失败写成能力结论。
