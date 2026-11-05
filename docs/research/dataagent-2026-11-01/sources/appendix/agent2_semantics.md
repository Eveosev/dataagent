# 语义层 / Ontology / 指标：技术现状、接口契约与建设成本

**研究基准日：2026-11-01（Asia/Shanghai）**
**范围：** 为《DataAgent 模块化能力拆分调研报告》提供“语义层/ontology/指标”模块的证据与接口建议。狭义 DataAgent 假设语义库已给定；广义 General DataAgent 必须构造、验证、发布、维护可复用语义，并处理冲突与变化。本文论证：语义层是最高杠杆模块，也是最容易被低估建设成本的模块。

**证据标记：**
- **[事实·官方]** 官方规范/产品文档/官方仓库中的可复核描述。
- **[事实·源码]** 固定提交或官方仓库源码中的字段、命令、行为。
- **[推断]** 由事实归纳的判断，不冒充厂商承诺。
- **[建议]** 面向 DataAgent 的接口/架构建议，不是任一产品的现有能力。
- **[未核实]** 本轮未取得可复核一手材料，或仅有二手线索。

**证据边界（重要）：** 本轮可直接联网抓取 dbt、Cube、Snowflake 官方页面（2026-11-01）；OSI/Ossie、Palantir、Wren、OpenMetadata、DataHub 等以本仓库 2026-10-31 的官方页面/固定提交缓存为主，未逐页重抓。所有链接均为官方公开地址；标注“缓存”的页面正文来自 `docs/research/dataagent-landscape-2026-10-31/sources/`。未对任何产品做安装、压测或端到端正确性评测；本文的“成本”是建设逻辑推演，不是项目实测工时。

---

## 0. 五条可直接引用的结论

1. **语义层不是“一张 YAML”，而是“可执行的业务契约 + 发布治理 + 回归证据”。** 2025–2026 的 dbt、Cube、Snowflake Semantic Views、Wren 都能把指标编译成 SQL；但没有一个产品替企业决定“哪个口径正确、对哪段时间生效、谁批准、何时失效”。这部分必须自建。[事实·官方][推断]
2. **OSI/Apache Ossie 是交换标准，不是运行时。** 它已进入 ASF 孵化（2026-06-22），2026-07-10 更名；当前核心规范 `0.2.0.dev0` 明示草案、schema 可变、勿用于生产。它标准化的重点是“模型可互换”，不是查询 API、指标引擎、审批或语义等价。[事实·官方]
3. **指标语义 CI 已有可用的“窄版本”，但没有跨厂商的“完整版本”。** dbt 用 `dbt sl validate --select state:modified+` 在 CI 中对语义节点做仓库 EXPLAIN 验证；Snowflake Cortex Analyst 用 verified queries 做准确率/回归/延迟评测。二者验证的是“能生成可执行 SQL / 能答对既有题”，不等于“业务口径正确”。[事实·官方][推断]
4. **Verified Query Repository（VQR）是语义资产，不是聊天记录。** 必须绑定 semantic release、源 schema/as-of、权限范围、验证人、有效期和失效条件；否则一次口径变更后，历史“已验证”查询会变成高置信度的错误答案。[事实·官方][建议]
5. **建设策略应是“复用语义引擎，自建语义控制面”。** 复用 MetricFlow/Cube/MDL/Snowflake 的编译与聚合能力；自建 draft→validate→compile→explain→publish→deprecate→diff 的生命周期、冲突裁决、VQR 失效与漂移回归。控制面才是 DataAgent 的差异化，也是最容易被低估的成本。[建议]

---

## 1. 2025–2026 时间线与格局

| 时间 | 事件 | 对 DataAgent 的含义 |
|---|---|---|
| 2025-11 | Open Semantic Interchange（OSI）仓库开放；17 个 launch partners | 厂商开始承认“语义碎片化”是 AI 问数的根因之一 |
| 2025-12-11 | Ossie 版本史记录 `0.1.1` 首发（本轮未核验 ASF 正式发行物） | 规范有历史版本，但不应据此称“稳定标准” |
| 2026-03-24 | Denodo 加入 OSI | 生态仍在扩张，数据虚拟化/目录厂商进入 |
| 2026-06-04 | FSI Semantic Working Group 首次正式会议 | 行业工作组开始按垂直领域细化语义 |
| 2026-06-22 | OSI 进入 Apache Incubator | 治理中立化；但仍是孵化项目 |
| 2026-07-10 | 更名 Apache Ossie（incubating） | “OSI”成为历史名称；规范/YAML 格式不变 |
| 2026-10 | Ossie `0.2.0.dev0` 草案；>50 组织；Metric Language/Catalog/Ontology 三个 WG | 覆盖“语义层 + ontology”的交换，但查询/引擎/治理仍缺 |
| 2026 | dbt 1.12/1.13 beta：`osi_document.json` 产物；measures 弃用、simple metric 统一 | dbt 成为 Ossie 最明确的“生产侧导出者” |
| 2026 | Cube 商业产品转向 agentic analytics；Chat API、`ai_context`、语义视图/视图组 | 语义层直接服务 Agent，而不只是 BI |
| 2026 | Snowflake 推荐 Semantic Views 替代 legacy YAML；VQ 评测、ASOF/range join、derived metric | 仓库内语义对象 + 内置评测，形成“语义 CI”的参照 |
| 2026 | Wren 定位 “open-source GenBI for AI agents”；MDL + knowledge + memory | “语义即配置/上下文即资产”的工程化样板 |

**判断：** 市场已经从“有没有语义层”进入“语义层能否被 Agent 消费、能否治理、能否回归”的阶段。语义层的竞争点从“建模 GUI”转向“可编译、可解释、可发布、可验证”。[推断]

---

## 2. OSI / Apache Ossie：标准化了什么，没标准化什么

### 2.1 状态与治理

