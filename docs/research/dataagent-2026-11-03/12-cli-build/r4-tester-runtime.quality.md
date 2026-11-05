# 质检报告 — packages/capabilities/dataagent-runtime

snapshot: `sha256:78c93a64776a5dbc4ad45fd9c3f9f849d5d105b300f08179445fcaa2f9e1f400`（67 文件）｜rubric: `docs/standards/code-landing-rubric.json`

## 结论

- 未评分：未给 --result
- 测试：ok（102 passed / 0 failed / 0 errors），独立 venv=True
- 复跑：`cd dataagent-runtime && .venv/bin/python -m pytest -p no:warnings`

## 测量

| 项 | 结果 |
|-|-|
| 生产文件 | 19 |
| TODO/FIXME | 0 |
| 裸 except / 吞错 | 0 / 0 |
| pyc / __pycache__ | 49 / 5 |
| 重复率 | 2.21%（53/2402 行；包内 20，跨包 33；15 组） |
| bundle 漂移 | 一致；vendored: dataagent_contracts |
| CC>10 / CC>25 LOC 占比 | 25.77% / 0.0%（ast（radon 计数规则；radon 未安装），153 函数） |
| 超长函数 / 模块 | 0 / 0 |
| rubric / scorer 副本 | 一致 / 一致 |

## 位置

- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py:300, packages/capabilities/dataagent-data/src/dataagent_data/invoke.py:24, packages/capabilities/dataagent-scenarios/src/dataagent_scenarios/gate.py:127
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py:101, packages/capabilities/dataagent-data/src/dataagent_data/adapters/storage/sqlite.py:140
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py:109, packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py:149
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/cli.py:3, packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/mcp_server.py:7
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py:17, packages/capabilities/dataagent-scenarios/src/dataagent_scenarios/gate.py:20
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py:255 CC=25（84 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py:299 CC=24（109 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py:138 CC=16（41 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:95 CC=16（27 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py:153 CC=15（58 行代码）

## 已预填规则

A1.1, A5.1, A5.2, A5.3, D1（measured_by=quality_run；其余规则由评审人填写）

## 下一步

- 无阻塞项；把本报告与 score JSON 一起归档。
