---
version: v0.3.8
date: 2026-11-05
status: S0 实施中
kernel: agent-kernel@f0fa521
basis: 02-application-layer.md；05-contracts.md；06-data-layer-build-plan.md
changes-from-v0.1: |
  事实修正（可行性评审 2026-11-04 与实测）：
  - FDE 能力组为 16 项（非 19 项）；
  - FieldValue.status 取值为 extracted/missing/conflict/low_confidence，没有 unknown（05 §3.4）；
    §5.1 相应改为：missing 与 conflict 参与运算得 unknown，low_confidence 使用其值并给 warning；
  - ExecutableSpec / EngineBinding 已迁入 core.semantics（0.1.x）；Assessment.evidence、
    ComputedResult.sql_digest / engine_binding 为 0.1.x 新增字段（只增不改）。
  v0.3（Tester r19 修复轮）：
  - P2 定案：S0 只支持 mint-core 路径 + 运行时完整复检，不宣称内核豁免（§2）；
  - 共享运行时已存在并由数据层依赖（W1a/W1b 完成，§2）；
  - §1 的“按需 90 / S1 7”以 Catalog 全量 93/4 为分母口径：阶段 2 的 90 项是
    Catalog 中除 S0 13 项、FDE 16 项与 S1 4 项之外的按需项（DA05.8、DA07.4 实为 4 项），
    逐项映射在阶段 2 开工前再核；
  - DA06.3.5 增加 rule.combination 一致性校验；DA06.3.1 绑定口径后校验度量列、
    聚合与固定过滤；DA07.5.x / DA07.1.3 执行前比对 EngineBinding；
    inference_request 先过 EgressDecision（S0 默认 warn）。
  v0.3.1（Tester r20 修复轮）：
  - W0 六项接缝规格与两族完整样例已冻结为独立文档：
    w0-seam-specifications.md（版本化 codec 与 name↔field_id 字段身份、规则执行顺序与
    三值真值表、结构化单表计划 Schema、basis_refs→EvidenceRef 解析路径、模型可见输出
    边界、P2 执行点与 Mint 宿主 env 注入机制）；
  - DA06.3.1 口径校验增强：绑定维度/grain 与固定过滤的算子/常量；
  - EgressDecision allow 路径可用（destination 取决策自身或调用方声明）；
  - 数据层 define_metric_formula 输出 field_id 并携带过滤 referenced_fields。
  v0.3.2（Tester r22 修复轮）：
  - DA06.3.1 口径校验补全（B1）：绑定时间窗必须实际约束区间的起止值（时间列仅
    IS NOT NULL 或换成 2020 年份不再通过）；固定过滤必须以无条件合取项出现
    （OR 中性化 approved = true OR approved = false、NOT 取反不再满足绑定）；
    带 DISTINCT 的聚合不再视作绑定的聚合（SUM(DISTINCT) 拒绝）；
  - 应用 bundle 三包 vendoring 重同步、数据层审计 manifest 按当前树重算
    （205 项，B2/B3）。
  v0.3.3（Tester r24 修复轮）：
  - DA06.3.1 口径绑定改为作用域感知（B1）：只有产出结果的 SELECT（及其读取的
    CTE/派生表链）的 WHERE 合取项、顶层投影聚合与 GROUP BY 才承载口径——
    未被读取的 CTE、EXISTS/标量子查询里的谓词不绑定任何固定过滤或时间窗；
    标量子查询里的聚合或仅按维度分组的子查询不满足度量聚合与 grain 绑定；
    窗口聚合（`sum(x) OVER ()`）不视作绑定的分组聚合；
  - 行数保持性：绑定表（与每个 CTE）在 FROM 中只允许读取一次——自连接
    （含 `JOIN ... ON true`、CTE 自连接）放大行数，直接拒绝；
  - 回归：tests/test_r24_caliber_scope_fixes.py（12 测试）；合法的
    CTE 链/派生表形状仍通过。
  v0.3.4（Tester r25 修复轮）：
  - DA06.3.1 口径绑定改为聚合形状感知（B1）：聚合参数必须是裸度量列
    （`sum(amount * 2)`、`sum(amount + 50)`、`sum(CASE ...)` 拒绝）；带 `FILTER`
    子句的聚合改变聚合行集，拒绝；投影不得在聚合外再做变换（`sum(amount) * 2`
    拒绝；值保持包装 `CAST`/`TRY_CAST`/括号除外）；读取 CTE/派生表已聚合的列
    必须以裸列投影（外层 `total * 2`、`coalesce(total, 0)` 拒绝）；
  - 回归：tests/test_r25_aggregate_shape_fixes.py（13 测试）；合法形状
    （精确聚合、CAST 包装、CTE 裸列）仍通过并交付绑定合计。
  v0.3.5（Tester r26 修复轮）：
  - DA06.3.1 口径绑定补五类走私（B1）：HAVING 拒绝（未声明的分组过滤，
    即使聚合文本正确）；LIMIT/OFFSET 拒绝（绕过执行侧行数预算）；
    ROLLUP/CUBE/GROUPING SETS 拒绝（小计/合计行改变 grain）；绑定时间字段与
    固定过滤列上不得有额外谓词（矛盾窗口/`approved = true AND approved = false`
    中和口径）；CTE/派生表列血缘跟踪——`amount * 2 AS amount` 使外层聚合视为
    变换聚合、派生过滤/时间列上的谓词不绑定（`SELECT *` 原样透传可用，
    带 EXCEPT/REPLACE/RENAME 拒绝）；
  - 误拒修复：聚合参数内值保持 `CAST` 通过（`sum(CAST(amount AS DOUBLE))`）；
    `BETWEEN` 等价展开接受（纯日期粒度下 `<= <to-1天>` 等价排他端点 `< to`）；
  - 判定词表定案为 core `Verdict`（pass/fail/unknown/not_applicable），
    业务别名 satisfied/violated 由消费方映射：05 §3.3、W0 §2.3、README 同步；
  - 新增 tests/test_r26_caliber_shapes.py（14 测试）与
    tests/test_bundle_sync.py（3 测试：bundle↔source 零漂移 + 0 pyc 门禁）；
    应用 bundle 重同步。
  v0.3.6（Tester r27 修复轮）：
  - DA06.3.1 口径绑定补三类走私（B1）：`QUALIFY` 拒绝（含 CTE/派生表内层——
    与 HAVING/LIMIT 同类的分组后行过滤）；聚合后 `WHERE` 拒绝（对 CTE/派生表
    已聚合列的过滤是变相 HAVING）；WHERE 合取项闭环——只有绑定的固定过滤与
    时间窗端点可以选择行：非绑定列上的额外过滤（维度 `region = 'north'`、
    度量 `amount > 150`、`IN` 列表，含 CTE 内层）、绑定列上无法与绑定算子/常量
    核对的形式（`IN`/`LIKE`/`IS NULL`）与无列常量合取项（`1 = 0`，等价
    LIMIT 0）均拒绝；
  - 回归：tests/test_r27_caliber_where_fixes.py（13 测试）；合法形状
    （精确聚合、`SELECT *` CTE 透传、仅绑定过滤的 CTE 链、聚合 CTE 裸列读取）
    仍通过并交付绑定合计；应用 bundle 重同步。
  v0.3.7（Tester r29 修复轮）：
  - DA06.3.1 口径绑定补 FROM 形状走私（B1/B2）：一切 JOIN 拒绝——ON 合取项是
    变相 WHERE（`JOIN (SELECT 'north' AS keep) x ON t.region = x.keep`、
    `ON a.total > y.threshold` 聚合后过滤、`ON t.approved = false` 矛盾谓词、
    `ON false` 常量、`ON t.amount > (SELECT avg(amount) FROM <bound>)` 二次
    读取、SEMI JOIN、`USING`/`NATURAL`、逗号交叉连接的行数放大），收集器
    仍统计 JOIN 源以保留 read-once 诊断；行采样拒绝——`FROM t TABLESAMPLE`
    （含 CTE/派生表内层）与 `USING SAMPLE`（select 级）在绑定聚合前丢行；
    推理请求 constraints 同步补“无 JOIN / 无行采样”约束；
  - 回归：tests/test_r29_join_tablesample_fixes.py（16 测试）；合法形状
    （精确聚合、`SELECT *` CTE 透传、仅绑定过滤的 CTE 链）仍通过并交付绑定
    合计；应用 bundle 重同步。`GROUP BY ALL` 维持保守拒绝（本版约束：不支持）。
  v0.3.8（Tester r32 修复轮）：
  - DA06.3.1 时间窗端点定死（B1）：绑定窗口为半开区间 `>= from AND < to`，
    每个端点只接受唯一算子/值对——起点 `>= from`（纯日期粒度等价
    `> <from-1天>`）、终点 `< to`（纯日期粒度等价 `<= <to-1天>`）；
    `> from`（丢掉含端起行）与 `<= to`（保留排端行）不再承载
    `metric_version`；`BETWEEN a AND b` 展开为 `>= a AND <= b`，故仅当
    `b = <to-1天>` 时等价——`BETWEEN <from> AND <to>` 拒绝；
  - 推理请求 time_semantics 与代码对齐为 `'from' inclusive, 'to' exclusive
    unless stated`；r22 产品测试的 BETWEEN 合法对照更新为
    `BETWEEN '2026-01-01' AND '2026-01-31'`；
  - 回归：tests/test_r32_time_boundary_fixes.py（7 测试，边界行两侧各一：
    01-01 在窗内、02-01 在窗外，绑定合计 340，走私形状交付 300/840/840）；
    等价窗口（半开、`> from-1天 AND <= to-1天`、`BETWEEN ... AND <to-1天>`）
    仍通过并交付绑定合计；应用 bundle 重同步、dist 制品重建。
