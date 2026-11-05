---
version: v0.1
date: 2026-11-05
scope: dataagent 数据层 / 执行应用层 / 评测治理层 的落地情况与代码质量
method: 14 个只读子代理并行审计 + 主代理复核
baseline: catalog 18 模块 / 141 能力组 / 458 原子；S0 51 项（数据 32 / 应用 13 / 治理 6）
tests: contracts 117 / runtime 75 / data 649 / application 201 / governance 117 / scenarios 12
revision: agent-kernel HEAD c1231ab（文档 pin f0fa521，领先 168 commits）；AgentOS 根目录非 git 仓库
---

# DataAgent 三层落地与代码质量评估

## 1. 结论

1. **表面落地是完整的**：51/51 个 S0 原子全部注册、全部经 MCP `tools/list` 暴露，operation、`source_file`、`catalog-snapshot` 与总 Catalog 逐项一致；六个包 1171 个测试全绿，三个 bundle 源码与 vendored 副本零漂移，应用层 dist 制品可解包复现。
2. **语义闭环没有成立**：应用层口径守卫可被一个 decoy 聚合整体绕过（交付错值仍标 `m-r32`）；治理层有 4 个 P0 级"自己绕过自己"（列级约束不裁剪、合成资源锚点、内容自证 provenance、CJK 敏感信息漏报）；数据层存在一条会静默产生乱码的编码探测路径。
3. **S0 的 enforce 姿态没有交付到产品路径**：应用层 bundle 的 `.mcp.json` 缺 `DATAAGENT_ENFORCEMENT_MODE=enforce`，安装 preset 后仍是 `warn`；治理层 MCP 未注入宿主主体/用途，Agent 可通过调用参数自选身份；`allow_masked` 在三层都走不通。端到端测试用测试代码显式注入 enforce，掩盖了这一点。
4. **工程质量高于同规模代码的平均水平，但工程门禁不足**：0 TODO/FIXME、错误分类清晰、路径穿越与 SQL 外部访问防护扎实、契约 `extra=forbid`、测试与源码约 1:1；但没有 CI、lint、类型检查、覆盖率，根目录不是 git 仓库，kernel 引用落后 168 个 commit，证据日志存在过期与覆盖。
5. **判断**：当前状态可作为 **S0 演示与联调基线**，不能作为 **S0 验收/交付基线**。宣称"已实现"前至少需要修完第 10 节的 P0 项，并把端到端测试改为经安装后的 bundle 启动。

## 2. 方法与基线

- 14 个只读子代理分头审计：三层各自的 S0 覆盖、代码质量、测试与打包，加上契约、共享运行时与 W0 接缝、端到端与发布、跨层安全、文档声称核对。
- 主代理独立复核：MCP 黑盒 `tools/list`、Catalog/snapshot 比对、`resource_fields` 覆盖统计、编码与敏感识别探针、bundle 漂移与 dist 检查、pyc/缓存清点。
- 全部命令使用各包已有 `.venv`，未联网、未安装依赖、未修改源码。

| 包 | src 行 | tests 行 | 测试数 | 结果 |
|-|-|-|-|-|
| dataagent-contracts | 1,586 | 1,572 | 117 | 全绿 |
| dataagent-runtime | 2,397 | 1,569 | 75 | 全绿 |
| dataagent-data | 10,586 | 11,124 | 649 | 全绿 |
| dataagent-application | 4,982 | 4,856 | 201 | 全绿 |
| dataagent-governance | 4,143 | 4,161 | 117 | 全绿 |
| dataagent-scenarios | — | — | 12 | 全绿 |

补充事实：`pytest` 必须用 `python -m pytest` 才能导入 `tests.conftest`；直接 `.venv/bin/pytest` 在 application/governance 分别有 3/8 个 collection error，文档未记录该差异。

## 3. 总览评分

5 分制；"落地"指能力面可达且语义成立，"发布"指可安装、可追溯、可运维。

