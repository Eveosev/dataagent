# r1 修复/实现记录 — 统一 CLI

- 轮次：r1（2026-11-06）
- 方案：[12-unified-cli-build-plan.md](../12-unified-cli-build-plan.md)（依据 [12-unified-cli-research.md](../archive/12-unified-cli-research.md) v0.3 §5）
- 评分：[r1.score.json](r1.score.json) / [r1.score.txt](r1.score.txt) — **59.0/100（GATE-RED：D1 重复率硬阈，见下）**
- 源码快照（改动前）：`/tmp/agentos-snapshots/pre-cli-20261106-013324.tar.gz`

## 按清单项的实现

| 清单项 | 实现位置 | 测试 |
|-|-|-|-|
| W1 参数解析（--input-file/--set/--set-json/--file/--ref/--proposal-file/--authorize） | `dataagent-runtime/src/dataagent_runtime/interfaces/unified.py:108-157, 252-357, 435-471` | `dataagent-runtime/tests/test_unified_cli.py`（22 项） |
| W1 `--help` 扁平参数表（无 `$defs`） | `unified.py:383-419` | `test_op_help_flat_without_defs` |
| W1 `list` 每行一 op | `unified.py:421-428` | 三层冒烟：data 32 / app 13 / gov 6 行 |
| W1 摘要 ≤32KiB + 全文落盘 + `--detail full` | `unified.py:539-616` | `test_summary_truncated_over_32kib`、`test_detail_full_prints_whole_result` |
| W1 needs_input → inference_request + next_command | `unified.py:582-596` | `test_needs_input_emits_request_and_next_command` |
| W1 输出前外发检查（enforce 剥离） | `unified.py:360-380` | `test_egress_scrub_*` |
| W1 退出码 0/1/2/3 | `unified.py:37-40` 及各分支 | `test_failed_result_exit_1` 等；数据层黑盒断言更新为 2/3 |
| W1 身份只取宿主 env | `unified.py:330-336,437-441`；`dataagent-data/src/dataagent_data/runtime.py:80-84`（补 env 读取） | `test_input_file_cannot_smuggle_context`、`test_authorize_*` |
| W2 三层接入 + bundle 重建 | 三层 `interfaces/cli.py`；bundle：data/gov `scripts/build_bundle.py`，app 手工同步 | 各层套件全绿；app `test_bundle_sync` 3 passed |
| W2 gov `confirm <file>` / `policy apply <file>` | `dataagent-governance/.../cli.py:112-158` | `test_cli_confirm_accepts_file`、`test_cli_policy_apply` |
| W3 `dataagent/cli` 分发器 | `dataagent-cli/bin/dataagent`（sh，无 Python 依赖） | `dataagent-cli/tests/test_dispatcher.py`（12 项） |
| W3 link/setup/doctor | 同上 `link_cmd`/`setup_cmd`/`doctor_cmd` | dispatcher 测试 |
| W3 SKILL.md + mint.toml artifacts | `dataagent-cli/skills/dataagent-cli/SKILL.md`、`dataagent-cli/mint.toml` | — |
| W3 preset 依赖 | `dataagent-s0/mint.toml:21` | — |
| W4 测试与评分 | 见上 + 本文件 | 全量：runtime 99、app 179、gov 121、data 全绿 |

## 按缺陷 ID

| ID | 级别 | 状态 | 说明 |
|-|-|-|-|
| D1 | P2 | open | 包间重复率 13.84% > 3%（D1/A1.1 red → GATE-RED 封顶 59）。**基线（改动前快照实测）19.26%**，本轮删除数据层 CLI 旧拷贝后下降 5.4pp；剩余为三层 runtime wiring/sqlite adapter 既有架构性复制，需专门一轮去重，超出 r1 范围 |
| D2 | P2 | open | `_parse_params`/`_emit` CC 26/23；A5.1/A5.2 超阈亦含既有 tabular/enforcement/invoke |
| D3 | P2 | open | CLI 内核无默认超时（invoke 尊重 CallContext.deadline） |
| D4 | P2 | open | 3 处 `except ValidationError: continue` 跳过式处理 + 1 处预存 gold_ledger best-effort 被 A10.1 计为吞错 |

## 命令

```sh
cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -q          # 99 passed
cd ../dataagent-data && .venv/bin/python -m pytest -q                               # 全绿
cd ../dataagent-application && .venv/bin/python -m pytest -q                        # 179 passed
cd ../dataagent-governance && .venv/bin/python -m pytest -q                         # 121 passed
cd ../dataagent-cli && python3 -m unittest discover -s tests                        # 12 OK
python3 skills-path/quality_run.py --repo . --package packages/capabilities/dataagent-runtime --fill docs/research/dataagent-2026-11-03/12-cli-build/r1.score.json
python3 skills-path/score_landing.py --result docs/research/dataagent-2026-11-03/12-cli-build/r1.score.json
```

## 结论

功能面（W1-W4 清单 17/17 done）完成且全量测试通过；rubric 不可验收仅因继承的 D1 重复率硬阈
（本轮已改善 19.26%→13.84%）。建议 r2 立项：三层 runtime wiring 去重 + `_parse_params/_emit`
拆分 + CLI 默认超时。
