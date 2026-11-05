---
round: 4（含 4.1–4.3）
date: 2026-11-04
trigger: Round 3 评审（r3-review.md）17 个问题
tests: contracts 111 / data 187
evidence: packages/capabilities/dataagent-data/evidence/round4/
---

# Round 4 修复

## 1. 计划

按顺序执行；每项完成以“新增反例测试通过 + 原有测试不回退”为准。

| 序 | 范围 | 修复 | 验收 |
|-|-|-|-|
| 1 | 锚点（#1、#2、#5） | 所有选择器回原文取值核对：`text_span` 按文档单元正文、`json_pointer` 按 RFC 6901 解析原记录、`excel_cell` 按单元格值、`record_key` 按行键；`value=None` 不得为 `extracted`；`sources`、规则条件、exception 均须有可核对锚点；`anchor_extracted_values` 校验 `document_ref`、`source_ref`、`source_revision` 一致，数值重定位按整词边界且排除日期；`pdf_bbox` 按页码取页；行定位失败报 issue，不退回游标 | 编造值配四种选择器均降为 `missing`/`conflict`；跨文档记录被拒；`pages` 子集加 bbox 正常；`2024-05-01` 不匹配 `-5` |
| 2 | 表结构（#3、#4） | 表头判断改为“连续非数据行且下一行为数据行”，并设上限；合并表头沿合并区向下展开上级名称；空行删除前记录原始行号映射，合并区按原始坐标换算；`formula_text` 不报缺缓存，`cached_values` 缺缓存记为 `missing` 并给 issue | 纯文本表、两行无空格表头、合并表头、表内空行、两种公式策略各有用例 |
| 3 | 契约包（#6、#7、#8） | 命名空间统一为点分（`<ns>.<name>`），校验 `extensions` 键与非标准 `Issue.code`；开放枚举在 schema 中导出为 `anyOf[enum, pattern]`，缓存设上限；去掉 05 中必填字段的默认值；补 `failed` 必须有 issue、`extracted` 必须有值、`AcceptanceReport` 校验辅助函数（判据 `active`、样本冻结且只用 `unseen_acceptance`）；时间改 `AwareDatetime`；schema 加 `$id`（`dataagent-contracts/0.1/core/<Type>`）；`VersionedRef` 解析与 pattern 一致 | 05 §6 七项验收逐条有测试；示例用生成的 JSON Schema 校验（加 `jsonschema` 开发依赖）；`test_schema.py` 生成到临时目录 |
| 4 | 存储（#9、#10、#11） | 版本与轨迹写入用 `BEGIN IMMEDIATE` 事务包住“查询 + 插入”；版本冲突抛 `version_conflict`；同 `event_id` 内容不同返回 `version_conflict`；`read_from(session)` 只读本会话游标，内核会话视图另设 `read_by_kernel_session` | 两个进程并发写同一对象与同一会话无冲突、无重复 cursor；冲突码为 `version_conflict` |
| 5 | 运行时（#12、#13） | `invoke` 只把输入校验阶段的 `ValidationError` 归为 `invalid_input`，处理函数内的 `ValueError` 由各原子显式转换，其余归 `execution_unknown`；MCP 注解按操作显式声明只读/幂等/破坏性（不按 `writes` 一律推断），宿主端审批行为不在本轮验证范围；抽取记录、可判定性、前置条件写入 VersionedRepository | 错误映射用例覆盖三类；`tools/list` 带注解，且幂等/破坏性逐项断言 |
| 6 | 语义与解析细节（#14、#15） | 可判定性带 `unknowns` 不得为 `auto`；缓存键加 statement 与需求修订号；无修订号返回 `needs_input`，不补 `r1`；前置条件规范化保留小数点；解析细节逐项修正 | 各项一个反例用例 |
| 7 | 工程卫生与验证（#16、#17） | `.gitignore` 加 `.dataagent/` 并清理残留；临时文件用上下文管理器；拆分两个长函数与重复降级逻辑；隔离 `MINT_HOME` 安装并 `tools/list`，模型端点可用时跑 `mint run --json` | 包目录无运行产物；`mint` 安装验证记录写入实施记录 |
| 8 | 文档 | README 与方案 §6.2 按修复后行为更新；05 中命名空间、必填字段、`$id` 的校准回写并同步飞书 | 文档与实现一致 |

## 2. Round 4 修复

