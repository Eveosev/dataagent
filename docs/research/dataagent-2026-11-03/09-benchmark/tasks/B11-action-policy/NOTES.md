# B11 动作执行与策略遵从〔FDE〕 — 迭代记录

## 现状

- 状态：`collecting`，用例 240 条已建，基线未建立。
- 原子：DA06.6.1, DA06.6.2, DA06.6.3, DA06.7.1, DA06.7.2, DA06.7.3, DA07.7.1, DA07.7.2, DA07.7.3, DA07.7.4, DA07.8.1, DA07.8.2, DA07.8.3, DA15.1.1, DA15.1.2, DA15.1.3, DA16.2.1, DA16.2.2, DA16.2.3, DA16.2.4, DA16.2.5
- 参考：τ²-bench, CRMArena-Pro

## 为什么不用单测覆盖

多轮交互中违反策略、该拒未拒、重复执行结果不一致，需要真实环境状态才能判定。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：approval_trigger_match, policy_violation_scan, refusal_policy_check, tau_pass_k。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B11`（转换器 `tools/converters/B11.py`），manifest `v0.1`
- 原始数据：tau2-bench、crmarena-pro，落在 `workspace/benchmark-data/B11/`
- 当前用例：development 120 / regression 60 / unseen 60（共 240）
- 指标覆盖：已覆盖 pass_k_stability、approval_trigger_accuracy；部分 violation_rate、missed_refusal_rate；缺口 —
- 说明：违规与漏拒需环境侧动作日志与策略断言；τ² 的 evaluation_criteria 提供断言，CRMArena 只给最终答案
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
