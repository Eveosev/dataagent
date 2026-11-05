---
round: 5-independent
date: 2026-11-04
subject: 对 06 建设方案与 packages/capabilities 下 dataagent 实现的独立复核（盲评后对照 r4-review）
score: 6.8/10
baseline: 06-data-layer-build-plan.md v0.3；源码 mtime 2026-11-04 12:06–12:18；r4-review 14:20
---

# 独立复核：dataagent 数据层完成度与代码质量

范围：`packages/capabilities/dataagent-contracts`、`packages/capabilities/dataagent-data`
（不含 `packaging/bundle/`，该目录为 gitignore 的构建产物）。

方法：先读 [06-data-layer-build-plan.md](../06-data-layer-build-plan.md) §1–§10 建立验收点，
再**独立**跑测试、入口、注册表、快照与缺陷复现；最后才读 [r4-review.md](r4-review.md)
做对照。文中每条结论都给出可重跑的命令或代码位置。

## 1. 与方案的逐项核对（实测）

| 方案条目 | 实测 | 结论 |
|-|-|-|
| §1 契约 36 类型 | `schema/generated` 66 schema + index，`index.json` 记 `core_type_count=36`（34 具体 + 2 泛型绑定）；`CORE_TYPES` 36 | 一致 |
| §1 数据层 32 原子（骨干 9 / 判定 14 / 计算 9） | `catalog-snapshot.json` 32 原子、32 个唯一 operation；按 id/operation/source_file 与总 Catalog 的 32 条 `layer=01-data-layer.md` 记录**逐字段 0 差异** | 一致 |
| §3 包结构 | `runtime/ports/adapters/ingestion/preparation/semantics/memory/interfaces` 齐全，46 个 py、7,779 行；契约 12 个 py、1,482 行 | 基本一致 |
| §3 `tests/{contracts,ingestion,...}` 7 个子目录 | 实际为**扁平** `tests/*.py`（22 个 test 文件 + conftest，无子目录） | 偏差（不影响功能） |
| §4.1 快照校验 | 快照随包发布（`src/dataagent_data/catalog-snapshot.json`）；`source_file` 由 handler `__module__` 推导；`export_catalog_snapshot.py --check` → `OK: 32 atoms` | 一致，机制优于方案要求 |
| §4.2 MCP | 子进程 NDJSON：`initialize`/`tools/list` 正常，**32 个工具**；注解 8 只读 / 26 幂等 / 0 破坏性 | 一致 |
| §4.3 CLI | `--list` 32；`failed`→1、用法错→2、`needs_input`→0；绝对路径/`..`/符号链接越界均被拒 | 一致 |
| §5 两段式推理 | 无 `proposal` → `needs_input` + `inference_request`；带 `proposal` 逐条核对锚点、无依据值降级 | 流程在，但锚点判据有 P0 缺陷（§2） |
| §6 存储/轨迹 | 内容寻址原子写；SQLite 显式 revision + `BEGIN IMMEDIATE`；`event_id` 去重、cursor 从 1、checkpoint digest | 形状一致，并发语义有洞（§2 D5） |
| §8 打包 | bundle 69 文件、契约 vendoring、`.mcp.json`、`mint.toml`、2 个 Skill、`source-ref.toml` 含 catalog/snapshot 双 hash | 一致（`.mcp.json` 多一个 `timeout_s`，无害） |
| §10 验证 | contracts 111 passed；data 187 passed；schema `--check` OK；快照 `--check` OK | 一致 |
| 测试声称 | 56 / 174 个 `test_` 函数参数化成 111 / 187 用例，0 skip / 0 xfail | 一致 |

## 2. 复现的缺陷（全部在本机重跑过）

