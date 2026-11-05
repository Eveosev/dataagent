# r8 修复记录：r7-review D16 残留（合法 TOML 空白 pin 被忽略 + fail-open）处置

## 背景

r7 独立验收（[r7-review.md](r7-review.md)）判不可验收（79.0 / C，GATE-P1 + GATE-CHECKLIST `#b9b374`）：D5 已关闭，但 **D16 partial**——r7 修复「无 pin 回退」时把「条目版本不可读」并入「无 pin」一并 `return 1`，且 `pinned_version` 的 sed/grep 只认标准格式 `name = "…"`，导致两类 fail-open：

| mint.lock（均为合法 TOML，`tomllib.loads` 可解析） | 已装 | r7 实测（review §3） |
|-|-|-|
| compact `name="…"`/`version="0.1.0"` | 0.1.0 + 0.2.0 | pin 被忽略，dispatch/doctor 均解析 **0.2.0**（取最高已装） |
| 缩进 `  name = "…"` 形式 | 0.1.0 + 0.2.0 | 同上解析 **0.2.0** |
| compact `version="0.2.0"`（未装） | 仅 0.1.0 | **exit 0 执行 0.1.0**（r6 同输入 exit 3，D13 fail-closed 被撤销） |
| 条目无 version 字段 | 仅 0.1.0 | exit 0 回退（r6-review 期望 fail-closed） |

同时 r7 新增测试 `test_lock_unreadable_pin_falls_back` 把 fail-open 固化为期望行为。本轮（r8）按 handoff 修复并重新送审。自评 **93.1 / 100（A，可验收，无闸门）**（[r8.score.txt](r8.score.txt)）。

改动前快照：`/tmp/agentos-snapshots/pre-r8-20261106-051928.tar.gz`；改动后 `dataagent-runtime@sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66`（67 文件，runtime 源零改动，本轮全部改动在 dataagent-cli）。

## D16 fixed（P1 → 关闭）

**根因**（两层）：

1. `pinned_version` 用 `sed -n "/name = \"dataagent\\/$pkg\"/,/^\\[\\[/p" | grep -m1 '^version'` 解析——锚定 `^version` 且要求 ` = ` 定界，compact（`version="0.1.0"`）/缩进（`  version = …`）/字面字符串（`'…'`）等 `tomllib` 合法变体全部漏读 → 静默当「无 pin」回退最高已装；
2. r7 把「条目版本不可读」也并入 `return 1`（无 pin 回退），违反 r6-review 的清除条件「区分该层无 pin 与 pin 读取失败，不能撤销 D13 的 fail-closed」。

