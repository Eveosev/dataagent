# E — 语义层/Ontology 标准与数据接入协议（MCP）生态调研

> 调研日期：2026-10-30　方法：web_search 不可用，全部通过 web_fetch 直取一手规范/文档；无法直取的条目标注「未核实」。
> 结论面向 DataAgent 的 ontology 载体、版本化与"接千行百业的库"三件事。

---

## 1. 执行摘要

1. **语义层标准已经收敛到 Ossie，不该再自造对外格式。** Open Semantic Interchange（OSI）在 2025-12-11 发布 0.1.1，2026-06-22 进入 Apache 孵化并更名 **Apache Ossie**（Apache-2.0），2026-05-29 的 0.2.0.dev0 新增了 **ontology 规范 + mapping 文档**。站台组织 50+，含 Snowflake、Databricks、dbt Labs、Cube、AtScale、Salesforce、Oracle、DataHub、Collibra、Alation、Atlan、Informatica。更关键的是 **dbt v1.12 已原生解析 Ossie 文档**（`osi/` 目录），转换器矩阵已覆盖 Snowflake Cortex、dbt、Salesforce、Apache Polaris、GoodData、Power BI/Fabric TMSL。
2. **但 Ossie 仍是 0.x，且 0.2.0 有破坏性变更。** 文档形态从 `semantic_model` 数组改为扁平单模型；名字解析从"source 列"改为"dataset field"；dbt 目前只接受 `0.1.0`/`0.1.1`，其他版本字符串直接 parse error。**这决定了我们必须锁定 0.1.1 兼容子集作为落地形态。**
3. **Ossie 的 ontology 层被严重低估。** 它有 concept（EntityType/ValueType）、relationship（roles、multiplicity、verbalizes、identify_by、derived_by、requires）、可选 IRI + prefixes，以及独立的 mapping 文档（object_mappings / link_mappings，支持复合主键的 referent 嵌套）。这实质上是「RDF 的实用子集 + R2RML 的现代化版本」，且天然分成「本体 / 维度模型 / 映射」三份文件——正是 DataAgent 需要的分层。
4. **因此：ontology 不要用 RDF/OWL 直接承载，也不要自造 schema。** 用 Ossie ontology 表达概念与关系，用 `iri` 字段单向挂接外部本体（FOAF/Org/schema.org），用 Ossie mapping 把概念落到物理 dataset。只有需要外部知识图谱对齐时才引入三元组，且只作为导出视图。
5. **MCP 在 2026-07-28 变成无状态协议，架构假设必须更新。** 删除了 `initialize`/`initialized` 握手、删除了 `Mcp-Session-Id` 与协议级会话、`server/discover` 成为强制 RPC、版本与能力改为每请求 `_meta` 自描述、server→client 请求被 **MRTR（multi round-trip）** 取代、`roots`/`sampling`/`logging` 进入弃用、DCR 弃用转向 CIMD。**任何"登录后拿游标、会话内保持状态"的接入设计会直接过时**；游标必须是服务端铸造的普通工具参数。
6. **数据类 MCP server 已从"社区玩具"转为"厂商官方 + 框架化"。** Snowflake 社区版 server 已明确弃用并指向官方 Cortex MCP；Google 的 **MCP Toolbox for Databases**（Apache-2.0，v1.15.0）用一份 `tools.yaml` 覆盖 20+ 数据库并内置连接池、IAM、OpenTelemetry；`mcp-clickhouse` 已实现 2026-07-28，默认 `readonly=1`，写/破坏性操作双层闸门，30s 超时 + `KILL QUERY`，并用 `DESCRIBE`/`EXPLAIN ESTIMATE` 做执行前成本探测。
7. **接入层建议：MCP 作控制面，直连驱动作数据面。** LLM 只应看到语义操作（`query_metric`/`list_entities`/`describe_field`），绝不应拿到通用 `execute_sql`。结果集在服务端消费、只回传聚合后的结构化结果，否则大 schema + 大结果是必然的上下文爆炸。

---

## 2. 标准对比表

