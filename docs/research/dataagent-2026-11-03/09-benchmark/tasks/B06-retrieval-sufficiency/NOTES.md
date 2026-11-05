# B06 召回检索与检索充分性 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA05.1.1, DA05.1.2, DA05.1.3, DA05.2.1, DA05.2.2, DA05.2.3, DA05.2.4, DA05.4.1, DA05.4.2, DA05.6.1, DA05.6.2, DA05.9.1, DA05.9.2, DA05.9.3, DA05.9.4
- 参考：BRIGHT, TARGET

## 为什么不用单测覆盖

漏召回无法归因、停止时机只有整链跑起来才可测。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：ndcg, recall_k, retrieval_stop_audit, step_audit。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B06`（转换器 `tools/converters/B06.py`），manifest `v0.1`
- 原始数据：bright，落在 `workspace/benchmark-data/B06/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 recall_at_k、ndcg_at_10；部分 —；缺口 miss_on_stop_rate、redundant_step_rate
- 说明：停止时机与多余步数需检索轨迹；先由 harness 记录 step 序列再补
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
