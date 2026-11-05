# DataAgent 开源实现与企业语义层调研

调研日期：2026-10-30，Asia/Shanghai。范围：为 MintHub 的 DataAgent bundle/preset/app 寻找模块与设计证据；本轮不实现、不接生产数据、不运行第三方代码。

## 1. 结论与证据边界

1. **推荐组合是模块组合**：文件分析用 DuckDB/Arrow，查询检查用 SQLGlot，企业语义编译重点评估 Wren MDL/MetricFlow，元数据治理对接 DataHub/OpenMetadata；预测实验借鉴 RD-Agent。
2. **最接近完整目标的是能力拼接**：Wren 提供文件化语义与执行，SuperSonic 提供中文语义召回和查询翻译参考，DB-GPT 提供分析工作流，三者都不能直接证明拥有目标中的全部治理能力。
3. **ontology 至少包含可执行业务约束**：实体、指标、维度、grain、cardinality、时间、权限、值字典、映射、join、来源和审批版本。表描述 embedding、DDL RAG 和问答记忆只是索引或证据。
4. **默认不 fork 整个产品**：优先调用稳定 SDK/服务边界，再借鉴可独立测试的策略；MintHub 的执行、身份、审批和工件管理应由本地架构负责。
5. **许可证必须按 commit、路径、制品检查**：SuperSonic 当前有商业衍生附加条件；Chat2DB 5.3.0+ 不是普通 Apache-2.0；Wren 和 MetricFlow 也有路径或历史版本差异。

证据标记：**[源码]** 已读当前固定 commit 的实现；**[官方]** README/文档描述；**[推演]** 基于静态代码的分析；**[建议]** DataAgent 设计建议；**[未验证]** 本次没有运行或没有展开到该实现。

方法：GitHub API 遇到匿名限流后，使用禁用 credential helper 的 `git ls-remote`、无 checkout 的浅克隆和 `git show` 静态读取；少量候选使用固定 SHA 的 raw README/LICENSE。
所有 SHA 均在本次读取时固定；不以 star 数、README 徽章或单个提交日期推断项目质量、维护 SLA 或安全性。源码阅读未做依赖闭包和法律审计。

## 2. 固定版本与定位

| 项目 | 本次固定 commit | 定位与已读范围 |
| --- | --- | --- |
| WrenAI | `8edc086b1f8f9f2974b9faf8ab7c639c85851b46` | 深读；README、LICENSE、MDL 类型、context、memory、engine、policy、访问控制 |
| wren-engine | `bc2b06a1950a946aa9bd16356fe0c84e9dc504bc` | 历史补充；README、Ibis server rewrite、LICENSE |
| Vanna | `365d0617c1a4567ffee1b19b40c27feb4206bfcf` | 深读；README、Agent、registry、run_sql、legacy generate_sql、LICENSE |
| DB-GPT | `06a46eea2d248a0f2b3e9096035424df4f2dc2eb` | 深读；README、ChatDB、DBSummaryClient、DBSchemaRetriever、LICENSE |
| SuperSonic | `ce881947433f07bb8d5469c7c157991046645113` | 深读；README、mapper、parser、Ontology、translator、权限 aspect、LICENSE |
| RD-Agent | `484776c211e4fbbeef03e0ec00d6bbee7362a4f4` | 深读；README、DataScienceRDLoop、runner、interactor、LICENSE |
| DataHub | `47be57949cf2b85c291228d5c1ce689a2b0ee795` | 深读；README、schema/glossary/policy/version PDL、LICENSE |
| MetricFlow | `fe4b8c1ccb72a8ca77494b345777eff20a714119` | 深读；README、engine、join evaluator、LICENSE |
| Cube | `d1241a63d6802792b01dd5131eb2b43eb23a3b3d` | 补充；README、JoinGraph、LICENSE |
| XiYan-SQL | `603dedac706d57ece47bc30d02f90744a537b6a0` | 补充；XGenerationLab 仓库 README、目录、LICENSE |
| M-Schema | `755751451be841f7a54f8b08c0a1f818b041a1c0` | 补充；README、m_schema.py、schema_engine.py、LICENSE |
| DuckDB | `ed0443f18a0267ec5814d7cc2f1f421ad3e5b335` | 基础模块；README、LICENSE，未展开内核 |
| SQLGlot | `f31f109daef0ca99347d36295534a0d59956059c` | 基础模块；README、LICENSE，并核对 Wren 中的真实调用 |
| OpenMetadata | `eeee22d6f74cd926d71dec61fa232b690ff7c692` | 目录治理备选；README、LICENSE，未深读实现 |

## 3. 七个项目的源码比较

### 3.1 WrenAI：语义编译和版本化上下文最值得优先评估

