---
round: r9
date: 2026-11-06
subject: 统一 CLI 独立验收
plan: docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md r1；研究设计 v0.3
rubric: 2.1 sha256:5e65f6c6006a28192894e531c362bfbf668e43bde338974f3ab1b0342a6d4f1c
snapshot:
  dataagent-runtime: sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66
  dataagent-cli: sha256:7e5277c313bb834161b15014f16040c82805b325dc0217cb20b80306307a811e
facts_ref: implementation@92fcd268feab58c9606a9a417fd1fe326184bbcb；实际 Mint 0.1.26
verdict: 不可验收
score: 79.0（C）
---

# 统一 CLI 独立验收

## 0. 结论

**不可验收：79.0 / 100（C），GATE-P1（D16）+ GATE-CHECKLIST（`#b9b374`）。**

- **D17 已修复**：真实 Mint 安装 preset、CLI 与三层包成功；安装后的三层独立 frozen 环境、doctor、list 与 CSV 解析也通过。
- **D16 部分修复，并新增同类回归**：原 Reviewer 24 组合全部通过；但实际 Mint 接受的等价 TOML 表头、转义键、inline package 数组仍绕过 pin，多行字符串 pin 被误拒。quoted 表头锁定未安装版本，同输入 **r8 exit 3 → r9 exit 0 执行 0.2.0**。
- 五套测试 **112 / 654 / 203 / 123 / 36** 全绿，不能替代上述语义探针。
- P2 仍为 D2 partial、D3 open。未修改产品源码、测试或 fixtures；只新增验收证据与记录。

证据：[独立证据目录](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/>)、[独立评分](<r9-reviewer-runtime.score.json>)、[机器质量报告](<r9-reviewer-runtime.quality.md>)、[评分输出](<r9-reviewer.score.txt>)、[轮次对比](<r9-reviewer-round-diff.txt>)。

## 1. 冻结基线与仓库约定

| 项 | 实测 |
|-|-|
| 实现 HEAD | `92fcd268feab58c9606a9a417fd1fe326184bbcb`，初始目标包无未提交修改；仅两个既存 RSI 子模块 dirty |
| runtime 快照 | `8a7692b4…`，67 文件，与 r8 相同；本轮 runtime commit diff 为空 |
| CLI 快照 | `7e5277c3…`，6 文件，与开发者声明相同 |
| 五套测试 | runtime 112（0.49s）、data 654（8.34s）、application 203（3.38s）、governance 123（1.15s）、CLI 36（14.126s）；全部 exit 0，CLI 两项真实 Mint 测试未 skip |
| 独立 quality_run | runtime 独立 venv 112 passed；重复率 2.13%（53/2489）；CC>10 28.32%，CC>25 0.0%；裸 except / 吞错 0 / 0；bundle 一致；rubric/scorer 副本一致 |
| 构建 | `uv lock --check` exit 0；`uv build` exit 0；真实 wheel 22 members / 19 `.py` / 0 `.pyc`；`sh -n` exit 0 |
| vendored | 四份 vendored shared CLI 与源文件 `cmp` 逐字节一致 |
| 发布基线 | tag object `20022e0a…` → commit `fbe24d8…`；重新 archive 后 runtime 快照 `78c93a64…`（67 文件）；旧 stdin / JSON `--list` 保持；R13 green |

