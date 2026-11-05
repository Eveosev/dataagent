# Round 21 修复 — Reviewer r21 F1/F2/F3（P1）+ F4（P2）+ F5 文档漂移 + N5/N6 范围内推进

对照 [reviewer_r21_report.md](../../../.dsh/state/agent-teamwork/team/reviewer_r21_report.md)（独立真实 MCP 两段式 + SQLite 探针）。

## F1 — P1：引号内字符串的数字间逗号仍被吞

来源 `status = '12,34'` / `status = 'v1,2'`（真实 PDF 曲引号抽出）在 r20 的
`_normalize_filter_value` 中被剥引号后统一做数字间逗号删除，提案
`status = '1234'` / `status = 'v12'` 得到 `ok` 并落库——字符串类型信息丢失。

### 修复（`semantics/metrics_rules.py`）

- `_normalize_filter_value` 重写为三形态：
  - **引号 literal**：内容逐字保留（`'12,34'` → `12,34`、`'v1,2'` → `v1,2`），
    仅折叠大小写与曲引号；不再做任何逗号删除。quoted `'1,000'` 因此是字符串，
    不默认折算成数值（如业务上要按数值解释，需显式约定/字段类型，本层不吞）。
  - **无引号数字 literal**：必须完整匹配有效千分位语法
    `-?\d+(,\d{3})*(\.\d+)?`（`_NUMERIC_LITERAL.fullmatch`），才移除逗号；
    `1,000` → `1000`（N4 控制保留）。
  - **裸 token**：仅剥离句末标点（`.。!?;；…?`），不再动逗号。

### 修复后实测（单元级 + 场景级）

| 来源 / 提案 | 修复前 | 修复后 |
|-|-|-|
| `'12,34'` / `'1234'` | ok（错误放行，落库） | partial，divergence，落库带 unresolved |
| `'v1,2'` / `'v12'` | ok（错误放行，落库） | partial，divergence |
| `'12,34'` / `'12,34'` | ok | ok（控制组） |
| `amount > 1,000`（无引号）/ `1000` | ok | ok（N4 控制保留） |
| `amount > '1,000'`（引号）/ `1000` | ok | partial（quoted 是字符串，显式不折算） |

## F2 — P1：数字分支无 token 边界，截断裸常量

来源 `status = 1000USD` 被 r20 数字分支 `\d[\d,]*` 读成 `1000`：同值
`status = '1000USD'` 被误拒（stated=`1000`），截短假值 `status = '1000'`
反而 `ok` 落库——以部分 token 当完整来源事实。

### 修复

- `_SOURCE_PREDICATE` 数字分支改为
  `-?\d+(,\d{3})*(?:\.\d+)?(?=$|[\s,;]|\.(?!\d))`：
  - **完整 literal 边界**：数字后必须是行尾/空白/逗号/分号，或"后随非数字的
    句点"（`1,000.` 句末 vs `1,000.50` 小数）；
  - `1000USD` 不再落入数字分支，整 token 由裸 token 分支消费
    （stated=`1000usd`）：截短提案 `status = '1000'` → partial，同值提案 → ok；
  - 负号并入 literal（见 F4）。

| 来源 / 提案 | 修复前 | 修复后 |
|-|-|-|
| `status = 1000USD` / `'1000'` | ok（错误放行，落库） | partial，divergence |
| `status = 1000USD` / `'1000USD'` | partial（误拒） | ok（Reviewer 控制组） |
| `status = '1000USD'` / `'1000USD'` | ok | ok |
| `amount > 1,000.`（句末句点）/ `1000` | ok | ok |
| `amount > 1,000.50` / `1000.50` | — | ok（小数完整保留） |

已知边界（与 pre-r20 行为一致，非新回归）：无引号且千分位分组不完整的
literal（如 `1,000USD`、`12,34`）在裸 token 分支于逗号处截断；引号形态
（Reviewer 反例）不受影响，无引号且合法分组的数字不受影响。

## F3 — P1：同字段多个必要谓词，仅携带一个即静默删除其余

来源 `amount >= 1000 and amount <= 5000`，提案 `filters=['amount >= 1000']`
得到 `ok` 落库：r20 的 `_dropped_source_constraints` 只核对**字段**被携带，
不核对字段上的**每一个必要谓词**。

### 修复

- `_dropped_source_constraints` 改为**按谓词**核对：来源陈述的每个
  `(field, op, value)` 都必须被某个提案 filter 携带（同一归一化口径比较）；
  不可解析的 filter 不计入覆盖（其自身已由 divergence 检查显式 unresolved）。
- 连接语义按保守的合取读法处理：无法判读时显式 unresolved，而不是把候选
  谓词集合当作任选其一。

| 来源 / 提案 | 修复前 | 修复后 |
|-|-|-|
| `>= 1000 and <= 5000` / `['amount >= 1000']` | ok（错误放行，落库） | partial：`amount <= '5000'` drops 条目 |
| 同上 / 两条都带 | ok | ok（控制组） |
| 同上 / `['amount >= 2000']` | partial（仅 divergence） | partial（divergence + 两 drops，不互相掩盖） |
| 同上 / `['amount BETWEEN 1000 AND 5000']` | — | partial（not a supported predicate + drops） |

## F4 — P2：负数千分位截断（同一 tokenizer，随 F2 一并修复）

数字分支增加可选负号：来源 `amount > -1,000`、提案 `amount > -1000` → ok；
反向（来源 `-1000`、提案 `-1,000`）→ ok。

## F5 — P2：文档/表述漂移

