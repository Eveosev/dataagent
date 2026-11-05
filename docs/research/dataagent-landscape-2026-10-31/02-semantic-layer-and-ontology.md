# DataAgent 的语义层、Ontology、实体关系与版本机制

研究日期：2026-10-31，Asia/Shanghai。本文研究外部技术方案，不是实施计划，也不要求采用某个运行时或先完成全企业建模。

证据标记：**[事实·源码]** 固定提交中的静态实现；**[事实·官方]** 官方规范或产品文档的描述；**[推断]** 从这些材料归纳的适用范围；**[建议]** 可参考的设计机制；**[未核实]** 当前证据不足。没有执行、安装或大规模克隆第三方代码，没有数据库实测、准确率评测或完整法律审计。

## 1. 结论

1. **应组合不同层次的能力。** glossary/catalog 管资产和术语；MetricFlow、Cube、Wren MDL 等可执行语义层生成或重写查询；object ontology 定义业务对象及其关系、约束乃至动作；Ossie 是语义定义交换规范。它们解决的问题不同，不能作为同类可替代产品排名。
2. **治理重点是少数关键口径及危险连接。** 已有认证指标应直接复用；长尾探索可以按问题读取 dbt 转换、上游 DAG、应用代码、历史 SQL 和业务说明，再验证结果。经复核且反复使用的定义再固化。[建议] 不必先完整建模，但必须知道本次答案采用了什么定义、证据和时点。
3. **MetricFlow 最值得参考的是类型化 join 与指标计划。** PRIMARY/UNIQUE/FOREIGN/NATURAL、有效期和可用维度约束优于按字段名拼 join；它不负责自动发现正确业务口径，也不能证明源数据符合声明。[事实·源码][推断]
4. **Cube 提供另一种 fanout 处理机制。** 对声明会倍增的度量，按其实体主键去重、独立聚合再合并；这与 MetricFlow 限制危险 join 的策略不同。两者都依赖可靠的键、粒度和关系声明，不能自动解决多对多分摊业务含义。[事实·源码][推断]
5. **Apache Ossie 当前必须按草案看待。** 官方名称为 Apache Ossie（incubating），原名 Open Semantic Interchange / OSI。当前 `0.2.0.dev0` 明示未发布、schema 可变、不要生产依赖；规范的版本史写 `0.1.1` 于 2025-12-11 首发，但本轮 remote 仅见 `osi-0.1.1-rc1` 标签，未取得可验证的 ASF 正式发行物。不能称“Apache 稳定版 0.2”，也不能把版本史自动等同 ASF 正式发布。[事实·官方]
6. **交换成功不等于语义等价。** Ossie 的 dbt 转换器明确报告 natural entity、漏斗、private 指标、累计窗口等损失；反向拒绝成组复合键并默认时间粒度为 DAY。它适合研究适配边界，不能据“支持 dbt”声称任意模型无损互通。[事实·源码]

## 2. 四个经常混淆的层次

| 层次 | 典型对象与职责 | 本轮参考 | 不能据此推出 |
| --- | --- | --- | --- |
| 术语与目录 | 资产 ID、schema、owner、描述、glossary、lineage、认证/审核状态、metadata version | DataHub、OpenMetadata | 能按经营口径计算指标、数据库授权自动落实、连接一定安全 |
| 可执行分析语义 | 物理映射、实体键、维度、度量/指标、时间粒度、合法 join、查询计划和 SQL | dbt Semantic Layer/MetricFlow、Cube、Wren MDL | 自动发现所有业务定义、所有表都已建模、任意 SQL 正确 |
| 对象 ontology | 对象类型/实例、属性、身份、关系、约束；部分平台还有 action/function 和对象权限 | Palantir；Ossie ontology 草案描述概念及映射 | 等于 BI 指标系统，或所有 ontology 都自带动作、推理、实体消歧、SCD 引擎 |
| 交换规范 | 跨工具编码上述部分定义、引用、扩展、schema 验证和转换损失 | Apache Ossie | 编译器、查询服务、授权服务、发布审批或跨引擎结果等价已经具备 |

**例子：**“客户”可以同时是 glossary term、数据目录中的 CRM 表、MetricFlow 的 join entity、Palantir 的 Customer object type、Ossie 的 EntityType。它们的稳定 ID、粒度和职责需要映射，名称相同并不构成同一对象。[推断]

Palantir 官方将 Ontology 描述为连接实际数据与现实对象的运营层，区分 objects/properties/links 与 actions/functions/dynamic security。Object type 是 schema，object 是实例，object set 是集合；link type 是关系 schema，link 是关系实例，多对多 link 可以由独立 datasource 支撑。[事实·官方][P1–P3] 这比分析语义层范围广，但本文没有验证它的指标 fanout、SCD 或部署性能，不能据厂商定位认定其能替代 MetricFlow。

## 3. 版本基线与本次增量

先读并复用 [昨日开源与 ontology 研究](../dataagent-2026-10-30/02-open-source-and-ontology.md) 第 3、5、7 节及 [昨日标准研究](../dataagent-2026-10-30/04-minthub-composition-and-standards.md) 第 5 节；不将旧文的产品组合建议视为本轮选型结论。

