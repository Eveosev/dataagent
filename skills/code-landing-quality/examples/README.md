# Examples

输出均为 2026-11-05 在本仓库实跑的结果。

## 从方案到清单

```console
$ python3 skills/code-landing-quality/scripts/plan_checklist.py \
    docs/research/dataagent-2026-11-03/07-application-layer-build-plan.md | head -6
# 验收清单 — 07-application-layer-build-plan.md

方案版本：v0.3.8｜状态：S0 实施中

## 4.1 调用

- [ ] `4.1#3b1a1d` `invoke(operation, input, CallContext) -> CapabilityResult[T]`，MCP 工具名 = operation …
```

条目 id 由章节号和文本哈希组成：方案中插入章节不会改变已有 id，改写条目文本则会产生新 id。

## 测量并预填

```console
$ python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
    --package packages/capabilities/dataagent-application --fill /tmp/app.score.json
- 测试：ok（201 passed / 0 failed / 0 errors），独立 venv=True
| 裸 except / 吞错 | 0 / 1 |
| 重复率 | 6.07%（228/3754 行；包内 189，跨包 39；56 组） |
| bundle 漂移 | 一致；vendored: dataagent_contracts, dataagent_runtime |
| CC>10 / CC>25 LOC 占比 | 50.19% / 28.8%（ast（radon 计数规则；radon 未安装），104 函数） |
| 超长函数 / 模块 | 1 / 1 |
- except：packages/capabilities/dataagent-application/src/dataagent_application/execution/sql.py:206
```

`--fill` 写入 A1.1=0、D1=red、A5.1=0、A5.2=0、A5.3=0、A10.1=0（均带位置证据），以及 `snapshot` 和 `rubric_version`。其余规则、`profile`、`checklist`、`defects` 由评审人填写。

## 语义缺陷不再能拿 A

把 L2.1–L2.3 判 0、其余全部通过：2.0 版给出 92.0（A，可交付）。2.1 版要求同时登记对应的清单条目和缺陷，结果为：

```console
总分: 59.0 / 100    等级: E 不合格    结论: 不可验收
| GATE-P0 | 59 | D1 |
| GATE-CHECKLIST | 79 | 5.2#000000 |
```

如果只把规则判 0、不登记缺陷，`defects=null` 触发 GATE-NO-DEFECTS（封顶 89）；如果登记了 P0 缺陷却仍把关联规则判 1，评分脚本以退出码 2 拒绝出分。

## 轮次对比

```console
$ python3 skills/code-landing-quality/scripts/round_diff.py r5-app.score.json r6-app.score.json --fail-on-regression
| ID | 级 | r5 | r6 | 结论 | 问题 | 位置 |
| D1 | P2 | fixed | open | 回归 | … |
| D2 | P1 | — | open | 新缺陷 | … |
```

完整的 Tester 流程见 [../references/tester.md](../references/tester.md)。