- `r20-fixes.md`：N2×6 更正为 **N2×5**（实际分布 N1×3、N2×5、N3×4、N4×3）；
  "字符串逗号是值一部分" 的表述追加 r21 更正注记（引号内数字间逗号仍被吞，
  见本文 F1）；"所有结构化守门（含情态）在快路径前" 更正为实际顺序
  （情态/主体/条件方向检查仍在快路径之后，控制组无回归）。
- `tests/test_round20_reviewer_findings.py` 两个 helper docstring 不再自称
  "two-phase"：明确只回放 proposal 阶段；两段式 + SQLite 落库由 Reviewer MCP
  探针与 `test_round21_reviewer_findings.py` 的持久化断言覆盖。

## 测试（新增 `tests/test_round21_reviewer_findings.py`，17 例）

F1×5（两反例 + 引号同值 / 引号千分位 / 无引号千分位控制组 + **落库持久化断言**
——partial 草案写入版本库且 unresolved 随草案持久化，06 §5 降级后写版本）、
F2×5、F3×4、F4×2。全部只回放 proposal 阶段，docstring 如实声明。

## N5 — P2：计划 §10.2 两条完整场景（`tests/test_scenarios.py` 新增 2 例）

- **计算族** `test_compute_chain_full_06_1012_combination`：同一工作簿携带计划
  点名的全部四项不规则——**多行表头**（2 行）、**合并单元格**（表头 B3:C3 +
  数据 A5:A6）、**合计行**、**1904 日期系统**——经 `inspect_workbook_calc_state`
  （断言 `date_system=1904`）→ `extract_irregular_excel`（表头 2 行合并为单一
  逻辑名，`row_numbers=[5,6,7,8]` 证明表头不混入数据，空表头歧义显式披露）→
  `expand_merged_cells` → `classify_table_rows`（3 detail + total）→
  `profile_table_structure` → `infer_field_types`（`c4=date`）→
  `define_metric_formula`（field_id 锚定 c3/c4/c5/c1）。日期断言
  `2026-01-05T00:00:00` 等原值：1904 系统被尊重，无 1462 天漂移。
- **判定族** `test_judgment_chain_full_06_1012_combination`：制度 PDF + 单据
  JSON（`claim.json` 无 `invoice_number`）→ `segment_document` 条款单元 →
  `extract_fields_to_schema` **两段式**（第一阶段 needs_input + candidate_spans；
  第二阶段模拟 Agent proposal：5000/CNY 均带真实 span 锚点，未陈述字段
  `invoice_field` 不提案 → `missing`，不补造）→ `define_business_rules`
  （条款锚点）→ `define_rule_applicability` 两段式 → `define_rule_preconditions`
  （单据金额事实 c1=True，发票事实缺失 → verdict=**unknown**、
  `missing_facts=['c2']`，不折算为 false）→ `assess_automatic_decidability`
  （needs_evidence，unknowns 原样保留）→ `identify_evidence_or_human_gaps`
  （1 条 evidence gap 指向 invoice）→ `mark_automation_coverage`
  （covered=0：unknown 不折入 auto）。

N5 移交口径中 Tester 侧（独立跑完整链 + 真实落库值核查）仍待执行。

## N6 — P2：范围内推进（三项中两项落地，一项仍移交）

- **SQLite 连接生命周期（本轮落地）**：`SqliteDatabase` 新增 `session()`
  contextmanager（`with conn:` 提交/回滚 + `finally: conn.close()`），15 处
  仓储方法与初始化全部改走该入口。验证：save/get 后创建的连接再执行
  SELECT 即 `ProgrammingError: Cannot operate on a closed database`
  （r21 审计中 21 个连接存活的问题关闭）。
- **dev 门前提（本轮落地）**：`scripts/verify_local.sh` 开头显式检查两包
  pytest 与 contracts jsonschema（`uv run --frozen --no-sync` 探测），缺失时
  直接失败并给出 `uv sync --frozen --extra dev` 修复命令；两包 README 固化
  "发布门禁前提"。缺验收依赖时不再中段才以晦涩错误暴露。
- **来源追溯（仍移交）**：`packaging/source-ref.toml` 的完整 commit /
  内容归档 → 制品 digest 映射未在本轮实现（需要发布流程决策，非代码补丁
  可独立闭合），保持 P2 移交。

## 验证

- 数据层全量：**621 passed**（596 + 17 新增 r21 回归 + 2 新增 §10.2 场景 +
  6 并发新增），无 skip/xfail。
- 契约全量：**117 passed**。
- `bash scripts/verify_local.sh`：**EXIT 0**（含新 dev 前提检查、manifest、
  bundle、mint dry-run、隔离 wheel 冷启动），详见 `evidence/round4/verify_local.log`。

## 变更文件

- 源码（2）：`semantics/metrics_rules.py`（F1/F2/F3/F4）、
  `adapters/storage/sqlite.py`（N6 连接生命周期）。
- 测试（2 新 + 2 改）：`tests/test_round21_reviewer_findings.py`（新）、
  `tests/test_scenarios.py`（+2 场景）、`tests/test_round20_reviewer_findings.py`
  （docstring 更正）。
- 文档（4）：`r21-fixes.md`（本文，新）、`r20-fixes.md`（F5 更正）、
  dataagent-data / dataagent-contracts `README.md`（门禁前提）。
- 脚本：`scripts/verify_local.sh`（dev 前提检查）。
- 门禁工件：`evidence/round4/manifest.sha256` / `manifest-check.log`
  （202→203，r20→r21 轮换 + 新测试与新文档）、`packaging/bundle/`（重建）。
