---
date: 2026-11-05
scope: docs/
---

# 文档状态

| 状态 | 含义 | 处理 |
|-|-|-|
| 现行 | 当前基线或仍被引用的依据 | 保留 |
| 证据 | 历史快照、评审对象、生成输入 | 保留，不作为基线 |
| 过期 | 已被替代，或依据的版本已落后 | 保留备查；引用时改指替代文档 |
| 无用 | 重复副本、过程片段、散落代码、缓存 | 删除候选，删除前确认 |

2026-11-05 已删除并修复受影响链接：`dev/rsi_toolkit/` 下 16 份与 `apps/plugins/rsi-toolkit/docs/design/` 重复的文档、5 个 `cloud-*.xml`、3 个散落脚本；`design/dataagent-design-v0.1/feishu-publication/`；`dev/.DS_Store`；`dev/rsi_toolkit/`、`research/dataagent-2026-11-03/`、`research/dataagent-2026-11-01/` 下的 `__pycache__/`。

2026-11-05 已删除 Collaboration OS 项目文档（已有其他实现）：`research/collaboration-os-2026-10-31/`（20 个文件）、`superpowers/plans/2026-10-31-codecollabration-{program,plugin-foundation,runtime,delivery}.md`、`2026-10-31-pilotdeck-native-trajectory.md`。

已在原位标记：`docs/design/dataagent-*-v0.1/README.md`（`status: superseded` + `superseded_by`）、`docs/research/dataagent-2026-11-01/README.md`（状态行）、`docs/research/dataagent-2026-11-02/README.md`（逐项状态表）、`docs/architecture/2026-10-30-ql-audit-mint-plugin.md`（状态行）、`docs/dev/rsi_toolkit/README.md`（索引逐项标注）。其余目录以本表为准。

## DataAgent

| 路径 | 状态 | 说明 |
|-|-|-|
| `research/dataagent-2026-11-03/` | 现行 | 当前设计与实施，入口 `README.md` |
| `research/dataagent-2026-11-02/online-r1024-review.md` | 现行 | 修订 R1–R8 的依据；`11-03/tools/build.py`、`to_feishu.py` 引用 |
| `research/dataagent-2026-11-02/sources/feishu-r1045/` | 证据 | `11-03/tools/build.py` 的 `SRC`，删除后 00–04 无法重新生成 |
| `research/dataagent-2026-11-02/sources/freeze-v0.2-2026-11-03/` | 证据 | v0.2 冻结 |
| `research/dataagent-2026-11-02/sources/` 其余 | 证据 | r1024 导出、r958 / r1022 回写前后快照 |
| `research/dataagent-2026-11-02/spec/` | 过期 | 被 `11-03/01–05`、`06–08` 替代 |
| `research/dataagent-2026-11-02/Pluggable-DataAgent*.md`（4 份）、`archive/` | 过期 | 被 `11-03/00-pluggable-dataagent.md` 替代；无入链 |
| `research/dataagent-2026-11-01/` | 过期 | 被 `11-03/00` 与总 Catalog 替代 |
| `design/dataagent-design-v0.1/`、`dataagent-{data,application,governance,operations-fde}-layer-v0.1/` | 过期 | 基线 r1022，分别被 `11-03/00–04` 替代；各目录 `atomic-capability-catalog.json` 被 `11-03/catalog/` 替代 |
| `research/dataagent-2026-10-30/` | 现行（调研） | 市场、开源、benchmark 调研仍有效；§7 MintHub 产品设计、§8 路线图已被 `11-03/00` 切片与 `06–08` 替代 |
| `research/dataagent-landscape-2026-10-31/`、`dataagent-retrieval-2026-10-31/` | 现行（调研） | 被 `11-03/00` 附录 A 调研参照引用 |
| `research/fde-agent-2026-11-02/README.md` | 现行（概念） | 六个基础模块概念页；能力定义以 `11-03/04-operations-fde-layer.md` 为准 |
| `research/fde-agent-2026-11-02/archive/` | 过期 | README 已标“结论已被本页取代” |

### `dataagent-2026-11-03/` 内的问题

