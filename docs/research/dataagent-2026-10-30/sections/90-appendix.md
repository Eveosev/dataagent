## 附录 A：Ontology 载体草案

> 目标：给"探查 → 建模 → 问数 → 分析"一条链上的所有组件一个唯一的、可版本化、可 diff、可被人审阅的语义载体。
> 原则：**对外兼容 Apache Ossie 0.1.1，对内扩展证据、版本与策略字段**；不另造对外格式。

### A.1 分层

| 层 | 文件 | 变更频率 | 责任方 | 说明 |
|---|---|---|---|---|
| L0 物理画像 | `profile/<dataset>.json` | 每次探查 | 系统自动 | 类型、空值率、基数、分位、Top-K、采样。**可再生，不进 Git** |
| L1 语义模型 | `semantic/model.yaml` | 随数仓 | 数据工程 | Ossie 兼容：dataset / field / metric / relationship |
| L2 概念本体 | `semantic/concepts.yaml` | 随业务语言 | 业务/治理 | 实体类型、值类型、关系语义、同义词。可选 |
| L3 物理映射 | `semantic/mapping.yaml` | 随建模习惯 | 数据工程 | 概念 ↔ 物理字段。可选 |
| L4 运行策略 | `semantic/policy.yaml` | 随合规要求 | 安全/平台 | 只读、行过滤、脱敏、预算。**与语义解耦** |
| L5 证据与记忆 | `memory/`（SQLite + 向量索引） | 每次问答 | 系统自动 | verified queries、失败样本、澄清记录。**本机数据** |

**关键判断**：L0/L5 不进版本库——体积大、变化快、含敏感值。语义版本只覆盖 L1–L4。

### A.2 `semantic/model.yaml`（Ossie 0.1.1 兼容子集 + 扩展）

```yaml
version: 0.1.1
name: sales
description: 销售域语义模型
ai_context:
  instructions: |
    金额统一为人民币元；GMV 含税、不含退款。
    “本月”默认按自然月，财年从 4 月开始。
  synonyms: [销售域, 交易域]

datasets:
  - name: orders
    source: dw.sales.orders
    primary_key: [order_id]
    unique_keys: [[order_no]]
    description: 订单主表，一行一个订单
    fields:
      - name: order_id
        expression: { sql: order_id }
        datatype: String
      - name: paid_at
        expression: { sql: pay_time }
        datatype: Timestamp
        dimension: { is_time: true }
        ai_context: { synonyms: [支付时间, 成交时间] }
      - name: status
        expression: { sql: order_status }
        datatype: String
        ai_context:
          synonyms: [订单状态]
          enum: [paid, refunded, cancelled, pending]
      - name: amount_cents
        expression: { sql: pay_amount }
        datatype: Decimal
        ai_context: { synonyms: [支付金额, 成交额], unit: cent }

  - name: customers
    source: dw.crm.customers
    primary_key: [customer_id]
    fields:
      - name: customer_id
        expression: { sql: cust_id }
        datatype: String
      - name: region
        expression: { sql: region_name }
        datatype: String
        ai_context: { synonyms: [大区, 区域] }

relationships:
  - name: orders_to_customers
    from: orders
    to: customers
    from_columns: [customer_id]
    to_columns: [customer_id]
    ai_context: { description: 订单归属客户，多对一 }

metrics:
  - name: gmv
    expression: { sql: "SUM(orders.amount_cents) / 100.0" }
    datatype: Decimal
    ai_context:
      synonyms: [GMV, 成交总额, 商品交易总额]
      unit: CNY
      examples: ["上个月华东区 GMV", "今年 GMV 同比"]

custom_extensions:
  - vendor_name: AGENTOS
    data: |
      {
        "schema": "dataagent.agentos/v1",
        "ontology_id": "01J8ZK3Q7M2R9V6T0W4X8Y2B5C",
        "model_version": "2.3.0",
        "digest": "sha256:9f2c…",
        "stable_ids": { "orders": "01J8ZK3Q", "orders.gmv": "01J8ZK4A" },
        "evidence": {
          "orders.customer_id->customers.customer_id": {
            "kind": "many_to_one",
            "confidence": 0.997,
            "signals": ["declared_fk_pg_constraint", "value_overlap=0.997", "distinct_ratio=0.12"],
            "proposed_by": "profiler@0.4.2",
            "reviewed_by": "u_1024"
          }
        },
        "value_index": {
          "orders.status": { "kind": "enum", "values": ["paid","refunded","cancelled","pending"] },
          "customers.region": { "kind": "topk", "values": ["华东","华南","华北","西南"], "coverage": 0.98 }
        }
      }
```