**方案**（[bin/dataagent:47-124](../../packages/capabilities/dataagent-cli/bin/dataagent#L47-L124)，POSIX sh + awk，无 Python 依赖）：

- `pinned_version` 改为 **awk TOML 子集解析**：表头行（`[[package]]` 等任意 `[`-开头）切分条目，`name`/`version` 键值接受任意前导缩进、`=` 两侧空白可有可无、basic（`"…"`）与 literal（`'…'`）字符串、行尾注释；首个匹配条目胜出。三态出口：**0**＝有可读 pin（stdout 输出版本）；**1**＝无 mint.lock / 无该层条目（回退最高已装）；**2**＝有条目但版本不可读（损坏锁）。
- `pinned_version` **不再内部 die**：实现过程中实测发现 die 置于 `if ver=$(pinned_version …)` 条件内会被 set -e 的条件豁免吞掉（子 shell exit 3 只使条件为假 → 回退执行），这正是又一类 fail-open——现由 `pin_status` 以 `ver=$(pinned_version "$pkg") || pin_rc=$?` 捕获三态，注释明确「不得置于 if 条件内」。
- `resolve_dir`（[:117-135](../../packages/capabilities/dataagent-cli/bin/dataagent#L117-L135)）：`pin_rc=2` → `die` exit 3（「without a readable version」）；`pin_rc=0` 且未装 → die exit 3（D13 语义原样保留）；`pin_rc=1` → 最高已装（D16 无 pin 回退语义保留）。
- `doctor_cmd`（[:203-217](../../packages/capabilities/dataagent-cli/bin/dataagent#L203-L217)）同序消费：`2` → `package …: LOCK unreadable` + `status=3` + `continue`（保持「报告不 die、汇总 exit 3」契约）；策略探针目录解析（[:243-252](../../packages/capabilities/dataagent-cli/bin/dataagent#L243-L252)）对 `2` 不回退（gov_dir 空 → `policy: governance layer unavailable` + status=3），不再探查被绕过的版本。

**黑盒复现**（真实三层 `/tmp/r8-mint`：app/gov 为仓库包软链 + 真实 venv；data 两个版本目录各以 wrapper 解释器记录实际 exec 目录后 exec 真实 data-layer venv python，dispatch 解析结果可直接观测；策略已 apply；完整矩阵 [D16_r8_matrix.json](/Users/payne/.dsh/state/agent-teamwork/team/r8-fix-evidence/D16_r8_matrix.json)、探针 `d16_probe_r8.py`）：

| mint.lock | 已装 | dispatch | doctor |
|-|-|-|-|
| 标准 / compact / 缩进 / 字面 pin 0.1.0 | 0.1.0 + 0.2.0 | **exit 0，实际 exec `data-layer@0.1.0`**（r7 为 0.2.0） | exit 0，报 `data-layer@0.1.0` |
| compact / 缩进 pin 0.2.0 | 0.1.0 + 0.2.0 | exit 0，实际 exec `data-layer@0.2.0` | exit 0，报 `@0.2.0` |
| 无锁 / 仅 pin 其他层 | 0.1.0 + 0.2.0 | exit 0，exec 最高已装 `@0.2.0` | exit 0，报 `@0.2.0` |
| 标准 / compact / 缩进 pin 0.2.0 | 仅 0.1.0 | **exit 3**，stdout 空、未 exec 任何进程 | **exit 3**，`MISSING pinned 0.2.0` |
| 条目无 version 字段 | 仅 0.1.0 | **exit 3**，「without a readable version」，未执行 | **exit 3**，`LOCK unreadable` |

r7/r8 同输入对照（[D16_pre_post_control.txt](/Users/payne/.dsh/state/agent-teamwork/team/r8-fix-evidence/D16_pre_post_control.txt)，即 r7-review 的 fail-open 原例）：compact pin 0.2.0 未装——r7 bin（85e4618）`data list` **exit 0 / 32 行（执行 0.1.0）**、doctor exit 0；r8 bin dispatch **exit 3 / 未执行**、doctor exit 3。

**回归测试**（cli 17→23 全 OK）：

- 修正 `test_lock_unreadable_pin_falls_back` → `test_lock_unreadable_pin_fails_closed`（fail-open 预期改正：exit 3 + 未执行）；
- 新增 `test_doctor_lock_unreadable_pin_fails_closed`（doctor 记 `LOCK unreadable` + `governance layer unavailable`，策略探针不回退）；
- 新增矩阵回归 `_pin_matrix` 共用体 ×5：`test_compact_pin_dual_versions_uses_pin`、`test_indented_pin_dual_versions_uses_pin`、`test_literal_pin_dual_versions_uses_pin`（compact/缩进/字面 pin 0.1.0 双版本已装 → dispatch 实际 exec 0.1.0 且 doctor 同报）与 `test_compact_pin_missing_exits_3`、`test_indented_pin_missing_exits_3`（pin 0.2.0 未装 → dispatch exit 3 未执行 + doctor exit 3 `MISSING pinned`）。

既有 17 项全部保持通过（含 D13 的 `test_pinned_version_missing_exits_3`/`test_doctor_pinned_version_missing_exits_3` 与 D16 无 pin 回退的 `test_lock_without_layer_pin_falls_back`）。

## 其余缺陷（按既定处置，非本轮闸门）

D2 partial（CC>10 28.32%，runtime 源本轮零改动）、D3 open（默认 deadline/在途取消），留待后续轮。

## 复跑命令与结果

```sh
cd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")       # 112 passed
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")         # 654 passed
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")  # 203 passed
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")   # 123 passed
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)                             # 23 tests OK
sh -n packages/capabilities/dataagent-cli/bin/dataagent                                                                              # rc=0
python3 skills/code-landing-quality/scripts/snapshot.py packages/capabilities/dataagent-runtime
# sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66  67 files（runtime 源零改动）
python3 skills/code-landing-quality/scripts/quality_run.py --repo . --package packages/capabilities/dataagent-runtime \
    --fill docs/research/dataagent-2026-11-03/12-cli-build/r8-runtime.score.json \
    --out docs/research/dataagent-2026-11-03/12-cli-build/r8-runtime.quality.md
python3 skills/code-landing-quality/scripts/score_landing.py --result …/r8-runtime.score.json   # 93.1 / A / 无闸门
python3 skills/code-landing-quality/scripts/round_diff.py …/r7-runtime.score.json …/r8-runtime.score.json
# 无回归、无未复核；未修复 1（D3）、部分修复 1（D2），其余 14 条保持关闭
```

机器测量（[r8-runtime.quality.md](r8-runtime.quality.md)）：重复率 2.13%、裸 except 0 / 吞错 0、CC>10 28.32%（D2 partial，与 r7 持平——runtime 源零改动）、CC>25 0.0%、bundle 一致。

## 变更文件

- 产品：`packages/capabilities/dataagent-cli/bin/dataagent`（`pinned_version`/`pin_status`/`resolve_dir`/`doctor_cmd`）
- 测试：`packages/capabilities/dataagent-cli/tests/test_dispatcher.py`（17→23）
- 记录：`12-cli-build/r8-fixes.md`、`r8-runtime.score.json`、`r8-runtime.quality.md`、`r8.score.txt`、README r8 行（含登记 r7-review/r7-tester 记录）、build-plan r8 行
