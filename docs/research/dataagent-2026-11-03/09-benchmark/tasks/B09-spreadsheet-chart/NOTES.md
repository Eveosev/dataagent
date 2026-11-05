# B09 表格计算、图表与报告 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA10.1.1, DA10.1.2, DA10.1.3, DA10.1.4, DA10.2.1, DA10.2.2, DA10.3.1, DA10.3.2, DA10.3.3
- 参考：SpreadsheetBench 2, VisEval, nvBench 2.0

## 为什么不用单测覆盖

大型多 sheet 工作簿里的目标单元格选错、未修改区域被改坏，只有整簿比对才可见。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：chart_readability_rubric, chart_schema_check, sheet_untouched_diff, workbook_cell_diff。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B09`（转换器 `tools/converters/B09.py`），manifest `v0.5`
- 原始数据：spreadsheetbench、spreadsheetbench、nvbench2，落在 `workspace/benchmark-data/B09/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 cell_accuracy、region_iou；部分 —；缺口 report_factuality
- 说明：图表类由 nvBench2 覆盖（mark/encoding 结构匹配）；报告成稿质量待 VisEval 数据
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