| 项目 | 固定提交 | 本轮边界 |
| --- | --- | --- |
| MetricFlow | `fe4b8c1ccb72a8ca77494b345777eff20a714119` | 当前 HEAD 与昨日相同；重读 README/LICENSE、engine、join evaluator，增读 entity protocol、dataflow builder、包许可 |
| dbt 官方文档 | `dea062642c4969d0a3709ee66580fa21e5acc524` | 语义模型、entities、dimensions/SCD、metrics、join、validate、商业服务/API 边界 |
| 旧 dbt-semantic-interfaces | `c2ba16a0c3367d68f5e14d3da1403858b66b6724` | README 已宣布弃用；`0.10.5` 为最后 release；MetricFlow `0.210.0` 起由 `metricflow-semantic-interfaces` 接替 |
| Apache Ossie | `2fd19c7a40b360bb87c18e8e0b7db482684b220a` | 当前 HEAD；昨日为 `7a8de20f850dad3934e307a1ac7425b09e9ca89f`。README/Core/expression/roadmap 字节相同；ontology 修正一处 YAML 列表示例 |
| Ossie converters | `46c673d18dd23e6c424798d952d7fd97496fd0cf` | 独立仓库，固定 README、dbt 转换器实现、issues、pyproject/LICENSE |
| Cube | `d1241a63d6802792b01dd5131eb2b43eb23a3b3d` | 沿用昨日 pin；重读 JoinGraph，增读 BaseQuery，结合当前官方模型/join 文档；未声称重核其 HEAD |
| WrenAI | `8edc086b1f8f9f2974b9faf8ab7c639c85851b46` | 沿用昨日 pin；重读 MDL、复合键/layout、context/memory、路径许可 |
| DataHub / OpenMetadata | `47be57949cf2b85c291228d5c1ce689a2b0ee795` / `eeee22d6f74cd926d71dec61fa232b690ff7c692` | 沿用昨日 pin；复核 schema/glossary/version 及 OpenMetadata glossary 审批字段 |

注意 dbt 文档包含 `1.9–1.11` 与 `1.12` 的 VersionBlock：旧版 standalone `semantic_models`/measures 与新版 model 内 column-level entity/dimension、simple metric 形状不能混用。文档提及 `1.12` 产生 `osi_document.json`，只证明文档中的特定版本行为，不证明当前客户制品已经支持。[事实·官方][D1–D4,D8]

## 4. 定义能表达什么，哪些仍要补充

| 定义 | dbt/MetricFlow | Cube | Wren MDL | Ossie 当前草案 | 需要保留的业务问题 |
| --- | --- | --- | --- | --- | --- |
| 实体、标识 | 逻辑实体名与 PRIMARY/UNIQUE/FOREIGN/NATURAL；`expr` 映射到列或表达式 | Cube + `primary_key` dimension、关系声明 | Model + 单列/复合 PrimaryKey、relationship | Core dataset PK/unique_keys；ontology EntityType/ValueType、identify_by | tenant scope、跨系统 identity、合并/拆分、逻辑删除 |
| 指标/度量 | simple、ratio、derived、cumulative、conversion；聚合、筛选、time spine、non_additive 等 | measure 类型、SQL、筛选、预聚合；编译时处理 multiplied measure | Cube 内 measure 的 name/expression/type，基于 model | dataset/model scoped metric SQL；不支持 metric 引用 metric | 净额/税费/退款、distinct 对象、半可加性、分摊、缺失值 |
| 维度 | categorical/time，绑定 primary entity，查询时推导可达维度 | dimension、hierarchy、segment | dimension/time_dimension、drill-down hierarchy | field、datatype、dimension.is_time；ontology 属性关系 | 哪个指标可按其切分、分类有效期、敏感值 |
| 粒度 | 实体键、聚合、group by、时间粒度；声明驱动 | 主键、维度和聚合计划 | model 主键与 Cube 分组；不是业务 grain 证明 | Core 有键；一等 grain/aggregation 仍在 roadmap | 一行是订单、订单行、事件、日快照还是累计快照 |
| 时间 | agg_time_dimension、time_granularity、time spine、SCD validity | time dimension 和查询粒度；任意 SQL 不等于自动 SCD 契约 | time_dimension 表达式/类型；已读类型未建立完整 SCD 契约 | is_time 与 Date/DateTime/DateTimeTz；无可移植时间粒度字段 | event/booking/payment 时间、时区、财务日历、迟到/更正、as-of |
| 单位/币种 | 可放 meta/定义中；本文未验证自动单位推理或汇率一致性 | 显示格式/SQL 可以表达；不证明量纲运算正确 | 类型/表达式可以承载；未核实自动单位演算 | datatype 表值类型；measurement 等仍为扩展提案 | 元/分、USD/CNY、汇率来源/时点、可相加单位 |
| 关系/物理映射 | entity name 建图，model/ref 与 expr 映射；合法 join 由编译器决定 | join SQL + relationship、sql_table/sql/data_source | ref_sql/table_reference/base_object、column expression、join condition/type | source、field expression、FK 数组；ontology 独立概念映射 | bridge、路径歧义、时间条件、API/JSON 数据粒度 |