---

# 执行应用层能力建设方案

## 1. 范围

| 项 | 内容 |
|-|-|
| 模块 | DA05 召回检索、DA06 语义查询与计算计划、DA07 计算执行、DA08 分析、DA09 预测仿真与优化、DA10 表格可视化与交互 |
| 原子 | 非 FDE 110 项：S0 13 项（阶段 1）；按需 90 项（阶段 2）；S1 项（DA05.8、DA07.4，阶段 3；Catalog 实数 4 项，v0.3 起以 Catalog 93/4 口径核对） |
| 不含 | FDE 能力组 DA06.6、DA06.7、DA07.7、DA07.8、DA07.9（16 项） |
| 包 | `packages/capabilities/dataagent-application/`，Mint `kind = "bundle"` |
| 运行路径与 LLM | 同 [06](06-data-layer-build-plan.md) §1：Python 核心 + MCP 入口；LLM 在 Agent 侧，按两段式调用 |

S0 原子：

| 族 | 原子 | operation |
|-|-|-|
| 骨干 | DA06.3.5 函数调用与表达式生成 | `generate_function_expressions` |
| 骨干 | DA07.5.1 标量表达式计算 | `evaluate_scalar_expression` |
| 骨干 | DA07.5.2 表数据表达式计算 | `evaluate_table_expression` |
| 骨干 | DA07.10.1 引擎获取与版本对齐 | `acquire_and_align_engine` |
| 骨干 | DA10.3.1 文档报告生成 | `compose_document_report` |
| 骨干 | DA10.3.3 报告格式导出 | `export_report_format` |
| 计算族 | DA06.1.1 指标与维度绑定 | `bind_metrics_and_dimensions` |
| 计算族 | DA06.1.2 时间与过滤解析 | `parse_time_and_filters` |
| 计算族 | DA06.1.3 计算歧义识别 | `identify_calculation_ambiguities` |
| 计算族 | DA06.1.4 澄清问题生成 | `generate_clarification_questions` |
| 计算族 | DA06.3.1 单表 SQL 生成 | `generate_single_table_sql` |
| 计算族 | DA07.1.3 本地 DuckDB 执行适配 | `execute_duckdb_sql` |
| 计算族 | DA10.1.1 结果工作簿生成 | `build_result_workbook` |

