---
title: "广义 General DataAgent 数据工程能力：现状、可复用件与 agent 化改造点"
description: "为《DataAgent 模块化能力拆分调研报告》提供 8 类广义数据工程能力的成熟度、代表件、接口、输入输出契约与 agent 化改造点，并给出'扩展 vs 补充'判定"
source: "https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c"
reference: "../../docs/research/dataagent-2026-11-01/00-module-capability-draft.md"
retrieved_on: 2026-11-01
timezone: Asia/Shanghai
status: research-input
category: research
type: landscape
tags: [General-DataAgent, data-engineering, ingestion, modeling, quality, entity-resolution, lineage, observability, rbac, orchestration]
---

# 广义 General DataAgent 数据工程能力调研

> 本文只回答一个问题：当 DataAgent 从"给定数据库和语义库"变成"无数据库 → 构建并持续运行数据库"时，8 类数据工程能力里哪些能直接复用、哪些只是同一模块的边界变大、哪些是狭义根本不存在的模块。
>
> 与[模块能力草案](../../docs/research/dataagent-2026-11-01/00-module-capability-draft.md)的 `DA01–DA12` 对齐，不另立一套编号；新增模块在第三节给出建议编号。

## 0. 阅读约定

**证据标记。** 文中每条判断前标 `【事实】` 或 `【推断】`：
- `【事实】`：来自官方文档/规范/法条原文，见第六节链接（均为 2026-11-01 访问）。允许"文档这么写、实现未必如此"的落差，已尽量标注。
- `【推断】`：基于接口形状、工程经验和相邻产品行为的外推，没有单一原文可引。

**成熟度两轴。** 工具成熟 ≠ agent 可编排。两类分开打分（M0–M3）：

| 等级 | 工具成熟度 | agent 可编排度 |
| --- | --- | --- |
| M3 | 事实标准 + 多实现 + 生产验证多年 | 有机器可读的声明式配置 + 可预览/可 diff + 可回滚 |
| M2 | 主流工具，接口稳定但生态分散 | 有声明式配置，但缺 plan/diff，或只有专有 API |
| M1 | 单点可用，接口随版本变 | 只能通过 UI 或自然语言描述，无法机器校验 |
| M0 | 无标准、无稳定实现 | 无 |

**agent 化四层框架（后文反复使用）。** 从"人写配置/人点按钮"到"agent 生成 + 人审核"，任何一类能力都要补齐四层：

| 层 | 内容 | 缺了会怎样 |
| --- | --- | --- |
| A0 发现 | agent 能列出对象、字段、当前状态、历史版本 | agent 只能猜，改错对象 |
| A1 生成 | agent 产出声明式配置（YAML/DQDL/SodaCL/SQL/settings JSON） | 只能人肉操作，无法复现 |
| A2 预演 | 在隔离环境 `plan`/`diff`/`dry-run`/采样验证，产出可审阅的变更计划 | 变更直接打生产，"生成成功"被当成"正确" |
| A3 发布 | 版本、审批、回滚、审计、影响面 | 错误进入共享资产并扩散 |

**8 类能力在这四层上的完成度，是本文最重要的结论来源**：A1 普遍可做（都是声明式），A2 只有建模域（dbt/SQLMesh）真正做好，A0/A3 几乎全行业缺失。

## 1. 8 类能力总表

| # | 类别 | 成熟度（工具/agent） | 代表件（开源 / 商业） | 可作为契约的标准接口 | agent 化改造点（缺哪层） | 最易低估的难点 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 接入与同步 | M3 / M1 | Airbyte、dlt、Debezium、Kafka Connect；Fivetran、HVR；Iceberg/Delta/Hudi | Airbyte Protocol（catalog/stream/field）、Debezium 信令表、Iceberg REST、Delta protocol | A2 缺失：有 catalog 无"变更计划"。需把 source schema diff + 游标状态 + 回填范围做成可审阅 plan | 增量 + schema evolution + 软删除三者组合出的"静默丢列/静默重复" |
| 2 | 建模与转换 | M3 / M2 | dbt、SQLMesh、Spark、Iceberg/Delta；Databricks、Snowflake | dbt contract YAML + manifest.json；SQLMesh plan/state；表格式 | A3 部分缺失：有 preflight 无"业务口径审批"。需把 contract 变更升级为语义审批 | 契约只保证形状，不保证口径；`select *` 让"breaking"判定失效 |
| 3 | 数据质量 | M2 / M2 | Great Expectations、Soda、dbt tests、Deequ；Sifflet、Anomalo | GX Expectation Suite JSON；SodaCL；DQDL；dbt test YAML | A0/A2 弱：规则生成容易，但"规则是否拟合了历史缺陷"无人校验 | 规则把现状写成契约；规则爆炸与归因错误 |
| 4 | 实体解析与身份 | M2 / M1 | Splink、Zingg；Senzing、Commercial MDM | Splink settings JSON（blocking/comparisons）；Zingg 配置；输出 cluster + match_probability | A3 缺失最严重：无 merge/split 工作流、无证据链、无撤销 | 合并不可逆，且下游已按旧 ID 固化 |
| 5 | 目录、血缘与元数据 | M2 / M2 | DataHub、OpenMetadata、OpenLineage、Unity Catalog、Iceberg REST | OpenLineage RunEvent + facet；DataHub URN/aspect；OM REST；UC REST | A0 覆盖率高估：lineage 要每个 job 主动 emit，column 级依赖 SQL 解析 | "有血缘"≠"血缘完整"；动态 SQL/UDF 断裂无告警 |
| 6 | 可观测性 | M2 / M2 | Elementary；Monte Carlo、Metaplane、Bigeye | MaC YAML（Monitors as Code）、Elementary 配置；无开放告警标准 | A2 呈现方式错：agent 能给阈值，但给不出"预期告警量" | 告警疲劳 + 基线漂移 + 影响面漏算，三件事互相掩护 |
| 7 | 权限与合规 | M2 / M0 | BigQuery policy tags、Snowflake masking/row policy、Iceberg credential vending；Immuta | policy tag、masking policy、row access policy、Iceberg REST 凭证下发 | A0–A3 全缺：无"权限对派生副本的传播"接口 | 权限在采样/索引/缓存/LLM 上下文处失效，入口检查通过 |
| 8 | 调度与编排 | M3 / M2 | Airflow、Dagster、Temporal；Dagster+、Prefect | Airflow asset-aware scheduling；Dagster asset/partition；Temporal workflow/activity | A2 部分有（backfill 预览），A3 弱：agent 生成的 DAG 无"幂等性证明" | 非幂等重跑、回填与增量交错、取消不生效导致僵尸 run |

