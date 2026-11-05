# Round 13 fixes — 独立评审 P1 阻断项

对照本轮独立评审报告（reviewer_report.md，评分 完成度 8.0 / 质量 5.5 / 综合 6.8）的
P1 阻断项 F1–F6 逐项修复。P2/P3 项（F7 可判定性 basis、F8 截断披露、F9 工程债、
F10 Mint 宿主验收）本轮未处理，见文末。

## F1 — DocumentRef 正文与原始来源绑定（阻断）

- 问题：`load_document_content` 只按调用方给的 `blocks_ref` 取 JSON。把 A 文档的
  `original_ref` 与 B 文档的 `blocks_ref` 拼在一起，锚点验证全部通过，抽取结果仍宣称
  来自 A。
- 修复：
  - 新增 `document_blocks_key` / `register_document_blocks`
    （`preparation/documents.py`）。三个解析原子（`parse_text_pdf`、`ocr_pdf`、
    `ocr_image`）产出 `DocumentRef` 时，把 `(source_ref, source_revision, blocks_ref)`
    三元组存入 `document_blocks` 版本库。
  - `load_document_content` 改为 fail-closed：找不到对应绑定记录即
    `invalid_input`，不再接受未绑定引用。键含 `blocks_ref`，同源不同 `pages` 参数的
    多次解析各自有绑定，互不覆盖。
  - 测试中手工构造的 `DocumentRef`（round7/round12、`test_maintain_anchors_detects_drift`
    的 revision-map 夹具）显式调用 `register_document_blocks` 注册。

## F2 — 规则语义守门（阻断）

比较界限、连接词、论元次序全部纳入 `anchor_supports_text`（`runtime/anchors.py`）：

- 包含性：`_comparison_analysis` 的界限从 `(direction, number)` 扩为
  `(direction, number, inclusive)`。`above 5000`（严格）与 `at least 5000`（含边界）
  现在冲突；否定/避免动词产生的界限按补集记为 inclusive（`不得超过5000` = ≤5000）。
  模式拆成 `_STRICT_COMPARISON_PATTERNS` 与 `_INCLUSIVE_COMPARISON_PATTERNS`，inclusive
  先扫描并 blank，防止 `no less than 5000` 同时读出严格 `< 5000`。
  `_comparison_bounds` 保持二元组投影，既有断言不变。
- 连接词：`_connective_signature` 比较 and/or/或 的计数，`and→or` 改述被拒。放在
  子串快速路径之后，精确引用不受影响。
- 论元次序：全 token 覆盖但乱序且无 dropped qualifier 时，要求条件 token 是锚点
  token 的有序子序列（`_is_ordered_subsequence`），`Managers approve employees` ↔
  `Employees approve managers` 被拒。

## F3 — 无锚点条件不得凭 facts 下结论（阻断）

- `define_rule_preconditions` 输入新增 `declared_facts: bool = False`。默认（fail-closed）
  无锚点条件进入 `unknowns`，无论是否带 `document_ref`；调用方显式声明
  `declared_facts=true` 才信任 caller 断言的 facts。
- 既有依赖旧行为的测试改为显式 opt-in，并新增默认 fail-closed 的回归用例。

## F4 — 指标/适用范围逐项校验（阻断）

- `define_rule_applicability`（DA03.16.1）：`scope_expression`、`object_types`、
  `scenarios` 逐项用新增的 `ungrounded_terms` 对照有效来源文本；未落实的词进入
  `draft.unknowns` 并出 `da03.scope_not_grounded` warning，整体 `partial`。不再出现
  “来源存在即 ok 且无 unknowns”。
- `define_metric_formula`（DA03.4.1）：`dimensions`/`filters` 字段名必须属于
  `available_fields`；`grain` 各分量必须是维度、字段、时间粒度或常用时间词；
  `unit` 必须被来源文本支持。未满足项进入 `draft.unresolved` 并出
  `da03.metric_unresolved`，整体 `partial`。
- 既有测试中不严谨的夹具同步修正（来源文本补 CNY/reimbursement、filter 绑定真实
  列名 `状态`、`document_anchor` 锚定整页）。

## F5 — 抽取值须符合目标字段 schema（阻断）

- `extract_fields_to_schema` 新增 `_target_schema_mismatch`：proposal 的
  `value_type`/`unit` 与目标 `FieldSpec` 不一致，或值本身不符合目标类型
  （数字/文本/布尔可本地验证），降为 `conflict`（`da02.field_type_mismatch`），
  value 置空、原值进 `alternatives`。`Alice:string/BTC` 不再能作为
  `amount:number/CNY` 成功抽取。

## F6 — 轨迹身份与原子性（阻断）

- F6a：`actor_ref` 写入 enriched payload（参与存储层的重复提交比对）；重放返回首次
  记录的 actor；不同 actor 重放同一 event_id 被存储层判 `version_conflict`，审计身份
  不可重述。
- F6b：`timestamp` 为 naive datetime 时在写入前 `invalid_input`，不再出现
  “先落库、输出校验才失败”的 `execution_unknown`，游标不前进。

## 验证

| 检查 | 命令 | 结果 |
|-|-|-|
| 数据层全量 | `pytest -p no:cacheprovider -o addopts="" -q` | **506 passed**（493 + 13 个 Round 13 用例，`tests/test_round13_reviewer_findings.py`） |
| 契约全量 | contracts 包 `pytest` | **111 passed** |
| Schema 门禁 | `scripts/generate_schema.py --check` | 66 files，exit 0 |
| Catalog 门禁 | `scripts/export_catalog_snapshot.py --check` | 32 atoms，exit 0 |
| CLI / MCP 计数 | `--list` / `tools/list` | 32 / 32 |
| Bundle | `scripts/build_bundle.py` | 69 files，0 `.pyc`，与包内源码逐文件一致 |
| 审计 manifest | `shasum -a 256 -c evidence/round4/manifest.sha256` | 190/190 OK（重哈希，含新增测试文件） |
| 评审探针复跑 | `reviewer_provenance.py` / `reviewer_probe.py` / `reviewer_followup.py` | F1 `failed/invalid_input`；F2 三例 `needs_input` 未持久化；F3 `unknown`；F4 `partial + unknowns/unresolved`；F5 `conflict`；F6a 重放返回首次 actor、换 actor `version_conflict`、F6b `invalid_input` 且游标不变 |

## 未修复（记录为限制）

- F7（P2）：DA03.15.1 basis 仍只判空、statement 缓存仍依赖调用方传入。
- F8（P2）：抽取候选/切分的截断披露仍未统一。
- F9（P2/P3）：错误映射宽捕获、SQLite 连接显式关闭、lint/type-check 门禁、长函数
  拆分、测试目录化仍未做。
- F10（P2）：mint 隔离安装 + mint-core 宿主加载验收仍未实测；`source-ref.toml` 的
  来源投影仍不完整。