## 2. 前置条件

与评测治理层（[08](08-governance-layer-build-plan.md)）共用：

| 项 | 内容 | 状态 |
|-|-|-|
| 共享运行时 | `packages/capabilities/dataagent-runtime/`：`invoke`、`CallContext` 校验、错误映射、注册表与 Catalog 校验、存储端口与 SQLite/内容寻址适配器、表编解码端口（`ports/tabular.py`）、`InferencePort`、DA12.1 enforcement（access recheck / egress check）、MCP/CLI 入口骨架 | 已落地（W1a）；`dataagent-data` 已切换为依赖它并删除自带副本（W1b，数据层门禁不变） |
| 共享 `data_root` | 三个 bundle 指向同一 `data_root`，`TableRef`、`DocumentRef` 等按内容 digest 从同一 ContentStore 读取；版本库与轨迹库共用，并发由 `BEGIN IMMEDIATE` 保证 | 随共享运行时 |
| P2 | 采用 C：经内核时以 guard 为准；无内核路径（mint-core）由 DA12.1 判定，运行时复检 `authorization_ref` | 已定案：S0 只支持 mint-core 路径加运行时完整复检，不宣称内核豁免；`kernel_session_id` 单独出现不构成豁免，须可信宿主声明 `kernel_guard_declared`（评审 §7.3） |
| 契约字段 | 本层 S0 产出、且被其他层消费的类型先迁入 core（§4.2） | 阶段 1 开工前 |