| 位置 | 问题 |
|-|-|
| `06-data-layer-build-plan.md` §12 | 未登记 `r19-fixes.md`、`r20-fixes.md`、`r21-fixes.md`、`rule-decision-code-inventory.md`；文首 `status` 停在 Round 17 |
| `06-data-layer-build/r21-fixes.md:3` | 链接 `../../../.dsh/state/agent-teamwork/team/reviewer_r21_report.md` 目标不存在 |
| `08-governance-layer-build-plan.md` | `status: 待评审`，`packages/capabilities/dataagent-governance` 已有实现 |
| `README.md` 文件表 | 缺 `07-08-feasibility-review-2026-11-04.md`、`w0-seam-specifications.md` |
| `README.md`「未完成」、`06`–`08` 文首 | 内核依据 `agent-kernel@f0fa521`；可行性评审已核到 `c1231abf` |
| `feishu/06-data-layer-build-plan.md`、`feishu/01–04` | 生成于 11-03；本地 `06` 已到 11-05，`01–04` 于 11-04 重新生成。推送前重跑 `sync_feishu.py prepare` |
| `09-benchmark/tasks/` | 10142 个文件 / 331 MB 评测数据，放在 docs 目录下 |

## RSI Toolkit / iface

| 路径 | 状态 | 说明 |
|-|-|-|
| `superpowers/specs/2026-10-28-rsi-iface-v2-design.md`、`-rsi-package-pages-and-tests.md`、`-rsi-cpmrt-transport-design.md` | 现行 | v2 设计、配套规范、M6 需求基线 |
| `superpowers/plans/2026-10-28-rsi-iface-v2-m0-m1.md` | 现行 | v2 首批实施计划 |
| `superpowers/specs/2026-10-28-rsi-iface-modularization-design.md`（方案 B） | 过期 | 被 v2 替代 |
| `superpowers/specs/2026-10-27-pluggable-rsi-toolkit-design.md` | 过期（部分） | 里程碑被 v2 统一；trace / 经验 / recall 契约尚无其他文档承接 |
| `superpowers/plans/2026-10-27-harness2-benchmark-mint-test.md`、`-real-benchmark-execution.md` | 过期 | 已执行的一次性计划 |
| `architecture/rsi-toolkit-design.md`、`2026-10-28-rsi-toolkit-设计理念与落地规划.md`、`rsi-toolkit-modules.toml`、`package-layout.md` | 现行 | 产品设计、技术配套、模块清单、包布局 |
| `dev/rsi_toolkit/README.md`、`iface-review/README.md`、`iface-review/B-revised-2026-10-29.md` | 现行 | 入口；C1–C7 当前口径 |
| `dev/rsi_toolkit/mint-rsi-iteration-results-2026-10-27.md` | 证据 | Job-Bench / WorkBuddy 唯一完整结果 |
| `dev/rsi_toolkit/2026-10-27-usability-and-rsi-landscape.md`、`-host-hooks-and-adapter-review.md` | 现行（调研） | 被 `architecture/rsi-toolkit-design.md` 附录 C 引用 |
| `dev/rsi_toolkit/2026-10-28-iface-modularization-and-minthub.md`（方案 A）、`-iface-plan-rationale.md`、`-iface-plans-review.md` | 过期 | 被 v2 替代 |
| `dev/rsi_toolkit/2026-10-28-mint-platform-notes.md` | 过期 | 基于 Mint CLI 0.1.11 |
| `dev/rsi_toolkit/2026-10-27-pluggable-plugin-and-experience-feasibility.md` | 过期 | 被 `-host-hooks-and-adapter-review.md` 修正 |
| `dev/rsi_toolkit/iface-review/A`、`C`、`D`、`E`、`E1`、`E2`、`B-capability-contracts.md`、`F-upstream-delta-2026-10-29.md` | 过期 | 被 v2 与 `B-revised` 替代；D、F 基于 `kernel-iface` 0.1.0 |
| `dev/rsi_toolkit/mint-iface/` | 过期 | 被 `packages/agent-kernel/scripts/sync-iface-packages.sh`、`publish-iface-mint-hub.sh` 替代 |
| `dev/rsi_toolkit/cloud-handoff.md`、`cloud-artifacts.md`、`mint-hub-publish-plan.md`、`real-benchmark-results-2026-10-27.md`、`harness2-repro-research.md`、`mint-rsi-benchmark-iteration-plan.md`、`mint-rsi-iteration-review-2026-10-27.md`、`rsi-benchmark-process-media.md`、`rsi-evidence-audit.md` | 过期 | 10-27 首版交接、已执行计划、一次性评审 |
| `dev/rsi_toolkit/progress.md` | 证据 | 比 `apps/plugins/rsi-toolkit/docs/design/progress.md` 多“02:36 Handoff”一节，保留 |

