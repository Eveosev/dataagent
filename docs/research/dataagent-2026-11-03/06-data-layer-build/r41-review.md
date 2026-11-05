---
round: 41
date: 2026-11-05
subject: dataagent-data 与 dataagent-contracts（契约 core）的完成度与质量评审
kernel: agent-kernel@c1231ab（本地 HEAD，未 fetch；source-ref 与 05 记为 f0fa521，HEAD 领先 168 个提交，期间 iface 只追加）
tests: contracts 117 passed；data 649 passed，1 warning
---

# Round 41 评审：数据层与契约 core

范围：`packages/capabilities/dataagent-data`、`packages/capabilities/dataagent-contracts`。跨包共性问题（宿主权威、复检 fail-open、约束不执行、外发检查）记在 [08 r41-review.md](../08-governance-layer-build/r41-review.md) §1，本文用 X1–X5 引用。

| 项 | 结果 |
|-|-|
| 规模 | data src 44 文件 / 10,586 行，tests 39 文件 / 11,124 行；contracts src 12 文件 / 1,586 行，tests 1,572 行 |
| 测试 | `.venv/bin/python -m pytest -p no:cacheprovider -o addopts=''`：data 649 passed，1 warning；contracts 117 passed |
| 注册与入口 | `registry_errors()` 为空；MCP `tools/list` 与 CLI `--list` 各 32 项 |
| 快照 | `export_catalog_snapshot.py --check` OK；快照 sha `072d61…`，Catalog sha `fbd48e…`，与 `source-ref.toml` 一致 |
| bundle | `build_bundle.py --out <tmp> --no-lock` 与 `packaging/bundle` 无差异（85 文件，0 pyc）；临时副本 `mint publish --dry-run`（mint 0.1.26）通过 |
| 审计 manifest | `shasum -c` 207 项 OK |
| schema | `generate_schema.py --out <tmp>` 与 `schema/` 逐字节一致；68 个 schema + index |

结论：32 项全部注册可调用，r19–r21 的修复均在代码中；enforce 下的访问复检有三条可复现的绕过路径，判定族下游三项信任调用方输入。S0 记为 22 项已完成、10 项部分完成。

## 1. 既有记录落实情况

| 来源 | 项 | 状态 | 证据 |
|-|-|-|-|
| r19 | F1–F4 适用范围语义放行 | 已修复 | `applicability.py:202` `semantic_divergence`；比较绑定带 inclusive；`_guard_is_dropped` 先于快路径 |
| r20 | N1/N2 指标校验绕过；N3/N4 片段标点与引号 | 已修复 | `anchors.py:37`、`:2041` `_SENTENCE_FINAL_MARKS`；无 schema 时同样执行谓词校验 |
| r21 | F1–F4 引号字符串逗号、按谓词核对、`SqliteDatabase.session()` | 已修复 | `metrics_rules.py` `_normalize_filter_value` 三形态；`session()` 16 处；`verify_local.sh` dev 前提检查 |
| r21 | §10.2 两条场景 | 已修复 | `test_scenarios.py:189`、`:323` |
| r19 F5 / r20 N6 / r21 | source-ref 实现 commit、内容归档到制品 digest 的映射 | 未修复 | 三轮均标为移交 |
| r19 P3 | `anchors.py`（2,360 行）重构阈值；lint 与类型门 | 未修复 | 无 lint / type 配置 |
| r21 N5 | Tester 独立跑完整链并核对落库值 | 未修复 | — |
| 方案 §10.4 | 隔离 `MINT_HOME` 安装、mint-core 加载 `.mcp.json`、`mint run --json` | 未修复 | `evidence/round4/isolated-install.log:56` 记为 not verified，自 r3 起未证 |
| 方案 §12 | r19–r21 登记 | 已修复（本轮补登） | §12 索引表 |

## 2. S0 完成度

测试引用列为 tests 中引用该 operation 的文件数 / 调用次数。