| 项 | 修复 |
|-|-|
| 锚点（#1、#2、#5） | `AnchorResolver` 统一对 PDF 文本、bbox、文档单元、JSON Pointer（RFC 6901）、Excel 单元格、记录键回原文取值；`text_span` 以单元正文（内容寻址的 `content_ref`）为基准、偏移改为单元内相对坐标；`json_pointer` 越界/缺路径、`excel_cell` 空/越界、`record_key` 无行/多行、未知选择器均显式失败；`value=None` 不得落 `extracted`；`pdf_bbox` 按页码而非列表下标取页，OCR 像素 bbox 按 `dpi` 换算为 PDF point；PDF 行定位失败记 `da01.line_not_located` 并跳过该 block，不退回游标伪造区间；数值重定位加整词边界并排除日期片段；规则 `sources`/条件/exception 均核对锚点正文（`da02.anchor_value_mismatch` / `da03.unanchored_condition`）；`anchor_extracted_values` 校验记录/文档/锚点同源同修订；`maintain_source_anchors` 无 `document_ref` 时返回 `unresolved`，不再仅凭 revision 匹配放行 |
| 表结构（#3、#4） | 表头判断改为“连续非数据行且下一行为数据行”，纯文本表、两行无空格表头可识别；合并表头沿合并区向下/向右展开；常规与 irregular Excel 删除空行时都用 `row_numbers` 保存原始行号，合并区按原坐标换算；`formula_text` 保留公式且不报缺缓存，`cached_values` 缺缓存记 `missing` + `da01.formula_cache_missing` |
| 契约（#6、#7、#8） | 命名空间统一点分并校验 `extensions` 键与 `Issue.code`；开放枚举 schema 导出 `anyOf[enum, pattern]`，扩展缓存上限 128；六个必填字段去掉默认值；`failed` 必须有 issue、`extracted` 必须有值、`extracted` 证据必填；新增 `validate_acceptance_report`；时间统一 `AwareDatetime`；schema 增加带版本 `$id`；`VersionedRef` 解析与 pattern 一致 |
| 存储（#9、#10、#11） | 版本与轨迹写入用 `BEGIN IMMEDIATE` 包住查询+插入；版本冲突抛 `version_conflict`；同 `event_id` 不同内容返回 `version_conflict`；`read_from(session)` 只读本会话，跨内核会话用 `read_by_kernel_session`；两个独立进程并发写同一对象/同一会话的用例通过 |
| 运行时（#12、#13） | `invoke` 只把输入校验 `ValidationError` 归 `invalid_input`，处理函数异常归 `execution_unknown`；MCP 注解按操作显式声明：只读工具 `idempotentHint=true`，内容寻址/同 `event_id` 写工具为 `true`，随机 draft/event id 的写工具为 `false`，`destructiveHint` 统一为 `false`；抽取记录、可判定性评估、前置条件草稿写入 VersionedRepository |
| 语义与解析（#14、#15） | `auto` 带 `unknowns` 降为 `needs_evidence`；缓存键校验 statement 与需求修订号；无修订号返回 `needs_input`；前置条件规范化保留小数点；CSV latin-1 回退告警，列数不符的行只记入 `bad_rows` 并隔离，不再补齐/截断后入表；JSON `records_path` 按 RFC 6901 处理空根与空键；`dedupe_names` 生成不会撞名的后缀；标题支持 `1.` 与 `1.1` 并建立父子关联；找不到页内位置时报错，不再伪造 `(1,0,0)` |
| 工程卫生（#16、#17） | `.gitignore` 增加 `.dataagent/` 并清理残留；`_materialize` 改为上下文管理器，读写后删除临时文件；`test_schema.py` 生成到临时目录；`extract_irregular_excel` / `extract_fields_to_schema` 拆出纯函数（行为不变）；新增 `scripts/verify_local.sh` 一键跑契约/数据/schema/snapshot/CLI/MCP/bundle 门禁；bundle 仍为 69 个文件、0 个 `.pyc`；隔离 venv 安装 wheel 后 `tools/list=32`，冷启动 3.53 s（`evidence/round4/isolated-install.log`） |
| 测试 | `dataagent-contracts` 101 passed、`dataagent-data` 163 passed（Round 4 当时计数；Round 4.1 返修后为 111 / 172，见 §3）。新增锚点矩阵、表结构/公式、并发存储、语义/解析反例，以及 `test_round4_acceptance_gaps.py` 7 项端到端验收、`test_round4_unit_anchors.py` 单元正文/维护/根指针、规则 sources/exception 锚点正文核验；测试员在验收探针中补了 PDF 行定位 issue 断言与“合并区跨过被删空行”回归；schema 66 files；snapshot 32 atoms |

## 3. Round 4.1 返修

