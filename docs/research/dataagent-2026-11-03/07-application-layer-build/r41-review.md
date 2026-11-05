---
round: 41
date: 2026-11-05
subject: dataagent-application 的完成度与质量评审
kernel: agent-kernel@c1231ab（本地 HEAD，未 fetch；source-ref 记为 f0fa521）
tests: application 201 passed
---

# Round 41 评审：执行应用层

范围：`packages/capabilities/dataagent-application`。对数据层、runtime、contracts 只核对接口对接。跨包共性问题见 [08 r41-review.md](../08-governance-layer-build/r41-review.md) §1（X1–X5）。

| 项 | 结果 |
|-|-|
| 规模 | src 17 文件 / 4,982 行（另有 `catalog-snapshot.json` 127 行）；tests 21 文件 / 4,856 行 |
| 测试 | `.venv/bin/python -m pytest -p no:cacheprovider -o addopts=''`：201 passed |
| 注册 | `mcp_server --validate-only`：`registry OK: 13 operations`；`source_file` 与 Catalog 一致 |
| 制品 | 三包 vendoring 后与源码 diff 为零；dist `tar.zst` 解包与 `packaging/bundle/src` 一致；bundle `uv.lock` 不引用兄弟路径 |
| 入口 | MCP `tools/list` 由注册表生成，13 项有黑盒测试；Skills `compute-plan`、`rule-execute` 覆盖 13 项 |

结论：13 项接口齐全，口径校验覆盖了 r20–r32 的全部走私形状，但存在 4 个高危：口径校验可整体绕过、无访问复检、固定过滤语义不闭合、不支持的条件按 true 求值。S0 记为 5 项已完成、8 项部分完成。

## 1. S0 完成度

| 原子 | 名称 | 状态 | 证据 |
|-|-|-|-|
| DA06.1.1 | 指标与维度绑定 | 已完成 | `requirements.py:184`；12 个测试文件引用；name→field_id 已解析 |
| DA06.1.2 | 时间与过滤解析 | 部分完成 | `requirements.py:329`；输出过滤文本 `c4 eq ['已支付']`（`:400`）不能被 DA06.3.1 消费（A3） |
| DA06.1.3 | 计算歧义识别 | 已完成 | `requirements.py:430`；确定性兜底补 `time_boundary`、`unit` 警告 |
| DA06.1.4 | 澄清问题生成 | 已完成 | `requirements.py:545`；blocking 歧义未答返回 `needs_input` |
| DA06.3.1 | 单表 SQL 生成 | 部分完成 | `planning/expressions.py:1764`；`requirement` 可省略，不拦 blocking 歧义（A1、A3、A7） |
| DA06.3.5 | 函数调用与表达式生成 | 部分完成 | `planning/expressions.py:531`；combination 真值表比对已实现；unsupported 条件按 true（A4） |
| DA07.1.3 | 本地 DuckDB 执行适配 | 部分完成 | `execution/sql.py:114`；external access 关闭、配置锁定、只载明细行；执行前不复核口径，超时路径失效（A1、A5） |
| DA07.5.1 | 标量表达式计算 | 已完成 | `execution/expressions.py:544`；三值逻辑、gate 顺序、`low_confidence` 警告 |
| DA07.5.2 | 表数据表达式计算 | 部分完成 | `execution/expressions.py:691`；截断后总体 verdict 可为 pass（A6） |
| DA07.10.1 | 引擎获取与版本对齐 | 部分完成 | `execution/engines.py:183`；版本比对可用；wheel 校验和不可验证，`dataagent-expression` 别名被拒（A10） |
| DA10.1.1 | 结果工作簿生成 | 部分完成 | `presentation/workbooks.py:55`；三张表齐全；`=` 开头字符串写成公式（A8） |
| DA10.3.1 | 文档报告生成 | 已完成 | `presentation/reports.py:87`；section 的 `evidence_refs` 须有对应 EvidenceRef |
| DA10.3.3 | 报告格式导出 | 部分完成 | `presentation/reports.py:248`；md 带依据锚点，html / docx 丢失依据段（A11） |

