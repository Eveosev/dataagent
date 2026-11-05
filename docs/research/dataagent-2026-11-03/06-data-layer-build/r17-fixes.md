# Round 17 fixes — Tester r17 的阻断项（B1/B2/B3 + R4c）

对照本轮 Tester 独立复评报告（team 目录 `tester_r17_report.md`，评分 完成度 8.4 /
质量 6.7 / 综合 7.6，VERDICT FAIL）修复其 §4 阻断项。契约类型、注册表、CLI/MCP
入口、Catalog 的原子集合均未改动。

## B2 / R4 — P2（fail-open）：伪造 basis_refs 可支撑 `auto` 并落库

### 现象（tester_r17_probe.py，真实 invoke 路径）

```
case=r4_fabricated   status=ok  verdict=auto  basis_refs=["nonexistent:evidence"]  issues=[]
case=r4_lookalike    status=ok  verdict=auto  basis_refs=["evidence:0000000000000000"]  issues=[]
case=r4_fabricated_persisted  persisted=true
```

`assess_automatic_decidability` 只在 `not basis_refs` 时降级（`da03.auto_without_basis`），
引用了不存在的对象与 `auto` 一样通过并落库，下游 `identify_evidence_or_human_gaps`
据此得出 `gaps=0`。对应计划 §5 步骤 3（“没有依据的值降为 missing 或 conflict”）与
§10.2（“缺失值不补造”）。

### 修复（`semantics/decidability.py`、`adapters/storage/sqlite.py`、`ports/versioned.py`）

- 仓储新增 `ref_exists(ref)`：`ref` 为已持久化对象的完整 `object_id`（如
  `file:<id>@<digest>`，这类 id 自身含 `@`）或 `<object_id>@<revision>` 时可解析；
  端口协议 `VersionedRepository` 同步声明。
- 新增 `_unverifiable_basis_refs`：`auto` 判定引用的每个 basis 必须解析为运行时
  真实产物——版本化对象（`versions.ref_exists`）或内容寻址 blob（`content.exists`，
  `sha256:<64 hex>`）。
- `assess_automatic_decidability`：存在不可解析引用时降级
  `needs_evidence`，发 `da03.auto_unverifiable_basis`（warning），且**丢弃**
  不可解析引用——伪造字符串不再以“证据”身份落库。空 basis（r4 既有行为）与
  unknowns 检查保持不变。

### Tester 探针复跑（修复后实测）

| 探针 | 修复前 | 修复后 |
|-|-|-|
| r4_fabricated / r4_lookalike | `ok / auto`，落库 | `partial / needs_evidence / da03.auto_unverifiable_basis`，`persisted=false` |
| r4_empty_control | `needs_evidence` | 不变（`da03.auto_without_basis`） |

合法引用不受影响（防过拟合回归）：已注册的 `file:<id>@<digest>` 源引用、解析产物
`blocks_ref`（内容寻址）、`versions.save` 产生的 `evidence:<id>@<rev>` 均保持
`ok / auto`。

## B3 / R5 — P2（完整性失真）：切分/抽取截断仍报 `complete_in_declared_scope`

### 现象

- `segment_document(max_units=2)` 对 3 单元文档返回 2 单元，
  `completeness=complete_in_declared_scope`（`preparation/documents.py` 切片后直接
  `helpers.complete`）。
- 抽取第一阶段候选 span：719 字符截为 300、40 条截为 30 条，仍报
  `complete_in_declared_scope`（`preparation/extraction.py`）。

对应计划 §4.1 与契约 `CompletenessExtent.truncated` 的语义：声明完整必须与真实覆盖
一致。`helpers.truncated(...)` 已存在（r12 起用于规则推理上下文），本次接入两处。

### 修复

- `segment_document`：记录切分前的 `total_units`；超出 `max_units` 时
  `completeness=truncated`，reason 为 `max_units=<n> returned <k> of <total>
  detected units`，observed 带 `units/total_units`。未截断仍 `complete`。
- `_candidate_spans` 改为返回 `(spans, truncations)`：span 文本 >300 字符与
  数量超过 30 条都记入 truncations；`extract_fields_to_schema` 第一阶段据此报
  `truncated`，并把 `truncations` 附进 `inference_request`，Agent 侧可见上下文
  被截断。第二阶段（proposal 落库）不涉及截断，completeness 语义不变。