| # | 级 | 现象 | 证据 | 根因 |
|-|-|-|-|-|
| D1 | P0 | 规则条件**方向反转仍被接受**：锚点为 “Claims above 5000 CNY require department head approval.”，提案 “Claims **below** 5000 …” 与 “**less than** 5000 …” 均返回 `ok`、`kept=1`、无 issue | `define_business_rules` 原子级复现 | `above/below/less/more/least` 在 `runtime/anchors.py:622` 停用词表；数字集合相同 + 内容词 100% 覆盖即通过 |
| D2 | P0 | 丢弃阈值的条件也通过：“**department head approval**” 返回 `ok`、无 issue | 同上 | `anchor_supports_text` 的子串快路径（`anchors.py:682`）在数字检查**之前** return，绕过了“不得丢弃锚点数字” |
| D3 | P1 | 稀疏首行被并入表头并**静默丢行**：`[["name","q1","q2"],["Alice",None,None],["Bob",1,2]]` → `recover_headers` 返回 `ok`、`header_rows=2`、`columns=['name / Alice','q1','q2']`、`ambiguities=[]`、`issues=[]`，只剩 Bob 一行 | 原子级复现 | `preparation/structure.py:50 _detect_header_rows` 只看候选行“是否像数据”，不看非空占比与下一行类型 |
| D4 | P1 | 值匹配按子串：`anchor_value_mismatch("Acme Inc. total 200", "Acm") == ""`（视为支持） | 直接调用 | `anchors.py:591` 文本值走 `needle in span` |
| D5 | P1 | 乐观并发**丢失更新**：两个并发 `register_extraction_schema_version` 同带 `expected_revision=r1`，两个都返回 `ok`（r2、r3），本应恰一个 `version_conflict` | 双线程 + 屏障复现 | handler 先 `current()` 后 `save_content_addressed()`，两者不在同一事务；`save(expected_revision=)` 无任何 handler 使用 |
| D6 | P1 | `find_file_ref` 写死 `r1`：同一 `f1@1` 已写到 r2 后仍返回 r1 的内容（digest `sha256:00000…`） | 直接调用 | `runtime/helpers.py:147` |
| D7 | P1 | 跨会话游标不可作续读令牌：task-A 写过 3 条后，task-B 追加 cursor=1 的事件；读过 `cursor>=4` 的调用方**永远看不到**该事件（`[]`），而从 1 读则返回 `a1,b1,a2,a3`（乱序） | 直接调用 | `adapters/storage/sqlite.py:309` 用**每会话** cursor 过滤跨会话视图 |
| D8 | P2 | 冲突前已 `content.put`，留下孤儿内容：第二次 `append_task_event` 因 event_id 内容不同报 `version_conflict`，内容文件 2→3 | 直接调用 | `memory/traces.py:47` 先写内容、后判冲突 |
| D9 | P2 | **（新）重复行锚点全部指向首次出现**：同一行在文献中出现 3 次时，`inference_request.clauses` 里这 3 条的锚点全部是 `char 0…50` | 原子级复现 | `semantics/metrics_rules.py:270` 子句枚举 `page.text.find(text, max(0, start-(cursor-len(line))))`，括号内恒为 0 |
| D10 | P2 | **（新）静默截断**：`define_business_rules` 只取 `content.pages[:5]`、最多 40 条子句，超出的条款不产生 issue / completeness 提示 | 代码 `metrics_rules.py:264,285` | 硬编码上限 |
| D11 | P2 | `VersionedRef(id="a@b", revision="r1")` 序列化为 `a@b@r1` 后无法再解析；`validate_acceptance_report(report)` 省略两个可选参数时**什么都不校验** | 直接调用 | `refs.py:26`、`evaluation.py:153` |
| D12 | P2 | 连接不关闭（`with sqlite3.connect(...)` 只提交事务不 close，每次调用重复 `PRAGMA journal_mode=WAL`）；`_read_primary` 与 `read_from` 重复；`PACKAGE_ROOT`、`store_json` 无引用 | 代码核查 | 工程卫生 |

> D1–D3 已足以推翻“每个值都有锚点、`unknown` 不折算、缺失不补造”的产品承诺：
> 三者都是 `status=ok` 且无 issue 的**静默错误**，下游无法察觉。

## 3. 做得好的部分（避免只列缺陷）

- **注册表防漂移**：`operation` 名即函数名，`source_file` 由 `__module__` 推导，快照与总 Catalog 双向校验，`--check` 在 CI 可用；比方案 §4.1 要求更硬。
- **契约不变量落到模型层**：`CapabilityResult` 的 `failed/partial/pending/needs_input` 约束由 `model_validator` 强制（`envelope.py:141`），枚举封闭、`extensions` 键命名空间校验。
- **路径安全**：绝对路径、`..`、符号链接逃逸三层拒绝，CLI 黑盒验证通过。
- **失败关闭**：伪造的 `unit_ref` 不被 `text_span` 接受；PDF 文本层定位失败报 `da01.line_not_located` 且不造 bbox；CSV 列数不符入 `bad_rows` 而非补/截断。
- **存储**：`BEGIN IMMEDIATE` 串行化“读当前 + 追加”，内容寻址写幂等，`event_id` 去重，checkpoint 前缀 digest。
- **测试**：32 个原子在测试中都有引用（平均 8.6 次）；`test_scenarios.py` 是真实 runtime + sqlite + content store 的 token 级链路，不是 mock；反例覆盖明显强于同类工程。
- **打包自洽**：bundle 内 vendoring 契约、`source-ref.toml` 记录 research/catalog/snapshot 三个 hash，`mint publish --dry-run` 在证据日志中通过。

## 4. 证据现状的一个问题

`evidence/round4/manifest.sha256` 现在**不是全绿**：

```text
shasum -a 256 -c .../manifest.sha256  →
docs/research/dataagent-2026-11-03/06-data-layer-build-plan.md: FAILED
其他 183 条: OK
```

原因不是代码：manifest 生成于 12:20，而方案文档 14:20 才更新（§12 表格挪目录）。
`evidence/round4/verify_local.log` 最后一次运行（2026-11-04T07:07:54Z）也在这一步退出非 0，
因此 “`verify_local.sh` 全绿” 目前**不可复现**，与 r4-review “manifest 184/184 OK” 不符
（当时成立，现在已过期）。建议门禁把 `docs/**` 排除或随文档改动重生成 manifest。

## 5. 评分（0–10）

权重按“数据层的价值 = 可信的判定/计算”设定，而非按代码量。

