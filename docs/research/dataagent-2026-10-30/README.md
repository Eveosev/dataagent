# DataAgent 调研（2026-10-30）

本目录是「DataAgent 市场调研 + MintHub 落地方案」的完整证据与交付物。

## 先读哪一篇

| 文件 | 内容 | 适合谁 |
|---|---|---|
| **[DataAgent-调研与落地方案-2026-10-30.md](DataAgent-调研与落地方案-2026-10-30.md)** | 主报告：市场地图、能力拆解、benchmark、中国市场、MintHub bundle/preset/app 设计、路线图、风险 | 所有人；决策者读第 1、7、8 节即可 |
| [sections/00-summary.md](sections/00-summary.md) | 一页结论（十条判断 + 只做三件事 + 现在/未来一览） | 时间有限时先读这个 |
| [sections/80-roadmap.md](sections/80-roadmap.md) | 0–3 / 3–9 / 9–18 月路线图、决策门 | 产品/研发负责人 |
| [sections/90-appendix.md](sections/90-appendix.md) | Ontology YAML 草案、`mint.toml` 示例、关键来源 | 工程实现 |

## 证据文件（子 Agent 原始产出）

| 文件 | 覆盖 | 关键结论 |
|---|---|---|
| [parts/A-commercial.md](parts/A-commercial.md) | 16 家商业厂商（Databricks/Snowflake/Microsoft/Google/ThoughtSpot/Tableau/Qlik/AWS/Palantir/AtScale/Cube/dbt/Kyligence/Sigma/Dataiku） | 四种形态；语义层成为可分发资产；Databricks knowledge store 与应用级语义层 |
| [parts/B-opensource.md](parts/B-opensource.md) | 55 个开源项目 | 八成可复用；缺 join 发现、语义层 diff/召回、RLS DSL；许可雷区 |
| [parts/C-benchmarks.md](parts/C-benchmarks.md) | 20+ benchmark | BIRD 饱和、交互式是分水岭、分数不可跨 harness 比较；评测矩阵与 14 个任务模板 |
| [parts/D-academic.md](parts/D-academic.md) | 2024–2026 论文 | 召回优先、多候选+选择器、澄清收益、编排不总是增益 |
| [parts/E-standards-connectors.md](parts/E-standards-connectors.md) | Ossie / MCP / dbt / Cube / Palantir | 用 Apache Ossie 0.1.1；MCP 2026-07-28 已无状态；控制面与数据面分离 |
| [parts/F-china-market.md](parts/F-china-market.md) | 中国市场 25+ 产品 | NL2SQL 非护城河；指标平台是入场券；文件→受治理指标是空档 |
| [parts/G-kernel-packaging.md](parts/G-kernel-packaging.md) | MintHub/Kernel 源码级能力边界 | bundle 可带 MCP；工具命名即权限；60s 超时；升级不迁用户数据 |
| [parts/H-ontology-schema-draft.md](parts/H-ontology-schema-draft.md) | Ontology 载体设计稿 | 五层分离、Ossie 兼容、稳定 ID、证据与策略字段 |

## 补充材料（更细的一手引用）

| 文件 | 内容 |
|---|---|
| [01-commercial-landscape.md](01-commercial-landscape.md) | 商业竞品的逐条原文证据（快照式，带 [S]/[D]/[L] 编号与页面日期），覆盖 Snowflake/Databricks/Looker/Fabric/Spotter/Palantir/Quick BI/FineBI/Hex/dbt/Cube/观远 |
| [03-benchmarks-and-evaluation.md](03-benchmarks-and-evaluation.md) | Benchmark 的评测器级细节（Spider2 / BIRD / LiveSQLBench / BIRD-Interact / BEAVER / BIRD-CRITIC / DSBench / SpreadsheetBench / GIFT-Eval / Monash）与分层评测建议 |

这两份是子 Agent 的原始落盘，引用粒度比主报告更细，适合做尽调或复核；主报告已吸收其关键结论。

## 五个最重要的判断

1. 单轮 NL2SQL 已商品化（BIRD Test 83.40% vs 人类 72.37%），竞争转到语义资产、交互与交付物。
2. 交互是真正的鸿沟：BIRD-Interact 16.33%；Spider 2.0 同题 23.58%→96.70% 的差距来自 scaffold。
3. 开源缺三个关键件：产品级 join 发现、语义层 diff→影响面→召回、RLS DSL——这是自研重点。
4. MintHub 形态：`bundle`（能力 + MCP + Skill）+ `preset`（精确锁），`plugin`/`mcp` 今天装不下。
5. 中国最锋利的切入点：文件即席分析 → 一键升格为受治理指标。

## 调研方法

7 个并行子 Agent + 主 Agent 交叉核对；web_search 不可用，全部用 `web_fetch` / `curl` / GitHub API / arXiv API 直取一手来源。无法核实的一律标注，未做推断。详见主报告第 2 节。
