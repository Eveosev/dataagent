# W0 接缝规格（Seam Specifications）

- 版本：v1.0（2026-11-05）
- 状态：已冻结为 S0 实现的约束；对应 07 计划 v0.3 §4/§5 与可行性评审 §5
- 实现锚点：`dataagent-runtime/src/dataagent_runtime/ports/tabular.py`、`dataagent-application/src/dataagent_application/{helpers,contracts,planning,execution}.py`、`dataagent-data/src/dataagent_data/{helpers,semantics/metrics_rules,ingestion/files}.py`
- 本文是批准工作流 W0 的交付：六项接缝规格 + 判定族/计算族各一份完整样例。样例中的引用（`sha256:`、`table:`、`schema:`、`draft:` 等）均为真实形状，取自本轮实测链路。

## §1 版本化 codec 规格（表 / 文档 / 来源映射）

### 1.1 表载荷（`dataagent_runtime.ports.tabular`）

所有层读表必须经共享 codec（`decode_table` / `decode_table_payload`），禁止导入 `dataagent_data`。

| 项 | 规格 |
|-|-|
| 版本声明 | `payload_version` / `format_version` 为显式整数；缺省时按 v1 形状识别（`columns` + `rows` 均为 list） |
| 未知版本 | `invalid_input`（`unsupported_table_version` 语义），绝不猜测解码 |
| v1 列 | `columns[].{name, field_id, value_type, unit?, source_path}` |
| v1 行 | `rows` 行主序；`row_meta[]` 与行一一对应，携带 `role` 与 `reason` |
| 行角色（row role） | `detail / subtotal / total / title / unknown`；`unknown` 按不可聚合处理（fail closed） |
| 聚合规则 | 消费方必须用 `detail_rows()`；`subtotal/total/title/unknown` 不得与明细一起求和（合计行是明细的再聚合） |
| 身份 | `TableRef{asset, schema_ref, data_ref, row_identity?, source_map_ref?}`；`data_ref` 是内容寻址 digest |

反例（已测试）：对含 3 行明细 + 1 行合计（2500）的表求 `sum(amount)`，明细合计 300 是正确答案；把合计行当明细会得到 600（双重计数）。

### 1.2 字段身份（name ↔ field_id）

B1 接缝（tester r20）冻结如下：

1. **稳定身份是 `field_id`**（提取时指派，如 `c1..c4`），`name` 是人类表头。跨层数据流（`MetricDefinition`、`RequirementSpec`、SQL 列名）一律引用 `field_id`。
2. **数据层负责解析**：`define_metric_formula`（DA03.4.1）经 `register_file_tables`/`file_field_map`（源文件 → 已提取表索引，版本化对象 `file_tables`，key 为 `<source_ref>@<source_revision>`）把 proposal 里的人类表头名规范化为 `field_id`；同一表头名在不同表中解析到不同 `field_id` 时视为歧义，保留原名并计入 `unresolved`。指标固定过滤携带 `referenced_fields=[field_id]`。
3. **应用层兜底解析**：DA06.1.1 绑定时对 `measure.field_ref`、`time.time_field`、`filters[].referenced_fields`、`proposal.dimensions` 同时接受 `field_id` 或表内唯一的 `name`（`_field_identity_index`），歧义名（多义、或与另一列 id 撞名）不解析，按 id 校验失败处理。规范化后的 `RequirementSpec.dimensions` 只含 `field_id`。
4. **SQL 侧**：DuckDB 执行把列注册为 `field_id`（`execution/sql.py::_load_table`），SQL caliber 校验按 `field_id` 比对。

### 1.3 文档与来源映射

- 文档：解析为块后按内容寻址存储（`content.put`），`DocumentRef` 引用块资产；块 payload 与 codec 版本随 `dataagent-data` S0。
- 来源映射：`SourceAnchor{source_ref, source_revision, selector}`。selector 目前支持 `excel_cell`（sheet/range）、`json_pointer`、`text_span`（unit_ref/char_start/char_end）。文件身份由 `register_file_ref` 固化（kind `file_ref`，`<id>@<revision>` 不可重绑定到不同字节）；锚点解析经 `AnchorResolver`，解析失败显式报告，不静默接受。

## §2 规则执行顺序与三值真值表

### 2.1 执行顺序（固定，不可重排）

```
1. applicability（适用性）      —— 不适用 → not_applicable
2. preconditions（前置条件）    —— 未满足 → not_applicable
3. exceptions（例外规格）       —— 任一例外成立 → not_applicable（例外优先于主表达式）
4. 主表达式（combination 编译出的封闭算子 AST）
5. verdict 映射（见 2.3）
```