| 维度 | 数据层 | 执行应用层 | 评测治理层 |
|-|-|-|-|
| 能力面落地（32/13/6） | 5.0 | 5.0 | 5.0 |
| 语义保真（对照 01/02/03 与 06/07/08） | 3.5 | 2.5 | 2.0 |
| 代码质量 | 4.0 | 3.5 | 3.0 |
| 测试有效性 | 3.5 | 3.5 | 3.0 |
| 发布/可运维 | 2.5 | 3.0 | 2.5 |
| **综合** | **3.6** | **3.3** | **2.9** |

契约/共享运行时 3.5；跨层安全 2.5；工程门禁 2.0。

## 4. 数据层

### 4.1 落地

- 32 项全部注册，`registry_errors()==[]`；MCP 32 个工具与 Catalog 完全一致，无多无少；CLI `--list` 32 条。
- `catalog-snapshot.json` 与总 Catalog 的 id / operation / source_file / s0_family 零差异，`export_catalog_snapshot.py --check` 通过；packaging 镜像逐字节相同。
- 无桩实现、无 TODO；6 个两段式原子正确返回 `needs_input` + `inference_request`。
- 22 项完整实现，10 项"部分"：输入/输出字段声明了但从不消费，或缺少文档要求的策略分支。

| 原子 | 缺口 |
|-|-|
| DA02.1.1 `detect_workbook_regions` | `layout_hints` 未消费；`overlapping` 硬编码 False |
| DA02.4.1 / 4.3 画像与类型推断 | 文档允许 SchemaRef 输入，代码只认 TableRef，按文档调用直接 `invalid_input` |
| DA02.8.1 `segment_document` | 只有 headings/paragraphs，无表格分块 |
| DA02.12.4 schema 版本注册 | 只算 digest，无字段差异与兼容性说明 |
| DA03.15.2 / 15.3 | `allowed_methods`、`allowed_scope` 声明未用；覆盖图会虚报自动覆盖 |
| DA03.16.3 / 16.4 | `conflicts` 恒空；新 assessment 未落库 |
| DA01.4.3 分隔文件解析 | 输出无 SchemaRef / 行位置 |
| DA01.4.5 PDF 解析 | 无文本层时不返回 `da01.no_text_layer` |

### 4.2 代码质量

强项：0 TODO/FIXME，0 裸 except，21 处 `except Exception` 均带 `noqa: BLE001` 与分类理由；`CapabilityError` 先重抛再分类；路径校验（绝对路径、`..`、symlink）实测全部阻断；18 个 pydantic 模型全部 `extra="forbid"`；`BEGIN IMMEDIATE` 防跨进程丢更新。

缺陷：

| 级别 | 位置 | 问题 |
|-|-|-|
| P0 | `adapters/parsers/delimited.py:13,23` | 编码顺序 utf-8 → gb18030 → latin-1；gb18030 先于 latin-1 命中，cp1252 字节 `"région"` 被解成 `"r間ion"`，不告警，`da01.encoding_fallback` 因 latin-1 不可达成为死代码（主代理已复现） |
| P1 | `ingestion/ocr.py:164-175`、`parsers/pdf.py:80-96`、`helpers.py:124` | 无页/行/字节上限；OCR 先把全部页渲染成 PNG 常驻内存；620KB 文本 PDF 实测 RSS 1.41GB，11MB xlsx 实测 1.47GB |
| P1 | `ingestion/files.py:92-95,112-113,165` | 同一 sheet 三次 `sheet_grid`、两次落盘、两次全量 `load_workbook` |
| P2 | `preparation/structure.py:168,184` | 合并表头已正确展开，仍误报 "header row has empty cells" |
| P2 | `adapters/parsers/json_records.py:85` | jsonl 分支忽略 `records_path`；全行失败时逐行诊断丢失 |
| P2 | `preparation/profiles.py:49,53` | `distinct_count` 用 `str(value)` 合并 1/1.0/"1"；mean 用 float，与 anchors 的 Decimal 两套数值模型 |
| P2 | `adapters/storage/sqlite.py:470-482` | `verify_checkpoint` 复算走 `INSERT OR REPLACE`，只读校验带写副作用 |
| P2 | `semantics/metrics_rules.py:687` = `applicability.py:378` | `anchor_reason` 逐字复制；跨文件 6 行重复块 53 处 |
| P3 | `decidability.py:308/317` | `allowed_scope` 传入 None / `only:ap_invoice` / `nothing`，输出完全相同 |

