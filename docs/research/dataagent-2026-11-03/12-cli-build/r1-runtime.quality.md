# 质检报告 — packages/capabilities/dataagent-runtime

snapshot: `sha256:9240f8ec01c356ade9b4a783ddab0f616c2bfed3e7777d93fa7d2579e3ba41af`（67 文件）｜rubric: `docs/standards/code-landing-rubric.json`

## 结论

- 未评分：未给 --result
- 测试：ok（99 passed / 0 failed / 0 errors），独立 venv=True
- 复跑：`cd dataagent-runtime && .venv/bin/python -m pytest -p no:warnings`

## 测量

| 项 | 结果 |
|-|-|
| 生产文件 | 19 |
| TODO/FIXME | 0 |
| 裸 except / 吞错 | 0 / 4 |
| pyc / __pycache__ | 49 / 5 |
| 重复率 | 13.84%（319/2305 行；包内 20，跨包 299；171 组） |
| bundle 漂移 | 一致；vendored: dataagent_contracts |
| CC>10 / CC>25 LOC 占比 | 29.2% / 4.9%（ast（radon 计数规则；radon 未安装），140 函数） |
| 超长函数 / 模块 | 0 / 0 |
| rubric / scorer 副本 | 一致 / 一致 |

## 位置

- except：packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/gold_ledger.py:136
- except：packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py:194
- except：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:272
- except：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:287
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py:90, packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py:130, packages/capabilities/dataagent-runtime/src/dataagent_runtime/ports/versioned.py:17 …(+5)
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py:82, packages/capabilities/dataagent-data/src/dataagent_data/adapters/storage/sqlite.py:153, packages/capabilities/dataagent-data/src/dataagent_data/adapters/storage/sqlite.py:194
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py:300, packages/capabilities/dataagent-data/src/dataagent_data/invoke.py:24, packages/capabilities/dataagent-scenarios/src/dataagent_scenarios/gate.py:127
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/runtime.py:70, packages/capabilities/dataagent-data/src/dataagent_data/runtime.py:51, packages/capabilities/dataagent-governance/src/dataagent_governance/runtime/runtime.py:74
- 重复组：packages/capabilities/dataagent-runtime/src/dataagent_runtime/__init__.py:14, packages/capabilities/dataagent-governance/src/dataagent_governance/runtime/errors.py:5
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/ports/tabular.py:118 CC=31（68 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:108 CC=26（45 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py:234 CC=25（84 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py:299 CC=24（109 行代码）
- 复杂度：packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:462 CC=23（69 行代码）

## 已预填规则

A1.1, A10.1, A5.1, A5.2, A5.3, D1（measured_by=quality_run；其余规则由评审人填写）

## 下一步

- 重复率 13.84% > 3.0%（A1.1=0，D1 red）
- 存在裸 except 或吞错（A10.1=0）