## 2. 按需与 S1

Catalog 中执行应用层 126 项：S0 13，按需 102（非 FDE 93、FDE 9），S1 11（非 FDE 4、FDE 7）。

| 范围 | 数量 | 已实现 | 说明 |
|-|-|-|-|
| 按需非 FDE | 93 | 0 | 11 项的 Catalog 源码文件因与 S0 共用而存在，未注册 operation：DA06.3.2–3.4、DA07.1.1–1.2、DA07.10.2–10.3、DA10.1.2–1.4、DA10.3.2；`retrieval/`、`analysis/`、`prediction/`、`ports/`、`adapters/` 目录不存在 |
| S1（DA05.8 4 项、DA07.4 3 项） | 7 | 0 | DA05.8 指向的 `retrieval/components.py` 不存在 |
| FDE | 16 | 0 | 按范围排除 |

## 3. 可行性评审与 W0 接缝落实

| 缺口 | 状态 | 证据 |
|-|-|-|
| 评审 §3 / W0 §1：版本化表 codec、行角色、合计行不重复计数 | 已修复 | runtime `ports/tabular.py:118`；应用层只经 `helpers.load_table` 读表，执行与求值走 `detail_rows()` |
| W0 §1.2：name↔field_id | 部分修复 | DA06.1.1 已解析；DA06.1.2 只接受 field_id（`requirements.py:378`） |
| 评审 §4 / W0 §2：规则执行顺序、三值真值表、四种 verdict | 部分修复 | gate 顺序与 Kleene 逻辑已实现；applicable / preconditions 是调用方传入的布尔值，`rule.applicability_ref`、`precondition_refs` 不被消费；新缺陷 A4、A7 |
| 评审 §5 / W0 §3：SQL 绑定口径 | 部分修复 | `sql_caliber_errors` 覆盖 r20–r32 全部形状；只在提供 requirement 时运行，执行侧不复核，blocking 歧义不拦；新缺陷 A1、A3 |
| 评审 §6 / W0 §4：`Assessment.evidence`、`ComputedResult.sql_digest/engine_binding`、`basis_refs` 解析 | 部分修复 | 字段已入 core；`spec:<id>` 对应的 ExecutableSpec 不持久化，spec_id 不含 AST；新缺陷 A9 |
| 评审 §7 / W0 §6：访问复检、P2 mint-core 完整复检 | 未修复 | 13 个 op 均未声明 `resource_fields`，`invoke.py` 复检与闭包校验不触发（A2） |
| 评审 §8 / W0 §5：模型可见输出边界 | 部分修复 | 两段式 `inference_request` 已过 gate；enforce 下剥离内容；`content_refs` 按内容寻址绑定（r38/r40）；默认 warn 且 bundle 未注入 enforce（X3）；InferencePort 零调用；ok 结果（表值、报告）经 MCP 回给 Agent，不受 gate 约束 |
| 评审 §11：Mint 独立制品 | 部分修复 | vendoring 与 dist 一致；未在真实 Mint loader 下安装，未覆盖自定义 data_root，无离线 wheel 预取 |
| 07 §5.4：wheel 哈希取自 uv.lock | 未修复 | A10 |
| 07 §11.4：与数据层联调 | 未修复 | tests 无 `dataagent_data` 导入；两族链路用手造夹具（`test_scenarios.py`） |

## 4. 新缺陷