- **版本变化 [官方]**：当前 README 说明 2026-05-07 engine 合并到 `core/`，旧 `wren-engine` 归档；旧聊天产品保存在 `legacy/v1`，并声明不再提供新功能和安全修复。[W1]
- 当前主线是 Rust/DataFusion 语义 engine、Python SDK/CLI、WASM、agent SDK 和 skills；不能把过去的 `wren-ai-service` 检索架构当作当前主线事实。
- **数据结构 [源码]**：`manifest-macro/src/lib.rs` 的 `Model` 有 `ref_sql/table_reference`、columns、primary_key、row access rules；`Relationship` 有 models、join_type、condition。[W2]
- `JoinType` 显式表达 1:1、1:N、N:1、N:N；`Cube` 有 measures、dimensions、time_dimensions 与 drill-down 层级；这比表描述向量多了可编译的关系和分析定义。
- `manifest.rs` 支持单列/复合主键，并拒绝超过 engine 最大支持值的 `layout_version`；布局兼容版本不等于业务定义发布版本。[W3]
- **文件链 [源码]**：`context.py` 将 YAML MDL 转成 manifest JSON；项目文件包含 models、views、relationships、knowledge/rules、knowledge/sql。[W4]
- 其生成的 agent 指引是 `memory fetch → recall → 编写模型名 SQL → 执行 → 保存确认过的问答`；“确认过”出现在流程说明，不证明工具强制执行人工审批。
- **召回 [源码]**：`MemoryStore.get_context` 对小 schema 返回全文，对大 schema 向量查询；支持 item_type、model_name、mdl_hash 过滤，避免直接召回旧 manifest 的 schema。[W5]
- NL→SQL history 独立存储；`source:seed`、用户条目和 Markdown 同步来源有区别，schema 更新可替换 seed、保留用户历史；保存成功仍不等于业务正确。
- **执行 [源码]**：`WrenEngine.query → dry_plan/_plan → AST policy → manifest extract → CTERewriter → connector.query`，结果返回 Arrow table。[W6]
- `policy.py` 始终检查只读语句；strict mode 额外限制 manifest 外对象与函数，并显式处理外部文件/数据库 reader；文件函数封禁表本身需要随 connector 演进维护。[W7]
- **权限 [源码]**：Rust `WrenAccessControlProvider` 将 row rules 合并为逻辑 AND，column access 返回 Allow/Deny；会话属性需要由可信身份层提供。[W8]
- **产品边界 [官方]**：同一 commit 的 README 将完整 row/column security 与 users/groups access control 列入商业产品。源码存在规则执行原语，不等于 OSS 已交付完整权限系统，也不能据此推定商业产品授权。[W1]
- **边界 [源码]**：`wren ask` 只是渲染 guided/direct prompt，不发起 SQL，也不独立完成 agent loop；编排仍由调用者提供。[W9]
- **Ibis 历史 [源码]**：归档 repo 的 `ibis-server/app/mdl/rewriter.py` 使用 SQLGlot 转方言，选择 Java external 或 embedded rewriter；Ibis 在后端和方言注册中参与。[W10]
- 因此应分别评估当前 DataFusion/CTE 路径与归档 Ibis server 的兼容经验，不能把它们描述成同一代运行架构。
- **版本/审批 [建议]**：复用文件化项目、hash 索引和 dry-plan；另加审批状态、不可变 release、回归查询与发布记录。
- **许可 [源码]**：根 LICENSE 按路径划分，core/sdk/skills/examples 为 Apache-2.0，docs 为 CC BY 4.0，制品 manifest 在其规则中优先；AGPL 文本存在不表示当前全部源码为 AGPL。[W11]

### 3.2 Vanna：轻量 agent 与 SQL 工具接口，可用作适配参考

- **架构 [源码]**：当前 2.x `Agent` 组合 LlmService、ToolRegistry、UserResolver、AgentMemory、ConversationStore，提供 lifecycle/middleware/recovery/enricher 等扩展点。[V1]
- 这是可扩展的应用框架；若 MintHub 已有 agent runtime，整套嵌入会重复会话、执行、审计和身份管理。
- **旧版检索 [源码]**：legacy `generate_sql` 依次取相似问答 SQL、DDL、文档，拼 prompt 后调用 LLM；并非语义关系图。[V2]
- 需要中间 SQL 探查时，`allow_llm_to_see_data=False` 默认阻止将数据结果送回模型；开启后把查询结果 DataFrame 放入第二轮 prompt。
- 该授权开关值得保留为“数据可否出域”的独立策略，不能由“已允许执行只读 SQL”隐含授权。
- **工具权限 [源码]**：`ToolRegistry` 在 schema 展示和执行阶段检查 user groups 与 tool access_groups 交集，并能审计拒绝。[V3]
- **关键限制 [源码]**：`transform_args` 的默认实现是 NoOp；README 的 RLS 能力需要注入 SQL runner/registry 策略，不能理解为任意默认部署自动注入行权限。
- **执行 [源码]**：`RunSqlTool.execute` 先调用注入的 `SqlRunner.run_sql`，再按 SQL 首 token 生成表格/通知，导出 CSV 给后续可视化。[V4]
- 它包含 INSERT/UPDATE/DELETE 的结果分支；该工具自身不是只读安全闸门，也没有在调用 runner 前完成语义正确性验证。
- **人类确认 [未验证]**：已读主链没有业务定义审批或 SQL 执行前必须确认的内置契约；需要调用方 lifecycle/workflow 实现。
- **版本 [推演]**：ConversationStore 和 AgentMemory 是可替换存储边界，不能直接代替带审阅历史的企业语义模型版本库。
- **复用 [建议]**：借鉴 user-aware tool context、数据可见授权、结构化 UI result 与 SQL runner 接口；业务 ontology 和可靠查询计划另行提供。
- **许可 [源码]**：本次根 LICENSE 为 MIT；premium 集成、远端服务、模型和向量数据库的条款需分别核对。[V5]

