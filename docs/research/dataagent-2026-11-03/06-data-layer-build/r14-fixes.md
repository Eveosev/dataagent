# Round 14 fixes — Tester r13 复核的两条阻断项

对照本轮 Tester 复核报告（team 目录 `tester_r13_report.md`，建议评分 完成度 8.4 /
质量 6.3 / 综合 7.3）的两个 P1 阻断项修复。契约、注册表、CLI/MCP 入口、Catalog 均未改动。

## F1 — 伪造 FileRef 信任边界（阻断）

- 问题：`read_file_ref` 只校验 `content_digest`，解析原子直接把调用方可控的
  `FileRef.id/revision` 抄进 `original_ref`。因此“B 的真实字节 + A 的摘要派生 id”
  可以伪造出“名为 A、实为 B”的来源绑定，抽取后 record 仍声称 A（tester probe 4）。
- 修复（`runtime/helpers.py`）：
  - `read_file_ref`：字节校验通过后，若 `id` 形如 `<kind>:<16位hex>`（摘要派生
    形态），其 hex 必须由**刚验证的字节**派生，否则 `invalid_input`。自由形态 id
    （如 `file:policy`）不受此限，保住 W3.2“revision 是调用方版本标签”的契约。
  - `register_file_ref`：来源身份不可变——已注册的 `(id, revision)` 不允许重新绑定
    到不同 `content_digest`，冒用已存在身份 → `invalid_input`。
- 边界（记录为 P3 限制）：自由形态 id 由先注册者拥有；若攻击者先以该名字注册 B
  字节，后续 A 会被拒绝（拒绝服务而非伪造，见 `tester_r15_probe5.log`）。

## F2 — 英文情态词互换（阻断）

- 问题：`must/shall/should/may/might/can/could` 在 `_STOPWORDS` 中，内容覆盖为
  100% 时 `anchor_supports_text` 不比较情态，`must be approved` ↔ `may be approved`
  均放行并持久化（tester probe 3）。
- 修复（`runtime/anchors.py`）：新增 `_MODAL_CLASSES`（强义务 must/shall、弱义务
  should、许可 may/might/can/could）、`_modality_signature`、`_invented_modality`；
  条件声明了锚点未陈述的情态类即拒绝。该规则同时覆盖所有单句互换方向
  （must→may 与 may→must 都是“发明锚点没有的情态”），并保留既有合法改写
  （第 12 轮 “not exceeding 5000 CNY” 引用 “should avoid exceeding 5000 CNY”，
  情态可随片段引用省略；must↔shall 同类等力互换）。

## 验证（本轮执行）

| 检查 | 命令 | 结果 |
|-|-|-|
| 数据层全量 | `pytest -p no:cacheprovider -o addopts="" -q` | **520 passed**（506 + 14 个 Round 14 用例，`tests/test_round14_tester_findings.py`） |
| 契约全量 | contracts 包 `pytest` | **111 passed** |
| Schema / Catalog | `generate_schema.py --check` / `export_catalog_snapshot.py --check` | 66 files / 32 atoms |
| 全量门禁 | `bash scripts/verify_local.sh` | `verify_local: OK`：CLI/MCP 各 32、bundle 69、mint dry-run、manifest 191/191 |
| tester probe 4 复跑 | `tester_probe4.py` | B 字节 + A 身份 → `failed / invalid_input`（探针按旧漏洞写断言，进程退出 1 为预期） |

## 未修复（记录为限制）

- F2 残余：跨子句情态互换、整句丢弃情态在第 15 轮 Tester 复核中仍可复现，见
  `r15-fixes.md`。
- 其余 P2/P3（F7–F10、量词 all/any 加改、Mint 宿主验收）维持 Round 13 记录。
