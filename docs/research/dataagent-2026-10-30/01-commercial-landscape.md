# DataAgent 商业竞品与一手证据

调研日期：2026-10-30，Asia/Shanghai。定位前提：DataAgent 是 MintHub 上组合多个模块的 bundle / preset / app，覆盖即席文件分析、企业多源探查、业务语义、检索取数、BI 与深分析。

## 1. 阅读边界

- 本文实际抓取并阅读官方文档和产品页，未登录任何商业租户，未运行其服务或测试 SQL 正确率。
- `D`：官方技术文档明确说明；`M`：官方产品营销宣称；`I`：基于证据的设计推论。D 仍不是独立实测。
- 未抓取商业服务源码，因此本文没有“闭源实现已由代码证明”的结论；官方示例代码仅证明接口与配置形态。
- 下文“未证实”表示本次资料没有支持，不能解释为产品必然没有该能力。
- 网页为持续更新的现行页面；记录抓取时的内容，页面更新时间不能直接当成功能发布日期。
- 本文不从旧名消失、目录变化或页面无 Preview 标签推导全面迁移、全面 GA 或所有地区可用。
- 研究重点是九个代表实现；dbt / Cube 是语义执行参照，观远是中国市场补充证据。

## 2. 最值得采用的结论

1. 可信分析的共同基础是可治理的语义资产：实体、粒度、指标、关系、同义词、例题与权限。单纯把 schema 塞进上下文不够。[S1][S3][D2][L1][A2]
2. “自动理解”正在增加，但公开证据仍有明确边界：自动读取元数据、搜索历史 SQL、推荐关系与定义，和人工接纳、配置、评测同时存在。[D2][D3][A2]
3. 表检索、字段检索、值检索应分开设计。Looker 有字段元数据、100 值采样与 fuzzy search；Snowflake 将低基数样本与高基数 Search 服务分开；Genie 有 format assistance 与 entity matching。[L1][S4][D2]
4. 需要同时存在受约束查询路径和开放探索路径。Looker / dbt / Cube 让语义执行器编译 SQL；Hex / Cortex Agents 通过 Python 和多步工具补足复杂分析。[L1][B2][C1][H2][S2]
5. 文件与仓库开始融合。Genie 文档已经明确 CSV / Excel / PDF 与 Unity Catalog 表同会话分析；Quick BI 文档展示 Excel 即席分析；Fabric data agent 则明确要求文件先暴露成表。[D4][A1][F1]
6. 学习闭环的可复用单位是经审阅的语义变更和回归用例。普通点赞、单次成功 SQL、聊天记忆不能直接升级为全企业业务事实。[D2][D5][S5][H4]
7. 预测必须区分“生成一段分析代码”“调用已注册预测函数”“有回测和误差度量的正式预测产品”。本次能证实多家提供预测入口，不能证实统一的统计可靠性。[T1][A3][R1]

## 3. 九个代表实现

| 实现 | 核心资产与取数路径 | 自动化与人工边界 | 对 DataAgent 最直接的启发 |
| --- | --- | --- | --- |
| Snowflake Cortex | Semantic Views + Analyst；Agents 编排 Search、Python、图表、自定义工具 | 明确定义逻辑表、指标与关系；值检索与优化建议自动化 | 原生语义对象与 agent 工具分层；评测结果集而非仅比较 SQL 字符串 |
| Databricks Genie | Unity Catalog 资产 + agent 局部 knowledge store + SQL / functions | 元数据、历史查询、作者反馈可产生建议；作者审阅配置 | 自动探查到候选资产，再经过审核发布；文件与企业数据融合 |
| Looker | LookML Explore + 字段 / 过滤 / 排序 / limit 计划 | 开发者建模；agent 查字段和值，Looker 编译 SQL | 指标语义可靠时优先结构化查询计划，保留 Python 后处理 |
| Fabric data agent | 最多五个配置数据源；SQL / DAX / KQL 路由 | 开发者选表、写说明与例题；agent 选择来源并生成、验证查询 | 异构查询语言统一编排；权限与输出限制需要进入产品契约 |
| ThoughtSpot Spotter | 语义层、search tokens / AgentQL 到 governed SQL | 官网宣称自动建模、记忆、深分析；细节验证不足 | 编译式查询与场景 analyst；营销中的确定性必须实测 |
| Palantir Ontology / AIP | objects、links、actions、functions、权限与分支 | 企业数据映射成业务对象；应用使用对象与工具 | ontology 可以承载业务操作与版本，不只是表的别名 |
| 阿里 Quick BI 小Q | 数据集 / 分析主题 + 业务知识 + 多个专用 Agent | 人工配置数据类型、口径、知识；字段质量评估与值学习辅助 | 统一入口、多模块 bundle、文件分析到报告的实际工作流 |
| 帆软 FineChatBI | FineBI 指标中心与预加载指标 | 管理员先准备指标；模糊值交用户确认 | 指标口径透明、即时纠偏、下钻、归因、预测与看板保存 |
| Hex | 文件、warehouse、semantic model、SQL / Python notebook | agent 探查与生成单元，用户确认；上下文评测后发布 | 文件即席分析与可复现 notebook 是独立、重要的产品路径 |