表内是表达能力，不是质量保证。[事实·源码/官方][D1–D6,M1–M4,C1–C3,W1–W3,O1–O4] 同名 `Cube` 在 Wren MDL 中是其分析类型，不能误认成 cube-js 产品。

**[建议]** 对高价值定义，最小记录应包括稳定概念 ID、业务定义/别名、数据集 grain、键及 tenant scope、指标公式/聚合/可加性、维度适用范围、时间角色/时区/日历、单位/币种、关系与物理映射、出处、验证证据和负责审核者。无需把所有字段都塞进某一厂商 schema；不能无损映射的部分应明确保留并报告。

## 5. dbt Semantic Layer 与开源 MetricFlow

本节研究范围是语义引擎和托管接口，不能据此概括整个 dbt 产品线。补核的 Wizard、Explore、Copilot/Insights 和 MCP 产品能力见 [dbt AI 专题](05-dbt-ai-addendum.md)；dbt 同时属于竞品和可集成基础设施。

### 5.1 商业服务、开源库与许可证不能混称

**[事实·官方]** dbt architecture 表将 MetricFlow 与 semantic interface 配置列为 Apache-2.0，本地可用；Service layer/Gateway、托管 Semantic Layer APIs 列为 proprietary，按当日文档属 Starter/Enterprise 等付费能力。[D7–D9] 自建 MetricFlow SQL 编译服务是可研究的组合方式，不等于获得 dbt 托管 API、认证、缓存、连接器集成和 SLA。

**[事实·源码]** 当前 MetricFlow README、LICENSE、`pyproject.toml` 的许可一致为 Apache-2.0。README 的历史说明为：0–0.140.0 AGPL、0.150.0–0.208.2 BSL、0.209.0+ Apache-2.0；README 仍有“source-available”措辞与旧徽章，不能用这些词替代固定版本 LICENSE。[M1,M5] 旧 BSL 版本或独立商业服务的条款不能从当前 Apache 许可倒推。

**[事实·源码]** `MetricFlowEngine.query → _create_execution_plan → query parser/dataflow → execution plan → SequentialPlanExecutor`；`explain` 暴露计划/SQL。它是指标语义编译与执行接口，不是完整 DataAgent、业务审批系统或对象操作平台。[M2]

### 5.2 Join、SCD、复合键和多事实表

- **非 fanout 类型约束。[事实·源码]** `SemanticModelJoinEvaluator` 允许 FOREIGN→PRIMARY/UNIQUE 和部分 NATURAL 组合，拒绝 FOREIGN→FOREIGN、PRIMARY→FOREIGN、NATURAL→NATURAL 等；右侧 NATURAL 必须有 validity dimensions，两侧都带有效期时直接拒绝。[M3] 该文件声明 `MAX_JOIN_HOPS = 2`；本轮仅核对常量，未追踪其全部调用路径，不能据此认定系统实测 join 上限，也不能宣传任意深度关系推理。
- **数据约束仍要验证。[推断]** 如果表实际上有重复主键、缺 tenant_id 或时间窗重叠，即使声明为 PRIMARY，类型判断也不会替代实际数据校验。`EXPLAIN` 成功不能证明收入不重复。
- **SCD 不是普通等值 join。[事实·官方]** 文档要求 natural entity、valid_from/valid_to、每个键不重叠的有效期；示例使用 `metric_time >= valid_from AND (metric_time < valid_to OR valid_to IS NULL)`。SCD semantic model 不能含 measures（旧形状）或 simple metrics（新版形状）。尤其要注意文档称粗时间粒度下默认取该粒度起点生效的维度值；不能默认等于逐笔交易时点归属。[D3] 哪个规则符合业务必须单独确认。
- **复合键是表达式边界。[事实·源码/官方]** entity protocol 的 `expr` 是单字符串；dbt 文档建议将多列组合为 surrogate expression。Ossie→MSI 转换器明确拒绝多字段 PK/unique key，理由是无法无损保留成组键语义。[D2,M4,O7] 因而不能说 MetricFlow 原生接收任意 tuple key。字符串拼接/hash 还要处理分隔符、NULL、类型、碰撞和 tenant scope。[建议]
- **多事实表不能直接明细互连。[事实·官方/源码]** dbt 文档描述多事实表使用 full outer join；dataflow builder 中使用 `CombineAggregatedOutputsNode` 合并已聚合输出。[D5,M6] 可借鉴“每个事实按合法公共粒度分别计算再对齐”的机制。[建议] 公共维度、缺失组、NULL/0、不同时间角色和 ratio 分子/分母粒度仍须验收，不能把该机制理解成开放 FOREIGN→FOREIGN 明细 join。

### 5.3 验证、发布与 schema drift