**一句话读表**：8 类里没有一类是"工具不够用"，缺的几乎都是同一件东西——**机器可审阅的变更计划**。这直接决定了报告里"agent 生成 + 人审核"能否落地为接口，而不是产品话术。

---

## 2. 分类详述

### 2.1 接入与同步

**成熟度。** `【事实】` Airbyte 的 Protocol 把接入抽象为 actor（source/destination）与 catalog/configured catalog/stream/field 四类原语，并区分 STDIO JSON 与 Socket(Protobuf) 两种通道；同步模式按"源侧 incremental（cursor 或 CDC）/full refresh"×"目标侧 overwrite/append/append+deduped"组合。`【事实】` Fivetran 的模型是 initial sync → incremental sync，用 cursor 记录同步历史，失败或不一致时走 re-sync，部分连接器每天做一次 rollback sync 补窗口；默认每 6 小时同步一次。`【事实】` dlt 提供 delete-insert/scd2/upsert/insert-only/cdc 等 merge 策略与 cursor 增量，并有 `schema_contract` 的三级（tables/columns/data_type）× 四态（evolve/freeze/discard_value…）。`【事实】` Debezium PostgreSQL 连接器支持 initial/always/no_data 等 `snapshot.mode`，ad-hoc 与 blocking snapshot，incremental snapshot 通过信令表（`execute-snapshot`）或 Kafka 信令 topic 触发。

**可复用件。**
- 连接器/协议：Airbyte Protocol（可作为"任意源 → 统一 catalog"的适配层）、dlt（Python 内嵌，最适合 agent 生成代码）、Debezium（CDC 事实标准）。
- 表格式：`【事实】` Iceberg 以 snapshot + 单调递增 sequence number 组织版本，snapshot 带 `snapshot-id`/`timestamp-ms`，`refs` 支持 branch/tag，删除以 equality/position delete（v4 起为 deletion vector）表达；`【事实】` Delta 提供 time travel 与 CDF（跨版本行级变更）；`【事实】` Hudi 以 timeline 的 instant 组织提交，支持 snapshot 与 incremental 查询（指定 `beginInstantTime`）。

**接口（可作为 DataAgent 契约的部分）。**

| 接口 | 能表达什么 | 不能表达什么 |
| --- | --- | --- |
| Airbyte configured catalog | 选哪些 stream/field、用哪种 sync mode | 业务粒度、软删除语义、口径 |
| Debezium 信令表 | 触发一次性快照/增量快照 | 快照期间的 schema 变更（`【事实】` 文档明确：incremental snapshot 运行中不支持 schema change） |
| Iceberg/Delta 表格式 | as-of 读取、schema evolution、行级删除 | "这条删除是业务撤销还是合规删除" |
| Iceberg REST Catalog | 目录与凭证下发（`【事实】` 支持 credential vending / remote signing） | 数据内容级授权 |

**输入输出契约（建议）。**

```yaml
# 输入
source: {type: postgres|s3|api, connection_ref: secret://..., selection: [stream...]}
mode: {read: cursor|cdc|full, write: append|merge|scd2, cursor: {field, start, lag_window}}
schema_policy: {on_add: evolve|fail, on_type_narrow: fail, on_drop: fail_and_report}
slo: {freshness_minutes, completeness_window}
# 输出
dataset_version:
  source_id, stream, snapshot_id | cursor_value, watermark_ts,
  schema_hash, row_count, deleted_row_count, partial: bool,
  dropped_columns: [...],   # 必须显式，不能静默
  lineage_event_ref, sync_receipt_ref
```

**agent 化改造点。**
1. A0：把 `catalog` + 当前 cursor + 上次同步回执暴露为可查询对象（Airbyte/dlt 都有元数据，但未按"agent 可读"组织）。
2. A1：agent 生成 configured catalog + schema_policy，而不是点 UI。dlt 的 Python 声明式最适合，Airbyte 走 API 次之。
3. A2（**关键缺口**）：生成"接入变更计划"——新增/删除列、类型收窄、游标回退、需要回填的区间、预计行数与成本，全部在真正同步前给人看。当前工具只给"同步结果"，不给"同步前差异"。
4. A3：把 `schema_policy` 的每一次触发（尤其 drop/narrow）记成可审计事件，并与 DA12 的回归集绑定。

**最容易低估的难点。** 增量位点、schema 演化、软删除不是三个独立配置，而是一个三元耦合：`【推断】` 上游改列名后，evolve 策略会新建列、旧列变 NULL，下游 `not_null` 仍通过；软删除若只写 `_deleted=true` 而不参与游标过滤，增量窗口会永远重复投递同一批已删行；回填与 CDC 并行时，若 merge 无唯一键，同一行会被计两次。工具层不会报错，指标层会静默偏移。

### 2.2 建模与转换

**成熟度。** 这是 8 类里唯一"agent 可编排度"接近 M2 的域，因为它的产物天然是声明式 + 可 diff 的。`【事实】` dbt contract 在 `enforced: true` 时要求声明每一列的 name 与 data_type，构建前做 preflight 校验，构建时把列与约束写进 DDL；breaking change（删列/改类型/改约束/删合约模型）会直接报错；`【事实】` dbt model versions 提供 `latest_version` 与 `deprecation_date`（1.6 起）。`【事实】` SQLMesh 的 plan 把变更分为 breaking / non-breaking / forward-only：breaking 会连带回填下游，non-breaking 只回填自身，forward-only 复用物理表不回填；destructive change 默认 `error`、additive 默认 `allow`，可用 `--allow-destructive-model` 临时放开；每个模型版本对应独立物理表，环境只是引用集合（virtual environments）。

**可复用件。** dbt（contract/versions/tests/exposures）、SQLMesh（plan/virtual env/column-level lineage）、Spark（执行）、Iceberg/Delta（存储契约）。`【事实】` SQLMesh 的 column-level lineage 依赖 optimizer；关掉 optimizer 或使用未限定列/`select *` 时，该模型及下游的列级血缘会失效——这条直接决定"能不能信任 agent 生成的 lineage"。

**接口。**

| 接口 | 能表达 | 不能表达 |
| --- | --- | --- |
| dbt contract（YAML） | 列名、类型、部分约束（多数平台只强制 not_null） | 业务口径、指标定义、时间语义 |
| dbt tests | 内容级断言（可 `store_failures` 落表） | 变更影响面 |
| SQLMesh plan | 变更分类、回填区间、成本 | 业务审批意见 |
| manifest.json / state | 依赖图、编译产物 | 运行期真实数据特征 |

