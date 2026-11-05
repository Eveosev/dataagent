---
round: r8
date: 2026-11-06
subject: dataagent-runtime 统一 CLI 第 8 轮独立验收（dataagent-cli 分发器 D16 收口）
plan: docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md r1
rubric: 2.1 sha256:5e65f6c6006a
snapshot:
  dataagent-runtime: sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66
  dataagent-cli: sha256:6c65d4035daba8776aa26b672f9ab8bac96a8e993ca5f249a394b35978cd3a7c
facts_ref: dataagent-runtime@ecf866dbfcac4714ef77fb9fe312fb2dc485010f
verdict: 可验收
score: 93.1（A）
---

# 第 8 轮验收：统一 CLI（dataagent-runtime + 三层接入 + dataagent-cli 分发器）

## 0. 结论

**可验收：93.1 / 100（A），无闸门。** r7-review 的唯二阻断全部清除：

- **D16 fixed（P1）**：`pinned_version` 改为 awk TOML 子集解析并区分三态（0 有 pin / 1 无该层条目 / 2 条目版本不可读）。独立真实三层布局（`/tmp/r8-tester`，解释器 wrapper 记录实际 exec 目录）复跑 28 个矩阵组合 + 7 个补充边界：standard/compact/indented/literal/tab/注释/`[package]` 七种合法 TOML 写法的 pin 0.1.0 在双版本已装时 **dispatch/doctor 均落到 0.1.0**（r7 为 0.2.0）；四类写法的 pin 0.2.0 未装时 **dispatch exit 3 且未 exec、doctor exit 3 `MISSING pinned 0.2.0`**；条目无 version/空 version/坏引号/裸数字 → **双双 exit 3 fail-closed**；无锁/空锁/仅他层 pin → 回退最高已装（0.2.0）。r7/r8 同输入对照在独立环境复现：r7 bin **exit 0 / 32 行 / 执行 0.1.0** → r8 bin **exit 3 / 未执行**。
- **D5 fixed（P1）**：真实 dispatcher 精确字节边界成立；未截断 JSON 32,767 B → stdout **32,768 B** 不截断，32,768 / 32,769 / 40,000 B → **285 B** 且 `truncated=true`，40,000 字符长句柄 651 B、Unicode 句柄 1,033 B。

五套测试 **112 / 654 / 203 / 123 / 23** 全绿；16 条缺陷逐条复核，无未复核、无回归。未关闭仅 P2：**D2 partial**（CC>10 LOC 占比 28.32%，runtime 源本轮零改动）、**D3 open**（无默认 deadline）。无 P0/P1。

独立证据目录：[r8-cli-review-evidence](/Users/payne/.dsh/state/agent-teamwork/team/r8-cli-review-evidence/)（`d16_probe.py`、`d16_edges.py`、`d5_probe.py`、`cli_probe.py`、`runtime_probe.py`、`audit.py` 与全部 JSON/对照输出）。

## 1. 基线

| 项 | 实测 |
|-|-|
| HEAD / facts_ref | `ecf866dbfcac4714ef77fb9fe312fb2dc485010f`（与 r8-fixes 声明一致；父提交 `85e4618`） |
| 测试 | runtime **112 passed**（0.60s）｜data **654**（8.43s）｜application **203**（3.27s）｜governance **123**（1.17s）｜cli **23 OK**（7.80s） |
| 快照 | `dataagent-runtime@sha256:8a7692b4…`（67 文件，与 r7 相同）；`dataagent-cli@sha256:6c65d403…`（5 文件） |
| 重复率 / 复杂度 | 2.13%（53/2489 行；包内 20 / 跨包 33，15 组）｜CC>10 28.32%｜CC>25 0.0%｜裸 except 0 / 吞错 0 |
| bundle | 四份 vendored `unified.py` 与源 `cmp` 逐字节一致；`quality_run` bundle 漂移=一致 |
| 构建 | `uv lock --check` → Resolved 13 packages（rc=0）；`uv build` rc=0；wheel 22 members / 19 `.py` / unified 31,587 B / 0 `.pyc`；`sh -n bin/dataagent` rc=0 |
| 基线 tag | `dataagent-runtime-0.1.0` tag object `20022e0a…` → commit `fbe24d8…`；tag 内 runtime 快照 `78c93a64…`（67 文件）与 r3 验收态一致；tag 后 runtime 变更仅 `unified.py` + `/tests`（524+/47-，增量、旧模式测试保留）；`git fsck` 仅报 unreachable 旧 tag `8544568c`（D11 已记录的重建残留）→ **R13 green** 维持 |

## 2. 方案清单

27 条：**done 17 / partial 0 / not_done 0 / na 10 / waived 0**（完成率 100%）。

