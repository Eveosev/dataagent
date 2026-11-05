---
generated_by: tools/report.py
do_not_edit: true
---

# 迭代趋势

任务 15 个，轮次 0 次。本文件由 `tools/report.py` 生成，不要手改；
迭代叙事写入 `tasks/<task>/NOTES.md`，告警归因写入 `monitor/incidents/`。

## 轮次总览

| 轮次 | 标签 | 环境 | 已评分 | block 通过 | guard 告警 | 建成基线 | 结论 |
|-|-|-|-|-|-|-|-|
| — | 尚未开轮 | — | 0/15 | — | — | — | 见 README §5 第 1 步 |

## 分任务最新值

| 任务 | 主指标 | 取值 split | 最新轮 | 基线轮 | 最新值 | 基线值 | Δ | 门槛 | verdict |
|-|-|-|-|-|-|-|-|-|-|
| B01 不规则表格理解 | header_cell_accuracy | — | — | — | — | — | — | block | pending |
| B02 文档解析与 OCR | text_ned | — | — | — | — | — | — | block | pending |
| B03 字段抽取与锚点 | value_f1 | — | — | — | — | — | — | block | pending |
| B04 制度 → 规则 → 可判定性与适用范围 | rule_selection_accuracy | — | — | — | — | — | — | block | pending |
| B05 指标定义与语义查询编译 | execution_accuracy | — | — | — | — | — | — | block | pending |
| B06 召回检索与检索充分性 | recall_at_k | — | — | — | — | — | — | warn | pending |
| B07 端到端多步数据分析 | exact_match_accuracy | — | — | — | — | — | — | warn | pending |
| B08 预测与优化 | smape | — | — | — | — | — | — | warn | pending |
| B09 表格计算、图表与报告 | cell_accuracy | — | — | — | — | — | — | warn | pending |
| B10 持续监控与告警 | vus_pr | — | — | — | — | — | — | warn | pending |
| B11 动作执行与策略遵从〔FDE〕 | pass_k_stability | — | — | — | — | — | — | warn | pending |
| B12 权限、敏感信息与外部数据安全 | attack_success_rate | — | — | — | — | — | — | guard | pending |
| B13 记忆与经验召回 | memory_accuracy | — | — | — | — | — | — | warn | pending |
| B14 数据建模与物化 | srdel | — | — | — | — | — | — | warn | pending |
| B15 FDE 交付效果 | time_to_first_trusted_answer | — | — | — | — | — | — | field | pending |

## 数据就绪度

| 任务 | manifest | development | regression | unseen | 原始来源 | 构建版本 |
|-|-|-|-|-|-|-|
| B01 | v0.2/collecting | 120 | 60 | 60 | 2 | 2（240 例） |
| B02 | v0.2/collecting | 120 | 60 | 60 | 1 | 2（240 例） |
| B03 | v0.5/collecting | 120 | 60 | 60 | 3 | 5（240 例） |
| B04 | v0.3/collecting | 120 | 60 | 60 | 1 | 3（240 例） |
| B05 | v0.10/collecting | 120 | 60 | 60 | 5 | 10（240 例） |
| B06 | v0.1/collecting | 120 | 60 | 60 | 1 | 1（240 例） |
| B07 | v0.2/collecting | 120 | 60 | 60 | 2 | 2（240 例） |
| B08 | v0.4/collecting | 120 | 60 | 60 | 2 | 4（240 例） |
| B09 | v0.5/collecting | 120 | 60 | 60 | 3 | 5（240 例） |
| B10 | v0.4/collecting | 120 | 60 | 60 | 2 | 4（240 例） |
| B11 | v0.1/collecting | 120 | 60 | 60 | 2 | 1（240 例） |
| B12 | v0.1/collecting | 73 | 17 | 23 | 1 | 1（113 例） |
| B13 | v0.2/collecting | 120 | 60 | 60 | 2 | 2（240 例） |
| B14 | v0.2/collecting | 120 | 54 | 50 | 1 | 2（224 例） |
| B15 | v0.0/planned | 0 | 0 | 0 | 2 | 0（0 例） |

## 门槛状态

- 仍有 `pending_baseline` 指标的任务：B01, B02, B03, B04, B05, B06, B07, B08, B09, B10, B11, B12, B13, B14, B15
- 绝对门槛 2 条：`monitor/thresholds.json`
- 默认相对规则：阻断 -5.0pp / 告警 -2.0pp；最少样本 20

## 待办

- 尚无基线的任务：B01, B02, B03, B04, B05, B06, B07, B08, B09, B10, B11, B12, B13, B14, B15
- 开新轮：`python3 tools/new_round.py --label <标签>`；改完重跑本脚本
