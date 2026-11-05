# B14 数据建模与物化 — 迭代记录

## 现状

- 状态：`collecting`，用例 224 条已建，基线未建立。
- 原子：DA13.1.1, DA13.1.2, DA13.2.1, DA13.2.2, DA13.3.1, DA13.3.2, DA13.3.3
- 参考：ELT-Bench, ELT-Bench Verified, Spider 2.0

## 为什么不用单测覆盖

转换模型的列与真值不一致，只有跑完加载与物化才暴露。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：cost_report, pipeline_load_check, pipeline_transform_check。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B14`（转换器 `tools/converters/B14.py`），manifest `v0.2`
- 原始数据：elt-bench，落在 `workspace/benchmark-data/B14/`
- 当前用例：development 120 / regression 54 / unseen 50（共 224）
- 指标覆盖：已覆盖 model_schema_match、column_semantics_match；部分 —；缺口 pipeline_run_success、data_freshness
- 说明：端到端跑通需要 Docker + Airbyte + Snowflake/Redshift/Databricks 凭证，本机不构建；Spider 2.0 的 dbt 任务（spider2-dbt）已决定延后，暂由 ELT-Bench 覆盖
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
