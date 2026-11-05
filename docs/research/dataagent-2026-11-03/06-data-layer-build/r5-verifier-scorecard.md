---
round: 5-verifier
date: 2026-11-04
subject: 对 06 建设方案与 dataagent 实现的独立评分（先盲评、后对照 r4-review）
score: 7.0/10
sub_scores: 完成度 9.0 / 代码质量（含正确性守门）6.5
baseline: 06-data-layer-build-plan.md v0.3；源码 mtime 2026-11-04 12:06–12:18；r4-review 14:20
---

# 独立评分：dataagent 数据层

范围：`packages/capabilities/dataagent-contracts`、`packages/capabilities/dataagent-data`。
方法：按方案 §1–§10 建验收点 → 在当前工作树重跑测试/入口/打包/缺陷 → 最后对照
[r4-review.md](r4-review.md) 与 [r5-independent-audit.md](r5-independent-audit.md)。
未改动任何源码或测试。

## 0. 结论

**7.0 / 10（可接受区间 6.9–7.1）；其中完成度 9.0，代码质量 6.5。**

- 不能给 8.1：那份评分的 D1–D7 全部落在接口与工艺，未把“数据正确性”单列。本实现
  在方案 §5 第 3 步、§10 第 2 条验收点上仍有 2 个 P0 与 2 个 P1 未修复，且都能在
  原子入口复现。
- 也不应低于 6.5：32 原子、36 类型、双入口、bundle、298 个用例、隔离 wheel 安装都是
  真实兑现的；旧评审的 6.5 主要输在正确性，完成度被低估。
- 与 6.8/7.0 的差异在权重。我把“数据正确性与锚点可信度”放到 35%，因为它正是这个
  数据层相对普通 CRUD 的不可替代价值。

## 1. 实测基线（2026-11-04 15:2x，本机）

| 项 | 实测 |
|-|-|
| 契约测试 | **111 passed** / 0.69s |
| 数据层测试 | **187 passed** / 3.47s；174 个 `test_` 函数、621 条断言、0 skip / 0 xfail |
| 原子 | `catalog-snapshot.json` **32**（骨干 9 / 判定 14 / 计算 9）；`export_catalog_snapshot.py --check` → OK |
| 类型 | 36 个 core 类型（34 具体 + 2 泛型）、66 个 schema；`generate_schema.py --check` → OK |
| 入口 | CLI 32、MCP `tools/list` 32；注解 8 只读 / 24 写 / 26 幂等 / 0 破坏性 |
| 打包 | bundle 69 文件；bundle 与源码 `diff -r` 0 差异；`mint publish --dry-run` exit 0 |
| 隔离安装 | 从 wheel 装入干净 venv，`initialize + tools/list` → 32 个工具 |
| 安全 | 绝对路径、`..`、符号链接越界均拒绝；`read_file_ref` 重算 sha256 后比对 |
| 证据 | `manifest.sha256` 当前 **182/184**；失败项是方案文档与 `uv.lock`（证据漂移，见 §5） |

## 2. 复现的缺陷

| # | 级 | 现象（原子入口实测） | 状态 |
|-|-|-|-|
| D1 | **P0** | 锚点 “Claims **above** 5000 CNY…” 下，提案 “claims **below** 5000 CNY” / “claims **less than** 5000 CNY” 均返回 `ok`、`kept=1`、`issues=[]` | r4-review #1 已记录，未修复 |
| D2 | **P0** | 同一锚点下，提案 “department head approval”（丢弃 5000 阈值）返回 `ok`、`issues=[]`；对照 “above 9000” 正确返回 `needs_input` + `da02.anchor_value_mismatch` | r4-fixes §6 已列为已知限制 |
| D3 | **P1** | 3 行工作表 `[["name","q1","q2"],["Alice",None,None],["Bob",1,2]]` 走 `detect_workbook_regions → recover_headers`，返回 `ok`、`header_rows=2`、列 `name / Alice`、行只剩 Bob、`ambiguities=[]`；稀疏首行被并入表头且无 issue | r4-review #3 已记录，未修复 |
| D4 | **P1** | 两个线程同带 `expected_revision=r1` 调 `register_extraction_schema_version`，两个都 `ok`（r2、r3）；`versions.save(expected_revision=)` 在存储层可用但 handler 未使用 | r4-review #10 已记录，未修复 |
| D5 | P2 | 32 个 MCP 工具的 `inputSchema` 都未把 `context` 列入 `required`（实测 32/32），严格按 schema 组装的客户端会漏传，到服务端才报 `invalid_input` | 本次新记录 |
| D6 | P2 | `define_business_rules` 准备阶段只取前 5 页、最多 40 条、正文截 300 字，且不返回 `truncated` issue；长制度 PDF 的后半部分对 Agent 不可见 | 本次新记录 |
| D7 | P2 | `find_file_ref` 固定读 `"r1"`；但 `object_id` 是 `id@revision`，正常路径不会产生 r2，属脆弱写法而非现行 bug | r4-review §2 已记录 |
| D8 | P2 | 字符串字段值用子串匹配：`anchor_value_mismatch("Acme Inc. total 200", "Acm") == ""`，截断值会被当作有据 | r4-review #1 已记录 |

