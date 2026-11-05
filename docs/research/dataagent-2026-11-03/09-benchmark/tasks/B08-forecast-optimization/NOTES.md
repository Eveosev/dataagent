# B08 预测与优化 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA09.1.1, DA09.1.2, DA09.1.3, DA09.2.1, DA09.2.2, DA09.3.1, DA09.3.2, DA09.4.1, DA09.4.2
- 参考：Context is Key, OptiBench, OptiMATH / 综述

## 为什么不用单测覆盖

预测需结合文本上下文；求解结果要区分最优、可行、未知，三者混淆在单测里看不出来。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：crps, feasibility_classification, smape, solver_objective_match。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B08`（转换器 `tools/converters/B08.py`），manifest `v0.4`
- 原始数据：orlm-bench、context-is-key，落在 `workspace/benchmark-data/B08/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 formulation_exact_match、constraint_coverage；部分 —；缺口 optimality_gap、constraint_satisfaction_rate
- 说明：最优值需运行求解器；本机无 LP/MIP 求解器，先按结构匹配判分；约束满足率需在 grader 里按 constraint_min/max 复核
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
