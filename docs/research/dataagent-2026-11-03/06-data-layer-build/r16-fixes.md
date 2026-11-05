# Round 16 fixes — Reviewer r16 复评的 P1/P2 阻断项

对照本轮 Reviewer 独立复评报告（team 目录 `reviewer_r16_report.md`，评分 完成度 8.4 /
质量 6.4 / 综合 7.4，VERDICT FAIL）修复其 P1 阻断项（R1/R2，同属“语义改写被放行并
持久化”一类）与 P2 的 R6（宽捕获把内部故障归为 invalid_input）。契约、注册表、
CLI/MCP 入口、Catalog 均未改动。

## R1 — P1：片段豁免仍允许跨子句互换情态

Round 15 的情态序列校验只对“完整复述”生效；去掉一个外围内容 token（`Policy:`
标签或句尾 `promptly` 之类限定词）就把改写降级为“片段引用”而跳过校验，真实 MCP
返回 `ok / issues=[] / unresolved=[]` 并把互换后的文本落库，同一提案作为前置条件配
`facts={c1:true}` 还返回 `satisfied / unknowns=[]`。

### 修复（`runtime/anchors.py`）

- 新增 `_modal_scopes`：每个情态词按出现位置给出（类，其向前作用域内的内容 token
  集合），作用域截止于下一个情态词或句边界。
- 新增 `_unsupported_modal_scopes` / 检查：条件中每个带作用域内容的情态词，必须
  由锚点中**同类**情态词的作用域覆盖。片段引用因此只能带上自己那条子句的力：
  `Invoices may be filed`（引用许可子句）保持 `ok`，而 `Invoices must be filed`
  与 `Claims may be approved and invoices must be filed`（R1 探针）均
  `da02.anchor_value_mismatch`。
- 完整复述的情态序列校验（r15）与发明类校验（r14）保留；r12 片段省略情态的豁免
  （`not exceeding 5000 CNY` 引用 `should avoid exceeding 5000 CNY`）不受影响——
  该类片段不含情态词，作用域检查为空即通过。

## R2 — P1：比较对象、逻辑连接与条件方向未绑定到命题

三个改写均保持全部内容 token、情态作用域与连接词计数，全局界限集合也相同，真实
MCP 均 `ok` 并落库：

1. 比较对象互换：`Claims above 5000 CNY and invoices below 5000 CNY` ↔ 反向。
2. 蕴含方向反转：`If claims are approved then invoices may be filed.` ↔
   `Claims are approved if invoices may be filed.`
3. AND/OR 作用域互换：`Claims and invoices or receipts` ↔ `Claims or invoices
   and receipts`（计数各 1，顺序互换）。

### 修复（`runtime/anchors.py`）

- 新增 `_comparison_bindings` / `_comparison_subject_conflicts`：对每个比较短语
  取同子句内最近的前置内容 token 作为主语，条件对同一主语声称的 (方向, 数值)
  必须是锚点对该主语声称集合的子集。双主语共享阈值的方向互换因此被拒（全局集合
  相同不再能借力）；单主语方向互换仍由既有的全局界限校验拦截。主语缺失（数字
  开头形式、无主语引用）不参与绑定，交由全局校验。
- 新增 `_conditional_structure` / `_conditional_reversal`：`_is_pdf…` 类似的
  结构读取——英文 `if … then`、中文 `如果/若/一旦 … 那么/则/就`，取前件与后件的
  内容 token 集合；两侧均为条件句时前件必须一致（后件一致仅在两侧都有时校验）。
  反转（`B if A`、`If B then A`）拒绝；`If A, B`（逗号替代 then）、`B only if A`
  （逻辑等价，if 引导的仍是前件）保持接受。
- `_connective_signature` 由计数改为**有序序列**（and/or/和/与/或 按出现位置），
  捕获 AND/OR 作用域互换；同类中文互换（和↔与）不受影响。

## R6 — P2：宽捕获把内部执行错误归为 invalid_input

- `adapters/parsers/excel.py` `open_workbook`：仅已知文件/格式错误
  （`InvalidFileException`、`BadZipFile`、损坏 zip 结构的 `KeyError`、`OSError`）
  映射 `invalid_input`，其余（如注入的 `RuntimeError`）映射 `execution_unknown`。
- `ingestion/ocr.py` `ocr_pdf`：复用 `adapters/parsers/pdf.py` 的
  `is_pdf_input_error` 分类器（新增公开别名），仅 PDF 格式/加密错误归
  `invalid_input`；`parse_page_range` 的 `CapabilityError` 原样放行不再被重包装。

## 回归

新增 `tests/test_round16_reviewer_findings.py`（16 例）：R1 三个互换/借用变体 +
preconditions 路径 1 例（断言 `partial / unknown / unknowns=["c1"]`）、R2 四个
结构改写（比较对象互换、两种蕴含反转、AND/OR 作用域）、4 个必须存活的改写/
引用（片段保留自身情态、逗号条件句、单主语界限片段、逐字双主语界限）、R6 四例
（注入内部错误 → `execution_unknown`，损坏 xlsx/PDF → 仍 `invalid_input`）。

## 验证（本轮执行）

| 检查 | 命令 | 结果 |
|-|-|-|
| 数据层全量 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -o addopts="" -q` | **548 passed**（532 + 16 个 Round 16 用例） |
| 契约全量 | contracts 包同上 | **111 passed** |
| Schema / Catalog | `generate_schema.py --check` / `export_catalog_snapshot.py --check` | 66 files / 32 atoms |
| 全量门禁 | `PYTHONDONTWRITEBYTECODE=1 bash scripts/verify_local.sh` | `verify_local: OK`：contracts 111、data 548、schema 66、catalog 32、CLI 32、MCP 32、bundle 69、mint dry-run、manifest 194/194、隔离安装 32 工具 |
| Reviewer 探针复跑 | `reviewer_r16_probe.py` 副本（新临时目录） | R1/R2 六例全部 `needs_input / da02.anchor_value_mismatch` 且未持久化；precondition 变 `partial / unknown / unknowns=["c1"]`；verbatim 控制组与源身份回归不变 |

## 未修复（记录为限制）

- P2 R3：Mint 宿主加载（mint-core 从 bundle 拉起 MCP、审批行为）仍无实测证据，
  仅 dry-run + 隔离 wheel 安装；无模型凭据，保持未验证。
- P2 R4：可判定性 basis 充分性核验与 statement digest 自动失效未实现。
- P2 R5：抽取候选/文档切分的截断披露（truncated 而非 complete）未实现。
- P2/P3 R7/R8：SQLite 连接显式 close、lint/type 门禁、守门模块拆分（anchors.py
  本轮新增约 220 行，债务加深）、按领域组织测试矩阵，维持既有记录。