### 4.3 测试与证据

- 649 passed / 1229 assert / 389 函数；0 skip / 0 xfail；坏文件、越界路径、symlink、digest 不符、OCR 缺依赖均有覆盖。
- 真实样本系统性缺失：fixtures 仅 70B csv + 176B json，xlsx/pdf 全部由 conftest 合成；合成 PDF 用 Helvetica，中文抽出为 `(cid:…)`，因此"中文制度 PDF → 锚点"这条主链路没有端到端保护。
- 19 个 round13–20 测试只断言 `status==ok`（`keeps_modal/keeps_direction` 语义未验证）。
- 证据不同步：`evidence/round4/bundle-sync.log` 仍是 Round 12 的 493 passed / 69 files；`verify_local.log` 815KB 每次覆盖同名。
- 覆盖空白：`local_content.py` 45%、`sqlite.py` 45%、`runtime.py` 27%、`registry.py` 44%。

## 5. 执行应用层

### 5.1 落地

13 项全部注册、`source_file` 一致、无桩、统一走 `dataagent_runtime.invoke`；201 个测试全绿。

07 方案 v0.3.x 声称 r22–r32 修复的 19 类 SQL 走私（JOIN、HAVING、LIMIT、QUALIFY、TABLESAMPLE、ROLLUP、聚合参数变换、投影二次变换、时间窗端点、OR 中性化、DISTINCT/FILTER 等）经 22 个对抗探针实测**全部被拒绝**，合法形状（精确聚合、CAST、`SELECT *` CTE 透传、未读 CTE）全部通过——这部分修复是真的。

### 5.2 语义缺口（核心）

| 级别 | 位置 | 问题 | 复现 |
|-|-|-|-|
| P0 | `planning/expressions.py:1322-1395` | 守卫只校验"作用域内存在精确聚合"，不校验"交付的投影列就是该聚合"。任何不含聚合的投影（常量、标量子查询、`median`、窗口）直接放行，另一个 decoy 聚合即可满足绑定 | `SELECT region, 0 AS total, sum(amount) AS decoy …` → ok，交付 0，结果仍标 `m-r32`；`WITH ok AS (SELECT region,sum(amount) AS total …) SELECT region,0 AS total FROM ok` 同样通过 |
| P1 | `execution/sql.py:147,242,269` | `execute_duckdb_sql` 执行前只复检单 SELECT/表白名单，无口径复检；`semantic_versions` 由调用方直传写入结果 | 伪造 `ExecutableSpec(sql="SELECT region,sum(amount)*2 … WHERE approved=false")` + `semantic_versions=[m-r32]` → status=ok，交付 100，结果带 `m-r32` |
| P1 | `planning/expressions.py:1600` | 时间窗只在"恰好一个 metric 时间字段"时绑定；metric 未声明 `time` 时整段窗口校验被静默跳过 | 单 metric 无 time + `requirement.time=2026-01` → SQL 无窗口谓词仍 ok，交付 1540/900（应为 140/200） |
| P2 | `planning/expressions.py:1658` | 只校验 GROUP BY 含绑定维度，不校验维度被投影 | `SELECT sum(amount) AS total … GROUP BY region` 通过，结果无 region 列 |
| P2 | `planning/requirements.py:400` ↔ `expressions.py:802` | DA06.1.2 产出 `region eq ['north']`，DA06.3.1 只认 `= != >= <= > <`，该格式永远无法绑定，还会把合法 SQL 判拒 | — |
| P2 | `planning/expressions.py:825` | 字符串常量比较做 `.lower()`，`'Paid'` 被当作绑定 `'paid'` | — |