### 3.1 Snowflake：语义对象、值检索与工具编排

- `D` Semantic Views 是 schema 级对象，定义 logical tables、dimensions、facts、metrics、relationships，集成 RBAC / sharing / catalog；旧 stage YAML 仍支持。[S1][S3]
- `D` 关系列仍需定义。当前 YAML 文档说明：`relationship type ... automatically inferred from the data and primary key definitions`，并说明不再需要旧模型的 `join_type` / `relationship_type`。[S3，“Relationships”]
- `D` 支持复合关系列、ASOF 与 range relationship；这不是仅靠同名列猜 join 的产品承诺。[S3]
- `D` 低基数维度建议 sample values；高基数或频繁变化的值可接 Cortex Search。文档仍出现 `In this preview, only a single Cortex Search Service per logical dimension is supported`，因此不统一宣称该集成功能 GA。[S4]
- `D` Analyst 文档明确查询受 RBAC 约束，并列出 stage、Search 服务与底层表所需权限。Agents 的各工具仍受各自执行上下文控制，不能把 agent 访问权限等同于全部数据权限。[S1][S2]
- `D` Analyst 单独定位于 SQL 问题；文档指出不能基于前一次查询结果回答“第二个产品”，也不处理任意商业趋势解读。Agents 增加持久 thread、plan / use tools / reflect 循环、Python sandbox、图表及自定义工具。[S1][S2]
- `D` Analyst eval 执行生成 SQL，与 verified query 的结果比较，记录回归和延迟；评测前会从临时语义副本移除被测例题，防止直接命中答案。[S5]
- `D` eval 文档仍列“单 semantic view”“无多轮评测”“评测集需人工整理”等限制；优化可建议语义变更，不等于自动产生可信 ontology。[S5]
- `I` 可学习项：把业务语义当版本化产品资产；工具各自授权；值检索独立服务；将参考例题与保留测试集隔开。
- 未证实：未经预配置便跨任意企业连接器自动发现完整业务语义；原生 ontology 分支合并；拖入任意本地 Excel 的完整体验。

### 3.2 Databricks：候选知识自动挖掘与作者审核

