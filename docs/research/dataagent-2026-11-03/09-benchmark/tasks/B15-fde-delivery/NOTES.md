# B15 FDE 交付效果 — 迭代记录

## 现状

- 状态：`planned`，评测集未采集，基线未建立。
- 原子：DA18.5.1, DA18.5.2, DA18.5.3, DA11.6.1, DA11.6.2, DA11.6.3, DA11.6.4, DA11.7.1, DA11.7.2, DA11.7.3, DA11.8.1, DA11.8.2, DA11.8.3, DA16.5.1, DA16.5.2
- 参考：无外部参照

## 为什么不用单测覆盖

只能在真实客户环境测量；不合成、不外推，按交付 cohort 统计。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：field_log_aggregate。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 无公开数据可下载；不建离线评测集（`manifest.status=planned`，用例 0）
- 需要的材料：客户 engagement 台账（开始 / 首次可信答案 / 验收时间、返工轮次）、影子运行日志、验收结论
- 动作：① 客户授权与脱敏（合同 / DPA）；② 台账模板化；③ 日志接入 harness；④ 累计 ≥3 个 engagement 后建 development 集
- 在数据到位前，B15 只在现场测量中打分，不参与 CI（`in_ci: false`）
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