### 5.3 代码质量

4982 行 / 114 函数；`_collect_caliber_scope` 圈复杂度 71（267 行）、`sql_caliber_errors` 59（301 行）。SQL 校验用 sqlglot（duckdb 方言）+ DuckDB 执行，不存在自写 tokenizer，"两套解析器漂移"不成立。

| 级别 | 位置 | 问题 |
|-|-|-|
| P1 | `execution/sql.py:184-197` | 超时分支不可用：worker 持连接时主线程 `conn.close()` 抛 `ResourceInUseException`，`timeout` issue 永不返回；`Budget` 全字段可空 → 默认无超时 |
| P1 | `execution/sql.py:105,256` | `field_id` 直接拼进 `CREATE TABLE`，未转义；DuckDB 单次 `execute` 执行多语句，实测可建出 `pwn` 表 |
| P1 | `execution/expressions.py:333-347` | `and/or/not` 用 `is False` 判真，`and(True,"s")` → True、`not("x")` → False |
| P1 | `execution/expressions.py:551,698` | 求值入口不调用 `_walk_op`/`type_check`；`{"op":"field"}` → KeyError、3000 层 → RecursionError 逃逸出 operation |
| P2 | `presentation/workbooks.py:73` | 宣称只写值，实际以 `=` 开头的字符串被 openpyxl 写成公式；控制字符抛未捕获异常 |
| P2 | `planning/expressions.py:255` | `allowed_tables |= cte_names` 原地修改调用方 set |

### 5.4 测试与打包

- 201 passed；387 assert；"只断言 ok" 仅 11/157，且都与同文件负例配对；SQL 负例 13 个。
- 缺口：没有 decoy 形状的负例（这正是 P0 所在）；只有 5 个测试起真实子进程；157 个测试函数没有一个经过 `invoke()` 分发层；`test_execution_sql.py:116` 5 个负例只断言异常类型、不校验原因。
- bundle：src ↔ bundle 零漂移，dist 112,628B 解包与树逐字节相同，无 pyc/缓存；catalog 与 snapshot 的 sha256 可核对。但 `source-ref.toml` 没有 commit、源码归档、制品 digest；`source-ref` 记录的 kernel pin 为 `f0fa521`（落后 HEAD 168 commits）。
- 技能文档两处错误：`rule-execute/SKILL.md` 写 `satisfied/violated`（实际 `pass/fail`）；`compute-plan` 与 README 写"预算来自 Budget"（实际 `max_rows`/`max_seconds`，传 `budget` 会被 `extra=forbid` 拒）。
- `execute_duckdb_sql` 写 `computed_table` 却未标 `writes=True`，MCP 声明为 `readOnlyHint=true`。

## 6. 评测治理层

### 6.1 落地

6 项全部注册、`source_file` 一致、实现有实质；`check_result_grain_and_merge` 用 DuckDB 做粒度/Join/守恒/分页四检。运行时钩子的三态真实生效：

| 场景 | off | warn | enforce |
|-|-|-|-|
| 决策缺失/不可解析 | 放行 | 放行 + warning | failed `da12.access_denied` |
| 过期 / 资源不覆盖 / 用途不符 | 放行 | 放行 + warning | failed |
| `kernel_session_id` + 宿主声明 | — | — | 只校验存在，不校验有效期/用途 |
| 缺 EgressDecision | 放行 | 放行 + warning（内容照发） | 剥离部分内容 + `egress_required` |

但覆盖范围极不对称：声明 `resource_fields` 的 operation 数据层 22/32、治理层 1/6、应用层 0/13。

### 6.2 P0：治理层绕过自己的门禁

