# dataagent-application

DataAgent 应用层（[07 执行应用层能力建设方案](../../../../docs/research/dataagent-2026-11-03/07-application-layer-build-plan.md)）的 S0 实现：13 个原子。

## 范围（S0）

| 族 | 原子 | operation |
|-|-|-|
| 骨干 | DA06.3.5 函数调用与表达式生成 | `generate_function_expressions` |
| 骨干 | DA07.5.1 标量表达式计算 | `evaluate_scalar_expression` |
| 骨干 | DA07.5.2 表数据表达式计算 | `evaluate_table_expression` |
| 骨干 | DA07.10.1 引擎获取与版本对齐 | `acquire_and_align_engine` |
| 骨干 | DA10.3.1 文档报告生成 | `compose_document_report` |
| 骨干 | DA10.3.3 报告格式导出 | `export_report_format` |
| 计算族 | DA06.1.1 指标与维度绑定 | `bind_metrics_and_dimensions` |
| 计算族 | DA06.1.2 时间与过滤解析 | `parse_time_and_filters` |
| 计算族 | DA06.1.3 计算歧义识别 | `identify_calculation_ambiguities` |
| 计算族 | DA06.1.4 澄清问题生成 | `generate_clarification_questions` |
| 计算族 | DA06.3.1 单表 SQL 生成 | `generate_single_table_sql` |
| 计算族 | DA07.1.3 本地 DuckDB 执行适配 | `execute_duckdb_sql` |
| 计算族 | DA10.1.1 结果工作簿生成 | `build_result_workbook` |

依赖：`dataagent-contracts`、`dataagent-runtime`（含共享表编解码端口）；不导入 `dataagent_data`、`dataagent_governance`。

## 两段式协议

`DA06.1.1–1.4`、`DA06.3.1`、`DA06.3.5` 第一次调用（无 `proposal`）返回 `needs_input`，`issues[].inference_request` 携带候选与约束；第二次调用带 `proposal`，工具做确定性校验（编造的指标、维度、表名、字段、条件来源一律拒绝）。

## 表达式语义（07 §5.1）

- 封闭算子集：`and/or/not`、`eq/ne/lt/le/gt/ge`、`add/sub/mul/div`、`in`、`between`、`is_missing`、`date_diff`、`string_match`。
- 三值逻辑：缺失/冲突的 `FieldValue` 使子树为 `unknown`，不折算为 `false`；类型不符报 issue。
- 解释器实现，不用 `eval`；判定顺序：例外（命中 → `not_applicable`，未知 → `unknown`）→ 主表达式（`pass/fail/unknown`，core `Verdict` 词表；业务别名 `satisfied/violated` 由消费方映射）。

## SQL 语义（07 §5.2）

- sqlglot 校验：单条 `SELECT`（CTE 允许）、引用表 ⊆ 绑定表、函数黑名单（`read_*`、`COPY`、`ATTACH`、`INSTALL` 等）。
- DuckDB 进程内连接，`enable_external_access=false`；`TableRef` 经共享编解码端口载入为临时表；**合计/小计行不载入**，避免重复求和；预算行数/超时来自 `Budget`。
- 输出 `ComputedResult`：SQL digest 与 `EngineBinding`（0.1.x 新增字段）。

## 引擎（07 §5.4）

S0 引擎为 DuckDB 与表达式解释器；版本比对失败返回 `failed`（`da07.engine_version_mismatch`）；不联网。

## 运行

```bash
uv run --frozen --project . python -m dataagent_application.interfaces.mcp_server
uv run --frozen --project . python -m dataagent_application.interfaces.cli --list
```

`DATAAGENT_DATA_ROOT` 指向共享数据根（默认 `.dataagent/`），与数据层、评测治理层共用内容寻址存储。