## 3. 包结构

```text
dataagent-application/
  pyproject.toml  uv.lock  mint.toml  .mcp.json  README.md  packaging/source-ref.toml
  skills/dataagent-compute-plan/SKILL.md      # 需求绑定、澄清、SQL 生成两段式
  skills/dataagent-rule-execute/SKILL.md      # 规则 → 表达式 → 求值
  src/dataagent_application/
    contracts/       # 本层特有类型：RequirementSpec、Ambiguity、LogicalPlan、EngineBinding、ReportDraft 等
    retrieval/       # DA05
    planning/        # DA06
    execution/       # DA07
    analysis/        # DA08
    prediction/      # DA09
    presentation/    # DA10
    ports/           # retrieval、execution、scientific、rendering、policy、validation、task_changes
    adapters/        # duckdb、expression、sqlglot、openpyxl、docx、index(sqlite_fts)、scientific
    interfaces/      # mcp_server.py、cli.py（基于 dataagent-runtime）
  tests/{contracts,planning,execution,presentation,retrieval,analysis,prediction,interfaces,scenarios}/
  fixtures/
```

- 组文件与 operation 以[总 Catalog](catalog/atomic-capability-catalog.json) 的 `source_file`、`operation` 为准；注册表启动时校验，规则同 06 §4.1。
- 依赖：`dataagent-contracts`、`dataagent-runtime`；不导入 `dataagent_data`、`dataagent_governance`。

## 4. 调用约定与跨层

### 4.1 调用

- `invoke(operation, input, CallContext) -> CapabilityResult[T]`，MCP 工具名 = operation，注解按操作显式声明（同数据层）。
- 两段式推理：DA06.1.1–1.4、DA06.3.1、DA06.3.5。第一次调用返回 `needs_input` 与 `inference_request`；带 `proposal` 的第二次调用由工具做确定性校验：
  - DA06.1.x：绑定的指标、维度必须存在于输入的 `MetricDefinition` 与 `TableRef` schema；时间与过滤值须能解析；
  - DA06.3.1：SQL 经 sqlglot 解析，见 §5.2；
  - DA06.3.5：表达式 AST 经类型检查，见 §5.1。