| # | 位置 | 问题 | 复现 |
|-|-|-|-|
| 1 | `runtime/runtime.py:44` | bootstrap 用合成资源 `table@*` 求值，从不评估真实资源 | 策略含 `allow table` + `deny table:salaries` 时，`access_resolver("policy:x")` → allow，`_ref_covers` → True |
| 2 | `governance/access.py:302` | `visible_fields` 只写进 EgressDecision，从不裁剪 payload | 规则约束 `[region, amount]`，vendor_api 产物仍含 `cost_price=42.5` |
| 3 | `governance/access.py:121-133` | `_table_anchor` 信任内容自报的 `sheet` 作为来源 | 伪造 `{"sheet":"orders", ... salaries}` 的 `_content_covered=True` |
| 4 | `governance/sensitivity.py:29-32` | `\b` 与 CJK 同属 `\w`，身份证紧贴中文即不匹配；`+86`、`138-0013-8000`、空格分组卡号漏报，mask 原样返回 | 主代理复现：`身份证11010519491231002X` → []；`+8613800138000` → []；`6222 0212 3456 7890` → []；只有 `a@b.com` 与裸手机号能识别 |

### 6.3 P1 级缺陷

| # | 位置 | 问题 |
|-|-|-|
| 1 | `helpers.py:286` + `enforcement.py:330` + `access.py:303` | 三层都不传 `load_masked`，`masking_ref` 存的是 mask_id，`allow_masked` 永远走不通 |
| 2 | `enforcement.py:179` vs `helpers.py:115` | 运行时只剥 `"content"` 键，应用层有 14 个内容键；enforce 下 `statement/conditions/metrics` 仍可能残留 |
| 3 | `.mcp.json:11-13` + `runtime.py:111` | 未注入宿主主体/用途，`_authority` 回退到调用方可写的 `arguments.context`——Agent 可自选 `subject_ref/purpose` 取得 allow；08 v0.1.1 B7 的"宿主权威"实际未生效 |
| 4 | `adapters/local_split_vault.py:209` | `add_samples` 无条件写 `frozen=False`，冻结集可被解冻 |
| 5 | `local_split_vault.py:248` | 金标门禁是调用方自报的 purpose 字符串，任意调用方传 `evaluate_business_acceptance` 即可读金标，暴露台账零增量 |
| 6 | `evaluation/criteria_samples.py:679` | `unknown_policy=report_separately` 时 unknown 仍留在分母（3 例全 unknown → pass_rate=0.0，fail） |
| 7 | `criteria_samples.py:683` | 阈值 0.0 时 `pass_rate>=0.0` 恒真，唯一用例 fail 也判 pass |
| 8 | `criteria_samples.py:755` | `Coverage(covered=len(cases), total=len(eligible))` 恒等 1 |
| 9 | `sensitivity.py:147,351` | `next(iter(ids))` 遍历 set，`MaskedEntry.field` 随 `PYTHONHASHSEED` 变化（seed 1–5 交替输出两种标签） |
| 10 | `policy/evaluator.py:147` | `allows[0]` 先到先得，脱敏义务取决于规则顺序 |
| 11 | `adapters/local_policy.py:36` | `load(None)` 硬编码 `tenant:default` |
| 12 | `evaluation/computation.py:341,422` | 空集记 unknown 但未计入 `unanalysed`；度量守恒只对首表求和 |
| 13 | `tests/` | 08 §10.2 要求的"过期决策被拒"零用例；`PolicyRule.valid_until` 只写入 decision，不拒绝到期 allow；warn 模式零用例 |

### 6.4 测试、fixtures 与文档