| 原子 | operation | 状态 | 源码 | 测试引用 | 说明 |
|-|-|-|-|-|-|
| DA01.4.1 | `parse_regular_excel` | 已完成 | `ingestion/files.py` | 9 / 17 | |
| DA01.4.2 | `extract_irregular_excel` | 已完成 | `ingestion/files.py` | 6 / 10 | 含 1904 组合链 |
| DA01.4.3 | `parse_delimited_file` | 已完成 | `ingestion/files.py` | 9 / 27 | |
| DA01.4.4 | `parse_json_records` | 已完成 | `ingestion/files.py` | 7 / 13 | |
| DA01.4.5 | `parse_text_pdf` | 已完成 | `ingestion/files.py` | 23 / 52 | |
| DA01.4.6 | `inspect_workbook_calc_state` | 部分完成 | `ingestion/files.py` | 5 / 6 | `workbook_ref` 入口绕过复检（D1） |
| DA01.5.1 | `ocr_pdf` | 部分完成 | `ingestion/ocr.py` | 5 / 9 | 只测桩引擎；`.venv` 未装 rapidocr，`adapters/ocr/engine.py` 未执行 |
| DA01.5.2 | `ocr_image` | 部分完成 | `ingestion/ocr.py` | — | 同上 |
| DA02.1.1 | `detect_workbook_regions` | 部分完成 | `preparation/regions.py` | 4 / 5 | `workbook_ref` 绕过复检（D1） |
| DA02.2.1 | `recover_headers` | 部分完成 | `preparation/structure.py` | 4 / 4 | `region` 入口绕过复检（D1） |
| DA02.2.2 | `expand_merged_cells` | 已完成 | `preparation/structure.py` | 6 / 8 | |
| DA02.2.3 | `classify_table_rows` | 已完成 | `preparation/structure.py` | 4 / 5 | |
| DA02.4.1 | `profile_table_structure` | 已完成 | `preparation/profiles.py` | 5 / 11 | 输入 `schema_ref` 未使用 |
| DA02.4.3 | `infer_field_types` | 已完成 | `preparation/profiles.py` | 5 / 8 | |
| DA02.8.1 | `segment_document` | 已完成 | `preparation/documents.py` | 8 / 15 | |
| DA02.8.2 | `maintain_source_anchors` | 已完成 | `preparation/documents.py` | 4 / 6 | |
| DA02.12.1 | `extract_fields_to_schema` | 已完成 | `preparation/extraction.py` | 10 / 21 | |
| DA02.12.3 | `anchor_extracted_values` | 已完成 | `preparation/extraction.py` | 6 / 8 | |
| DA02.12.4 | `register_extraction_schema_version` | 已完成 | `preparation/extraction.py` | 5 / 11 | |
| DA03.4.1 | `define_metric_formula` | 部分完成 | `semantics/metrics_rules.py` | 10 / 17 | 谓词校验缺陷（D5） |
| DA03.4.3 | `define_business_rules` | 已完成 | `semantics/metrics_rules.py` | 16 / 29 | |
| DA03.15.1 | `assess_automatic_decidability` | 已完成 | `semantics/decidability.py` | 7 / 12 | |
| DA03.15.2 | `identify_evidence_or_human_gaps` | 部分完成 | `semantics/decidability.py` | 4 / 6 | 信任调用方 Assessment（D4） |
| DA03.15.3 | `mark_automation_coverage` | 部分完成 | `semantics/decidability.py` | 4 / 5 | 同上 |
| DA03.15.4 | `resolve_decidability_cache` | 部分完成 | `semantics/decidability.py` | 5 / 9 | 同上 |
| DA03.16.1 | `define_rule_applicability` | 已完成 | `semantics/applicability.py` | 6 / 8 | |
| DA03.16.2 | `define_rule_preconditions` | 已完成 | `semantics/applicability.py` | 9 / 18 | |
| DA03.16.3 | `normalize_precondition_references` | 已完成 | `semantics/applicability.py` | 3 / 5 | 输出 `conflicts` 恒为 `[]`（`applicability.py:548`） |
| DA03.16.4 | `resolve_unknown_applicability` | 已完成 | `semantics/applicability.py` | 3 / 4 | |
| DA04.1.1 | `append_task_event` | 已完成 | `memory/traces.py` | 11 / 20 | enforce 下接受伪造授权（X2） |
| DA04.1.2 | `append_invocation_record` | 已完成 | `memory/traces.py` | 4 / 4 | |
| DA04.1.3 | `append_user_correction` | 已完成 | `memory/traces.py` | 5 / 7 | |

其它交付物：

| 交付物 | 状态 | 证据 |
|-|-|-|
| 契约 core | 已完成，含新缺陷 | §4 |
| 注册表与 Catalog 快照校验 | 已完成 | 见文首表 |
| Mint bundle、`.mcp.json`（注入 enforce）、`mint.toml` | 已完成 | `.mcp.json` 未注入 `DATAAGENT_HOST_*`（X1） |
| Skills（judgment / compute） | 已完成 | `skills/*/SKILL.md` |
| `verify_local.sh` | 已完成，本轮未运行 | 会重写 `packaging/bundle` 与证据日志；最近日志 2026-11-04T22:18Z，649 / 117 OK |
| 外发检查接入 | 未开始 | `src` 中 egress 引用 0 处，`inference_request` 6 处均不经外发检查（X4） |
| 附录 A 内核事件接口 | 仅提案 | 轨迹仍为本地 SQLite |