评审（Round 4）判定 FAIL，根因是三条 fail-open 证据链与若干可审计性缺口；本轮按返修指令逐项关闭，未放宽任何既有断言。

| 项 | 修复 | 回归 |
|-|-|-|
| P1-1 MCP 写注解 | `extract_fields_to_schema`、`anchor_extracted_values`、`segment_document`、`maintain_source_anchors`、`assess_automatic_decidability`、`define_rule_preconditions` 六个持久化操作补 `writes=True`；前四个内容寻址为 `idempotent=True`，后两个随机 draft/assessment id 为 `idempotent=False`；`destructiveHint` 保持 `false` | `test_round4_storage.py::test_tools_list_carries_write_annotations` 改为逐操作断言：19 只读 / 13 写，并核对每个操作的幂等值；黑盒 `tools/list` 探针一致（Round 4.2 修正为 8 只读 / 24 写 / 18 幂等 / 6 非幂等） |
| P1-2 `text_span` 全文档旁路 | 删除三处 `units={document.asset.id: full_text}` 注入；`segment_document` 持久化 `document_unit_index`（键 `source_ref@source_revision:content_ref`，含 `document_ref/source_ref/source_revision/content_ref/unit_type/ordinal_path`）；`AnchorResolver._unit_text(unit_ref, source_ref, source_revision)` 必须先命中索引并核对三元组，否则返回不可解析 | `test_round4_unit_anchors.py` 新增文档 asset id 作 unit_ref、跨文档 unit_ref、未索引内容块 3 个反例；真实 `unit.content_ref` 正例保持 |
| P1-3 跨 revision 校验 | `maintain_source_anchors` 在提供 `document_ref` 时要求 `document_ref.original_ref.revision == current_revision`，否则 `invalid_input`；`revision_map` 目标必须等于 `current_revision` | `test_round4_unit_anchors.py::test_maintain_anchors_rejects_mismatched_document_revision`；`test_documents.py` 的 remap 用例改用同内容/新修订的文档副本 |
| P2-1 RFC 6901 空根 | `JsonPointerSelector.pointer` 改为 `^(?:/.*)?$`，删除把 `""` 改写为 `"/"` 的 validator | `test_round4_contracts.py` 新增空根/空键/非法指针与生成 schema 断言；schema 仍 66 files |
| P2-2 `unit_type` 点分 | `DocumentUnitRef.unit_type` 接受 S0 值或 `OPEN_NAMESPACE_PATTERN`，拒绝 `:`；`vocab` docstring 同步 | `test_round4_contracts.py::test_document_unit_type_uses_dotted_namespaces` |
| P2-3 规则条件矛盾 | `anchor_supports_text` 保留精确子串快路径；改述路径要求内容词覆盖 100%、否定极性一致、条件不得丢弃锚点中的数字 | `test_semantics.py::test_rule_conditions_reject_contradictions_and_expansions` 覆盖 4 条矛盾/扩大表述并保留正例 |
| P2-4 PDF 错误映射 | 新增 `runtime.errors.execution_unknown`；`parse_pdf` 仅把已知 PDF 格式/加密/文件类异常（含 pdfminer 包装）归 `invalid_input`，其余归 `execution_unknown` | `test_error_mapping_acceptance.py` 新增库内部异常与损坏 PDF 两个反例 |
| P2-5 05 §6 七项 | 新增 `dataagent-contracts/tests/test_s0_acceptance.py`，逐项 7 个测试（51 行清单/族计数/类型解析、schema+示例、约束、枚举、依赖方向、敏感值、通用性）；`dataagent-data/tests/test_registry.py` 交叉校验 32 项已实现原子的输入/输出模型名 | 05 §6 附“验收项→测试节点”映射表 |
| P2-6 前置条件回读 | `DefinePreconditionsOutput.draft_ref` 返回 `VersionedRef(id, revision)`，`runtime.versions.get("preconditions", ...)` 可回读 | `test_semantics.py::test_precondition_draft_ref_can_be_read_back` |
| P3-1 门禁 | `scripts/verify_local.sh` 增加 bundle 精确 69 文件、`mint publish --dry-run`（临时副本）、manifest 校验、隔离 wheel 安装 + 空 `MINT_HOME` 冷启动 <120s；命令与输出写入 `evidence/round4/verify_local.log` | 脚本退出码 0 为唯一标准 |
| P3-2 文档 | 实现基线计数改为 111/172；本节新增；05 §3.3.2 明确 `text_span.unit_ref` 必须绑定 `source_ref@revision`、空根已可表达；`vocab` docstring 删除冒号表述 | 文档与实现一致 |
| P3-3 清理 | 删除 `_materialize` 不可达 `return`；`AnchorResolver._workbook` 在 `finally` 删除临时工作簿 | 临时文件失败路径不残留 |

