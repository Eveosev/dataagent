# 执行应用层模块拆分（DA05–DA10）

> 依据：`Pluggable-DataAgent.md`（飞书 r953）。类型系统、错误模型、命名与权限约定沿用 `00-data-layer.md` §0，本文不重复。

## 0. 本层共性

| 项 | 约定 |
|-|-|
| 入口形态 | 全部为**软组件**（skill + 工具），只有执行后端是硬组件 |
| 与数据层关系 | 只消费 `DataRef / SchemaRef / SemanticRef`，不直连源 |
| 与动作面关系 | DA06.6–7 产计划，**执行一律经 DA07.7 网关**，不允许绕过 |
| 中间产物 | DA06 的逻辑计划、DA07 的中间结果是**可复用资产**，须带版本 |

---

## 1. DA05 召回检索

**模块定义**：给定问题，找出该看哪些表、字段、语义、记忆、文档与资产。不判断正确性（DA11），不排序业务优先级。

### 1.1 目录结构

```
packages/capabilities/dataagent-retrieval/
├── mint.toml
├── skills/da05-recall/SKILL.md
├── src/dataagent_retrieval/
│   ├── contracts.py            # Hit{Candidate, score, why}
│   ├── tools/
│   │   ├── catalog.py          # search_tables / search_columns / lookup_values
│   │   ├── semantic.py         # search_entities / metrics / rules / mappings
│   │   ├── memory.py           # search_history / experience / corrections / queries
│   │   ├── doc.py              # search_docs_keyword / search_docs_semantic
│   │   ├── asset.py            # search_code / search_models / search_templates
│   │   ├── rerank.py           # dedupe / rerank
│   │   └── lineage.py          # trace_up / trace_down / trace_semantic
│   └── index/{bm25.py, vector.py, hybrid.py, cache.py}
└── tests/conformance/
```

### 1.2 代码结构规则

1. **候选必须带 `why`**：每个 `Hit` 返回命中理由（命中哪一列、哪个模板、哪条经验），否则无法解释答案来源。
2. 检索与重排分离：`index/` 只负责召回，`rerank` 负责排序；换索引不改重排策略。
3. 混合检索统一走 `hybrid.py`（BM25 + 向量 + 结构化过滤），不允许各工具自选。
4. 记忆检索**必须带作用域与时效**，跨现场不得默认共享。

### 1.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA05.1.1 | 表/数据集召回 | 问题或条件 | `Hit[]{table_ref, score, why}` |
| DA05.1.2 | 字段召回 | 问题 + 表 | `Hit[]{column, score}` |
| DA05.1.3 | 取值召回与反查 | 值片段 | `Hit[]{column, value, 匹配方式}` |
| DA05.2.1 | 实体召回 | 问题 | `Hit[]{entity, version}` |
| DA05.2.2 | 指标召回 | 问题 | `Hit[]{metric, 口径摘要}` |
| DA05.2.3 | 业务规则召回 | 问题 | `Hit[]{rule, 适用范围}` |
| DA05.2.4 | 关系与映射召回 | 实体/字段 | `Hit[]{relation \| mapping}` |
| DA05.3.1 | 历史任务召回 | 当前任务 | `Hit[]{task, 相似理由}` |
| DA05.3.2 | 经验召回 | 当前任务 | `Hit[]{experience, 作用域, 生效时间}` |
| DA05.3.3 | 用户纠正召回 | 当前结论 | `Hit[]{correction, 原值→新值}` |
| DA05.3.4 | 已验证查询召回 | 问题 | `Hit[]{query, 验证状态}` |
| DA05.4.1 | 文档关键词检索 | 关键词 | `Hit[]{doc, anchor}` |
| DA05.4.2 | 文档语义检索 | 查询 | `Hit[]{doc, anchor, 片段}` |
| DA05.5.1 | 分析代码/函数召回 | 意图 | `Hit[]{asset_id, 签名}` |
| DA05.5.2 | 模型召回 | 意图 | `Hit[]{model_id, 指标}` |
| DA05.5.3 | 报表/模板召回 | 意图 | `Hit[]{template_id}` |
| DA05.6.1 | 候选去重 | `Hit[]` | 去重后 `Hit[]` + 合并说明 |
| DA05.6.2 | 相关性重排 | `Hit[]` + 上下文 | 有序 `Hit[]` |
| DA05.7.1 | 上游来源追溯 | 对象 | `Node[]{来源, 深度}` |
| DA05.7.2 | 下游依赖查找 | 对象 | `Node[]{影响对象}` |
| DA05.7.3 | 语义到物理实现追溯 | `SemanticRef` | `[表, 列, 表达式]` |

