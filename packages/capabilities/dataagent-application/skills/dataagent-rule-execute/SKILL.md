---
name: dataagent-rule-execute
description: 用 DataAgent 应用层的判定族原子，把规则定义编译为封闭算子表达式并求值，输出带证据的 Assessment。涉及 DA06.3.5、DA07.5.1、DA07.5.2、DA07.10.1 时使用。
---

# DataAgent 规则执行（判定族）

判定族负责"规则 → 表达式 → 三值求值"。缺失值永远是 `unknown`，不会折算成 `violated`。

## 两段式协议（强制）

1. **先不带 `proposal` 调用 `generate_function_expressions`。** 返回 `needs_input`，`issues[].inference_request` 给出条件、锚点、封闭算子集与 AST 形状。
2. **只在候选范围内生成 AST。** 每个叶子带 `condition_id` 来源。工具会确定性校验：
   - 算子必须在封闭集合内（`and/or/not`、`eq/ne/lt/le/gt/ge`、`add/sub/mul/div`、`in`、`between`、`is_missing`、`date_diff`、`string_match`）；出现其它算子直接拒绝；
   - 叶子字段必须在 `fields[]` 内；编造字段、编造 condition_id 一律拒绝；
   - 未覆盖且未声明不支持的条件会导致拒绝；表达不了的条件放进 `unsupported_conditions`，由 DA03.15 人工判定；
   - 例外子句建议编译为 `exceptions[]` 表达式：命中 → `not_applicable`，未知 → `unknown`。

## 求值

- `evaluate_scalar_expression`：对单条 `ExtractedRecordRef`；输出 `Assessment`（verdict：`satisfied/violated/unknown/not_applicable`），`evidence` 列出参与运算的字段值与锚点。
- `evaluate_table_expression`：对 `TableRef` 逐行；合计/小计行不参与（避免重复计数）；混合结果 verdict 为 `unknown`（fail-closed）。
- `acquire_and_align_engine`：执行前对齐解释器/DuckDB 版本；不一致返回 `da07.engine_version_mismatch`。

## 反例（务必自测）

- 缺失字段参与比较 → `unknown`，不是 `false`；
- `is_missing` 对缺失字段 → `satisfied`（可判定的检查）；
- 字符串字段与数字字面量比较 → `da07.expression_type_mismatch`。