**[事实·官方]** 文档提供 `mf validate-configs` / `dbt sl validate`、warehouse validation/EXPLAIN、配置与可达维度检查；旧版有 `--skip-dw`，所以“validate 通过”还必须说明具体执行了哪些检查。[D5,D6] 文档建议在 PR/CI 验证，再 merge、parse、部署 manifest；托管 API 使用最近一次部署 manifest。[D8,D10]

**[推断]** Git 提供变更历史，manifest 提供某次解析的结构，发布环境提供当前服务定义；它们不自动形成“业务口径 11 月 1 日生效、10 月报表按旧定义重算”的双时间契约。本轮未验证托管 API 对任意历史 semantic release 的查询固定能力。schema 漂移也不止列不存在：类型变化、键唯一性改变、枚举漂移、有效期重叠和币种切换可能继续编译成功。

## 6. Cube 与 WrenAI 的可参考机制

### 6.1 Cube：从关系声明推导倍增风险，再按键聚合

**[事实·源码]** `JoinGraph.ts` 检查 sum/avg/count/number 等受倍增影响的 measure 是否有 primary key，根据 `hasMany/belongsTo` 等关系推导 multiplicationFactor；冲突 join 声明会被报错或排除。[C2]

**[事实·源码]** `BaseQuery.ts::fullKeyQueryAggregate` 分离 multiplied/regular/cumulative measures；`aggregateSubQuery` 以 `primaryKeyDimensions` 构造去重键查询、按多列 `AND` 连接后聚合；无法安全处理的跨 cube measure 会抛出 row multiplication 错误。[C3] 官方文档也解释 fan/chasm trap 的 distinct 主键再聚合过程，并给出多列组合键示例。[C4]

**[建议]** 值得参考的是“关系声明→每个度量的倍增标记→分支查询→结果对齐→不可处理时报错”的编译机制。不要概括成对所有 join 统一 `DISTINCT`，更不能推断系统自动决定多对多 attribution。一个订单可以属于两个活动，按活动去重求收入后各组相加仍可能大于总收入；这涉及指标是否可加和是否要权重分摊。[推断]

**[未核实]** 本轮没有沿 Cube 的 SCD、口径审批、业务生效时间全链检查，不把自由 SQL、Git 配置或 refresh_key 当作这些能力的证明。根 LICENSE 规定默认 Apache-2.0、部分包 MIT；已读 schema-compiler LICENSE 为 Apache-2.0；Cube Core 与商业 Cube 产品范围分别见固定 README。[C1,C5]

### 6.2 WrenAI：文件化 MDL 与按 manifest hash 限定上下文

**[事实·源码]** 当前 pin 的 MDL Model 有物理表/query/base object、columns、单列/复合 PrimaryKey；Relationship 具有 models、condition、ONE_TO_ONE/ONE_TO_MANY/MANY_TO_ONE/MANY_TO_MANY；Cube 定义 measure/dimension/time_dimension/hierarchy。[W1,W2] “能表达 N:N”不等于已经验证所有 N:N 聚合正确。

**[事实·源码]** `manifest.rs` 拒绝超过 engine 支持范围的 `layout_version`；这是序列化布局兼容性，不能当业务发布版本。`MemoryStore.get_context` 使用 `mdl_hash` 限制 schema 检索，schema 更新可替换 seed query 并保留用户确认历史；“保留历史”也意味着历史问答不能无条件作为新口径正确答案。[W2,W3]

**[建议]** 可参考文件项目、manifest hash、先 dry-plan/重写再查询、schema 与人工知识分别留存的机制。继承昨日研究的边界：当前 Rust/DataFusion engine 已整合在 `core/`，不要把归档 Ibis server 当当前架构；“user-confirmed”标签和文档流程也不能代替有权限的审批状态机。core/sdk/skills/examples 在该 pin 为 Apache-2.0、docs 为 CC BY 4.0，发布制品仍按其 manifest 的优先规则检查。[W4,W5]

## 7. Apache Ossie：标准化了什么，尚未完成什么

### 7.1 名称、Apache 归属与发布状态

**[事实·官方]** ASF Incubator 的状态页记载 Ossie 于 **2026-06-22** 进入孵化，源码为 `apache/ossie`；项目在 **2026-07-10** 公告更名，避免 OSI 缩写歧义。它处于孵化阶段，不能写成已毕业顶级项目或 ASF 对实现稳定性的背书。[O9,O10]

**[事实·源码]** 当前 Core 首页写 DRAFT，version=`0.2.0.dev0`；Version History 写未发布且 schema 可变、不要生产依赖。Ontology 也标 `0.2.0.dev0`，不能因为文件没有重复 DRAFT 横幅就当独立稳定规范。[O1,O2] 版本史的 `0.1.1 (2025-12-11)` 是可核实文本；remote `osi-0.1.1-rc1` 解引用到 `faf581054dcf7964d5fe0ceae7d6f415c8ce32a5`，对应 spec 标 0.1.1；该标签带 rc，本轮 ASF downloads 路径返回 404，未验证发行投票与制品。因此这里只称“版本史记录的历史 0.1.1”，不声称已核实最新正式稳定发行。[O11]