### A.3 `semantic/policy.yaml`（与语义版本独立）

```yaml
version: 1
read_only: true
budgets:
  max_scan_bytes: 2000000000
  timeout_ms: 30000
  max_rows: 5000
  max_llm_calls_per_question: 8
row_filters:
  orders: "region_id IN (SELECT region_id FROM auth.user_region WHERE uid = :uid)"
column_masks:
  customers.phone: sha256
  customers.id_card: deny
export:
  allow_raw_rows: false
```

### A.4 版本与 diff 规则

| 维度 | 规则 |
|---|---|
| 版本号 | `major.minor.patch`。删字段/改表达式/改 join 基数 = major；加同义词/样例/描述 = minor；措辞 = patch |
| digest | canonical JSON（RFC 8785 JCS）+ sha256；digest 变而语义未变不触发重编译 |
| 稳定 ID | 每个 entity/field/metric/join 一个 ULID，与 name 解耦（Ossie 的 name-as-id 未决） |
| 状态机 | `draft → review → published → deprecated`；只有 published 被问数链路默认使用 |
| diff | 机器 RFC 6902 JSON Patch；人读语义 diff（breaking / non-breaking）+ 影响面分析 |
| 迁移 | `migrations/<from>-<to>.yaml` + `supersedes` 链 + 等价性断言 |
| 兼容 | 导出 `to_ossie_0_1_1()` / `to_ossie_0_2()`；dbt / Snowflake / Cube 转换器作为回归门禁 |

### A.5 自动化水位

| 步骤 | 自动化 | 人的角色 |
|---|---|---|
| 枚举对象 / 画像 | 100% | 选范围 |
| 主键/唯一键 | 90% | 冲突裁决 |
| 外键/包含依赖 | 70–85% | 低置信确认 |
| 表/列语义命名 | 80% | 抽样审阅 |
| **指标口径** | **30–50%** | **必须人审** |
| 已验证问答 | 40% | 逐条确认 |
| 发布 | 95% | 审批 |

---

## 附录 B：Mint 包清单示例

### B.1 能力入口 bundle（`dataagent-ask`）

```toml
[package]
name = "dataagent/ask"
version = "0.1.0"
kind = "bundle"
description = "DataAgent 智慧问数：召回、NL2SQL、澄清、执行"

[provides]
mcp_servers = ["dataagent_ask"]
skills = ["dataagent-ask"]

[dependencies]
"dataagent/iface" = "=0.1.0"
"dataagent/ontology" = "=0.1.0"
"dataagent/recall" = "=0.1.0"
"dataagent/nl2sql" = "=0.1.0"
"dataagent/connectors" = "=0.1.0"

[capabilities]
exec = ["node"]
env = ["DATAAGENT_PROJECT_ROOT", "DATAAGENT_DATA_ROOT", "DATAAGENT_CONFIG"]

[capabilities.reason]
exec = "Run the DataAgent MCP service and bounded workers."
env = "Read explicit project configuration and secret references."

[artifacts]
layout = "any"
```

`.mcp.json`：

```json
{
  "mcpServers": {
    "dataagent_ask": {
      "command": "node",
      "args": ["$PKG/dist/index.mjs"]
    }
  }
}
```

目录：

```text
ask/
├── mint.toml
├── .mcp.json
├── dist/index.mjs
├── skills/dataagent-ask/SKILL.md
├── schemas/            # 工具入参/出参 JSON Schema
└── README.md
```

### B.2 契约 bundle（`dataagent-iface`）

```toml
[package]
name = "dataagent/iface"
version = "0.1.0"
kind = "bundle"
description = "DataAgent 契约：Ontology / Answer / Job / Connector 的形状"

[provides]
interfaces = ["dataagent-ontology", "dataagent-answer", "dataagent-connector"]
skills = ["dataagent-iface"]
```

### B.3 组合 preset（`dataagent`）