前置同步按 [AGENTS.md:3–17](</Users/payne/Vibe/AgentOS/AGENTS.md#L3-L17>) 执行 fetch，exit 0；agent-kernel HEAD `698ac1b2e89a8199c69f415d090d03167d24818e`，origin/main `29dd1b7611390eadc471d4b013214cee78efbf2f`，落后 7 commits；iface check exit 0。遵守本次「不改源码」，没有 pull/改动该 checkout。单独核对上游与 HEAD 的 Mint CLI、manifest、pack、dirs 取证路径差异为空；本报告运行事实来自实际安装的 Mint 0.1.26，不宣称整个 kernel 为最新。见 [同步日志](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/kernel-sync.log>)、[取证路径上游 diff](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/upstream-contract-diff.log>)。

## 2. P1 阻断：D16 未关闭

### 等价 TOML pin 仍失效

实现只把去空白后的裸 `[[package]]` / `[package]` 识别为包条目；quoted keys 仅剥引号不解码；value scanner 只处理一行。

位置：[分发器:183–205](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L183-L205>)、[字符串解析:113–163](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L113-L163>)、[dispatch 回退:231–244](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L231-L244>)、[doctor 回退:314–332](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L314-L332>)。

每个合法输入先经 stdlib tomllib 确认，并以真实 `mint list --offline --json` 复核：Mint **exit 0，锁中 bundle pin 为 0.1.0**。独立布局安装 0.1.0 和 0.2.0；`.venv/bin/python` wrapper 先记录自身路径再 exec 真实解释器，因此下表版本是实际 exec 观测，不是仅据 stdout 推断。

| 输入（其余字段完整且同 canonical） | Mint / tomllib 期望 | r9 dispatch / doctor |
|-|-|-|
| canonical、单行 triple-quote | 0.1.0 | 双双 exit 0、exec 0.1.0 |
| `[["package"]]`、`[['package']]`、`[["pack\u0061ge"]]` | 0.1.0 | **双双 exit 0、exec 0.2.0，忽略 pin** |
| `"\u006eame" = "dataagent/data-layer"` | 0.1.0 | **双双 exit 0、exec 0.2.0，忽略 pin** |
| `"vers\u0069on" = "0.1.0"` | 0.1.0 | **双双 exit 3，误拒已装合法 pin** |
| 多行 basic name / version、多行 literal、basic continuation | 0.1.0 | **双双 exit 3，误拒已装合法 pin** |
| `package = [{name="…", version="0.1.0", …}]` | 0.1.0 | **双双 exit 0、exec 0.2.0，忽略 pin** |

补充矩阵 **24 项中 20 项失败**。原 Reviewer standard / compact / indented / literal / quoted keys / escaped values / nested requires / invalid suffix / empty lock **24/24 全通过**，因此原修复是部分成立，不能据原例判 D16 fixed。

完整原输入与 Mint 输出：[补充探针](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/lock_edges.py>)、[补充结果](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/lock-edges-results.json>)、[24 组合原探针结果](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/lock-results.json>)。

### 新回归：quoted 表头撤销 missing-pin fail-closed

同目录安装 0.1.0 + 0.2.0，合法锁内容为：

```toml
v = 1
[["package"]]
name = "dataagent/data-layer"
version = "0.9.9"
kind = "bundle"
source = "path+file:///fixture"
integrity = "h1:fixture"
cksum = ""
```

实际 Mint 可解析并报告 0.9.9 未安装。以 `git show ecf866d:…/bin/dataagent` 取出 r8，和 r9 对同一输入、同一环境运行：

| 命令 | r8 | r9 | 期望 |
|-|-|-|-|
| data list | **exit 3，stdout 空，未 exec** | **exit 0，exec 0.2.0，32 行** | exit 3，未执行未锁定版本 |
| doctor | **exit 3，data-layer 未 exec** | **exit 0，报 / exec 0.2.0** | exit 3，MISSING pinned |

canonical missing pin 在两轮仍均 exit 3；quoted 表头是 r9 表作用域新规则引入的 fail-open 回归，沿用 D16，不另编缺陷 id。见 [前后对照](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/lock-control-results.json>)、[对照日志:1–12](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/lock-control.log#L1-L12>)。

**阻断要求**：不能把未支持但合法的包表示静默当「无 pin」。按真实 Mint TOML 语义正确读取 package/name/version，或为无法排除 pin 的表示明确 fail-closed；合法、已安装的 pin 仍须可用。补上 quoted/escaped 表头、escaped keys、多行字符串、inline package 数组和 missing-pin 同输入前后回归。

## 3. D17 已关闭：真实 Mint 安装与执行

[CLI 清单:15–19](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/mint.toml#L15-L19>) 补 `layout = "any"`；[preset 依赖:16–21](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-s0/mint.toml#L16-L21>) 未破坏。

独立临时 MINT_HOME 的 trust ledger，不复用用户信任写入路径；仅复用本机 offline cores/cache/index。实测：

1. 原「fresh path dependency + lock --dry-run」分别 CLI / preset 不再报 missing layout，而是 **exit 2：path 依赖尚无 lock 条目，须先 add/install**。这是 Mint lock 不安装的正常语义，不能误写 fresh 原例 exit 0。
2. `mint init --name r9-cli-independent --offline -y` → **exit 0**。
3. `mint add <preset path> --offline -y` → **exit 0**，安装 dataagent/{preset-s0,cli,data-layer,application-layer,governance-layer}@0.1.0。
4. add 后 `mint lock --dry-run --offline -y` → **exit 0**。
5. 安装的 CLI executable 与被测源逐字节相同。三层安装副本各自 `uv sync --frozen`，不借用 repo venv；data/gov Python 3.12、app Python 3.13。
6. installed CLI `link` / `policy apply` / `doctor` → **exit 0**；`list` → **32 / 13 / 6 行**；`parse_delimited_file --file orders.csv --set delimiter=,` → **exit 0，row_count 2**。

初次 `uv sync --offline` 因本机缓存无 pinned pydantic-core wheel 失败；随后联网 frozen 同锁安装成功。未改锁文件、依赖或源码，不将缓存缺失归为产品缺陷。实际 Mint 安装阶段全程 offline 成功。

见 [安装探针](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/install_probe.py>)、[继续执行探针](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/install_continue.py>)、[安装与执行结果](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/install-results.json>)、[add 结果](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/chain-add.json>)、[post-add lock](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/chain-lock.json>)。

## 4. P2 遗留与旧缺陷复核

| ID | 级 | 状态 | 独立复核 |
|-|-|-|-|
| D2 | P2 | partial | CC>10 LOC **28.32% > 7.3%**；[enforcement.py:255](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py#L255>)，本轮 runtime 未改 |
| D3 | P2 | open | CLI deadline 为 None；显式 20 ms deadline 下 handler **130 ms 后仍 ok 且 completed=true**；[context:426–449](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L426-L449>)、[invoke:353–360](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L353-L360>)；[行为证据](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/runtime-probes.log>) |
| D1、D4 | P2 | fixed | 重复率 2.13%；裸 except / 吞错 0 / 0 |
| D5 | P1 | fixed | 含换行 32 KiB 精确边界、40K/Unicode 句柄、全文持久化通过；[fits:676–679](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L676-L679>)；[精确边界证据](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/boundary-results.json>) |
| D6–D9 | P2 | fixed | usage 正确；summary/full 外发内容剥离；missing file / invalid confirm / bad JSON usage2，无 traceback |
| D10 | P1 | fixed | 三层 249 字段 / 121 标量 / 44 ops，判型 mismatch0 / coerce failure0；delimiter/bool/resource_ref 成功 |
| D11 | P2 | fixed | 实际 tag20022e0a 与带日期更正记录一致；archive digest 复算 |
| D12 | P1 | fixed | TableRef / CriteriaRef 的 --ref / --set 控制通过，无 schema extra_forbidden |
| D13 | P1 | fixed | 原 canonical 与 compact missing-pin 输入仍拒3；新增 quoted-header 同类回归归 D16，不能外推所有等价形都安全 |
| D14 | P1 | fixed | fresh enforce root doctor3/no policy；authorize3；policy apply 后 doctor0 |
| D15 | P1 | fixed | proposal-only 与空 input control 均 draft 成功0；stage1 needs_input |
| D16 | P1 | partial | 原24组合修复；补充20失败；quoted missing-pin 回归 |
| D17 | P1 | fixed | 见 §3，实际 Mint 安装/执行全链路通过 |

[CLI 50 项回归日志](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/cli-probes.log>)：失败 0；[management 11 项](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/probes/management-checks.json>)：失败 0。17 条缺陷全部保留、全部复核。

## 5. 清单、评分与轮次对比

- 提取清单 28 条：**done16 / partial1 / na11**（有效需求 17 条，完成率 94.1%）。唯一 partial：`W3分发器包实现#b9b374`。
- 独立分数 **79.0 / C**，证据覆盖 100%。硬规则 R01/R03/D1/V1/R13/R14 green，E1 按 runtime profile 为 na。
- 得 0：A5.1、L2.1、L2.4、L4.2；未关闭 P1 D16、P2 D2/D3。
- 对比 r8 Reviewer supplement：D17 open→fixed、L6.2 0→1；D16 partial 保持，D2/D3 保持；其余 13 条保持关闭。runtime 快照不变是预期：改动在 CLI，评分变化来自 CLI 清单和锁解析取证。
- `round_diff --fail-on-regression` exit 0，仅表示**缺陷状态/规则/清单**未退化；工具不会理解同一 partial 缺陷中新出现的输入级回归。§2 的 quoted missing-pin 前后对照明确证明行为回归，不能引用 rc0 宣称「无回归」。

## 6. 开发者声明核对

在独立评分完成后读取 [修复记录](<r9-fixes.md>)：

| 声明 | 结论 | 依据 |
|-|-|-|
| D17 layout / init+add+post-addlock 成功 | 已证实 | 实际 Mint 安装与 installed bundle 执行通过；fresh lock 先要求安装，语义须注明 |
| D16 原 Reviewer 24 组合全 PASS | 已证实 | 原脚本仅改证据输出目录，24/24 |
| D16 fixed、合法 TOML 等价形都正确 | **部分成立** | quoted table / escaped key / multiline / inline array 20/24 失败，实际 Mint 接受 |
| D13 fail-closed 原样保留、无回归 | **部分成立** | canonical 缺 pin 保持；quoted header missing pin r8exit3→r9exit0exec0.2 |
| 五套 112/654/203/123/36；runtime 零改动；质量/构建/cmp 一致 | 已证实 | 独立复跑及快照相同 |
| 自评 93.1 / A / 无闸门 | **不成立** | 独立 D16 partial / #b9b374 partial，79.0 / C，两闸门 |
| D2/D3 遗留 | 已证实 | 独立复杂度与 deadline 探针复现 |

## 7. 真实截图与视觉验收范围

真实桌面截图命令 `screencapture -x …/cli-desktop.png` **exit 1**，错误 `could not create image from display`；未生成桌面图片。[失败证据](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/visual-capture.stderr.txt>)。

随后用实际 CLI `data list` 子进程获取 32 行原样 stdout，Google Chrome headless 打开该纯文本文件；断言浏览器 body 与 CLI stdout 完全一致后用 Playwright capture，并已读取截图检查。无 mockup / 合成表格 / 替代产品 UI。

**截图绝对路径**：[cli-actual-output.png](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/cli-actual-output.png>)；[截图命令与原样匹配记录](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/visual-evidence.json>)。

视觉判定：**CLI stdout 原样浏览器渲染已验证**（每 op 一行、包含编号/recheck/two_phase，32 行可见）；**原生终端/桌面呈现未验证**（display capture unavailable）。任务不含 GUI shell 改动，没有把当前 Harness 页面当成该 CLI 的验收对象。

## 8. 复跑入口

```sh
cd /Users/payne/Vibe/AgentOS
E=/Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence
# 五套命令见对应 *-tests.log；quality_run 未 skip 测试或重复率
python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime --fill "$E/runtime.score.json" --out "$E/runtime.quality.md"
python3 "$E/lock_probe.py"         # 原24组合
python3 "$E/lock_edges.py"         # Mint + tomllib 参考，20失败
python3 "$E/lock_controls.py"      # r8/r9 quoted missing-pin对照
python3 "$E/install_probe.py"      # 独立 Mint init/add/lock；若 offline wheel缓存不全，继续下一行
python3 "$E/install_continue.py"   # 相同安装目录，frozen联网补wheel并执行三层
python3 "$E/d5_boundary.py"
python3 "$E/probes/cli_probe.py"
python3 "$E/probes/management_probe.py"
# 所有产物有 command/cwd/exit 与真实 stdout/stderr；评分后方读取开发者声明
python3 skills/code-landing-quality/scripts/score_landing.py --result "$E/runtime.score.json"
python3 skills/code-landing-quality/scripts/round_diff.py \
  /Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/runtime.score.json \
  "$E/runtime.score.json" --fail-on-regression
```

HANDOFF: Developer | 修复 D16 quoted/escaped 表头与键、多行/inline package 等价表示的 pin 解析和 missing-pin fail-open；补真实 Mint differential 回归后重新送审
VERDICT: FAIL