## 3. 新缺陷：dataagent-data

| # | 严重度 | 确认/疑似 | 位置 | 问题 | 复现 |
|-|-|-|-|-|-|
| D1 | 高 | 确认 | `ingestion/files.py:717`、`:722`；`preparation/regions.py:148`、`:153-158`；`preparation/structure.py:245`、`:250-257`；`dataagent-runtime/.../invoke.py:73-87` | `resource_fields` 只登记 `file_ref` / `table_ref`；`workbook_ref.file_ref`、`region.workbook_ref.file_ref` 两条路径读文件不经复检；`_to_versioned_ref` 不识别 WorkbookRef / TableRegion | `repro_bypass.py`：决策只覆盖 orders.csv；`inspect_workbook_calc_state{file_ref: secret.xlsx}` → `da12.access_denied`；改为 `{workbook_ref:{file_ref: secret}}` → ok；`detect_workbook_regions` → ok；返回的 region 交 `recover_headers` → ok，columns `["name","salary"]` |
| D2 | 高 | 确认 | `helpers.py:159-177`；`dataagent-runtime/.../invoke.py:262-271` | revision 非 digest 形态时 runtime 跳过闭包校验；handler 只在 `(id, revision)` 已登记时比对字节，新造 revision 永远未登记 | `repro_label.py`：决策 `file:report@*`，传 `{id:"file:report", revision:"rev:evil", locator:"secret.csv"}` → ok，读出 `[['alice','99999']]`；子树 `file:report/x` 同样可读 |
| D3 | 中 | 确认 | `runtime.py:43-79`；`dataagent-runtime/.../enforcement.py:152`；`mcp_server.py:77-86` | 数据层 `create` 不读 `DATAAGENT_HOST_SUBJECT_REF` / `HOST_PURPOSE`；`arguments.context` 优先于 `_meta`；`subject_ref` 为空时跳过主体比对（X1 在数据层的表现） | `repro_subject.py`：真实 MCP 子进程，enforce，env `HOST_SUBJECT_REF=user:alice`、`HOST_PURPOSE=audit`；context 传 mallory → 拒；省略 `subject_ref` → ok，宿主 purpose 被忽略 |
| D4 | 中 | 确认 | `semantics/decidability.py:254`、`:317-325`、`:376-382`、`:408` | DA03.15.2/3/4 不复核 15.1 的降级规则（auto 须有可解析 basis 且无 unknowns），也不核对 Assessment 是否已落库 | `repro_decid.py`：伪造 `{verdict:auto, basis_refs:["evidence:fabricated"], unknowns:["invoice number missing"]}`；`mark_automation_coverage` covered=1；`identify_evidence_or_human_gaps` gaps=0；`resolve_decidability_cache` prior=`a@r1`、current=`a@r2`、调用方传 `previous_dependencies=a@r2` → hit=True；不传 statement 也 hit=True |
| D5 | 中 | 确认 | `semantics/metrics_rules.py:146`、`:209`、`:434` | `_source_predicates` 只收集 `field op value`，丢弃 or / except / not；等式型公式文本被当作过滤约束 | `probes/test_probe_metrics.py`：来源 `status = 'paid' or status = 'settled'`、提案两条合取 filter → ok；来源 `all claims except status = 'paid'`、提案 `status = 'paid'` → ok；来源 `net = gross minus refunds`、`filters=[]` → partial，误报 drops `net = 'gross'` |
| D6 | 中 | 确认 | `adapters/storage/sqlite.py:470-496` | `verify_checkpoint` 比对整个流的 cursor 与 digest，合法追加后返回 False，与篡改不可区分；内部调用 `checkpoint()` 写入新行；返回 bool，不是 StoreContract 要求的 `(cursor, digest)` 或错误 | `repro_ckpt.py`：追加 e2 后 verify=False；篡改 e1 后 False；每次 verify 新增一行检查点 |
| D7 | 低 | 确认 | `dataagent-runtime/.../enforcement.py:69-72` | 无法识别的 `DATAAGENT_ENFORCEMENT_MODE`（如 `enforcing`）静默回落 warn，无日志 | 设该值后 `create().enforcement.mode == "warn"` |
| D8 | 低 | 疑似 | `anchors.py:104-125` | `define_metric_formula` / `define_rule_applicability` 只给 `sources` 不给 `document_ref` 时，锚点经 `find_file_ref` 直接读工作区文件；`resource_fields` 只登记 `document_ref`。泄露面限于锚点有效性判定 | 读代码 |
| D9 | 低 | 确认 | `06-data-layer-build-plan.md` frontmatter；`r19-fixes.md` | frontmatter 记 560 测试，实测 649；无 r18 记录；r19 记 bundle 69 文件，`EXPECTED_BUNDLE_FILES=85` | 读文件 |