- `D` 当前官方概述原文：`Genie Agents were formerly known as Genie Spaces`；页面显示 2026-10-07 更新。这里只记录当前文档命名，不推断各客户完成迁移。[D1]
- `D` 每个 agent 由分析师配置 UC datasets、SQL examples、SQL expressions 与文字说明；最多挂 50 个 tables / views / metric views。[D1][D3]
- `D` 创建时 Genie Code 可读取数据、建议表说明和示例，作者 review / accept；未知表时可从业务描述识别相关数据并向作者确认。历史 SQL 推荐只搜索作者可查看、且关联已挂载资产的查询。[D3]
- `D` knowledge store 支持表列描述、同义词、隐藏列、filters / measures / fields、join relationship。配置作用于该 agent，不修改 UC 元数据。[D2]
- `D` join 支持 many-to-one、one-to-many、one-to-one；同表多关系和 self join 自动给右表起别名。已声明 PK/FK 可自动存成关系；没有证据证明任意统计相关列可直接成为正式关系。[D2，“Define join relationships”“Knowledge mining recommendations”]
- `D` 值匹配分 format assistance 与 entity matching；后者支持最多 120 列，每列最多 1,024 个值。代表值按作者数据权限生成，成为 agent 共享上下文；row filter 表全部排除，column mask 只排除被遮罩列。[D2]
- `D` SQL 仓库计算权限可来自配置者嵌入凭据，数据权限始终按终端用户 UC identity 评估；row filters / column masks 对用户强制执行。[D3]
- `D` 参数化例题或 UC SQL function 可作为 trusted asset；仅精确采用参数化查询原文等指定情形才给 verified answer，不能把任意生成 SQL 都标认证。[D2]
- `D` 普通反馈本身不改变 agent 行为。作者 thumbs-up / 下载结果可能触发知识挖掘建议；这与未经审核的全局自动学习不同。[D2][D5]
- `D` 文件页明确 CSV / Excel / PDF 可同 UC 表分析；25 文件 / conversation；CSV / Excel 单个 <200 MB、少于 100 列；PDF 有单独限制且需 Agent mode，API 上传 PDF 未支持。[D4]
- `D` 文件仅上传者可访问，存于 user + agent 专属 managed volume；一部分文件数据会发送给外部模型。不能据 UC 查询授权推断文件数据完全不出域。[D4]
- `I` 可学习项：分别治理 catalog 全局事实、agent 局部定义、个人文件、训练候选；把采样值也作为敏感资产管理。
- 未证实：每个 agent 的原生 Git 语义分支、无配置跨企业数据仓库联邦查询、通用预测回测。

### 3.3 Looker：让模型选择字段，让语义层决定 SQL

- `D` 数据真相来自开发者维护的 LookML；agent 可连接最多五个 Explores，提供 business glossary、persona、custom instructions、verified queries。[L1]
- `D` 关键原文：`Instead of querying your database directly ... fields, filters, sorts, and limits`，然后 `Looker then composes and executes the query`。这是一种受语义模型约束的计划生成路径。[L1，“How does Conversational Analytics work?”]
- `D` 字段检索使用 name / label / description / type / dimension_group；hidden 字段不进入选取；值工具可返回最多 100 个值或 fuzzy search，并使用 suggestion API。[L1]
- `D` join、aggregation、filters、access grants、user attributes 等由 LookML 执行。分享 agent 不授予底层 Explore 数据访问权限。[L1]
- `D` Advanced Analytics 会生成并执行 Python，支持更复杂分析；dashboard agents 不支持此功能。[L1，“Key features”“Data agents versus Conversations”]
- `D` 同一概述的 standard question limitations 仍列预测、复杂统计等不支持。应按标准 SQL 路径 / Python 功能 / dashboard agent 分别理解，不能直接写“Looker 所有对话都支持预测”。[L1，“Limitations on questions”]
- `D` 文档提到 version-controlled LookML dashboard agents；这只证明该类型可以版本控制，不能外推所有会话和 agent 配置都在 Git。[L1]
- `D` 本次页面显示 `Last updated 2026-10-26 UTC`，其中 triggered / scheduled agentic workflows、query feedback review 有 Preview 标签；未将这些能力统一写为 GA。[L1]
- `I` 可学习项：统一 metric / dimension / filter 查询计划作为可验证中间结果；业务事实由执行器编码；Python 在可信结果上继续分析。
- 未证实：自动从原始库构建已验收 LookML；自由文件上传；自由跨 Explore SQL join 的完整覆盖。

### 3.4 Microsoft Fabric：异构语言路由与权限身份

