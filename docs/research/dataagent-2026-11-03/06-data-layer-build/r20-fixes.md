# Round 20 fixes — Reviewer r20 的指标校验绕过（N1/N2 P1）与片段标点/引号 Tokenizer（N3/N4 P2）

对照本轮 Reviewer 独立审查报告（team 目录 `reviewer_r20_report.md`，评分 完成度 8.6 /
质量 6.7 / 综合 7.7，VERDICT FAIL）修复其 §4 的 N1/N2 两项 P1 与 N3/N4 两项 P2。全部
四项在修复前均以 `ok / unresolved=[]` 通过并落库（N1/N2，真实 MCP + SQLite 实证）或把
合法片段误拒（N3/N4）。修复后：绕过路径全部降级为 `partial` + 显式 `unresolved`
（`da03.metric_unresolved`），合法片段（含句末标点、曲引号+逗号常量、千分位数字）保持
`ok`，且 r12–r19 既有守门（含 F4 guard、连接词交换、r16 片段豁免）不回归。

N5（计划 §10.2 完整场景组合验收）与 N6（source-ref 内容归档、SQLite 显式 close、
dev 依赖门）**本轮未处理**，见文末"未处理项"。

## N1 — P1：省略可选 `available_fields` 即完全绕过来源谓词校验

### 现象（reviewer_r20_source3_probe.log:30–31，真实 MCP 两段式 + SQLite 只读核查）

来源仍为 `Sum amount CNY for status = 'paid' by department.`，仅不传默认 `[]` 的
`available_fields`：

| 提案 filter | 修复前 |
|-|-|
| `status = 'refunded'` | ok / unresolved=[]，落库 |
| `status != 'paid'` | ok / unresolved=[]，落库 |

根因：F2 修复把 `_filter_predicate_divergence` 放进了 `if data.available_fields:`
分支——schema 是可选输入，来源一致性却是独立义务；省略 schema 不能等同于"来源没有约束"。

### 修复（`semantics/metrics_rules.py`）

- 来源一致性校验（filter 谓词对比、来源约束携带检查）移出 `if data.available_fields:`
  分支，**无论是否提供 schema 都执行**；
- 仅"字段是否在绑定 schema 中"的存在性检查保留条件执行（无 schema 无从检查存在性）；
- `measure_field` / `time_field` 的 schema 绑定不变（无 schema 时维持原行为）。

### 修复后实测（test_round20_reviewer_findings.py）

| 提案 filter（无 schema） | 结果 |
|-|-|
| `status = 'refunded'` | partial，unresolved 含 divergence，`da03.metric_unresolved` |
| `status != 'paid'` | partial，同上 |
| `status = 'paid'`（控制组） | ok，unresolved=[] |

## N2 — P1：删除来源过滤或换语法仍错误放行

### 现象（reviewer_r20_source3_probe.log:34–35）

同一来源（含 `available_fields`）：

| 提案 | 修复前 |
|-|-|
| `filters=[]`（整条 paid 约束被删除） | ok / unresolved=[]，落库 |
| `filters=["status IN ('refunded')"]` | ok / unresolved=[]，落库 |

根因：校验只针对"提案中**存在且可被 `_FILTER_PREDICATE` 正则解析**"的过滤——
`filters=[]` 没有任何 filter 可比对；`IN` 语法解析失败时 helper 返回 `None`，被当成
"无冲突"。"无法解析"不能等同于"无冲突"。

### 修复（`semantics/metrics_rules.py`）

- 新增 `_dropped_source_constraints(filters, source_text)`：来源文本内联陈述了某字段的
  谓词（如 `status = 'paid'`）而提案没有任何 filter 携带该字段时，产出显式
  `unresolved` 条目（"the definition sources state a constraint on status that the
  proposal drops"）。只约束来源**确实陈述过符号谓词**的字段；措辞型来源
  （"paid status"）不触发，字段携带比对使用与既有 `_FILTER_FIELD` 相同的字段读取。
- `_filter_predicate_divergence`：filter 的字段被来源陈述谓词约束、但 filter 本身不是
  可解析的 `field op literal` 形态（如 `status IN ('refunded')`）时，返回
  "not a supported predicate form" 的 unresolved 原因，不再静默返回 `None`。

### 修复后实测

| 提案（含 schema） | 结果 |
|-|-|
| `filters=[]` | partial，unresolved 含 status 约束被丢弃 |
| `filters=["status IN ('refunded')"]` | partial，unresolved 含 "not a supported predicate form" |
| `filters=["status = 'paid'"]`（控制组） | ok |
| 措辞型来源 + `filters=[]`（控制组） | ok（无符号谓词即无携带义务） |

无 schema 时同样执行（N1 修复保证）。

## N3 — P2：合法片段追加句末标点即误拒

### 现象（reviewer_r20_source3_probe.log:22–23）

源 `Policy: Claims must be approved and invoices may be filed.`：

| 条件 | 修复前 |
|-|-|
| `Claims must be approved` | ok |
| `Claims must be approved.` | needs_input / "different logical connectives" / 不落库 |

根因：句末句号使 `normalize_text` 的产物尾部多出 `.`，子串快路径不命中，落入全锚点
AND 与单子句片段的连接词比较——片段没有连接词而锚点有 `and`，被误判分歧。加一个句号
不改变命题。

