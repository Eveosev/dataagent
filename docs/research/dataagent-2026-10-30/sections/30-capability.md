## 4. 能力拆解：三个子问题，各自的最优解与坑

> 这一节回答"具体怎么做"。结论来自开源代码（B）、论文（D）、标准（E）与厂商文档（A）的交叉验证；凡是只有厂商宣称、没有第三方复现的，标注"宣称"。

### 4.1 数据探查与 ontology 构造

#### 4.1.1 自动化的天花板在哪

把这件事拆成 8 步，每步的自动化程度差别很大：

| 步骤 | 能自动到什么程度 | 主要方法 | 人的角色 |
|---|---|---|---|
| 枚举对象 | 100% | `information_schema` / catalog API，分页 + 上限 | 选建模范围 |
| 画像 | 100% | SQL 直算：类型、空值率、基数、分位、Top-K、唯一性 | 无 |
| 主键/唯一键 | 90% | 唯一性 + 非空 + 命名模式 + 与业务 ID 格式匹配 | 冲突时裁决 |
| 外键/包含依赖 | 70–85% | 值重叠率、IND 算法（Spinder/Binder/Mind）、命名相似、类型兼容 | 低置信度确认 |
| 表/列语义命名 | 80% | LLM + 领域词典 + 历史注释 | 抽样审阅 |
| **指标口径** | **30–50%** | LLM 从列名/枚举/历史 SQL 提议公式 | **必须人审** |
| 已验证问答 | 40% | 从历史查询日志、用户反馈挖掘 | 逐条确认 |
| 发布 | 95% | 校验 + 审批流 | 审批人 |

**判断：把工程预算压在 1–5 步，把人力压在 6–7 步。** 反过来做（追求全自动指标生成）会得到一堆"看起来对、口径不对"的指标，比没有更危险。

#### 4.1.2 join 发现：唯一没有产品级开源实现的关键件

现状很清楚：语义层里的 join 全靠手写；开源只有 Metanome（197★，2025-06 停更）和 HPI 的 IND 算法集（13★，2019 停更）。学术界 2026 年开始工程化：SemJoin 用 advisor 在"聚类剪枝"和"分类器"间路由（比 adaptive block join 高 20–33 F1 且 token 更少）；Uber-Join 把 join 放进预算约束的多臂老虎机，用抽样验证给出精度保证。这两个工作说明一件事：**LLM 全量 pair 比较在成本上不可行，必须先剪枝再判定。**

建议的四段流水线（也是我们的差异化点）：

```text
probe       对每列采样（如 2000 行）、算基数/空值/最小最大/长度分布
candidates  候选生成：命名相似（customer_id / cust_id）+ 类型兼容 + 值重叠率
            + 共现（同一查询里出现过）+ 复合键组合；剪到每表 top-20
verify      对候选做有界采样验证：重叠率、包含方向、唯一性 → 推断基数
            （1:1 / 1:N / N:1 / N:M），记录失败样本
propose     LLM 只做「语义判定 + 命名 + 解释」，输入是证据包而非裸 schema；
            输出带 confidence、evidence、proposed_by，进入 review 队列
```

成本控制：`verify` 阶段的采样查询要合并成一条 SQL（多列 `COUNT(DISTINCT)` + 交集），单表一次，避免 N×M 次往返。经验阈值：重叠率 <0.6 直接丢弃，0.6–0.95 进人工，>0.95 且方向唯一自动通过；唯一性决定基数。

#### 4.1.3 ontology 的载体：用 Ossie，不自造

2026 年这件事已经没有争议：**Open Semantic Interchange（OSI）已于 2025-12-11 发布 0.1.1，2026-06-22 进入 Apache 孵化并更名 Apache Ossie**，50+ 组织站台（Snowflake、Databricks、dbt Labs、Cube、AtScale、Salesforce、Oracle、DataHub、Collibra、Alation、Atlan、Informatica），7 个官方转换器，dbt v1.12 已能原生解析 `osi/` 目录。Ossie 0.2.0.dev0（2026-05-29）还加了 **ontology 规范 + mapping 文档**：concept（EntityType/ValueType）、relationship（roles、multiplicity、verbalizes、identify_by、derived_by、requires）、可选 IRI，以及 object_mappings / link_mappings。

