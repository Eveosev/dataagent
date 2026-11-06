---
date: 2026-11-05
scope: docs/
source: 自 AgentOS docs/STATUS.md「DataAgent」节迁入（2026-11-06）
---

# 文档状态

| 状态 | 含义 | 处理 |
|-|-|-|
| 现行 | 当前基线或仍被引用的依据 | 保留 |
| 证据 | 历史快照、评审对象、生成输入 | 保留，不作为基线 |
| 过期 | 已被替代，或依据的版本已落后 | 保留备查；引用时改指替代文档 |
| 无用 | 重复副本、过程片段、散落代码、缓存 | 删除候选，删除前确认 |

已在原位标记：`docs/design/dataagent-*-v0.1/README.md`（`status: superseded` + `superseded_by`）、`docs/research/dataagent-2026-11-01/README.md`（状态行）、`docs/research/dataagent-2026-11-02/README.md`（逐项状态表）。其余目录以本表为准。

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