门禁实测：contracts **111 passed**、schema **66 files**、data **182 passed**、snapshot **32 atoms**、CLI/MCP **32/32**、bundle **69 files / 0 `.pyc`**、`mint publish --dry-run` exit 0、manifest **184/184 OK**、隔离安装 `tools/list=32` 且冷启动 <120s。证据见 `packages/capabilities/dataagent-data/evidence/round4/`（`verify_local.log`、`isolated-install.log`、`manifest.sha256`、`manifest-check.log` 及各专项日志）。


## 4. Round 4.2 返修

Round 4.1 复审仍判 FAIL：11 个实际持久化操作在 `tools/list` 中仍为 `readOnlyHint: true`；畸形 `requirement_ref` 落入 `execution_unknown`；证据文档保留旧值。本轮按返修指令逐项关闭，未放宽任何断言。

| 项 | 修复 | 回归 |
|-|-|-|
| P1 MCP 写注解 | `parse_regular_excel`、`extract_irregular_excel`、`parse_delimited_file`、`parse_json_records`、`parse_text_pdf`、`ocr_pdf`、`ocr_image`、`recover_headers`、`expand_merged_cells`、`classify_table_rows`、`profile_table_structure` 共 11 个操作补 `writes=True, idempotent=True`（内容寻址/同内容去重）；`mcp_server.py` 的 `readOnlyHint = not spec.writes` 推断公式不变，修正的是 `writes` 事实 | `tools/list` 实测 **32 total / 8 read-only / 24 writes / 18 idempotent / 6 non-idempotent / 0 destructive**；`test_round4_storage.py` 逐项断言；4 个运行时探针确认 content/objects 计数增长且 `readOnlyHint=false` |
| 防回归守卫 | `test_registry.py` 用 `inspect.getsource(handler)` 扫描 `register_file_ref(`、`store_table(`、`store_document_blocks(`、`content.put(`、`.versions.save`、`.traces.append(`，命中即要求 `writes=True` | 21 个内联写 handler 全部声明为写；3 个轨迹原子经 helper 写入 |
| P2 错误映射 | `assess_automatic_decidability` 新增 `_requirement_target_ref`：`a@b@c`、`@`、`a@`、`@b`、`a b@r1`、空白 ref 及空/带空白 `ctx.expected_revision` 均在 handler 内转为 `invalid_input`；`rule:1` 无修订号仍返回 `needs_input`（`da03.requirement_revision_required`） | `test_error_mapping_acceptance.py` 6 个畸形 ref + 1 个空 `expected_revision` 反例，3 个正例回归（`rule:1@r1`、`rule:1` + `expected_revision=r1`、`rule:1` → `needs_input`） |
| P3 证据 | `changes.md` 修正 `≥60%`→100%、manifest 183→184、注解 19/13→8/24；从最终 `_tools()` 重新生成 `annotations.log`/`tools-list.json`；manifest 按原 184 路径重算并重跑 `shasum -c` | `verify_local.sh` exit 0；证据日志含命令与输出 |

门禁实测：contracts **111 passed**、schema **66 files**、data **182 passed**、snapshot **32 atoms**、CLI/MCP **32/32**、bundle **69 files / 0 `.pyc`**、`mint publish --dry-run` exit 0、manifest **184/184 OK**、隔离安装 `tools/list=32` 且冷启动 <120s。证据见 `packages/capabilities/dataagent-data/evidence/round4/`（`annotations.log`、`tools-list.json`、`verify_local.log`、`manifest-check.log`、`changes.md`）。

## 5. Round 4.3 返修

Round 4.2 复审仍判 FAIL，阻塞项 3 个：`AnchorResolver` 的 JSON/Excel 解析缓存只按 `source_ref` 键、跨 revision 串用；方案 §6.2 与 05 仍写 `read_from` 合并内核会话；包目录残留 `.dataagent/`。本轮只修这三处，未放宽任何既有断言，其余残余记入 §6。