| # | 严重度 | 确认/疑似 | 位置 | 问题 | 复现 |
|-|-|-|-|-|-|
| A1 | 高 | 确认 | `execution/sql.py:131-149`、`:233-254`；`planning/expressions.py:1569`、`:1880` | 口径校验可整体绕过：DA07.1.3 接受任意 SQL spec，执行前不复核，`semantic_versions` / `filters_applied` 由调用方填写并原样写入 ComputedResult；DA06.3.1 不传 `requirement` 时跳过校验；`metrics` 省略时度量校验经 `if draft is None: continue` 跳过；blocking 歧义与 unresolved 不拦生成 | `r1_caliber_bypass.py`：伪造 spec `SELECT sum(c2)` 带 `draft:metric:paid@r1` 与过滤 `状态='已支付'` → ok，value=340（正确口径 140）；不传 requirement，`max(c2) WHERE c4='已退款'` → ok；`metrics=[]` 加 `max(c3)` → ok；带 blocking 歧义 → ok |
| A2 | 高 | 确认 | 注册表（13 个 op 的 `resource_fields` 为空，如 `execution/sql.py:114`、`execution/expressions.py:691`、`planning/expressions.py:1764`） | 读 TableRef 内容不做 DA12.1 复检与 asset↔`data_ref` 闭包校验；enforce 下不可解析的 `authorization_ref` 也能读整表 | `r2_no_access_recheck.py`：`ops with resource_fields: []`；enforce + `authorization_ref="nope"`，execute → ok，rows=3；`asset.revision` 指向另一 digest、`data_ref` 指向真实表，`evaluate_table` → ok |
| A3 | 高 | 确认 | `planning/expressions.py:1677-1729`；`requirements.py:398-404` | 固定过滤语义不闭合：`referenced_fields=[]` 的过滤（数据层 `metrics_rules.py:398-405` 字段不可解析时产出）被静默丢弃，不带过滤的 SQL 通过，带过滤的正确 SQL 被判 extra WHERE；非 `field op value` 形式的过滤（含 DA06.1.2 自身产出的 `c4 eq ['已支付']`）不可满足：存在性检查要求该列出现在 WHERE，闭环检查又拒绝该列任何谓词 | `r6_unref_filter.py`：`支付状态='已支付'`、refs=[]，`SELECT sum(c2)` → ok，加 `WHERE c4='已支付'` → failed；`r4_seams.py` a/a2：DA06.1.2 输出放入 requirement，三种 SQL 均 failed |
| A4 | 高 | 确认 | `planning/expressions.py:490-499`、`:736-745` | 声明为 unsupported 的条件以 `?true` 代入 combination，ExecutableSpec 不记录未编译条件；人工判定需求只留在 DA06.3.5 的一条 warning；与方案 §12 “不支持的条件返回 `needs_input`” 不符 | `r3_rule_semantics.py` a：`c1 and c2`，c2 unsupported，状态 partial；对 amount=6200、approver=missing 的记录求值 → pass（应为 unknown） |
| A5 | 中 | 确认 | `execution/sql.py:178-199` | 超时后 `conn.close()` 时查询线程仍占用连接，抛 `ResourceInUseException`，映射为 `execution_unknown` 而非 `timeout`；未调用 `conn.interrupt()`，查询跑到结束，进程退出被阻塞 180s 以上；无超时测试 | `r5b.py`：递归 CTE + `max_seconds=1`，1.0s 后 failed / `execution_unknown`，消息 "connection is busy with another call"；`r5_exec.py` 进程 180s 未退出 |
| A6 | 中 | 确认 | `execution/expressions.py:773`、`:819-824` | `max_rows` 截断后总体 verdict 只看已求值行；status 为 partial，`Assessment.verdict` 为 pass | `r3_rule_semantics.py` b：两行（6000、10），规则 amount>5000，`max_rows=1` → overall=pass |
| A7 | 中 | 确认 | `planning/expressions.py:1408-1427`、`:1625` | 时间窗端点只比 `YYYY-MM-DD` 前缀；非零点窗口与带时区窗口被整日 SQL 通过，行集不同而 `metric_version` 相同 | `r4_seams.py` b：from=`2026-01-15T12:00Z`，SQL `>= '2026-01-15'` → ok；窗口 `+08:00`、SQL 无时区 → ok |
| A8 | 中 | 确认 | `presentation/workbooks.py:73-75` | `=` 开头的字符串被 openpyxl 写成公式，违反只写值，构成公式注入 | `r4_seams.py` c：`=HYPERLINK("http://x","点我")`、`=1+1` 的 `data_type` 为 `'f'` |
| A9 | 中 | 确认 | `planning/expressions.py:721`、`:737`；`execution/expressions.py:584`、`:656` | spec_id 只由 statement 与字段集合计算，revision 恒为 r1，不同 AST 得同一 `id@r1`；ExecutableSpec 不持久化，`basis_refs=["spec:<id>"]` 不可解析；同一 spec 对不同记录产出相同 `assessment_id` 与 `target_ref`；exception spec 无 `engine_binding` | `r5_exec.py` b：阈值 5000 与 50 均为 `expr:6d951411f9ac4e0c@r1`；`r3_rule_semantics.py` d：两条记录 `as:expr:1c79…` 相同；e：`exception_specs[0].engine_binding=None` |
| A10 | 中 | 确认 | `execution/engines.py:43-46`、`:175-180`、`:193` | `distribution._path` 是 dist-info 目录不是 .whl，任何安装方式都落到 not a wheel 分支；不读 uv.lock 哈希；DA06.3.5 写入的 `engine_id="dataagent-expression"` 不能直接传给 acquire（只接受 `expression`） | `r4_seams.py` e：duckdb wheel 安装、传 uv.lock 哈希 → failed / `da07.engine_digest_unavailable`；`engine_id=dataagent-expression` → `invalid_input` |
| A11 | 低 | 确认 | `presentation/reports.py:177-201`、`:204-238` | html / docx 导出不输出 `draft.evidence`；只有 md 有依据段 | `r4_seams.py` d：md 含 `doc-9@r7`，html 不含 `doc-9` |
| A12 | 低 | 确认 | `requirements.py:158`、`:470`；`planning/expressions.py:655`、`:680`、`:1775`；`execution/expressions.py:331-347`、`:561-565` | 嵌套模型 ValidationError 映射为 `execution_unknown`；省略 `fields` 时跳过字段存在性与类型检查；and/or 操作数为非布尔值时按真假值处理 | `r4_seams.py` f：坏 draft / ambiguity / table_ref → `execution_unknown`；`r3_rule_semantics.py` c：无 fields 的编造字段 → ok；f：`and("张三")` → pass，`or("张三")` → fail |

