# Round 15 fixes — Tester r15 复核的 P1 阻断项

对照本轮 Tester 复核报告（team 目录 `tester_r15_report.md`，评分 完成度 8.4 / 质量
6.4 / 综合 7.4，VERDICT FAIL）的 P1 阻断项修复。F1（伪造来源身份）在 r14 已关闭，
本轮只修 F2 的两个残余绕过。契约、注册表、CLI/MCP 入口、Catalog 均未改动。

## F2 — 情态守门的两个残余绕过（阻断，同根）

Round 14 的守门按情态类**全局计数**比较，两个改写都保持全部内容 token 与类直方图，
因此均被放行并持久化：

1. 跨子句情态互换（tester probe 7）：锚点同时含 must 与 may 时，
   “A must x and B may y” 改述为 “A may x and B must y” 后两类计数不变，
   `ok` 且持久化为互换后的条件。
2. 整句丢弃情态（tester probes 5–6）：“must be approved” 改述为 “are approved” /
   “will be approved”（“are/will” 是停用词，内容覆盖 100%），`ok` 且持久化；
   `define_rule_preconditions` 同样把 “Trip must be pre-approved” 放宽为
   “Trip is pre-approved” 返回 `satisfied / unknowns=[]`。

### 修复（`runtime/anchors.py`）

- 新增 `_modality_sequence`：按 token 出现顺序给出情态类序列。计数无法区分
  跨子句互换与合法改述——两者共享类直方图，但每个子句上的力相反；序列跟随
  token 次序，子句间的搬家必然改变序列。
- 新增 `_restates_anchor_clause`：以内容 token 判定条件是否**完整复述**锚点子句
  （完整复述 = 锚点内容 token 全部保留，只差停用词/情态词）；片段引用因按定义
  省略锚点内容而不受影响。
- `anchor_supports_text`：完整复述时要求条件的情态序列与锚点子句**逐项相同**，
  否则 `da02.anchor_value_mismatch`。该规则同时覆盖“跨子句搬家”（序列顺序变化）
  与“整体丢弃”（序列变短）；单句 must↔may 互换仍由第 14 轮的发明类检查拦截。
- 片段引用豁免保留并加注释：第 12 轮 “not exceeding 5000 CNY” 引用
  “should avoid exceeding 5000 CNY” 仍放行（片段省略锚点内容，情态随内容一起省略）。
- 同类等力互换（must↔shall）不受影响：同类互换序列不变。

### 修复后的行为（tester 探针复跑）

| 探针 | 修复前 | 修复后 |
|-|-|-|
| swap1/2/3（跨子句互换） | `ok`，持久化互换后条件 | `needs_input`，`da02.anchor_value_mismatch` + `da03.unanchored_condition`，未持久化 |
| drop1–5（丢弃 must/may/should） | `ok`，持久化 | `needs_input`，同上 |
| `define_rule_preconditions` “Trip is pre-approved” / “Trip pre-approved” | `satisfied / unknowns=[]` | `partial / verdict=unknown / unknowns=["c1"]` |
| r12 片段引用 “not exceeding 5000 CNY” | `ok` | `ok`（豁免保留） |
| must↔shall 同类互换 | `ok` | `ok` |

调用点 `semantics/metrics_rules.py` 与 `semantics/applicability.py` 走同一
`anchor_supports_text`，无需单独改动。

## 回归

新增 `tests/test_round15_tester_findings.py`（12 例）：3 个跨子句互换变体、5 个
丢弃情态变体、preconditions 路径 2 例（断言 `partial/unknown`）、片段引用豁免、
同类跨子句互换、多情态逐字引用各 1 例。

## 验证（本轮执行）

| 检查 | 命令 | 结果 |
|-|-|-|
| 数据层全量 | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -o addopts="" -q` | **532 passed**（520 + 12 个 Round 15 用例） |
| 契约全量 | contracts 包同上 | **111 passed** |
| Schema / Catalog | `generate_schema.py --check` / `export_catalog_snapshot.py --check` | 66 files / 32 atoms |
| 全量门禁 | `PYTHONDONTWRITEBYTECODE=1 bash scripts/verify_local.sh` | `verify_local: OK`：contracts 111、data 532、schema 66、catalog 32、CLI 32、MCP 32、bundle 69、mint dry-run、manifest 192/192、隔离安装 32 工具 |
| tester 探针复跑 | `tester_probe5.py` / `tester_probe6.py` / `tester_probe7.py` | 全部按上表转为拒绝/未知；F1 残余行为不变 |

## 未修复（记录为限制）

- P2：Mint 宿主加载（mint-core 从 bundle `.mcp.json` 拉起）仍只有 dry-run + 隔离
  wheel 安装，未实测（无模型凭据，`mint run --json` 401）。
- P3：量词加改（条件加 all/any 类量词仍 `ok`）、测试按轮次平铺命名、无 lint/type
  门禁、F7–F10，维持 Round 13/14 记录。
