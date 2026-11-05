# DataAgent · 2026-11-02

当前设计以 [`../dataagent-2026-11-03/`](../dataagent-2026-11-03/README.md) 为准。

| 路径 | 状态 | 说明 |
|-|-|-|
| [online-r1024-review.md](online-r1024-review.md) | 现行（依据） | 修订 R1–R8 的依据；`dataagent-2026-11-03/tools/build.py`、`to_feishu.py` 引用 |
| `sources/feishu-r1045/` | 现行（生成输入） | `dataagent-2026-11-03/tools/build.py` 的 `SRC`；删除或改动会使 00–04 无法重新生成 |
| `sources/freeze-v0.2-2026-11-03/` | 现行（冻结） | v0.2 冻结：飞书六篇导出、总 Catalog 记录、`manifest.json` |
| `sources/feishu-r1024/` | 证据 | `online-r1024-review.md` 的评审对象 |
| `sources/pluggable-dataagent-*-revision-*.{json,xml}` | 证据 | 飞书 r958 / r1022 回写前后快照 |
| `spec/` | 过期 | 基于 r953 的本地 spec 与决策 D1–D12；被 `dataagent-2026-11-03/01–05`、`06–08` 替代 |
| `Pluggable-DataAgent.md` | 过期 | 飞书总规划 r953 导出（`spec/` 的依据）；被 `dataagent-2026-11-03/00-pluggable-dataagent.md` 替代 |
| `Pluggable-DataAgent_claude.md`、`pluggable-dataagent_codex.md`、`Pluggable-DataAgent_glm.md` | 过期 | 三个模型的并行改写稿，无入链；已由 `archive/Pluggable-DataAgent-v2.md` 合并 |
| `archive/` | 过期 | `Pluggable-DataAgent-v2.md`、`-v3-rich.md` 早期版本，无入链 |
