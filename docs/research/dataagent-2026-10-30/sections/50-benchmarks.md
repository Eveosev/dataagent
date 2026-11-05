## 5. Benchmark 与真实差距：分数涨了，产品没跟上

### 5.1 榜单现状（截至 2026-10-30）

| Benchmark | 考什么 | 规模/形态 | 当前最好成绩 | 关键结论 |
|---|---|---|---|---|
| **BIRD** | 单轮 text-to-SQL，真实脏数据 + 外部知识 + 效率 | 95 个库、33.4GB、12,751 问 SQL 对、37 领域（官方页） | Test EX **83.40%**（AT&T AskData，2026-10-22）；人类 Test 72.37% / Dev 92.96% | Test 上机器已越过人类均值；前排被中国团队占据（华为 82.39、腾讯 82.28） |
| **BIRD-Interact**（ICLR 2026 Oral） | 交互式：对话澄清 + agentic 主动探索，含 CRUD | 600 任务（Full）/300（Lite），PostgreSQL | Full **16.33%**（2025-08）；GPT-5 Medium 8.67%（c-Interact）/17.00%（a-Interact） | **交互是真正的鸿沟**；"交互时间扩展"（ITS）只有少数模型成立 |
| **Spider 2.0** | 企业级真实工作流：超大 schema、多方言、项目级上下文 | 632 题（Snow 547 / DBT 68 / Lite 547） | Snow 榜首 **96.70**（Genloop Sentinel v2 Pro，2026-10）；同一题集 Spider-Agent+o1-preview 仅 **23.58%**；论文期 o1-preview 17.1% | **分数是 scaffold 的产物**：同一题集从 5.48% 到 96.70%，差 17 倍；真正考验元数据检索、方言、长上下文 |
| **LiveSQLBench / DII**（BIRD 团队，2025-05 起） | 防污染、持续更新的活库；2026 起加"业务上下文理解 + 语义建模" | Base/Large；Large 每库约 54 表、~1K 列、480 任务、平均 84K prompt tokens | Gemini-2.5-pro 口语化查询 28.67、常规 35.67（Base） | 明确把 **语义建模** 纳入评测——与我们的方向一致 |
| **Spider 1.0 / SParC / CoSQL** | 经典单轮/多轮 | — | 已被刷到 90%+ | 只适合做回归，不适合做卖点 |
| **Dr.Spider / AmbiQT** | 鲁棒性 / 歧义 | — | — | 企业场景必测，但少有人报 |
| **BIRD-CRITIC（=SWE-SQL）** | SQL 调试与修复（不是生成） | 600 dev + 200 OOD，多方言 | — | 与问数链路只部分重叠，但对 Agent 自我修复有参考价值 |
| **DABench / DA-Code / DSBench / DABstep / SpreadsheetBench / InfiAgent-DABench** | 数据分析 agent：多步、代码、表格、真实业务 | 规模不一 | Data Interpreter 在 InfiAgent-DABench 上 75.9→94.9（论文自报） | 更接近"分析"而非"问数"；适合验证 function 层 |

三条必须说清楚的话：

1. **BIRD 高分不等于企业可用。** BIRD 的 schema 是给定的、问题是有标准答案的、外部知识是标注好的；企业现场是"1000 张表、没有注释、口径在老板脑子里"。
2. **Spider 2.0 的分数差才是企业真相。** 同一 547 题，Spider-Agent+o1-preview 23.58%，Genloop Sentinel v2 Pro 96.70%——差 4 倍。差距不在基座模型，在 scaffold（元数据检索、方言、项目上下文、执行反馈）。**引用 Spider 2.0 分数必须同时报 harness，否则没有意义。**
3. **BIRD-Interact 的 16% 说明"会问问题"比"会写 SQL"更难。** 这正是我们把澄清做成显式协议的理由（见 4.2.4）。

### 5.2 现有 benchmark 测不到的东西

| 能力 | 为什么测不到 | 我们的替代验证 |
|---|---|---|
| ontology 构造质量 | 没有"给定库，产出语义层"的标准评测 | 自建：给定 20 张表，人工标注 30 个实体/指标/join，比 P/R |
| 指标口径一致性 | BIRD 只比结果集，不比口径 | 自建：同一指标多问法，检查是否走同一 metric |
| 权限与治理 | 公开集没有 RLS/CLS | 自建：带行过滤的账号，检查越权率 = 0 |
| 多轮协作 | 单轮为主 | BIRD-Interact + 自建澄清集 |
| 成本/延迟 | 论文很少报 | 自建：每次问答的 LLM 调用数、token、P95 |
| 可维护性 | 无法评测 | 自建：ontology 升级后回归通过率 |

### 5.3 我们自己的评测集：DA-Bench（内部）

**六个任务族，首版 150 题**（每族 25 题），跑在 3 个真实库 + 5 个文件数据集上：

| 族 | 考什么 | 通过标准 | 题数 |
|---|---|---|---|
| A. 元数据问答 | "orders 表的主键是什么""哪些表有 region" | 精确匹配 / 集合匹配 | 20 |
| B. 指标问答 | "上月华东 GMV""今年新客 ARPU" | 结果集比对（容差 0.1%）+ 必须命中指定 metric | 40 |
| C. 值召回 | "已付款订单""华东大区" | 生成的 WHERE 必须包含正确枚举/值映射 | 20 |
| D. Join 推理 | 跨 3 表、含桥表、含 fan-out 陷阱 | 结果正确 + join 路径合法 | 25 |
| E. 歧义澄清 | "最近的销售情况""大客户" | 必须提问或显式声明假设；不得静默选一个 | 20 |
| F. 多步分析 | 同比 + 下钻 + Top-N + 归因 | 最终表正确 + 中间产物可追溯 | 25 |

**指标口径**（每次回归都报）：

- **答案正确率**：执行结果比对，B/C/D 族用；A 族用精确匹配。
- **口径符合率**：答案是否走了指定的 metric/ontology 版本（人工抽检 30%）。
- **澄清精确率**：该问的问了、不该问的没问（E 族）。
- **平均轮次 / P95 延迟 / 单问 LLM 调用数 / 单问 token**：成本四件套。
- **越权率**：必须为 0（红线）。
- **回归通过率**：ontology 升级后重跑，作为发布门禁。

**任务模板示例**（可直接落 YAML）：

```yaml
- id: B-001
  family: metric
  question: 上个月华东区的 GMV 是多少？
  ontology: sales@2.3.0
  expect:
    metric: gmv
    filters: {region: 华东, month: "2026-09"}
    tolerance: 0.001
  must_not: [use_raw_sum_without_tax]
- id: E-003
  family: ambiguity
  question: 最近的销售情况怎么样？
  expect:
    behavior: clarify        # 必须问"最近"指哪段时间、销售指 GMV 还是订单数
    max_rounds: 2
- id: D-007
  family: join
  question: 每个客户的首次下单金额分布
  expect:
    joins: [orders, customers]
    forbid_fanout: true
```

### 5.4 对外怎么报数

- 只报**可复现**的数字：benchmark 版本、日期、模型、prompt 版本、候选数、成本。
- 同时报 **BIRD（单轮能力）、BIRD-Interact（交互能力）、DA-Bench（企业能力）** 三个维度，不要只报最高的那个。
- 把"我们没做什么"写清楚（例如"未做跨库联邦""未做写回"），比夸大更能建立信任。