---

## 2. DA06 语义查询与计算计划

**模块定义**：把问题变成可执行的计算/动作计划。不执行（DA07），不评测（DA11）。

### 2.1 目录结构

```
packages/capabilities/dataagent-planner/
├── src/dataagent_planner/
│   ├── contracts.py            # LogicalPlan / ExecExpr / ActionPlan
│   ├── tools/
│   │   ├── parse.py            # parse_intent / bind / parse_time / detect_ambiguity / ask
│   │   ├── compile.py          # expand_metric / expand_relations
│   │   ├── emit.py             # gen_sql_* / translate / gen_api / gen_expr
│   │   ├── repair.py           # fix_syntax / fix_runtime / fix_logic
│   │   ├── orchestrate.py      # match_target / orchestrate
│   │   └── action.py           # plan_actions / insert_human / plan_branches / draft_*
│   └── dialect/{duckdb.py, postgres.py, mysql.py, hive.py, ql.py}
└── tests/golden/                 # 计划快照回归
```

### 2.2 代码结构规则

1. **计划是数据结构不是字符串**：`LogicalPlan` 必须可序列化、可比对，SQL 只是它的一种渲染。
2. 方言转换集中在 `dialect/`，`emit.py` 不写方言分支。
3. 修正（4.x）只改计划、不重跑；重跑由 DA07 负责，避免隐式副作用。
4. 动作计划（6.x）必须显式标出**人工步骤、等待点、审批点**，缺一不得发布。

### 2.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA06.1.1 | 指标与维度绑定 | 问题 + 语义候选 | `{metric, dims[], 置信}` |
| DA06.1.2 | 时间与过滤解析 | 问题 + 时间口径 | `{range, filters[], 时区}` |
| DA06.1.3 | 计算歧义识别 | 问题 + 语义 | `Ambiguity[]{位置, 影响}` |
| DA06.1.4 | 澄清问题生成 | `Ambiguity[]` | `{问题, 候选选项[]}` |
| DA06.2.1 | 指标计算展开 | `Metric` | 展开后表达式树 |
| DA06.2.2 | 关系与约束展开 | 实体关系 | Join 与约束子句 |
| DA06.3.1 | 单表 SQL 生成 | `LogicalPlan` | SQL + 参数绑定 |
| DA06.3.2 | 多表 SQL 生成 | `LogicalPlan` | SQL + Join 顺序说明 |
| DA06.3.3 | SQL 方言转换 | SQL + 目标方言 | 方言 SQL + 差异说明 |
| DA06.3.4 | API/MCP 调用生成 | `LogicalPlan` | 调用序列 + 参数 |
| DA06.3.5 | 函数调用与表达式生成 | 意图 + 函数目录 | 表达式 AST |
| DA06.4.1 | 语法与参数修正 | 报错 + 计划 | 修正后计划 |
| DA06.4.2 | 执行错误修正 | 运行错误 + 计划 | 修正后计划 + 原因 |
| DA06.4.3 | 计算逻辑修正 | 结果偏差 + 计划 | 修正后计划 + 假设变更 |
| DA06.5.1 | 执行目标匹配 | 子目标 | `{引擎, 后端}` |
| DA06.5.2 | 多步计算依赖编排 | 子计划集 | DAG + 并行分组 |
| DA06.6.1 | 多步动作序列 | 业务目标 + 动作契约 | `ActionPlan{steps[]}` |
| DA06.6.2 | 人工步骤与等待点插入 | `ActionPlan` | 插入后计划（标 `human`） |
| DA06.6.3 | 分支与异常路径 | `ActionPlan` | 分支图 + 兜底路径 |
| DA06.7.1 | 目标转状态机草案 | 目标 | 状态机草案 |
| DA06.7.2 | 审批点建议 | 状态机 + 权属 | `[审批点 + 理由]` |
| DA06.7.3 | 成功判据与回滚草案 | 目标 | `{判据, 回滚步骤}` |