### 3.3 DB-GPT：表/字段分级召回与分析工作流的参考

- **产品范围 [官方]**：README 覆盖数据库、CSV/Excel、Python 分析、skills、图表/报告与 sandbox；这些广度描述未在本轮逐项运行验证。[D1]
- 源码按 core/ext/serve/app 分包，ChatDB 场景与 connector、RAG 组件、Web API 分开，利于识别可替换模块边界。
- **入口 [源码]**：`ChatWithDbAutoExecute.generate_input_values` 调用 `DBSummaryClient.get_db_summary(db, question, top_k)`，组装 dialect/table_info 等生成输入。[D2]
- 检索失败时回退 `table_simple_info`，并按配置长度截断；该分支可能丢失关键连接表，不能被当作“完整 schema 已送入模型”。
- `do_action` 返回 `database.run_to_df`，说明此场景可以自动进入执行；本文件没有强制的人工 SQL 确认步骤。
- **索引 [源码]**：`DBSummaryClient` 创建 table 和 field vector connectors；通过 assembler 拆分/持久化 schema，并用 per-db lock 避免刷新与删除索引互相干扰。[D3]
- **分级召回 [源码]**：`DBSchemaRetriever._similarity_search` 先召回 table chunks，再对 `separated` 的大表，用 metadata filter 召回该表字段。[D4]
- 非拆分表直接返回；拆分表字段查询并发限制为 3；最后将片段重新构造为 DDL 风格的上下文。
- **边界 [源码]**：该检索链没有直接证明存在值级召回、业务指标可加性、join grain 审批或权限闭包；它解决的是相关 schema 缩减。
- **权限 [未验证]**：本轮未沿最新 sandbox/RBAC 全链检查，不能依据 README 声称自动执行任意代码已经得到企业级隔离。
- **版本 [推演]**：schema summary version、索引刷新和应用数据库 migration 有用，但不同于语义口径 release、审批和结果可复现快照。
- **复用 [建议]**：优先借鉴 table→field 检索、schema assembler、connector 模式与失败诊断；在 MintHub 内做薄适配，避免复制整个平台。
- **许可 [源码]**：根 LICENSE 为 MIT；驱动、模型权重和 sandbox 后端不自动继承该许可。[D5]

### 3.4 SuperSonic：中文业务语义召回与受约束查询的强参考

- **官方仓库** 是 `tencentmusic/supersonic`；本次尝试的 `Tencent/supersonic` 不可用，不能据名称猜测出处。
- **架构 [官方]**：Headless BI 建语义模型；Knowledge Base→Schema Mapper→Semantic Parser→Corrector→Translator→SQL；同时有规则与 LLM 路径。[S1]
- **ontology [源码]**：`Ontology` 明确指可星形/雪花 join 的一组数据模型，含 database、modelMap、metricMap、dimensionMap、joinRelations。[S2]
- 这里的 ontology 是分析语义模型，不能据类名声称具有通用知识推理、公理体系或任意企业流程建模。
- `JoinRelation` 保存 left/right、joinType、条件 triple；这证明关系是结构化对象，但没有单凭该类证明 cardinality 经数据验证。[S3]
- **召回 [源码]**：`SchemaMapper` 的目标明确包括 metrics/dimensions/entities/values；`EmbeddingMapper` 将召回结果转成带 dataset/type/id 的 `SchemaElementMatch`。[S4]
- `EmbeddingMatchStrategy` 先做基础匹配，可按配置增加 LLM 召回筛选，分批查询并去重；筛选 prompt 要求仅返回已召回的 ID。[S5]
- 该设计比纯表名 RAG 更接近“值→维度→指标”的中文映射；向量召回仍可能漏召回，ID 约束也不能保证口径选择正确。
- **生成 [源码]**：`LLMSqlParser` 对请求重试、SQL 去重、记录候选权重；失败时可能调整温度，不等于执行验证已经通过。[S6]
- **翻译 [源码]**：`DefaultSemanticTranslator` 依次运行接受该 QueryStatement 的 parser，合并 ontology 内层 SQL 与外层语义 SQL，再运行 optimizer。[S7]
- 对 DataAgent 最有价值的原则是让 agent 选择指标/维度/筛选，join 和表达式由可检查的编译层生成。
- **权限 [源码]**：`S2DataPermissionAspect` 检查身份、model 可见性、敏感列和行条件；但 `needAuth=false` 会跳过，管理员也存在提前通过分支。[S8]
- 因而“有三层权限”不等于每个入口和配置都强制生效；集成时要证明外部请求不能控制绕过参数。
- **人类确认/版本 [未验证]**：本次未找到已验证的 Git 式模型发布与审批状态机，不能把管理 UI 操作等同于受审计的发布流程。
- **许可风险 [源码]**：当前 LICENSE 在 Apache-2.0 外添加条件，基于其开发并分发 derivative work 需商业许可；不应列为可直接无条件 fork 的 Apache 项目。[S9]
- **建议**：作为架构和中文召回机制参考；若要复制或派生代码，先完成目标用法的许可评估。