- 117 passed / 324 assert；负例总体扎实（deny 优先、indeterminate、用途不符、资源不覆盖、allow_masked、缺依据/超时/计分）。
- MCP 端到端很薄：6 例经 `mcp_server.handle` 进程内调用，0 例走真实 stdio；`fixtures/` 只有 README，策略/样本/金标全是内联玩具字典（4 条规则、`{"gold": case_id}`）。
- 08 方案 `status: 待评审`、§2 仍写"共享运行时 待做 / P2 待定案 阻塞 DA12.1"，与 117 个测试、6 个工具、bundle/preset/e2e 均已存在矛盾——是文档滞后且缺评审记录（无 `08-*` 记录目录）。

## 7. 契约与共享运行时

### 7.1 dataagent-contracts

- 35 个具体类型 + 2 个泛型，无缺失/多余；仅依赖 pydantic，无反向依赖；68 个 schema 再生成零漂移；examples 5 个全部通过模型与 jsonschema。
- P1：开放枚举在嵌套 schema 中被封闭——`EvidenceRef.json`/`MetricDefinition.json` 的 `$defs` 拒绝文档允许的 `acme.weighted_mean`，Python 模型却接受；只有独立 enum 文件是开放联合。
- P1：`ExecutableSpec` 的"封闭 AST"只在 docstring，`semantics.py:233` 仅检查 `op` 键存在，`{"op":"eval_js"}` 通过。
- P2：`Assessment` 无证据门（`fail` + 空 `basis_refs` + `evidence=[]` 通过，`verdict="totally_bogus"` 也通过）；`sql_digest` 不校验 `sha256:<hex>`；除 refs 外模型可变（校验后改 `status` 可造出非法载荷）。
- 计数口径不一致：05 §3.2 表相加为 34+2=36，代码/文档正文称 37；`EngineBinding` 既作内嵌又单出 schema。

### 7.2 dataagent-runtime 与 W0 接缝

- 三层确实复用：data 22/44 模块、app 11/17、gov 9/34 import runtime；gov 复用度最高。
- P1：访问复检 fail-open——`resource_fields` 的值映射不出 `VersionedRef`（如 str）时返回空 ref 列表，复检无 ref 可查即放行。
- P1：`gold_ledger` 无锁整文件读改写；20 线程 `note_exposure` 只落 2 条，`_load` 遇损坏静默重置。
- P2：resolver 异常、非法 issue 的 `CapabilityResult` 校验错误都会逃出 `invoke`；裸 `Exception` 一律映射为 `execution_unknown` + "inspect the input"，把编程错误伪装成输入问题。
- P2：`local_content.get` 不校验摘要（篡改后静默返回错字节）、丢弃 `media_type`；决策表 `INSERT OR REPLACE` 可覆写。
- P2：应用层 `mcp_server.py` 不传 runtime，落 `runtime.sqlite3`，与 data/governance 的版本库不共享。
- P2：数据层保留了一份 94 行的 `local_content` 与 496 行 sqlite 适配器，与 runtime 版本仅注释差异；`save()` 语义漂移（data 幂等短路、runtime 总追加）。
- W0 六项：1.1 表 codec、1.2 name↔field_id、§2 三值真值表、§3 单表计划 Schema 已落地且有测试；§4 basis_refs→EvidenceRef 只有构造、无解析器；§5 模型可见边界只有应用层自剥、运行时 gate 不认识 14 个内容键；§6 P2/kernel guard 声明通道产品不可达。

## 8. 发布、端到端与 benchmark

- 端到端：scenarios 12 项全过，两条族链路真起子进程，断言到业务结论（`overall=pass`、`value==600.0`、p95=640），不是只断言 status。但三个 bundle 都由 `python -m` 拉起，没有走 `.mcp.json` / `uv --project $PKG`——发布包的启动路径未被测试覆盖。
- preset：本地 `mint add path:… --offline` 可装 4 个包、无循环；但三条依赖全是相对 path，只有 application 有 dist，data/governance 无 dist；`mint pack` 出的 preset 仅 5,070B 且依赖仍指向 `../dataagent-*`，不可异地发布。
- README 的离线步骤在干净机上不可复现：`mint init --no-preset --offline -y` 报"离线且本机没有满足 ^0.1（std）的内核"。
- benchmark：可运行骨架（`run.py`/`grade.py` 可执行、能出 scorecard）；15 个任务、B01–B14 各 243 case、3217 份 expected、39 个数据集；但 B05–B15 缺 34 个 grader、0 个正式轮次、`dataagent` CLI 不存在，B15 只有 3 case。