### Tester 探针复跑（修复后实测）

| 探针 | 修复前 | 修复后 |
|-|-|-|
| r5_segment_truncated | `complete_in_declared_scope` | `truncated`，reason=`max_units=2 returned 2 of 3 detected units` |
| r5_extract_span_truncated（719→300） | `complete_in_declared_scope` | `truncated` |
| r5_extract_span_cap（40→30） | `complete_in_declared_scope` | `truncated` |

## R4c — P2：缓存失效依赖调用方自觉

`resolve_decidability_cache` 仅在同时传入 `statement` 与 `prior_statement` 时才比
对；只传 `statement` 时语句已变仍 `hit=true`。修复：`statement` 非空而
`prior_statement` 缺失时保守判 `hit=false`（reason 说明无法确认语句未变），与既有
“依赖列表为空 → 保守失效”同一原则。两侧同传且一致仍 `hit=true`。

## B1 — 发布门禁红：审计 manifest 10/194 不匹配 + 文档漂移

根因：并发工作流（07/08）把 `ExecutableSpec`/`EngineBinding` 迁入
`dataagent-contracts` core（36→37 类型、schema 66→68 文件、契约测试 111→112），
但未重生成审计 manifest，也未同步文档。修复：

- 重生成 `evidence/round4/manifest.sha256`：按原 194 路径重哈希，移除
  `r16-fixes.md`、加入 `r17-fixes.md`（沿既有“仅保留当前轮 fixes 文档”的惯例）、
  补入新增的 `schema/generated/{EngineBinding,ExecutableSpec}.json`、契约新测试
  `tests/test_round5_semantics_fields.py`（07/08 并发工作流新增）与
  `tests/test_round17_tester_findings.py`；共 198 条，`shasum -c` 全量 OK，
  `manifest-check.log` 同步刷新。
- 类型计数同步：`05-contracts.md`（进展注记与 §3.2 汇总行）、
  `06-data-layer-build-plan.md`（§1/§9）、contracts README 均改为 37 个类型
  （35 具体 + 2 泛型），并注明迁入来源（07 §4.2）。

## 验证（本轮实际执行，均带 `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`）

| 检查 | 结果 | 退出码 |
|-|-|-:|
| 数据层全量 | **560 passed**（548 + 12 个新用例） | 0 |
| 契约全量 | **117 passed**（含 07/08 并发工作流新增用例；tester 评估时为 112） | 0 |
| 新回归 `tests/test_round17_tester_findings.py` | 12 passed（R4 5 例 + R4c 2 例 + R5 5 例） | 0 |
| Tester r17 探针复跑 | R4 三例全部降级且未落库；R5 三例全部 `truncated` | 0 |
| `bash scripts/verify_local.sh` | `verify_local: OK`：contracts 117、data 560、schema 68、catalog 32、CLI 32、MCP 32、bundle 69、mint dry-run、manifest 198/198、隔离安装 32 工具、冷启动 2.88s | 0 |

## 变更文件

- **src（4）**：`semantics/decidability.py`（B2 依据守门 + R4c 保守失效）、
  `preparation/documents.py`（B3 切分截断披露）、`preparation/extraction.py`
  （B3 候选 span 截断披露）、`adapters/storage/sqlite.py` + `ports/versioned.py`
  （`ref_exists`）
- **tests（5）**：新增 `test_round17_tester_findings.py`（12 例）；
  `test_semantics.py`、`test_error_mapping_acceptance.py`、
  `test_round4_acceptance_gaps.py`、`test_scenarios.py` 中原以 `ev:1` 等伪造
  引用支撑 `auto` 的用例改为先持久化真实证据（`versions.save` / 已注册源引用 /
  已落库抽取记录），断言不变
- **docs（3）**：`05-contracts.md`、`06-data-layer-build-plan.md`（计数 36→37、
  §12 表补 r17 行）、新增本文
- **evidence（1）**：`evidence/round4/manifest.sha256` 重生成（194→198 条），
  `manifest-check.log` 刷新
