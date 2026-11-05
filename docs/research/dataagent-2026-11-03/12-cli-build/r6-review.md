---
round: r6
date: 2026-11-06
subject: dataagent-runtime 第 6 轮独立验收
plan: docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md r1（research v0.3）
rubric: 2.1 sha256:5e65f6c6006a28192894e531c362bfbf668e43bde338974f3ab1b0342a6d4f1c
snapshot:
  dataagent-runtime: sha256:4c55f3057bd9dc22b399ebab400f3791848f21bb1e9ee1830981cc35205faef0
facts_ref: dataagent-runtime@b12887fcb7208d672c59781e676be8e21ce40cf8
verdict: 不可验收
score: 79.0（C）
---

# 第 6 轮独立验收：统一 CLI

## 0. 结论

**不可验收：79.0 / 100（C），GATE-P1 + GATE-CHECKLIST。** 五套测试通过，r5-review 的五项原探针全部通过；但等价边界探针发现 **D5 仍 partial（P1）**，以及 r6 新引入的 **D16（P1，open）**。D12–D15 fixed；D1/D4/D6–D11 保持关闭；D2 partial、D3 open 为既定非阻断 P2。无 P0。

成果：[独立评分](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-tester-runtime.score.json>)、[评分器输出](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-tester.score.txt>)、[机器质量报告](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-tester-runtime.quality.md>)；全部原始探针证据保存在工作目录下的 [r6-cli-review-evidence](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/>)。

## 1. 冻结输入与基线