## 9. 横向问题：门禁、溯源、文档

1. **没有工程门禁**：全仓无 CI、ruff、mypy、coverage 配置；测试只靠人工跑；无 `-W error`、无依赖审计。
2. **不可追溯**：AgentOS 根目录不是 git 仓库（`git status` 报 not a git repository），评审结论无法钉到 revision；唯一完整性证据 `dataagent-data/evidence/round4/manifest.sha256` 只覆盖文档字节，不覆盖代码。
3. **kernel 引用过期**：文档与 source-ref 均 pin `agent-kernel@f0fa521`，实际 HEAD `c1231ab` 领先 168 个 commit；文档引用的 `mint-runtime-launch.sh:351-363` 在 HEAD 已移位（292 行）。"host 无 MCP""tool.execute=SideEffect"等结论在 HEAD 仍成立，但行号不可复核。
4. **文档数字与状态滞后**：06 写"数据层 560 测试"（实测 649）；07 写 r27 13 个测试（实测 14）、"按需 90 / S1 7"（Catalog 非 FDE 口径 93/4）；08 仍"待评审"；05 写 66 schema（实际 68+index）、`ExecutableSpec` 归属自相矛盾；06 §12 记录索引只到 r17，r19–r21 未登记且目录无 README。
5. **仓库卫生**：源码树内有 349 个 `.pyc`、48 个 `__pycache__`、多个 `.pytest_cache`、空 `.claude/.cc-writes`；治理层 `.gitignore` 未忽略 `.dataagent/`，运行时会在包内落 `decisions.sqlite3` 与 `vault/` 金标；`evidence` 里存在 98B 纯点号日志与过期日志。
6. **"零漂移"门禁名不副实**：只有 application 的 `test_bundle_sync.py`，且只比 `*.py`；本次人工比对三包×三模块 9 组全部一致，但这依赖人工。

## 10. 修复优先级

### P0（未修不应宣称 S0 验收）

1. **应用层交付列绑定**（`planning/expressions.py:1322-1395`）：每个绑定度量必须在顶层投影以裸聚合或值保持 CAST 出现；禁止常量/标量子查询/未映射函数/窗口作为度量列；绑定维度必须被投影。
2. **执行侧复检或 provenance 绑定**（`execution/sql.py:147`）：`execute_duckdb_sql` 复算口径，或只接受带生成回执（SQL digest + requirement）的 spec，禁止调用方直传 `semantic_versions`。
3. **治理层列级约束**（`governance/access.py:302,232`）：按本决策的 `field_constraints` 投影后再 `put`；敏感字段取自本决策的 `masking_obligations`，不取全策略。
4. **治理层资源锚点**（`runtime/runtime.py:44`、`access.py:121`）：用真实资源求值，不信任内容自报的 `sheet`/类型。
5. **敏感识别与 `allow_masked`**（`sensitivity.py:29-32`、`enforcement.py:330`）：修 CJK/`+86`/分隔符漏报；三层接线 `load_masked`，让 `allow_masked` 真正替换内容。
6. **统一 enforce 姿态**（`dataagent-application/.mcp.json`、`dataagent-data/interfaces/cli.py`）：应用层补 `enforce`，CLI 显式 enforce 或拒跑；治理层注入 `DATAAGENT_HOST_SUBJECT_REF/PURPOSE`；CI 断言禁止任何 bundle 回落到 warn。
7. **数据层编码探测**（`delimited.py:13,23`）：latin-1/cp1252 前置或先判 CJK 字节分布，消除静默乱码。