| 维度 | 权重 | 分 | 主要依据 |
|-|-|-|-|
| 能力覆盖与入口 | 20% | 9.0 | 32/32 注册、快照零差异、CLI/MCP 各 32、打包齐全 |
| 契约包 | 15% | 8.0 | 36 类型、66 schema、枚举/不变量/示例校验；扣 D11 与 schema 未表达命名空间约束 |
| 数据正确性与锚点可信度 | 30% | 5.0 | D1/D2/D3/D4/D9/D10 均为静默错误；优点见 §3 |
| 运行时与存储 | 15% | 6.5 | 路径/错误映射/事务好；扣 D5/D6/D7/D8、连接不关闭 |
| 工程与代码质量 | 8% | 6.5 | 15 个 >80 行函数（最大 239）、21 处宽口径 except、`Any` 逃逸、无 ruff/mypy、死代码 |
| 测试与验收 | 7% | 6.5 | 298 用例全绿、原子全覆盖；扣源码扫描式守卫、硬编码 21/24/18、缺 TOCTOU 与方向反转用例 |
| 打包与可复现证据 | 5% | 7.0 | bundle/mint 通过；扣 manifest 当前红、mint-core 加载未证 |

加权：`0.20×9.0 + 0.15×8.0 + 0.30×5.0 + 0.15×6.5 + 0.08×6.5 + 0.07×6.5 + 0.05×7.0 = 6.80`

**综合 6.8/10**（完成度 9/10、代码质量约 6/10）。

与 r4-review 的 6.5 对照：在我抽样的每一项上 r4 的结论都**可复现**（测试数、注解分布、
D1–D4、D5、D6、D7、D8 均属实），所以 6.5 是可信的；我给出 6.8 的差异来自
“完成度被低估 + D9/D10 两处新缺陷”相互抵消，而非对旧缺陷的翻案。可接受区间 6.5–7.0。

## 6. 建议修复顺序

1. **P0**：删掉 `anchor_supports_text` 的子串快路径；把方向/比较词移出停用词表并做方向核对；
   `record_key`/`json_pointer` 必须定位到字段，拒绝根指针与多单元格区域。
2. **P0**：表头判定加非空占比 + 与下一行类型一致性；判为多行表头时至少给 issue。
3. **P1**：handler 把 `expected_revision` 交给 `save(expected_revision=)`（存储层已支持）。
4. **P1**：`read_by_kernel_session` 用全局序号分页；`find_file_ref` 按 revision 读；冲突检查先于 `content.put`。
5. **P2**：子句枚举的 offset 用 `page.text.find(text, start)`；5 页/40 条上限写进 `completeness`/issue。
6. **工程**：连接关闭、拆 100 行以上函数、统一错误码命名空间、门禁改为存储层埋点观测。

## 附录：复现命令

```bash
cd packages/capabilities/dataagent-contracts && uv run --frozen pytest          # 111 passed
cd packages/capabilities/dataagent-data       && uv run --frozen pytest          # 187 passed
cd packages/capabilities/dataagent-data && uv run --frozen python scripts/export_catalog_snapshot.py --check
cd packages/capabilities/dataagent-contracts && uv run --frozen python scripts/generate_schema.py --check
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | uv run --frozen python -m dataagent_data.interfaces.mcp_server               # 32 tools
uv run --frozen python -m dataagent_data.interfaces.cli --list                   # 32 ops
```

关键探针（在 `packages/capabilities/dataagent-data` 下运行，脚本放 /tmp 即可）：

```python
# D1/D2：解析 PDF -> 取 inference_request.clauses[0].anchor -> 带 proposal 再调
prep = invoke("define_business_rules", {"statement": "approval",
        "document_ref": doc.model_dump(mode="json")}, ctx, runtime=rt)
anchor = prep.issues[0].inference_request["clauses"][0]["anchor"]
for cond in ["Claims above 5000 CNY require department head approval.",
             "Claims below 5000 CNY require department head approval.",
             "department head approval"]:
    prop = {"conditions": [{"condition_id": "c1", "text": cond,
            "referenced_fields": ["amount"], "anchors": [anchor]}], "combination": "all"}
    out = invoke("define_business_rules", {"statement": "approval",
            "document_ref": doc.model_dump(mode="json"), "proposal": prop}, ctx, runtime=rt)
    print(out.status.value, len(out.data.draft.definition.conditions), out.issues)  # 3 次都是 ok/1/[]

# D3：带稀疏首行的表
rh = invoke("recover_headers", {"table_ref": t.model_dump(mode="json")}, ctx, runtime=rt)
print(rh.status.value, rh.data.header_rows, rh.data.columns, rh.data.ambiguities)  # ok 2 ['name / Alice',...] []
```

D5 用 `threading.Barrier` 包住 `runtime.versions.current`（仅测试钩子）让两个
`register_extraction_schema_version` 同读 r1；D6/D7/D8 直接调用
`helpers.find_file_ref`、`SqliteTraceRepository.read_by_kernel_session`、`append_task_event`
两次（同 event_id 不同 payload）即可。
