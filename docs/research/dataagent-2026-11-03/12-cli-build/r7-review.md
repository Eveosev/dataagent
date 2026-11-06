---
round: r7
date: 2026-11-06
subject: dataagent-runtime 统一 CLI 第 7 轮独立验收
plan: docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md r1
rubric: 2.1 sha256:5e65f6c6006a
snapshot:
  dataagent-runtime: sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66
facts_ref: dataagent-runtime@85e46185eb742f1cb1127d77cf9f906209c2a092
verdict: 不可验收
score: 79.0（C）
---

# 第 7 轮验收：统一 CLI（dataagent-runtime + 三层接入 + dataagent-cli）

## 0. 结论

**不可验收：79.0 / 100（C），GATE-P1 + GATE-CHECKLIST。** r6-review 的两项阻断只清除了一项：

- **D5 fixed**：真实 stdout 精确字节边界成立。JSON 32,767 B → stdout 恰 32,768 B 且不截断；JSON 32,768 B → 截断后 277 B；32,769 / 40,000 B 同样 ≤32,768 B。
- **D16 partial**：无 pin 回退与 doctor/dispatch 一致性已修复（`v = 1`、仅 pin 其他层 → dispatch exit 0 / 32 行、doctor exit 0）；但 **compact / 缩进等合法 TOML 空白变体仍不可读，且修复把 r6 的 fail-closed 变成了 fail-open**：锁 pin 0.2.0 未安装时 r7 **exit 0 执行 0.1.0**（r6 同输入 exit 3）；两版本均装时锁 0.1.0 被忽略、解析到 0.2.0。这违反 r6-review 的 D16 清除条件「区分该层无 pin 与 pin 读取失败……不能撤销 D13 的 fail-closed 修复」。

五套测试 112 / 654 / 203 / 123 / 17 全通过，D1–D15 逐条复跑无未复核；除 D5 外无新增修复。D2 partial（28.32%）、D3 open 仍为非阻断 P2。无 P0。

独立证据目录：[/Users/payne/.dsh/state/agent-teamwork/team/r7-cli-review-evidence/](/Users/payne/.dsh/state/agent-teamwork/team/r7-cli-review-evidence/)（探针脚本 `d16_probe.py`、`d16_two_versions.py`、`d5_probe.py`、`cli_probe.py`、`followup_probe.py`、`management_probe.py`、`runtime_probe.py`、`audit.py` 与全部 JSON 输出）。

## 1. 基线与复跑

| 项 | 实测 |
|-|-|
| HEAD / facts_ref | `85e46185eb742f1cb1127d77cf9f906209c2a092`（与 r7-fixes 声明一致） |
| 测试 | runtime **112 passed**（0.51s）｜data **654**（8.78s）｜application **203**（3.85s）｜governance **123**（1.41s）｜cli **17 OK**（4.86s） |
| 快照 | `dataagent-runtime@sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66`（67 文件，独立复算） |
| 重复率 / 复杂度 | 2.13%（53/2489；包内 20 / 跨包 33）｜CC>10 28.32%｜CC>25 0.0%｜裸 except 0 / 吞错 0 |
| bundle | 四份 vendored `unified.py` 与源 `cmp` 逐字节一致；`quality_run` 漂移=一致 |
| 构建 | `uv lock --check` → Resolved 13（rc=0）；`uv build` rc=0；wheel 22 members / 19 `.py` / unified 31,587 B / 0 `.pyc` |
| 基线 tag | `dataagent-runtime-0.1.0` ref `20022e0a…` → commit `fbe24d8…`；tag 内 runtime 快照 `78c93a64…`（67 文件）与 r3 验收态一致；tag 后 runtime 仅 `unified.py` + 测试增量（524+/47-，旧模式测试保留）；`git fsck` rc=0 → **R13 green** 维持 |

## 2. 方案清单

27 条：**done 16 / partial 1 / not_done 0 / na 10 / waived 0**（完成率 94.1%）。

| 条目 | 判定 | 说明 |
|-|-|-|
| `W1共享内核实现（dataage#99a1de` stdout 摘要 32 KiB | **done** | r7 `fits()` 计入 `print` 换行（[unified.py:676-679](../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L676-L679)、[:780](../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L780)）；真实 dispatcher 边界见 §3 D5 |
| `W3分发器包实现#b9b374` mint.lock 优先 / 缺省最高版本 | **partial** | 无 pin 回退与 doctor/dispatch 一致性已成立；合法 TOML 空白 pin 仍不可读且 fail-open，见 §3 D16 |
| 其余 15 条（W1 参数/help/list/退出码/身份/needs_input/外发、W2 三层接入、W3 link/setup/SKILL/s0、W4 测试与交付） | done | 复跑证据见 `r7-tester-runtime.score.json` checklist；na 10 条为元数据与记录行 |