**输入输出契约（建议）。**

```yaml
# 输入
intent: {metrics: [...], dimensions: [...], grain: ..., time_semantics: ...}
target: {engine, materialization: table|view|incremental, partition: {column, granularity}}
guardrails: {contract: enforced, max_backfill_days, cost_budget, allow_destructive: false}
# 输出
model_plan:
  plan_id, diff: {added, removed, modified},
  classification: breaking|non-breaking|forward-only,
  compiled_sql, contract_status: pass|fail|uncontracted,
  backfill: {range, estimated_rows, estimated_cost},
  lineage_edges: [{from_col, to_col, transform}],
  semantic_binding: {metric_id, version}
```

**agent 化改造点。**
1. A1 已可用：agent 生成模型 SQL + contract YAML。
2. A2 是**现成的最佳范式**：`sqlmesh plan` 已经输出"改了什么 / 属于哪类变更 / 要回填哪段 / 大概多少钱"，这正是 DataAgent 需要的"可审阅变更计划"形状。dbt 的 preflight 只覆盖形状，不覆盖回填与成本。
3. A3 缺口：plan 通过 ≠ 口径正确。必须把 contract 变更接到 DA05 语义版本与 DA11 审批，否则 agent 可以"合法地"把 `gmv` 的过滤条件改掉而所有测试通过。
4. 需要补的元能力：区分"结构变更"与"语义变更"（同名列、同类型、不同口径），后者只能靠指标定义 diff，不能靠 schema diff。

**最容易低估的难点。** 契约保证的是**形状**，不是**口径**。`【事实】` dbt 官方明确 contract 与 tests 的分工：contract 是返回数据集的形状，tests 是内容校验，"tests 不属于 contract"。`【推断】` 于是 agent 生成的最危险变更不是删列（会报错），而是"同形状换语义"：把 `paid_at` 换成 `created_at`、把含税改成不含税、把 `status in ('paid')` 改成 `!= 'cancelled'`。所有 contract/preflight 都通过，只有业务方看得出来。

### 2.3 数据质量

**成熟度。** 规则引擎成熟（M2–M3），规则**生成**容易，规则**治理**（归因、修复、复核、退役）几乎全行业 M1。

**可复用件与接口。**
- `【事实】` Great Expectations：Expectation Suite 是 Expectation 集合，Checkpoint 是主要校验入口，可挂 Actions。
- `【事实】` Soda：SodaCL 以人类可读的 check 描述质量规则（v3 文档）。
- `【事实】` dbt tests：generic（内置四种 + 自定义 macro）与 singular（`tests/` 下 SQL），`--store-failures` 把失败行落表——这一点对 agent 归因极重要，因为失败样本可直接作为证据。
- `【事实】` Deequ：`VerificationSuite` + `Check`，支持 metrics repository、大数据 profiling、**基于历史指标的异常检测**、**约束自动建议**、增量指标计算，以及 DQDL 声明式规则语言。

**输入输出契约（建议）。**

```yaml
# 输入
assertions:
  - id, scope: {table, column?, partition?}, type: not_null|unique|range|enum|rowcount|freshness|custom_sql
    severity: warn|error, owner, baseline: {window, method: static|seasonal|quantile}
    sampling: {mode: full|sample, fraction, min_rows}
# 输出
check_run:
  run_id, assertion_id, status: pass|fail|error|skipped,
  observed, expected, deviation, anomaly_score,
  failing_rows_ref, sample_ref,
  attribution: [{candidate: upstream_job|schema_change|source_backfill, confidence, evidence_ref}],
  proposed_fix: {kind: dedupe|cast|map_value|fix_rule, diff, risk},
  review: {state: proposed|approved|rejected, reviewer, reason}
```

**agent 化改造点。**
1. A1：从 profile 生成候选断言（Deequ 的 constraint suggestion 已是现成能力），但**默认状态必须是 `proposed` 而不是 `enforced`**。
2. A0/A2（真缺口）：agent 需要"这条规则在过去 90 天会不会误报"的预演——即在历史分区上回放规则，输出告警量而非通过率。当前所有工具都只告诉你"现在过不过"。
3. A3：规则本身要有 owner、版本、退役条件；否则 agent 每接一个源就加 20 条规则，半年后没人敢删。
4. 归因必须走血缘（见 2.5），否则 agent 只能说"这张表有问题"，不能说"是上游 A 的 3 点那次回填导致的"。

**最容易低估的难点。** 规则会把**现状**写成**契约**。`【推断】` 用当前数据 profile 生成 `amount between 0 and 100000`，第二天出现 120000 的真实大单就被判失败；团队于是把上界调到 1e9，规则失去意义。更隐蔽的是"规则拟合缺陷"：源系统本来就有 2% 重复，agent 把 `duplicate_rate < 0.03` 写成断言，等于把 bug 合法化。质量规则的第一职责是表达**业务承诺**，不是描述**当前分布**——这条区分必须在契约里显式存在（`baseline.method` 与 `owner` 就是为此存在）。

### 2.4 实体解析与身份对齐

**成熟度。** 算法成熟（Fellegi-Sunter 几十年），工程化 M2，**治理**（合并/拆分/证据/撤销）M1。

**可复用件与接口。**
- `【事实】` Splink：blocking rules 决定候选对数量，`【事实】` 官方给的量级是 100 万条记录全量两两比较约 5000 亿对，因此必须用多条"紧"规则取并集；文档还提供 `count_comparisons_from_blocking_rules` 与 `n_largest_blocks` 做定量分析。`【事实】` Splink 5 已发布。
- `【事实】` Zingg：以 identity graph / Zingg ID 组织实体，文档区分 phases 与 incremental matching、跨数据集 link。
- `【事实】` Senzing：定位为 entity resolution（"resolve, not just match"）而非模糊匹配。
- 商业 MDM（Informatica/SAP/Stibo 等）：主数据生命周期、golden record、工作流——`【推断】` 这些产品的真正价值不在匹配算法，而在合并审批与拆分流程。

**输入输出契约（建议）。**