| 标准 | 主导方 | 成熟度（2026-10） | 表达力 | 工具链 | 许可 |
|---|---|---|---|---|---|
| **Apache Ossie**（原 OSI）core + ontology + mapping | ASF 孵化（PPMC），50+ 厂商 | 0.1.1 已发布；0.2.0.dev0 开发中（ontology 2026-05-29 加入） | 维度模型（dataset/field/metric/relationship）+ 概念本体 + 物理映射；多方言表达式；无推理 | JSON Schema + validate.py；7 个官方转换器仓；dbt v1.12 原生读 | Apache-2.0 |
| **dbt Semantic Layer / MetricFlow** | dbt Labs | v1.12 稳定，v1.13 beta；v2 在途 | 实体/维度/简单指标/指标类型，强于 join 图与时间粒度；无本体概念 | 自有 manifest、`semantic_manifest.json`、dbt MCP、SQL 生成 | 核心 Apache-2.0，平台商业 |
| **Cube** | Cube Dev | 成熟（多年生产） | cube/view/measure/dimension/join/pre-aggregation/access_policy，含预聚合与行级访问策略 | YAML 或 JS 建模、REST/SQL/GraphQL API、语义缓存 | 开源核心 + 商业云（许可细节未核实） |
| **LookML** | Google Cloud（Looker） | 成熟但封闭 | view/explore/dimension/measure/derived_table，表达力强、Looker 专属 | 仅 Looker；Git 版本化；无开放 schema | 专有 |
| **Databricks UC Metric Views** | Databricks | GA（Unity Catalog semantics） | source/field/measure/filter，星型与多级 join、窗口度量、参数、物化、agent metadata（同义词/格式） | SQL DDL + YAML、Catalog Explorer、Genie/BI 直查 | 平台内建，无独立规范 |
| **Snowflake Semantic Views** | Snowflake | GA，schema 级对象 | logical table/fact/metric/dimension/relationship，可 `SELECT` 直查，Cortex Analyst/Agents 消费 | SQL DDL、YAML 上传、Semantic Studio、INFORMATION_SCHEMA 反射 | 平台内建，无独立规范 |
| **Palantir Ontology / OSDK** | Palantir | 成熟（Foundry 核心） | object type/property/link type/action type/interface/function，含写回与动作；value type 有版本 | OSDK（TS/Python）、branching ontology + proposals、Ontology Manager | 专有 |
| **RDF / OWL / SHACL** | W3C | 标准稳定（Rec） | 最强：类/属性/公理/约束/推理；OWL 2 profile 可判定 | Jena、Oxigraph、rdflib；BI/Agent 侧弱 | W3C 开放 |
| **R2RML / OBDA** | W3C | 稳定但生态萎缩 | 关系表→三元组映射，成熟范式 | Ontop 等；新项目采用少 | W3C 开放 |
| **OpenLineage** | LF AI & Data | 规范 2-0-2（JSON Schema 2020-12） | RunEvent/DatasetEvent/JobEvent + facet 扩展点（`_producer`/`_schemaURL`） | Airflow/Spark/dbt 集成、Marquez 等 | Apache-2.0 |
| **OpenMetadata / DataHub** | 各自社区 | OpenMetadata v2.0.x；DataHub 成熟 | 实体化目录：table/column/lineage/glossary/term/domain/data product/tag | 各自 UI/API/事件流；两家均在 Ossie 阵营 | Apache-2.0 |
| **Iceberg REST Catalog / Hudi** | ASF | Iceberg 1.12（REST catalog 为事实标准） | 表格式与 catalog 协议，不表达业务语义 | Spark/Flink/Trino/各云 | Apache-2.0 |
| **ODCS（Open Data Contract Standard）** | Bitol | v3.1.0+ 分节拆分 | schema/quality/SLA/roles/servers/pricing/team | YAML + JSON Schema，多为 CI 校验 | 开放（CC/Apache 类，未逐条核实） |
| **MCP** | Anthropic 发起，Linux 基金会旗下治理演进中 | **2026-07-28 为 current**；2025-11-25 为上一版 | 工具/资源/提示 + 授权 + 任务扩展；不管语义 | 官方 registry（preview）、多语言 SDK、大量 server | 规范开放（MIT/Apache 类，未逐条核实） |
| **schema.org / Dublin Core** | 社区 / DCMI | 稳定 | 文档与网页级元数据；无指标/join 概念 | 搜索引擎、CMS | 开放 |

**读法：** Ossie 与 dbt/Cube/LookML/Databricks/Snowflake 同层竞争、经 Ossie 互通；RDF/OWL 更上层但生态错位；OpenLineage/OpenMetadata/Iceberg 属**邻层**（血缘、目录、存储），互补而非替代。

---

## 3. ontology 载体建议（含 schema 草案）

### 3.1 三层文件 + 一层扩展