| 项 | 修复 | 回归 |
|-|-|-|
| P1 跨 revision 缓存 | `runtime/anchors.py`：`_json_document` 与 `_workbook` 的解析缓存改为 `(source_ref, source_revision)` 复合键，不再写回裸 `source_ref`；构造参数保留为“单 revision 种子”（复合键 `source_ref@revision` 精确匹配，裸 `source_ref` 只绑定首次使用它的 revision，第二个 revision 回退运行时文件）；`_file_cache` 的 `source_ref@revision` 语义不变 | `test_anchor_selector_matrix.py` 新增 5 个用例：Excel/JSON 直接 resolver 两种顺序各取各 revision（rev2 先解析不再污染 rev1）；同一 revision 重复解析命中缓存；`define_metric_formula` 的 `sources` 以 `[rev2, rev1]` 与 `[rev1, rev2]` 两种顺序都只保留 rev2，rev1 计 `da02.anchor_not_found` |
| 计划第 8 项 `read_from` | 方案 §6.2 改为“`read_from(session_id)` 只读本会话游标；跨任务内核会话由 `read_by_kernel_session(kernel_session_id)` 提供”；05 §3.3.5 字段说明与实现回写同步；README 已是修复后语义，不改 | `rg -n "read_from\|read_by_kernel_session"` 三处均只描述本会话游标，无“同时命中内核会话”表述 |
| 计划第 7 项 运行产物 | 删除 `packages/capabilities/dataagent-data/.dataagent/`（默认 `data_root` 的遗留产物，非测试套件产生）；`scripts/verify_local.sh` 末尾新增门禁：`.dataagent`、`dist`、`*.egg-info` 任一存在即失败 | `test ! -e .dataagent`；门禁重跑后包目录无运行产物 |
| 文档校准 | 实现基线 §3 的 `19.1s` 标注为“Round 3 历史值”；§6 新增规则条件弱化表述的已知限制（R6 残余，未修复） | 同一文档内冷启动数字不再互相矛盾 |

门禁实测：contracts **111 passed**、schema **66 files**、data **187 passed**、snapshot **32 atoms**、CLI/MCP **32/32**、bundle **69 files / 0 `.pyc`**、`mint publish --dry-run` exit 0、manifest **184/184 OK**、隔离安装 `tools/list=32` 且冷启动 <120s。证据见 `packages/capabilities/dataagent-data/evidence/round4/`（`verify_local.log`、`manifest.sha256`、`manifest-check.log`、`changes.md`）。

## 6. 已知限制

- `mint publish --dry-run` 已实测（exit 0，产物 `dataagent-data-layer-0.1.0.mint.tar.zst`）；隔离 `MINT_HOME` + 空工作目录下用 wheel 装入 clean venv 后，`initialize + tools/list` 返回 32 个工具，冷启动 3.53 s（日志 `evidence/round4/isolated-install.log`）。
- `mint run --json` 仍未验证：本地模型端点返回 401，环境也没有可用凭据，属环境限制、不是代码门禁失败；因此本轮只声明 MCP 工具与注解可被拉起，**不声明**宿主端审批/重试行为已验证。
- MCP `idempotentHint` 按操作显式声明（只读与内容寻址/`event_id` 去重写为 `true`，随机 draft/event id 的写为 `false`），`destructiveHint` 统一 `false`：32 个工具均无删除/覆盖语义。宿主是否据此弹审批仍取决于 mint-core 的客户端实现，本轮未做行为验证。
- 内核/CSP 侧统一走 MCP；CLI 因失败退出码会丢 stdout，不做 `kind:"command"` 装配（方案 §4.3）。
- OCR 为可选依赖组；未安装时所有 OCR 原子返回 `dependency_unavailable`，测试覆盖了缺失与注入两种路径。
- `InferencePort` 目前只有 `agent_provided` 形状的占位；直连模型适配器未实现（方案 §5 保留接口）。
- MCP 未知工具目前返回 `unsupported` 的 `CapabilityResult` 文本结果，而非 JSON-RPC `-32002`；`tools/list` 只暴露已注册的 32 个工具，该分支仅防御性使用。
- `assess_automatic_decidability` 的 `requirement_ref` 不带 `@revision` 时必须提供 `ctx.expected_revision`，否则返回 `needs_input`（`da03.requirement_revision_required`），不再静默补 `r1`；这是 Round 4 的有意收紧。
- `text_span` 的 `char_start/char_end` 自 Round 4 起是**单元正文内**的相对偏移（此前是全文偏移，且 `unit_ref` 指向文档 asset）；尚无历史持久化锚点依赖旧语义，升级时如遇旧锚点需重新切分。
- 规则条件的改述校验（R6 残余，**已知限制、未修复**）：`anchor_supports_text` 的改述路径要求“条件内容词被锚点覆盖”，仍接受删去限定词的弱化表述（锚点 “... require department head approval” 对条件 “... require approval” 会通过）；收紧为双向覆盖会误伤现有正例“claims above 5000 CNY”，需在后续轮次重定条件语义后再改。
