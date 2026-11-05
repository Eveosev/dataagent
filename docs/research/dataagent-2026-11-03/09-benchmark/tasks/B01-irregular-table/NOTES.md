# B01 不规则表格理解 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA01.4.2, DA01.4.6, DA02.1.1, DA02.1.2, DA02.2.1, DA02.2.2, DA02.2.3, DA02.2.4, DA02.4.1, DA02.4.2, DA02.4.3, DA02.4.4, DA02.4.5
- 参考：RealHiTBench, MiMoTable

## 为什么不用单测覆盖

多行表头、合并单元格、合计行的识别依赖真实表格分布；单元测试只能覆盖合成表。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：header_cell_match, qa_exact_match, row_retention。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B01`（转换器 `tools/converters/B01.py`），manifest `v0.2`
- 原始数据：mimotable、realthitbench-data，落在 `workspace/benchmark-data/B01/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 downstream_qa_accuracy；部分 header_cell_accuracy、row_retention；缺口 —
- 说明：外部集只给问答答案；表头正确率与行保留率需用自建金标（结构标注）判定
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