## 5. 测试覆盖缺口

- 201 例中约 70 例集中在 DA06.3.1 口径走私形状（r22–r32）；`parse_time_and_filters`、`identify_calculation_ambiguities`、`generate_clarification_questions`、`evaluate_table_expression` 各只在 1 个文件出现。
- 无负例：超时与预算；enforce 下的访问复检（无一测试涉及 `resource_fields` 或 `access_denied`）；不传 requirement / metrics 的 SQL 生成；DA07.1.3 拒绝伪造 spec；DA06.1.2→DA06.3.1 对接；截断后的 verdict；工作簿公式字符串；html / docx 依据段。
- `test_scenarios.py` 用手造 TableRef 与 MetricDefinition，不经数据层真实产出。
- `test_bundle_sync.py` 只校验源码同步与无 pyc，不安装制品，不经 Mint loader 启动。
- 直接 `.venv/bin/pytest` 有 3 个 collection error，须用 `python -m pytest`。

## 6. 复现

脚本在 [r41-repro/](r41-repro/)：`repro_common.py`（夹具）、`r1_caliber_bypass.py`（A1）、`r2_no_access_recheck.py`（A2）、`r3_rule_semantics.py`（A4、A6、A9、A12）、`r4_seams.py`（A3、A7、A8、A10、A11、A12）、`r5_exec.py` / `r5b.py`（A5、A9）、`r6_unref_filter.py`（A3）。

脚本把 `/tmp/claude-502/application` 写死为 `sys.path` 与临时目录，`r4_seams.py:83` 含本机绝对路径。运行：

```bash
mkdir -p /tmp/claude-502/application && cp docs/research/dataagent-2026-11-03/07-application-layer-build/r41-repro/*.py /tmp/claude-502/application/
cd packages/capabilities/dataagent-application && .venv/bin/python /tmp/claude-502/application/r1_caliber_bypass.py
```

`r5_exec.py` 会阻塞约 180s（A5）。