> 注：`plan_checklist.py` 未提取 r3 记录行（表格第二列不含 “验收” 关键词）；该行为元数据，不影响需求条目的判定。

## 3. 缺陷

### D5（P1 → fixed）32 KiB 摘要上限

| 输入（真实 dispatcher + governance venv，`DATAAGENT_ENFORCEMENT_MODE=warn`） | 期望 | 实测 |
|-|-|-|
| `draft_acceptance_criteria`，未截断 JSON 恰 **32,767 B** | stdout（JSON+\n）≤32,768，不截断 | exit 0，stdout **32,768 B**，`data.truncated` 缺失（未截断） |
| 未截断 JSON 恰 **32,768 B**（r6 为 32,769 B） | ≤32,768 | exit 0，stdout **277 B**，`data.truncated=true` |
| 32,769 B / 40,000 B | ≤32,768 | 277 B / 277 B，截断；全文在 `result_path` 保留 |
| 40,000 字符 criteria id；Unicode 句柄（回归） | ≤32,768 | 658 B / 1,040 B |

复跑：[d5_probe.py](/Users/payne/.dsh/state/agent-teamwork/team/r7-cli-review-evidence/d5_probe.py)；输出 `D5_json_32767.json`…`D5_json_40000.json`、`D5_long_handle.json`、`D5_unicode_handle.json`。结论：D5 关闭。

### D16（P1 → partial）无 pin 回退已修，合法 TOML pin 仍被忽略并 fail-open

**已成立的一半**（`/tmp/r7-tester` 真实三层 `.venv`，策略已配置）：

| mint.lock | `data list` | `doctor` |
|-|-|-|
| 仅 `v = 1` | **exit 0 / 32 行** | **exit 0**，`data-layer@0.1.0` |
| 仅 pin `governance-layer` 0.1.0 | **exit 0 / 32 行** | **exit 0** |
| 标准格式 pin `data-layer` 0.1.0 | exit 0 / 32 行 | exit 0，解析 0.1.0 |
| 标准格式 pin `data-layer` 0.2.0（未装） | exit 3，stdout 空 | exit 3，`MISSING pinned 0.2.0` |

**未成立的一半**：TOML 允许的空白变体（`tomllib.loads` 解析结果与标准格式相同）仍未被 `pinned_version` 的 `sed`/`grep` 识别：

| mint.lock（均为合法 TOML，`tomllib` 可解析） | 已装版本 | 期望 | 实测 |
|-|-|-|-|
| compact：`name="dataagent/data-layer"` + `version="0.1.0"` | 0.1.0 + 0.2.0 | 按 pin 用 **0.1.0** | exit 0；dispatcher 与 doctor 均解析 **0.2.0**（pin 被忽略，取最高已装） |
| 同上，缩进形式 | 0.1.0 + 0.2.0 | 0.1.0 | 同解析 **0.2.0** |
| compact：`version="0.2.0"`（未安装） | 仅 0.1.0 | **exit 3**，不得执行其他版本（D13 fail-closed） | **exit 0 / 32 行**，执行 0.1.0 |

r6/r7 同输入对照（同一 `/tmp/r7-tester`、同一 compact lock pin 0.2.0 未装）：

```sh
git show b12887f:packages/capabilities/dataagent-cli/bin/dataagent > /tmp/.../bin-r6
bin-r6 data list   # exit=3  stderr: mint.lock pins dataagent/data-layer without a readable version
bin data list      # exit=0  32 行（r7 fail-open）
```