```yaml
# 输入
entity_type: customer
records: {source_versions: [...], fields: [...]}
match_model:
  blocking: [{rule: "normalize(name) + postcode[0:3]", est_pairs}]
  comparisons: [{field, method: exact|jaro|levenshtein|numeric_diff, levels: [...]}]
  thresholds: {auto_link: 0.95, review_band: [0.80, 0.95], auto_reject: 0.60}
policy: {merge_mode: proposal_only|auto_with_audit, reversible: true, retention_days}
# 输出
resolution:
  cluster_id, members: [{source, record_id}],
  match_probability, match_weight, evidence: [{field, level, contribution}],
  action: linked|merged|queued_for_review|rejected,
  merge_proposal: {golden_record, field_provenance, conflicts},
  split_candidates: [...], audit_ref
```

**agent 化改造点。**
1. A1：agent 生成 blocking 规则与 comparison levels（Splink settings 是 JSON，天然可生成），并用 `count_comparisons` 预估候选对数量——这是少见的"生成即可验证"的域。
2. A2：需要"合并影响面预演"——这条合并会改动多少下游 FK、多少报表维度、多少已发出的对账单。当前没有任何开源工具输出这个。
3. A3（最缺）：默认 `proposal_only`，合并要人批；必须有 split（拆回）路径与证据保留。`【推断】` Zingg/Splink 输出 cluster，Senzing 输出 resolved entity，但"合并错了怎么拆"是产品能力，不是算法能力。
4. LLM 做实体解析的边界：**适合**生成归一化规则、判断"这两个名称是否指向同一实体"的候选、解释冲突；**不适合**作为唯一判定器（不可复现、阈值不可校准、无法给出可审计的 match_weight）。合理架构是 LLM 产候选 + 规则/统计模型打分 + 人审临界带。

**最容易低估的难点。** 合并是**不可逆的语义操作**，而 ER 工具的评测指标（pairwise precision/recall）完全不反映这一点。一次误合并会把两个法人的合同、发票、信用额度挂到同一 `customer_id` 上；三个月后拆分需要重建 ID 映射，而下游 200 张报表已按旧 ID 固化，拆分成本远大于收益。所以 ER 的输出单位不是"对/错"，而是"**可撤销的决策 + 证据**"。

### 2.5 目录、血缘与元数据

**成熟度。** 模型与规范成熟（M2–M3），**覆盖率**普遍被高估（M1–M2）。

**可复用件与接口。**
- `【事实】` OpenLineage：以 RunEvent 描述 run/job/dataset，用 facet 扩展；column-level lineage 是 dataset facet 的一种，示例事件里带 `columnLineage` 与 `inputFields`。
- `【事实】` DataHub：实体 = 类型（如 dataset）+ URN + 一组 aspect（每个 aspect 描述一个 facet）。
- `【事实】` OpenMetadata：产品面覆盖 Discovery / Lineage / Observability / Data Contract / Governance。
- `【事实】` Unity Catalog：提供 REST API、UC Delta API，官方客户端覆盖 Python/Spark/DuckDB/Polars，元数据可落 PostgreSQL。
- `【事实】` Iceberg REST Catalog 规范：支持 credential vending 与 remote signing，可用于跨引擎共享表。

**输入输出契约（建议）。**

```yaml
# 输入
scope: {catalogs: [...], include_columns: true, emit_points: [dbt, airflow, spark, sqlmesh]}
ownership_map: {team_pattern -> owner}
glossary_candidates: [{term, definition, synonyms, source_refs}]
# 输出
metadata_snapshot:
  entities: [{urn, type, aspects: {schema, ownership, tags, glossary_terms}}],
  lineage_edges: [{from_urn, to_urn, column_map: [{from, to}], job_run_ref, confidence: parsed|declared|inferred}],
  coverage: {tables_total, tables_with_owner, tables_with_lineage, columns_with_lineage, emit_gap: [...]}
```

**agent 化改造点。**
1. A0：agent 应把 **coverage** 当一等对象读，而不是假设"有 DataHub 就有血缘"。
2. A1：agent 可以产出 glossary 候选、owner 建议、tag 建议——这些是低风险高价值的写入。
3. A2：lineage 的"置信度"必须可见（解析得到 / 声明得到 / 推断得到）。`【事实】` SQLMesh 关闭 optimizer 或用 `select *` 会让列级血缘失效，说明 lineage 是**解析产物**，会静默降级。
4. A3：元数据写入要审计；agent 不能因为"看到一次 join"就把关系发布为事实（与 DA06 的边界一致）。

**最容易低估的难点。** 血缘的完整性依赖**每个作业主动 emit**，这是一个组织问题而非技术问题。`【推断】` 典型企业里 60–80% 的表有表级血缘、只有 20–40% 有列级血缘；剩下的部分不会报错，只会让 agent 的影响面分析悄悄漏掉下游。更糟的是动态 SQL、存储过程、UDF、`insert overwrite` 之后的重命名——解析器会给出"看起来合理但错误"的边。因此影响面分析必须输出"未覆盖清单"，而不是一个自信的下游列表。

### 2.6 数据可观测性

**成熟度。** 商业产品成熟（M2），开放接口弱（M1），与"质量规则"的边界在实践中经常混在一起。

**可复用件与接口。**
- `【事实】` Monte Carlo：table monitor 对 freshness / volume / schema change 做"宽覆盖、低配置"的异常检测，**只做异常检测、没有用户自定义阈值**，靠 `sensitivity` 控制；其 YAML 配置即 "Monitors as Code"；另有 field lineage 与 PII 检测能力。
- `【事实】` Metaplane：持续采集 metrics / metadata / lineage / logs，在历史值上训练异常检测模型，对离群点告警。
- `【事实】` Elementary：dbt 原生，OSS 侧有 anomaly detection tests，Cloud 侧直连仓库做监控。
- 无开放告警标准：`【推断】` 事件侧只能靠 OpenLineage + 自建 incident schema，告警语义（severity/blast radius）各厂商私有。

**输入输出契约（建议）。**

```yaml
# 输入
monitored: [{asset, checks: [freshness, volume, schema, distribution], sensitivity: low|med|high}]
baseline: {window_days, seasonality: none|weekly|monthly}
alerting: {route, dedupe_key, expected_alerts_per_week}   # 用"预期告警量"代替阈值
# 输出
incident:
  incident_id, asset, check_type, detected_at, window,
  severity, deviation, baseline_ref,
  blast_radius: [{downstream_asset, hop, materialized, owner}],
  suspected_cause: {kind: upstream_delay|schema_change|backfill|source_anomaly, evidence_ref},
  coverage_gap: [...]   # 影响面里没血缘覆盖的部分
```