### 复现片段（节选）

```text
claims above 5000 CNY              => ('ok', 1, [])
claims below 5000 CNY              => ('ok', 1, [])          # D1
claims less than 5000 CNY          => ('ok', 1, [])          # D1
department head approval           => ('ok', 1, [])          # D2
claims above 9000 CNY              => ('needs_input', 0, ['da02.anchor_value_mismatch', ...])
header_rows 2 / columns ['name / Alice', 'q1', 'q2'] / rows [['Bob', 1, 2]]   # D3
seed r1 -> ('note-0','ok','r3'), ('note-1','ok','r2')        # D4
```

D1/D2 的根因在 `runtime/anchors.py`：`above/below/less/more/least` 被放进 `_STOPWORDS`，
方向词不参与覆盖判断；同时 `anchor_supports_text` 的归一化子串快路径在数字检查之前
`return ""`，绕过了“不得丢弃锚点数字”的保护。

## 3. 计划符合度

| 方案条目 | 结论 |
|-|-|
| §3 两个包、模块分层 | 基本一致；`tests/{contracts,ingestion,...}` 7 个子目录未落实，实际为扁平 `tests/*.py`（r1 §4 未记录此偏差） |
| §4.1 快照与注册表 | 一致且强于方案：`source_file` 由 `__module__` 推导，启动时双向比对；`--check` 通过 |
| §4.2 MCP | 协议、32 工具、`_meta`/`arguments.context`、`isError` 均实现；`context` 未进 `required`（D5） |
| §4.3 CLI | 32 操作；`failed`→1、用法错→2；不装配为 command 组件，符合方案 |
| §5 两段式 | 6 个两段式原子均按“先 `needs_input`、再校验 proposal”实现；但 D1/D2 使“无依据值必须降级”未完全成立 |
| §6 存储/轨迹 | 内容寻址、SQLite revision、`BEGIN IMMEDIATE`、`event_id` 去重、checkpoint digest 均在；handler 层 CAS 有洞（D4） |
| §7 依赖 | pydantic/openpyxl/pdfplumber，OCR 可选；全仓无网络调用 |
| §8 Mint | `mint.toml`、`.mcp.json`、69 文件 bundle、vendoring、`source-ref.toml` 三 hash 齐全；dry-run 通过 |
| §10 验证 | 单测/场景/入口黑盒均通过；`mint install`、`mint run --json` 未验证（与 r4-fixes §6 一致） |

方案记录偏差 7 条（r1 §4），另有“测试目录扁平”1 条未记录。

## 4. 代码质量

**做得好的：**

- 分层清楚：runtime / ports / adapters / ingestion / preparation / semantics / memory / interfaces，
  依赖方向正确；契约包有 `test_dependency.py` 防止反向依赖。
- 注册表防漂移是机制而非约定：operation 名即函数名，`source_file` 从模块推导，启动时
  与快照双向比对，缺失/多余/id 不一致/路径不符都报错。
- 安全链路完整：`workspace_path` 先拒绝绝对路径与 `..`，再 `resolve` 后做包含判断；
  `read_file_ref` 重算摘要，不符抛 `source_changed`。
- 测试使用真实样本（合并单元格、1904 日期、多行表头、合计行），断言落到具体单元格
  与角色；32 个原子全部被测试引用。
- 错误映射与两段式协议统一，`Issue` 带 `suggested_action` / `inference_request`，
  文档注释普遍解释“为什么”而不只是“做什么”。

**扣分项：**

- 长函数：**22 个 >60 行，7 个 >100 行**。`define_business_rules` 239 行，内嵌
  “前 5 页 / 40 条 / 300 字”的启发式；`_evaluate_field` 161、`segment_document` 151、
  `extract_irregular_excel` 137。
- 魔法数：`1_000_000`、`timeout=10`、`[:12]/[:16]/[:40]` 等（r4-review 统计 31 处），部分不进配置也不进文档。
- 宽口径异常：全仓 21 处 `except Exception`，其中 `anchors.py` 10 处；注释都给了理由，
  但连续吞掉会让索引结构错误伪装成“锚点未解析”。
- 死代码/重复：`PACKAGE_ROOT`、`helpers.store_json` 无引用；`_read_primary` 与
  `read_from` 逻辑重复；`_materialize` 与 `AnchorResolver._workbook` 两套临时文件逻辑。