**根因**：[bin/dataagent:53-63](../../../../packages/capabilities/dataagent-cli/bin/dataagent#L53-L63) 的 `pinned_version` 把「该层没有条目」与「条目版本不可读」都 `return 1`；[resolve_dir:64-73](../../../../packages/capabilities/dataagent-cli/bin/dataagent#L64-L73) 与 [doctor:143-152](../../../../packages/capabilities/dataagent-cli/bin/dataagent#L140-L152) 随后回退最高已装。r6-review 的清除条件要求区分二者并保留 D13 的 fail-closed；新增测试 `test_lock_unreadable_pin_falls_back`（[test_dispatcher.py:251-263](../../../../packages/capabilities/dataagent-cli/tests/test_dispatcher.py#L251-L263)）反而把 fail-open 固化为期望行为，因此 17 条 cli 测试全绿不能证明该语义正确。

复跑：[d16_probe.py](/Users/payne/.dsh/state/agent-teamwork/team/r7-cli-review-evidence/d16_probe.py)（矩阵 `D16_matrix.json`）、[d16_two_versions.py](/Users/payne/.dsh/state/agent-teamwork/team/r7-cli-review-evidence/d16_two_versions.py)（`D16_two_versions.json`）、`D16_pre_post_control.txt`、`cli_probe.py`（`D13_compact_toml` 失败项）。

### 16 条缺陷复核

| ID | 级 | 状态 | 与上轮对比 | 复现（输入 → 期望 / 实际） | 位置 |
|-|-|-|-|-|-|
| D1 | P2 | fixed | 保持关闭 | `quality_run` 重复率 2.13%（≤3%） | sqlite.py 等 |
| D2 | P2 | partial | 保持 | CC>10 LOC 占比 **28.32%**（阈 7.3%）；CC>25 0.0% | [enforcement.py:255](../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py#L255) |
| D3 | P2 | open | 保持 | CLI `ctx.deadline=None`；显式 20 ms deadline 下 handler 仍跑 **125 ms** 并完成，`status=ok` | [invoke.py:353-360](../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L353-L360) |
| D4 | P2 | fixed | 保持关闭 | 裸 except 0 / 吞错 0（AST） | unified.py 等 |
| D5 | P1 | **fixed** | **partial→fixed** | 见上表；32,768 B JSON → stdout 277 B | unified.py:676-679,780 |
| D6 | P2 | fixed | 保持关闭 | `dataagent bogus` usage 文本含 `dataagent <layer> <command> [flags]`，无多余 `<layer>` | bin/dataagent:224 |
| D7 | P2 | fixed | 保持关闭 | `probe_detail_egress.py`：enforce 下 summary/full 的 statement 均 False | unified.py |
| D8 | P2 | fixed | 保持关闭 | `--file nope.csv` → exit 2，无 traceback | unified.py:572 |
| D9 | P2 | fixed | 保持关闭 | 非法 confirmation → exit 2 `confirm: invalid confirmation record: 4 validation errors`；坏 JSON → exit 2 | governance cli.py |
| D10 | P1 | fixed | 保持关闭 | 三层判型审计 **121 标量字段 / 44 ops，mismatch 0 / computed 0**；`gov run check_access_scope --set resource_ref=table@*` → exit 0 allow；`data ... --set delimiter=,` → exit 0 | unified.py:176-242 |
| D11 | P2 | fixed | 保持关闭 | r4-fixes.md:17 与 r4-runtime.score.json 均引用实际 ref `20022e0a…`（r5 更正仍在） | 文档 |
| D12 | P1 | fixed | 保持关闭 | table 句柄 `--ref`/`--set` 两通道均 exit 1 且 `decision.resource_ref` 与句柄逐字相等；criteria 句柄同构 | unified.py:360-385 |
| D13 | P1 | fixed | 保持关闭 | 标准格式 pin 0.2.0 未装 → dispatch/doctor 均 exit 3、stdout 空 | bin/dataagent:64-73 |
| D14 | P1 | fixed | 保持关闭 | fresh data_root + enforce + 无策略 → doctor exit 3（`policy: none`）；`policy apply` 后 exit 0 `configured` | bin/dataagent:172-201 |
| D15 | P1 | fixed | 保持关闭 | `draft_acceptance_criteria --proposal-file`（单独）→ exit 0 draft；加空 `--input-file` 等价 | unified.py:142-155 |
| D16 | P1 | **partial** | **open→partial** | 无 pin 回退/doctor 一致性 fixed；合法空白 TOML pin 仍被忽略且 fail-open（见上） | bin/dataagent:53-63,143-152 |

## 4. 分数

`score_landing.py --result …/r7-tester-runtime.score.json`（完整输出 [r7-tester.score.txt](r7-tester.score.txt)）：

- 总分 **79.0 / C**，证据覆盖 100%；闸门 **GATE-P1（D16）+ GATE-CHECKLIST（#b9b374）**。
- 得 0：**A5.1**（28.32%）、**L2.1**（清单 partial）、**L2.4**（D16 边界语义）、**L4.2**（D3）。
- 硬规则：R01/R03/D1/V1/R13/R14 green，E1 na。
- 未关闭：P1 **D16**；P2 D2、D3。D5 关闭后清单 #99a1de 恢复 done，L2.1/L2.4 仍被 D16 压住。

独立评分原始加权为 **87.4**，被 GATE-P1 与 GATE-CHECKLIST 封顶至 **79.0**；与开发者自评 **93.1 / A / 无闸门** 的规则差异全部来自 D16：其自评将 D16 记为 fixed、#b9b374 记为 done，因而 L2.1=1、L2.4=1；独立探针在等价合法 TOML 输入上不成立。自评分数在其自身结果文件上可复现（scorer 无矛盾），但结论不成立。

## 5. 与上一轮对比

`round_diff.py r6-tester → r7-tester`（rc=0，无规则退化、无未复核）：

- 已修复 1：**D5**；部分修复 2：**D16**（open→partial）、D2；未修复 1：D3；保持关闭 12：D1、D4、D6–D15。
- 规则 1→0 退化：无；已判定→未测量：无。
- 清单 done 15/27 → 16/27（新增 r6 记录行新文本与 r7 记录行、移除 r3 旧记录行与旧 r6 行，均为 na 元数据；#99a1de done、#b9b374 partial）。
- 计分同为 79.0，但结构变化：D5 出闸、D16 由「误拒已装层」变为「忽略合法 pin 并 fail-open」——同一 id 的失败面收窄但未清除。

## 6. 开发者声明核对

| 声明（r7-fixes.md 节号） | 结论 | 依据 |
|-|-|-|
| D16 fixed：无该层 pin → 回退最高已装；dispatch/doctor 同序 | **已证实（仅此一半）** | `v=1` / 仅 governance pin → dispatch 0/32 行、doctor 0 |
| D16「版本不可读 → return 1」不撤销 D13 语义 | **不成立** | compact/缩进合法 TOML pin 0.2.0 未装：r6 exit 3 → r7 exit 0 执行 0.1.0（`D16_pre_post_control.txt`） |
| D16 黑盒仅覆盖「无 pin / 标准格式 pin」 | **部分成立**（覆盖缺口） | 未覆盖 compact/缩进 pin 与他版本已装组合；新增 `test_lock_unreadable_pin_falls_back` 把 fail-open 当预期 |
| D5 fixed：fits 计入换行，整条 stdout ≤32 KiB | **已证实** | 32,767→32,768 不截断；32,768→277 截断；40,000 长 id / Unicode 回归通过 |
| 五套测试 112/654/203/123/17 | **已证实** | 独立复跑同上 |
| 快照 8a7692b4…（67 文件）、vendored 4 份一致、bundle 无漂移 | **已证实** | snapshot.py、`cmp` ×3、quality_run |
| 自评 93.1 / A / 无闸门 | **仅在其自评结果上复现** | 独立加回 D16 → 79.0 / C / GATE-P1 + GATE-CHECKLIST |

另：r7-fixes 第 10 行仍把 D5 标为 P2，与 r5-review 起沿用的 P1 不一致；因 D5 已 fixed，不影响本轮闸门，但严重级记录应沿用独立判级。

## 7. 未测量

| 规则 | 测量需要的条件 |
|-|-|
| （无） | 45 条规则均判定或按 profile 明确 na；视觉验收（GUI 截图）不在本轮范围，未作为证据 |

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)

python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime \
  --fill docs/research/dataagent-2026-11-03/12-cli-build/r7-tester-runtime.score.json \
  --out docs/research/dataagent-2026-11-03/12-cli-build/r7-tester-runtime.quality.md
python3 skills/code-landing-quality/scripts/score_landing.py \
  --result docs/research/dataagent-2026-11-03/12-cli-build/r7-tester-runtime.score.json
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r6-tester-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r7-tester-runtime.score.json --fail-on-regression

# D16/D5 独立探针（/tmp/r7-tester 为真实三层 .venv 布局）
python3 .../r7-cli-review-evidence/d16_probe.py          # 无 pin / 标准 pin / compact / 缩进矩阵
python3 .../r7-cli-review-evidence/d16_two_versions.py   # 两版本均装：锁 0.1.0 被忽略
python3 .../r7-cli-review-evidence/d5_probe.py           # 真实 stdout 32767/32768/32769/40000
python3 .../r7-cli-review-evidence/cli_probe.py          # 50 项黑盒回归（D13_compact_toml 失败）
python3 .../r7-cli-review-evidence/management_probe.py   # link/setup/scrub/confirm 11 项
python3 .../r7-cli-review-evidence/runtime_probe.py      # D3 deadline 行为
```

HANDOFF: Developer | 让 `pinned_version` 区分「无该层条目」与「条目版本不可读」：用 TOML 解析（或同时接受紧凑/缩进键值）读取合法 pin；读到 pin 后按 D13 fail-closed（未装 → exit 3），不得回退最高已装；补 compact/缩进 pin × 已装/未装 × 双版本 的 dispatch+doctor 回归，并删除/改正 `test_lock_unreadable_pin_falls_back` 的 fail-open 预期，重新送审
VERDICT: FAIL