**agent 化改造点。**
1. A1：agent 生成 monitor 配置很容易（MaC 是 YAML），难的是**敏感度**——它不可解释、没有单位。
2. A2：人审的正确对象不是 `sensitivity: high`，而是"过去 90 天这套配置会产生多少条告警、其中多少条会被忽略"。这是 agent 必须补的预演输出。
3. A3：incident 要能回写到质量规则（"这次异常应该沉淀为断言"），否则可观测与质量是两套孤岛。
4. 影响面分析要区分"物化下游"（报表已固化，必须重算）与"逻辑下游"（只是可能被查）。

**最容易低估的难点。** 告警疲劳、基线漂移、影响面漏算三件事会互相掩护：告警太多 → 团队调低敏感度 → 真实事故被压掉；基线随业务增长自然上移 → 异常检测把"新常态"当正常；血缘不全 → 影响面看起来很小 → 事故被判定为局部。三者叠加的结果是"系统一直在报警，但没人认为它在工作"。

### 2.7 权限与合规

**成熟度。** 仓库内成熟（M2），跨副本/跨上下文 M0–M1。这是 8 类里**工具最成熟、agent 就绪度最低**的一类。

**可复用件与接口。**
- `【事实】` BigQuery：column-level access control 通过 policy tag 实现（依赖 Dataplex 分类）。
- `【事实】` Snowflake：column-level security 用 masking policy（Enterprise Edition 起）、row-level 用 row access policy（schema 级对象，按角色/映射决定行可见性）。
- `【事实】` Iceberg REST：credential vending / remote signing，把存储凭证按表下发。
- `【事实】` GDPR Art.17：数据主体可要求"无不当延迟"地删除个人数据，控制者有对应删除义务。
- `【事实】` 个保法第 47 条：处理目的已实现/无法实现/不再必要、停止提供服务或保存期限届满等情形，处理者应主动删除；未删除的个人有权请求删除。第 38 条：跨境需通过安全评估、专业机构认证、标准合同等条件之一；第 39 条：跨境须告知境外接收方名称/联系方式/目的/方式/种类/行权方式，并取得**单独同意**。

**输入输出契约（建议）。**

```yaml
# 输入
principal: {user, tenant, roles, purpose: analytics|support|model_training}
classification: {policy_tags: [...], pii_types: [phone, id_card], jurisdiction: CN|EU}
obligations: {retention_days, deletion_request_ref, cross_border: {allowed, mechanism}}
# 输出
effective_policy:
  row_filter, column_masks: [{column, mask: hash|redact|tokenize|generalize}],
  allowed_purposes, export: {max_rows, watermark, require_approval},
  propagation: {derived_assets: [{asset, inherits: policy_id}], cache_ttl, index_policy}
decision: allow|deny|mask|aggregate_only
audit: {decision_id, policy_version, evaluated_at, reason}
```

**agent 化改造点。**
1. A0：agent 需要能问"我能看哪些列/哪些行/为什么"，而不只是拿到一个 403。
2. A1：agent 生成查询时就要带 purpose 与 classification，而不是查询后过滤。
3. A2（真缺口）：**派生副本的预演**——这次采样/建索引/写缓存会让哪些数据离开原策略域？当前没有工具能回答。
4. A3：导出、跨境、删除权必须有独立审批与凭证；删除权还要能生成"删除证明"（覆盖备份、派生表、索引、模型训练集）。

**最容易低估的难点。** 权限在**派生层**失效，而入口检查全部通过。具体路径：agent 为提速把 `customers` 采样 10 万行写入向量索引，采样时正确应用了 `region='CN'`，但索引只存 `text + id`；检索时按相似度返回了跨区客户摘要。或者：LLM 上下文中带了未脱敏手机号，被写进 trace 与缓存。根因是把权限当 API gateway 的 RBAC，而不是**沿数据血缘传播的 label**。`【推断】` 这也是"LLM 上下文边界"目前无法用现成产品解决的唯一环节：policy tag 能保护表和列，保护不了 prompt、trace、embedding 和临时文件。

### 2.8 调度与编排

**成熟度。** 工具 M3，数据语义 M2；agent 生成 DAG 的"幂等性证明"完全缺失。

**可复用件与接口。**
- `【事实】` Airflow 3.3.2 提供 Asset-Aware Scheduling（由 asset 事件触发 DAG，替代纯时间驱动）。
- `【事实】` Dagster 以 `@dg.asset` 定义资产，partition 是管理大数据集与增量的核心概念。
- `【事实】` Temporal：Workflow Definition 定义步骤、Workflow Execution 执行；Activity 有 Schedule-To-Start / Start-To-Close / Schedule-To-Close 三种超时与 Activity Heartbeats，用于检测卡死与实现及时取消。
- `【推断】` 对 DataAgent 最有价值的不是"定时跑"，而是"asset 有新分区 → 触发下游 → 失败只重算该分区"。

**输入输出契约（建议）。**

```yaml
# 输入
graph: {assets: [...], deps: [...], partitions: {kind: time|static|dynamic, granularity}}
trigger: {kind: schedule|asset|event, cron?, upstream_assets?, freshness_sla}
runtime: {idempotency_key: "{asset}:{partition}", retry: {max, backoff}, timeout, cancel_grace}
backfill: {range, concurrency, dry_run: true}
# 输出
run:
  run_id, asset, partition_range, state, attempts,
  heartbeat_at, idempotent: proven|assumed,
  outputs: [{asset_version, row_count}], lineage_events: [...],
  cancel: {requested_at, effective_at}
backfill_plan: {partitions, estimated_cost, conflicts: [{with: incremental_run, window}]}
```

**agent 化改造点。**
1. A1：agent 生成 DAG/asset 定义与 partition 映射。
2. A2：backfill **必须默认 dry-run**，输出分区清单、成本、以及与正在运行的增量任务的冲突窗口。SQLMesh 的 plan 已经证明这个交互可行。
3. A3：幂等性要能被"证明"而不是"假设"——最小可行做法是要求每个 asset 声明 `idempotency_key` 与写入模式（overwrite partition / merge on key / append），agent 生成时若无法确定就用 `append` 必须显式确认。
4. 长任务取消：`【事实】` Temporal 靠 heartbeat 检测卡死；`【推断】` 若 activity 不发送 heartbeat，取消会在下一个检查点才生效，期间可能已产生副作用（写表、发消息、扣款）。

**最容易低估的难点。** 回填与增量在同一条链上交错时，"重跑"不等于"幂等"。具体：修复上游后回填 90 天，若 merge 无唯一键或写入是 append，重复行使 GMV 翻倍；若回填与当日增量并发，同一分区被两个 run 写，最后写入者胜出，结果依赖调度时序。这类错误在监控上表现为"数据量正常、指标偏高"，最难归因。