| 条目 | 判定 | 说明 |
|-|-|-|
| `W1共享内核实现#99a1de` stdout 摘要 32 KiB | **done** | D5 边界见 §3；`fits()` 计入换行（[unified.py:676-679](/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L676-L679)） |
| `W3分发器包实现#b9b374` mint.lock 优先 / 缺省最高版本 | **done** | r8 独立矩阵全部成立，见 §3 D16 |
| 其余 15 条 | done | 复跑证据见 [r8-tester-runtime.score.json](r8-tester-runtime.score.json) checklist |
| 10 条 na | na | 方案元数据/记录行（非需求） |

## 3. 缺陷

### D16（P1 → fixed）合法 TOML pin 被忽略 + fail-open

**独立环境**：`/tmp/r8-tester`，三层均为真实 `.venv`（symlink 到仓库包），每个版本目录的 `.venv/bin/python` 为 wrapper：先把自己所在目录写入 `exec.log` 再 exec 真实解释器，因此“实际执行了哪个版本”是观测值而非推断。策略经 `gov policy apply` 配置，`doctor` 基线 exit 0。

| mint.lock（均经 `tomllib` 验证为合法 TOML） | 已装 | dispatch `data list` | doctor |
|-|-|-|-|
| standard / compact / indented / literal / tab / 注释 / `[package]` pin **0.1.0** | 0.1.0 + 0.2.0 | **exit 0，exec `data-layer@0.1.0`，32 行** | **exit 0，报 `data-layer@0.1.0`** |
| standard / compact / indented / literal pin **0.2.0** | 0.1.0 + 0.2.0 | exit 0，exec `@0.2.0` | exit 0，报 `@0.2.0` |
| 四类写法 pin **0.2.0** | 仅 0.1.0 | **exit 3，stdout 空，未 exec 任何层** | **exit 3，`MISSING pinned 0.2.0`** |
| compact pin **0.2.0**（r7 fail-open 原例） | 仅 0.1.0 | r7 bin（`git show 85e4618`）**exit 0 / 32 行 / exec 0.1.0** → r8 **exit 3 / 0 行 / 未 exec** | r7 exit 0 → r8 exit 3 |
| 无锁 / 空锁 / 仅他层 pin / 他层同前缀名 | 0.1.0 + 0.2.0 | exit 0，exec 最高已装 `@0.2.0` | exit 0，报 `@0.2.0` |
| 条目无 version / 空 version / 坏引号 / 裸数字 | 0.1.0 + 0.2.0 | **exit 3，未 exec** | **exit 3，`LOCK unreadable`** |
| CRLF 行尾 pin 0.2.0 | 0.1.0 + 0.2.0 / 仅 0.1.0 | pin 生效 `@0.2.0` / **exit 3** | 同序 |
| version 在 name 前、无尾换行、键间注释 | 0.1.0 + 0.2.0 | pin 生效 `@0.1.0` | 同序 |
| 重复条目 0.1.0 后 0.2.0 | 0.1.0 + 0.2.0 | 首个匹配生效 `@0.1.0` | 同序 |
| gov 条目不可读 / gov pin 0.9.9 未装 | data 正常 | data 仍 exit 0 / exec 0.2.0 | **exit 3**（`LOCK unreadable` 或 `MISSING pinned`，策略探针 `governance layer unavailable`）；data pin 0.1.0 时 dispatch 仍 exit 0 exec 0.1.0 |

复跑：[d16_probe.py](/Users/payne/.dsh/state/agent-teamwork/team/r8-cli-review-evidence/d16_probe.py)（`D16_matrix.json`，28 组合）、[d16_edges.py](/Users/payne/.dsh/state/agent-teamwork/team/r8-cli-review-evidence/d16_edges.py)（`D16_edges.json`，7 组合）、`ctrl-r7.*` / `ctrl-r8.*`。实现位置：[bin/dataagent:68-118](/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L68-L118)（`pinned_version` 三态 + awk 子集解析）、[:114-118](/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L114-L118)（`pin_status` 以 `||` 捕获，避免 `if` 条件吞掉 die）、[:120-140](/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L120-L140)（`resolve_dir`）、[:193-240](/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L193-L240)（`doctor` 与策略探针）。结论：**D16 关闭**。

### D5（P1 → fixed）32 KiB 摘要上限（含换行）

真实 dispatcher + 三层 venv，`DATAAGENT_ENFORCEMENT_MODE=warn`：