### 7.2 Core、ontology 与表达式的边界

- **Core。[事实·源码]** 一份 JSON/YAML 对应一个 model；包含 dataset/source、PK/unique keys、field expression、FK 数组关系、dataset/model scoped metrics、datatype、is_time、ai_context、custom_extensions。`from/to_columns` 是声明 field 的名字，不是物理 source column；迁移时不处理这点可能得到语法有效但含义错误的 SQL。[O1]
- **复合键。[事实·源码]** Core 支持键字段数组和有顺序的多列关系，但关系形状是 many→one 外键边；它不是任意时间区间谓词或完整 N:N attribution 模型。[O1]
- **Ontology。[事实·源码]** EntityType/ValueType、extends、identify_by、requires、derived_by、relationship multiplicity、IRI 与逻辑模型映射分开描述概念与物理表示；compound identity 示例通过 referent mappings 表达。[O2] 这些是声明，不证明有实体匹配服务、OWL 推理器、约束执行器、动作系统或数据质量监控。
- **映射演进。[事实·源码]** 新草案推荐独立 mapping document，引用恰好一个 ontology 与一个 semantic model；embedded `ontology_mappings` 已 deprecated，但文本明确说 standalone mapping 的 parser/converter 支持尚未提供，需要另加。[O2] 规范表达力与工具可消费性要分开记录。
- **表达式。[事实·源码]** `OSSIE_SQL_2026` 定义逻辑层可移植 SQL 子集；其他 dialect string 是 opaque，消费者可以忽略。表达式文档明确“model declaration”与“querying”不同，它不定义查询 API；添加 DAX/SQL 方言名称不能推出有对应执行引擎。[O3]
- **仍缺的通用语义。[事实·源码/官方]** Core 当前不允许 field 引用 field、metric 引用 metric、dataset 以另一个 dataset 为 source，也不定义跨 model 引用/bundle。grain、聚合/窗口、日历和时间、版本/访问控制/治理、标准查询语言与 reference compiler 仍出现在 roadmap。[O1,O4] datatype/is_time 不能代替时区、SCD、财务日历、单位或汇率规则。

### 7.3 转换器不是互操作性证明

**[事实·源码]** `apache/ossie-converters` 独立版本；根 README 与 dbt `pyproject.toml` 当前使用 `0.2.0.dev0`，dbt 包名 `apache-ossie-dbt`，Apache-2.0。spec 仓库及 converters 根 LICENSE 都为 Apache-2.0；不由此推定各厂商服务许可。[O5,O8]

| dbt 转换方向 | 该固定提交的行为 | 含义 |
| --- | --- | --- |
| MSI→Ossie | `CONVERSION_METRIC_DROPPED`、`PRIVATE_METRIC_DROPPED`、`NATURAL_ENTITY_DROPPED` | 漏斗、可见性、SCD 身份不等价 |
| MSI→Ossie | 累计指标保留基础聚合但报告 `CUMULATIVE_SEMANTICS_LOSS`；非累计指标若被 `_has_nonportable_semantics` 判定涉及不可移植 window/grain/offset/time-spine 等语义，则报告 `NON_PORTABLE_METRIC_SEMANTICS` 并整项 drop | 基础聚合降级与指标整项丢弃是两种不同结果；不能把 warning 当无关元数据 |
| MSI→Ossie | 复用同一 metric reference 的不同 filter 无 alias 时可能歧义并 drop；常量聚合在多 dataset 时报告来源归属损失 | 指标组合/row count 也要检查 |
| Ossie→MSI | 成组 composite PK/unique key 抛 ValueError；复杂跨 dataset 表达式、窗口/嵌套聚合/自定义函数等不支持 | schema 能表达并不表示转换器能消费 |
| Ossie→MSI | 时间维度固定 `TimeGranularity.DAY`；对支持输入 best effort 推导 SIMPLE/RATIO 等 | 导入后必须重新验证最小粒度和时间含义 |

上表同时核对 README、`msi_to_ossie.py`、`ossie_to_msi.py` 和 `converter_issues.py`，不是运行结果。[O6,O7]

**[建议]** 有价值的机制是返回 `output + issues`、明确支持矩阵、输入/输出验证、保留未知 extension、按版本迁移。生产适配是否阻断，应按每一条损失是否影响口径决定。至少要区分：结构通过、转换无损、目标编译成功、样例结果相等、权限等价；这五件事不能互相代替。README 的 hub-and-spoke 图和厂商列表只说明目标架构/存在转换方向，不能证明所有转换器全量、双向、无损或已发布。

## 8. 自动候选、审核、版本与 schema drift

### 8.1 自动化产物应是候选和证据

**[建议]** 自动来源可以分层：已有认证 BI/dbt 指标与 FK → schema/约束/lineage → 历史 SQL/转换代码 → 合法采样/统计 → 文本或 embedding 推断。每个候选附来源、源版本、采集时间、范围与置信信息；统计唯一率和列名相似不能直接提升为业务事实。