- `D` data agent 支持配置最多五个来源，文档列 lakehouse、warehouse、Power BI semantic model、KQL database、ontology、Microsoft Graph；开发者选择相关表并添加说明与例题。[F1]
- `D` 对应 NL2SQL / NL2DAX / NL2KQL，工具生成、验证、执行查询。文档的 validation 说明是形式、安全与 RAI 约束，没有证明业务口径必然正确。[F1]
- `D` 使用请求者身份与权限读取 schema 和查询数据；分享 agent 不授予数据源权限；Power BI semantic model 使用 Read 权限，无需 Build，RLS / CLS 仍适用。[F1]
- `D` 明确只读；不直接读 lakehouse 的 CSV / JSON 文件，要先导入或暴露为表；不支持 PDF / DOCX / TXT 等非结构化文件。[F1，“Limitations”]
- `D` 当前文档列输出最多 25 行 × 25 列、英语限制、跨不同 region capacity 的数据源限制，Power BI semantic model 不支持添加 question-query examples。[F1]
- `D` 文档明确 Git integration、deployment pipelines、diagnostics；这是 agent 配置生命周期证据，范围包括说明、例题、数据源选择。[F1，“ALM and DevOps”]
- `D` 文档中 Purview 保护的部分能力标 Preview；不能把产品整体或每项安全能力统一标成熟商用。[F1]
- `I` 可学习项：adapter 不只适配 SQL，还需语义模型查询语言；认证身份、结果截断、区域和语言限制应在能力声明中明确。
- 未证实：跨来源自动 federated join、预测函数编排、自动探索任意外部数据库的 ontology。

### 3.5 ThoughtSpot Spotter：编译式问数与深分析宣称

- `M` 官网称问题转为 search tokens，复杂多步问题转为 AgentQL，然后编译为 governed SQL，并称 `identical governed SQL on every run`。未实测这一确定性承诺。[T1]
- `M` 官网列 forecasting、change analysis、regression、跨结构化 / 非结构化信息、Slack / Confluence 上下文、记忆纠正、场景化 Spotter Analysts。[T1]
- `M` 官网称可使用 ThoughtSpot semantic layer、Snowflake semantic views、dbt semantic models，支持 30+ live-query 来源，query engine 强制行列权限。[T1]
- `M` “learns from conversations / models / Liveboards”没有本次抓取到的细粒度审核、作用域、冲突处理证据；不能直接推断为已治理的语义自动学习。[T1]
- `I` 可学习项：将 NL 转换与 SQL 编译分离；团队专属 analyst 以认证数据、工具与说明组成，可作为 MintHub preset 的对照。
- 未证实：AgentQL 精确语言契约、SQL 验证链、join 多重性规则、文件混合分析、记忆版本回滚与各功能 GA 状态。

### 3.6 Palantir：Ontology 管的是业务对象与可执行操作

- `D` ontology 把数据集、虚拟表、模型映射到对象 / 属性 / links，同时包含 actions / functions / dynamic security，不只描述报表指标。[P1]
- `D` link type 双向可遍历，同一对对象类型可有多个不同现实关系；many-to-many 的 link type 需要自己的 backing datasource。[P2，“Directionality”]
- `D` ontology branch 支持对象、action、link、interface、shared property 等资源的变更、rebase、冲突解决、review、merge checks；受保护资源必须走分支 proposal。[P3]
- `D` 权限区分 ontology resources 的 schema 和 objects / links 的实际值。具备资源查看权限不应被误认为能访问全部实例值。[P5]
- `D` AIP Chatbot Studio 当前文档原文：`was previously known as AIP Agent Studio`；通过 ontology、documents、自定义 tools 支持读写工作流，并继承平台安全模型。[P4]
- `D` AIP 概述含 Evals、审计、模型管理，但注明功能可随客户变化；本次未验证整套自动数据探查到发布 ontology 的路径。[P6]
- `I` 可学习项：关系本身是命名、有权限、有版本的对象；未来 action 与分析工具可共享 ontology，当前 DataAgent 仍应清楚区分读分析和业务写操作。
- 未证实：从未知 schema 自动建立完整领域 ontology、自动统计检验关系、业务预测的通用可用性。

### 3.7 阿里 Quick BI 小Q：最接近多模块 bundle 的中国实例

