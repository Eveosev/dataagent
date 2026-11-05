# 质检报告 — packages/capabilities/dataagent-runtime

snapshot: `sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66`（67 文件）｜rubric: `docs/standards/code-landing-rubric.json`

## 结论

- 总分 **93.1**（A 可交付），可验收，证据覆盖 100.0%，rubric sha 5e65f6c6006a
- 闸门：无
- 测试：ok（112 passed / 0 failed / 0 errors），独立 venv=True
- 复跑：`cd dataagent-runtime && .venv/bin/python -m pytest -p no:warnings`

## 测量

| 项 | 结果 |
|-|-|
| 生产文件 | 19 |
| TODO/FIXME | 0 |
| 裸 except / 吞错 | 0 / 0 |
| pyc / __pycache__ | 50 / 5 |
| 重复率 | 2.13%（53/2489 行；包内 20，跨包 33；15 组） |
| bundle 漂移 | 一致；vendored: dataagent_contracts |
| CC>10 / CC>25 LOC 占比 | 28.32% / 0.0%（ast（radon 计数规则；radon 未安装），153 函数） |
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
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:176 CC=17（29 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py:138 CC=16（41 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:95 CC=16（27 行代码）

## 未通过 / 未测量

- 得 0：A5.1, L4.2
- 未测量：无

## 下一步

- 无阻塞项；把本报告与 score JSON 一起归档。