`applicable` / `preconditions_met` 显式传 `null` 表示"未知"，按 `unknown` 处理（不是 false，也不是省略——省略走默认适用路径）。例外规格先于主表达式求值：例外命中即 `not_applicable`，不再看主表达式。

### 2.2 三值真值表（`execution/expressions.py`，`True/False/UNKNOWN`）

解释器不使用 `eval`；`UNKNOWN` 是独立哨兵。字段值 missing/conflict（`FieldValue.status ∈ {missing, conflict}`）或空单元格使**所在子树**为 `UNKNOWN`，不折算为 false；`is_missing` 算子本身可判定（把缺失作为谓词，而不是传染）。

| and | T | F | U |
|-|-|-|-|
| **T** | T | F | U |
| **F** | F | F | F |
| **U** | U | F | U |

| or | T | F | U |
|-|-|-|-|
| **T** | T | T | T |
| **F** | T | F | U |
| **U** | T | U | U |

| not | |
|-|-|
| **T** | F |
| **F** | T |
| **U** | U |

封闭算子集：逻辑 `and/or/not`；比较 `eq/ne/lt/le/gt/ge`；算术 `add/sub/mul/div`；特殊 `in/between/is_missing/date_diff/string_match`；叶子 `field/literal`。算子集外的一律 `invalid_input`（fail closed）。

### 2.3 字段四态 → verdict 映射

字段值状态（`FieldValue.status`，**无 `unknown` 取值**，07 v0.3 已修正）：`present / missing / conflict / low_confidence`。

| 主表达式结果 | 字段状态参与 | verdict |
|-|-|-|
| `true` | 全部 present（或 low_confidence 仍可用值） | `pass` |
| `false` | 同上 | `fail` |
| `UNKNOWN`（missing/conflict/空单元格传染） | — | `unknown` |
| — | 适用性不满足 / 前置条件未满足 / 例外命中 | `not_applicable` |
| — | 类型不匹配（标量） | `failed`（`da07.expression_type_mismatch`） |
| — | 类型不匹配（表行） | 该行 `unknown` + warning issue |

verdict 词表即 core `Verdict`（05 §3.3：`pass/fail/unknown/not_applicable`），与治理层 08 的验收交付一致；消费方需要业务别名（`satisfied`/`violated`）时自行映射，生产方不再输出旧词表。

`low_confidence` 字段按值参与并附 `da07.low_confidence_field` 警告（不静默丢弃，也不折算为 unknown）。

## §3 结构化单表计划 Schema（约束 SQL 口径）

`RequirementSpec`（`dataagent_application/contracts.py`）是绑定后的口径，DA06.3.1 生成 SQL 与 DA07.1.3 执行都必须服从：

```jsonc
{
  "requirement_id": "req:<sha256[:16]>",        // 由 statement 内容派生
  "statement": "按部门统计已支付金额",
  "metrics":   [{"id": "draft:metric:...", "revision": "r1"}],
  "dimensions": ["c1"],                          // 只含 field_id（§1.2）
  "time":      {"from": "...", "to": "..."},     // 可选；ISO-8601
  "filters":   [{"text": "状态 = '已支付'", "referenced_fields": ["c4"]}],
  "grain":     "部门 x month",
  "assumptions": [], "unresolved": [], "ambiguities": []
}
```

DA06.3.1 的口径校验（`sql_caliber_errors`，tester r20 B2 / r24 / r25 / r26 / r27 B1 后的强度）逐项绑定：

