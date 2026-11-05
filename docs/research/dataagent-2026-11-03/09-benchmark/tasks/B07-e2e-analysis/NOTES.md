# B07 端到端多步数据分析 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA06.4.1, DA06.4.2, DA06.4.3, DA06.4.4, DA06.4.5, DA06.4.6, DA06.5.1, DA06.5.2, DA07.1.1, DA07.1.2, DA07.1.3, DA07.2.1, DA07.2.2, DA08.1.1, DA08.1.2, DA08.2.1, DA08.2.2, DA08.2.3, DA08.2.4, DA08.3.1, DA08.3.2, DA08.3.3, DA08.4.1, DA08.4.2, DA08.4.3, DA08.5.1, DA08.5.2, DA08.6.1, DA08.6.2, DA08.6.3, DA08.6.4
- 参考：DABstep, KramaBench

## 为什么不用单测覆盖

跨文件综合、读业务手册、中间结果正确性只在多步链上出现；单步单测无法替代。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：cost_report, exact_match, pass_k, step_audit。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B07`（转换器 `tools/converters/B07.py`），manifest `v0.2`
- 原始数据：dabstep、kramabench，落在 `workspace/benchmark-data/B07/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 exact_match_accuracy；部分 —；缺口 step_efficiency、final_report_quality
- 说明：步骤效率与报告质量需要轨迹与成稿；先由 harness 记录 steps 与 report
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
