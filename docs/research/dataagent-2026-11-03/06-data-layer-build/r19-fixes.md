# Round 19 fixes — Reviewer r19 的四类 P1 语义放行（F1–F4）

对照本轮 Reviewer 独立审查报告（team 目录 `reviewer_r19_report.md`，评分 完成度 8.2 /
质量 6.4 / 综合 7.3，VERDICT FAIL）修复其 §3 的四类 P1 阻断项。这十项反例在修复前
均以 `ok / issues=[] / unknowns=[] / unresolved=[]` 通过并落库，其中两项还进入前置条件
`satisfied` 结论；修复后全部 fail-closed（`needs_input` / `partial`，unknowns/unresolved
非空，规则类不落库），且 4 个控制组与 r12–r18 既有守门（含 r16 片段豁免、must↔shall
同类互换、`B only if A` 互逆式拒绝）不回归。

## F1 — P1：适用范围表达只核对内容词，否定/界限/连接词改写仍以 ok 落库

### 现象（reviewer_r19_probe.log:9–11，真实 MCP 两段式）

| 源 | 提案 scope_expression | 修复前 |
|-|-|-|
| `Employee claims are covered by this policy.` | `Employee claims are not covered by this policy.` | ok，落库 |
| `This policy covers claims above 5000 CNY.` | `This policy covers claims below 5000 CNY.` | ok，落库 |
| `This policy covers claims and invoices.` | `This policy covers claims or invoices.` | ok，落库 |

根因：`define_rule_applicability` 只用 `ungrounded_terms` 逐词核对，而 `not` / `above` /
`and` 都是覆盖检查的停用词——内容词与数字全部匹配即通过，语义相反也一样。

### 修复（`runtime/anchors.py` 新增 `semantic_divergence`，`semantics/applicability.py` 接入）

- 新增 `semantic_divergence(condition, source_text)`：把规则路径（`anchor_supports_text`）
  已验证的结构化守门原语——否定极性、比较界（含 inclusivity）、连接词有序序列、
  情态类发明/作用域、条件方向、主语绑定、guard 丢失、全量复述的情态序列——以
  "冲突原因列表"的形式暴露给非引用型字段复用。
- `define_rule_applicability`：scope_expression 逐项跑 divergence，任一冲突降级为
  `partial`，记 `unknowns` 与 `da03.scope_semantic_divergence`（warning）。计划 §5
  步骤 3 的"unknown 不折算"仍由既有 `da03.scope_not_grounded` 项保证，两项并行。

### 修复后实测（dev_r19_fixed_probe.log）

| 提案 | 结果 |
|-|-|
| `...are not covered...` | partial，unknowns 含 "different negation polarity" |
| `...below 5000...`（含 `under` 变体） | partial，unknowns 含比较界与主语绑定冲突 |
| `...claims or invoices...` | partial，unknowns 含 connective 冲突 |
| 控制组 `applies to employee claims` | ok，unknowns=[] |

## F2 — P1：指标过滤只校验字段存在，不校验谓词值与运算符

### 现象（reviewer_r19_probe.log:12–14）

定义来源 `Sum amount CNY for status = 'paid' by department.`（available_fields 含
status），提案过滤 `status = 'refunded'`、`status != 'paid'` 均 `ok / unresolved=[]`
并落库。字段在 schema 中不代表任意常量或相反运算符被来源支持。

### 修复（`semantics/metrics_rules.py`）

- 新增 `_source_predicates`：扫描定义来源文本内联谓词（`field op value`，含直引号与
  PDF 曲引号 `’paid’` 的归一化、大小写与千分位逗号）。
- 新增 `_filter_predicate_divergence`：**仅当来源对过滤字段确有内联谓词时**，过滤的
  `(op, value)` 必须命中其一，否则记 `unresolved` + `da03.metric_unresolved`，
  status 降为 `partial`。来源从未约束该字段（如措辞型 `minus refunds`）时不受影响，
  交给 schema 检查——避免对合法的措辞型来源误报。

