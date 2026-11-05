# H. DataAgent Ontology 载体草案（设计稿，未实施）

> 目标：给「探查 → 建模 → 问数 → 分析」一条链上的所有组件一个**唯一的、可版本化、可 diff、可被人审阅**的语义载体。
> 原则：**对外兼容 Apache Ossie，对内扩展 AgentOS 需要的证据、版本与策略字段**；不另造对外格式。

---

## 1. 分层

| 层 | 文件 | 变更频率 | 责任方 | 说明 |
|---|---|---|---|---|
| L0 物理画像 | `profile/<dataset>.json` | 每次探查 | 系统自动 | 类型、空值率、基数、分位、Top-K 值、采样行。**可再生，不进 Git**。 |
| L1 语义模型 | `semantic/model.yaml` | 随数仓 | 数据工程 | Ossie 兼容：dataset / field / metric / relationship。BI、dbt、Snowflake、Cube 都能读。 |
| L2 概念本体 | `semantic/concepts.yaml` | 随业务语言 | 业务/数据治理 | 实体类型、值类型、关系语义、同义词、业务规则。可选；没有也能跑。 |
| L3 物理映射 | `semantic/mapping.yaml` | 随建模习惯 | 数据工程 | 概念 ↔ 物理字段；等价 R2RML 的现代写法。可选。 |
| L4 运行策略 | `semantic/policy.yaml` | 随合规要求 | 安全/平台 | 只读、行过滤、列脱敏、预算、超时、可外发字段。**与语义解耦**，避免每次合规变更都改模型版本。 |
| L5 证据与记忆 | `memory/`（SQLite + 向量索引） | 每次问答 | 系统自动 | 已验证问答、失败样本、口径澄清记录、查询日志。**本机数据，不进包**。 |

> 关键判断：**L0/L5 不进版本库**。它们体积大、变化快、含敏感值；进 Git 只会让 diff 不可读。语义版本只覆盖 L1–L4。

---

## 2. 文件草案

```yaml
# semantic/model.yaml —— Ossie 0.1.1 兼容子集 + AgentOS 扩展
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
        description: 订单唯一标识
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
    metrics:
      - name: order_count
        expression: { sql: COUNT(DISTINCT order_id) }
        datatype: Integer

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

# ── AgentOS 扩展：只放在 custom_extensions，保证 Ossie 校验通过 ──
custom_extensions:
  - vendor_name: AGENTOS
    data: |
      {
        "schema": "dataagent.agentos/v1",
        "ontology_id": "01J8ZK3Q7M2R9V6T0W4X8Y2B5C",
        "model_version": "2.3.0",
        "digest": "sha256:9f2c…",
        "stable_ids": {
          "orders": "01J8ZK3Q", "orders.gmv": "01J8ZK4A",
          "customers": "01J8ZK5B"
        },
        "evidence": {
          "orders.customer_id->customers.customer_id": {
            "kind": "many_to_one",
            "confidence": 0.997,
            "signals": ["declared_fk_pg_constraint", "value_overlap=0.997", "distinct_ratio=0.12"],
            "proposed_by": "profiler@0.4.2",
            "reviewed_by": "u_1024",
            "reviewed_at": "2026-10-21T09:12:00+08:00"
          }
        },
        "grain": { "orders": ["order_id"] },
        "freshness": { "orders": { "column": "paid_at", "lag_minutes": 15 } },
        "value_index": {
          "orders.status": { "kind": "enum", "values": ["paid", "refunded", "cancelled", "pending"], "source": "profile:2026-10-21" },
          "customers.region": { "kind": "topk", "values": ["华东", "华南", "华北", "西南"], "coverage": 0.98 }
        }
      }
```

```yaml
# semantic/concepts.yaml —— 只在需要“业务语言 → 概念”对齐时出现
name: sales_ontology
prefixes:
  org: "http://www.w3.org/ns/org#"
concepts:
  - concept: Customer
    type: EntityType
    iri: org:FormalOrganization
    identify_by: [customer_id]
    relationships:
      - name: places
        roles: [{ concept: Order }]
        multiplicity: OneToMany
        verbalizes: ["{Customer} 下单 {Order}"]
  - concept: Order
    type: EntityType
    identify_by: [order_id]
```

```yaml
# semantic/policy.yaml —— 与语义版本独立演进
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
  allow_raw_rows: false      # 只允许聚合结果离开本机
```

---

## 3. 版本与 diff

| 维度 | 规则 |
|---|---|
| 版本号 | L1 语义模型 `major.minor.patch`。删字段/改表达式/改 join 基数 = major；加同义词/加样例/补 description = minor；措辞 = patch。 |
| digest | 对 canonical JSON（RFC 8785 JCS）算 sha256。**digest 变而语义未变**（格式化/键序）不触发下游重编译。 |
| 稳定 ID | 每个 entity/field/metric/join 一个 ULID，**与 name 解耦**。重命名不产生“删除+新建”，血缘不断。 |
| 状态机 | `draft → review → published → deprecated`。只有 `published` 能被问数链路默认使用；草稿只能被显式指定。 |
| diff | 机器：RFC 6902 JSON Patch；人：按 entity/field/metric/join 分类的语义 diff，标 breaking / non-breaking。 |
| 迁移 | `migrations/<from>-<to>.yaml` 声明式改写 + `supersedes` 链；CI 跑「旧模型 + 迁移 = 新模型」等价性断言。 |
| 兼容 | 导出器保证 `to_ossie_0_1_1()` 与 `to_ossie_0_2()` 双版本可校验；dbt / Snowflake / Cube 转换器作为回归门禁。 |

---

## 4. 从物理库自动生成到哪一步

| 步骤 | 自动化程度 | 产出 | 人工介入 |
|---|---|---|---|
| 1. 枚举对象 | 全自动 | 表/视图清单（分页、上限） | 选择建模范围 |
| 2. 画像 | 全自动 | 类型、空值、基数、分位、Top-K、采样 | 无 |
| 3. 主键/唯一键推断 | 全自动（唯一性 + 非空 + 命名） | 候选键 + 置信度 | 冲突时确认 |
| 4. 外键/包含依赖 | 自动（值重叠率、包含依赖算法、命名相似） | join 候选图 | 低置信度需确认 |
| 5. 表/列语义命名 | LLM 生成 + 词典 | 中文名、描述、同义词 | 抽样审阅 |
| 6. 指标候选 | LLM 从列名/枚举/历史 SQL 提议 | 指标草案（公式、口径） | **必须人审** |
| 7. 已验证问答 | 从历史查询/用户反馈挖掘 | verified queries | 逐条确认 |
| 8. 发布 | 自动校验 + 审批 | `published` 版本 + digest | 审批人 |

> 经验判断：**1–5 可以做到 80% 自动化，6–7 只能做到“提议”，第 8 步必须有人。** 把人力集中在指标口径与已验证问答上，是投入产出比最高的做法。