### 3.5 RD-Agent：预测/实验闭环，而不是企业语义层

- **架构 [官方+源码]**：“R”提出假设，“D”实现实验；本次聚焦 Data Science 场景，不沿量化收益或基准冠军宣传下结论。[R1]
- `DataScienceRDLoop` 创建 experiment generator、interactor、各类 coder、runner、trace、summarizer。[R2]
- **执行链 [源码]**：`direct_exp_gen → coding → running → feedback → record`；按 DataLoader/Feature/Model/Ensemble/Workflow/Pipeline task 路由 coder。
- runner 配置默认 `env_type="docker"`，有有限次数开发循环；这只是该场景配置事实，不证明任意部署的网络、磁盘或资源隔离充分。[R3]
- **反馈 [源码]**：runner 结合评估器、调试失败代码，要求产生 `scores.csv`；选择新实验时考虑 acceptable、score 和 metric_direction。
- 这使“结果是否改善”成为可保存工件，而不只是一段 LLM 自评文字；仍需要检查数据泄漏和验证集设计。
- **人工交互 [源码]**：`DSInteractor/FBDSInteractor` 可收集 confirm/rewrite，展示候选假设、任务和当前代码。[R4]
- **重要限制**：等待超时后返回原实验继续，不能复用为 DataAgent 高风险操作的强制审批；审批应 fail-closed。
- **版本 [源码+推演]**：trace、实验工作区、候选和 feedback 支持实验追溯，但不替代指标、实体、权限语义模型的版本。
- **业务边界 [建议]**：将预测设成异步 job，输入绑定数据 snapshot、目标、时间切分、预算、模型范围，输出模型/指标/诊断/预测工件。
- 不让预测 job 随意修改线上业务语义定义，也不能因某次评分提升自动替换已发布模型。
- **许可 [源码]**：根 LICENSE 为 MIT；训练数据、比赛数据、模型、Qlib 等依赖仍有独立许可与使用边界。[R5]

### 3.6 DataHub：元数据图、来源和治理底座

- **定位 [官方]**：OSS 提供 metadata graph、connector、lineage、governance/discovery；README 同时介绍 Cloud/Context Platform，不能将全部产品能力归入 OSS。[H1]
- **schema [源码]**：`SchemaMetadata` 有 hash、native platformSchema、fields、primaryKeys、foreignKeys；`SchemaField` 包括类型、描述、审计时间、tag/glossary 关联。[H2][H3]
- **术语 [源码]**：`GlossaryTermInfo` 有 definition、parentNode、termSource、sourceRef/sourceUrl，支持业务名与物理字段的治理关联。[H4]
- **权限 [源码]**：`DataHubPolicyInfo` 的注释明确是 DataHub UI access policy，包含 resources、privileges、actors、state。[H5]
- 这不自动变成数据库行权限；DataAgent 必须把目录可见性与底层数据访问授权分别实现，并确保检索阶段不泄露不可见元数据。
- **版本 [源码]**：`VersionProperties` 有 versionSet、VersionTag、aliases、comment、sortId、source/metadata created stamp。[H6]
- 该 aspect 证明能表示资产版本；本轮未验证它对每种 glossary/metric 变更都形成 DataAgent 所需不可变发布。
- **召回 [源码+边界]**：PDL 的 Searchable 和 Relationship 注解支持搜索字段与图边；本轮未深入检索服务，因此不声称已验证端到端混合搜索质量。
- **执行边界 [建议]**：把 DataHub 当 catalog/provenance/ownership 接口；SQL 生成、join 合法性、执行和指标计算交给其他模块。
- **审批 [官方/未验证]**：README 提到 domain experts review Context Hub，但本轮未证实该完整流程在当前 OSS 中可直接复用。
- **复用 [建议]**：已有目录优先对接 API/MCP 并同步稳定 URN，避免 DataAgent 重建同一份组织目录；无目录时可先实现小型受版本控制的必要子集。
- **许可 [源码]**：根 LICENSE 为 Apache-2.0；Cloud API、托管服务和商标不由该源码许可自动覆盖。[H7]

### 3.7 MetricFlow：指标请求到 SQL 的可检查编译路径