---

## 3. DA07 计算执行

**模块定义**：把计划跑出来，并保证副作用可控、可对账。不做业务判断。

### 3.1 目录结构

```
packages/capabilities/dataagent-executor/
├── src/dataagent_executor/
│   ├── contracts.py            # ExecResult / Receipt / JobRef
│   ├── tools/
│   │   ├── sql.py  code.py  function.py  write.py  expr.py  plan.py
│   │   ├── gateway.py          # 动作网关：分档、幂等、dry-run、后置校验
│   │   ├── compensate.py       # 补偿与对账
│   │   ├── job.py              # 作业化：受理、进度、结果
│   │   └── engine.py           # 自举与一致性验证
│   ├── backends/{duckdb.py, dbapi.py, mcp_sql.py, sandbox.py, local_fn.py, api.py}
│   ├── guard/{tier.py, idempotency.py, precheck.py, postcheck.py}
│   └── engine/{fetch.py, verify.py, degrade.py}
└── tests/{conformance, replay}
```

### 3.2 代码结构规则

1. **唯一写通道**：所有写动作必须经 `gateway.py`；backend 不得暴露写入口（编译期禁止直接 import write backend）。
2. `guard/` 四件事固定顺序：档位判定 → 幂等键 → dry-run → 后置校验。任一失败即中止。
3. 结果一律返回 `ExecResult{rows_ref, stats, receipt}`；不允许只返回 rows。
4. 一致性验证（10.x）产出的差异必须**分类**（版本差异 / 语义差异 / 数据差异），不允许只报 diff。

### 3.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA07.1.1 | 企业 SQL MCP/API 执行适配 | SQL + 连接引用 | `ExecResult` |
| DA07.1.2 | 数据库驱动执行适配 | SQL + 连接引用 | `ExecResult` |
| DA07.1.3 | 本地 DuckDB 执行适配 | SQL + 数据引用 | `ExecResult` |
| DA07.2.1 | 本地 Python 执行 | 代码 + 输入引用 | `{stdout, outputs[], exit}` |
| DA07.2.2 | 远程沙盒代码执行 | 代码 + 资源限制 | `{stdout, outputs[], exit}` |
| DA07.3.1 | 本地函数调用 | 函数名 + 参数 | 返回值 |
| DA07.3.2 | 远程领域函数调用 | 函数引用 + 参数 | 返回值 + 版本 |
| DA07.3.3 | 业务 API/MCP 调用 | 动作 + 参数 | 响应 + 请求回执 |
| DA07.4.1 | 本地文件/数据集变更应用 | 变更意图 | 写入回执 + 前后快照 |
| DA07.4.2 | 企业 API/MCP 写回 | 变更意图 | 写入回执 |
| DA07.4.3 | 写入回执与状态核对 | 回执 + 目标状态 | `{一致 \| 不一致 + 差异}` |
| DA07.5.1 | 标量表达式计算 | 表达式 + 变量 | 值 \| `UNKNOWN` |
| DA07.5.2 | 表数据表达式计算 | 表达式 + 行集 | 列结果 + 逐行判定 |
| DA07.6.1 | 多步计算执行 | DAG | 中间结果集 + 最终结果 |
| DA07.6.2 | 中间结果衔接 | 上游结果 + 下游计划 | 绑定后的执行结果 |
| DA07.7.1 | 分档执行（A0/A1/A2） | 已判档动作 | 执行结果 + 档位回执 |
| DA07.7.2 | 幂等键与去重 | 动作 + 键 | 首次执行 / 命中返回原结果 |
| DA07.7.3 | dry-run 预演 | 动作 + 参数 | 将发生什么 + 影响面 |
| DA07.7.4 | 后置状态校验 | 回执 + 期望状态 | `{通过 \| 偏差 + 明细}` |
| DA07.8.1 | 反向/补偿动作 | 已执行动作 | 补偿结果 |
| DA07.8.2 | 副作用未知的对账 | 未知动作 | 实际状态 + 结论（**不重放**） |
| DA07.8.3 | 部分失败逐项说明 | 批量结果 | 每项状态 + 失败原因 |
| DA07.9.1 | 受理与作业号 | 长任务请求 | `JobRef` |
| DA07.9.2 | 进度与部分结果 | `JobRef` | `{进度, 部分结果}` |
| DA07.9.3 | 未知状态不重放 | `JobRef` | 查询 + 对账结论 |
| DA07.10.1 | 引擎获取与版本对齐 | 引擎坐标 | `{引擎, 版本, 校验和}` |
| DA07.10.2 | 双引擎一致性校验 | 同输入 + 两引擎 | 差异 + 分类 |
| DA07.10.3 | 降级留证 | 降级原因 | `{范围, 已知差异, 证据}` |