---

## 3. "扩展 vs 补充"判定

### 3.1 判定标准

不看功能名，看三条：

| 判据 | 狭义 | 广义 | 判定含义 |
| --- | --- | --- | --- |
| 触发者 | 人提问/人点按钮 | agent 提议 + 人批准（或策略自动） | 需要 A2/A3 层，通常是"扩展 + 补层" |
| 时间跨度 | 任务内、一次性 | 跨任务、跨版本、跨租户 | 状态与版本成为新对象，倾向"新模块" |
| 失败代价 | 答案错，可重答 | 资产错，被复用并扩散 | 需要不可逆防护，倾向"新模块" |

三者中占两项以上"广义"，就不能塞进狭义模块的二级能力，必须单列。

### 3.2 逐条判定

| 能力 | 判定 | 对应模块 | 理由 |
| --- | --- | --- | --- |
| 接入与同步 | **扩展**（边界显著变大） | DA01 | 狭义的 DA01 已有"连接器 / 快照与截至时间 / 读取契约"；广义把"读一次"变成"持续同步 + schema evolution + 软删除 + as-of 回溯"。对象没变（源→任务空间），时间跨度和状态机变了。 |
| 探查与画像 | **扩展** | DA02 | 狭义是任务内探查；广义是持续 profile + 漂移基线。同一套统计，多了时间轴与基线管理。 |
| 数据质量 | **扩展** | DA03 | 狭义只校验"本次结果"；广义是规则资产生命周期（生成→审阅→退役）+ 归因 + 修复复核 + 影响面。归属不变，深度变化。 |
| 实体解析 / MDM | **扩展但需新建子模块**（能力层面是新建） | DA04 | 模块表上 DA04 已含"稳定身份与主数据对齐"；但狭义产品里不存在 blocking/阈值/合并-拆分/证据链/MDM 工作流。**模块层面算扩展，实现层面等于新建**——报告必须写清这个区别，否则会被读成"DA04 已经规划过了"。 |
| 语义层 | **扩展** | DA05 | 狭义是"复用或临时定义"，广义是版本化发布；已有 draft→published 状态机可延伸。 |
| 建模与转换（dbt/SQLMesh/湖仓物化） | **新模块** | 建议 DA13 | 狭义完全没有"物理模型 + 物化策略 + 契约 + 回填"这一层。DA05 只管"口径怎么定义"，不管"在哪张表、什么分区、怎么增量、改了要不要回填"。 |
| 目录 / 血缘 / 元数据 | **新模块** | 建议 DA14 | 狭义假设"已有语义库"，因此不需要自己维护 catalog、ownership、glossary、column-level lineage。广义要"构造并维护可复用语义"，血缘是它的前置事实。 |
| 数据可观测性 | **新模块** | 建议 DA15 | 狭义没有"持续监测无规则异常"的概念；DA03 是规则（有预期值），可观测是无规则（只有基线）。两者的失败模式、告警语义、影响面分析都不同，合并会互相污染。 |
| 权限与合规 | **扩展 + 新增合规章节** | DA11（+ 合规子模块） | 狭义已有"权限、脱敏与外发治理"；广义要把它变成沿血缘传播的 policy，并新增删除权、跨境、单独同意等**法定流程**——后者不是权限系统的能力，是合规工作流。 |
| 调度与编排 | **新模块** | 建议 DA16 | 狭义由 AgentOS 的"事件、队列、重试与取消"承载（见草案第四节），但那是**运行时**，不是**asset-centric 编排**。分区、回填、幂等、依赖图属于数据领域，AgentOS 不应重造。 |
| 反馈、评测与资产演进 | **扩展** | DA12 | 狭义的会话反馈延伸为"质量/血缘/ER 的回归集与漂移监测"，是同一模块的规模变化。 |

### 3.3 结论

- **4 个真新增模块**：DA13 建模与转换、DA14 目录血缘、DA15 可观测、DA16 调度编排。它们不是"DA01–DA12 没做好"，而是狭义假设里根本不存在（已有库、已有语义、单次任务）。
- **1 个"模块表算扩展、实现算新建"**：DA04 的实体解析/MDM。这是最容易被误读为"已覆盖"的坑。
- **5 个扩展**：DA01、DA02、DA03、DA05、DA11、DA12（DA11 另加合规章节）。
- **对 AgentOS 的边界含义**：DA16 与草案第四节"AgentOS 提供事件/队列/重试/取消"并不冲突——AgentOS 提供**执行原语**，DA16 提供**数据资产的编排语义**（分区、回填、幂等键、依赖图）。同理 DA11 的合规工作流复用 AgentOS 的审批与审计，但 policy 传播逻辑属于 DataAgent。

---

## 4. 三个最容易被低估的难点

### 4.1 实体解析：合并是不可逆的语义操作

**为什么被低估**：ER 的评测指标是 pairwise precision/recall，看起来像分类问题；工具也都输出"cluster + 概率"，让人以为错了可以重跑。

**失败场景**：营销库和财务库各有 "Acme"，agent 用 `normalize(name)+postcode` 做 blocking，阈值 0.95 自动合并。实际是母公司与子公司两个法人。合并后 `customer_id` 统一，历史发票、合同、授信额度挂到同一实体；三个月后财务对账发现异常，需要拆分——但 200+ 张报表已按旧 cluster_id 做维度固化，拆分要重建 ID 映射并回刷全部历史分区。团队最终选择"不改"，错误永久固化。

**正确做法**：默认 `proposal_only`；合并必须带 field-level provenance 与冲突清单；cluster 之上保留"引用层"（golden record 可换，引用不变）；任何 auto-link 都要有拆分脚本与影响面预演。ER 的输出不是"谁和谁是同一个"，而是"**这个判断的证据、代价和撤销方式**"。

### 4.2 schema evolution × 回填 × 幂等：三个正确配置组合出错误结果

**为什么被低估**：每一项单独看都有成熟方案——evolve 策略、backfill 命令、merge 写入。问题在于它们在同一个 DAG 里耦合，且失败是**静默**的。

**失败场景**：上游把 `amount` 从 `decimal(10,2)` 改成带货币符号的字符串。接入层按 `evolve` 新建列、旧列写 NULL；dbt 层该 staging 表没有 contract（contract 只加在 mart 上）；质量规则是 `not_null(amount)`，NULL 行被过滤掉所以"通过"；指标 `sum(amount)` 下降 30%，但报表显示"数据正常、口径未变"。修复后回填 90 天，写入模式是 append 且无唯一键，重复行让 GMV 翻倍——此时监控显示"数据量增长"，被当成业务增长。