| 层 | 文件 | 承载 | 格式 |
|---|---|---|---|
| L1 语义模型 | `model.yaml` | dataset/field/metric/relationship（可被 BI、dbt 消费） | Ossie **0.1.1** 兼容子集（`semantic_model` 数组形态） |
| L2 概念本体 | `concepts.yaml` | concept/relationship/roles/requires/iri | Ossie ontology 0.2.0.dev0 裁剪子集 |
| L3 物理映射 | `mapping.yaml` | 概念 ↔ dataset 字段的 object/link mapping | Ossie mapping 文档 |
| L4 AgentOS 扩展 | `model.yaml` 内 `custom_extensions` | 稳定 ID、样例值、术语表、权限策略、已验证查询、成本预算 | `vendor_name: AGENTOS` + JSON |

**为什么不放一个文件：** 三层变更频率差一个数量级（L1 随数仓、L2 随业务语言、L3 随建模习惯）。合并会让每次物理改动都触发本体版本跳变，diff 噪声淹没语义变更。

**为什么 L1 用 0.1.1 而不追 0.2.0：** 理由见 §1.2。折中方案是**按 0.2.0 语义思考、按 0.1.1 落盘**，用 `to_ossie_0_1_1()` 适配层隔离，等 dbt v2 支持后切换。

### 3.2 草案（节选，非法字段已省略）

```yaml
# ── L1: agentos/ontology/sales/model.yaml（Ossie 0.1.1，dbt 可直接读）
version: 0.1.1
semantic_model:
  - name: sales_domain
    description: 销售域语义模型（DataAgent 真源）
    ai_context:
      instructions: 金额单位为分；GMV 含税、不含退款。
    datasets:
      - name: orders
        source: dw.sales.orders          # 物理定位，必须能在 catalog 解析
        primary_key: [order_id]
        fields:
          - name: order_id
            expression: { sql: order_id }
            datatype: String
          - name: order_date
            expression: { sql: order_date }
            datatype: Date
            dimension: { is_time: true }
          - name: amount_cents
            expression: { sql: pay_amount }
            datatype: Decimal
            ai_context: { synonyms: [成交额, 支付金额] }
        metrics:
          - name: gmv
            expression: { sql: SUM(amount_cents) / 100.0 }
            datatype: Decimal
            ai_context: { synonyms: [GMV, 成交总额], examples: ["上个月华东区 GMV"] }
    relationships:
      - name: orders_to_customers
        from: orders
        to: customers
        from_columns: [customer_id]
        to_columns: [customer_id]
    metrics:
      - name: arpu
        expression: { sql: SUM(orders.amount_cents)/100.0 / COUNT(DISTINCT customers.customer_id) }
        datatype: Decimal
    custom_extensions:
      - vendor_name: AGENTOS
        data: |
          {"bundle":"sales@2.3.0","digest":"sha256:9f2c…",
           "stable_ids":{"orders":"01J8ZK3Q","orders.gmv":"01J8ZK4A"},
           "samples":{"orders.amount_cents":[1299,4999],"orders.status":["paid","refunded"]},
           "glossary":[{"term":"GMV","maps_to":"gmv","definition":"含税支付金额，扣退款前"}],
           "policy":{"read_only":true,
                     "row_filters":["region_id IN (SELECT region_id FROM auth.user_region WHERE uid = :uid)"],
                     "column_masks":{"customers.phone":"sha256","customers.id_card":"deny"},
                     "max_scan_bytes":2000000000,"timeout_ms":30000,"max_rows":5000},
           "verified_queries":[{"id":"vq_001","q":"近30天GMV","plan_ref":"plans/vq_001.sql"}]}
```

```yaml
# ── L2: concepts.yaml（Ossie ontology 子集：只保留 AgentOS 用得到的构造）
name: sales_ontology
prefixes: { foaf: "http://xmlns.com/foaf/0.1/", org: "http://www.w3.org/ns/org#" }
ontology:
  - concept: Customer
    type: EntityType
    iri: org:FormalOrganization          # 单向挂接外部本体，不做推理
    identify_by: [ customer_id ]
    relationships:
      - name: customer_id
        roles: [ { concept: CustomerId } ]
        multiplicity: OneToOne
        verbalizes: [ "{Customer} 的客户编号是 {CustomerId}" ]
      - name: places
        roles: [ { concept: Order } ]
        multiplicity: ManyToOne
        verbalizes: [ "{Customer} 下单 {Order}" ]
  - concept: CustomerId
    type: ValueType
    extends: [ String ]
    requires: [ "LENGTH(CustomerId) = 12" ]
```