| 绑定项 | 校验 |
|-|-|
| 度量列 × 聚合 | SQL 的聚合函数必须是 `<aggregation>(<measure field_id>)`，且出现在**产出结果的 SELECT 的顶层投影**（标量子查询里的聚合、窗口聚合 `sum(x) OVER ()`、带 DISTINCT 的聚合都不满足） |
| 聚合形状 | 聚合参数必须是**裸度量列**：`sum(amount * 2)`、`sum(amount + 50)`、`sum(CASE ...)` 都不是绑定的聚合；带 `FILTER` 子句的聚合改变聚合行集，不满足；投影不得在聚合外再做变换（`sum(amount) * 2` 拒绝；值保持包装 `CAST`/`TRY_CAST`/括号除外，聚合参数内同理——`sum(CAST(amount AS DOUBLE))` 通过）；读取 CTE/派生表**已聚合的列**必须以裸列投影（外层 `total * 2`、`coalesce(total, 0)` 拒绝）（r25 B1） |
| 列血缘 | CTE/派生表导出的列只有**原样透传**物理列时才承载口径：`amount * 2 AS amount` 使外层 `sum(amount)` 视为变换聚合、对派生 `approved`/时间列的谓词不绑定（r26 B1）；`SELECT *` 原样透传可用，带 `EXCEPT/REPLACE/RENAME` 拒绝 |
| 固定过滤 | 字段**出现**且**算子与常量一致**（`approved = true` 不能写成 `= false`；文本谓词解析为 `field <op> literal` 后与 WHERE 逐列比对；无法解析的自由文本退化为存在性检查），且必须是**无条件合取项**（OR 替代项、NOT 取反不绑定；r22）；固定过滤列上**不得有额外谓词**（`approved = true AND approved = false` 中和口径，拒绝；r26 B1） |
| 维度 / grain | 绑定的每个维度必须出现在 GROUP BY；GROUP BY 里不得出现绑定口径（维度 ∪ 时间字段）之外的列；GROUP BY 不得使用派生列或 ROLLUP/CUBE/GROUPING SETS（小计/合计行改变 grain；r26 B1） |
| 时间区间 | 绑定 time 时时间字段必须被 WHERE 约束，且起止值实际对齐（仅 `IS NOT NULL` 或错误窗口不满足；r22）；窗口为半开区间，**每个端点只接受唯一算子/值对**：起点 `>= from`（纯日期粒度等价 `> <from-1天>`）、终点 `< to`（纯日期粒度等价 `<= <to-1天>`）——`> from`（丢含端起行）与 `<= to`（保排端行）拒绝，边界行在场时它们交付不同合计却携带同一 `metric_version`（r32 B1）；`BETWEEN` 展开为 `>= low AND <= high`，故仅 `high = <to-1天>` 时等价；时间字段上**不得有额外谓词**（`AND occurred_on >= '2030-01-01'` 中和窗口，拒绝；r26 B1） |
| 作用域 | 过滤/时间窗/聚合/GROUP BY 只从**产出结果的 SELECT 及其读取的 CTE/派生表链**收集：未被读取的 CTE、EXISTS/标量子查询里的谓词不绑定任何约束（r24 B1） |
| 行数保持 | 绑定表与每个 CTE 在 FROM 中只允许读取一次：自连接（含 `JOIN ... ON true`、CTE 自连接）放大行数，直接拒绝（r24 B1）；**HAVING / QUALIFY / LIMIT / OFFSET 拒绝**：HAVING 是未声明的分组过滤（即使聚合文本正确），QUALIFY 是同类的分组后行过滤（含 CTE/派生表内层），LIMIT/OFFSET 绕过执行侧行数预算（r26/r27 B1） |
| WHERE 合取项闭环 | 只有**绑定的固定过滤与时间窗端点**可以选择交付行：任何作用域（含 CTE/派生表内层）的 WHERE 合取项都必须是绑定时间/过滤列上可与绑定算子/常量核对的谓词——非绑定列上的额外过滤（维度 `region = 'north'`、度量 `amount > 150`、`IN` 列表）、对已聚合/派生 CTE 列的过滤（聚合后 `WHERE`，变相 HAVING）、绑定列上无法核对的形式（`IN`/`LIKE`/`IS NULL`）与无列常量合取项（`1 = 0`，等价 LIMIT 0）均拒绝（r27 B1） |
| JOIN / 采样闭环 | **一切 JOIN 拒绝**（inner/outer/semi、`ON`/`USING`/`NATURAL`、逗号交叉连接，含 CTE/派生表内层）：ON 合取项是变相 WHERE（维度/度量/时间/矛盾/常量谓词均可走私），等值连接右侧行数放大不受控，ON 内子查询绕过 read-once 守卫（r29 B1）；**行采样拒绝**：`FROM t TABLESAMPLE`（含 CTE/派生表内层）与 select 级 `USING SAMPLE` 在绑定聚合前丢行（r29 B2）。`GROUP BY ALL` 不支持（保守拒绝，按显式列 GROUP BY） |
| 行角色 | 执行侧由 `detail_rows()` 保证（§1.1），SQL 无需也无法引用行角色 |

任一不符 → `failed`（`da06.sql_caliber_mismatch`），不允许"SQL 语法对但口径错"带着指标版本通过。SQL 安全约束（单条 SELECT、绑定表、函数黑名单）在口径校验之前执行。

## §4 basis_refs → EvidenceRef 解析路径

判定产物 `Assessment` 同时携带两个引用面：