- `inference_request` 携带原文或表样本前，先校验 `EgressDecision`（DA12.1.4，由 `InferencePort` 统一执行，见 08 §4.3）；`deny` 时不附内容，返回 `needs_input`。

### 4.2 类型迁移（`dataagent-contracts` 0.1.x，只增不改）

| 类型 | 原位置 | 第二消费方 | 处理 |
|-|-|-|-|
| `ExecutableSpec`（含表达式 AST、SQL） | 本层 | DA11.2.3 结果粒度与合并检查；DA11.4.5 引擎一致性回归 | 迁入 `core.semantics` |
| `EngineBinding` | 本层 | DA11.4.5；DA12.6 重现条件 | 迁入 `core.semantics` |
| `ReportDraft` | 本层 | — | 留本层；对外以 `AssetRef` 传递 |
| `RequirementSpec`、`Ambiguity`、`LogicalPlan` | 本层 | — | 留本层 |

迁移按 05 §2.3 执行，字段同步回写 05 §3.3 与 §3.6。

### 4.3 消费的跨层类型

| 类型 | 产出方 | 本层用途 |
|-|-|-|
| `TableRef`、`SchemaRef`、`DataBatchRef` | DA01、DA02 | DuckDB 输入、需求绑定 |
| `MetricDefinition` | DA03.4.1 | 需求绑定、SQL 生成 |
| `RuleDefinition`、`Assessment` | DA03.4.3、DA03.15、DA03.16 | 表达式生成与求值 |
| `ExtractedRecordRef`、`FieldValue` | DA02.12 | 表达式求值输入 |
| `AcceptanceReport` | DA11.5.5 | 报告附验收结论 |
| `AccessDecision`、`EgressDecision` | DA12.1 | 读取与模型外发前复检 |

## 5. S0 实现

### 5.1 表达式（DA06.3.5、DA07.5.1、DA07.5.2）

| 项 | 规则 |
|-|-|
| 表示 | `ExecutableSpec.backend_kind = "expression"`，`expression_or_call` 为 JSON AST；算子封闭集合：比较、算术、逻辑、`in`、`between`、`is_missing`、日期差、字符串匹配 |
| 来源 | `RuleDefinition` 的条件逐项编译为 AST；每个节点保留 `RuleCondition` 来源与 `SourceAnchor` |
| 语义 | 三值逻辑：`true / false / unknown`；`missing` 与 `conflict` 状态的 `FieldValue` 参与运算得 `unknown`，不折算为 `false`；`low_confidence` 使用其值并附 warning；类型不符报 issue |
| 求值 | 解释器实现，不用 `eval`；标量对单条 `ExtractedRecordRef`，表数据对 `TableRef` 逐行 |
| 输出 | `Assessment<V>`，`evidence` 列出参与运算的字段值与锚点；表数据输出另存 `ComputedResult` |
| 引擎版本 | 解释器版本写入 `implementation_ref` 与 `EngineBinding` |

### 5.2 SQL（DA06.3.1、DA07.1.3）