---

## 4. DA08 分析

**模块定义**：在已取到的数据上做描述、统计、关系分析，并解释结果。不做预测（DA09），不评价方法好坏（DA11）。

### 4.1 目录结构

```
packages/capabilities/dataagent-analysis/
├── src/dataagent_analysis/
│   ├── tools/{plan.py, describe.py, stat.py, relate.py, explain.py, program.py}
│   ├── methods/{yoy.py, contribution.py, funnel.py, cohort.py, interval.py, tests.py, regression.py}
│   ├── explain/{trace.py, hypothesis.py}
│   └── codegen/{python.py, formula.py, repair.py}
└── tests/golden/
```

### 4.2 代码结构规则

1. 每个方法一个文件，签名统一 `run(df, params) -> {value, ci?, assumptions}`，**必须声明前提假设**。
2. 解释（5.x）只能引用已产出的中间结果，不允许在解释阶段新取数。
3. 代码生成（6.x）产出可执行程序 + 依赖锁，修复记录保留 diff。

### 4.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA08.1.1 | 问题分解 | 问题 | 子问题 DAG |
| DA08.1.2 | 分析方法选择 | 子问题 + 数据画像 | `{方法, 理由, 前提}` |
| DA08.2.1 | 同比/环比分析 | 序列 + 口径 | `{变化率, 贡献分解}` |
| DA08.2.2 | 贡献度分析 | 维度 + 指标 | `{每维贡献, 占比}` |
| DA08.2.3 | 漏斗分析 | 事件序列 | `{各步转化, 流失}` |
| DA08.2.4 | 留存/Cohort 分析 | 用户 × 时间 | 留存矩阵 |
| DA08.3.1 | 分布与区间估计 | 样本 | `{统计量, CI, 假设}` |
| DA08.3.2 | 假设检验 | 两组样本 | `{统计量, p, 结论, 前提}` |
| DA08.3.3 | 回归分析 | 变量集 | `{系数, 拟合, 诊断}` |
| DA08.4.1 | 关系路径分析 | 图 + 起止 | 路径 + 权重 |
| DA08.4.2 | 群组/聚集分析 | 实体特征 | 簇 + 解释 |
| DA08.4.3 | 异常关系识别 | 关系图 | 异常边 + 依据 |
| DA08.5.1 | 查询答案解释 | 结果 + 计划 | 自然语言解释 + 溯源 |
| DA08.5.2 | 变化原因假设生成 | 变化 + 证据 | `[假设 + 支持证据]` |
| DA08.6.1 | Python 分析代码生成 | 分析目标 | 代码 + 依赖锁 |
| DA08.6.2 | 表格公式生成 | 目标计算 | 公式 + 目标区域 |
| DA08.6.3 | 执行反馈驱动的程序修复 | 报错/偏差 + 代码 | 修复后代码 + diff |

---

## 5. DA09 预测、仿真与优化

**模块定义**：在历史与假设上外推、寻优。不做因果断言（需 DA08 证据），不改真实系统。