```yaml
# ── L3: mapping.yaml（概念 ↔ 物理；等价于 R2RML 的现代写法）
version: 0.2.0.dev0
name: sales_mapping
ontology_ref: { name: sales_ontology, iri: ./concepts.yaml }
semantic_model_ref: { name: sales_domain, iri: ./model.yaml }
concept_mappings:
  - concept: Customer
    object_mappings:
      - referent_mappings:
          - relationship: Customer.customer_id
            expression: customers.customer_id
    link_mappings:
      - object_mapping: { concept: Order, expression: orders.order_id }
        relationship: Customer.places
```

### 3.3 版本化与 diff

- **三套版本各自独立 semver**：`spec`（Ossie 版本，`0.1.1`）、`model`（业务语义，`2.3.0`）、`mapping`（物理映射，`1.7.2`）。对外只暴露 `bundle = name@model_version`，内部保留三元组。
- **内容寻址**：对 canonical JSON（RFC 8785 JCS）算 `sha256`，作为 `digest` 写进 `custom_extensions`。用途不是替代 semver，而是**检测"语义未变但序列化变了"**——防止格式化、键序、注释导致的无意义 diff 触发下游重编译。
- **稳定标识必须独立于 name**。Ossie 路线图里 "Make stable identifiers explicit rather than reusing name"（discussion #31）仍是未决项，所以自己加 `stable_ids`（ULID）。没有它，重命名就等于删除+新建，血缘断链。
- **diff 双轨**：机器用 RFC 6902 JSON Patch（可回放、可审批）；人用**语义 diff**——按 `entity/field/metric/relationship` 分类，标出 breaking（删字段、改 datatype、改 metric 表达式、删 relationship）与 non-breaking（加同义词、加样例值、补 description）。
- **迁移**：`migrations/` 目录放声明式脚本 + `supersedes` 链；CI 里跑「旧模型 + 迁移 → 新模型」的等价性断言（对 TPC-DS 样例跑指标回归）。破坏性变更必须 bump major 并提供 dbt 侧同步的转换器。

---

## 4. 接入层建议

### 4.1 MCP 优先，但不唯一：控制面 / 数据面分离

| 场景 | 选型 | 理由 |
|---|---|---|
| 长尾数据库、第三方 SaaS、客户自带库 | **MCP**（远程 Streamable HTTP 优先） | 一个协议吃下异构；权限可委托给厂商 server；无需为每个库发版 |
| 一方高频库（PG/ClickHouse/Snowflake）、大结果集、低延迟 | **Native 驱动**（ADBC/JDBC/DB-API） | 省一跳网络与 LLM 往返；可控游标、批量、压缩、流式 |
| 需要事务/写入/回滚 | **Native**（MCP 2026-07-28 无会话，跨调用事务不成立） | 无状态协议下事务只能靠服务端句柄 |
| 元数据/血缘/目录 | **HTTP API**（OpenMetadata/DataHub/OpenLineage） | 这批不是 MCP 的强项，别硬套 |

**核心判断：** 让 LLM 决定"查什么语义"，不让它决定"发什么 SQL"。所以 MCP server 暴露的应是**语义化工具**（`query_metric`、`list_entities`、`describe_field`、`sample_values`），而不是通用 `execute_sql`。通用 SQL 工具一开，Text-to-SQL 的准确率、权限、成本三件事同时失控。

### 4.2 Connector 抽象

```ts
interface Connector {
  readonly id: string;
  readonly dialect: Dialect;                    // postgres | snowflake | bigquery | clickhouse | ...
  readonly caps: {
    rowLevelSecurity: boolean; columnMasking: boolean;
    streaming: boolean; cdc: boolean; explain: boolean;
    maxConcurrency: number;
  };
  listNamespaces(): AsyncIterable<Namespace>;
  listObjects(ns: Namespace, opt: { pageToken?: string; filter?: string }): Promise<Page<TableRef>>;
  describeTable(ref: TableRef): Promise<TableSchema>;
  plan(q: SemanticQuery): Promise<SqlPlan>;      // 方言感知，编译自 Ossie 模型
  explain(p: SqlPlan): Promise<CostEstimate>;    // 字节/行数预估，用于闸门
  execute(p: SqlPlan, o: ExecOpts): Promise<ResultStream>;  // o: timeoutMs/maxRows/budget
  health(): Promise<Health>;
}
```

