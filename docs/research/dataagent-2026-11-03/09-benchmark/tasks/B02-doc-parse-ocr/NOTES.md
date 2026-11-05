# B02 文档解析与 OCR — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA01.4.5, DA01.5.1, DA01.5.2, DA02.8.1, DA02.8.2
- 参考：OmniDocBench, olmOCR-Bench

## 为什么不用单测覆盖

扫描件、盖章件、复杂版面的退化只在真实文档分布上出现；合成样本会低估版面错乱。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：assertion_pass_rate, ned_edit_distance, order_accuracy, teds。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B02`（转换器 `tools/converters/B02.py`），manifest `v0.2`
- 原始数据：omnidocbench，落在 `workspace/benchmark-data/B02/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 text_ned、table_teds、reading_order_accuracy；部分 —；缺口 —
- 说明：断言式评分（olmOCR-Bench）待其数据到位后追加
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
