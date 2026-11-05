# B12 权限、敏感信息与外部数据安全 — 迭代记录

## 现状

- 状态：`collecting`，用例 113 条已建，基线未建立。
- 原子：DA12.1.1, DA12.1.2, DA12.1.3, DA12.1.4, DA16.1.1, DA16.1.2, DA16.1.3, DA16.1.4
- 参考：AgentDojo, CRMArena-Pro

## 为什么不用单测覆盖

指令劫持藏在文件与单元格里；只有真实文档载体才能复现攻击面。

## 待办

1. 按 `dataset/manifest.json` 的 sources 采集并脱敏，写入 `dataset/cases/`，金标与输入分离。
2. 落地 grader：agentdojo_attack_success, benign_utility, pii_leak_scan。
3. 第 1 次 r 轮次跑完后，按 `monitor/thresholds.json` 回填各指标门槛。
4. 首次基线写入 `history/baseline.json`；趋势看板由 `tools/report.py` 生成，本文件只记结论与决策。

<!-- data-build:start -->
## 数据构建

- 构建：`tools/build_cases.py --task B12`（转换器 `tools/converters/B12.py`），manifest `v0.1`
- 原始数据：agentdojo，落在 `workspace/benchmark-data/B12/`
- 当前用例：development 73 / regression 17 / unseen 23（共 113）
- 指标覆盖：已覆盖 injection_resistance、task_completion；部分 sensitive_leak_rate、privilege_escalation_rate；缺口 —
- 说明：泄漏与越权需要工具调用日志里的参数快照；agentdojo 环境在 harness 侧起
<!-- data-build:end -->

## 迭代日志

| 轮次 | 结论 | 变更 |
|-|-|-|
| — | 尚未运行 | — |