- `D` 官方概述把问数、解读、报告、搭建、洞察描述为增值 Agent 模块；统一入口按用户意图路由到专用 Agent，也可接自定义 agent。[A1][A4]
- `D` 操作指南有“内外部数据问数”与 Excel 文件案例：上传数据、提问、得到图表 / 结论、加入报告；还可使用企业知识库、分析思路、内容模板。[A1]
- `D` 管理员先配置数据集展示名、描述、数据类型、字段与默认聚合；字段质量评估给建议，用户选择接纳并重新学习。[A2]
- `D` 值学习有学习源高级配置、重新学习、超学习上限时的自动 / 自定义改写策略；知识库支持业务定义、解释、同义词、正则与强制改写，dataset knowledge 高于企业知识库。[A2]
- `D` 问数配置与问数数据授权分别存在；问数运营能查看业务逻辑 SQL / 执行 SQL、点赞点踩、跟踪记录与处理状态。[A2][A5]
- `D` 概述明确历史走势预测与多步问数；洞察模块用配置的归因链路、即时 / 定期归因、预计算，简报有全局开发者视角与个人权限视角。[A3][A4]
- `D` 同期两页分别写四个与五个增值 Agent，属于文档口径差异；本报告不据此给出精确套餐数量或价格。[A1][A4]
- `I` 可学习项：行业思路、报告模板、数据集语义、取数能力组成可复用 preset；值改写应显示匹配证据，归因不能直接当因果证明。
- 未证实：自动 join 发现的算法与多重性保证、连接器权限透传的完整边界、预测方法 / 回测 / 置信区间、语义 Git 分支。

### 3.8 帆软 FineChatBI：指标底座、歧义确认和分析闭环

- `D` 手册说明管理员先在 FineBI 指标中心搭建指标、加入预加载列表，用户基于指标提问。不能描述为对任意裸库即开即用。[R1，“3.1”]
- `D` 支持意图解析与指标口径即时调整；模糊字段会联想枚举值并返回给用户确认；提供问答思路与相似问题。[R1，“3.2–3.4”]
- `D` 支持异常点、指标波动归因、明细下钻、多轮问答、折线图预测、把结果组件保存成仪表板。[R1，“3.5–3.9”]
- `D` 文档显示更新于 2025-11-27；没有独立预测算法、精度或权限传播实验，文档的“历史数据越多预测准确率越高”也不应作为普遍统计结论引用。[R1]
- `I` 可学习项：面向业务用户暴露口径、歧义值确认和可保存分析资产，降低“答案看似合理但语义错位”的风险。
- 未证实：agentic catalog 检索、多源自动 join、ontology 版本、开放预测工具与反馈回归流水线。

### 3.9 Hex：文件即席分析与可复现深分析

- `D` 项目可上传 CSV / JSON 等文件，Python cells 可读，CSV 可用 dataframe SQL 查询；100 文件 / project，单文件小于 2 GB。notebook / app / scheduled run 的文件持久化边界不同。[H1]
- `D` Notebook agent 读取项目、warehouse schema、已有 SQL / Python、outputs、授权 semantic models；可生成 Python / SQL / pivot / chart 等 cells，并使用已有项目为上下文，引用具体来源。[H2]
- `D` agent 变更按 cell 逐项 Confirm / Undo；新建 thread 会保存项目版本；可创建 app 布局与发布，但 Notebook agent 本身不运行在 published app 内。[H2]
- `D` Context Studio 管理 guides、endorsements、semantic models，允许观察问题、建议、评测并在发布前测试上下文变更。[H3]
- `D` YAML eval 支持答案 / 全轨迹 LLM judge、数值或 SQL ground truth、模型与 effort 比较；Git context preview 后评测再 publish，跟踪时间、credits 和回归。[H4]
- `D` 原文：`Governed mode isn't a security control`，只是强引导可信来源，真实权限依赖 data connection permissions。此措辞值得 DataAgent 明确采用。[H5]
- `I` Python notebook 可承载预测、统计与复杂数据清洗；本次文档未证实 turnkey forecasting、默认回测、置信区间，因此不把“会写 Python”当“已经做好预测产品”。
- 可学习项：即席结果能变为可读、可复跑、可编辑的分析工程；临时文件升级为企业共享数据资产需要单独发布和授权。