```toml
[package]
name = "dataagent/dataagent"
version = "0.1.0"
kind = "preset"
description = "DataAgent 默认组合：探查 + 问数 + 分析"

[provides]
presets = ["dataagent"]

[dependencies]
"dataagent/explore" = "=0.1.0"
"dataagent/ask" = "=0.1.0"
"dataagent/functions" = "=0.1.0"
"dataagent/eval" = "=0.1.0"

[artifacts]
layout = "any"
```

### B.4 安装与验证（发布前必须做）

```bash
mint publish --dry-run                     # 本地检查，不上传
mint add dataagent/dataagent@0.1.0         # 干净项目
mint inspect dataagent/dataagent --abilities
# 启动后确认：工具可见、ask_question 可调用、job 可轮询、产物路径可读
```

注意：`mint publish --dry-run` **不验证远端权限**；真实发布需要 `publish-new`/`publish-update` 令牌；版本不可重复发布。

---

## 附录 C：关键来源

**标准与协议**
- Apache Ossie：https://github.com/apache/ossie ｜ 规范：https://github.com/apache/ossie/blob/main/core-spec/spec.md ｜ ontology：https://github.com/apache/ossie/blob/main/ontology/ontology.md
- dbt 对 Ossie 的支持：https://docs.getdbt.com/docs/build/ossie-semantic-models
- MCP 规范（current = 2026-07-28）：https://modelcontextprotocol.io/specification/versioning
- MCP Toolbox for Databases：https://github.com/googleapis/mcp-toolbox

**商业产品**
- Databricks Genie：https://docs.databricks.com/aws/en/genie/ ｜ Genie Agents：https://docs.databricks.com/aws/en/genie-agents/
- Snowflake Cortex Agents：https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents ｜ Semantic Views：https://docs.snowflake.com/en/user-guide/views-semantic/overview
- Microsoft Fabric data agent：https://learn.microsoft.com/en-us/fabric/data-science/concept-data-agent
- Palantir Ontology：https://www.palantir.com/docs/foundry/ontology/overview/
- Cube：https://cube.dev/ ｜ dbt Semantic Layer：https://www.getdbt.com/product/semantic-layer ｜ AtScale：https://www.atscale.com/
- ThoughtSpot：https://docs.thoughtspot.com/cloud/latest/ ｜ Sigma：https://www.sigmacomputing.com/product/ai

**开源**
- WrenAI：https://github.com/Canner/WrenAI ｜ MDL：https://github.com/Canner/WrenAI/blob/main/docs/core/reference/mdl.md
- DB-GPT：https://github.com/eosphoros-ai/DB-GPT ｜ SuperSonic：https://github.com/TencentMusic/SuperSonic
- Cube：https://github.com/cube-js/cube ｜ MetricFlow：https://github.com/dbt-labs/metricflow
- DuckDB：https://github.com/duckdb/duckdb ｜ sqlglot：https://github.com/tobymao/sqlglot
- DataHub：https://github.com/datahub-project/datahub ｜ OpenMetadata：https://github.com/open-metadata/OpenMetadata

**Benchmark 与论文**
- BIRD：https://bird-bench.github.io/ ｜ BIRD-Interact：https://bird-interact.github.io/ ｜ LiveSQLBench：https://livesqlbench.ai/
- Spider 2.0：https://arxiv.org/abs/2411.07763
- CHESS：https://arxiv.org/abs/2405.16755 ｜ CHASE-SQL：https://arxiv.org/abs/2410.01943 ｜ XiYan-SQL：https://arxiv.org/abs/2411.08599
- ReFoRCE：https://arxiv.org/abs/2502.00675 ｜ LinkAlign：https://arxiv.org/abs/2503.18596
- DSABench：https://arxiv.org/abs/2610.14700 ｜ SemJoin：https://arxiv.org/abs/2606.29532 ｜ Uber-Join：https://arxiv.org/abs/2610.25178

**中国**
- Quick BI：https://www.aliyun.com/product/quick-bi ｜ FineBI：https://www.finebi.com/ ｜ SmartBI：https://www.smartbi.com.cn/
- Kyligence：https://cn.kyligence.io/ ｜ 观远：https://www.guandata.com/ ｜ 腾讯云 BI：https://cloud.tencent.com/product/bi
- OceanBase：https://www.oceanbase.com/ ｜ SelectDB：https://www.selectdb.com/ ｜ StarRocks：https://www.starrocks.io/

> 完整来源见 `parts/A–G` 各文件末尾；本附录只列决策直接依赖的一手链接。
