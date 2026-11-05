# graders：指标实现

文件名即 `task.json` 中的 `metric.grader`；多个任务共用同一实现，改一次全生效。

| grader | 服务的任务 | 指标 | 状态 |
|-|-|-|-|
| `header_cell_match` | B01 | `header_cell_accuracy` | 已实现｜金标缺 headers，当前全 missing |
| `row_retention` | B01 | `row_retention` | 已实现｜金标缺 row_count，当前全 missing |
| `qa_exact_match` | B01 | `downstream_qa_accuracy` | 已实现 |
| `ned_edit_distance` | B02 | `text_ned` | 已实现 |
| `teds` | B02 | `table_teds` | 已实现（Zhang-Shasha 树编辑距离） |
| `order_accuracy` | B02 | `reading_order_accuracy` | 已实现（块级 Kendall tau） |
| `assertion_pass_rate` | B02 | `assertion_pass_rate` | 已实现｜金标缺 assertions，当前全 missing |
| `field_value_f1` | B03 | `value_f1` | 已实现 |
| `record_recall` | B03 | `record_completeness` | 已实现 |
| `span_f1` | B03 | `evidence_span_f1` | 已实现｜CORD 派生词级 span 可判（70 条），FUNSD/EB 仍 missing |
| `page_match` | B03 | `evidence_page_f1` | 已实现｜EB schema 页码提示 + CORD 单页可判 |
| `hallucination_probe` | B03 | `hallucination_rate` | 已实现 |
| `rule_choice_match` | B04 | `rule_selection_accuracy` | 已实现 |
| `direction_symmetry` | B04 | `condition_direction_consistency` | 已实现｜金标缺配对，当前全 missing |
| `decidability_classification` | B04 | `decidability_accuracy` | 已实现｜金标缺三分类标注，当前全 missing |
| `unknown_preservation` | B04 | `unknown_retention` | 已实现；当前 B04 无 unknown 样本，恒 missing |
| `sql_exec_match` | B05 | `execution_accuracy` | 未实现 |
| `repeat_consistency` | B05 | `metric_definition_consistency` | 未实现 |
| `refusal_check` | B05 | `unexpressible_refusal_rate` | 未实现 |
| `recall_k` | B06 | `recall_at_k` | 未实现 |
| `ndcg` | B06 | `ndcg_at_10` | 未实现 |
| `retrieval_stop_audit` | B06 | `miss_on_stop_rate` | 未实现 |
| `step_audit` | B06, B07 | `redundant_step_rate`, `steps_per_task` | 未实现 |
| `exact_match` | B07 | `exact_match_accuracy`, `hard_subset_accuracy` | 未实现 |
| `pass_k` | B07 | `pass_k_stability` | 未实现 |
| `cost_report` | B07, B14 | `cost_per_pipeline`, `cost_per_task` | 未实现 |
| `crps` | B08 | `crps` | 未实现 |
| `smape` | B08 | `smape` | 未实现 |
| `solver_objective_match` | B08 | `objective_value_accuracy` | 未实现 |
| `feasibility_classification` | B08 | `feasibility_class_accuracy` | 未实现 |
| `workbook_cell_diff` | B09 | `cell_accuracy` | 未实现 |
| `chart_schema_check` | B09 | `chart_validity` | 未实现 |
| `chart_readability_rubric` | B09 | `chart_readability` | 未实现 |
| `sheet_untouched_diff` | B09 | `unmodified_region_retention` | 未实现 |
| `vus_pr` | B10 | `vus_pr` | 未实现 |
| `alert_precision` | B10 | `alert_precision` | 未实现 |
| `detection_delay` | B10 | `detection_latency` | 未实现 |
| `tau_pass_k` | B11 | `pass_k_stability` | 未实现 |
| `policy_violation_scan` | B11 | `violation_rate` | 未实现 |
| `refusal_policy_check` | B11 | `missed_refusal_rate` | 未实现 |
| `approval_trigger_match` | B11 | `approval_trigger_accuracy` | 未实现 |
| `agentdojo_attack_success` | B12 | `attack_success_rate` | 未实现 |
| `benign_utility` | B12 | `task_completion_under_attack` | 未实现 |
| `pii_leak_scan` | B12 | `sensitive_leak_rate` | 未实现 |
| `longmemeval_accuracy` | B13 | `memory_accuracy` | 未实现 |
| `staleness_probe` | B13 | `stale_misuse_rate` | 未实现 |
| `refusal_score` | B13 | `refusal_correctness` | 未实现 |
| `pipeline_load_check` | B14 | `srdel` | 未实现 |
| `pipeline_transform_check` | B14 | `srdt` | 未实现 |
| `field_log_aggregate` | B15 | `approval_burden`, `onboarding_effort`, `shadow_agreement`, `time_to_first_trusted_answer` | 未实现 |

## 实现顺序

按门槛层级：先 B01–B05 与 B12 用到的 grader（block / guard），再 warn 组。

## 约束

- 返回 `value=None` 表示不可判定，进 `samples.missing`，不得当 0 分。
- 只算值，不判阈值；方向与门槛在 `task.json` / `monitor/thresholds.json`。
- 语言模型当评委的 grader（`chart_readability_rubric`、`refusal_score`）必须双人复核样本 ≥ 30 条，并记录评审一致性；不一致的用例降级为 `development`。
- 每个 grader 带一个自测：`tests/test_<grader>.py`，用 3–5 条手算期望值钉住口径。

## 已实现范围与金标缺口（2026-11-05）

已实现 16 个 grader，覆盖 B01–B04。**当前金标下能真正打出分的指标 11 个**：

| 任务 | 可判指标 | 判不了的原因 |
|-|-|-|
| B01 | `downstream_qa_accuracy` | 主指标 `header_cell_accuracy` / `row_retention` 缺表头与行数金标（外部集只发 QA 答案） |
| B02 | `text_ned` / `table_teds` / `reading_order_accuracy` | `assertion_pass_rate` 缺断言集 |
| B03 | `value_f1` / `record_completeness` / `evidence_span_f1` / `evidence_page_f1` / `hallucination_rate` | FUNSD 是实体+bbox 形态，不进 `value_f1`；span 只覆盖 CORD |
| B04 | `rule_selection_accuracy` / `unknown_retention` | `decidability_accuracy` 缺三分类标注；`condition_direction_consistency` 缺配对 |

补金标的最小路径：

- B01：对 MiMoTable/RealHiTBench 抽样 60 条，人工标注表头行与数据行数（或只对结构清晰的子集标）；
- B02：给 30–50 页写结构断言（`path/op/value`），直接喂 `assertion_pass_rate`；
- B03：span/page 已用派生金标补齐（CORD OCR 词序列、ExtractBench schema 页码提示）；剩余缺口是 FUNSD 的 bbox 形态，需要 `bbox_iou` 判分器而不是 span；
- B04：生成条件正反配对（同一规则、相反取值）并补 `decidability` 三分类标注。

在补齐前，这些指标在 scorecard 里是 `value: null` + `missing` 计数，**不会**按 0 分参与聚合。

## 运行

```bash
# 单测（口径钉死）
python3 -I harness/tests/test_graders.py

# 端到端（金标回填应满分，扰动应掉分）
python3 -I harness/tests/test_pipeline.py

# 判分
python3 -I harness/grade.py --task B02 --pred runs/<run>/predictions.jsonl \
  --run-id x001-2026-11-05 --out runs/<run>/scorecard.json --detail runs/<run>/detail.jsonl
```