测试 warning：`tests/test_enforcement_gate.py:62-70`、`:175` 用 `model_copy(update={"valid_until": "2020-…Z"})` 写入字符串；`model_copy(update=)` 不校验，序列化时报 `PydanticSerializationUnexpectedValue`。契约字段定义为 `AwareDatetime`，无误；同一对象不经存储直接交 `access_recheck` 时在 `enforcement.py:143` 抛 `TypeError`（见 C4）。

## 4. 契约 core：dataagent-contracts

### 4.1 完成度

| 项 | 状态 | 证据 |
|-|-|-|
| S0 类型与字段（05 §3.3.1–3.3.7） | 已完成 | `_types.py:10-80`：35 具体 + 2 泛型 + 18 内嵌结构，字段逐表一致；新增字段 `CallContext.subject_ref/purpose`（`envelope.py:52-53`）未登记进 05 §3.3.1 |
| 枚举（05 §3.4） | 已完成 | `vocab.py` 13 个，取值一致；3 个开放枚举经 `_missing_` 接受点分命名空间值 |
| schema 由代码生成且与仓库一致 | 已完成 | 68 schema + index；05 §6 写 66，已过时 |
| schema 与模型等价 | 部分完成 | C1、C2 |
| 准入规则（`extra=forbid`、扩展键带命名空间） | 部分完成 | `_base.py:21-43` 模型侧已实现；schema 不校验扩展键命名空间 |
| 版本与兼容（05 §2.3、§7） | 部分完成 | `$id` 含 `0.1`（`generate_schema.py:74`）；只增不改检查、CI 兼容检查、依赖方版本范围未实现（C7） |
| `LifecycleStatus` 统一 | 部分完成 | core 一份枚举；层内仍用 `Literal`：`dataagent-data/.../contracts/layer.py:126`、`:173`，`dataagent-governance/.../contracts/acceptance.py:68`；schema 不表达子集 |
| S1/S2 预留 | 未开始（按计划） | 无 `action/`、`delivery/` |
| 文档自洽 | 部分完成 | 05 §3.2 记 `ExecutableSpec` 已迁入 core，§3.3.4 末尾与 §3.6 仍写为应用层类型 |

### 4.2 新缺陷