### 修复（`runtime/anchors.py`）

- `anchor_supports_text` 中，子串快路径使用的 needle 在归一化后剥离**句末**标点
  （`.。!?;…`，`_SENTENCE_FINAL_MARKS`，仅 rstrip，不动中间标点）；
- 子串快路径**之前**执行的结构化守门为：guard 丢失、数字、比较界、否定极性
  （r21 复核更正：情态/主体/条件方向检查仍在快路径之后，本轮控制组未见回归，
  r21 修复文档对此不再作"全部在前"的表述）。

### 修复后实测

| 条件 | 结果 |
|-|-|
| `Claims must be approved.` | ok |
| `Claims must be approved`（控制组） | ok |
| `Invoices may be filed.`（guard 丢弃 + 句号，F4 回归） | 仍被拒（needs_input） |
| `...approved or invoices may be filed.`（整句连接词交换） | 仍被拒 |

## N4 — P2：曲引号归一太晚，含逗号字符串常量被截成半个值

### 现象（reviewer_r20_source3_probe.log:32–33）

PDF 实际抽出 `status = ’paid,final’`（曲引号）。合法同值提案被降级：谓词正则在引号
归一**之前**运行，`’` 不匹配 `'[^']*'`，落入 `[^\s,;]+` 分支并在逗号处截断，stated
值变成 `'paid`。

根因：`_SOURCE_PREDICATE` 的 value 分支按"先引号、后裸 token"排序，但曲引号折叠发生在
`_normalize_filter_value`（正则之后）；且 `_normalize_filter_value` 对所有值统一
`replace(",", "")`，把千分位规则套用到了字符串常量上。

### 修复（`semantics/metrics_rules.py`）

- 引号折叠（`_QUOTE_FOLD`）提前到**tokenize 之前**：`_source_predicates` 对来源文本、
  `_filter_predicate_divergence` 对 filter 文本都先折叠再匹配；
- `_SOURCE_PREDICATE` value 分支增加数字形态 `\d[\d,]*(?:\.\d+)?`（在裸 token 之前），
  千分位数字 `1,000` 不再截断成 `1`；
- `_normalize_filter_value` 的逗号移除改为仅限**两个数字之间**（千分位，
  `_THOUSANDS_SEPARATOR`），字符串常量内的逗号（`paid,final`）是值的一部分。
  （r21 复核更正：该口径仍不完整——数字间逗号删除被套用到了**引号内**的字符串
  常量上，`'12,34'` 仍被折算成 `1234`；见 r21-fixes.md F1。）

### 修复后实测（PDF 直引号输入 → Helvetica 抽出曲引号，同 Reviewer 夹具）

| 来源 / 提案 | 修复前 | 修复后 |
|-|-|-|
| `’paid,final’` / `status = 'paid,final'` | unresolved（stated=`'paid` 截断） | ok |
| `’paid,final’` / `status = 'paid'` | unresolved | partial，divergence |
| `amount > 1,000` / `amount > 1000` | stated=`1`，divergence | ok |

## 验证

- 数据层全量 `pytest -p no:cacheprovider -o addopts="" -q`：**596 passed**
  （581 + 15 新增 `tests/test_round20_reviewer_findings.py`，含 N1×3、N2×5、N3×4、
  N4×3；r21 复核确认实际分布为 N2×5 而非本文件早先写的 N2×6）。
  这 15 例只回放两段式的 proposal 阶段，真实 MCP 两段式 + SQLite 落库证据
  由 Reviewer/Developer 探针另行提供（r21 起产品测试亦补了持久化断言）。
- 契约全量：**117 passed**。
- 修复前基线复演：将 N1/N2/N3 钩子临时还原后重跑新测试，**11 failed / 4 passed**
  （N4 由独立 tokenizer 实测证明：旧正则对抽出文本产出 `('status','=','\'paid')`，
  新代码产出 `paid,final`）。
- 发布门禁 `scripts/verify_local.sh`：见 manifest-check.log / verify_local.log。

## 变更文件

- `packages/capabilities/dataagent-data/src/dataagent_data/semantics/metrics_rules.py`（N1/N2/N4）
- `packages/capabilities/dataagent-data/src/dataagent_data/anchors.py`（N3，仅 needle 尾部标点剥离 + `_SENTENCE_FINAL_MARKS` 常量）
- `packages/capabilities/dataagent-data/tests/test_round20_reviewer_findings.py`（新增）
- `packages/capabilities/dataagent-data/evidence/round4/manifest.sha256` /
  `manifest-check.log`（重生成，r19-fixes.md 轮换为 r20-fixes.md，加入新测试文件）
- `packages/capabilities/dataagent-data/packaging/bundle/`（重建）
- 本文档

## 未处理项（Reviewer r20 §4 N5/N6，非本轮范围）

- **N5（P2）**：计划 §10.2 指定的完整场景组合仍缺——计算场景无多行表头 + 1904 epoch
  组合，判定链无单据 JSON → 两段式字段抽取，applicability/preconditions 未接入场景链。
- **N6（P2）**：`packaging/source-ref.toml` 仍缺实现 commit/内容归档与制品 digest；
  SQLite 连接仍不显式 close；clean 环境下 `verify_local.sh` 依赖预先
  `uv sync --frozen --extra dev`（jsonschema/pytest 未显式声明为 dev group）。
