---
round: r10-reviewer
date: 2026-11-06
subject: 统一 CLI 独立验收
plan: 12-unified-cli-research.md v0.3; 12-unified-cli-build-plan.md r1
rubric: 2.1 sha256:5e65f6c6006a28192894e531c362bfbf668e43bde338974f3ab1b0342a6d4f1c
commit: 9b452c11caa589ff581d633e734b5e867d7eb680
snapshot:
  dataagent-runtime: sha256:8a7692b415f87eed92aa13c5afed968cf6a916f72d46e94a966c304f24e8ac66
  dataagent-cli: sha256:03c900e73c4ec261bdb92de3ba0cf0de0aa77199d60942ac1c7b602770c607ff
facts_ref: agent-kernel@29dd1b7611390eadc471d4b013214cee78efbf2f; actual Mint 0.1.26
verdict: 不可验收
score: 79.0（C）
---

# 统一 CLI 独立验收

## 0. 结论

**不可验收：79.0 / 100（C），GATE-P1（D16）+ GATE-CHECKLIST（`#b9b374`）。** 原有探针通过，但新探针证明 D16 仍 partial：真实 Mint 接受的 CRLF 多行 name 会被忽略，锁定 0.1.0 / 未安装 0.9.9 时均执行 0.2.0；同输入 r9 拒绝、r10 成功执行，构成新的 fail-open 回归。CRLF 多行 version / 续行仍误拒；键路径注册表存在碰撞；无效锁并非全部 fail-closed。

按严重级排序的阻断位置：