对我们的三个直接结论：

1. **不要自造对外格式，也不要用 OWL 承载。** 用 Ossie 的维度模型表达 dataset/field/metric/relationship，用 Ossie ontology 表达概念与关系，用 mapping 落到物理字段；需要外部知识图谱时用 `iri` 单向挂接（schema.org / org / FOAF），只做导出视图。
2. **锁 0.1.1，不追 0.2.0。** 0.2.0 是破坏性的（`semantic_model` 数组 → 扁平单文档；名字解析从 source 列改为 dataset field），而 dbt v1.12 只接受 `0.1.0`/`0.1.1`，其他版本字符串直接 parse error。做法：**按 0.2.0 的语义思考，按 0.1.1 落盘**，中间加一层 `to_ossie_0_1_1()` 适配器，等 dbt v2 支持再切。
3. **三层文件，各自独立版本。** 语义模型（随数仓变）、概念本体（随业务语言变）、物理映射（随建模习惯变）分开；合成一个文件会让每次物理改动都触发本体版本跳变，diff 噪声淹没真正的语义变更。

版本化必须自己补三样 Ossie 没有的东西：

| 缺口 | 我们的做法 |
|---|---|
| 稳定 ID | 每个 entity/field/metric/join 一个 ULID，**与 name 解耦**。Ossie 的 name-as-id 仍是未决 issue #31；没有稳定 ID，重命名 = 删除+新建，血缘断链。 |
| 内容寻址 | canonical JSON（RFC 8785 JCS）+ sha256，用于检测"语义没变但序列化变了"，避免无意义重编译。 |
| 语义 diff | 机器用 RFC 6902 JSON Patch；人用按 entity/field/metric/join 分类的语义 diff，标 breaking / non-breaking。再加**影响面分析**：这个改动会让哪些指标、哪些 verified query、哪些 dashboard 失效。 |

#### 4.1.4 企业库的坑（按痛感排序）

1. **万级表**：物理枚举绝不进上下文。只暴露"已建模"对象；未建模走 `list_objects` 分页（单次 ≤50），服务端检索，命中后才回传候选。
2. **方言**：不要写"通用 SQL"。Ossie 的多方言表达式就是为此设计；落库按 dialect 选形，缺失回退主形并记 warning。国产库（达梦、人大金仓、GaussDB、OceanBase）必须有方言适配包，BIRD 上达梦 Blender-SQL 74.51 已证明可行。
3. **权限**：行级/列级必须**下推到数据库**（RLS/CLS、Snowflake row access policy、PG RLS）。MCP server 里的过滤只是二次校验；ClickHouse 文档自己写明"destructive gate 不是安全边界，边界是 grant"。连接必须用专用只读角色。
4. **视图/存储过程**：只把视图当表读；存储过程一律不进 agent 可见面（副作用不可控）。
5. **成本**：三道闸——`EXPLAIN` 预估 → `max_scan_bytes` 拒绝 → 运行时 `timeout_ms` + `KILL QUERY`。没有 EXPLAIN 的库退化为"采样估算 + 强制 LIMIT"。
6. **连接池**：MCP 2026-07-28 已变无状态（删了 initialize 握手、删了 Mcp-Session-Id），连接复用完全落在 server 内部，必须显式配池上限，否则 agent 并发一上来就打爆数据库连接数。

### 4.2 智慧问数：召回、生成、校验、澄清

#### 4.2.1 召回顺序：指标优先，不是表优先

传统 RAG 是"表 → 列 → 值"，企业问数应该反过来：

```text
问题 → 意图（指标/维度/时间/过滤/对比）
     → 指标召回（metric 名 + 同义词 + 描述 + 历史问法）      ← 先命中"GMV"这个业务概念
     → 实体召回（metric 所属 entity，以及可以下钻的维度实体）
     → 字段召回（该实体下参与计算的列，≤30 列）
     → 值召回（枚举/Top-K/同义词/脏值映射）
     → join 路径（在 join 图上找最短且基数安全的路径）
```

为什么指标优先：业务用户问的是"上月华东 GMV"，不是"orders 表里 sum(pay_amount)"。先命中指标，join 路径和过滤条件都由指标定义带出来，准确率和可解释性都更高。Snowflake Cortex Analyst 的 Semantic Views、Databricks 的 Metric Views、dbt 的 metric 都是这个思路。