- **定位 [官方]**：metric requests 编译为 dataflow plan，再优化成目标 engine SQL；当前使用依赖 dbt project/adapter。[M1]
- 它更适合“受治理指标查询”的确定性计划，不能单独承担企业 API 探查、文件清洗、自由代码分析和 agent loop。
- **主链 [源码]**：`MetricFlowEngine.query → _create_execution_plan → query parser validation → dataflow → execution plan → SequentialPlanExecutor`；`explain` 只构建计划。[M2]
- 结果保留 SQL 与计划信息，为执行前展示和回归检查提供边界；不能用“能编译”替代数据库数据正确性验证。
- **join [源码]**：`SemanticModelJoinEvaluator` 根据 PRIMARY/UNIQUE/FOREIGN/NATURAL 类型允许非 fanout 连接，明确拒绝 FOREIGN→FOREIGN 等组合。[M3]
- 两边都有 validity dimensions 时拒绝；右侧 NATURAL 缺少 validity dimensions 也拒绝，直接体现 SCD 时间窗与粒度风险。
- 这比“字段名像 id 所以 join”可靠，但前提仍是实体类型与有效期被正确声明；统计唯一性不等于业务主键已确认。
- 文件定义和 `SemanticManifestLookup` 是结构化语义输入；query dimension availability 的解析应作为 agent 的可选动作，避免 LLM 自造可切维度。
- **人类确认/权限 [边界]**：已读 engine 与 evaluator 没有提供租户身份审批系统，SQL client 的连接授权也不等于业务行列权限。
- **版本 [建议]**：以 dbt/Git manifest 为输入版本，DataAgent 固定 semantic release、adapter/engine 版本和数据时间，构建 golden metric 查询。
- **许可 [源码]**：本次 LICENSE 为 Apache-2.0；README 明确历史：0–0.140.0 为 AGPL，0.150.0–0.208.2 为 BSL，0.209.0+ 为 Apache-2.0。[M1][M4]
- 不能沿用“MetricFlow 始终 AGPL/BSL”或“历史版本全部 Apache”的结论，下载制品时仍核对目标版本。

## 4. 其他模块候选及取舍

| 项目 | 证据、适用边界与取舍 |
| --- | --- |
| Cube Core | [官方] measures/dimensions/joins/access rules，提供 SQL/REST/GraphQL；[源码] JoinGraph 校验目标存在和聚合相关主键，构建有向/无向连接图。[C1][C2] 适合 headless BI/API/cache，整套部署较重；Core 与商业 BI/RBAC 功能须分清。根许可默认 Apache-2.0，部分 MIT。[C3] |
| M-Schema | [源码] `MSchema` 保存 table/field/type/comment/PK/examples/FK，能按选中表列输出 prompt；`SchemaEngine` 通过 SQLAlchemy inspector 读取 PK/FK，执行 DISTINCT LIMIT 获取例值。[X2][X3] 适合 schema transport，不含完整指标、权限、审批 ontology；例值采样必须受策略约束。Apache-2.0。[X4] |
| XiYan-SQL | [源码目录] XGenerationLab 当前 repo 只有 README/PDF/图片/LICENSE；[官方] 多生成器、ICL/SFT、选择模型、中文 DateResolver，并指向新 `alibaba/XiYan-SQL` 与独立组件。[X1] 本轮未深读新训练框架，benchmark 数字仅官方声称，不能说本 repo 已提供完整在线 agent 实现。 |
| DuckDB | [官方] 进程内 OLAP，支持 CSV/Parquet/JSON 与 Excel 扩展、复杂类型及远程 reader。[B1] 适合即席文件 SQL 和物化 API 数据；不是企业权限或 ontology；Excel 类型/公式/多表头需另做导入处理。根 MIT 风格许可已读，扩展另核对。[B2] |
| SQLGlot | [官方] AST/parser/transpiler/optimizer；README 明说 parser 宽松、不是数据库 validator，解析成功可能执行失败。[B3] 用于语句与对象分析、方言转换、lineage 辅助；不能独立证明 SQL 安全或口径正确。MIT。[B4] |
| OpenMetadata | [官方] README 描述统一 metadata graph、quality/lineage/glossary/metrics/policy/MCP；本轮仅 README/LICENSE，尚未证实具体语义审批与查询执行实现。[O1] 作为 DataHub 同类对接备选，Apache-2.0 LICENSE 已读。[O2] |
| DB-GPT-Hub | README 已读，固定 `3ed19c1fcf848f064d129131c3b1e7d7ae86df17`；主要是 Text2SQL/NU/GQL 训练与评估，适合数据/benchmark 工具链，非运行时语义治理。[A1] |
| Chat2DB | README 已读，固定 `ce3f045bdcfa19ab611cb4d686c44212fe6a4f31`；数据库客户端/SQL 工作台，适合 UX 参考。README 明说 5.3.0+ 为 Apache 基础上附条件的 source-available，历史版本另论；本轮未审其完整 LICENSE。[A2] |
| Dataherald | README 已读，固定 `f8946182e6db55522b88cd5a831c788339b8fc42`；区分 engine、enterprise、admin-console、slackbot，认证/组织层在独立服务，适合 API 分层参考；未深读执行源码，不依 README badge 给整仓许可结论。[A3] |

PandasAI、DeepAnalyze、AutoGluon 本轮未展开；预测深读选择 RD-Agent 是为了核对假设→实验→评估→追溯链。后续若要普通表格预测函数，应单独对 AutoGluon 的 Tabular/TimeSeries 接口、资源预算和验证策略做小型评估。

## 5. 企业语义层的最小完备结构

以下是 **[建议] DataAgent 内部结构**，不是声称某个开源项目已经全量提供；可映射到 MDL/dbt/Cube，但应保留不能无损映射的治理字段。

