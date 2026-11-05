# B05 指标定义与语义查询编译 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA03.4.1, DA06.1.1, DA06.1.2, DA06.1.3, DA06.1.4, DA06.2.1, DA06.2.2, DA06.2.3, DA06.3.1, DA06.3.2, DA06.3.3, DA06.3.4, DA06.3.5, DA06.8.1, DA06.8.2, DA06.8.3, DA07.5.1, DA07.5.2
- 参考：BEAVER, data.world CWD, dbt-llm-sl-bench

## 为什么不用单测覆盖

同一问题多次口径不一，只有重复提问与多 schema 才能测；企业级 schema 复杂度不可合成。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：refusal_check, repeat_consistency, sql_exec_match。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B05`（转换器 `tools/converters/B05.py`），manifest `v0.10`
- 原始数据：bird-mini-dev、cwd、spider2-lite、beaver-table、beaver，落在 `workspace/benchmark-data/B05/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 execution_accuracy、unexpressible_refusal_rate；部分 metric_definition_consistency；缺口 —
- 说明：执行准确率需本地起库：CWD 可用 CSV 建库；BEAVER 已取 beaver_db.zip（dw/nova/neutron 的 MySQL dump，解压 2.1 GB），装载后可按 SQL 执行比对；BIRD 与 Spider2 的库仍需另行申请。BEAVER 全量 7,978 条按 8% 抽样 592 条入库，全量留在原始目录；任务卡已并入 beaver-table 的列名/类型/示例行（381 张表），join_keys 与 domain_knowledge 用于口径与连接语义判分
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
