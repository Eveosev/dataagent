---
name: dataagent-s0-judgment
description: DataAgent S0 判定族端到端链路：访问判定 → 接入 → 抽取或规整 → 规则 → 判定 → 验收 → 报告。用三个 bundle 完成单条业务判定的完整交付时使用。
---

# 判定族端到端（S0 组合）

一次判定交付按固定顺序经过三层；每一步的输出是下一步的输入。

1. **访问判定（治理层）**：读取任何资源前先 `check_access_scope`（主体、资源、
   动作、用途），拿到 `AccessDecision`；其 `decision_id` 作为后续调用的
   `authorization_ref`。无匹配规则得 `indeterminate`，按拒绝处理。
2. **接入（数据层）**：`parse_delimited_file` / `parse_regular_excel` /
   `parse_text_pdf` 等把源文件解析为 `TableRef` 或 `DocumentRef`。
3. **抽取或规整（数据层）**：`detect_workbook_regions`、`recover_headers`、
   `classify_table_rows`、`expand_merged_cells`、`extract_fields_to_schema`、
   `anchor_extracted_values` 把源数据规整为结构化记录与锚点。
4. **规则（应用层）**：`bind_metrics_and_dimensions`、`generate_function_expressions`
   两段式生成可执行表达式；`acquire_and_align_engine` 对齐引擎版本。
5. **判定（应用层）**：`evaluate_scalar_expression` / `evaluate_table_expression`
   对记录求值，产出 `Assessment`（verdict + 依据）。
6. **验收（治理层）**：`draft_acceptance_criteria` 两段式起草判据（阈值、证据
   要求、`unknown_policy`），经管理入口确认后 `active`；`isolate_acceptance_samples`
   按分组键整组划分并冻结样本；`evaluate_business_acceptance` 只在未见样本上
   评测，失败、超时计入分母，`unknown` 按 `unknown_policy` 计分。
7. **报告（应用层）**：`compose_document_report` / `export_report_format` 汇总
   结论与 `AcceptanceReport`。

## 规则

- 主体与用途取自 `CallContext`（可信宿主固定）；调用参数不能覆盖。
- 治理层以 `enforcement = enforce` 运行：读取输入资源前复检决策存在、
  `allow`、未过期、资源覆盖、用途一致，否则 `da12.access_denied`。
- 生成 `inference_request` 前先 `check_model_context_egress`；`allow_masked`
  只附脱敏内容，`deny` 或缺失时不附内容（`da12.egress_required`）。
- 金标只经 `evaluate_business_acceptance` 读取；其他读取会写入暴露台账并把
  该样本降为 `regression`，冻结旧版也不得再当未见样本使用。