| 项 | 规则 |
|-|-|
| 生成 | 两段式；工具提供表 schema、`MetricDefinition`、`RequirementSpec`；Agent 提交 SQL |
| 校验 | sqlglot 解析：只允许单条 `SELECT`（含 CTE）；引用表 ⊆ 输入绑定的 `TableRef`；禁止函数黑名单（文件读写、扩展加载、`read_*`）；绑定 `RequirementSpec` 后口径逐项对齐：度量列/聚合（DISTINCT、窗口聚合 `sum(x) OVER ()` 视为不同聚合，聚合必须在顶层投影）、固定过滤的算子/常量且必须为无条件合取项（OR 替代项/NOT 取反不绑定）、绑定时间窗的半开区间端点定死：起点仅 `>= from`（纯日期粒度等价 `> <from-1天>`）、终点仅 `< to`（纯日期粒度等价 `<= <to-1天>`），`> from`/`<= to` 与更窄的端点变体不承载口径（`BETWEEN` 展开为 `>= a AND <= b`，故仅 `b = <to-1天>` 时等价）、维度/grain（v0.3.2）；口径绑定作用域感知：只有产出结果的 SELECT 及其读取的 CTE/派生表链承载过滤/时间窗/聚合，未被读取的 CTE 与 EXISTS/标量子查询不绑定；绑定表与每个 CTE 仅可读取一次，自连接拒绝（v0.3.3）；口径绑定聚合形状感知：聚合参数必须是裸度量列、不得带 `FILTER`，投影不得在聚合外变换（值保持 `CAST` 除外，聚合参数内同理），读取已聚合的 CTE 列必须以裸列投影（v0.3.4）；口径绑定形状与血缘收口：HAVING、LIMIT/OFFSET、ROLLUP/CUBE/GROUPING SETS 拒绝，绑定时间字段与固定过滤列上不得有额外谓词，CTE/派生表列必须原样透传才承载口径（`amount * 2 AS amount` 不绑定；v0.3.5）；口径绑定 WHERE 合取项闭环：`QUALIFY` 拒绝（含 CTE/派生表内层），聚合后 `WHERE`（对已聚合 CTE/派生表列的过滤，变相 HAVING）拒绝，WHERE 合取项必须是绑定时间/过滤列上可与绑定算子/常量核对的谓词——非绑定列额外过滤（维度/度量/`IN`）、绑定列上不可核对形式与无列常量合取项（`1 = 0`）均拒绝（v0.3.6）；口径绑定 JOIN/采样闭环：一切 JOIN（inner/outer/semi、ON/USING/NATURAL、逗号交叉连接）拒绝——ON 合取项是变相 WHERE、等值连接右侧行数放大不受控、ON 子查询绕过 read-once 守卫，`TABLESAMPLE`（含 CTE/派生表内层）与 `USING SAMPLE` 在绑定聚合前丢行（v0.3.7）；口径绑定时间窗端点定死：每个端点只接受唯一算子/值对（`>= from` / `> <from-1天>` 与 `< to` / `<= <to-1天>`），`> from`（丢含端起行）与 `<= to`（保排端行）不再通过——边界行在场时它们交付不同合计却携带同一 `metric_version`（v0.3.8） |
| 执行 | DuckDB 进程内连接；`TableRef` 从 ContentStore 载入为临时表；`SET enable_external_access = false`、`SET lock_configuration = true`；超时与行数上限来自 `Budget` |
| 输出 | `ComputedResult`：值、口径（`MetricDefinition` 版本）、粒度、过滤、输入 `TableRef` 版本、SQL digest、`EngineBinding`；截断时 `Completeness` 标注 |

### 5.3 需求绑定与澄清（DA06.1.1–1.4）

- 输出 `RequirementSpec`：`metrics[]`、`dimensions[]`、`time`、`filters`、`grain`、`assumptions[]`、`unresolved[]`。
- DA06.1.3 识别影响结果的歧义（多口径、时间边界、币种与单位、去重粒度），每项给 `result_impact` 与 `blocking`。
- DA06.1.4 对 `blocking` 歧义返回 `needs_input`，`Issue.alternatives` 列候选及依据，允许自由回答；非阻塞歧义写入 `assumptions[]` 并在报告中列出。

### 5.4 引擎（DA07.10.1）

- S0 引擎为 DuckDB 与表达式解释器。记录坐标（包名）、版本、wheel 哈希（取自 `uv.lock`），运行时比对实际已装版本；不一致返回 `failed`，code `da07.engine_version_mismatch`。
- 不联网下载；离线包须在锁文件中有校验和。

### 5.5 交付（DA10.1.1、DA10.3.1、DA10.3.3）