值召回是最容易被低估的一环。痛点不是"找不到"，而是"值和问题里的表述不同形"：枚举里是 `paid/refunded`，用户说"已付款"；地区表里是"华东大区"，用户说"华东"。工程上成熟的做法是 **embedding + BM25 混合 + LSH/倒排剪枝，再对 top-k 列做 cell matching**；领域同义词表人工维护一小份高置信映射，比让 LLM 每次现推稳定。

上下文预算的硬指标：**生成阶段 ≤30 列**。CHESS 的 Schema Selector 把列数压到几十，换来约 +2% 准确率和 5 倍 token 下降；ReFoRCE 的表分组压缩也是同一逻辑。召回阈值应偏松（漏一列几乎必错，多几列只是费 token），用"候选集 + 二次判定"而不是"一次硬过滤"。

#### 4.2.2 生成与选择：按难度路由，不要全局开满

2024–2026 的方法论已经收敛：单次生成 → 多候选 + 选择器是主线，但收益与成本是对数关系。CHASE-SQL（三生成器 + 成对比较选择）、MCS-SQL（多 prompt + 置信度过滤）、Agentar-Scale-SQL（RL + 迭代精修 + 锦标赛选择）都是这个套路；BIRD 公开榜从 55.9% 推到 81.67%（2025-09），2026-10 已被推到 83.40%（AT&T AskData）。

dbt 的 join 逻辑已经证明：join 不是"模型自由发挥"，而是语义层的能力——它有 allowed matrix（哪些实体允许 join）、EXPLAIN 与 hop 上限。我们的 join 路径规划也应如此：**先在图上找合法路径，再让模型写条件**，而不是让模型直接拼 JOIN。

生产上不应该对所有问题开满候选。建议路由：

| 问题特征 | 策略 | 预算 |
|---|---|---|
| 单表、指标明确 | 单次生成 + 校验 | 1 次 LLM |
| 2–3 表 join、有指标定义 | 单次 + 执行反馈修复（最多 2 轮） | 2–3 次 |
| 多表/多库、口径歧义、超大 schema | 多候选（3–5）+ 选择器 + 澄清 | 5–8 次，带硬上限 |

#### 4.2.3 校验：语法、逻辑、质量三段

- **语法**：parse（sqlglot 或目标库 parser）+ 列存在性 + 方言合法性。dry-run / `EXPLAIN` 能挡住大部分低级错误。
- **逻辑**：指标定义是否被正确展开（过滤条件、时间窗口、去重口径）；join 是否造成 fan-out（一对多放大）；NULL 语义；除零。
- **质量**：结果行数/量级是否异常（同比突变 10 倍）、空结果是否有合理解释、是否有未使用的过滤条件。
- **语义**：执行通过 ≠ 语义正确。2026-10 的 Beyond Correctness 指出 agent 会用"碰巧对上答案的未验证假设"蒙混过关，必须让模型显式披露假设，并配语义校验。

#### 4.2.4 澄清：做成显式协议，不是模型的即兴行为

这是当下投入产出比最高的体验改进。DSABench（2026-10）显示多库任务 Route+Exec 成功率仅 6.69–7.98%，给一次澄清后升到 11.44–13.25%，最优 16.99%；歧义任务上，澄清把"正确分支源召回"提高 39.8–43.2pp。BIRD-Interact（ICLR 2026 Oral）更直接：SOTA 模型在 600 个交互式任务上只有约 16% 成功率，最好的模型也只在"交互时间扩展"（ITS）上勉强成立。

落地要点：
- 维护 **question pool**：每个识别出的歧义必须"问"或"显式放弃并记录假设"，不能静默跳过。PlanPool 指出的失败根因正是"过早终止澄清"。
- 默认 1 轮、最多 2 轮；问题要可点选（口径 A / 口径 B / 都不是），不要开放式提问。
- 最终答案必须附"我假设了什么"，让用户能一眼看出偏差来源。

#### 4.2.5 失败模式清单（上线前逐条打勾）