| 候选 | 技术验证 | 仍需业务判断 |
| --- | --- | --- |
| 实体/复合键 | 唯一性、NULL、tenant 组合、碰撞、逻辑删除 | 是否代表同一对象、跨系统冲突如何处理 |
| join | 左右匹配数分布、coverage、join 前后行数/总额、时间窗重叠/缺口、跨租户负例 | 关系含义、允许方向、桥表及分摊规则 |
| 指标 | 类型/单位、聚合层次、时间边界、已知样例对账、反例 | 退款/税费/状态过滤、业务时间、认证 owner |
| 维度和值 | 枚举分布、编码映射、有效期、权限范围 | “01”含义、当前/历史属性、可切分范围 |
| mapping | 方言 AST/编译、字段存在、转换前后对账、API 分页和嵌套粒度 | 权威来源、同名概念是否等同 |

**[事实·源码]** DataHub 的 `SchemaMetadata` 有 schema hash、fields、PK/FK；`GlossaryTermInfo` 有 definition/sourceRef/sourceUrl；VersionProperties 有 versionSet、tag、alias、时间与注释。[H1–H3] OpenMetadata 的 table schema 有列/约束、join 使用信息与版本；glossaryTerm schema 有 reviewers/status、changeDescription。[H4,H5] 这说明已有资产可作为候选来源和追溯锚点；本轮没有验证这些字段对每种变更都执行了所需审批，尤其不能把 glossary Approved 自动当可执行 join Approved。

### 8.2 别把所有“版本”压成一个数字

| 版本/时间 | 意义 | 不可替代的其他项 |
| --- | --- | --- |
| source schema fingerprint | 此次看到的物理结构/约束 | 业务定义、数据值快照 |
| semantic revision/release | 一组指标、关系、映射及规则的内容 | 数据 snapshot、审批身份 |
| spec/layout version | 解析器理解的文件结构，如 Ossie version、Wren layout | 业务口径生效时间 |
| review/deploy time | 谁在何时批准、何时服务开始使用 | 该口径适用哪个业务期间 |
| business effective interval | 某定义/映射对哪些业务时间有效 | 系统何时获知这条更正 |
| SCD valid interval | 对象属性在现实/业务中的有效期 | 指标公式版本、查询执行时间 |
| data as-of/snapshot | 答案基于哪份数据、是否可重现 | 语义口径与政策版本 |
| index/context build | 检索索引、人工说明、示例依赖哪些定义 | 原始源的完整性与实时状态 |

**[建议]** 对需要追溯的场景，可记录 draft/proposed/reviewed/released/deprecated 状态、不可变 revision、父版本/diff、reviewer、批准与部署时间、effective_from/to、影响资产、回归结果。业务追溯需要时再区分 valid-time 与 recorded-time；不要求每个临时分析都采用重型发布流程。

**[建议]** schema drift 检测后先判断影响：新增无关列可更新目录；引用列删除/改名、数值类型/单位改变、PK 不再唯一、SCD 重叠、grain 变化、权限收紧须重新验证受影响关系/指标。旧 release 的物理映射可能失效，保留旧 YAML 并不能保证可重放。查询记录应绑定 semantic release、source schema、数据 as-of、policy、引擎/适配器版本与 SQL/计划；索引至少避免混用旧 schema（Wren 的 mdl_hash 是具体参考）。

### 8.3 静态语义与动态上下文可以并存

**[建议]** 对外可提供两种清楚的分析路径：认证 KPI 查询绑定已发布定义；探索问题按需读取转换/DAG/应用代码、业务 quirks 与已审核问答，生成带来源的计划并检查。第二条路径产出的高复用定义可经复核进入第一条；从已有 trusted metric 开始，无需复制或改写另一套公式。

Jamie Quint 的 *How to Build a Data Agent in 2026*（2026-03-06）主张按问题读取转换逻辑、DAG、应用代码；LinkedIn 的 *Inside LinkedIn’s Data Context Layer*（2026-10-09）描述自动 schema/code/query-log/sample context 与 owner-reviewed Git 知识分别存储、按 asset ID 结合读取。[外部案例，正文及缓存见主报告来源][X1,L1] Ramp/Ian Macomber 的 *Post AI Data Stack*（2026-08-30）则提供 agent 可读 Markdown/SQL、缓存结果与跨界面同指标核对的案例。[R1] 它们支持研究渐进建模/上下文维护，但不证明“语义层已无用”，也不证明长尾 SQL 不再需要粒度、join 和业务审核。本文未独立复核两篇案例的量化结果，不引用其数字作为组件能力证据。

## 9. 适用机制与主要未解问题