| # | 严重度 | 确认/疑似 | 位置 | 问题 | 复现 |
|-|-|-|-|-|-|
| C1 | 高 | 确认 | `scripts/generate_schema.py:84-94`；`tests/test_round4_contracts.py:168-173` | 开放枚举只在独立文件生成 `anyOf`+pattern；组合类型 `$defs` 中 `Aggregation`、`EvidenceType`、`TraceEventType` 仍为封闭 `enum`；MCP `tools/list` 的 `model_json_schema(mode="validation")` 同样封闭；测试只查独立文件 | `contracts/schema_vs_model.py`：`MetricDefinition.aggregation="acme.weighted_mean"`、`EvidenceRef.evidence_type="acme.foo"`、`TraceEventRef.event_type="acme.foo"`：模型接受、schema 拒绝 |
| C2 | 中 | 确认 | `generate_schema.py:80-116` | schema 只导出 pydantic 默认结构，不含校验器约束：扩展键命名空间、`Issue.code` pattern、`failed` 须带 issue、`inline_rows`≤500、bbox 顺序、active `CriteriaRef` 须有 `confirmation_ref`、`counts` 非负、`SemanticDraft.status` 子集均不表达；时间只有 `format: date-time` | 同上脚本，上述用例均为 model=reject、schema=accept；`deadline="not-a-date"` 加 FormatChecker 仍被接受 |
| C3 | 中 | 确认 | `core/_base.py:21`；`governance.py:31`；`envelope.py:58` | 模型非 strict：`AwareDatetime` 接受整数时间戳（`valid_until=0`、`1893456000`），与 05 §2.4 “RFC 3339 带时区”不符；`Issue.retryable="yes"` 转 True；`DataBatchRef.row_count="5"`、`5.0` 被接受 | `contracts/contract_probe2.py` “lax coercion” 段 |
| C4 | 低 | 确认 | `governance.py:31`；全部模型无 `validate_assignment` / `frozen` | `model_copy(update=)` 与直接赋值不校验：`d.valid_until="garbage"` 成功；未经存储往返的对象交 `access_recheck` 抛 `TypeError: '>' not supported between datetime and str`（`enforcement.py:143`） | `contracts/contract_probe2.py` 第一段 |
| C5 | 中 | 确认 | `semantics.py:60`、`:70` | `RuleDefinition.combination` 中以 `all`/`any`/`not` 开头的 token 一律跳过，`anything_else`、`nothing_here`、`notary` 等未知 id 通过；`combination=""` 配非空 conditions 被接受 | `combination="c1 and anything_else"` → 接受；`"c1 and zzz"` → 拒绝 |
| C6 | 低 | 确认 | `semantics.py:131-139`、`:241-246` | `kind ∈ {entity, relationship, dimension}` 搭配 RuleDefinition / MetricDefinition 通过；`ExecutableSpec` docstring 称拒绝封闭算子集外的 op，实际只校验 `op` 为字符串 | `kind=entity` 配 RuleDefinition → 接受；`{"op":"os.system"}` → 接受 |
| C7 | 中 | 确认 | `pyproject.toml:7`；`generate_schema.py:127`；`dataagent-runtime/pyproject.toml:13` | 0.1.x 期间追加 6 个以上字段，包版本、`index.json`、`$id` 仍为 `0.1.0` / `0.1`，同一版本号对应多份 schema digest；`--check` 只查与已提交文件的漂移；依赖方未声明版本范围 | 读文件 |
| C8 | 低 | 确认 | `vocab.py:120-145` | 开放枚举合成成员缓存上限 128，淘汰后重建为新对象，`==` 为 True、`is` 为 False；现有代码只对内置成员用 `is` | 创建 `TraceEventType("acme.e0")` 后再建 129 个值，再取 `acme.e0` |

## 5. 测试覆盖缺口

- 复检门测试（`test_enforcement_gate.py`，26 例）只覆盖 `file_ref`、`table_ref`、`profile_ref`、`document_ref`；缺按 22 个声明 `resource_fields` 的原子遍历全部入口字段、label revision、省略 subject、宿主 env 注入。
- DA03.15.2/3/4、DA03.16.3/16.4 各 3–4 个文件引用，无伪造或不一致 Assessment 的对抗输入。
- 指标谓词测试只覆盖 r19–r21 的反例族（值、运算符、引号、千分位），无 OR、否定、except、公式等号。
- 轨迹检查点无“追加后仍通过 / 篡改报错”的区分测试；现有测试把追加后返回 False 固化为正确行为。
- OCR 只测桩引擎；MCP 子进程 `tools/call` 5 例；mint-core 实装加载未验证。
- r20/r21 回归只回放 proposal 阶段；真实两段式加 SQLite 落库只有 r21 F1 一例持久化断言与 2 条场景链。
- contracts 无“模型拒绝则 schema 也拒绝”的反向等价测试；无宽松转换、`model_copy`/赋值绕过、combination 前缀绕过的测试；`jsonschema` 仅在 dev 组，相关测试用 `importorskip`，未安装时静默跳过。

## 6. 复现

脚本在 [r41-repro/](r41-repro/)：`data/` 对应 D1–D6（`repro_bypass.py`、`repro_label.py`、`repro_subject.py`、`repro_decid.py`、`repro_ckpt.py`、`probes/test_probe_metrics.py`；`probe_parsers.py` 为解析器边界探针，结果正常），`contracts/` 对应 C1–C4（`schema_vs_model.py`、`contract_probe2.py`、`cp3.py`、`cp4.py`）。

脚本按原工作目录编写，临时目录写死为 `/tmp/claude-502/data`，部分脚本含本机绝对路径。运行：

```bash
mkdir -p /tmp/claude-502/data && cp -R docs/research/dataagent-2026-11-03/06-data-layer-build/r41-repro/data/. /tmp/claude-502/data/
cd packages/capabilities/dataagent-data && .venv/bin/python /tmp/claude-502/data/repro_bypass.py
```

contracts 脚本用 `packages/capabilities/dataagent-contracts/.venv/bin/python` 运行。
