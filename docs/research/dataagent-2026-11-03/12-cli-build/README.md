# 12-cli-build 记录目录

统一 CLI 方案 [12-unified-cli-research.md](../12-unified-cli-research.md) 与实现计划
[12-unified-cli-build-plan.md](../12-unified-cli-build-plan.md) 的实施/评审记录。

| 文件 | 轮次 | 内容 |
|-|-|-|
| [r1-fixes.md](r1-fixes.md) | r1 | 开发者实现与自评记录（含 D1–D4） |
| [r1.score.json](r1.score.json) | r1 | 开发者自评结果（59.0，GATE-RED） |
| [r1.score.txt](r1.score.txt) | r1 | 自评 `score_landing.py` 输出 |
| [r1-runtime.score.json](r1-runtime.score.json) | r1 | Tester 独立验收结果（59.0，7 条 P2） |
| [r1-runtime.quality.md](r1-runtime.quality.md) | r1 | `quality_run.py` 机器测量报告 |
| [r1-review.md](r1-review.md) | r1 | 第 1 轮验收（不可验收；D1 GATE-RED + 2 清单项 partial） |
| [r1-repro/](r1-repro/) | r1 | D5/D7 复现探针（`probe_overflow2.py`、`probe_detail_egress.py`、`probe_overflow.py`） |
| [r2-fixes.md](r2-fixes.md) | r2 | 开发者修复记录：r1 三闸门（D1 重复率 13.84%→2.21%、#99a1de/#7cf8d0 两清单项、R13 na）+ D4/D5/D6/D7 |
| [r2-runtime.score.json](r2-runtime.score.json) | r2 | 开发者自评结果（93.1 / A / 可验收，无闸门；D2 partial、D3 open 留待后续轮） |
| [r2.score.txt](r2.score.txt) | r2 | 自评 `score_landing.py` 输出 |
| [r2-tester-runtime.score.json](r2-tester-runtime.score.json) | r2 | Tester 独立验收结果（89.0 / B / GATE-UNKNOWN；D1/D4–D7 fixed、D2 partial、D3 open、D8/D9 新 P2） |
| [r2-tester-runtime.quality.md](r2-tester-runtime.quality.md) | r2 | Tester 复跑的 `quality_run.py` 机器测量报告 |
| [r2-review.md](r2-review.md) | r2 | 第 2 轮验收（不可验收：功能面全通过，rubric GATE-UNKNOWN/R13；自评 93.1 不可复现） |
| [r3-fixes.md](r3-fixes.md) | r3 | 开发者修复记录：D8/D9 两条 P2（结构化 exit 2，无 traceback）+ R13 更正为 unknown（自评与 Tester 评分同构 89.0） |
| [r3-runtime.score.json](r3-runtime.score.json) | r3 | 开发者自评结果（89.0 / B / GATE-UNKNOWN；D8/D9 fixed、D2 partial、D3 open；R13 清除待 owner 决策） |
| [r3.score.txt](r3.score.txt) | r3 | 自评 `score_landing.py` 输出 |
| [r4-fixes.md](r4-fixes.md) | r4 | 开发者基线建立记录：owner 批准后 git init + tag `dataagent-runtime-0.1.0`（commit `fbe24d8`），R13 green；产品代码与 r3 零改动 |
| [r4-runtime.score.json](r4-runtime.score.json) | r4 | 开发者自评结果（93.1 / A / 无闸门；R13 green 证据：基线 tag + 旧 wire 形状锁定测试 16 passed） |
| [r4.score.txt](r4.score.txt) | r4 | 自评 `score_landing.py` 输出 |
| [r4-tester-runtime.score.json](r4-tester-runtime.score.json) | r4 | Tester 独立验收结果（79.0 / C / 不可验收；GATE-P1 D10 `--set` anyOf/$ref 标量 + GATE-CHECKLIST #ceedd2；R13 green 已验证，D11 新 P2） |
| [r4-tester-runtime.quality.md](r4-tester-runtime.quality.md) | r4 | Tester 复跑的 `quality_run.py` 机器测量报告 |
| [r4-review.md](r4-review.md) | r4 | 第 4 轮验收（不可验收：基线 tag 可核且 R13 green，但 `--set` 不支持 anyOf/$ref 标量 → P1 + 清单 partial；自评 93.1 仅在其自身结果文件上复现，独立 79.0） |
| [r5-fixes.md](r5-fixes.md) | r5 | 开发者修复记录：D10（`_resolve_kind` 解析 anyOf/$ref/$defs，`--set` 支持字符串形模型/枚举/可选标量/Any 字段，`--help` 渲染实际标量类型）+ D11（r4 记录 tag object 更正为实际 ref `20022e0a`，带审计标注） |
| [r5-runtime.score.json](r5-runtime.score.json) | r5 | 开发者自评结果（93.1 / A / 无闸门；D10/D11 fixed、`#ceedd2` done；D2 partial、D3 open 留待后续轮） |
| [r5-runtime.quality.md](r5-runtime.quality.md) | r5 | `quality_run.py` 机器测量报告 |
| [r5.score.txt](r5.score.txt) | r5 | 自评 `score_landing.py` 输出 |
| [r5-tester-runtime.score.json](r5-tester-runtime.score.json) | r5 | Tester 独立验收结果（93.1 / A / 可验收，无闸门；D10/D11 fixed、`#ceedd2` done；D2 partial、D3 open） |
| [r5-tester.score.txt](r5-tester.score.txt) | r5 | Tester `score_landing.py` 输出 |
| [r5-tester-runtime.quality.md](r5-tester-runtime.quality.md) | r5 | Tester 复跑的 `quality_run.py` 机器测量报告 |
| [r5-review.md](r5-review.md) | r5 | 第 5 轮验收（可验收：D10/D11 复现通过、三层判型审计 121 字段/44 ops、R13 仍 green；93.1 / A，无闸门） |
| [r6-fixes.md](r6-fixes.md) | r6 | 开发者修复记录：r5-review 后续探针 5 项——D12（`--ref` 富句柄进 VersionedRef 字段，字符串形回填）、D13（缺锁定版本 exit 3）、D14（doctor 缺策略 exit 3）、D15（proposal-only 输入判定）、D5 补全（32 KiB 兜底复检编码大小，单句柄裁剪） |
| [r6-runtime.score.json](r6-runtime.score.json) | r6 | 开发者自评结果（93.1 / A / 无闸门；D12–D15 fixed、D5 re-fixed；D2 partial、D3 open 留待后续轮） |
| [r6-runtime.quality.md](r6-runtime.quality.md) | r6 | `quality_run.py` 机器测量报告 |
| [r6.score.txt](r6.score.txt) | r6 | 自评 `score_landing.py` 输出 |
| [r6-review.md](r6-review.md) | r6 | 第 6 轮独立验收：79.0 / C / 不可验收；D12–D15 fixed，但 D5 精确 stdout 边界仍 partial、新增 D16 无 pin 分发回归；GATE-P1 + GATE-CHECKLIST，视觉验收 unverified |
| [r6-tester-runtime.score.json](r6-tester-runtime.score.json) | r6 | 独立评分，16 条缺陷完整复核：未关闭 P1 D5/D16、P2 D2/D3；清单 done15 / partial2 / na10 |
| [r6-tester-runtime.quality.md](r6-tester-runtime.quality.md) | r6 | 独立机器测量：111 passed、重复率2.13%、CC>10 28.24%、吞错0、bundle一致 |
| [r6-tester.score.txt](r6-tester.score.txt) | r6 | 独立 `score_landing.py` 输出：79.0 / C / GATE-P1 + GATE-CHECKLIST |
| [r7-fixes.md](r7-fixes.md) | r7 | 开发者修复记录：r6-review 两项阻断——D16（`pinned_version` 无该层 pin → return 1，resolve_dir/doctor 同序回退最高已装）、D5 收口（`fits` 计入 print 换行，上限=整条 stdout 行）|
| [r7-runtime.score.json](r7-runtime.score.json) | r7 | 开发者自评结果（93.1 / A / 无闸门；D16 fixed、D5 re-fixed；D2 partial、D3 open 留待后续轮）|
| [r7-runtime.quality.md](r7-runtime.quality.md) | r7 | `quality_run.py` 机器测量报告（112 passed、重复率 2.13%、CC>10 28.32%）|
| [r7.score.txt](r7.score.txt) | r7 | 自评 `score_landing.py` 输出 |
| [r7-review.md](r7-review.md) | r7 | 第 7 轮独立验收（不可验收 79.0 / C；GATE-P1 D16 + GATE-CHECKLIST #b9b374；D5 fixed，D16 partial：合法空白 TOML pin 仍被忽略且 fail-open；D2 partial、D3 open） |
| [r7-tester-runtime.score.json](r7-tester-runtime.score.json) | r7 | 独立验收结果（79.0 / C；16 条缺陷完整复核；清单 done16 / partial1 / na10） |
| [r7-tester-runtime.quality.md](r7-tester-runtime.quality.md) | r7 | 独立机器测量（112 passed、重复率 2.13%、CC>10 28.32%、吞错 0、bundle 一致） |
| [r7-tester.score.txt](r7-tester.score.txt) | r7 | 独立 `score_landing.py` 输出（79.0 / C / GATE-P1 + GATE-CHECKLIST） |
| [r8-fixes.md](r8-fixes.md) | r8 | 开发者修复记录：r7-review D16 残留——`pinned_version` 改 POSIX awk TOML 子集解析（compact/缩进/字面字符串均同解析），三态出口区分「无该层条目」（回退）与「条目版本不可读」（fail-closed exit 3）；`pin_status` 以 `\|\|` 捕获防 if 条件吞 die；pin 未装仍 D13 exit 3 不回退；cli 17→23 |
| [r8-runtime.score.json](r8-runtime.score.json) | r8 | 开发者自评结果（93.1 / A / 无闸门；D16 fixed；D2 partial、D3 open 留待后续轮） |
| [r8-runtime.quality.md](r8-runtime.quality.md) | r8 | `quality_run.py` 机器测量报告（112 passed、重复率 2.13%、CC>10 28.32%、runtime 源零改动） |
| [r8.score.txt](r8.score.txt) | r8 | 自评 `score_landing.py` 输出 |
| [r8-review.md](r8-review.md) | r8 | 第 8 轮独立验收（**可验收 93.1 / A，无闸门**；D16 fixed——28+7 组合真实三层矩阵：合法 TOML pin 0.1.0 双版本已装 dispatch/doctor 均 0.1.0、pin 未装 exit 3 未执行、不可读 fail-closed；D5 fixed；D2 partial、D3 open 为非阻断 P2） |
| [r8-tester-runtime.score.json](r8-tester-runtime.score.json) | r8 | 独立验收结果（93.1 / A / 无闸门；16 条缺陷完整复核；清单 done 17 / na 10；L2.1/L2.4 恢复 1） |
| [r8-tester-runtime.quality.md](r8-tester-runtime.quality.md) | r8 | 独立机器测量（112 passed、重复率 2.13%、CC>10 28.32%、吞错 0、bundle 一致） |
| [r8-tester.score.txt](r8-tester.score.txt) | r8 | 独立 `score_landing.py` 输出（93.1 / A / 无闸门）；此结论被下述 Reviewer 新增探针推翻 |
| [r8-reviewer-supplement.md](r8-reviewer-supplement.md) | r8 补充评审 | **不可验收 79.0 / C**；同源码快照新增 P1 D17（真实 Mint 解析 CLI 清单失败，缺 artifacts.layout）与 D16 partial（嵌套 package.requires 被误认 pin、合法引号键/转义 pin 被绕过）；D5 保持 fixed；视觉截图失败、unverified |
| [Reviewer 独立评分](/Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/runtime.score.json) / [评分输出](/Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/score.txt) | r8 补充评审 | 17 条缺陷全量保留，GATE-P1（D16/D17）+ GATE-CHECKLIST；done14 / partial3 / na10 |
| [Reviewer 机器报告](/Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/runtime.quality.md) / [复现证据](/Users/payne/.dsh/state/agent-teamwork/team/r8-reviewer-evidence/) | r8 补充评审 | 独立五套 112/654/203/123/23 全绿、质量测量、真实 Mint 清单解析、24 组合锁探针、r7/r8 嵌套锁回归对照 |
| [r9-fixes.md](r9-fixes.md) | r9 | 开发者修复记录：r8-reviewer D16/D17——D17 `mint.toml [artifacts]` 补必填 `layout="any"`（真实 Mint init+add+lock 全链路 exit 0，安装 5 包含 cli）；D16 `pinned_version` awk 解析器表作用域感知（仅 `[[package]]`/`[package]` 为 pin 条目，`[[package.requires]]` 依赖边忽略）+ 引号键 + basic 字符串完整转义（`\uXXXX` 等）+ 值后仅许空白/注释否则 fail-closed；reviewer 24 组合 lock_probe 全 PASS；cli 23→36（+9 D16、+4 D17 真实 Mint 清单/安装回归） |
| [r9-runtime.score.json](r9-runtime.score.json) | r9 | 开发者自评结果（93.1 / A / 无闸门；D16/D17 fixed；D2 partial、D3 open 留待后续轮；runtime 源零改动） |
| [r9-runtime.quality.md](r9-runtime.quality.md) | r9 | `quality_run.py` 机器测量报告（112 passed、重复率 2.13%、CC>10 28.32%） |
| [r9.score.txt](r9.score.txt) | r9 | 自评 `score_landing.py` 输出（93.1 / A / 无闸门）；修复证据 [r9-fix-evidence](/Users/payne/.dsh/state/agent-teamwork/team/r9-fix-evidence/)（install-chain.log、lock-results.json、D16_pre_post_control.txt） |
| [独立评审](<r9-review.md>) | r9 | **不可验收 79.0 / C**，GATE-P1 D16 + GATE-CHECKLIST #b9b374；D17 fixed、原锁24/24通过，但实际Mint可解析的quoted/escaped表头与键、inline package数组绕过pin、多行pin误拒（补充20/24失败）；quoted missing pin同输入r8exit3→r9exit0exec0.2回归；五套112/654/203/123/36全绿 |
| [Reviewer独立评分](<r9-reviewer-runtime.score.json>) / [评分输出](<r9-reviewer.score.txt>) / [轮次对比](<r9-reviewer-round-diff.txt>) | r9 | 17条缺陷完整复核，done16 / partial1 / na11；D17关闭、D16部分修复、D2/D3保持P2；round_diff状态rc0不代表输入级无回归 |
| [Reviewer机器报告](<r9-reviewer-runtime.quality.md>) / [复现证据](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/>) / [真实stdout截图](</Users/payne/.dsh/state/agent-teamwork/team/r9-reviewer-evidence/cli-actual-output.png>) | r9 | 独立质量、真实Mint安装及installed bundle执行、原24与补充24锁矩阵；截图为浏览器原样渲染真实CLI stdout，原生桌面截图失败未验证 |
| [r10-fixes.md](r10-fixes.md) | r10 | 开发者修复记录：r9-review D16 残余——`pinned_version` 由逐行解析改为**单遍字符级 TOML 扫描器**（POSIX awk + LC_ALL=C，镜像 stdlib tomllib 文法：解码点路径表头/键、完整字符串/inline/数组值、根级 `package=[{…}]` 同一数组、tomllib 重复键注册表），不可解析/不可排除 pin 一律 exit 2 fail-closed；无 Python 依赖与三态出口语义逐字保留 |
| [r10-runtime.score.json](r10-runtime.score.json) | r10 | 开发者自评结果（93.1 / A / 无闸门；D16 fixed；D2 partial、D3 open 留待后续轮；runtime 源零改动，cli@03c900e7…） |
| [r10-runtime.quality.md](r10-runtime.quality.md) | r10 | `quality_run.py` 机器测量报告（112 passed、重复率 2.13%、CC>10 28.32%） |
| [r10.score.txt](r10.score.txt) | r10 | 自评 `score_landing.py` 输出（93.1 / A / 无闸门）；round_diff r9→r10 rc=0 无回归；修复证据 [r10-fix-evidence](/Users/payne/.dsh/state/agent-teamwork/team/r10-fix-evidence/)（lock-results.json、lock-edges-results.json、lock-control-results.json、lock-fuzz-results.json、lock-fuzz-invalid-results.json 及探针脚本） |