### 5.1 目录结构

```
packages/capabilities/dataagent-forecast/
├── src/dataagent_forecast/
│   ├── tools/{predict.py, simulate.py, solve.py, compare.py}
│   ├── models/{ts.py, exogenous.py, probabilistic.py}
│   ├── solvers/{lp.py, milp.py, schedule.py}
│   └── eval/{backtest.py, calibration.py}
└── tests/golden/
```

### 5.2 代码结构规则

1. 预测必须返回**区间与前提**，只给点值视为未完成。
2. 求解器（3.x）不可行时必须返回**不可行原因与冲突约束**，不允许只报 `infeasible`。
3. 方案比较（4.x）必须给权衡维度，不允许单一总分。

### 5.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA09.1.1 | 时间序列预测 | 历史序列 + 周期 | `{点预测, 区间, 前提}` |
| DA09.1.2 | 带外生变量预测 | 序列 + 外生变量 | `{预测, 区间, 变量影响}` |
| DA09.1.3 | 概率预测 | 序列 + 分位 | 分位数曲线 |
| DA09.2.1 | 参数敏感性分析 | 模型 + 参数范围 | `{参数→结果} 敏感度` |
| DA09.2.2 | 业务情景模拟 | 情景假设 | 情景结果 + 假设清单 |
| DA09.3.1 | 线性/整数规划求解 | 目标 + 约束 | `{解, 目标值}` \| 不可行原因 |
| DA09.3.2 | 排程与资源约束求解 | 任务 + 资源 | 排程表 + 冲突 |
| DA09.4.1 | 目标指标比较 | 多方案结果 | 指标对比表 |
| DA09.4.2 | 多目标权衡分析 | 多目标值 | Pareto 集 + 权衡说明 |

---

## 6. DA10 表格、可视化与交互

**模块定义**：把结果变成人能用的东西，并接收人的即时修正。不做计算逻辑（DA06/07）。

### 6.1 目录结构

```
packages/capabilities/dataagent-present/
├── src/dataagent_present/
│   ├── tools/{sheet.py, chart.py, report.py, revise.py}
│   ├── render/{xlsx.py, chart_static.py, chart_interactive.py, docx.py, html.py}
│   └── revise/{intent.py, scope.py, state.py, recompute.py}
└── tests/golden/
```

### 6.2 代码结构规则

1. 产物一律落成**文件引用 + 生成参数**，可重放（同参数同产物）。
2. 修正（4.x）不得静默改结果：必须给出「改了什么、影响哪些下游」，并触发重算。
3. 报告必须内嵌数据与语义版本，否则三个月后无法复现。

### 6.3 原子能力输入输出

| 编号 | 原子能力 | 输入 | 输出 |
|-|-|-|-|
| DA10.1.1 | 结果工作簿生成 | `DataRef` + 版式 | `.xlsx` 引用 + 参数 |
| DA10.1.2 | 透视计算 | `DataRef` + 行列度量 | 透视表 + 口径 |
| DA10.1.3 | 表格公式计算 | 工作簿 + 公式 | 计算结果 + 重算范围 |
| DA10.2.1 | 静态图表生成 | `DataRef` + 图表类型 | 图片引用 + 参数 |
| DA10.2.2 | 交互图表生成 | `DataRef` + 交互配置 | HTML/组件引用 |
| DA10.3.1 | 文档报告生成 | 结论 + 图表 + 版本 | 文档引用 |
| DA10.3.2 | Dashboard 生成 | 指标 + 图表集 | Dashboard 引用 |
| DA10.3.3 | 报告格式导出 | 报告 + 目标格式 | 导出文件引用 |
| DA10.4.1 | 纠正意图识别 | 用户话语 + 当前结果 | `{纠正类型, 目标}` |
| DA10.4.2 | 修正对象与范围定位 | 纠正意图 + 任务状态 | `{对象, 范围, 影响}` |
| DA10.4.3 | 当前任务状态更新 | 修正 | 新任务状态 + 变更记录 |
| DA10.4.4 | 修正后续算与刷新 | 新状态 | 重算结果 + 刷新范围 |
