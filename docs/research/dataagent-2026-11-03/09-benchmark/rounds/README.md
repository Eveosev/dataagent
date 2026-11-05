# rounds：一次迭代的索引

一个 `rounds/<round-id>.json` = 一轮（15 个任务在同一环境下的同一批运行）。轮次文件只存索引与汇总裁定，明细在各任务的 `history/runs/<round-id>/`。

## 1. 命名

| 前缀 | 含义 | 进趋势 | 可建基线 |
|-|-|-|-|
| `r` | 正式轮：模型、内核、提示或工具版本有变更，或周期性复查 | 是 | 是 |
| `x` | 探索轮：调参、试 grader、跑单条失败用例 | 否 | 否 |

格式 `rNNN-YYYY-MM-DD`，同一天多轮时序号递增（`r003-2026-11-18`、`r004-2026-11-18`）。

## 2. 字段

| 字段 | 含义 |
|-|-|
| `round_id` | 与文件名一致 |
| `label` | 本轮目的：`baseline` / `model-swap` / `prompt-tune` / `post-fix` / `quarterly` |
| `created` | 开轮时间（带时区） |
| `env` | 适配器、模型、内核、dataagent、harness 版本；四项任一变即不可与旧轮直接比 Δ |
| `tasks` | 15 个槽位：`run_dir`、`status`、`verdict`、`gate` |
| `aggregate` | `gate`：`release` / `hold` / `warn` / `pending`；`blockers`：阻断项；`notes`：裁定说明 |

## 3. 命令

```bash
python3 tools/new_round.py --label post-fix --model <模型> --kernel agent-kernel@<sha>
python3 tools/new_round.py --label tune-embed --prefix x   # 探索轮
```

已存在的轮次不会被覆盖（同名直接报错退出）；要重跑请在 `label` 里体现，或用新轮次。

## 4. 开轮后的状态流转

| 槽位状态 | 触发 | 谁改 |
|-|-|-|
| `pending` | `new_round.py` 生成 | 脚本 |
| `running` | harness 开始跑该任务 | harness |
| `scored` | `scorecard.json` 与 `cases.jsonl` 写完 | harness |
| `skipped` | 无数据或环境缺件 | 裁定人，必须在 `aggregate.notes` 写原因 |

没有 `skipped` 的说明就是漏跑：`check.py` 只校验一致性，不替你判断「15 个都跑了没有」，裁定人需在 `aggregate.notes` 逐项交代。

## 5. 首轮（r001）范围

`check_rounds` 要求轮次文件覆盖 B01–B15 全部槽位，因此首轮按「能跑则跑、不能跑则 skipped 并写明原因」处理：

| 任务 | 首轮状态 | 原因 |
|-|-|-|
| B02 | 跑 | 主指标 `text_ned` 可判分，原子有实现 |
| B03 | 跑 | 主指标 `value_f1` 可判分；证据金标为派生（CORD OCR 词序列 + ExtractBench schema 页码） |
| B04 | 跑 | 主指标 `rule_selection_accuracy` 可判分 |
| B01 | skipped | 主指标 `header_cell_accuracy` 缺表头结构金标；严格派生的表头口径只覆盖 15/240 条，样本不足以支撑 block 门槛 |
| B05–B14 | skipped | 引用原子集中在应用层/运营层/治理层，这些层当前 0 个原子有实现，跑出来只能测到「未实现」 |
| B15 | skipped | 无公开数据（`planned`） |

裁定人需在 `rounds/r001-<date>.json` 的 `aggregate.notes` 逐条写明 skipped 原因，不能只留空槽位。

探索轮（`xNNN`）先只落 `tasks/<task>/history/runs/<round-id>/`，不强制写 `rounds/<round-id>.json`；等某次探索转正或进入 `r` 轮时，再补轮次索引——`check.py` 只校验已存在的轮次文件。