## 4. 语义执行与中国补充证据

- `D` dbt entities 分 primary / unique / foreign / natural；MetricFlow 用这些声明建语义图、规划 join，限制 fan-out / chasm。文档有允许关系表、EXPLAIN 校验、两跳路径限制。[B1][B2]
- `D` Cube 声明 one-to-one / one-to-many / many-to-one，M:N 用桥表；PK 用于避免 fanout，多路径用 `join_path` 消歧；同一对 cubes 仅一个 join，需要别名角色时建额外 cube。[C1]
- `I` 两者说明“自动生成 join”通常以先声明实体、键、粒度、方向为前提；这不等于自动推断真实业务关系，也不证明源数据满足声明。
- `M` 观远问数 Agent 官网列知识召回、多源跨表、历史 SQL / 文档知识、主题管理、问答行为学习与行列权限；洞察 Agent 官网页面列分析资产发现、模板、任务拆解与报告组装。[G1][G2]
- `M` 观远的“90%+准确率”没有本次可取得的公开测试集、计算方法和版本信息，不纳入横向准确率排名。[G1]

## 5. 对 DataAgent 模块与边界的建议（I）

1. connector / catalog：先探查来源、表、列、统计、权限与可用查询语言，保留来源与发现时间。
2. semantic authoring：自动产候选 entity、metric、synonym、join；记录键 / 粒度 / 基数、空值、覆盖率、M:N、角色和时间有效性，经过评测与审阅再发布。
3. retrieval：表、字段、维值三层召回；采样、embedding、全文、业务词典按数据规模与权限组合。
4. query planning：优先受约束 semantic query plan；开放 NL2SQL 则增加方言、只读、EXPLAIN、成本与结果合理性检查。
5. analysis runtime：文件 / dataframe / SQL / Python / 统计函数分别有明确能力、输入输出与资源限额；提供可复现代码和中间产物。
6. learning / version：个人修正、候选知识、共享语义、认证定义四种状态；发布前差异、受影响用例与回归结果可查。
7. apps / presets：按行业组合数据源、语义包、分析函数、报告模板、界面；底层语义与执行模块可复用，业务 preset 不复制一整套 agent 内核。
8. 权限必须覆盖 schema、样本值、检索索引、query result、上传文件、导出和缓存；“只读”“可信来源优先”均不能替代强制访问控制。

## 6. 已抓取一手来源

以下均在本次调研实际取得正文；链接小节名用于定位，站点日期若未呈现则不补造。