两个实现：`McpConnector`（把上面的方法映射到远端 MCP 工具，做能力探测与降级）与 `NativeConnector`（池化连接 + 方言改写）。上层只依赖接口，`caps` 驱动降级——比如目标库没有 `explain` 就退化为"采样估算 + 强制 `LIMIT`"。

### 4.3 接"千行百业的库"的三档落地

- **A 档（官方 MCP / 托管）**：Snowflake Cortex MCP、dbt MCP（远程 HTTP，5000 rpm/IP）、Databricks 托管 MCP。零运维，优先。
- **B 档（自托管框架）**：MCP Toolbox for Databases，一份 `tools.yaml`（sources/tools/toolsets/prompts/resources）覆盖 PG/MySQL/SQL Server/Oracle/BigQuery/Spanner/Snowflake/ClickHouse/Trino/Mongo/Redis/Neo4j。自带连接池、IAM、OTel——**这是"长尾库一次接入"的最高性价比路径**。
- **C 档（自研 Native + 导入器）**：性能/成本敏感或协议受限场景。配套 Ossie 导入器，从 catalog API 生成 L1 骨架，再由人补 metric 与 ai_context。

### 4.4 现实问题清单（按痛感排序）

1. **方言差异**：不要写"通用 SQL"。Ossie 的多方言表达式（`OSSIE_SQL_2026` 主形 + 厂商变体）即为此设计，落库时按 `dialect` 选形、缺失则回退主形并记 warning。
2. **catalog/schema 层级不齐**：Snowflake 三层、BigQuery `project.dataset.table`、PG `db.schema.table`、ClickHouse `db.table`。统一抽象成 `Namespace = string[]`，不要假设层数。
3. **视图/存储过程**：只把视图当表读；存储过程一律不进 agent 可见面（副作用不可控）。
4. **行级/列级权限**：**必须下推到数据库**（RLS/CLS、Snowflake row access policy、PG RLS）。MCP server 里的过滤只是二次校验，ClickHouse 文档自己也写明"destructive gate 不是安全边界，边界是 grant"。连接必须用专用只读角色。
5. **万级表**：物理枚举绝不进上下文。只暴露 L1 里"已建模"的对象；未建模的走 `listObjects` 分页（`page_token`，单次 ≤50），服务端检索，命中后回传少量候选。
6. **查询成本**：三道闸——`explain` 预估 → `max_scan_bytes` 拒绝 → 运行时 `timeout_ms` + `KILL QUERY`。mcp-clickhouse 的默认值可作为基线（30s 超时、10 worker、元数据独立线程池避免拖慢查询）。
7. **连接池/并发**：MCP 侧无状态后，连接复用完全落在 server 内部，必须显式配置池上限；否则 agent 并发一上来就打爆数据库连接数。
8. **CDC/实时**：不在 Connector 主路径。CDC 走独立管道落到表，语义层把它当普通表读，用 `freshness` 元数据（可借 OpenLineage facet）标注延迟。

---

## 5. 风险与治理清单

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| 1 | Ossie 0.x 破坏性变更（0.2.0 扁平化 + 名字解析改语义） | 已落盘模型失效、下游 parse error | 锁 0.1.1 子集；`to_ossie_0_1_1()` 适配层；CI 对两个版本双向校验 |
| 2 | dbt 只认 0.1.0/0.1.1 | 互通断链 | 版本白名单硬校验；dbt v2 支持前不升 |
| 3 | MCP 年更，2026-07-28 删会话/删 SSE 重放 | 长连接与游标设计作废 | 按无状态设计；游标作普通参数；`server/discover` 做版本协商 |
| 4 | MCP Registry 仍 preview，且**不支持私有 server** | 企业内部无法依赖公共注册表 | 自建私有 registry，实现官方 OpenAPI；server.json 作元数据格式 |
| 5 | 工具描述/返回内容构成注入面 | 提示注入、数据外泄 | 工具描述纳入评审；结果做结构化裁剪；不把自由文本原样回灌 |
| 6 | 「只读」被误当安全边界 | 全表扫打爆成本、越权读 | 专用只读角色 + RLS/CLS 下推 + 字节预算 + `KILL QUERY` |
| 7 | 万级表上下文爆炸 | 准确率崩、token 成本失控 | 只暴露已建模对象；服务端检索 + 分页；语义层裁剪 |
| 8 | 语义漂移（同名指标多定义） | 数字对不上、信任崩塌 | 单真源 + `verified_queries`；CI 做指标回归；OpenLineage 追影响面 |
| 9 | 稳定 ID 缺失导致血缘断链 | 重命名 = 删除+新建 | 自建 ULID `stable_ids`，与 name 解耦 |
| 10 | 命名冲突：DataHub 的「MCP」指 Metadata Change Proposal | 沟通与检索歧义 | 文档内一律写「Model Context Protocol」全称 |
| 11 | 许可与商标 | 合规风险 | Ossie/Apache 系 Apache-2.0；LookML/Palantir 专有，只做转换不做分发；Cube 核心与云版许可差异需法务确认（未核实） |