| 场景 | 值得参考的机制 | 选择前的关键缺口 |
| --- | --- | --- |
| 已有 dbt、认证指标密集 | MetricFlow 的实体类型、合法维度枚举、指标计划、parse/validate/CI；已有托管服务可直接引用 | 客户实际版本、复合键、SCD 分桶规则、历史 release 固定、权限和成本 |
| 嵌入式 BI/API、多维聚合 | Cube 的关系模型、每度量倍增分析、按键独立聚合、结果对齐 | 多对多归因、SCD/半可加性、复杂 measure、数据质量与发布治理 |
| SQL 探索与语义重写 | Wren 文件 MDL、复合键、manifest hash 上下文、规划与执行边界 | 目标 connector、N:N/SCD 正确性、审批与兼容版本、历史示例再验证 |
| 企业对象/工作流 | Palantir 的 type/instance/set 与 property/link/action/function 分层 | 产品锁定、真实执行/权限语义、是否确实需要动作而非只读分析 |
| 多工具定义交换 | Ossie 的概念/逻辑/物理映射区分、extensions、转换损失结果 | 草案变更、正式发布物、工具支持、semantic round-trip、单位/时间/治理缺失 |
| 已有元数据治理 | DataHub/OpenMetadata 稳定资产 ID、来源、owner、glossary 与版本导入 | 权限范围、同步冲突、人工纠错保护、认证状态能否映射为执行资格 |

仍不能由公开材料回答的问题包括：目标企业中正确的 grain/身份是什么；每个危险 join 的真实数据分布如何；多事实指标能共享哪些维度/时间角色；单位和汇率如何管理；SCD 是否按事件时点还是报告桶起点；历史重算与更正何时生效；源无 snapshot 时怎样界定可重复性；草案/扩展在客户具体工具版本中能否保真。它们需要客户样例、数据库与业务 owner 的证据，继续增加产品名单不能代替回答。

## 10. 一手来源与缓存索引

GitHub 链接均固定提交。官方在线文档随时会变，以缓存的抓取时点为准。源码仅静态阅读，未执行其中的命令或测试；这里只检查本文链接、缓存一致性与证据覆盖。全部成功/失败抓取和 SHA-256 见 [semantics-source-manifest.json](sources/semantics-source-manifest.json)；版本 pin 和增量说明见 [semantics-version-pins.json](sources/semantics-version-pins.json)。缓存均以 `sources/semantics-` 命名。