| 对象 | 必要字段与约束 | 自动化与审批边界 |
| --- | --- | --- |
| Source/Asset | 稳定 ID、connector、API/MCP tool、物理路径、schema hash、owner、数据驻留；凭据仅引用受管 secret ID | 自动探查可见 schema/文档；新增来源和权限范围由管理员批准 |
| Entity | 业务定义、别名、标识字段、复合键、tenant scope、身份合并/拆分规则 | 自动提出命名/键候选；实体同一性与跨系统 identity mapping 需业务确认 |
| Dataset/Grain | 一行代表什么、主键、去重规则、分区、有效范围、逻辑删除、事实/维度角色 | profile 得到唯一性/空值证据；业务 grain、快照/流水含义需批准 |
| Metric/Measure | 公式 AST、单位/币种、聚合、distinct 键、可加性、默认筛选、分子分母、适用维度 | 从既有 BI/dbt/查询提候选；财务/经营口径、退款税费和可加性需 owner 批准 |
| Dimension | 业务属性、类型、层级、分箱、关联实体、允许切分指标、空值/未知语义 | 类型/低基数/层级候选可推断；业务分类和指标适用性需确认 |
| BusinessTime | event/booking/payment/ingest 时间角色、timezone、财务日历、grain、as-of、SCD validity、迟到数据 | 探查列类型/时间分布；默认业务时间、跨期处理与有效期 join 必须确认 |
| ValueDictionary | canonical value、业务标签、同义词、编码映射、有效期、脱敏/可见范围、频率摘要 | 受限采样候选；“01=有效”、客户别名、敏感值可见性需有据审批 |
| Mapping | 业务对象→表/列/API JSONPath/MCP 返回字段，转换表达式、枚举/单位转换、适用版本 | 可按结构和注释建议；跨系统映射与转换需要测试和 owner 审核 |
| Join | 左右对象、键/谓词、方向、cardinality、join type、grain 变化、bridge、null policy、时间条件 | 提候选+样本证据；关系含义、多对多处理与允许路径需批准 |
| Policy | principal/role/tenant、row filter、column deny/mask、目的限制、值/元数据可见性、导出规则 | 读取已有策略作为证据；agent 不可自行批准或扩大权限 |
| Quality/Provenance | 来源系统、采集时间、freshness、lineage、断言、样本范围、置信度、人工证据 | 自动跑获准断言并记录；质量豁免与权威来源优先级需 owner 审批 |
| Version/Decision | immutable ID、父版本、diff、draft/proposed/approved/deprecated、reviewer、批准时间、失效时间、回归结果 | 自动生成变更案与影响分析；批准由有权限的人/既定策略作出 |

**自动推断的正确产物是 proposal + evidence，而不是已生效事实。** 列名相似、类型兼容、值重叠、唯一率、历史 join、外键约束都是不同等级证据，必须保留来源和采样时间。

### 5.1 Join 推断与防重复计算

1. 从声明 FK、已发布 dbt/BI 模型、人工规则和查询日志提出候选，再用列名/类型/embedding 扩充；不要全库任意两列盲配。
2. 用获准抽样/聚合验证 uniqueness、null、referential coverage、左右匹配数分布；记录分区、tenant、时间窗，区分全量约束与抽样结论。
3. 同时检测复合键、单位/编码转换、历史快照、逻辑删除、tenant key；抽样上的 1:1 不保证未来仍成立。
4. 估计 join 前后行数与指标总和，标记 fanout；N:N 需要 bridge、先聚合或明确去重策略，不能自动 `DISTINCT` 掩盖业务歧义。
5. 用业务 owner 确认语义、grain、连接方向和时间窗；批准后仅发布允许路径，并生成可回归的正反例查询。

### 5.2 Agentic 检索与执行建议

`身份/目的 → 固定 semantic release → 探查可见目录 → 业务词/指标/示例混合召回 → 表召回 → 字段召回 → 受限值查找 → approved graph 补齐 join → 歧义确认 → 语义计划/SQL → 静态与引擎校验 → 执行 → 工件与反馈`

- 表/字段/值是独立工具边界，分别控制 top-k、预算、可见性和样本出域；返回 stable ID、version、来源、score 与缺失信息。
- join 闭包需要把未被文本召回命中的 bridge/time/tenant key 补回，不能只把每个 top-k 片段直接拼 prompt。
- 有受治理指标时优先生成 `metric + dimensions + filters + time` 计划；自由 SQL 用于探索，并显式标记未认证口径。
- 执行前检查 AST、目标对象/列/函数、只读、租户策略、grain/fanout、参数绑定，再做真实 engine dry-run/EXPLAIN 与资源限额。
- 只读 SQL 仍可能通过文件/网络函数读取越界数据或消耗资源；最终授权要落在 connector 身份与隔离执行环境，不能只靠提示词。
- 字典/示例/用户文档视为数据，不允许覆盖执行与权限策略；检索索引按租户/权限/semantic release 过滤，不能检索后才隐藏展示。
- 查询成功后保存 question、计划、SQL、source snapshot/as-of、semantic release、模型/工具版本、policy decision、结果引用；用户反馈先进入待审案例池。
- 人类确认用于指标歧义、时点/grain、可执行 join 发布、敏感值访问、导出或写操作；已批准的重复只读查询可按既定策略直接运行。

### 5.3 具体静态走读：按地区统计上季度净收入

前提 **[建议]**：已批准 `net_revenue` 的退款/币种规则；orders 一行一订单，customers 一行一客户；customer FK→PK 是 N:1，使用付款时间和 Asia/Shanghai 自然季度。