| 过滤 | 修复后 |
|-|-|
| `status = 'refunded'` / `status != 'paid'` | partial，unresolved 非空 |
| `status = 'paid'` / `status = 'PAID'`（控制） | ok |
| 来源不含 status 谓词时的 `status != 'refunded'`（控制） | ok |

## F3 — P1：主语比较绑定丢失 inclusivity，双对象共享阈值时 `>`/`>=` 可互换

### 现象（reviewer_r19_probe.log:4–6）

源 `Claims above 5000 CNY and invoices at least 5000 CNY require approval.`，提案
交换两处界限（`at least`↔`above`）：全局比较集合相同（strict/inclusive 各一），
`define_business_rules` ok 落库；同一提案作前置条件配 `facts={c1:true}` 得
`satisfied`。数值恰为 5000 时适用集被改变。

### 修复（`runtime/anchors.py`）

`_comparison_bindings` / `_comparison_subject_conflicts` 的绑定键从
`(direction, number)` 扩为 `(direction, number, inclusive)`：inclusive 短语先匹配并
占位，strict 模式不重叠消费，每个主语保存自己的边界。

修复后：上述互换在 rules / preconditions 均被拒（`da02.anchor_value_mismatch`，
不落库 / unknown），逐字引用与单主语片段（`Claims above 5000 CNY`）保持 ok；
符号形式（`>`↔`>=`）同样被拒。

## F4 — P1：逐字片段快路径先于条件作用域检查，可丢掉整条 guard 仍得出确定结论

### 现象（reviewer_r19_probe.log:1–3）

源 `If claims are approved then invoices may be filed.`（及 `only after` 变体），提案
仅引用后件 `Invoices may be filed`：`define_business_rules` ok 落库；
`define_rule_preconditions` 配 `facts={c1:true}` 得 `satisfied`。子串快路径在任何
结构检查前 return，条件方向的 helper 又要求两侧都有条件标记。

### 修复（`runtime/anchors.py` 新增 guard 检查）

- 新增 `_guard_is_dropped(anchored, condition)`：识别锚点语句的 guard——
  `if/then`（复用 `_conditional_structure` 的前件）、`only if / only when /
  only after / unless`、中文 `只有X才Y` / `X方可Y`（含 `须先`、`之后才`）——
  并检查条件是否保留 guard 内容（英文按内容词，中文按内容字符、豁免"在/后"等
  功能字）。
- `anchor_supports_text` 在**子串快路径之前**执行该检查：引用后件而丢 guard 的
  条件返回 `da02.anchor_value_mismatch`，规则不落库；前置条件保持 `unknown`，
  guard 留在 unknowns（`["c1"]`）。引用前件本身（合法的前置条件形态）与完整引用
  不受影响。

| 提案 | 修复后 |
|-|-|
| `Invoices may be filed.`（引后件） | rules: needs_input 不落库；preconditions: unknown |
| `only if / only when / unless` 变体 | 同上被拒 |
| `Claims are approved.`（引前件，控制） | ok；preconditions satisfied |
| 完整引用 / 非条件锚点片段（r16 控制） | ok |

## 验证

- 数据层全量：`pytest -o addopts="" -q` → **581 passed**（560 + 21 项新增
  `tests/test_round19_reviewer_findings.py`：F1–F4 各含审查员原例、变体与控制组，
  含中文 guard 对）。契约包未改动。
- 独立 MCP 探针（`dev_r19_fixed_probe.py`，真实子进程两段式 + SQLite 落库核查）：
  27 案例，18 项错误放行全部关闭，9 项控制（含 r16 片段豁免、大小写归一、
  未约束字段）全部保持 `ok`。
- 发布门禁 `scripts/verify_local.sh`：contracts 117 / data 581、schema 68、
  catalog 32、CLI 32、MCP 32、bundle 69 文件 0 pyc、mint dry-run、manifest 199/199、
  隔离安装冷启动——`verify_local: OK`。

## 未处理（Reviewer r19 的非本轮范围项）

- F5 发布追溯（source-ref 完整 commit 归档）、F6 完整场景组合夹具、F7 SQLite 显式
  close、P3 重构阈值（anchors.py 行数、lint/type）——维持 Reviewer 记录，不因本轮
  修复而关闭。
