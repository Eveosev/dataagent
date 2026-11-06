---
round: r8-reviewer
version: v0.1
date: 2026-11-06
subject: 统一 CLI 独立补充评审
plan: docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md r1
research: docs/research/dataagent-2026-11-03/12-unified-cli-research.md v0.3
rubric: 2.1 sha256:5e65f6c6006a
snapshot:
  dataagent-runtime: sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66
  dataagent-cli: sha256:6c65d4035daba8776aa26b672f9ab8bac96a8e993ca5f249a394b35978cd3a7c
facts_ref: implementation@ecf866dbfcac4714ef77fb9fe312fb2dc485010f
verdict: 不可验收
score: 79.0（C）
---

# 统一 CLI 独立补充评审

## 结论

**不可验收：79.0 / 100（C），GATE-P1（D16、D17）+ GATE-CHECKLIST。** 五套测试全部通过，但真实 Mint 包解析与新增 CLI 锁文件探针发现两个 P1 阻断。未修改产品源码、测试或 fixtures。

与 [此前独立验收结论](<r8-review.md#L19-L24>) 为**相同源码快照**。结论不同来自新增取证：此前矩阵只覆盖独立顶层包条目，没有实际 Mint 安装/清单解析，也没有依赖子表、引号键与转义字符串。下列结果不是测试失败或评分口径变更。

## 基线

| 项 | 独立实测 |
|-|-|
| HEAD | `ecf866dbfcac4714ef77fb9fe312fb2dc485010f` |
| 测试 | runtime 112 / data 654 / application 203 / governance 123 / cli 23，全通过；[运行记录](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/tests.json>) |
| 质量 | 重复率 2.13%（53/2489）；CC>10 28.32%，CC>25 0.0%；裸 except / 吞错 0 / 0；[机器报告](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/runtime.quality.md>) |
| 构建 | `sh -n`、`uv lock --check`、`uv build` 均 exit 0；wheel 22 members / 19 py / 0 pyc |
| bundle | 四份 vendored unified.py 与 runtime 源逐字节一致，三层 bundle 同步测试通过 |
| R13 | 实际 tag object `20022e0a…` → commit `fbe24d8…`；新 archive 快照 `78c93a64…`，67 文件；旧 stdin / `--list` 模式复跑通过 |
| Mint | 本机 `mint 0.1.26`；按 [仓库约定](</Users/payne/Vibe/AgentOS/AGENTS.md#L3-L17>) fetch 成功，checkout `698ac1b…` 比 upstream `29dd1b7…` 落后 7 commits；未 pull，以遵守不修改源码。使用实际 Mint 二进制与读取的 upstream 文件核对；接口 `--check` exit 0。本文不声称 checkout 已最新 |

## Findings（按严重级）

### P1 / D17 新增：CLI 清单缺 artifacts.layout，真实 Mint 无法解析，CLI 与 preset 安装链路被阻断

位置：[CLI mint.toml:15–16](<../../../../packages/capabilities/dataagent-cli/mint.toml#L15-L16>)；[preset mint.toml:21](<../../../../packages/capabilities/dataagent-s0/mint.toml#L21>)。

`[artifacts]` 已声明却只包含 `bin = "dataagent"`，缺少必需的 `layout`。Mint 的 [Artifacts 定义:599–604](</Users/payne/Vibe/AgentOS/packages/agent-kernel/mint/crates/mint-manifest/src/lib.rs#L599-L604>) 没有给该字段 serde 默认值；整个表缺省与表内字段缺省不是同一语义。

在两个独立临时 agent 项目中分别把 `dataagent/cli`、`dataagent/preset-s0` 设为实际仓库 path 依赖，执行 `mint lock --dry-run --offline -y`，两者均 **exit 1**：

```text
missing field `layout`
in `artifacts`
```

该失败发生在包清单解析，早于安装/解析 lock，不是网络、审批或 `.venv` 缺失；preset 因新增 CLI 依赖也无法解析。设计要求用户/Mint 能安装 CLI bundle，手工构造 `.mint/packages` 的分发器测试不能证明此验收项。

复跑：[install_probe.py](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/install_probe.py>)；[双项目实测](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/install-results.json>)。直接 `mint add --dry-run` 首次受临时项目无信任记录阻挡（exit 8），没有把它误报为清单失败；最终结论来自独立 lock 命令，未写用户信任台账。

### P1 / D16 部分修复：锁解析不区分 TOML 表作用域，合法 pin 的等价表示仍被误拒或绕过

位置：[dataagent:73–101](<../../../../packages/capabilities/dataagent-cli/bin/dataagent#L73-L101>)；调用位置 [dataagent:120–134](<../../../../packages/capabilities/dataagent-cli/bin/dataagent#L120-L134>)、[doctor:203–217](<../../../../packages/capabilities/dataagent-cli/bin/dataagent#L203-L217>)。

1. **真实 Mint 锁结构回归。** `awk` 把任何 `[` 行视为条目边界，但没有记录是否处于 `[[package]]`。`[[package.requires]]` 的 `name` 因此被当成包名；该依赖边只有 `req` 没有 `version`，首个匹配即被标为不可读，后续真实包 pin 不再读取。Mint 的 [LockDep 定义](</Users/payne/Vibe/AgentOS/packages/agent-kernel/mint/crates/mint-pack/src/lib.rs#L580-L588>) 与 [真实自动生成锁](</Users/payne/Vibe/AgentOS/workspace/offline-ql-test/mint.lock#L16-L35>) 均使用此结构。
2. **引号键 / 转义字符串。** 正则仅接受裸 `name|version`，字符串使用 `index` 切片，未解析 basic string 的转义。`"name"` / `"version"` 键或 `name="dataagent\u002fdata-layer"` 仍被视作无 pin，静默执行最高已装版本；转义 dot 的 version 则当原始目录名误拒。

独立目录安装 0.1.0 + 0.2.0，wrapper 记录实际 exec 目录后执行真实三层解释器，策略已配置；所有合法输入先经 `tomllib` 核对。矩阵节选：

| 输入 | 期望 | dispatch / doctor 实测 |
|-|-|-|
| standard / compact / indented / literal pin 0.1.0 | exec 0.1.0 | exit 0 / exec 0.1.0，原修复成立 |
| `[[package.requires]] name="dataagent/data-layer" req="^0.1.0"` 先于真实包 pin 0.1.0 | 忽略依赖边，exec 0.1.0 | **双双 exit 3，LOCK unreadable / 未 exec** |
| 仅依赖边提到 data-layer，无顶层 pin | 回退最高已装 0.2.0 | **双双 exit 3** |
| 引号键 pin 0.1.0 | exec 0.1.0 | **双双 exit 0，exec 0.2.0（锁被绕过）** |
| 转义 slash 的 name，pin 0.1.0 | exec 0.1.0 | **双双 exit 0，exec 0.2.0** |
| `version="0\u002e1.0"` | exec 0.1.0 | **双双 exit 3** |

**独立回归对照**：同一嵌套依赖锁，r7 bin **exit 0 / 32 行** → r8 bin **exit 3 / stdout 空**；[对照记录](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/nested-control.json>)。实际 `mint list --offline --json` 对同锁 **exit 0** 并正确识别已装 data-layer@0.1.0；[Mint 解析证据](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/mint-nested-list.json>)，不是仅凭 tomllib 推断。

复跑：[lock_probe.py](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/lock_probe.py>)；[全部 24 组合](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/lock-results.json>)；[嵌套锁输入](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/nested-requires.lock>)。坏 TOML 行尾残留也被成功执行，但无须依赖该负例即可证明上述合法输入阻断。

### P2 / D2 遗留：复杂度占比超阈

位置：[enforcement.py:255](<../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py#L255>)、[invoke.py:299](<../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L299>)。独立 quality_run 的 CC>10 LOC 占比 **28.32% > 7.3%**，仍 partial；CC>25 为 0%。

### P2 / D3 遗留：无默认 deadline，也不取消在途工作

位置：[unified.py:426–449](<../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L426-L449>)、[invoke.py:353–360](<../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L353-L360>)、[invoke.py:438–442](<../../../../packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L438-L442>)。探针测得 CLI deadline=None；显式 20 ms deadline 时 handler 运行 **130 ms**，仍返回 ok 且完成；[行为证据](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/probes/runtime-checks.json>)。沿用既有 P2 定级，不作为新增 P1。

## 已通过与清单

- D1、D4–D15 保持关闭；50 项旧 CLI + 11 项管理探针全部通过，见 [CLI 记录](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/cli-probes.log>)、[管理记录](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/management-probes.log>)。
- D5 真实 stdout 精确上限：JSON 32767 B → stdout **32768 B，不截断**；JSON 32768 / 32769 / 40000 B → **337 B，truncated**；长 40K 字符与 Unicode 句柄均受限，全文 id 保留，见 [边界结果](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/boundary-results.json>)。
- D10 三层标量分类审计 121 字段 / 44 ops，无判型或转换失败；D12 富 table / criteria 句柄按正确身份回填；D14 doctor 缺策略退 3、配置后退 0；D15 proposal-only 成功。
- 清单 **done 14 / partial 3 / na 10**：`#b9b374`（D16）、`#c9ab0b`（D17 清单不可解析）、`#916584`（D17 preset 安装链路）为 partial。评分 [完整结果](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/runtime.score.json>) / [评分输出](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/score.txt>)。
- `round_diff --fail-on-regression` exit 1，原因是新 D17 / L6.2 / 两条清单退化；未丢弃上轮缺陷，见 [轮次对比](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/round-diff.txt>)。D17 为新增发现，清单以前误判 done，非本轮新增代码回归；D16 嵌套表则有 r7/r8 源码对照证明回归。

## 开发者声明核对

| 声明 | 判定 |
|-|-|
| D16 compact / 缩进 / literal 原例修复、三态捕获、missing pin 不回退 | 已证实 |
| D16 全部关闭、清单全部完成 | **部分成立**；合法 TOML 等价形与嵌套表失败 |
| runtime 源零改动、五套全绿、质量/构建/bundle 数值 | 已证实 |
| 93.1 / A / 无闸门，可验收 | **不能维持**；相同源码新增 D16/D17 证据，独立 79.0 / C |

## 视觉验收

**UNVERIFIED。** 执行真实 macOS 截图命令 `screencapture -x`，exit 1，`could not create image from display`；未生成截图。此会话没有可用终端/浏览器截图工具，不用伪造终端渲染或无关 GUI 图代替实现截图。绝对路径证据：[失败记录](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/visual-unverified.txt>) / [原始 stderr](</Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/visual-capture.stderr.txt>)。

## 复跑命令

```sh
# cwd /Users/payne/Vibe/AgentOS
(cd packages/capabilities/dataagent-runtime && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)
python3 /Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/install_probe.py
python3 /Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/lock_probe.py
python3 skills/code-landing-quality/scripts/score_landing.py --result /Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/runtime.score.json
```

HANDOFF: Developer | 修复 CLI artifacts.layout 安装清单；锁解析区分 package 与嵌套表并支持或显式拒绝 TOML 等价形、不得回退绕过 pin；补真实 Mint 解析/安装与嵌套依赖锁回归，重新送审
VERDICT: FAIL
