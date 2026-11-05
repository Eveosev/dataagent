---
name: dataagent-s0-compute
description: DataAgent S0 计算族端到端链路：访问判定 → 接入 → 指标与规整 → SQL 执行 → 粒度与合并检查 → 验收 → 报告。用三个 bundle 完成指标计算交付时使用。
---

# 计算族端到端（S0 组合）

一次计算交付按固定顺序经过三层；每一步的输出是下一步的输入。

1. **访问判定（治理层）**：读取任何资源前先 `check_access_scope`，拿到
   `AccessDecision`；其 `decision_id` 作为后续调用的 `authorization_ref`。
2. **接入（数据层）**：`parse_delimited_file` / `parse_regular_excel` /
   `parse_json_records` 把源表解析为 `TableRef`。
3. **指标与规整（数据层 + 应用层）**：`profile_table_structure`、
   `infer_field_types`、`expand_merged_cells` 规整表；`define_metric_formula`
   两段式定义指标口径；`bind_metrics_and_dimensions` 绑定维度并生成
   `RequirementSpec`。
4. **SQL 执行（应用层）**：`generate_single_table_sql` 生成绑定指标固定过滤的
   SQL；`acquire_and_align_engine` 对齐引擎（版本不符 fail closed）；
   `execute_duckdb_sql` 执行，产出 `ComputedResult`。
5. **粒度与合并检查（治理层）**：`check_result_grain_and_merge` 校验粒度键
   唯一、Join 基数（右表重复键判 fail）与度量守恒，分页回执须完整。
6. **验收（治理层）**：判据两段式起草并确认；样本隔离冻结；
   `evaluate_business_acceptance` 只在未见样本上评测（容差按判据
   `tolerance_relative`）。
7. **报告（应用层）**：`build_result_workbook` / `compose_document_report` /
   `export_report_format` 交付结果与 `AcceptanceReport`。

## 规则

- 主体与用途取自 `CallContext`（可信宿主固定）；调用参数不能覆盖。
- 治理层以 `enforcement = enforce` 运行：读取输入资源前复检决策，不满足返回
  `da12.access_denied`；外发缺失或 `deny` 时内容被剥离（`da12.egress_required`）。
- SQL 必须绑定 `ExecutableSpec.engine_binding` 与指标固定过滤；换引擎或换
  度量列都会被拒绝。
- 度量守恒检查中源端 WHERE/HAVING 造成的差异记 `unknown`，不得判 `pass`。