- [S1 Cortex Analyst](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst)：Semantic Views、RBAC、multi-turn limitations；正文及 `.md` 已抓取。
- [S2 Cortex Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)：reasoning loop、Tools、access、budget；正文 `.md` 已抓取。
- [S3 Semantic View YAML](https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec)：Relationships、composite / ASOF / range、旧模型差别。
- [S4 Literal Search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/cortex-analyst-search-integration)：sample values、Search、Preview 原文。
- [S5 Analyst Evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)：结果比较、移除被测例题、回归、Known limitations。
- [D1 Genie Agents](https://docs.databricks.com/aws/en/genie-agents/)：新旧命名原文，页面标 2026-10-07 更新。
- [D2 Tune Quality](https://docs.databricks.com/aws/en/genie-agents/tune-quality)：knowledge store、prompt matching、join、mining；页面标 2026-10-09 更新。
- [D3 Setup](https://docs.databricks.com/aws/en/genie-agents/set-up)：50 资产、review suggested queries、数据与计算权限；页面标 2026-10-09 更新。
- [D4 File Upload](https://docs.databricks.com/aws/en/genie-agents/file-upload)：文件类型、限制、ACL、外部模型；页面标 2026-10-16 更新。
- [D5 Test and Monitor](https://docs.databricks.com/aws/en/genie-agents/monitor)：`behavior does not change based on user feedback alone`；页面标 2026-09-17 更新。
- [L1 Looker Overview](https://cloud.google.com/looker/docs/conversational-analytics-overview)：字段与值工具、LookML 编译、Python、不同 agent 限制；页面标 2026-10-26 更新。
- [F1 Fabric Data Agent](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)：query pipeline、data scope、ALM、limitations；页面标 2026-05-11 更新。
- [T1 Spotter](https://www.thoughtspot.com/product/spotter)：抓取时跳转官方 `/product/agents/spotter`，编译、语义层、预测、memory 均属营销页证据。
- [P1 Ontology Overview](https://www.palantir.com/docs/foundry/ontology/overview/)：semantic / kinetic elements。
- [P2 Link Types](https://www.palantir.com/docs/foundry/object-link-types/link-types-overview/)：双向、多关系、M:N backing datasource。
- [P3 Ontology Branching](https://www.palantir.com/docs/foundry/ontologies/branching-ontology/)：protected resources、rebase、review、merge、limitations。
- [P4 Chatbot Studio](https://www.palantir.com/docs/foundry/chatbot-studio/overview/)：新旧命名原文、ontology / documents / tools、安全。
- [P5 Object Permissioning](https://www.palantir.com/docs/foundry/object-permissioning/overview/)：schema resources 与实际 objects / links 分层。
- [P6 AIP Overview](https://www.palantir.com/docs/foundry/aip/overview/)：治理、evaluations、版本、客户可用性提示。
- [A1 小Q操作指南](https://help.aliyun.com/zh/quick-bi/user-guide/smart-q-home-page)：文件案例、意图路由、模板、知识库、不同 Agent 入口。
- [A2 小Q数据准备](https://help.aliyun.com/zh/quick-bi/user-guide/prepare-data)：字段质量、值学习、业务定义、权限、默认聚合建议。
- [A3 小Q问数概述](https://help.aliyun.com/zh/quick-bi/user-guide/chat-bi-overview)：文件、预测、多步问数、配置和授权流程。
- [A4 小Q总览](https://help.aliyun.com/zh/quick-bi/user-guide/smartq)：五 Agent、归因、全局 / 私有视角。
- [A5 问数运营](https://help.aliyun.com/zh/quick-bi/user-guide/ask-the-number-of-operations)：SQL 追踪、反馈与问题处理列表。
- [R1 FineChatBI 简介](https://help.fanruan.com/finebi7.0/doc-view-2572.html)：3.1–3.9；页面标 2025-11-27 更新。
- [H1 Hex Upload Files](https://learn.hex.tech/docs/connect-to-data/upload-files)：文件与运行上下文限制。
- [H2 Hex Notebook Agent](https://learn.hex.tech/docs/explore-data/notebook-view/notebook-agent)：cells、确认、项目上下文、版本、analysis。
- [H3 Context Studio](https://learn.hex.tech/docs/agent-management/context-studio)：角色、上下文与观察闭环。
- [H4 Hex Evals](https://learn.hex.tech/docs/agent-management/evals)：YAML、SQL ground truth、Git preview、回归、发布。
- [H5 Governed Mode](https://learn.hex.tech/docs/agent-management/governed-mode)：`isn't a security control` 原文。
- [B1 dbt Entities](https://docs.getdbt.com/docs/build/entities)：entity types；页面标 2026-07-20 更新。
- [B2 MetricFlow Joins](https://docs.getdbt.com/docs/build/join-logic)：允许矩阵、EXPLAIN、hop 限制；页面标 2026-10-20 更新。
- [C1 Cube Joins](https://cube.dev/docs/product/data-modeling/concepts/working-with-joins)：PK、fanout、方向、M:N、diamond / join_path。
- [G1 观远问数 Agent](https://www.guandata.com/bi-copilot)：知识、召回、多源、权限、准确率宣称。
- [G2 观远洞察 Agent](https://www.guandata.com/InsightAgent)：结构化分析、分析资产调度、报告；营销证据。

抓取失败或无效页面未作为能力证据：`docs.palantir.com` 部分旧地址只返回首页、ThoughtSpot 文档站部分超时、腾讯页面无可读正文、Julius 被 Cloudflare 阻挡、Hex 旧 magic / AI 路径 404。已沿官网导航找到可读替代页面；没有用旧常识填补空白。