- 测试工程：扁平目录、硬编码计数（21/24/18）、用 `inspect.getsource` 扫 handler 而不追踪
  helper；未接 coverage，9,261 行源码无法量化覆盖。
- 类型：约 30 个 handler 的 `runtime` 参数无注解，`Runtime.inference` / `ocr_engine` 为 `Any`。

## 5. 评分（权重开审前冻结）

| 维度 | 权重 | 分 | 主要依据 |
|-|-|-|-|
| 能力覆盖与计划符合度 | 20% | 9.0 | 32/32 原子、36 类型、双入口、bundle 全兑现；扣测试目录、InferencePort 占位、mint 宿主未验证 |
| 数据正确性与锚点可信度 | 35% | 5.5 | D1–D4 四个开放缺陷；但数字错配、否定极性、前缀扩展等能正确拒绝，不是全坏 |
| 代码质量与可维护性 | 15% | 6.5 | 分层与防漂移优秀；长函数、魔数、死代码、宽异常拉低 |
| 测试与验收 | 10% | 8.0 | 298 用例、621 断言、真实夹具、负例充分；缺方向反转/CAS 用例、无覆盖率 |
| 契约包 | 8% | 8.5 | 36 类型、枚举封闭、schema/examples 校验；#6/#8 各余一处小约束 |
| 运行时与存储 | 7% | 6.5 | `BEGIN IMMEDIATE`、revision、去重、checkpoint 正确；handler CAS 有洞 |
| 打包与可复现证据 | 5% | 7.0 | dry-run、隔离 wheel、source-ref 齐全；manifest 182/184、`uv.lock` 三处不一致 |

加权：`9.0×.20 + 5.5×.35 + 6.5×.15 + 8.0×.10 + 8.5×.08 + 6.5×.07 + 7.0×.05 = 6.985` → **7.0**。

完成度单列 9.0；代码质量（含正确性守门）6.5。若只看“是否把方案写成了可运行系统”，
这是 9 分档；若看“能否放心把带锚点的规则/表格交给下游”，当前仍是 6.5 档。

## 6. 与其它评分的对照

- **8.1 分**：事实基本准确（32 原子、24 写、schema 缺 `context`、长函数），但把
  “计划符合度”给到 9.0，而 §5 第 3 步“没有依据的值降为 missing/conflict”恰好被
  D1 违反；D1–D7 没有一条覆盖数据正确性。另外“8 处偏差”实为 7 条有记录；“20 个
  >60 行函数”实测 22 个。
- **6.8 分**：复现结果与我一致。三处可下调：`find_file_ref` 写死 r1 没有现行触发路径
  （对象 id 已含 revision），不宜按 P1；`read_by_kernel_session` 未被任何原子暴露，
  属端口层隐患；宽泛 except 在 `anchors.py` 实为 10 处、全仓 21 处（不是 6 处），
  且都有注释。
- **r4-review 6.5**：D1–D4 全部可复现，评分可信；但它把完成度与正确性混在一个分里，
  没有单独体现“32/32 + 双入口 + 打包”的交付量。

## 7. 若要进入 8 分档

1. 方向词（above/below/less/more/least/以上/以下）移出停用词表并做方向核对；删除
   `anchor_supports_text` 的子串快路径，或把它放到数字/方向检查之后。
2. `_detect_header_rows` 在 `header_rows>1` 且首行含稀疏/文本单元格时给出 `ambiguity`
   或 issue；补 “Alice/None/None” 与 “Alice/N/A” 反例。
3. `register_extraction_schema_version` 改为 `versions.save(..., expected_revision=)`，
   把“读当前 + 写”放进同一事务；补双线程/双进程验收。
4. MCP `inputSchema.required` 追加 `context`；两段式截断返回 `truncated` issue。
5. 接 coverage；拆 100 行以上函数；把 5 页/40 条/300 字等常量提为配置并写进 README。

## 8. 关键命令（均可重跑）

```bash
cd packages/capabilities/dataagent-contracts && uv run --frozen pytest
cd ../dataagent-data && uv run --frozen pytest
cd ../dataagent-contracts && uv run --frozen python scripts/generate_schema.py --check
cd ../dataagent-data && uv run --frozen python scripts/export_catalog_snapshot.py --check
cd /Users/payne/Vibe/AgentOS && shasum -a 256 -c \
  packages/capabilities/dataagent-data/evidence/round4/manifest.sha256 | tail -3
# 缺陷复现：/tmp/repro_rules.py、/tmp/repro_header_atom.py、/tmp/repro_concurrency.py
```

## 9. 变更

- 新增本文件；未改任何源码、测试、锁文件或证据日志。
