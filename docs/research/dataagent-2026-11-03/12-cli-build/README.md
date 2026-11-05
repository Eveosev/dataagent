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