**正确做法**：把 schema 变更当作**跨层事件**而非接入层配置：变更必须同时触发（a）接入层 drop/narrow 显式上报，（b）建模层 contract 覆盖到 staging，（c）质量规则区分"值缺失"与"列消失"，（d）回填前做幂等性检查（写入模式 + 唯一键 + 分区覆盖）。回填默认 dry-run，并检测与增量 run 的时间窗冲突。

### 4.3 权限：在派生副本与 LLM 上下文处失效

**为什么被低估**：仓库内的 row/column 权限做得很好（policy tag、masking policy、row access policy 都是成熟产品能力），于是团队认为"权限已经解决"。但 DataAgent 的每一层加速手段——采样、索引、缓存、向量化、trace——都在**复制数据**。

**失败场景**：为降低延迟，agent 把 `customers` 采样 10 万行写入向量索引，采样时正确应用 `region='CN'`。但索引只存 `text + id`，检索按相似度跨区返回客户摘要；另一条路径上，排查问题时把含手机号的查询结果写进 trace 与 prompt 缓存，而 trace 的访问权限是"工程团队全员"。两条路径的入口检查都通过，泄露发生在派生层。

**正确做法**：权限必须作为 label 沿血缘传播到每个派生副本（索引、缓存、物化视图、训练集、trace），并在**读取派生对象时**重新求值，而不是在写入时求值一次。工程上最小可行：给每个派生资产打 `policy_id + purpose + expires_at`，检索/导出/入模三个出口强制校验；LLM 上下文单独定义"可进入 prompt 的字段白名单"，trace 按同一策略脱敏。

---

## 5. 可直接引用的结论

1. **8 类里 4 类是新模块，不是扩展。** 建模与转换、目录与血缘、可观测、调度编排在狭义假设（已有库、已有语义、单次任务）下根本不存在，必须在模块表新增 DA13–DA16；把它们塞进 DA01–DA12 会让"狭义能力扩展"和"广义新建"两件事混为一谈。
2. **DA04 是"模块表算扩展、实现算新建"的陷阱。** 草案已写"稳定身份与主数据对齐"，但 blocking/阈值/合并-拆分/证据链/MDM 工作流在狭义产品里没有任何实现基础，工作量应按新模块估算。
3. **8 类能力缺的是同一层：可审阅的变更计划（plan/diff/dry-run）。** 所有工具都能生成声明式配置（A1 普遍可做），但只有建模域（SQLMesh plan、dbt contract preflight）把"改了什么、属于哪类变更、要回填多少、大概多少钱"做成了机器可读输出。这是"agent 生成 + 人审核"能否成为接口而非话术的分水岭。
4. **两类能力做错了不可逆：实体解析与权限。** 前者合并后无法拆回，后者在采样/索引/缓存/LLM 上下文处静默泄露。二者的默认值必须是"提案 + 证据 + 可撤销"，自动执行只能是例外并带审计。
5. **血缘与可观测的覆盖率必须作为一等指标暴露给 agent。** OpenLineage 需要每个作业主动 emit，列级血缘依赖 SQL 解析（`select *`/关闭 optimizer 即失效），所以影响面分析必须同时输出"未覆盖清单"，否则 agent 会给出自信但漏项的结论。

---

## 6. 引用清单（访问日期均为 2026-11-01）

