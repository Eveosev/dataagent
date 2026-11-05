# B13 记忆与经验召回 — 迭代记录

## 现状

- 状态：`collecting`，用例 146 条已建，基线未建立。
- 原子：DA04.3.1, DA04.3.2, DA04.3.3, DA05.3.1, DA05.3.2, DA05.3.3, DA05.3.4, DA12.3.1, DA12.3.2, DA12.3.3, DA12.3.4
- 参考：LongMemEval v2, MemoryAgentBench

## 为什么不用单测覆盖

知识更新后仍用旧信息、时序推理，只在多会话序列里出现。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：longmemeval_accuracy, refusal_score, staleness_probe。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B13`（转换器 `tools/converters/B13.py`），manifest `v0.2`
- 原始数据：memoryagentbench、longmemeval-cleaned，落在 `workspace/benchmark-data/B13/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 answer_recall、conflict_detection；部分 —；缺口 provenance_accuracy、clarification_rate
- 说明：溯源与澄清率需要 harness 记录引用片段与追问动作
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
