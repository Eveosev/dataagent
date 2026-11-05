---
name: dataagent-compute-plan
description: 用 DataAgent 应用层的计算族原子，把需求绑定成 RequirementSpec、识别并澄清歧义、生成单表 SQL 并在本地 DuckDB 执行，产出 ComputedResult 与交付物。涉及 DA06.1.1–1.4、DA06.3.1、DA07.1.3、DA10.1.1、DA10.3.1、DA10.3.3 时使用。
---

# DataAgent 计算计划与执行（计算族）

计算族负责"先把口径问清楚，再算，再交付"。不要跳过歧义澄清直接算数。

## 两段式协议（强制）

`bind_metrics_and_dimensions`、`parse_time_and_filters`、`identify_calculation_ambiguities`、`generate_clarification_questions`、`generate_single_table_sql` 第一次调用不带 `proposal`，读 `issues[].inference_request` 里的候选（指标 id、维度字段、时间语义、表 schema、SQL 约束），再回带 `proposal`。工具会确定性校验：

- 编造的指标 id、维度字段、过滤字段、表名一律拒绝（`invalid_input`）；
- 时间边界必须可解析（ISO-8601），`from` 不得晚于 `to`；
- SQL：单条 `SELECT`（CTE 允许）、只许引用绑定表、`read_*`/`COPY`/`ATTACH`/`INSTALL` 等黑名单函数全部拒绝；
- blocking 歧义未澄清前，`generate_clarification_questions` 返回 `needs_input`，`alternatives` 列候选及依据；非阻塞歧义进 `assumptions[]` 并在报告中列出。

## 执行与交付

1. `acquire_and_align_engine`：先对齐 DuckDB 版本；
2. `execute_duckdb_sql`：合计/小计行不载入（避免重复求和）；预算行数/超时来自 `Budget`；输出 `ComputedResult`（SQL digest、`EngineBinding`、口径版本）；
3. `build_result_workbook`：openpyxl 只写值，三张表（结果、口径与来源、假设与未覆盖）；
4. `compose_document_report` + `export_report_format`：报告带逐条依据（`EvidenceRef` → 原文锚点）与不可判定项；导出 `md`/`html`/`docx`（docx 需可选依赖组）；**导出不等于发布**。

## 反例（务必自测）

- `SELECT 1; SELECT 2`、引用未绑定表、`read_csv(...)`、`ATTACH` 均被拒绝；
- 超行数预算 → `partial` + `Completeness=truncated`，不得静默截断。