1. `basis_refs: list[str]` —— 轻量字符串坐标，指向支撑判定的规格与输入：
   - 标量（DA07.5.1）：`["spec:<spec_id>"]`
   - 表（DA07.5.2）：`["spec:<spec_id>", "table:<table asset id>"]`
2. `evidence: list[EvidenceRef]`（contracts round 5 新增）—— 结构化证据，解析路径固定：

```
Assessment.basis_refs
  ├─ "spec:<spec_id>"   → ExecutableSpec.source_refs（VersionedRef → 规则草案/来源锚点）
  │                        └─ SemanticDraft.sources[].SourceAnchor → §1.3 锚点解析 → 原文/原单元格
  └─ "table:<asset id>" → TableRef → data_ref → §1.1 codec 解码 → 参与行（detail）与列（field_id）
参与求值的每个 FieldAccess（field_id、值、锚点、unknown/low_confidence 标记）
  → EvidenceRef{ id, evidence_type, source_anchors, value, obtained_by, verification_ref? }
```

`obtained_by` 记录取得方式（如 `"dataagent-application/DA07.5.2"`），`verification_ref` 指向可复核的执行回执。报告（DA10.3）只引用 `EvidenceRef`，不内嵌原文。

## §5 模型可见输出边界

- **两段式原子**的 `inference_request` 是唯一的模型可见内容通道。内容键：`statement / conditions / exceptions / fields / table / metrics / samples`（`EGRESS_CONTENT_KEYS`）；结构键（`kind / closed_operators / ast_shape / constraints / instruction` 等）永不剥离。
- **egress 门**（07 §4.1，`helpers.gate_inference_request` → `dataagent_runtime.enforcement.egress_check`）：
  1. 未提供 `egress_decision_ref`：S0 默认 `warn`——内容放行 + `da12.egress_required` 警告；
  2. 提供且决策为 `allow`：请求携带 `destination`（调用方声明，或取决策自身的 `ModelDestination`）→ 内容放行；调用方声明的 destination 与决策不一致时仍拒绝（fail closed）；
  3. `deny` / 不可解析 / 不覆盖 `content_refs`：剥离全部内容键，返回 `needs_input` + `da12.egress_required`；
  4. `allow_masked`：以掩码产物替换内容（需可解析的 `masking_ref`）。
- 判定/计算**结果**（Assessment、ComputedResult、工作簿、报告）不经模型：它们是确定性执行的产物，模型只参与第一段的提案生成。

## §6 P2 执行点与宿主注入

- **P2 定案（07 v0.3）**：`mint-core` 路径 + 运行时完整复检。内核会话存在且宿主声明 kernel guard 生效时，access 复检只验证决策存在；无声明则按无内核路径全量复检（08 §11 / 评审 §7.3）。不宣称内核豁免。
- **Mint 宿主环境注入（W1c，tester r20 B4 定案）**：Mint 0.1.25 内核清空 MCP 子进程环境；`.mcp.json` 服务描述符的 `env` 映射是唯一注入通道（值按字面传递，无 `$VAR` 展开，`$PKG` 仅出现在 args）。宿主要求三包共享自定义 `data_root` 时，在**项目根**写 `.mcp.json`，用同名服务覆盖包内声明，并注入：

```jsonc
{
  "mcpServers": {
    "dataagent-application": {
      "command": "uv",
      "args": ["run", "--frozen", "--project", "<安装包绝对路径>", "python",
               "-m", "dataagent_application.interfaces.mcp_server"],
      "timeout_s": 120,
      "env": { "DATAAGENT_DATA_ROOT": "/abs/custom/data-root" }
    }
  }
}
```

  同名服务冲突时内核忽略包内声明、项目级生效（内核日志可见“同名服务冲突，已忽略”）。`mint.toml [metadata.env]` 只是**声明**（文档），不是注入机制。`DATAAGENT_WORKSPACE` / `DATAAGENT_CATALOG_SNAPSHOT` 同理。

## §7 判定族完整样例

输入：PDF 报销政策（“Claims above 5000 CNY require department head approval.”）+ 1 条报销记录。