| 原子 | 实现 |
|-|-|
| DA10.1.1 | openpyxl 生成工作簿：结果表、口径与来源表（`MetricDefinition` 版本、输入版本、SQL digest）、未覆盖与假设表；只写值，不写需重算的公式 |
| DA10.3.1 | `ReportDraft`：结论、逐条依据（`EvidenceRef` → 原文锚点）、不可判定项与未覆盖范围、`AcceptanceReport` 摘要（若有）；内容为 Markdown + 结构化节 |
| DA10.3.3 | 导出 `md`、`html`（标准库）、`docx`（python-docx，可选依赖组）；导出产物内容寻址保存并返回 `AssetRef`；导出不等于发布 |

## 6. 阶段 2：按需能力

按组并行，组间只经类型与端口交互。

| 流 | 能力组 | 实现要点 | 依赖 |
|-|-|-|-|
| 检索 | DA05.1–05.7、DA05.9（25） | 本地索引端口：SQLite FTS5 全文；向量检索为可选适配器；`SearchHit` 保留索引时点、匹配依据与覆盖；DA05.9 判定必要依赖闭包与停止条件 | DA05.3 需数据层 DA04.3 作用域记忆；DA05.7 需 core `LineageEdge` 字段（05 §3.7 预留） |
| 计划 | DA06.2、DA06.3.2–3.4、DA06.4、DA06.5、DA06.8（17） | 多表 SQL 与方言转换基于 sqlglot；DA06.4 修订保留原业务目标与差异；DA06.8 经端口调用外部语义层编译认证指标，不可用时按 DA06.8.3 降级标注 | DA06.8 外部语义层适配器（按部署选型） |
| 执行 | DA07.1.1–1.2、DA07.2、DA07.3、DA07.6、DA07.10.2–10.3（11） | 企业 SQL 经 MCP/API 或驱动只读执行；DA07.2 代码执行须有隔离环境（只读挂载、无网络），无隔离时返回 `dependency_unavailable`，不回退本地执行；DA07.6 只执行固定 DAG | 隔离环境（容器或远程沙盒） |
| 分析 | DA08（18） | 描述分析基于 DuckDB；统计用 scipy、statsmodels；DA08.6 程序草案只生成，执行走 DA07.2 | DA07.2 |
| 预测 | DA09（9） | statsmodels 时序；求解用 HiGHS（经 scipy）；`OptimizationResult` 区分 optimal / feasible / infeasible / unknown | — |
| 展示 | DA10.1.2–1.4、DA10.2、DA10.3.2、DA10.4（10） | 图表输出 Vega-Lite `ChartSpec`，渲染为可选依赖；DA10.1.4 既有工作簿受限编辑保护未改区域；DA10.4 纠正提交给所属模块，不自建语义 | DA10.4 需 DA12.5 变更控制与 DA03/DA04 变更端口 |

## 7. 阶段 3：S1 能力

| 能力组 | 前提 |
|-|-|
| DA05.8 组件与 Skill/Preset 检索（4） | `ComponentMeta` 已在 core；与 DA18.7 同期 |
| DA07.4 变更写入（3） | 写入统一经 DA07.7 动作网关（FDE）；P1 定案后实施 |

## 8. 第三方依赖

| 用途 | 依赖 | 许可 |
|-|-|-|
| SQL 执行 | duckdb | MIT |
| SQL 解析与方言 | sqlglot | MIT |
| 工作簿 | openpyxl | MIT |
| docx 导出（可选） | python-docx | MIT |
| 统计（阶段 2） | scipy、statsmodels | BSD-3-Clause |
| 图表渲染（阶段 2，可选） | vl-convert-python | BSD-3-Clause |

## 9. Mint 打包