| ID | 一手来源/关键路径 | 本轮用途 |
| --- | --- | --- |
| M1 | [MetricFlow README 与许可历史](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/README.md) | 定位、历史许可、dbt 依赖 |
| M2 | [metricflow/engine/metricflow_engine.py](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/metricflow/engine/metricflow_engine.py#L522) | query/explain/计划/执行 |
| M3 | [semantic_model_join_evaluator.py](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/metricflow_semantics/model/semantics/semantic_model_join_evaluator.py#L44) | entity join 表、validity、MAX_JOIN_HOPS |
| M4 | [entity protocol](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/metricflow_semantic_interfaces/protocols/entity.py#L11)；[旧接口弃用声明](https://github.com/dbt-labs/dbt-semantic-interfaces/blob/c2ba16a0c3367d68f5e14d3da1403858b66b6724/README.md) | 单 expr 与接口迁移 |
| M5 | [LICENSE](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/LICENSE)；[pyproject.toml](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/pyproject.toml#L10) | 当前 Apache-2.0 |
| M6 | [dataflow_plan_builder.py](https://github.com/dbt-labs/metricflow/blob/fe4b8c1ccb72a8ca77494b345777eff20a714119/metricflow/dataflow/builder/dataflow_plan_builder.py#L810) | 已聚合输出组合 |
| D1–D4 | [semantic-models](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/build/semantic-models.md)；[entities](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/build/entities.md)；[dimensions/SCD](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/build/dimensions.md#L570)；[metrics-overview](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/build/metrics-overview.md) | 版本化 YAML、维度/时间/指标 |
| D5–D6 | [join-logic](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/build/join-logic.md)；[metricflow-commands](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/build/metricflow-commands.md) | fanout、多事实、校验边界 |
| D7–D10 | [architecture](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/use-dbt-semantic-layer/sl-architecture.md)；[部署](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/use-dbt-semantic-layer/deploy-sl.md)；[API](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/docs/docs/dbt-apis/sl-api-overview.md)；[部署 snippet](https://github.com/dbt-labs/docs.getdbt.com/blob/dea062642c4969d0a3709ee66580fa21e5acc524/website/snippets/_sl-run-prod-job.md) | OSS/商业、manifest 部署 |
| C1–C3 | [Cube README](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/README.md)；[JoinGraph.ts](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/packages/cubejs-schema-compiler/src/compiler/JoinGraph.ts#L98)；[BaseQuery.ts](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/packages/cubejs-schema-compiler/src/adapter/BaseQuery.ts#L2734) | 关系、倍增、独立聚合 |
| C4–C5 | [模型文档](https://docs.cube.dev/reference/data-modeling/cube)；[join 文档](https://docs.cube.dev/reference/data-modeling/joins)；[根 LICENSE](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/LICENSE)；[schema-compiler LICENSE](https://github.com/cube-js/cube/blob/d1241a63d6802792b01dd5131eb2b43eb23a3b3d/packages/cubejs-schema-compiler/LICENSE) | 声明模型、按路径许可 |
| W1–W2 | [MDL 类型](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren-core-base/manifest-macro/src/lib.rs#L147)；[manifest/PrimaryKey/layout](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren-core-base/src/mdl/manifest.rs#L98) | 物理映射、关系、键与布局 |
| W3–W5 | [memory/store.py](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/memory/store.py#L313)；[README](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/README.md)；[LICENSE](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/LICENSE) | hash、人工历史、当前架构、路径许可 |
| O1–O4 | [Core spec](https://github.com/apache/ossie/blob/2fd19c7a40b360bb87c18e8e0b7db482684b220a/core-spec/spec.md)；[ontology](https://github.com/apache/ossie/blob/2fd19c7a40b360bb87c18e8e0b7db482684b220a/ontology/ontology.md)；[expression language](https://github.com/apache/ossie/blob/2fd19c7a40b360bb87c18e8e0b7db482684b220a/core-spec/expression_language.md)；[ROADMAP](https://github.com/apache/ossie/blob/2fd19c7a40b360bb87c18e8e0b7db482684b220a/ROADMAP.md) | 草案、交换、概念/逻辑边界与缺口 |
| O5–O7 | [converters README](https://github.com/apache/ossie-converters/blob/46c673d18dd23e6c424798d952d7fd97496fd0cf/README.md)；[dbt README](https://github.com/apache/ossie-converters/blob/46c673d18dd23e6c424798d952d7fd97496fd0cf/dbt/README.md)；[msi_to_ossie.py](https://github.com/apache/ossie-converters/blob/46c673d18dd23e6c424798d952d7fd97496fd0cf/dbt/src/ossie_dbt/msi_to_ossie.py#L165)；[ossie_to_msi.py](https://github.com/apache/ossie-converters/blob/46c673d18dd23e6c424798d952d7fd97496fd0cf/dbt/src/ossie_dbt/ossie_to_msi.py#L185)；[converter_issues.py](https://github.com/apache/ossie-converters/blob/46c673d18dd23e6c424798d952d7fd97496fd0cf/dbt/src/ossie_dbt/converter_issues.py) | 按方向列明损失与拒绝 |
| O8 | [spec LICENSE](https://github.com/apache/ossie/blob/2fd19c7a40b360bb87c18e8e0b7db482684b220a/LICENSE)；[converters LICENSE](https://github.com/apache/ossie-converters/blob/46c673d18dd23e6c424798d952d7fd97496fd0cf/LICENSE)；[dbt pyproject](https://github.com/apache/ossie-converters/blob/46c673d18dd23e6c424798d952d7fd97496fd0cf/dbt/pyproject.toml) | Apache-2.0、dev 包版本 |
| O9–O11 | [ASF 孵化状态](https://incubator.apache.org/projects/ossie.html)；[改名公告](https://ossie.apache.org/updates/ossie-enters-apache-incubator/)；[rc tag 固定 spec](https://github.com/apache/ossie/blob/faf581054dcf7964d5fe0ceae7d6f415c8ce32a5/core-spec/spec.md)；[本地 refs](sources/semantics-ossie-remote-refs.txt) | Apache 归属、日期、正式发行证据边界 |
| H1–H3 | [DataHub SchemaMetadata](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/schema/SchemaMetadata.pdl)；[GlossaryTermInfo](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/glossary/GlossaryTermInfo.pdl)；[VersionProperties](https://github.com/datahub-project/datahub/blob/47be57949cf2b85c291228d5c1ce689a2b0ee795/metadata-models/src/main/pegasus/com/linkedin/common/VersionProperties.pdl) | 导入候选与 provenance/version |
| H4–H5 | [OpenMetadata table](https://github.com/open-metadata/OpenMetadata/blob/eeee22d6f74cd926d71dec61fa232b690ff7c692/openmetadata-spec/src/main/resources/json/schema/entity/data/table.json)；[glossaryTerm](https://github.com/open-metadata/OpenMetadata/blob/eeee22d6f74cd926d71dec61fa232b690ff7c692/openmetadata-spec/src/main/resources/json/schema/entity/data/glossaryTerm.json) | 约束、使用信息、reviewers/status |
| P1–P3 | [Palantir ontology](https://www.palantir.com/docs/foundry/ontology/overview/)；[object types](https://www.palantir.com/docs/foundry/object-link-types/object-types-overview/)；[link types](https://www.palantir.com/docs/foundry/object-link-types/link-types-overview/) | 官方对象模型边界，未实测 |
| R1 | [Post AI Data Stack](https://www.iandmacomber.com/blog/post-ai-data-stack) | 主报告研究者已读；Markdown/SQL context 与结果一致性校验案例；未独立复核量化效果 |
| X1 / L1 | [Jamie Quint](https://x.com/jamiequint/status/2029705203457609785)；[LinkedIn Data Context Layer](https://www.linkedin.com/blog/engineering/infrastructure/inside-linkedins-data-context-layer-curating-trustworthy-context-for-humans-and-agents) | 主报告研究者已读的动态上下文案例；本文不独立采信量化结论 |
