# B03 字段抽取与锚点 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA02.12.1, DA02.12.3, DA02.12.4
- 参考：ExtractBench, VRDU, DocILE

## 为什么不用单测覆盖

编造值、遗漏重复记录、证据位置错误都是分布相关行为，单测无法给出发生率。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：field_value_f1, hallucination_probe, page_match, record_recall, span_f1。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B03`（转换器 `tools/converters/B03.py`），manifest `v0.4`
- 原始数据：extractbench、cord-v2、funsd，落在 `workspace/benchmark-data/B03/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 value_f1、record_completeness、hallucination_rate、evidence_span_f1、evidence_page_f1；部分 no_anchor_recall；缺口 table_row_alignment
- 证据金标（派生，`derive` 标注）：CORD 用 `valid_line` 的 OCR 词序列把字段值对齐成词级 span（单页 page=1，70 条用例）；ExtractBench 从 schema description 的 "page N" 取字段页码（约 29% 用例带页码提示）；FUNSD 只有 bbox，不产出 span/page。
- 说明：证据金标为派生：CORD 用 OCR 词序列把字段值对齐成词级 span（单页，page=1）；ExtractBench 从 schema description 的 'page N' 提取字段页码（约 14% 字段带页码提示，其余字段不进 page 分母）；FUNSD 只有 bbox，未产出 span/page。DocILE 因 gated 已用 CORD-v2 + FUNSD 替代。
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