```
1. parse_text_pdf(DA01.2.1) → DocumentRef(doc:9f2c…@r1)，块内容寻址
2. segment_document(DA01.3.1) → units[]（text_span 锚点）
3. extract_fields_to_schema(DA02.12.1)
   → ExtractedRecordRef{asset: rec:…, fields: [
       FieldValue{field_id: "amount", status: present,  value: 6200,
                  anchors: [SourceAnchor{source_ref: "doc:9f2c…", source_revision: "r1",
                              selector: {kind: "text_span", unit_ref: "unit:char",
                                         char_start: 42, char_end: 46}}]},
       FieldValue{field_id: "approver", status: missing}]}
4. define_business_rules(DA03.4.3) → SemanticDraft(rule:…, r1)
   conditions: [c1: "报销金额超过 5000 CNY" (referenced_fields: [amount]),
                c2: "有部门主管审批记录"   (referenced_fields: [approver])]
   combination: "c1 and c2"
5. generate_function_expressions(DA06.3.5) → ExecutableSpec
   spec_id: "expr:…", backend_kind: "expression",
   engine_binding: {engine_id: "dataagent-expression", engine_version: "0.1.0"}
   expression: {"op":"and","args":[
     {"op":"gt","args":[{"op":"field","field_id":"amount","condition_id":"c1"},
                        {"op":"literal","value":5000}]},
     {"op":"field","field_id":"approver","condition_id":"c2"}]}
   （AST 与 combination 的布尔函数经真值表等价比对，and/or 翻转被拒）
6. evaluate_scalar_expression(DA07.5.1)
   applicability: true; preconditions_met: true; exceptions: []
   c1 → 6200 > 5000 → True；c2 → approver=missing → UNKNOWN
   and(True, UNKNOWN) = UNKNOWN（§2.2 真值表）
   → Assessment{verdict: "unknown",
      basis_refs: ["spec:expr:…"],
      unknowns: ["approver"],
      evidence: [EvidenceRef{id: "amount", evidence_type: "field_value",
                             value: 6200, obtained_by: "DA07.5.1",
                             source_anchors: [<步骤 3 的 text_span>]},
                 EvidenceRef{id: "approver", evidence_type: "field_value",
                             value: null, obtained_by: "DA07.5.1"}]}
   —— missing 不折算为 false，verdict 是 unknown 而非 violated
```

每一步的引用链：`Assessment.basis_refs → spec → source_refs → SourceAnchor → 原文 span`（§4）。

## §8 计算族完整样例（真实数据层产物）

输入：`expense.xlsx`（合并单元格 + 表头 + 3 行明细 + 1 行合计）。本轮实测链路：

```
1. extract_irregular_excel(DA01.4.2)
   → TableRef{asset: table:5bd9…, schema_ref: schema:7c1a…@r1, data_ref: sha256:5bd9…}
   columns: [c1 部门, c2 金额(number), c3 发生日期(date), c4 状态]
   （同时 register_file_tables：file:<id>@sha256:… → 该表）
2. expand_merged_cells → classify_table_rows
   → row_meta: [detail, detail, detail, total(reason: "label:合计")]
3. infer_field_types → types{c2: number}
4. define_metric_formula(DA03.4.1)
   proposal.measure_field: "金额"（人类表头名）
   → file_field_map 把 "金额"→"c2"、"发生日期"→"c3"、"状态"→"c4"（§1.2）
   → SemanticDraft(draft:metric:…, r1)
     measure: {field_ref: "c2", aggregation: "sum"}
     filters: [{text: "状态 = '已支付'", referenced_fields: ["c4"]}]
     dimensions: ["c1"], time: {time_field: "c3", grain: "month"}
5. bind_metrics_and_dimensions(DA06.1.1)
   proposal: {metric_ids: [draft:metric:…], dimensions: ["部门"], grain: "部门 x month"}
   → "部门" 经 name→field_id 解析为 "c1"
   → RequirementSpec{dimensions: ["c1"], filters: [referenced_fields: ["c4"]], grain: "部门 x month"}
6. generate_single_table_sql(DA06.3.1)
   → ExecutableSpec{backend_kind: "sql", sql_digest: sha256:…,
      engine_binding: {engine_id: "duckdb", engine_version: "2.0.0"}}
   口径校验（§3）：sum(c2)、WHERE c4 = '已支付'、GROUP BY c1 全部命中
   —— WHERE 值翻转为 '已退款'、丢掉 GROUP BY c1、按 c4 分组均被拒（da06.sql_caliber_mismatch）
7. execute_duckdb_sql(DA07.1.3)
   detail_rows() 排除合计行 → sum(金额) = 300（不是 600）
   → ComputedResult{sql_digest, engine_binding, 口径版本}
8. build_values_only_workbook(DA10.1.1) / export_report_format(DA10.3.3)
   → 三表只写值工作簿 + md/html 报告（EvidenceRef 引用 §4，导出≠发布）
```

该样例即 tester r20 探针 C1 的链路：真实数据层输出（`TableRef` + `MetricDefinition`）进入应用层并完成绑定（B1 修复后实测通过）。