| # | 主题 | URL | 类型 | 支撑的判断 |
| --- | --- | --- | --- | --- |
| 1 | Airbyte Protocol | https://docs.airbyte.com/understanding-airbyte/airbyte-protocol | 官方文档 | actor/catalog/stream/field 原语；STDIO 与 Socket 双通道 |
| 2 | Airbyte Sync Modes | https://docs.airbyte.com/platform/using-airbyte/core-concepts/sync-modes | 官方文档 | incremental(cursor/CDC) × overwrite/append/deduped 组合 |
| 3 | Fivetran Sync Overview | https://fivetran.com/docs/core-concepts/syncoverview | 官方文档 | initial→incremental、cursor、re-sync、rollback sync、默认 6 小时 |
| 4 | dlt Incremental Loading | https://dlthub.com/docs/general-usage/incremental-loading | 官方文档 | merge 策略（delete-insert/scd2/upsert/insert-only/cdc）、cursor、lag 窗口 |
| 5 | dlt Schema Contract | https://dlthub.com/docs/general-usage/schema-contracts | 官方文档 | evolve/freeze/discard_value；tables/columns/data_type 三级 |
| 6 | Debezium PostgreSQL | https://debezium.io/documentation/reference/stable/connectors/postgresql.html | 官方文档 | snapshot.mode、ad-hoc/blocking/incremental snapshot、信令表；快照期间不支持 schema change |
| 7 | Iceberg Spec | https://iceberg.apache.org/spec/ | 规范 | snapshot/sequence number/refs(branch,tag)/equality & position delete/deletion vector |
| 8 | Iceberg Spark Queries | https://iceberg.apache.org/docs/latest/spark-queries/ | 官方文档 | 时间旅行/as-of 读取 |
| 9 | Iceberg REST Catalog Spec | https://iceberg.apache.org/rest-catalog-spec/ | 规范 | credential vending / remote signing |
| 10 | Delta Batch | https://docs.delta.io/latest/delta-batch.html | 官方文档 | time travel |
| 11 | Delta Change Data Feed | https://docs.delta.io/latest/delta-change-data-feed.html | 官方文档 | 跨版本行级变更 |
| 12 | Delta Protocol | https://github.com/delta-io/delta/blob/master/PROTOCOL.md | 规范 | 事务日志与协议版本 |
| 13 | Hudi Querying | https://hudi.apache.org/docs/querying_data/ | 官方文档 | snapshot / incremental 查询（beginInstantTime） |
| 14 | dbt Model Contracts | https://docs.getdbt.com/docs/collaborate/govern/model-contracts | 官方文档 | enforced contract、preflight、breaking change 定义、contract 与 tests 分工 |
| 15 | dbt Model Versions | https://docs.getdbt.com/docs/collaborate/govern/model-versions | 官方文档 | latest_version / deprecation_date |
| 16 | dbt Data Tests | https://docs.getdbt.com/docs/build/tests | 官方文档 | generic/singular tests、store_failures |
| 17 | SQLMesh Plans | https://sqlmesh.readthedocs.io/en/stable/concepts/plans/ | 官方文档 | breaking/non-breaking/forward-only、回填、virtual env、destructive 默认 error |
| 18 | SQLMesh Models | https://sqlmesh.readthedocs.io/en/stable/concepts/models/overview/ | 官方文档 | column-level lineage 依赖 optimizer/列限定 |
| 19 | Great Expectations Overview | https://docs.greatexpectations.io/docs/core/introduction/gx_overview | 官方文档 | Expectation Suite / Checkpoint / Actions |
| 20 | SodaCL Overview | https://docs.soda.io/soda-cl/soda-cl-overview.html | 官方文档 | SodaCL 声明式 check（v3） |
| 21 | Deequ | https://github.com/awslabs/deequ | 开源仓库 | VerificationSuite/Check、DQDL、异常检测、约束建议、metrics repository |
| 22 | Splink Blocking Rules | https://moj-analytical-services.github.io/splink/topic_guides/blocking/blocking_rules.html | 官方文档 | 100 万记录≈5000 亿对、blocking 规则并集、候选对数量分析；Splink 5 |
| 23 | Splink Comparisons | https://moj-analytical-services.github.io/splink/topic_guides/comparisons/customising_comparisons.html | 官方文档 | comparison levels 自定义 |
| 24 | Zingg Docs | https://docs.zingg.ai/ | 官方文档 | identity graph、Zingg ID、phases、incremental matching |
| 25 | Senzing（ER 概念） | https://senzing.com/what-is-entity-resolution/ | 厂商文档 | "resolve, not just match" 的定位 |
| 26 | DataHub Metadata Model | https://docs.datahub.com/docs/metadata-modeling/metadata-model | 官方文档 | entity type + URN + aspects |
| 27 | DataHub GraphQL | https://docs.datahub.com/docs/api/graphql/overview | 官方文档 | 元数据读写 API |
| 28 | OpenLineage Object Model | https://openlineage.io/docs/spec/object-model | 规范 | RunEvent / job / dataset / facet |
| 29 | OpenLineage Column Lineage Facet | https://openlineage.io/docs/spec/facets/dataset-facets/column_lineage_facet | 规范 | columnLineage / inputFields |
| 30 | OpenMetadata | https://docs.open-metadata.org/latest | 官方文档 | Discovery/Lineage/Observability/Data Contract/Governance |
| 31 | Unity Catalog | https://docs.unitycatalog.io/ | 官方文档 | REST API、UC Delta API、多语言客户端 |
| 32 | Monte Carlo Monitors | https://docs.getmontecarlo.com/docs/monitors-overview.md | 官方文档 | 监控类型与"metadata 优先、低计算成本"策略 |
| 33 | Monte Carlo Table Monitor | https://docs.getmontecarlo.com/docs/table.md | 官方文档 | freshness/volume/schema 异常检测、无阈值只有 sensitivity、MaC YAML |
| 34 | Monte Carlo Field Lineage | https://docs.getmontecarlo.com/docs/field-lineage.md | 官方文档 | 列级血缘 |
| 35 | Elementary | https://docs.elementary-data.com/ | 官方文档 | dbt 原生监控 + anomaly detection tests |
| 36 | Metaplane | https://docs.metaplane.dev/ | 官方文档 | metrics/metadata/lineage/logs + 历史异常模型 |
| 37 | Airflow Asset-Aware Scheduling | https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/asset-scheduling.html | 官方文档 | Airflow 3.3.2 asset 触发 |
| 38 | Dagster Assets | https://docs.dagster.io/guides/build/assets/defining-assets | 官方文档 | @dg.asset 资产定义 |
| 39 | Dagster Partitioning | https://docs.dagster.io/guides/build/partitions-and-backfills/partitioning-assets | 官方文档 | partition 作为增量与回填单位 |
| 40 | Temporal Workflows | https://docs.temporal.io/workflows | 官方文档 | Workflow Definition / Execution |
| 41 | Temporal Activity Failure Detection | https://docs.temporal.io/encyclopedia/detecting-activity-failures | 官方文档 | Schedule-To-Start/Start-To-Close/Schedule-To-Close 超时、heartbeat |
| 42 | GDPR Art.17 | https://gdpr-info.eu/art-17-gdpr/ | 法规 | 无不当延迟删除义务 |
| 43 | 个保法（全国人大） | http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html | 法规 | 第 47 条删除、第 38 条跨境条件、第 39 条单独同意与告知 |
| 44 | BigQuery Column-Level Access Control | https://cloud.google.com/bigquery/docs/column-level-security | 官方文档 | policy tag 实现列级访问控制 |
| 45 | BigQuery Data Masking | https://cloud.google.com/bigquery/docs/column-data-masking | 官方文档 | 动态脱敏 |
| 46 | Snowflake Column-Level Security | https://docs.snowflake.com/en/user-guide/security-column-intro | 官方文档 | masking policy、Enterprise Edition |
| 47 | Snowflake Row Access Policies | https://docs.snowflake.com/en/user-guide/security-row-intro | 官方文档 | 行级访问策略 |
| 48 | DataAgent 模块能力草案（内部） | ../../docs/research/dataagent-2026-11-01/00-module-capability-draft.md | 内部文档 | DA01–DA12 编号与狭义/广义边界 |

## 7. 未验证与已知缺口

以下内容本文**没有**拿到一手证据，报告中若引用需标注为推断或补验：

1. **Iceberg REST 的具体端点与方法**（`/v1/config`、namespaces 路径等）：抓取页面为前端渲染，正文未包含端点表。本文只引用了安全机制（credential vending / remote signing）。
2. **Kafka Connect 的 SMT/Converter 契约**：本文以 Debezium 文档代替，未单独抓 Kafka 官方 Connect 章节。
3. **Fivetran 的 schema change / history mode 专页**：目标 URL 返回 404，本文只使用 Sync Overview 中可验证的事实（re-sync、cursor、rollback sync、去重）。
4. **Hudi 的 COW/MOR 表类型与 timeline 细节**：只验证了 snapshot/incremental 查询，表类型未抓原文。
5. **Splink 的 m/u 概率与 term frequency 调整**：抓取页面聚焦 blocking，未直接引用 m/u 定义；本文凡涉及 FS 模型细节处均已避免断言。
6. **Senzing 引擎架构与打分机制**：仅引用其 ER 定位，未验证 API 细节。
7. **各厂商"列级血缘覆盖率"数字**：本文给出的 60–80% / 20–40% 为经验推断，无公开统计支撑，报告中应改为定性表述。
8. **Monte Carlo 的 blast radius / 影响面分析具体实现**：仅验证了 field lineage 与 monitor 类型，未抓影响面文档。