**治理建议（最小可运行）：** (a) 语义模型走 Git + PR，CODEOWNERS 按域；(b) CI 四道门——Ossie schema 校验、语义 diff 分级、指标回归、`digest` 变更需人工 ack；(c) 每个 metric 必须有 owner、`ai_context`、至少一条 `verified_query`；(d) 上线前跑转换器矩阵（dbt / Snowflake / Cube），确保不是"只能自己读的模型"。

---

## 6. 链接

- Apache Ossie 仓库：https://github.com/apache/ossie （原 `open-semantic-interoperability/osi` 已重定向）
- Ossie 核心规范：https://github.com/apache/ossie/blob/main/core-spec/spec.md
- Ossie ontology 规范：https://github.com/apache/ossie/blob/main/ontology/ontology.md
- Ossie 路线图：https://github.com/apache/ossie/blob/main/ROADMAP.md
- Ossie 文档总览（含参与组织/转换器/版本策略）：https://github.com/apache/ossie/blob/main/docs/index.md
- Ossie 转换器：https://github.com/apache/ossie-converters
- ASF 孵化状态页：https://incubator.apache.org/projects/ossie.html
- dbt 语义模型：https://docs.getdbt.com/docs/build/semantic-models
- dbt 对 Ossie 文档的原生支持：https://docs.getdbt.com/docs/build/ossie-semantic-models
- dbt MCP server：https://docs.getdbt.com/docs/dbt-ai/about-mcp
- Cube 数据建模：https://docs.cube.dev/reference/data-modeling/cube
- LookML 概念（未直取，通用引用）：https://cloud.google.com/looker/docs/lookml-terms-and-concepts
- Databricks UC Metric Views：https://docs.databricks.com/aws/en/uc-semantics/metric-views
- Databricks Metric View YAML 参考：https://docs.databricks.com/aws/en/uc-semantics/metric-views/yaml-reference
- Snowflake Semantic Views：https://docs.snowflake.com/en/user-guide/views-semantic/overview
- Snowflake Semantic View YAML 规范：https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec
- Palantir Ontology：https://www.palantir.com/docs/foundry/ontology/overview/
- Palantir Ontology branching/proposals：https://www.palantir.com/docs/foundry/ontologies/branching-ontology/
- OpenLineage 规范：https://openlineage.io/ ；schema：https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.json
- OpenMetadata 词汇表：https://docs.open-metadata.org/latest/how-to-guides/data-governance/glossary
- DataHub：https://datahubproject.io/
- Iceberg REST Catalog 规范：https://iceberg.apache.org/rest-catalog-spec/
- ODCS：https://bitol-io.github.io/open-data-contract-standard/latest/
- MCP 版本策略（current = 2026-07-28）：https://modelcontextprotocol.io/specification/versioning
- MCP 2026-07-28 变更：https://modelcontextprotocol.io/specification/2026-07-28/changelog
- MCP 弃用登记表：https://modelcontextprotocol.io/specification/2026-07-28/deprecated
- MCP Registry：https://modelcontextprotocol.io/registry/about
- MCP 规范仓库：https://github.com/modelcontextprotocol/modelcontextprotocol
- MCP Toolbox for Databases：https://github.com/googleapis/mcp-toolbox
- mcp-clickhouse：https://github.com/ClickHouse/mcp-clickhouse
- Snowflake 官方 MCP（社区版已弃用）：https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp
- RFC 8785（JCS）：https://www.rfc-editor.org/rfc/rfc8785
- RFC 6902（JSON Patch）：https://www.rfc-editor.org/rfc/rfc6902

**未核实项汇总**：OSI 最初发起方名单（仅据仓库与站台组织推断）；Cube 开源核心的精确许可条款；MCP Registry 实际收录 server 数量与活跃度；AtScale 具体 schema 形态；Palantir OSDK 当前主版本号；ODCS/MCP 规范的许可证逐条条款。