| 阶段 | 输入/中间状态 | 验证重点 |
| --- | --- | --- |
| 召回 | “净收入”命中 metric ID；“地区”命中 customer.region；召回历史例子 | 例子必须和当前语义版本一致；地区是否当前属性或交易时属性 |
| 连接 | approved orders→customers 边；补回 customer_id、tenant_id | N:1 与 tenant scope；若客户为 SCD，则加付款时点有效期 |
| 计划 | metric、region、上季度时间范围、timezone、默认退款过滤 | 用户只需确认真正缺失的业务选择；不让模型重写已批准公式 |
| 编译 | MDL/MetricFlow 类编译层输出 SQL/plan | 检查 fanout、policy、时间边界与 engine EXPLAIN |
| 执行与留痕 | 只读 connector → 结果表/图表工件 → evidence record | 绑定 semantic release 和数据 as-of；成功执行不自动变更指标 |

这是设计推演，未对真实数据库执行，也不是任一项目的端到端实测。

## 6. 模块复用优先级与验收问题

| 能力 | 优先考察 | 必须补齐或证实 |
| --- | --- | --- |
| Excel/JSON 即席分析 | DuckDB/Arrow + 文件导入模块 | Excel 公式缓存、多 sheet、多表头、JSON nested grain、大小/资源限制 |
| API/MCP 探查 | DataHub/OpenMetadata catalog adapter + 受控 connector | 分页、一致性、字段映射、credential reference、来源与快照 |
| 业务语义与 join | Wren MDL；指标密集环境评估 MetricFlow；Cube 作 BI 服务备选 | ontology 治理字段、审批、版本固定、权限接入、grain 与时间回归 |
| agent 表/字段/值召回 | DB-GPT 分级检索；SuperSonic 的元素映射设计；Wren memory | 值字典授权、join closure、错误恢复、查询预算、租户隔离 |
| BI/表格输出 | 统一 Arrow/结果 schema，使用本地表格/图表组件 | 导出规则、缓存按权限分区、结果可复现，不重复接管 MintHub runtime |
| 预测/函数 | RD-Agent 实验链参考，另评估 AutoGluon | 时间验证、泄漏检查、资源预算、基线、模型发布审批与监控 |

进入实现前，应选 20–50 个带口径和正确结果的企业问题作为小型本地评估集，覆盖同名异义、无 FK、多对多、SCD、跨租户、敏感值、脏数据和 schema 变更；不直接套用公开 NL2SQL 榜单推算上线准确率。

## 7. 一手来源与源码阅读索引

以下链接固定到本次读取 SHA；路径和行锚点用于复核，不引用浮动 main/master 作为关键实现证据。