| 输入 | 期望 | 实测 |
|-|-|-|
| 未截断 JSON 恰 **32,767 B** | 整条 stdout ≤32,768 且不截断 | exit 0，stdout **32,768 B**，无 `truncated` |
| 未截断 JSON 恰 **32,768 B** | ≤32,768 | exit 0，stdout **285 B**，`truncated=true` |
| 32,769 B / 40,000 B | 同上 | 285 B / 285 B，截断；全文在 `result_path` |
| 40,000 字符 criteria id / Unicode 40,000 字 | ≤32,768 | **651 B / 1,033 B**，截断，落盘全文保留完整 id |

复跑：[d5_probe.py](/Users/payne/.dsh/state/agent-teamwork/team/r8-cli-review-evidence/d5_probe.py)（`D5_json_32767.json`…`D5_json_40000.json`）；长句柄/Unicode 在 `cli_probe.py` 的 `D5_long_handle` / `D5_unicode_handle`，断言与落盘完整性均通过。

### 16 条缺陷复核

| ID | 级 | 状态 | 与上轮对比 | 复现（输入 → 期望 / 实际） | 位置 |
|-|-|-|-|-|-|
| D1 | P2 | fixed | 保持关闭 | quality_run 重复率 **2.13%**（≤3%） | sqlite.py 等 |
| D2 | P2 | partial | 保持 | CC>10 LOC 占比 **28.32%**（阈 7.3%）；CC>25 0.0% | [enforcement.py:255](/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py#L255) |
| D3 | P2 | open | 保持 | CLI `ctx.deadline=None`；显式 20 ms deadline 下 handler 仍跑 **125 ms** 并完成，`status=ok` | [invoke.py:353-360](/Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L353-L360) |
| D4 | P2 | fixed | 保持关闭 | 裸 except 0 / 吞错 0（AST） | unified.py 等 |
| D5 | P1 | fixed | 保持关闭 | 见上表；32,768 B JSON → stdout 285 B | unified.py:676-679,708-711 |
| D6 | P2 | fixed | 保持关闭 | `dataagent bogus` usage 含 `dataagent gov policy apply <file>`，无多余 `<layer> gov`，exit 2 | bin/dataagent:288-311 |
| D7 | P2 | fixed | 保持关闭 | `probe_detail_egress.py`：enforce 下 summary/full 的 statement 均 False（460 B） | unified.py |
| D8 | P2 | fixed | 保持关闭 | `--file nope.csv` → exit 2，无 traceback | unified.py:572-579 |
| D9 | P2 | fixed | 保持关闭 | 非法 confirmation → exit 2（4 validation errors）；坏 JSON → exit 2，无 traceback | governance cli.py:113-123 |
| D10 | P1 | fixed | 保持关闭 | 三层判型审计 **249 字段 / 121 标量 / 44 ops，mismatch 0 / computed 0**；`gov --set resource_ref=table@*` → exit 0 allow；`data --set delimiter=,`/`has_header=no` 生效；非法 enum/ref→exit 2 | unified.py:176-242 |
| D11 | P2 | fixed | 保持关闭 | `r4-fixes.md:17` 与 `r4-runtime.score.json` 均引用实际 tag object `20022e0a…`（r5 更正仍在） | 文档 |
| D12 | P1 | fixed | 保持关闭 | table 句柄 `--ref`/`--set` 两通道均 exit 1 且 `decision.resource_ref` 与句柄逐字相等；criteria 句柄同构 | unified.py:360-385 |
| D13 | P1 | fixed | 保持关闭 | 标准/compact pin 0.2.0 未装 → dispatch/doctor 均 exit 3、stdout 空、未 exec | bin/dataagent:120-140 |
| D14 | P1 | fixed | 保持关闭 | fresh data_root + enforce + 无策略 → doctor exit 3（`policy: none`）；`policy apply` 后 exit 0 `configured`；`--authorize` 缺策略 exit 3 | bin/dataagent:193-287 |
| D15 | P1 | fixed | 保持关闭 | `draft_acceptance_criteria --proposal-file`（单独）→ exit 0 draft；加空 `--input-file` 等价 | unified.py:142-155 |
| D16 | P1 | **fixed** | **partial→fixed** | 见上表；28+7 组合全通过，r7 fail-open 原例 r7 exit 0 执行 0.1.0 → r8 exit 3 | bin/dataagent:68-140,193-240 |

## 4. 分数

`score_landing.py --result …/r8-tester-runtime.score.json`（完整输出 [r8-tester.score.txt](r8-tester.score.txt)）：

- 总分 **93.1 / 100（A 可交付）**，证据覆盖 100%，**无闸门**。
- 得 0：**A5.1**（28.32%）、**L4.2**（D3 open）——均为 P2，不封顶。
- 不适用（出分母）：A10.2、L1.1、L1.2、L1.3、L2.5、L3.5、L4.1（profile=runtime 的 `may_na`）。
- 硬规则：R01/R03/D1/V1/R13/R14 green，E1 na。
- 未关闭：仅 P2 D2、D3；P0/P1 为 0，清单无 partial。

## 5. 与上一轮对比

`round_diff.py r7-tester → r8-tester`（rc=0，无回归、无未复核）：

- 已修复 1：**D16**（partial→fixed）；保持关闭 13：D1、D4–D15；部分修复 1：D2；未修复 1：D3。
- 规则 0→1：**L2.1、L2.4**；1→0（退化）：无；已判定→未测量：无。
- 清单：done 16/27 → **17/27**，无条目退化/增删；计分 79.0 → **93.1**，GATE-P1 与 GATE-CHECKLIST 均清除。
- `round_diff` 提示「源码快照未变：dataagent-runtime」——这是**预期且不矛盾**：本轮修复全部在 `dataagent-cli`（r7 未登记 cli 快照，r8 起登记 `6c65d403…`）。runtime 源零改动由 `git diff --stat HEAD~1..HEAD -- packages/capabilities/dataagent-runtime`（空）与相同 snapshot digest 双重确认；结论变化来自 cli 侧 D16 修复 + 独立探针全部通过，而非 runtime 判定漂移。

## 6. 开发者声明核对

| 声明（r8-fixes.md 节号） | 结论 | 依据 |
|-|-|-|
| D16 fixed：awk TOML 子集解析，compact/缩进/字面/注释/任意空白均与 `tomllib` 同解析 | **已证实** | 7 种合法写法 ×（双版本已装/未装）矩阵全部符合；CRLF、version-first、无尾换行同样成立 |
| 三态 0/1/2；`pin_status` 以 `\|\|` 捕获，die 不置于 if 条件 | **已证实** | 无 version/空 version/坏引号/裸数字 → dispatch+doctor exit 3；无该层条目仍回退最高已装 |
| r7/r8 同输入对照：r7 exit 0 执行 0.1.0 → r8 exit 3 | **已证实** | 用 `git show 85e4618:…/bin/dataagent` 在同环境独立复现（`ctrl-r7.*`/`ctrl-r8.*`） |
| 回归测试 cli 17→23，fail-open 测试期望改正 | **已证实** | 独立复跑 23 OK；`test_lock_unreadable_pin_fails_closed` 断言 exit 3 + 未执行；矩阵 5 条 |
| 五套 112/654/203/123/23 | **已证实** | 独立复跑同上 |
| runtime 源零改动（快照 `8a7692b4` 与 r7 相同） | **已证实** | snapshot 相同 + commit diff 空 + tag 后增量仅 unified/tests |
| quality 2.13% / 28.32% / 吞错 0 / bundle 一致 | **已证实** | 独立 `quality_run` 输出一致 |
| 自评 93.1 / A / 无闸门 | **已证实** | 独立评分同为 93.1 / A / 无闸门（本轮不再有规则分歧） |
| D2 partial、D3 open 留待后续轮 | **已证实** | 独立测量 28.32% 与 20 ms deadline 125 ms 完成 |

## 7. 未测量

| 规则 | 测量需要的条件 |
|-|-|
| （无） | 45 条规则均判定，或按 profile=runtime 的 `may_na` 判 na 并写明理由；视觉验收（GUI 截图）不在本轮方案范围，未作为证据 |

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)