| 级别 / ID | finding | 位置 |
|-|-|-|
| **P1 / D16 — pin 绕过及回归** | CRLF 多行 basic/literal name，Mint/tomllib 解析为 `dataagent/data-layer`；dispatcher / doctor exit 0、实际 exec 0.2.0。锁定未装 0.9.9 同样 bypass；r9 exit 3 → r10 exit 0。 | [字符串扫描:182–248](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L182-L248>)、[读入:544](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L544>)、[回退:580–593](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L580-L593>) |
| **P1 / D16 — 合法锁误拒** | CRLF 多行 version 的前导 CR 未裁剪，已装 0.1.0 被报 missing；CRLF 续行不认 `\r\n`，报不可读。真实 Mint 两者 exit 0、pin 0.1.0。 | [续行:145–158](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L145-L158>)、[前导换行:185–186](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L185-L186>) |
| **P1 / D16 — 注册表碰撞回归** | 合法键 `"a\u001cb"=1` 与 `a.b=2` 被 SUBSEP 连接映射为同一个路径，误报重复键 exit 3；Mint 接受，r9/r8 均 exit 0 执行正确 pin。 | [键路径注册表:283–298](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L283-L298>) |
| **P1 / D16 — 不可解析锁未 fail-closed** | `resolver=INVALID`、`v=01`、非法日期、表头后同一行赋值、裸控制字符被 Mint/tomllib 拒绝；dispatcher / doctor 仍 exit 0 执行 0.1.0。 | [值扫描:347–377](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L347-L377>)、[表头:465–497](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L465-L497>)、[字符串:210–212](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-cli/bin/dataagent#L210-L212>) |

证据：[真实解释器复现](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/real-extra-results.json>)、[r8/r9/r10 同输入控制](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/crlf-control-results.json>)、[独立补充矩阵](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/extra-lock-results.json>)。

## 1. 输入冻结与仓库约定

被测目标提交 `9b452c1`；测量前后 runtime / CLI digest 完全一致，产品源码、测试和 fixtures 未修改。根仓库原有两个 RSI 子模块 dirty 与本任务无关。

按 [AGENTS.md:3–17](</Users/payne/Vibe/AgentOS/AGENTS.md#L3-L17>) 执行 kernel fetch：干净 kernel 从 698ac1b 落后 7 提交，已按约定 fast-forward 到 29dd1b76；iface `--check` exit 0（10 包一致）。这是独立 kernel 仓库的上游同步，不是 CLI 产品编辑。实际运行的 Mint 是 0.1.26，未以新 kernel 源码版本冒充本机 Mint 版本。

| 冻结项 | 实测 |
|-|-|
| rubric | 2.1；SHA 5e65f6c6…，rubric/scorer 副本一致，无修改 |
| runtime | 8a7692b4… / 67 文件；与 r9 相同 |
| CLI | 03c900e7… / 6 文件 |
| Python | 原锁差分 Python 3.15.0；runtime/data/gov 套件 3.12、app 3.13 |
| 发布基线 | tag 20022e0a → fbe24d8；独立 archive digest 78c93a64… / 67 文件；旧 stdin / `--list` 协议通过 |

## 2. 重跑结果

| 检查 | 独立结果 | 证据 |
|-|-|-|
| 五套完整回归 | **112 / 654 / 203 / 123 / 58 全通过**，未 skip CLI Mint 测试 | [runtime 日志](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/tests-dataagent-runtime.log>)、[data 日志](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/tests-dataagent-data.log>)、[app 日志](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/tests-dataagent-application.log>)、[gov 日志](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/tests-dataagent-governance.log>)、[CLI 日志](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/tests-dataagent-cli.log>) |
| 原 lock_probe | **24/24 PASS** | [原矩阵](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/lock-results.json>) |
| 原 lock_edges | **24/24 PASS**；每例真实 Mint + tomllib 复核 | [等价矩阵](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/lock-edges-results.json>) |
| 原 lock_controls | r10 **14/14 PASS**（7 输入 × dispatch/doctor）；全部 42 行中 14 个失败归历史 r8/r9 | [控制矩阵](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/lock-control-results.json>) |
| 原随机差分 | 1500 次生成，**1339 个合法锁实际执行、161 个跳过**；0 fail | [合法差分结果](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/lock-fuzz-results.json>) |
| 原非法锁差分 | 600 次生成，**64 个非法锁实际执行**，0 fail；原统计 incorrectly 输出 `invalid_cases=0` | [独立计数](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/original-fuzz-counts.json>) |
| 新随机差分 | 固定种子 1020261106；360 个合法锁 × 2 命令 = **720 检查 / 142 fail**；240 个确定非法锁 × 2 = **480 检查 / 158 fail** | [新生成器](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/independent_fuzz.py>)、[合法失败](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/independent-fuzz-valid.json>)、[非法失败](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/independent-fuzz-invalid.json>) |
| 新确定性矩阵 | 17 输入 × 2 命令：**34 检查 / 22 fail**；其中 dotted package dict 是 tomllib 接受但 Mint 拒绝，**不以它作为阻断依据** | [补充矩阵](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/extra-lock-results.json>) |
| 新真实三层复现 | **28 检查 / 24 fail**；包含 Mint 接受 CRLF / SUBSEP 与 Mint 拒绝的无效锁 | [真实层日志](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/real-extra.log>) |
| 重复键 fail-closed | 原套件及新 duplicate-name/version/inline nested duplicate 均 exit 3 未执行；但是合法 SUBSEP 键被误当重复 | [重复键输入与结果](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/extra-lock-results.json>) |
| 其他旧缺陷探针 | CLI 50 / management 11 全 pass；标量审计 249 字段 / 121 标量 / 44 ops，mismatch0 / coerce error0 | [CLI 日志](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/cli-probes.log>)、[management 结果](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/probes/management-checks.json>) |

新差分用新生成器、独立临时目录；期望由 tomllib 推导，实际版本由 wrapper 记录真实 exec 路径。先前并行启动的两个新探针曾共享临时锁目录，已取消随机作业并用独立临时目录重新完整执行；表中只采用最终隔离复跑结果。

### 最小 CRLF 回归

以下每行以 **CRLF** 写入，而不是 LF：

```toml
v=1
[[package]]
name="""
dataagent/data-layer"""
version="0.9.9"
kind="bundle"
source="path+file:///fixture"
integrity="h1:fixture"
cksum=""
```

装有 0.1.0 + 0.2.0 时，真实 Mint `list --offline --json` exit 0、pin 0.9.9。相同输入：r9 dispatcher / doctor **exit 3、未执行 data-layer**；r10 **exit 0、执行 0.2.0**。将 pin 换成 0.1.0 仍错误执行 0.2.0。原因是前导多行字符串仅裁剪 LF，缓冲区保留 CR，使解码 name 变成带前导 CRLF 的不同名称，随后被当成「无该层 pin」。

## 3. 安装、构建与质量

- D17 保持 fixed：真实 Mint `init` + `add <preset path> --offline -y` + 后续 `lock --dry-run --offline -y` 均 exit 0，装入五个 DataAgent 包；CLI 字节与被测源码完全相同。安装后的真实、独立三层 frozen 环境 doctor0 / list32,13,6 / CSV 两行解析通过。[安装链证据](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/install-results.json>)
- 初次 offline setup 默认选 3.13，数据层 cp313 pydantic-core wheel 未缓存，exit 1；查明原因后同一安装目录按 data/gov 3.12、app 3.13 继续 `uv sync --frozen --offline --python …`，均 exit 0。不是产品失败，也未以 repo venv 代替 installed bundle 环境。
- 独立 quality_run：runtime112 passed；重复率 **2.13%（53/2489，包内20 / 跨包33）**；裸 except / 吞错 **0 / 0**；CC>10 **28.32%**；CC>25 **0.0%**；bundle 与 rubric/scorer 一致。[机器报告](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/runtime.quality.md>)
- `uv lock --check`、`uv build`、`sh -n`、四份 vendored cmp 均 exit 0；wheel22 members / 19 py / 0 pyc。[payload 检查](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/packaging-inspection.json>)
- D5 保持 fixed：未截断 JSON32767 B → stdout32768 B；32768 / 32769 / 40000 B → stdout340 B、truncated；持久化全文精确一致。[边界结果](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/boundary-results.json>)

## 4. P2 与上轮缺陷复核

| ID | 级 | 状态 | 证据与位置 |
|-|-|-|-|
| D2 | P2 | partial | CC>10 28.32% > 7.3%；[enforcement.py:255](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/enforcement.py#L255>) |
| D3 | P2 | open | 无默认 deadline；显式 20 ms 后仍 **124 ms** 完成并返回 ok；[context:426–449](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/interfaces/unified.py#L426-L449>)、[invoke:353–360](</Users/payne/Vibe/AgentOS/packages/capabilities/dataagent-runtime/src/dataagent_runtime/invoke.py#L353-L360>)；[行为探针](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/runtime-probes.log>) |
| **D18 新增** | P2 | open | 原合法 fuzz 跳过161却描述1500合法锁；非法 fuzz仅实际测试64，统计式 `len(rows)+fails` 在全部通过时给0，不记录已测试数量。[合法计数:159–165](</Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock_fuzz.py#L159-L165>)、[非法生成筛选:22–28](</Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock_fuzz_invalid.py#L22-L28>)、[错误计数:49–51](</Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/lock_fuzz_invalid.py#L49-L51>) |

全部原17缺陷保留；D1、D4–D15、D17 共14条保持关闭。D10/D12 标量与句柄原控制通过；D13 canonical/compact 缺 pin 保持拒3，新增 CRLF 同类回归记入既有 D16，未用重复 ID 掩盖；D14 缺 policy doctor3 / apply 后0；D15 proposal-only 与第二阶段通过；D7 full/summary 外发剥离；D8/D9 无 traceback；D11 tag ref/archive复核。

## 5. 评分与 round_diff

[独立评分](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/runtime.score.json>)、[score_landing 完整输出](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/score.txt>)、[round_diff 完整输出](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/round-diff.txt>)：

- **79.0 / C，证据覆盖100%**；依据等级 A46.0% / B41.4% / C12.6%。硬规则 R01/R03/D1/V1/R13/R14 green，E1 按 runtime profile na；无未测量规则。
- 29清单项：done16 / partial1 / na12；有效需求17，完成率94.1%。唯一 partial 是 `W3分发器包实现#b9b374`。本轮比上一轮多1个历史索引项，已 na，不伪装成新增产品需求。
- 得0规则：A5.1、L2.1、L2.4、L4.2、L6.2。L6.2 1→0 对应新 D18。
- `round_diff --fail-on-regression` **exit 1**：L6.2 退化，D18 新增；D16/D2 partial、D3 open、14条 fixed 保持，无「未复核」。D16 内输入级 fail-open 回归不由状态 diff 自动识别，另有 r9/r10 实测控制，必须阻断。
- runtime 快照不变且得分封顶同为79不是「无变化」：本轮改动在 CLI，新增 D16 行为回归和 D18 证据缺陷，得分已被79闸门封顶。

## 6. 开发者声明核对

独立评分后才读取 [修复记录](</Users/payne/Vibe/AgentOS/docs/research/dataagent-2026-11-03/12-cli-build/r10-fixes.md>)。

| 声明 | 结论 | 实证 |
|-|-|-|
| 原24+等价24全 PASS；原missing对照恢复 | 已证实 | 24/24+24/24；r10 oldmissing14/14 |
| D16 fixed；所有合法等价形无静默回退；无missing-pin回归 | **部分成立** | LF输入修复；CRLF name锁定0.9.9仍exec0.2，r9拒绝→r10执行 |
| 所有不可解析锁 fail-closed；重复键注册表复刻 | **部分成立** | representative duplicates拒绝；非法token/header/rawcontrol放行，SUBSEP合法路径碰撞误拒 |
| 1500合法随机锁0失败 | **部分成立** | 实际1339合法执行、161跳过；独立更广生成器发现142/720失败 |
| 另扫600生成锁，所有tomllib拒绝者均拒绝 | **仅原生成器成立** | 600 attempts仅64非法被执行；原统计错误给0；新240确定非法锁158/480失败 |
| 本轮 self-score93.1无闸门 | **不成立** | D16 / #b9b374 未关闭；独立79.0及两闸门 |
| 五套58等、runtime零改动、质量/构建/cmp、D17保持 | 已证实 | 全量独立复跑与安装链；target snapshots前后相同 |

记录承认裸控制字符存在宽松解析，故该点不是「未声明」；但它与「任何不可解析锁拒绝」的全面声明冲突，不能用这段说明关闭验收条件。

## 7. 真实截图与未验证范围

真实 installed CLI 子进程 `data list` 产生32行原样 stdout，保存为纯文本后由真实 Google Chrome headless 打开并截图。没有生成模拟终端或替代产品 UI；已读取图片检查32行每 op 一行、编号/recheck/two_phase可见。

**截图绝对路径**：[cli-actual-output.png](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/cli-actual-output.png>)。

![真实 installed CLI 原样 stdout 的浏览器截图](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/cli-actual-output.png>)

[截图命令/真实stdout来源](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/visual-evidence.json>)。**CLI文本浏览器渲染已验证**。原生桌面/终端截图 `screencapture` exit1，`could not create image from display`，因此该范围仍 **unverified**；[失败记录](</Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence/visual-capture.stderr.txt>)。本任务没有 GUI shell 实现，不以 Harness 页面截图代替 CLI。

## 8. 复跑命令

```sh
cd /Users/payne/Vibe/AgentOS
E=/Users/payne/.dsh/state/agent-teamwork/team/r10-reviewer-evidence
# 五套套件命令与修复记录相同；日志位于 $E/tests-*.log
python3 skills/code-landing-quality/scripts/quality_run.py --repo . \
  --package packages/capabilities/dataagent-runtime --fill "$E/runtime.score.json" --out "$E/runtime.quality.md"
python3 skills/code-landing-quality/scripts/plan_checklist.py docs/research/dataagent-2026-11-03/12-unified-cli-build-plan.md --into "$E/runtime.score.json"
python3 "$E/lock_probe.py"
python3 "$E/lock_edges.py"
python3 "$E/lock_controls.py"
python3 "$E/lock_fuzz.py" 1500
python3 "$E/lock_fuzz_invalid.py"
python3 "$E/extra_lock_probe.py"
python3 "$E/crlf_controls.py"
python3 "$E/independent_fuzz.py"
python3 "$E/real_extra_edges.py"
python3 "$E/install_probe.py"      # 初次 auto-Python 缓存缺失见记录；继续同一安装目录
python3 "$E/install_continue.py"
python3 "$E/probes/cli_probe.py"
python3 "$E/probes/management_probe.py"
python3 "$E/d5_boundary.py"
python3 "$E/capture_visual.py"
python3 "$E/finalize_score.py"
python3 skills/code-landing-quality/scripts/score_landing.py --result "$E/runtime.score.json"
python3 skills/code-landing-quality/scripts/round_diff.py \
  docs/research/dataagent-2026-11-03/12-cli-build/r9-reviewer-runtime.score.json "$E/runtime.score.json" --fail-on-regression
```

HANDOFF: Developer | 修复 D16 CRLF多行/续行规范化与missing-pin fail-open、键路径碰撞和非法锁fail-closed；修正D18实际probe计数；补真实Mint差分与r9/r10回归测试后重新送审
VERDICT: FAIL