- **[事实·官方]** 官方名称 **Apache Ossie (incubating)**，原名 Open Semantic Interchange（OSI）。ASF 孵化状态页记录 **2026-06-22** 进入孵化；项目公告 **2026-07-10** 更名，理由是避免 OSI 缩写与其他开源项目冲突。[ASF 状态页](https://incubator.apache.org/projects/ossie.html)、[更名公告](https://ossie.apache.org/updates/ossie-enters-apache-incubator/)
- **[事实·官方]** 公告称：仓库 2025-11 开放；100+ commits、35 merged PR；贡献者来自 Snowflake、Dremio、Salesforce、Databricks、dbt Labs、RelationalAI、GoodData、Honeydew；联盟从 17 个 launch partners 增至 50+ 组织；三个 WG：Metric Language、Catalog、Ontology。[同上]
- **[事实·源码]** 当前核心规范首页写 **DRAFT**，版本 `0.2.0.dev0`；版本史明确“Unreleased，schema 可变，不要在生产依赖”。[core spec](https://github.com/apache/ossie/blob/main/core-spec/spec.md)
- **[事实·官方]** 生态更新中出现 Denodo、Kyvos 等；官方称实现包括 Ossie↔dbt Semantic Layer converters。[Ossie 官网](https://ossie.apache.org/)、[converters](https://github.com/apache/ossie-converters)

**结论：** 可以称“Apache 孵化中的开放规范”，不能称“Apache 稳定标准 0.2”，也不能把“50+ 组织”当成“50+ 产品已无损支持”。[推断]

### 2.2 覆盖范围

| 层 | Ossie 是否覆盖 | 证据/边界 |
|---|---|---|
| 语义模型 | 是 | `semantic_model` + `datasets` + `fields` + `relationships` + `metrics` |
| 指标表达式 | 部分 | metric 是 SQL 表达式（`expression.dialects`），没有统一聚合枚举、grain、可加性、单位/币种 |
| 关系 | 部分 | 外键式 `from_columns/to_columns`，支持复合键；不是任意时间区间/多对多归因模型 |
| Ontology | 有独立规范 | EntityType/ValueType、extends、identify_by、requires、derived_by、multiplicity、mapping documents |
| 查询 API/引擎 | 否 | roadmap 才列“Semantic Query Language & Reference Engine” |
| 版本/发布/权限 | 否 | roadmap 列 catalog/registry、versioning、access control |
| 跨模型 bundle | 否 | 一份文档一个 model；不定义 bundle 或跨 model 引用 |
| 字段→字段、指标→指标 | 否 | 当前明确不支持 |
| Grain 一等公民 | 否 | roadmap 的 Metric Semantics WG 正在讨论 |

- **[事实·源码]** Core spec 明确：“This version does not support: a field expression that refers to another field; a metric expression that refers to another metric; a dataset that uses another dataset as its source.” [core spec](https://github.com/apache/ossie/blob/main/core-spec/spec.md)
- **[事实·官方]** Roadmap 的 Metric Semantics 目标直言：当前模型“lacks sufficient support for metrics at different grains, filters, aggregation semantics, and relationships between metrics”；歧义限制互操作。它还列了 first-class grain、relationship cardinality、semantic filters、metric trees 等未完成项。[ROADMAP](https://github.com/apache/ossie/blob/main/ROADMAP.md)

**判断：** Ossie 的强项是“结构可交换 + 概念/物理映射分离 + 扩展点”；弱项恰好是 DataAgent 最需要的“指标语义、grain、时间、发布治理”。把它当运行时或“语义正确性标准”会失望。[推断]

### 2.3 与 dbt / Cube / AtScale / LookML / Microsoft 的关系

| 体系 | 与 Ossie 的可复核关系 | 不能据此推出 |
|---|---|---|
| **dbt Semantic Layer** | 最紧密。dbt 是 Ossie 贡献者；dbt 1.12+ 在 `dbt parse` 时生成 `osi_document.json`；官方 converters 提供 MSI↔Ossie，但报告 natural entity、漏斗、private metric、累计窗口等损失，Ossie→MSI 拒绝成组复合键并默认 DAY 粒度 | “任意 dbt 模型无损互通” |
| **Cube** | Cube 文档提供 `lkml2cube`（LookML→Cube）、`cube_dbt` 包、语义视图/视图组；本轮未在 Ossie 官方页面看到 Cube 转换器或“Ossie-native”声明 | “Cube 已支持 Ossie 导入导出” |
| **AtScale** | 本轮 AtScale 官网/文档返回 403/503，未取得可复核页面；Ossie 官方缓存页也未列 AtScale 实现 | “AtScale 支持/不支持 Ossie”均不能断言 |
| **LookML（Looker）** | Looker 以 LookML 为 semantic model/source of truth；Conversational Analytics 明确从 LookML 取 schema、按 LookML 的 join/filter/aggregation/permission 组查询。Cube 提供 LookML→Cube 迁移工具，但本轮未见 Looker 官方 Ossie 导出 | “LookML 可无损导出到 Ossie” |
| **Microsoft 语义模型** | Power BI semantic model 是 Tabular/DAX 模型；Fabric data agent 通过 NL2DAX 查询语义模型，支持 RLS/CLS。Ossie 官方页面未列 Microsoft 实现 | “Power BI 模型可直接被 Ossie 消费” |

**判断：** 截至 2026-11，Ossie 的“事实上的互操作”主要集中在 **dbt ↔ Ossie**；Cube/LookML/Microsoft 各自有强模型，但公开证据不足以称“标准互操作”。企业若要用 Ossie，应把它当 **导出/交换格式 + 一致性测试**，而不是唯一运行时。[推断]

---

## 3. dbt Semantic Layer + MetricFlow

### 3.1 规范对象与关键字段

dbt 当前文档同时存在 1.9–1.11 的 standalone `semantic_models`/`measures` 形状，以及 1.12+ 的 model 内 column-level entity/dimension/simple metric 形状；两者不能混用。[事实·官方]

| 对象 | 关键字段 | 备注 |
|---|---|---|
| Semantic model | `name`、`description`、`model: ref(...)`、`defaults.agg_time_dimension`、`entities`、`dimensions`、`measures`（旧）/`columns`（新）、`primary_entity`、`config.meta/group/enabled` | 1.12 起 entity/dimension 可挂在 model 的 column 下 |
| Entity | `name`、`type`（primary/unique/foreign/natural）、`expr`、`description`、`config.meta` | 类型决定 join 合法性；`expr` 是单字符串，复合键需 surrogate expression |
| Dimension | `name`、`type`（categorical/time）、`type_params.time_granularity`、`expr`、`is_partition`、`description`、`config.meta` | time 维度默认 `metric_time`；粒度只能由细到粗 |
| Measure（旧） | `name`、`agg`、`expr`、`agg_params`、`agg_time_dimension`、`non_additive_dimension`、`create_metric` | measures 已弃用，官方建议迁移为 `type: simple` metric |
| Metric | `name`、`description`、`type`（simple/ratio/derived/cumulative/conversion）、`type_params`、`filter`、`time_granularity`、`label`、`config.meta/group/tags/enabled` | 类型化指标是 dbt 相对 Ossie 的强项 |
| Saved query | `name`、`description`、`label`、`config.cache/export_as/group/meta/tags`、`limit`、`order_by`、`query_params.metrics/group_by/where`、`exports[]` | 查询时只能改 where/limit/order/compile，metrics/group_by 固定 |

- **[事实·官方]** 指标类型：simple、ratio、derived、cumulative、conversion；cumulative 支持 `window`、`grain_to_date`、`period_agg`；ratio 有 `numerator/denominator`；conversion 有 `entity/calculation/base_metric/conversion_metric/window/constant_properties`。[metrics](https://docs.getdbt.com/docs/build/metrics)
- **[事实·官方]** Saved queries 是 DAG 节点，可配置 exports（table/view）并由 job scheduler 写入仓库；多个 metrics 时只能 group by 它们共享的维度。[saved queries](https://docs.getdbt.com/docs/build/saved-queries)
- **[事实·官方]** 1.12+ `dbt parse` 生成 `semantic_manifest.json` 和 `osi_document.json`；部署 job 解析 manifest，Semantic Layer API 读取最近一次部署 manifest。[deploy](https://docs.getdbt.com/docs/use-dbt-semantic-layer/deploy-sl)

### 3.2 编译 / 查询 / 校验接口

| 能力 | 接口 | 输入 → 输出 | 边界 |
|---|---|---|---|
| 列出指标/维度 | `dbt sl list metrics/dimensions/entities/dimension-values` | 选择器 → 元数据 | 依赖最近部署 manifest |
| 查询 | `dbt sl query --metrics ... --group-by ... --where ... --order-by ... --limit ...` | 指标+维度+过滤+时间 → 结果/SQL | `--compile`/`--explain` 显示 SQL/计划；`--show-dataflow-plan` 显示 dataflow |
| Saved query | `dbt sl query --saved-query <name>` | 名称 → 固定查询结果 | 不能覆盖 metrics/group_by |
| 校验 | `dbt sl validate` / `mf validate-configs` | 配置+仓库 → 错误/警告 | `--skip-dw` 可跳过仓库验证；“通过”需说明跑了哪些检查 |
| CI | `dbt sl validate --select state:modified+` | 变更语义节点+下游 → EXPLAIN 验证 | 官方 CI 文档明确会执行 explain query；支持 deferral |
| API | GraphQL / JDBC / Python SDK | 下游工具 → 指标查询 | 托管 API 属付费计划；自建 MetricFlow 不等于获得托管 SLA |

- **[事实·官方]** dbt CI 文档：把 `dbt sl validate --select state:modified+` 加到 CI job，自动测试 metrics/semantic models/saved queries；对修改模型下游的语义节点执行 explain query；未修改的下游 defer 到生产模型。[CI jobs](https://docs.getdbt.com/docs/deploy/ci-jobs)
- **[事实·源码]** `MetricFlowEngine.query → _create_execution_plan → query parser/dataflow → execution plan → SequentialPlanExecutor`；`explain` 暴露计划/SQL。它是“指标语义编译与执行接口”，不是业务审批系统。[metricflow engine 缓存]
- **[事实·源码]** Join evaluator 允许 FOREIGN→PRIMARY/UNIQUE 和部分 NATURAL，拒绝 FOREIGN→FOREIGN、PRIMARY→FOREIGN、NATURAL→NATURAL；右侧 NATURAL 必须有 validity dimensions；`MAX_JOIN_HOPS = 2`。这说明“类型化 join”能防一部分 fanout，但不能证明数据真的符合声明。

### 3.3 版本与 CI 方式

- **Git 是事实上的版本库**：semantic models、metrics、saved queries 都是项目文件；PR + CI + merge + `dbt parse` + deploy job 是官方推荐链路。
- **manifest 是发布产物**：`semantic_manifest.json` 固定一次解析结果；`osi_document.json` 供交换。它不是“业务生效时间”的版本。
- **没有内置审批/生效区间**：dbt 不提供“某指标 11-01 生效、10 月报表按旧定义重算”的双时间契约；需要外部控制面。[推断]
- **CI 的盲区**：`validate` 能发现引用不存在、类型不匹配、join 不合法、EXPLAIN 失败；不能发现主键实际重复、SCD 重叠、币种混算、口径业务错误。[推断]

**判断：** dbt 是“指标密集 + 已有 dbt 工程”场景下最值得复用的编译/CI 基座；但它的治理边界清楚，不能把 `dbt sl validate` 当“口径正确”证明。[建议]

---

## 4. Cube：语义层 API、预聚合、多租户、Agent

### 4.1 定位与模型

- **[事实·官方]** Cube Core 是开源语义层：在代码中定义 metrics/dimensions/joins/access rules，通过 SQL、REST、GraphQL API 暴露给 BI、应用或 AI agents；内置关系型缓存引擎。[Cube README](https://github.com/cube-js/cube)
- **[事实·官方]** Cube 商业产品是构建在 Core 上的 agentic analytics platform：Analytics Chat、workbooks/dashboards、embedded analytics、managed deployment、RBAC、multi-tenancy、Tableau/Power BI/Excel/Sheets 集成；模型双向兼容。[同上]
- **[事实·官方]** 模型对象：cube 可含 `measures`、`dimensions`、`joins`、`pre_aggregations`、`access_policy`、`hierarchies`、`segments`、`refresh_key`、`public`、`extends`、`data_source`、`calendar`；另有 views、view groups、`sql_table`/`sql`。[Cube 模型文档](https://docs.cube.dev/reference/data-modeling/cube)

### 4.2 API 与编译

| 接口 | 用途 | 备注 |
|---|---|---|
| REST (JSON) API | 查询 cubes/views，返回 JSON | 支持 security context、CORS、API scopes |
| GraphQL API | 下游工具查询 | 适合 BI/应用集成 |
| SQL API | 用 SQL 查询语义层 | 与 REST/GraphQL 共享模型与权限 |
| Chat API | 与 Cube AI agents 实时对话/流式分析 | Premium/Enterprise；按 agent 或 deployment 寻址；JWT/security context 可带 tenant_id、userAttributes |
| Orchestration API | Airflow/Dagster/Prefect 调度 | 预聚合构建/刷新 |

- **[事实·官方]** Chat API 是“与 Cube AI agents 的实时流式对话”，支持 API key 或 Cube token；`sessionSettings.externalId/email/userAttributes`；token 的 security context 可含 `tenant_id`；API key 方式必须带 `agentId`。[Chat API](https://docs.cube.dev/reference/embed-apis/chat-api)
- **[事实·官方]** 模型 `meta.ai_context` 可向 AI agent 提供不出现在 UI 的上下文。[Cube 模型文档](https://docs.cube.dev/reference/data-modeling/cube)

### 4.3 预聚合

- **[事实·官方]** `pre_aggregations` 是物化汇总，至少要有 `name` 和 `type`；类型包括 `rollup`、`original_sql`、`rollup_join`、`rollup_lambda`；参数包括 measures/dimensions/time_dimension/granularity/segments/partition_granularity/refresh_key/scheduled_refresh/indexes 等；必须包含要查询的维度和度量。[pre-aggregations](https://docs.cube.dev/reference/data-modeling/pre-aggregations)
- **[事实·官方]** `refresh_key` 可用 `every`（至少一次，不保证至多一次）或 SQL（如 `MAX(updated_at)`）判断是否失效；预聚合表名参与 rollup 查询的 refresh key。
- **[推断]** 预聚合把“语义正确性”与“缓存正确性”绑定：口径变更后若没有版本化 preagg/缓存失效，Agent 会拿到旧口径的“快答案”。DataAgent 必须把 semantic release 编进 cache key。

### 4.4 多租户

- **[事实·官方]** `access_policy` 支持 `group/groups/conditions/member_level/member_masking/row_level`；row_level 可按 security context 过滤（如 `state = {userAttributes.state}`）。[access policies](https://docs.cube.dev/reference/data-modeling/data-access-policies)
- **[事实·官方]** `COMPILE_CONTEXT` 按 `context_to_app_id` 的 key 只编译一次；不同 tenant 可用不同 schema/table（如 `user_{{ COMPILE_CONTEXT.securityContext.deployment_id }}.users`）。[context variables](https://docs.cube.dev/reference/data-modeling/context-variables)
- **[推断]** Cube 的多租户能力依赖“security context 必须被正确签名/传递 + 每个 tenant 的 preagg/cache 隔离”。如果 API 层把 tenant_id 当普通参数而非签名上下文，仍可能越权。

### 4.5 与 OSI / Agent 的关系

- Cube 文档目录含 `cube_dbt`（dbt 模型导入）和 `lkml2cube`（LookML→Cube），说明它走“吸收既有模型”的路线，而不是等 Ossie。
- Cube 的 Agent 能力（Chat API、ai_context）是“语义层直接服务 Agent”的典型：Agent 不生成裸 SQL，而是通过语义层 API 查询。对 DataAgent 的启示是 **compile/explain 接口要原生面向 Agent**，而不是只面向 BI。[推断]

---

## 5. Wren AI 的 MDL：“语义即配置”

### 5.1 MDL 对象

- **[事实·源码]** Manifest：`layout_version`、`catalog`、`schema`、`models`、`relationships`、`views`、`data_source`、`cubes`。
- **[事实·源码]** Model：`name`、`ref_sql`/`base_object`/`table_reference`（三选一，非法组合会报错）、`columns`、`primary_key`（单列或复合）、`cached`、`refresh_time`、`row_level_access_controls`、`dialect`。
- **[事实·源码]** Column：`name`、`type`、`relationship`、`is_calculated`、`not_null`、`expression`、`is_hidden`、`column_level_access_control`。**计算字段就是 `expression` + `is_calculated`**。
- **[事实·源码]** Relationship：`name`、`models[]`、`join_type`（ONE_TO_ONE/ONE_TO_MANY/MANY_TO_ONE/MANY_TO_MANY）、`condition`。
- **[事实·源码]** View：`name`、`statement`、`dialect`；Cube：`name`、`base_object`、`measures`、`dimensions`、`time_dimensions`、`hierarchies`；另有 RLS/CLS。
- **[事实·源码]** `MAX_SUPPORTED_LAYOUT_VERSION = 4`；超过版本会拒绝，属于序列化布局兼容，不是业务发布版本。[Wren manifest](https://github.com/Canner/WrenAI)

### 5.2 语义重写与“配置即资产”

- **[事实·官方]** Wren 的 AGENTS.md 模板明确规定 Agent 工作流：
  1. `wren memory fetch -q "<question>"` 取相关 schema context；
  2. `wren memory recall -q "<question>" --limit 3` 找相似历史查询；
  3. 用 MDL 的 model 名写 SQL（不是裸表名）；
  4. `wren --sql "<sql>"` 通过语义层执行；
  5. `wren memory store --nl "<question>" --sql "<sql>"` 存 confirmed 结果。
- **[事实·官方]** 修改模型：编辑 `models/`、`views/`、`relationships.yml` → `wren context validate` → `wren context build`（生成 `target/mdl.json`）→ `wren memory index`。
- **[事实·官方]** 规则（canonical tables、default filters、units、enum meanings）放 `knowledge/rules/*.md`，由 `wren context instructions` 读取；confirmed NL→SQL 示例写 `knowledge/sql/`；两者都随项目提交。
- **[事实·官方]** `wren dry-plan --sql "..."` 预览 planned SQL；`wren memory status` 查看索引。
- **[事实·源码]** MemoryStore 的 schema items 带 `mdl_hash`；`get_context` 用 manifest hash 过滤，schema 更新会替换 seed、保留 user-confirmed；`store_query/recall_queries` 支持语义检索与来源标签。[Wren memory 缓存]

**判断：** Wren 的“MDL + knowledge + memory”是目前最接近“语义即配置”的开源样板：语义、业务规则、已验证查询三类资产都在 Git，且 Agent 通过 CLI/MCP 读写。但它的正确性仍依赖人确认与目标引擎，不自动解决口径冲突。[建议]

---

## 6. 指标平台与指标治理：能力矩阵与现实差距

### 6.1 指标定义应包含什么

| 维度 | 必填内容 | 为什么 |
|---|---|---|
| 身份 | 稳定 metric ID、名称、同义词、所属域、owner | 同名异义/异名同义是首要冲突源 |
| 公式 | 表达式 AST（不是字符串）、聚合、分子/分母、distinct 键 | 字符串公式无法做类型检查/差分/优化 |
| Grain | 输入事实的 grain、输出 grain、可加性 | 决定 join 后是否重复计算 |
| 时间 | 事件/下单/支付/入账时间、时区、财务日历、窗口、as-of | “上季度”在跨时区/财年下不唯一 |
| 过滤 | 默认过滤（退款、测试单、内部单）、状态机、币种 | 口径差异常来自“默认排除什么” |
| 单位/币种 | 单位、精度、币种、汇率来源/时点/类型 | 混币种求和是最常见的“看起来对”的错误 |
| 适用维度 | 允许 group by 的维度、层级、不可切分维度 | 防止把半可加指标随便切 |
| 治理 | 状态、版本、生效区间、reviewer、批准时间、替代/废弃 | 支持追溯与回滚 |
| 证据 | 验证查询、期望结果、回归集、数据 as-of | 没有证据的“已验证”不可复用 |

### 6.2 产品能力矩阵（只写可复核项）

| 能力 | dbt SL | Cube | Snowflake Semantic Views | LookML | Power BI / Fabric | Wren |
|---|---|---|---|---|---|---|
| 指标类型系统 | simple/ratio/derived/cumulative/conversion | measure 类型 + SQL/filter/rolling | 表级/视图级 metric、derived、non-additive | measure + table calc | DAX measure | cube measure |
| 时间粒度 | `metric_time`、time spine、SCD validity | time dimension + granularity | time_dimensions、ASOF/range join | dimension_group | DAX time intelligence | time_dimension |
| 可加性 | `non_additive_dimension` | 部分（measure 类型/时间窗） | `non_additive_dimensions` | 需手工 | 需 DAX | 需手工 |
| 多币种 | 需外部 | 需外部 | 需外部 | 需外部 | 需外部 | 需外部 |
| 语义 CI | `dbt sl validate` + CI explain | schema 编译/测试 | VQ evaluation（accuracy/regression/latency） | LookML Validator + Content Validator | 无同等“指标语义 CI”证据 | `context validate` + memory |
| 审批/生效区间 | 无内置（Git/PR） | 无内置（Git） | 无内置（DB 对象 + 权限） | 无内置（Git） | 无内置（Git/deployment pipeline） | 无内置（Git） |
| VQR | saved queries（无结果验证） | 无独立 VQR | `verified_queries` + 评测 | 无独立 VQR | Copilot verified answers（app-scoped） | memory confirmed queries |
| 多租户 | 依赖仓库/API | access_policy + security context | RBAC + 行访问策略 | access grants + user attributes | RLS/CLS | RLS/CLS |

- **[事实·官方]** Snowflake 明确“Semantic Views 是推荐方式”，legacy stage YAML 仅向后兼容；支持 derived metrics、public/private access modifier、RBAC/sharing/catalog 集成。[Snow semantic views](https://docs.snowflake.com/en/user-guide/views-semantic/overview)
- **[事实·官方]** Snowflake VQR 字段：`name`、`question`、`verified_at`、`verified_by`、`use_as_onboarding_question`、`sql`；SQL 必须用语义模型里的 logical table/column 名，不能用底层物理列名。[VQR](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository)
- **[事实·官方]** Cortex Analyst evaluations 用 VQ 做 ground truth；评测时会把选中的 VQ 从临时 semantic view 移除，防止“答案泄漏”；指标包括 accuracy、regressions（之前对现在错）、latency、per-query 结果；可用 `EXECUTE_AI_EVALUATION` SQL API 启动/查询/取消。[evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations)
- **[事实·官方]** Looker Conversational Analytics 把 LookML 当 source of truth：取 Explore schema（name/label/description/type/dimension_group），按 LookML 的 join/filter/aggregation/permission 组查询，hidden 字段忽略；支持 agent instructions 与 allowed_value/fuzzy search。[Looker CA](https://docs.cloud.google.com/looker/docs/conversational-analytics-overview)
- **[事实·官方]** Power BI Copilot 使用 semantic model；app-scoped Copilot 支持作者准备的 verified answers；模型作者需补 measure 描述/业务上下文；相同 prompt + 未变模型 24h 内走缓存。[Copilot](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-introduction)
- **[事实·官方]** Fabric data agent 支持 warehouse/lakehouse/Power BI semantic model/KQL/mirrored DB/ontology；每个数据源最多 100 条 example queries；支持 instructions、Git integration、deployment pipelines；Power BI 语义模型走 NL2DAX，RLS/CLS 仍生效；example queries 目前不支持 Power BI semantic model 数据源。[Fabric data agent](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent)

### 6.3 有没有成熟的“指标语义 CI”？

**分层回答：**

1. **编译级 CI：成熟。** dbt `dbt sl validate --select state:modified+` 在 CI 里对变更语义节点及下游执行仓库 EXPLAIN；Cube 有 schema 编译/测试；LookML 有 Validator；Wren 有 `context validate`。[事实·官方]
2. **问答级 CI：开始成熟。** Snowflake Cortex Analyst 用 VQ 做 accuracy/regression/latency 评测，并防止 VQ 泄漏；这是目前最完整的“语义视图 CI”产品化证据。[事实·官方]
3. **口径级 CI：不成熟。** 没有产品能自动判断“净收入是否该扣退款/税费/汇率”“活跃客户的定义是否符合财务口径”。这需要 owner 签字 + 对账 + 业务回归集。[推断]
4. **跨厂商 CI：不存在。** Ossie 没有 reference engine/query API；各产品的“验证”不可互换。[推断]

**建议的“指标语义 CI”最小门禁：**
- 结构：schema/ref/type/PK 唯一/FK coverage；
- 编译：目标 dialect 的 EXPLAIN；
- 语义：grain/fanout/SCD/时区/币种/可加性检查；
- 行为：golden set 的 SQL 结果差分（容差 + 维度分解）；
- 治理：owner 批准、生效区间、VQ 失效、下游影响；
- 证据：每次 run 绑定 semantic release + schema hash + data as-of。

---

## 7. Ontology 路线：Palantir、Ossie、OpenMetadata 与“实体图”

### 7.1 Palantir Ontology

- **[事实·官方]** Object type 是现实实体/事件的 schema；object 是实例；object set 是实例集合。Link type 是两个 object type 之间关系的 schema；link 是关系实例；多对多 link 由独立 datasource 支撑。[object types](https://www.palantir.com/docs/foundry/object-link-types/object-types-overview/)、[link types](https://www.palantir.com/docs/foundry/object-link-types/link-types-overview/)
- **[事实·官方]** Ontology 同时包含 semantic elements（objects/properties/links）与 kinetic elements（actions/functions/dynamic security）；action types 捕获操作者输入、编排决策，functions 编写业务逻辑；interfaces 提供 object type 多态。[Ontology overview](https://www.palantir.com/docs/foundry/ontology/overview/)
- **[事实·官方]** 官方文档目录含 branching the ontology、review ontology proposals、ontology branches、change management、review/restore changes、export/import。[Palantir docs 导航缓存]
- **[推断]** Palantir 的强项是“对象 + 关系 + 动作 + 权限”的运营闭环；它的指标聚合/fanout/SCD 语义不是本轮验证重点，不能据此认定可替代 MetricFlow/Cube。

### 7.2 Ossie ontology 与 OpenMetadata/DataHub

- **[事实·源码]** Ossie Ontology 定义 EntityType/ValueType、extends、identify_by、requires、derived_by、relationship roles/multiplicity、IRI、mapping documents（concept/object/link mappings）；`ontology_mappings` 已 deprecated，推荐独立 mapping document。[ontology spec](https://github.com/apache/ossie/blob/main/ontology/ontology.md)
- **[事实·源码]** 这些是“声明”，不证明有 OWL 推理器、实体匹配服务、约束执行器、动作系统或数据质量监控。[推断]
- **[事实·源码]** OpenMetadata glossaryTerm 有 `reviewers`、`entityStatus`（approval status）、`version`、`synonyms`、`relatedTerms`、`owners`；table schema 有 column/constraint/joins/profile。[OpenMetadata glossary schema](https://github.com/open-metadata/OpenMetadata)、[table schema](https://github.com/open-metadata/OpenMetadata)
- **[事实·源码]** DataHub `SchemaMetadata` 有 `schemaHash`、fields、primaryKeys、foreignKeys；`GlossaryTermInfo` 有 definition/sourceRef/sourceUrl；`VersionProperties` 有 versionSet/tag/alias/时间/comment。[DataHub schema](https://github.com/datahub-project/datahub)

**判断：** OpenMetadata/DataHub 是“元数据图 + 术语治理”，不是可执行语义层；Ossie ontology 是“概念交换”，不是推理/动作平台；Palantir 是“运营 ontology”。三者与 MetricFlow/Cube 不是替代关系。[推断]

### 7.3 知识图谱式 vs 关系式语义

| 维度 | 知识图谱/ontology | 关系式语义层 |
|---|---|---|
| 世界观 | 开放世界，概念/关系/约束可推理 | 封闭世界，表/列/键/聚合可编译 |
| 强项 | 实体消歧、跨系统 identity、关系路径、约束、动作、上下文 | 指标公式、grain、join 合法性、聚合、fanout、SQL 编译 |
| 弱项 | 聚合/可加性/查询优化不是原生 | 实体身份、跨域概念、动作/工作流不是原生 |
| 典型风险 | “关系很多但算不对数” | “数算对了但不知道对象是谁/能否操作” |
| DataAgent 分工 | 回答“是谁、有什么关系、能做什么、受什么约束” | 回答“怎么算、按什么 grain、能否切、结果多少” |

**“语义层 + 实体图”的分工建议：**
- **实体图（Entity Graph）**：实体类型/实例、identity/merge、关系与路径、约束、动作、权限、业务上下文；为 Agent 提供“对象级上下文”和 join 闭包。
- **指标语义层（Metric Layer）**：指标/维度/measure、grain、时间、可加性、币种、合法 join、编译/explain；为 Agent 提供“可执行计算”。
- **连接件**：实体图提供 entity key / join path / policy；指标层把 entity 映射为 semantic entity，并在 compile 时校验 cardinality；VQR 同时绑定两者。
- **不要合并**：用 ontology 直接算指标会重复造 fanout/聚合；用指标层做实体消歧会把它变成另一个 catalog。[建议]

---

## 8. Verified Query Repository（VQR）作为语义资产

### 8.1 存储什么

一条可复用的 VQ 至少应存：

| 字段 | 说明 |
|---|---|
| `vq_id` / `name` | 稳定 ID，不复用 |
| `question` / `normalized_intent` | 原始问法 + 规范化意图（指标/维度/过滤/时间） |
| `semantic_release` | 绑定哪个语义版本；不是“当前最新” |
| `sql` / `plan` | 以逻辑表/列名书写；保留 compiled SQL 与 plan hash |
| `dialect` / `engine_version` | 执行方言与引擎版本 |
| `source_schema_hash` / `data_as_of` | 物理 schema 与数据快照 |
| `parameters` / `result_schema` | 参数化槽位、结果列类型 |
| `expected_result` / `result_hash` / `tolerance` | 金标准结果或可接受范围 |
| `verified_by` / `verified_at` / `status` | 谁、何时、什么状态 |
| `effective_from/to` / `expires_at` | 业务有效期与失效时间 |
| `scope` / `tenant` / `policy` | 数据范围、租户、权限 |
| `evidence` | 执行日志、对账、review 记录 |
| `supersedes` / `superseded_by` | 版本链 |

- **[事实·官方]** Snowflake VQR 的官方字段就是 `name/question/verified_at/verified_by/use_as_onboarding_question/sql`；它要求 SQL 用语义模型的逻辑表/列名，不用底层列名。这说明“VQ 是语义层资产”，不是任意历史 SQL。[VQR](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository)
- **[事实·官方]** dbt saved query 是 DAG 节点，含 metrics/group_by/where/order_by/limit/exports；查询时 metrics/group_by 固定，只能覆盖 where/limit/order。[saved queries](https://docs.getdbt.com/docs/build/saved-queries)
- **[事实·官方]** Wren 把 confirmed NL→SQL 存 `knowledge/sql/`，并用 `memory recall` 检索；seed 与 user-confirmed 分开，schema 更新保留 confirmed。[Wren AGENTS.md / memory 缓存]

### 8.2 检索与复用

**建议的混合检索：**
1. 结构化过滤：tenant、权限、semantic release、方言、引擎、有效期、状态；
2. 精确匹配：normalized intent / metric set / dimension set / filter set；
3. 语义相似：question embedding + SQL/plan embedding；
4. 图约束：实体/指标/关系必须存在于当前 release；
5. 重排：验证时间、使用成功率、结果稳定性、owner 信任度、成本。

**复用规则：**
- 命中后先做 **compatibility check**：release、schema hash、方言、权限、参数；
- 通过则复用 plan/SQL；不通过则走 compile，不允许“静默回退到旧 SQL”；
- 复用结果必须带 `semantic_release` + `data_as_of` + `vq_id`；
- 同一问题有多个 VQ 时，按“更具体/更新/更高信任”排序，冲突时要求确认。

### 8.3 失效

**触发失效的条件：**
- semantic release 变更（指标公式/过滤/grain/时间/币种/join）；
- 物理 schema 变更（列删除/改名/类型/分区/键唯一性）；
- 源数据语义变更（状态机、枚举、退款政策、汇率源）；
- 权限/租户策略变更；
- 引擎/方言版本变更；
- 结果漂移超过容差；
- VQ 超过 `expires_at`。

**失效策略：**
- `soft invalidate`：标记 stale，检索降权，仍可查看但不可直接执行；
- `hard invalidate`：禁止执行，要求重新验证；
- 级联：依赖该 VQ 的缓存、示例、评测集、Agent few-shot 一并失效；
- 审计：记录谁在何时因何失效，避免“悄悄复活”。

**反例：** 退款政策从“全额退”改为“扣手续费”，VQ 仍按旧规则过滤 `status='paid'`，Agent 复用它后给出高置信度但高估的收入。这不是 SQL 错误，是语义资产失效。[推断]

---

## 9. 语义漂移：检测与回归

### 9.1 漂移分类

| 类型 | 例子 | 检测信号 |
|---|---|---|
| 物理 schema | 列改名/删除、类型 decimal→string、分区键变化 | schema hash、information_schema、contract test、lineage |
| 键/基数 | 主键不再唯一、FK 出现孤儿、SCD 有效期重叠 | uniqueness/null/orphan/overlap profiling |
| 数据分布 | 枚举新增、币种新增、时区变化、迟到数据 | 枚举监控、 freshness、分布漂移 |
| 业务规则 | 退款/税费/折扣/状态机/财年 | owner 变更单、规则版本、对账 |
| 口径 | 公式/过滤/分母/grain/时间窗 | semantic diff、golden set 结果差分 |
| 权限 | 行/列策略收紧或放宽 | policy diff、访问审计 |
| 引擎 | 方言/版本/函数行为 | EXPLAIN、回归 SQL |

### 9.2 检测与回归流程

```
schema snapshot/hash
  → 结构 diff（列/类型/键/分区）
  → 影响分析（引用该列的 model/metric/dimension/VQ/dashboard）
  → 语义 diff（公式/过滤/grain/时间/币种）
  → 编译（目标 dialect）
  → 行为回归（golden set，旧 vs 新，容差 + 维度分解）
  → 业务对账（总额/分组/边界）
  → 批准/回滚
```

**关键设计：**
- **双版本并行**：旧 release 继续服务，新 release 影子运行；比较结果而不是只看 SQL。
- **按维度分解差异**：总额相同但地区结构不同，仍是口径变化。
- **时间边界用例**：月初/月末/年末/闰年/时区边界/财年边界。
- **空值/孤儿/重复用例**：join 丢失、fanout、SCD 重叠。
- **回滚开关**：release 不可变，回滚是切换指针，不是改文件。
- **失效传播**：schema/semantic 变更自动标记受影响 VQ/缓存/示例。

**工具现状：** dbt 有 `state:modified`、tests、contracts、EXPLAIN；Cube 有 preagg refresh/编译；Snow 有 VQ evaluation；OpenMetadata/DataHub 有 schema/lineage/version；但没有一个工具把“物理漂移 → 语义 diff → 行为回归 → 业务批准”端到端串起来。DataAgent 需要自建这条链。[推断]

---

## 10. 语义层模块的接口契约（建议）

### 10.1 公共信封

所有接口共享：

```json
{
  "request_id": "uuid",
  "tenant": "acme",
  "actor": {"type": "user|agent|ci", "id": "...", "scopes": ["..."]},
  "semantic_release": {"release_id": "...", "version": "2026.11.1", "manifest_hash": "sha256:..."},
  "idempotency_key": "uuid",
  "dry_run": false
}
```

**不变量：**
- release 不可变；任何发布产生新 `release_id`。
- 所有响应带 `release_id + manifest_hash + evidence_ref`。
- 所有写操作支持幂等键；冲突用乐观锁（`base_revision`）。
- 任何“成功”必须说明检查了什么；禁止静默 fallback。
- Agent 与人类共用同一契约，仅 `audience/detail_level` 不同。

### 10.2 七个操作

| 操作 | 目的 | 输入 | 输出 | 主要错误 | 副作用 |
|---|---|---|---|---|---|
| **draft** | 创建/修改草稿 | `base_revision?`、`object_patch/full_object`、`message`、`actor`、`tenant` | `draft_id`、`revision`、`normalized_object`、`unresolved_refs[]`、`warnings[]`、`diff_preview` | `CONFLICT_REVISION`、`INVALID_SCHEMA`、`UNKNOWN_REF`、`IMMUTABLE_FIELD`、`POLICY_DENIED` | 仅草稿存储；不影响运行时/索引 |
| **validate** | 验证草稿/发布候选 | `revision/release`、`checks[]`、`target{dialect,engine_version}`、`data_snapshot/as_of`、`timeout` | `validation_id`、`status`、`errors[]`、`warnings[]`、`checks[{category,status,evidence,sql,metrics}]`、`impact`、`cost_estimate`、`expires_at` | `CHECK_FAILED`、`TIMEOUT`、`INSUFFICIENT_PRIVILEGE`、`DATA_UNAVAILABLE`、`NONDETERMINISTIC` | 只读查询/临时产物；不发布 |
| **compile** | 编译为逻辑计划/物理 SQL | `release`、`query{metrics[],group_by[],filters[],time_range,grain,limit,parameters}`、`dialect`、`policy_context`、`optimize` | `plan_id`、`logical_plan`、`physical_sql`、`referenced_objects[]`、`required_grants[]`、`plan_hash`、`cost_estimate`、`warnings[]` | `UNKNOWN_METRIC`、`INVALID_GROUP_BY`、`NON_ADDITIVE_SLICE`、`FANOUT_RISK`、`UNSUPPORTED_DIALECT`、`POLICY_VIOLATION`、`AMBIGUOUS_PATH` | 无执行；同输入应确定性 |
| **explain** | 面向 Agent/人解释 | `plan_id` 或 `compile_request`、`audience`、`detail_level` | `summary`、`metric_expansion[]`、`join_path[]`、`grain`、`filters_applied[]`、`time_semantics`、`additivity`、`assumptions[]`、`alternatives[]`、`risks[]`、`confidence`、`evidence_refs[]` | `PLAN_NOT_FOUND`、`EXPLAIN_UNSUPPORTED` | 无 |
| **publish** | 发布不可变 release | `revision`、`validation_id`、`approvals[]`、`effective_from/to`、`rollout{scope,percentage}`、`release_notes`、`deprecates[]` | `release_id`、`version`、`manifest_hash`、`signature`、`status`、`deployed_targets[]`、`index_refresh`、`affected_assets[]`、`rollback_to` | `VALIDATION_EXPIRED`、`APPROVAL_MISSING`、`BREAKING_CHANGE`、`SCHEMA_DRIFT`、`CONFLICT_RELEASE`、`POLICY_DENIED` | 写 release、切运行时指针、刷新索引/缓存、通知；需幂等 |
| **deprecate** | 标记废弃 | `release/object`、`reason`、`replacement?`、`sunset_at`、`migration_scope`、`notify[]` | `deprecation_id`、`status`、`impact[]`、`redirects[]`、`grace_period`、`query_warnings[]`、`removal_at` | `HAS_ACTIVE_DEPENDENTS`、`NO_REPLACEMENT`、`INVALID_SUNSET` | 不硬删除；宽限期告警，到期拒绝 |
| **diff** | 两版本差异/影响 | `from`、`to`、`include{structural,semantic,impact,behavioral}`、`data_snapshot?`、`golden_set?` | `structural_diff[]`、`semantic_diff[]`、`impact{downstream[],breaking[]}`、`behavioral{queries[],result_deltas[],tolerance}`、`migration_hints[]`、`classification` | `INCOMPARABLE_VERSIONS`、`MISSING_BASELINE` | 只读 |

### 10.3 validate 的检查目录（建议最小集）

| 类别 | 检查 | 失败示例 |
|---|---|---|
| 结构 | 引用存在、字段类型兼容、必填项、命名唯一 | metric 引用了已删除的 dimension |
| 键 | PK 唯一非空、复合键组合唯一、FK coverage、tenant scope | 订单表 `order_id` 实际重复 |
| Grain | 声明 grain 与行数/唯一键一致、指标输入 grain 匹配 | 订单表实际是订单行 |
| Join | cardinality 声明与数据分布一致、路径唯一、fanout 风险 | 声明 N:1 实际 1:N |
| 时间 | SCD 有效期不重叠、时区、日历、窗口边界 | SCD 两行同时有效 |
| 可加性 | 半可加/不可加维度、distinct 键 | 库存余额按月求和 |
| 单位/币种 | 单位一致、汇率来源/时点、精度 | USD 与 CNY 直接相加 |
| 策略 | RLS/CLS/tenant 过滤注入 | 查询缺 tenant_id |
| 编译 | 目标 dialect EXPLAIN | 函数不存在/类型错误 |
| 行为 | golden set 结果在容差内 | 净收入少了退款 |

### 10.4 diff 的分类

- **structural**：对象增删、字段增删/改名/类型。
- **semantic**：公式、过滤、grain、时间角色、币种、可加性、join cardinality。
- **impact**：下游 metric/dimension/VQ/dashboard/agent/缓存。
- **behavioral**：同一 golden set 的 SQL 结果差异（绝对值/相对值/分组结构）。
- **breaking**：删除/改名/收紧权限/改变 grain/改变默认过滤 → 必须 major version + 迁移指南。
- **non-breaking**：新增可选维度/描述/同义词 → minor/patch。

---

## 11. 最小可用语义模型清单

### P0：没有就不应上线（可回答“一个可信指标”）

1. **Dataset/Source**：稳定 ID、物理映射、grain（一行是什么）、PK/唯一键、tenant scope、freshness、owner。
2. **Entity**：业务实体、identity 字段、复合键、同义词、跨系统映射（至少一个权威源）。
3. **Dimension**：categorical/time、类型、表达式、层级（可选）、空值/未知语义、是否可切分。
4. **Metric**：公式 AST、聚合、可加性、默认过滤、分子/分母、单位/币种、时间锚点。
5. **Relationship**：左右实体、键/谓词、cardinality、方向、join type、fanout 策略、有效期。
6. **Business Time**：事件/下单/支付/入账时间、时区、财务日历、grain、as-of。
7. **Release/Version**：draft/proposed/validated/reviewed/published/deprecated、owner、effective_from/to。
8. **Query Contract**：metrics/group_by/filters/time/grain/limit → logical plan + SQL + explain。
9. **Validation Evidence**：结构/键/grain/join/时间/编译检查 + 至少一组 golden query。

### P1：规模化前补齐（多团队/多源/多租户）

10. SCD Type 2 / 有效期 join（客户、产品、组织架构）。
11. 多币种：交易币/报表币、汇率表、汇率时点/类型、 triangulation。
12. 层级/钻取、指标适用范围（哪些维度可切）。
13. VQR：verified queries + 失效 + 评测集。
14. 权限/租户：RLS/CLS、policy context、cache key 隔离。
15. 影响分析/lineage：metric → dashboard → agent → VQ。
16. 弃用/迁移：deprecate + replacement + 宽限期。
17. 漂移检测：schema hash、键/分布/枚举、golden set 回归。

### P2：进阶（按场景）

18. Ontology 对象/链接/动作（Palantir 式运营闭环）。
19. 跨域概念映射/本体推理（Ossie ontology/mapping）。
20. 自动候选发现（schema/query log/BI 导入）。
21. 成本优化/预聚合/物化视图选择。
22. What-if/模拟/分摊/单位换算。
23. 语义搜索/实体消歧/跨系统 identity resolution。
24. 多语言/多方言/多引擎适配。

**判定规则：** 如果指标是余额/库存/订阅数 → 半可加/SCD 是 P0；如果跨币种 → 多币种是 P0；如果客户属性会变 → SCD 是 P0；否则可放 P1。不要用“统一 P1”掩盖领域差异。[建议]

---

## 12. 建设成本与常见坑

### 12.1 成本结构（经验判断，非实测）

| 成本项 | 一次性 | 持续 | 易被低估的原因 |
|---|---|---|---|
| 建模 | 高 | 中 | 只算 YAML 时间，不算业务访谈/对账 |
| 验证 | 高 | 高 | 每个指标要 golden query、边界用例、数据快照 |
| 治理 | 中 | 高 | 审批、生效区间、冲突裁决、owner 维护 |
| 漂移/回归 | 中 | 高 | schema/业务规则/引擎持续变 |
| VQR | 中 | 中 | 验证一次容易，失效/重验难 |
| 组织 | 高 | 高 | 指标 owner 是政治问题，不是技术问题 |

**经验比例（[推断]，需用实际项目校准）：** 初始建设约 30–40% 建模、20–30% 验证、20–30% 治理/流程、10–20% 工具；上线后每年维护可能达到初始建设的 30–50%，指标越多、源越杂、变更越频繁，比例越高。**真正的成本不是“写 100 个指标”，而是“让 100 个指标在 20 个团队、3 个引擎、2 次组织调整后仍然一致”。**

### 12.2 七个具体失败例子

| 坑 | 具体失败例子 | 正确做法 |
|---|---|---|
| **可加性** | 库存表每天一行，期初 100 件；把 1–30 日的 `on_hand` 求和得 3000 件，对外说“月库存 3000”。实际月末仍是 100。 | 标记 semi-additive；按月取最后一天/期末快照；聚合函数按时间维度特殊处理。 |
| **时态/SCD** | 客户 7 月从“华东”迁到“华南”。订单表 join 当前客户维表（无有效期），1–6 月订单全被算成华南，区域同比失真。 | SCD2 + `order_time between valid_from and valid_to`；校验有效期不重叠；明确“按事件时点还是报告桶起点”。 |
| **多币种** | 把 USD 订单和 CNY 订单的 `amount` 直接 `SUM`，或把去年收入按今天的汇率折算。 | 交易币/报表币分离；汇率表含 date/type（收盘/平均）；按业务时点折算；校验量纲。 |
| **grain 冲突** | `orders` 一行一单，join `order_items` 后 `SUM(orders.amount)`；一单 5 行，收入被放大 5 倍。 | 在订单 grain 先聚合，或改用 `SUM(order_items.line_amount)`；声明 fact grain；编译器检测 fanout。 |
| **join fanout** | 一个客户属于两个行业标签，按行业统计收入时客户被计两次，各行业收入之和大于总收入。 | 明确多对多归因规则（主标签/权重/分摊）；桥表；不可加时禁止相加；Cube 式按 PK 去重再聚合只能解决“重复”，不能解决“分摊”。 |
| **口径冲突** | 市场部“活跃客户”= 30 天登录；财务“活跃客户”= 90 天有购买。两个看板都叫 `active_customers`，差距 18%，会上争论“系统错了”。 | 稳定 metric ID + 业务定义 + 同义词；同名不同义必须不同 ID；在语义层显式 owner/适用域；冲突检测按名称+公式+粒度。 |
| **语义与物理漂移** | dbt 模型把 `amount` 改名 `gross_amount`，语义模型仍引用 `amount`；开发环境缓存旧 manifest，生产查询才报错。或类型 decimal→string 后隐式转换，结果静默截断。 | schema hash + contract test + CI `state:modified` + 发布前 EXPLAIN；把 physical schema fingerprint 写入 release；变更自动失效 VQ/缓存。 |
| **时区/财年** | 订单 2026-03-31 23:30 UTC，按上海时区已是 4 月 1 日；按 UTC 算进 Q1，按本地算进 Q2。财务日历 4 月制，系统按自然季度。 | 明确时间角色/时区/日历；边界用例；在语义层固定，不让 Agent 临时猜。 |
| **租户/权限** | 预聚合缓存 key 只有 metric+day，没有 tenant_id；A 租户命中 B 租户缓存。 | cache key 含 tenant/security context；RLS/CLS 在编译期注入；跨租户负例测试。 |
| **VQ 过期** | 退款政策变更后，旧 VQ 仍复用；SQL 能跑、结果“看起来合理”，但高估收入。 | VQ 绑定 release + 失效条件 + 过期时间；复用前 compatibility check；冲突时要求确认。 |

### 12.3 为什么最容易被低估

1. **把“语义”当“文档”**：写 YAML 只是开始，真正成本在业务对账和边界用例。
2. **把“编译成功”当“口径正确”**：EXPLAIN 只证明 SQL 能跑。
3. **把“一次验证”当“永久有效”**：schema/业务/引擎都在变。
4. **把“一个指标”当“一个对象”**：实际是 metric + dimensions + joins + filters + tests + owner + VQ + deprecation。
5. **把“LLM 能猜”当“不用建模”**：语义层减少歧义，但不替企业做决策；Agent 越强，错误口径的破坏越大。
6. **忽略组织成本**：指标 owner、冲突裁决、跨部门对账，往往比技术更难。

---

## 13. 自建 vs 复用：判断与理由

| 能力 | 建议 | 理由 | 若自建的最小边界 |
|---|---|---|---|
| 语义**交换**格式 | **复用 Ossie**（导出/导入 + conformance），不把它当运行时 | 标准草案、无引擎；但结构/ontology 设计值得跟随 | 只实现导出 + 损失报告，不实现完整规范 |
| 指标编译/聚合 | **复用 MetricFlow / Cube / Snowflake / Wren** | 类型化 join、fanout、时间、SQL 编译是多年工程；自研易错 | 只做 adapter + 语义校验，不重写编译器 |
| 预聚合/缓存/API | **复用 Cube**（嵌入式/多租户/API 场景） | Core 开源、SQL/REST/GraphQL、preagg、access policy 成熟 | 不重复造 cache/查询网关 |
| Agent 语义重写/上下文 | **复用 Wren MDL + memory 模式** | MDL/知识/示例都在 Git；CLI/MCP 对 Agent 友好 | 复用其“配置 + 记忆”思想，治理层自建 |
| 目录/术语/血缘 | **复用 OpenMetadata / DataHub** | 稳定资产 ID、glossary、lineage、版本；自研成本高 | 只做语义层对象与目录对象的映射 |
| 运营 ontology | **仅在已有 Palantir 时复用** | 对象/关系/动作/权限闭环强，但锁定重 | 不复制其平台；用轻量实体图 |
| **语义控制面** | **自建** | 没有产品覆盖 draft→publish→deprecate、冲突裁决、生效区间、VQ 失效、漂移回归 | 这是差异化，必须自建 |
| **VQR** | **自建**（可借用 Snow VQ/评测模型） | 产品 VQR 多为“示例库”，缺少失效/权限/版本绑定 | 存储 + 检索 + 失效 + 评测 |
| **漂移/回归** | **自建** | 跨 schema/语义/行为/业务的链路无现成产品 | 先做 golden set + 结果差分 |
| **冲突检测/裁决** | **自建** | 同名异义/同义异名/粒度冲突是组织问题 | 规则 + 人工裁决 + 影响分析 |
| **权限/租户** | **复用引擎能力 + 自建策略映射** | Cube/Snow/Wren 有 RLS/CLS，但租户语义在应用层 | 统一 policy context + 负例测试 |

**一句话：** 复用“语义引擎”，自建“语义控制面”；复用“标准格式”，自建“发布与证据”。[建议]

---

## 14. 对 DataAgent 模块拆分的直接建议

1. **把“语义层”拆成两个子模块**：
   - **Semantic Runtime**：compile/explain/query，尽量复用引擎；
   - **Semantic Control Plane**：draft/validate/publish/deprecate/diff、VQR、漂移、冲突。
2. **接口先定 contract，再选引擎**：七个操作的输入/输出/错误码先稳定，引擎可替换（MetricFlow/Cube/Wren/Snow）。
3. **每个回答绑定证据**：`semantic_release + plan_hash + data_as_of + policy_decision + validation_id`；没有证据的答案标“未认证”。
4. **认证指标与探索 SQL 双轨**：认证指标走语义计划；未建模问题走受控 NL2SQL，产出候选语义，经复核再进入认证层。
5. **VQR 与评测集同源**：VQ 既是 few-shot/复用资产，也是回归题；评测时防泄漏（Snow 的做法）。
6. **先做 20–50 个高风险问题**：覆盖同名异义、SCD、多币种、fanout、跨租户、时区/财年、退款/税费；不要用公开 NL2SQL benchmark 代替企业验收。
7. **把“语义变更”当发布事件**：有版本、有 diff、有影响分析、有回滚、有生效区间；不是改一个 YAML 文件。

---

## 15. 来源与访问日期

**访问日期：2026-11-01（Asia/Shanghai）。** 标注“缓存”的页面正文来自本仓库 2026-10-31 的官方页面/固定提交缓存；标注“直抓”的页面为本轮直接抓取。未标注的官方 URL 为规范地址，未作为唯一事实依据。

### 15.1 OSI / Apache Ossie

| # | 来源 | 用途 | 访问 |
|---|---|---|---|
| O1 | [Apache Ossie 官网](https://ossie.apache.org/) | 定位、覆盖范围、最新动态 | 缓存 |
| O2 | [更名公告 2026-07-10](https://ossie.apache.org/updates/ossie-enters-apache-incubator/) | 更名、贡献者、17→50+、三个 WG | 缓存 |
| O3 | [ASF 孵化状态页](https://incubator.apache.org/projects/ossie.html) | 2026-06-22 进入孵化 | 缓存 |
| O4 | [Core spec](https://github.com/apache/ossie/blob/main/core-spec/spec.md) | DRAFT、0.2.0.dev0、字段、限制 | 缓存 |
| O5 | [Ontology spec](https://github.com/apache/ossie/blob/main/ontology/ontology.md) | EntityType/ValueType、mapping | 缓存 |
| O6 | [ROADMAP](https://github.com/apache/ossie/blob/main/ROADMAP.md) | 指标/grain/query engine 缺口 | 缓存 |
| O7 | [Ossie converters](https://github.com/apache/ossie-converters) | dbt 转换及损失 | 缓存 |
| O8 | [dbt 1.12 osi_document.json](https://docs.getdbt.com/docs/use-dbt-semantic-layer/deploy-sl) | 生产侧导出 | 直抓 |

### 15.2 dbt

| # | 来源 | 用途 | 访问 |
|---|---|---|---|
| D1 | [Semantic models](https://docs.getdbt.com/docs/build/semantic-models) | 模型字段 | 缓存 |
| D2 | [Entities](https://docs.getdbt.com/docs/build/entities) | primary/unique/foreign/natural | 缓存 |
| D3 | [Dimensions](https://docs.getdbt.com/docs/build/dimensions) | 时间粒度、is_partition、SCD | 缓存 |
| D4 | [Metrics](https://docs.getdbt.com/docs/build/metrics) | 五种类型、filter、time_granularity | 缓存 |
| D5 | [Saved queries](https://docs.getdbt.com/docs/build/saved-queries) | name/query_params/exports | 直抓 |
| D6 | [MetricFlow commands](https://docs.getdbt.com/docs/build/metricflow-commands) | list/query/validate/explain | 缓存 |
| D7 | [Deploy metrics](https://docs.getdbt.com/docs/use-dbt-semantic-layer/deploy-sl) | parse/manifest/osi_document | 直抓 |
| D8 | [CI jobs](https://docs.getdbt.com/docs/deploy/ci-jobs) | `dbt sl validate --select state:modified+` | 直抓 |
| D9 | [Semantic Layer APIs](https://docs.getdbt.com/docs/dbt-apis/sl-api-overview) | GraphQL/JDBC/Python | 缓存 |

### 15.3 Cube

| # | 来源 | 用途 | 访问 |
|---|---|---|---|
| C1 | [Cube README](https://github.com/cube-js/cube) | Core vs 商业、SQL/REST/GraphQL、agentic | 缓存 |
| C2 | [Cube 模型](https://docs.cube.dev/reference/data-modeling/cube) | cube 字段、ai_context | 缓存/直抓 |
| C3 | [Joins](https://docs.cube.dev/reference/data-modeling/joins) | 关系、chasm/fan trap、去重 | 缓存 |
| C4 | [Pre-aggregations](https://docs.cube.dev/reference/data-modeling/pre-aggregations) | rollup/original_sql/rollup_join/refresh_key | 直抓 |
| C5 | [Access policies](https://docs.cube.dev/reference/data-modeling/data-access-policies) | row/member level、security context | 直抓 |
| C6 | [Context variables](https://docs.cube.dev/reference/data-modeling/context-variables) | COMPILE_CONTEXT、多租户 | 直抓 |
| C7 | [REST API](https://docs.cube.dev/reference/core-data-apis/rest-api) | API scopes/security context | 直抓 |
| C8 | [Chat API](https://docs.cube.dev/reference/embed-apis/chat-api) | AI agents、tenant_id、session | 直抓 |

### 15.4 Wren

| # | 来源 | 用途 | 访问 |
|---|---|---|---|
| W1 | [WrenAI](https://github.com/Canner/WrenAI) | GenBI for AI agents、MDL/上下文 | 缓存 |
| W2 | `core/wren-core-base/src/mdl/manifest.rs` / macro | Model/Column/Relationship/Cube 字段 | 缓存 |
| W3 | Wren context/AGENTS.md | memory fetch/recall/store、context validate/build、dry-plan | 缓存 |
| W4 | Wren memory store | mdl_hash、seed/confirmed、检索 | 缓存 |

### 15.5 Snowflake / Looker / Microsoft

| # | 来源 | 用途 | 访问 |
|---|---|---|---|
| S1 | [Semantic Views overview](https://docs.snowflake.com/en/user-guide/views-semantic/overview) | 推荐方式、RBAC、derived/access modifier | 直抓 |
| S2 | [Semantic View YAML](https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec) | 表/维/事实/指标/关系/VQ/变量 | 缓存 |
| S3 | [Verified Query Repository](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository) | VQ 字段/逻辑列名 | 直抓 |
| S4 | [Cortex Analyst evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations) | accuracy/regression/latency、VQ 防泄漏 | 缓存 |
| L1 | [Looker Conversational Analytics](https://docs.cloud.google.com/looker/docs/conversational-analytics-overview) | LookML 作为 source of truth | 缓存 |
| M1 | [Power BI Copilot](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-introduction) | 语义模型/verified answers/缓存 | 缓存 |
| M2 | [Fabric data agent](https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent) | 语义模型/ontology/example queries/Git | 缓存 |

### 15.6 Ontology / 目录

| # | 来源 | 用途 | 访问 |
|---|---|---|---|
| P1 | [Palantir Ontology overview](https://www.palantir.com/docs/foundry/ontology/overview/) | semantic + kinetic | 缓存 |
| P2 | [Object types](https://www.palantir.com/docs/foundry/object-link-types/object-types-overview/) | schema/instance/set | 缓存 |
| P3 | [Link types](https://www.palantir.com/docs/foundry/object-link-types/link-types-overview/) | link、M:N datasource | 缓存 |
| OM1 | [OpenMetadata glossaryTerm schema](https://github.com/open-metadata/OpenMetadata) | reviewers/status/version | 缓存 |
| DH1 | [DataHub SchemaMetadata](https://github.com/datahub-project/datahub) | schemaHash/PK/FK/version | 缓存 |

### 15.7 未核实/待补

- **AtScale**：官网/文档返回 403/503，未取得可引用页面；其 OSI 支持、指标类型、CI 能力均标 **[未核实]**。
- **Microsoft Fabric Ontology**：本轮未取得独立官方页面；仅从 Fabric data agent 文档确认“ontology 可作为数据源”，不展开其对象模型。
- **Cube D3**：文档站子域为 `cubed3`，Chat API/`ai_context` 可复核；但“D3”作为独立产品名的定位/架构未取得官方单页，本文只把它归入 Cube 的 Agent 能力，不单列事实。[未核实]
- **Ossie 正式发行物**：版本史记录 0.1.1，但本轮未核验 ASF 投票/下载制品；不称“已正式发布稳定版”。

---

## 16. 附：最小 validate 请求/响应示例（建议）

```json
POST /semantic/v1/validate
{
  "request_id": "req-1",
  "tenant": "acme",
  "semantic_release": {"release_id": "draft-42", "version": "2026.11.0-draft"},
  "target": {"dialect": "snowflake", "engine_version": "2026.10"},
  "data_snapshot": {"as_of": "2026-10-31T23:59:59+08:00", "schema_hash": "sha256:..."},
  "checks": ["schema", "keys", "grain", "join", "time", "additivity", "currency", "compile", "golden"],
  "timeout_seconds": 300
}
```

```json
{
  "validation_id": "val-9001",
  "status": "failed",
  "errors": [
    {"code": "FANOUT_RISK", "path": "metrics.net_revenue.joins.order_items", "message": "declared N:1 but 1:N in sample", "evidence": "..."}
  ],
  "warnings": [
    {"code": "CURRENCY_MISMATCH", "path": "metrics.net_revenue", "message": "USD and CNY in same measure"}
  ],
  "checks": [
    {"category": "keys", "status": "passed", "evidence": "order_id unique 99.98%, 12 nulls excluded"},
    {"category": "golden", "status": "failed", "evidence": "3/10 queries differ > 0.5%"}
  ],
  "impact": {"metrics": ["net_revenue"], "vqs": ["vq-17"], "dashboards": ["finance-monthly"]},
  "cost_estimate": {"scanned_bytes": 123456789, "warehouse_seconds": 42},
  "expires_at": "2026-11-02T00:00:00+08:00"
}
```

---

**最终判断：** 语义层是 DataAgent 的最高杠杆模块，因为它同时决定“答案对不对、能不能解释、能不能复用、能不能治理”。它也是最容易被低估的模块，因为可见成本是 YAML，真实成本是业务对账、边界用例、发布治理、VQR 失效和持续漂移回归。2025–2026 的引擎已经足够好；真正稀缺的是 **语义控制面** 和 **可复核的证据链**。