python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-cli
python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime \
  --fill docs/research/dataagent-2026-11-03/12-cli-build/r8-tester-runtime.score.json \
  --out docs/research/dataagent-2026-11-03/12-cli-build/r8-tester-runtime.quality.md
python3 skills/code-landing-quality/scripts/score_landing.py \
  --result docs/research/dataagent-2026-11-03/12-cli-build/r8-tester-runtime.score.json
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r7-tester-runtime.score.json \
  docs/research/dataagent-2026-11-03/12-cli-build/r8-tester-runtime.score.json --fail-on-regression

# D16 / D5 / 黑盒 / D10 独立探针（/tmp/r8-tester 为独立真实三层 mint 布局）
python3 .../r8-cli-review-evidence/d16_probe.py     # 28 组合矩阵
python3 .../r8-cli-review-evidence/d16_edges.py     # 7 个补充边界
python3 .../r8-cli-review-evidence/d5_probe.py      # 真实 stdout 32767/32768/32769/40000
python3 .../r8-cli-review-evidence/cli_probe.py     # 50 项黑盒回归（0 失败）
python3 .../r8-cli-review-evidence/runtime_probe.py # D3 deadline
(cd packages/capabilities/dataagent-runtime && ../dataagent-{data,application,governance}/.venv/bin/python .../audit.py <layer>)
```

VERDICT: PASS