| 失败模式 | 症状 | 对策 |
|---|---|---|
| 指标错配 | 用了相似名字的另一个指标 | 指标优先召回 + 同义词白名单 + 口径确认 |
| join 放大 | 金额翻倍 | 基数感知的 join 路径 + fan-out 检测 |
| 时间窗口错 | 同比/环比差一天 | 时间语义显式建模（财年、时区、闭开区间） |
| 值不匹配 | 空结果 | 值索引 + 同义词 + 模糊匹配 + 澄清 |
| 方言错 | 函数不存在 | 方言适配层 + dry-run |
| 权限越界 | 看到了不该看的数据 | 数据库 RLS/CLS 下推 + 只读角色 |
| 幻觉列 | 列名不存在 | 列存在性校验 + 只允许 ontology 内字段 |
| 成本炸 | 全表扫 | EXPLAIN + scan budget + timeout |

### 4.3 分析 / 表格 / 预测：function 层怎么接

#### 4.3.1 原则：算术交给代码，判断交给模型

CodeAct 的结论（动作 = 可执行 Python 比 JSON 工具调用成功率高至多 20%）和 Data Interpreter 的层次图分解都指向同一件事：**让模型规划，让确定性代码执行**。LLM 做算术是不可靠的；但 LLM 决定"先按区域拆，再算同比，再做 Top-N"是可靠的。

因此 function 层应该是**窄而确定的工具**，不是"给模型一个 Python 解释器随便写"：

| 函数 | 输入 | 输出 | 说明 |
|---|---|---|---|
| `aggregate` | 表 + 维度 + 度量 + 过滤 | 表 | 走 SQL，不拉回本地 |
| `pivot` | 表 + 行/列/值 | 表 | 交叉表 |
| `window_compare` | 表 + 时间列 + 粒度 | 表 | 同比/环比/累计 |
| `cohort` | 表 + 用户/时间 + 行为 | 表 | 留存/复购 |
| `attribution` | 表 + 目标 + 维度 | 表 | 贡献度分解（Shapley/加法分解） |
| `detect_anomalies` | 序列 | 标注 | STL + 残差阈值 |
| `forecast` | 序列 +  horizon | 序列 + 区间 | ETS/ARIMA/Prophet，必须回测 |
| `export_xlsx` | 表 + 模板 | 文件 | 保留公式与格式 |

预测的三条纪律：
1. **先跑基线**：naive、季节 naive、ETS；深度模型只有在回测显著优于基线时才用。
2. **必须回测**：滚动 origin，报告 MAPE/sMAPE/MASE 与预测区间覆盖率；没有回测的预测不要给业务看。评测基准用 GIFT-Eval / Monash 这类时序专用集，不要拿通用 LLM 评测代替。
3. **把不确定性说出来**：给区间，不给单点；给"驱动因素"，不给"必然结论"。

#### 4.3.2 输出契约

每次分析返回固定结构，GUI 和下游 agent 都能消费：

```json
{
  "answer_id": "01J...",
  "question": "上月华东 GMV 同比",
  "sql": "SELECT ...",
  "rows": [["华东", 1234567, 0.183]],
  "columns": [{"name":"region","type":"string"}, ...],
  "chart": {"type":"bar","x":"region","y":"gmv_yoy"},
  "narrative": "华东 9 月 GMV 123.5 万元，同比 +18.3%，主要来自……",
  "assumptions": ["GMV 含税不含退款", "华东按 customers.region 归属"],
  "confidence": 0.86,
  "lineage": {"ontology_version":"2.3.0","metrics":["gmv"],"tables":["orders","customers"]},
  "artifacts": [{"path":"/.../answer.parquet","digest":"sha256:...","rows":128}]
}
```

`assumptions` 和 `lineage` 不是可选项。企业客户对"数字对不对"的追问，最终都要落到这两项上；没有它们，Agent 永远只是玩具。

#### 4.3.3 表格/Excel 的两个现实约束

- **不要试图在服务端做完整电子表格引擎**。读：SheetJS / openpyxl；写：模板填充 + 保留公式；复杂计算落 DuckDB。
- **文件即席分析的终点不是一张图，而是"可沉淀的口径"**。这是中国市场的空档（见第 6 节）：用户在 Excel 里算出的临时口径，应该能被提议为 ontology 里的一个新指标或一次修订，走审批流。SmartBI 只做到"模板 → 数据"的反向，Quick BI 的即席分析与指标层割裂，没有人做"文件 → 受治理指标"的正向闭环。