| 项 | 内容 |
|-|-|
| kind | `bundle`，名称 `dataagent/application-layer` |
| `.mcp.json` | 同数据层：`uv run --frozen --project $PKG python -m dataagent_application.interfaces.mcp_server` |
| `[capabilities]` | `exec = ["uv"]`、`fs.read = ["*"]`、`fs.write = [".dataagent/**"]`；无网络 |
| Skills | `dataagent-compute-plan`、`dataagent-rule-execute` |
| 组合 | S0 端到端由 Preset `dataagent-s0` 组合数据层、应用层、评测治理层三个 bundle（见 08 §8） |

## 10. 分步实施

| 步 | 内容 | 产出 | 可并行 |
|-|-|-|-|
| 0 | agent-kernel 最新检查并记录 HEAD；共享运行时抽出；P2 定案 | `dataagent-runtime` | 与 08 步 0 共同完成 |
| 1 | `ExecutableSpec`、`EngineBinding` 迁入 core；本层特有类型；包骨架与注册表 | 空服务，`tools/list` = 0 | — |
| 2 | 表达式：DA06.3.5、DA07.5.1、DA07.5.2、DA07.10.1 | 判定族执行链 | 与步 3 并行 |
| 3 | 计算：DA06.1.1–1.4、DA06.3.1、DA07.1.3 | 计算族执行链 | 与步 2 并行 |
| 4 | 交付：DA10.1.1、DA10.3.1、DA10.3.3 | 工作簿与报告 | 步 2、3 有产出后 |
| 5 | bundle、Skills；与数据层联调两族链路 | 可安装包 | — |
| 6 | 阶段 2 六个流 | 按需能力 | 六流并行 |
| 7 | 阶段 3 | S1 能力 | P1 定案后 |
| 8 | 文档回写：05 类型迁移；02 字段校准 | 文档一致 | — |

## 11. 验证

1. 单元：每个原子正例与反例；注册表与 Catalog 一致；注解与存储层观测一致。
2. 安全反例：
   - SQL：多语句、`COPY`、`ATTACH`、`read_csv`、未绑定表、扩展加载均拒绝；
   - 表达式：缺失值得 `unknown`；类型不符报 issue；AST 中出现非封闭算子拒绝；
   - 引擎：版本不一致返回 `failed`。
3. 两段式：proposal 中编造的指标、维度、表名被拒；`EgressDecision=deny` 时 `inference_request` 不含内容。
4. 链路（与数据层联调）：
   - 判定族：`RuleDefinition` + `ExtractedRecordRef` → AST → `Assessment`，`unknown` 不折算；
   - 计算族：不规则工作簿 → `TableRef` → `MetricDefinition` → `RequirementSpec` → SQL → `ComputedResult` → 工作簿与报告。
5. 入口黑盒与 Mint：同 06 §10 第 3、4 项。

## 12. 风险

| 风险 | 处理 |
|-|-|
| 共享运行时抽出影响数据层 | 抽出后数据层全部门禁重跑，行为不变为验收条件 |
| DuckDB 安全配置随版本变化 | 锁定版本；安全反例纳入门禁 |
| 表达式算子集不足以表达规则 | 不支持的条件返回 `needs_input`，由 DA03.15 判为不可自动判定；扩充算子按 05 版本规则 |
| DA07.2 无隔离环境 | 返回 `dependency_unavailable`，不降级为本地执行 |
| 阶段 2 依赖未建的数据层能力（DA04.3、`LineageEdge`） | 对应流后移，或先用符合契约的夹具开发 |

## 13. 实施与评审记录

修复轮次记在文首 frontmatter `changes`；评审与之后的修复记录在 `07-application-layer-build/`。

| 文件 | 轮次 | 日期 | 内容 | 测试 |
|-|-|-|-|-|
| [r41-review.md](07-application-layer-build/r41-review.md) | 41 评审 | 2026-11-05 | S0 13 项完成度（已完成 5 / 部分 8）；按需与 S1 统计；可行性评审与 W0 接缝落实；新缺陷 A1–A12；复现脚本 [r41-repro/](07-application-layer-build/r41-repro/) | 201 |