| 项 | 实测 |
|-|-|
| 被测 commit | `b12887fcb7208d672c59781e676be8e21ce40cf8`，验收前后未变 |
| runtime 快照 | `sha256:4c55f3057bd9dc22b399ebab400f3791848f21bb1e9ee1830981cc35205faef0`，67 文件；验收结束重算一致 |
| 实现计划 | [实现计划](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md#L1-L35>) r1；开始时 sha256 `65ed50fc93eceb9beb30afca2bd459b3d801384e014ef5a68141d40b02293e7e`（之后仅登记评审索引） |
| 原设计 | [统一 CLI 调研](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-unified-cli-research.md>) v0.3，sha256 `8263794105f7ecdbafcde90f7dd1b36d63164c1d1c3ac4f13bb51486325a3a4f` |
| rubric | 2.1，sha256 `5e65f6c6006a28192894e531c362bfbf668e43bde338974f3ab1b0342a6d4f1c`；scorer/bundled 副本一致 |
| runtime 测试 | **111 passed**，quality_run 内完整运行，未 skip |
| data / application / governance | **654 / 203 / 123 passed** |
| dispatcher | **15 tests OK** |
| 原始测试日志 | [runtime](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/dataagent-runtime-tests.log#L18>) / [data](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/dataagent-data-tests.log#L50>) / [application](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/dataagent-application-tests.log#L29>) / [governance](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/dataagent-governance-tests.log#L22>) / [dispatcher](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/dataagent-cli-tests.log#L3-L5>) |
| 重复率 / 吞错 | **2.13%（53/2486）** / 裸 except 0、吞错 0 |
| 复杂度 | CC>10 LOC **28.24%**（阈 7.3%）；CC>25 **0.0%**（达标）；无超长函数/模块 |
| bundle | runtime/data/application/governance 四份 vendored unified 与源逐字节一致；同步测试通过 |
| 构建 | `uv lock --check` exit 0，13 packages；`uv build -o /tmp/r6-tester-dist` exit 0；wheel 22 文件 / 19 `.py` / unified 31,289 B / 0 `.pyc` |
| R13 | annotated tag `dataagent-runtime-0.1.0` = `20022e0a962ecd42fd575bd9b8872ca2f11c3f99` → commit `fbe24d8f4263513a711fc96126ded588b9650f2c`；归档 runtime 重算 `sha256:78c93a64776a5dbc4ad45fd9c3f9f849d5d105b300f08179445fcaa2f9e1f400`（67 文件） |

独立性：本轮产品源码、测试、fixtures 零修改；探针与运行数据只写临时目录，归档证据与评审文档不属于产品源码。在评分完成后才读取开发者本轮修复记录与自评；共享线程已有声明只当待核对主张，不作为证据。

仓库前置约定：已执行 kernel `git fetch origin --prune`，本地 HEAD `698ac1b2e89a8199c69f415d090d03167d24818e`，`HEAD..@{u}` **7 commits behind**。本角色受“不修改源码”约束，没有 pull/sync 更新 kernel。本轮不作“当前 Mint/iface 最新契约对齐”结论；评价范围是冻结的 CLI 方案及本地 r6 制品。R14 仅评 runtime 与 vendored dataagent-contracts 同步。参见 [AGENTS](</Users/payne/Vibe/AgentOS/AGENTS.md#L3-L23>)。

## 2. 按严重级列出的 blocking findings

### P1 — D16 新增：存在锁文件但该层没有 pin，合法回退被误判环境缺失

位置：[dataagent:51–55](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L51-L55>)、[dataagent:63–65](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L63-L65>)；doctor 的不同处理见 [dataagent:135–145](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L135-L145>)。

复现：真实三层 `@0.1.0` 包及解释器已安装、策略已配置，锁文件只含 `v = 1`，或只含 governance 的 pin，没有 data-layer 条目。执行 `dataagent data list`：**exit 3、stdout 空**，错误声称 `mint.lock pins dataagent/data-layer without a readable version`。但同工作区 `doctor` **exit 0**。期望按 [计划:26](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md#L26>) 的“缺省取最高版本”正常列出 32 项。

原因：POSIX pipeline 的状态来自最后一个 sed；当上游没有匹配时最后 sed 仍 exit 0，`if ver=$(pinned_version ...)` 因而成功且值为空。r6 新增的空值分支把“无 pin”误当“有 pin 但不可读”。**同输入 pre-r6 exit 0 / 32 行，r6 exit 3 / 0 行**，已从 `b12887f^` 归档分发器作差分复证。这是 r6 新引入的合法客户端回归，不是缺包。

同根因旁证：标准 TOML 的 `name="..."` / `version="0.1.0"` 或缩进形式，在 Python tomllib 中解析为相同有效 pin；已装版本仍 exit 3。原精确空格形式同 pin exit 0。此格式局限早已存在，但无 pin 分支的拒绝是本轮回归。

证据：[前后版本对照](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D16_previous_control.json>)、[无 pin dispatch](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D16_dispatch_empty_lock.json>)、[同目录 doctor](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D16_doctor_empty_lock.json>)、[仅其他层 pin](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D13_other_layer_pin.json>)、[compact 合法 pin](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D13_compact_installed.json>)。复跑脚本：[followup_probe](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/followup_probe.py>)。

清除条件：区分“该层不存在 pin”和“pin 读取失败”，无 pin 恢复最高已装回退；读到有效 pin 后继续拒绝未安装锁定版本。补无条目/仅其他层条目/compact/缩进、doctor 与 dispatch 一致性回归，不能撤销 D13 的 fail-closed 修复。

### P1 — D5 部分修复：32 KiB 摘要检查漏算 stdout 换行

位置：[unified:674–678](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L674-L678>)、[unified:776](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L776>)。

本轮 40 KiB 单句柄 **已修复**：真实 gov 草稿，`existing_criteria_id=criteria:` + 40,000 个 x → stdout **656 B**（因本轮临时目录长度比开发者 634 B 多 22 B）；完整 40,009 字符 ID 保留。Unicode 40,000 个“界”的合法 ID（120 KiB UTF-8）→ **1038 B**。原 80×500B samples → **1524 B**。

但新增精确边界探针：真实 `draft_acceptance_criteria`，固定 ID `criteria:exact-boundary`，合法 proposal 的 `expected_outputs` 为 32,200 个 x。**exit 0，序列化 JSON 32,768 B，真实 stdout 32,769 B，data 未裁剪**。`fits()` 允许 JSON 恰好等于上限，随后 print 又加 `\n`。因此 [原设计:175](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-unified-cli-research.md#L175>) 与 [计划:13](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md#L13>) 的 stdout ≤32 KiB MUST 仍未完全成立。

证据：[真实精确边界](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D5_exact_real_stdout.json#L11-L14>)、[独立内核边界/超时](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/runtime-checks.json>)、[40 KiB 句柄](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D5_long_handle.json>)、[Unicode 句柄](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D5_unicode_handle.json>)、[原 samples](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/original-sample-overflow.log>)。

D5 沿用 r5 Reviewer 独立结果的 **P1**，不采纳开发者未说明依据的 P2 降级：未满足明确 MUST，只溢出 1 字节也不能把清单判 done。修复可为最终完整 stdout 预算预留换行或统一精确写入；补 32767/32768/32769 B 和 Unicode 字节边界。无需降低 rubric 阈值。

## 3. P2 已知非阻断缺口

| ID | 状态 | 复现 | 位置 |
|-|-|-|-|
| D2 | partial | CC>10 **28.24% >7.3%**（r5 26.56%）；CC>25 0.0% 达标 | [enforcement:255](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py#L255>)、[unified:176](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L176>) |
| D3 | open | CLI ctx.deadline=None；人为注入未来 **20ms** deadline 的 120ms handler，实测 **130ms / status ok / handler completed**，未中断 | [unified:426–449](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L426-L449>)、[invoke:353–360](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L353-L360>)、[invoke:438–442](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L438-L442>) |

D3 为既定方案外能力，不因本轮探针而扩大为新的 MUST。证据：[runtime_probe](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/runtime_probe.py>)、[机器报告](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-tester-runtime.quality.md>)。

## 4. D1–D15 全量复核

| ID | 级 / 状态 | 本轮独立实测及证据 | 位置 |
|-|-|-|-|
| D1 | P2 fixed | 2.13%（53/2486），D1 green | [sqlite:101](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/adapters/sqlite.py#L101>) |
| D2 | P2 partial | 28.24% / 0.0%，见 §3 | [enforcement:255](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py#L255>) |
| D3 | P2 open | 默认空 deadline，20ms 仍运行130ms，见 §3 | [invoke:353](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L353>) |
| D4 | P2 fixed | AST 裸 except / 吞错 **0 / 0** | [质量报告](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-tester-runtime.quality.md>) |
| D5 | P1 partial | 原 samples、40 KiB 单句柄通过；精确边界 **32769B**，见 §2 | [unified:674–678](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L674-L678>) |
| D6 | P2 fixed | bogus → exit2，usage 无多余 layer，含正确 gov policy | [dataagent:224](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L224>)；[探针](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D6_usage.json>) |
| D7 | P2 fixed | enforce summary/full 均剥离 statement/fields | [unified:456–476](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L456-L476>)、[原探针输出](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/original-egress.log>) |
| D8 | P2 fixed | 缺 CSV → exit2 usage，无 traceback | [unified:572–579](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L572-L579>)；[探针](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D8_missing_file.json>) |
| D9 | P2 fixed | 非法 confirmation / malformed JSON / 缺顶层 criteria_id → exit2；合法确认 r1→active r2，重放/越权→1 | [gov cli:115–124](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-governance/src/dataagent_governance/interfaces/cli.py#L115-L124>)；[缺字段探针](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D9_missing_top.json>) |
| D10 | P1 fixed | resource_ref table@* →0 allow；delimiter逗号→0,row_count2；has_header=no→0,row_count3；三层121标量字段/44 ops、0分歧/0失败 | [unified:176–242](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L176-L242>)；[独立判型](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/audit.py>) |
| D11 | P2 fixed | 实际 tag object `20022e0a` = 两处已审计更正记录；归档 digest78c93a64一致 | [r4修复:17](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r4-fixes.md#L17>)、[r4评分:221](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r4-runtime.score.json#L221>) |
| D12 | P1 fixed | **真实富表句柄** --ref resource_ref →0，与 --set 逐字相同；同表 --ref table_ref →0 整对象；CriteriaRef→VersionedRef →1业务 not_found，与 --set 相同、schema已通过；不兼容 CriteriaRef→FileRef →2 usage | [unified:360–385](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L360-L385>)；[表引用](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D12_table_ref_identity.json>)、[criteria引用](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D12_criteria_ref.json>) |
| D13 | P1 fixed | 锁0.2/仅装0.1 → dispatch3 stdout空、doctor3；锁已装0.1 →0。不回退未锁定代码；新相反边界分配D16 | [dataagent:63–71](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L63-L71>)；[缺pin版本](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D13_missing_pin_dispatch.json>) |
| D14 | P1 fixed | 真实三层解释器 fresh root enforce：无策略doctor3/authorize3；policy apply后doctor0 configured | [dataagent:177–206](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L177-L206>)；[无策略](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D14_doctor_missing_policy.json>)、[配置后](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D14_doctor_configured.json>) |
| D15 | P1 fixed | 完整 proposal-only →0 draft，空 input control→0；stage1仍needs_input | [unified:142–154](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L142-L154>)；[探针](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/D15_proposal_only.json>) |

主链路/负例另核对：三层 list32/13/6、扁平help无defs、旧 stdin/--list 形状、detail全文等于落盘、宿主身份走私拒绝、绝对/穿越/符号链接路径 exit1、坏 enum/ref/bool/json exit2。管理链路 link生成/拒覆盖、setup三次frozen、环境去凭据/去PYTHONPATH均通过。[50项原探针汇总](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/checks.json>) 与 [管理探针汇总](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/management-checks.json>) 均无失败；精确边界和D16在随后独立 followup 中发现，未把先前通过汇总当作最终验收结论。

## 5. 清单、评分与轮次对比

完整提取（`--all`）：**27 条，done15 / partial2 / na10**，17项真正要求完成15项；新增元数据计数来自此前未采入的r3/r6记录行，不改变有效分母。

- partial `#99a1de`：stdout 32KiB 精确边界，D5。
- partial `#b9b374`：锁文件优先/缺省最高回退，D16。
- `#ceedd2` 已done：D12/D15修复，argv/ref/proposal合法输入均通过。
- `#61fb67` 已done：D14 doctor策略修复、link/setup实证通过；锁版本一致性缺口归入版本分发项，避免重复降项。

```text
总分 79.0 / 100，C，不可验收，证据覆盖100%
GATE-P1: D5, D16
GATE-CHECKLIST: #99a1de, #b9b374
硬规则: R01/R03/D1/V1/R13/R14 green，E1 na
得0: A5.1, L2.1, L2.4, L4.2
无未测量规则（na均在runtime profile允许范围）
```

与 r5 Reviewer 补充结果对比：79→79；**已修复4**（D12–D15），**部分修复2**（D5、D2），**未修复1**（D3），**新缺陷1**（D16），**保持关闭8**。D1–D15未删除，无未复核。[轮次对比全文](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/round-diff.txt>)。

`round_diff --fail-on-regression` exit0，仅表示其“已有id/规则/清单”没有降级，不代表无行为回归：D16是新id，原L2.1/L2.4早已0、分发清单在r5补充评审中已partial，所以工具不会把它再计一次1→0。pre-r6/r6真实同输入对照已经确认它是**新引入行为回归**，本报告不会因diff显示“无退化”而忽略。

## 6. 开发者声明核对（评分后读取）

| 声明 | 结论 | 证据 |
|-|-|-|
| D12富句柄字符串回填、对象包装仍可用 | 已证实 | 真实表/criteria正例与对象/不兼容负例 |
| D13缺已锁版本exit3，不静默回退 | 已证实 | 原缺0.2pin探针3、stdout0；doctor3 |
| D13“无pin仍取最高已装” | **不成立** | 存在锁文件但该层没有条目→3；pre-r6同输入→0。见 [r6修复:43](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-fixes.md#L43>) |
| D14无策略doctor3、配置后0 | 已证实 | 真实三层venv+fresh enforce root |
| D15proposal-only合法 | 已证实 | 单proposal文件0，stage1needs_input |
| D5 40KiB单句柄stdout634B、全文保留 | 已证实（目录导致656B） | 单句柄656B，完整ID保存；Unicode1038B |
| D5“保证≤32KiB”、全部关闭 | **部分成立** | 原例通过，但真实边界32769B。见 [r6修复:65–71](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-fixes.md#L65-L71>) |
| 111/654/203/123/15全绿、snapshot/bundle/质量数字 | 已证实 | 独立五套完整测试、快照、cmp、quality_run |
| 自评93.1/A/无闸门 | **仅可在其自评结果复现，独立不成立** | 自评scorer确为93.1；加入D5边界和D16后79/GATE-P1+CHECKLIST |
| D2partial、D3open范围外 | 已证实 | 实测复杂度与deadline行为 |

D5严重级漂移：开发者修复记录写P2，r5 Reviewer已将同一MUST缺口登记P1；本报告沿用原独立id/严重级而不是静默降级。

## 7. 视觉验收与未测量

**视觉验收 UNVERIFIED。** 已真实尝试：

```sh
/usr/sbin/screencapture -x /Users/payne/.dsh/state/agent-teamwork/team/r6-cli-visual-evidence.png
# exit 1: could not create image from display
```

没有生成截图，不能给出存在的截图绝对路径作为证据。当前是CLI任务，未提供可用浏览器/终端截图API，宿主显示捕获失败；不把合成终端画面、JSON transcript或DSH GUI自身截图当作CLI实现截图。失败说明：[视觉未验证记录](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/visual-unverified.txt>)。功能证据是实际subprocess字节流，不是视觉验收替代物。该项未验证不会被写成PASS；本轮已有两个独立功能阻断。

rubric规则无未测量项；runtime允许na的规则与原因见 [独立评分输出](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r6-tester.score.txt#L55-L62>)。当前Mint/iface最新同步未验（kernel落后7提交且禁止改源码）；本轮不扩大到Mint实时兼容性或Hub发布。

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
S=skills/code-landing-quality/scripts
D=docs/research/dataagent-2026-11-03/12-cli-build
python3 $S/snapshot.py packages/capabilities/dataagent-runtime
python3 $S/quality_run.py --repo . --package packages/capabilities/dataagent-runtime \
  --fill $D/r6-tester-runtime.score.json --out $D/r6-tester-runtime.quality.md
(cd packages/capabilities/dataagent-data && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-application && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-governance && .venv/bin/python -m pytest -p no:warnings -o addopts="")
(cd packages/capabilities/dataagent-cli && python3 -m unittest discover -s tests)
(cd packages/capabilities/dataagent-runtime && uv lock --check && uv build -o /tmp/r6-tester-dist)

# 探针在临时目录运行，不改源码；followup根据首次stdout动态构造精确边界
python3 /tmp/r6-independent/cli_probe.py
packages/capabilities/dataagent-runtime/.venv/bin/python /tmp/r6-independent/runtime_probe.py
python3 /tmp/r6-independent/followup_probe.py
python3 /tmp/r6-independent/management_probe.py
PYTHONPATH=packages/capabilities/dataagent-runtime/src packages/capabilities/dataagent-runtime/.venv/bin/python \
  $D/r1-repro/probe_overflow2.py
PYTHONPATH=packages/capabilities/dataagent-runtime/src packages/capabilities/dataagent-runtime/.venv/bin/python \
  $D/r1-repro/probe_detail_egress.py

python3 $S/score_landing.py --result $D/r6-tester-runtime.score.json
python3 $S/round_diff.py \
  /Users/payne/.dsh/state/agent-teamwork/team/cli-review-evidence/reviewer-score.json \
  $D/r6-tester-runtime.score.json --fail-on-regression
```

归档可读脚本：[cli_probe](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/cli_probe.py>)、[runtime_probe](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/runtime_probe.py>)、[followup_probe](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/followup_probe.py>)、[management_probe](</Users/payne/.dsh/state/agent-teamwork/team/r6-cli-review-evidence/management_probe.py>)。

HANDOFF: Developer | 修复 D16 无 pin 误拒及有效 TOML 解析、doctor/dispatch 一致性；补 D5 含换行的真实 stdout 精确字节边界回归，再送审
VERDICT: FAIL