已修复：`dev/rsi_toolkit/README.md` 索引加入 v2 并标注方案 A 等为过期；`architecture/package-layout.md`、`architecture/rsi-toolkit-design.md` 的 IFace 链接改指 v2，附录 C 删除方案 A 链接；`package-layout.md` 改为 cpmrt 已随 `mint/core` 0.1.14 发布。

## ql-audit

| 路径 | 状态 | 说明 |
|-|-|-|
| `architecture/2026-10-30-ql-audit-mint-plugin.md` | 过期 | 方案 A，对应 `apps/plugins/ql-audit-plan-a`；主线 `apps/plugins/ql-audit` 采用方案 B，以其 `docs/design.md`、`implementation-plan.md` 为准 |
| `dev/ql-audit/2026-10-30-minthub-research-and-proposal.md` | 过期 | 文件头已标“已由模块化优化方案替代” |
| `dev/ql-audit/2026-10-30-minthub-modular-proposal.md` | 过期 | 实施依据为 `apps/plugins/ql-audit/docs/` |
| `dev/ql-audit/2026-10-30-modular-comparison.md` | 过期 | A / B 均已实现 |

## Mint 与官方资料

| 路径 | 状态 | 说明 |
|-|-|-|
| `official/` | 现行 | 飞书原文抄录与摘要 |
| `mint/2026-10-28-Mint指南梳理.md`、`2026-10-28-文档口径审计.md` | 现行 | core 0.1.14 / cpmrt 拆分后的口径 |
| `mint/README.md` | 过期 | 基线 CLI 0.1.10 / core 0.1.9；与 `apps/plugins/rsi-toolkit/docs/mint/README.md` 逐字节相同 |
| `2026-10-30-Mint-Iface-MintHub-开发难点梳理.md` | 现行 | 无入链 |

## 标准与 rubric

| 路径 | 状态 | 说明 |
|-|-|-|
| `standards/code-landing-rubric.md` | 现行 | 代码落地质检标准 v2：12 代码轴 + 6 落地轴 / 45 条二值规则 / 7 条硬规则 / 依据分级 |
| `standards/code-landing-rubric.json` | 现行 | 机器可读 rubric，`score_landing.py` 的输入；改规则须升 `version` |
| `standards/score_landing.py` | 现行 | 评分脚本：加权、硬规则封顶、unknown 语义、`--self-test` / `--template` / `--partial` |
| `standards/example-governance.score.json` | 证据 | 2026-11-05 对治理层的示例判定，来源为三层审计，不是正式验收结论 |
| `skills/code-landing-quality/SKILL.md` | 现行 | 项目级 skill：按方案开发 → 清单 → 快检 → rubric 评分 → 报告；已链到 `~/.dsh/skills` |
| `skills/code-landing-quality/scripts/plan_checklist.py` | 现行 | 从方案文档抽取 MUST/验收清单（JSON/Markdown），供逐条回填 rubric |
| `skills/code-landing-quality/scripts/quality_run.py` | 现行 | 跑测试、重复率、bundle 漂移、复杂度并调用评分器；`--out` 出报告，失败退出 1 |

## 杂项

| 路径 | 状态 |
|-|-|
| `standards/__pycache__/` | 无用 |
| `docs/**/.claude/`（10 个空目录） | Claude Code 写入记录目录，不属于文档 |
