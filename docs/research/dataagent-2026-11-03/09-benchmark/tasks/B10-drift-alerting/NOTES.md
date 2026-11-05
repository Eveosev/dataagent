# B10 持续监控与告警 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA14.2.1, DA14.2.2, DA14.2.3, DA14.2.4, DA14.3.1, DA14.3.2, DA14.8.1, DA14.8.2, DA14.8.3
- 参考：TSB-AD

## 为什么不用单测覆盖

误报与漏报只在真实时间序列上出现；合成异常会把检测延迟测低。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：alert_precision, detection_delay, vus_pr。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B10`（转换器 `tools/converters/B10.py`），manifest `v0.4`
- 原始数据：tsb-ad-u、tsb-ad-m，落在 `workspace/benchmark-data/B10/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 vus_pr、affiliation_f1；部分 —；缺口 alert_budget_compliance
- 说明：告警预算需 harness 统计巡检次数；先由 scorecard 记录 alert_count
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