### P1（S0 交付前）

8. 数据层与 OCR/PDF 的页/行/字节预算，xlsx 改 `read_only=True`，OCR 逐页渲染。
9. SQL 超时可中断（`conn.interrupt()`/子进程），`Budget.max_seconds` 给非空默认；`field_id` 转义并禁止多语句。
10. 表达式运行时类型闸门（bool 断言 + `_walk_op` 入口校验）。
11. 时间窗绑定与过滤条件结构化（去掉 `eq` 文本往返）。
12. `gold_ledger` 改追加写 + 文件锁（或 SQLite）；样本冻结不可被 `add_samples` 解冻；金标读取改身份校验。
13. 决策库/宿主权威：`decisions.sqlite3` 权限收紧或加 MAC；`load(None)` 按主体解析，不落 `tenant:default`。
14. 发布：补 data/governance 的 dist 与 preset 版本约束；`source-ref` 增加 commit/源码归档/制品 digest；修 README 离线步骤。

### P2（下一个迭代）

15. 契约：开放枚举在嵌套 schema 内真正开放；`ExecutableSpec` 补算子白名单或删除承诺；证据门与 `sql_digest` 校验；统一 37 的计数口径。
16. 文档：06/07/08 的数字、状态、记录索引与 Catalog 口径对齐；补 `06-data-layer-build/README.md` 与 08 评审目录；kernel 引用更新到 HEAD。
17. 测试：补 decoy 负例、过期决策、warn 模式、真实 CJK PDF、安装后 bundle 启动、并发读写 decisions.sqlite3；把端到端改为经 `.mcp.json` 启动。
18. 工程：加 CI（pytest + ruff + mypy + schema --check + bundle --check）、`.gitignore .dataagent/`、清理 pyc/缓存、证据日志带命令与时间戳。
19. benchmark：补 B05–B15 的 34 个 grader、真实 CLI 适配器、第一轮 r 基线。

## 11. 边界与未验证

- 未联网核对 Mint 上游行为：`uv run --frozen` 在 Mint 清空环境后的就绪、项目级 `.mcp.json` 覆盖语义、`$PKG` 展开均未实测。
- 未用真实 Mint loader 拉起三个 MCP；端到端只用 `python -m` 子进程。
- OCR 真实引擎（rapidocr）未安装，只验证 `dependency_unavailable` 分支；大图/扫描件未压测。
- 未跑完整 benchmark；B15 数据缺失。
- 未做 git 历史核对（根目录非 git）；kernel 仅记录 HEAD，未按 AGENTS.md 执行 fetch/`sync-iface-packages.sh --check` 后再对比 iface。
- 所有 P0 复现均在 `/tmp` 探针或进程内调用完成，未在生产 Mint 宿主复核。

## 12. 复核命令

```bash
# S0 能力面
python3 - <<'PY'
import json
c=json.load(open('docs/research/dataagent-2026-11-03/catalog/atomic-capability-catalog.json'))
print([ (a['layer'],a['operation']) for a in c['atoms'] if a.get('s0_family')][:3])
PY

# 六包测试
for p in dataagent-contracts dataagent-runtime dataagent-data dataagent-application dataagent-governance dataagent-scenarios; do
  (cd packages/capabilities/$p && .venv/bin/python -m pytest -p no:warnings | tail -1)
done

# bundle 漂移与 pyc
for p in dataagent-data dataagent-application dataagent-governance; do
  diff -rq -x '__pycache__' packages/capabilities/$p/src packages/capabilities/$p/packaging/bundle/src
done

# 编码 P0
cd packages/capabilities/dataagent-data && .venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'src')
from dataagent_data.adapters.parsers.delimited import ENCODINGS
raw="nom,région\n".encode("cp1252")
for e in ENCODINGS:
    try: print(e, '->', raw.decode(e))
    except Exception: print(e,'FAIL')
PY
```
