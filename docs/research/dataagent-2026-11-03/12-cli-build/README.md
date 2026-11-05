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