- [W1 WrenAI README](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/README.md)；[W2 MDL model/relationship/cube macros](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren-core-base/manifest-macro/src/lib.rs#L133)；[W3 manifest/PrimaryKey/layout](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren-core-base/src/mdl/manifest.rs#L98)。
- [W4 context.py](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/context.py#L21)；[W5 MemoryStore.get_context](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/memory/store.py#L290)；[W6 engine.py](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/engine.py#L97)。
- [W7 policy.py](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/policy.py#L1)；[W8 access control provider](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren-core/core/src/logical_plan/analyze/access_control/wren_provider.rs#L20)；[W9 ask.py](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/ask.py#L1)。
- [W10 归档 Ibis server Rewriter](https://github.com/Canner/wren-engine/blob/bc2b06a1950a946aa9bd16356fe0c84e9dc504bc/ibis-server/app/mdl/rewriter.py#L30)；[归档声明](https://github.com/Canner/wren-engine/blob/bc2b06a1950a946aa9bd16356fe0c84e9dc504bc/README.md)；[W11 Wren 路径许可](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/LICENSE)。
- [V1 Agent](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/core/agent/agent.py#L56)；[README](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/README.md)；[V2 legacy generate_sql](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/legacy/base/base.py#L93)。
- [V3 registry/NoOp transform](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/core/registry.py#L98)；[V4 RunSqlTool](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/tools/run_sql.py#L56)；[V5 LICENSE](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/LICENSE)。
- [D1 DB-GPT README](https://github.com/eosphoros-ai/DB-GPT/blob/06a46eea2d248a0f2b3e9096035424df4f2dc2eb/README.md)；[D2 ChatDB](https://github.com/eosphoros-ai/DB-GPT/blob/06a46eea2d248a0f2b3e9096035424df4f2dc2eb/packages/dbgpt-app/src/dbgpt_app/scene/chat_db/auto_execute/chat.py#L49)。
- [D3 DBSummaryClient](https://github.com/eosphoros-ai/DB-GPT/blob/06a46eea2d248a0f2b3e9096035424df4f2dc2eb/packages/dbgpt-serve/src/dbgpt_serve/datasource/service/db_summary_client.py#L98)；[D4 DBSchemaRetriever](https://github.com/eosphoros-ai/DB-GPT/blob/06a46eea2d248a0f2b3e9096035424df4f2dc2eb/packages/dbgpt-ext/src/dbgpt_ext/rag/retriever/db_schema.py#L190)；[D5 LICENSE](https://github.com/eosphoros-ai/DB-GPT/blob/06a46eea2d248a0f2b3e9096035424df4f2dc2eb/LICENSE)。
- [S1 SuperSonic README](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/README.md#L45)；[S2 Ontology](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/core/src/main/java/com/tencent/supersonic/headless/core/pojo/Ontology.java#L13)；[S3 JoinRelation](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/core/src/main/java/com/tencent/supersonic/headless/core/pojo/JoinRelation.java#L11)。
- [S4 EmbeddingMapper](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/EmbeddingMapper.java#L35)；[SchemaMapper 接口](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/SchemaMapper.java#L5)；[S5 EmbeddingMatchStrategy](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/EmbeddingMatchStrategy.java#L46)。
- [S6 LLMSqlParser](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/parser/llm/LLMSqlParser.java#L48)；[S7 DefaultSemanticTranslator](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/core/src/main/java/com/tencent/supersonic/headless/core/translator/DefaultSemanticTranslator.java#L27)。
- [S8 S2DataPermissionAspect](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/server/src/main/java/com/tencent/supersonic/headless/server/aspect/S2DataPermissionAspect.java#L69)；[S9 带商业附加条件的 LICENSE](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/LICENSE#L7)。
- [R1 RD-Agent README](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/README.md)；[R2 DataScienceRDLoop](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/loop.py#L87)。
- [R3 DSCoSTEERRunner](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/dev/runner/__init__.py#L140)；[R4 DSInteractor/超时继续](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/rdagent/scenarios/data_science/interactor/__init__.py#L71)；[R5 LICENSE](https://github.com/microsoft/RD-Agent/blob/484776c211e4fbbeef03e0ec00d6bbee7362a4f4/LICENSE)。
- [H1 DataHub README](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/README.md)；[H2 SchemaMetadata.pdl](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/schema/SchemaMetadata.pdl#L14)；[H3 SchemaField.pdl](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/schema/SchemaField.pdl#L11)。
- [H4 GlossaryTermInfo.pdl](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/glossary/GlossaryTermInfo.pdl#L14)；[H5 DataHubPolicyInfo.pdl](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/policy/DataHubPolicyInfo.pdl#L3)。
- [H6 VersionProperties.pdl](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/common/VersionProperties.pdl#L11)；[H7 LICENSE](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/LICENSE)。
- [M1 MetricFlow README/许可历史](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/README.md)；[M2 engine](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/metricflow/engine/metricflow_engine.py#L522)；[M3 join evaluator](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/metricflow_semantics/model/semantics/semantic_model_join_evaluator.py#L44)；[M4 LICENSE](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/LICENSE)。
- [C1 Cube README/Core 与商业边界](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/README.md)；[C2 JoinGraph.ts](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/packages/cubejs-schema-compiler/src/compiler/JoinGraph.ts#L68)；[C3 LICENSE](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/LICENSE)。
- [X1 XiYan-SQL README](https://github.com/XGenerationLab/XiYan-SQL/blob/603dedac706d57ece47bc30d02f90744a537b6a0/README.md#L29)；[X2 m_schema.py](https://github.com/XGenerationLab/M-Schema/blob/755751451be841f7a54f8b08c0a1f818b041a1c0/m_schema.py#L5)；[X3 schema_engine.py](https://github.com/XGenerationLab/M-Schema/blob/755751451be841f7a54f8b08c0a1f818b041a1c0/schema_engine.py#L82)；[X4 LICENSE](https://github.com/XGenerationLab/M-Schema/blob/755751451be841f7a54f8b08c0a1f818b041a1c0/LICENSE)。
- [B1 DuckDB README](https://github.com/duckdb/duckdb/blob/ed0443f18a0267ec5814d7cc2f1f421ad3e5b335/README.md)；[B2 LICENSE](https://github.com/duckdb/duckdb/blob/ed0443f18a0267ec5814d7cc2f1f421ad3e5b335/LICENSE)；[B3 SQLGlot README/FAQ](https://github.com/tobymao/sqlglot/blob/f31f109daef0ca99347d36295534a0d59956059c/README.md)；[B4 LICENSE](https://github.com/tobymao/sqlglot/blob/f31f109daef0ca99347d36295534a0d59956059c/LICENSE)。
- [O1 OpenMetadata README](https://github.com/open-metadata/OpenMetadata/blob/eeee22d6f74cd926d71dec61fa232b690ff7c692/README.md)；[O2 LICENSE](https://github.com/open-metadata/OpenMetadata/blob/eeee22d6f74cd926d71dec61fa232b690ff7c692/LICENSE)。
- [A1 DB-GPT-Hub README](https://github.com/eosphoros-ai/DB-GPT-Hub/blob/3ed19c1fcf848f064d129131c3b1e7d7ae86df17/README.md)；[A2 Chat2DB README/许可声明](https://github.com/chat2db/Chat2DB/blob/ce3f045bdcfa19ab611cb4d686c44212fe6a4f31/README.md)；[A3 Dataherald README](https://github.com/Dataherald/dataherald/blob/f8946182e6db55522b88cd5a831c788339b8fc42/README.md)。

后续阅读优先级：Wren MDL→engine/policy→SDK；MetricFlow join evaluator→time/SCD tests→query parser；SuperSonic mapper→corrector→权限入口；最后按同一企业评估集验证，不继续扩大项目名单代替实验。
