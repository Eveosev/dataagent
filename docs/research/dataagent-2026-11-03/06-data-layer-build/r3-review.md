---
round: 3
date: 2026-11-03
subject: Round 3 后的实现
score: 5.5/10
---

# Round 3 评审

范围：`packages/capabilities/dataagent-contracts`、`packages/capabilities/dataagent-data`（不含 `packaging/bundle/` 复制品）。测试 84 + 105 全部通过；注册表 32 项与总 Catalog 一致；bundle 复制品与源码一致。

## 1. 评分

| 维度 | 分 | 依据 |
|-|-|-|
| 方案符合度与架构 | 8 | 端口/适配器分层；注册表由 handler 模块推导 `source_file` 并校验快照；bundle 自包含 |
| 运行时与入口 | 7 | 错误统一映射为 `CapabilityResult`；坏 JSON、未知方法不退出；mint-core 经 `server/discover` 回退 `initialize` 可握手 |
| 安全边界 | 7 | 拒绝绝对路径、`..`、符号链接越界；无网络；OCR 缺失返回 `dependency_unavailable` |
| 契约包 | 6 | 36 个类型齐全，schema 与类型同步；命名空间、必填性、验收约束与 05 有偏差 |
| 存储与并发 | 5 | 内容寻址原子写；并发控制只在单进程内有效 |
| 能力正确性 | 4 | 表头识别、合并单元格、bbox 取页有缺陷 |
| 证据与锚点可信度 | 3 | 非 PDF 选择器只做格式检查 |
| 测试质量 | 6 | 断言有效，几乎只覆盖正向路径 |
| 可维护性 | 6 | 长函数、重复实现、魔数、临时文件不清理 |
| **综合** | **5.5** | |

## 2. 问题

| 级 | # | 问题 | 位置 |
|-|-|-|-|
| P0 | 1 | 非 PDF 选择器（`text_span`、`json_pointer`、`excel_cell`、`record_key`）只做格式检查，编造值可以 `extracted` 落库；`value=None` 加任意 PDF 区间判为 `extracted`；指标与适用范围的 `sources` 不核验；规则条件文本不核验原文；无锚点 exception 被接受 | `runtime/anchors.py:49-58,188`；`semantics/metrics_rules.py:104,352-363`；`semantics/applicability.py:85` |
| P0 | 2 | `anchor_extracted_values` 不校验记录、文档、锚点三者是否同一文档；按首次出现重定位，数字分词会从日期中取出 `-05` | `preparation/extraction.py` |
| P0 | 3 | 多行表头判断写反：表头之后的行不是“主要为数值”就并入表头，纯文本表丢失数据行；无空格、无重复的两行表头识别为单行；合并表头不向下展开 | `preparation/structure.py:66-72,263` |
| P0 | 4 | 删除空行后行坐标错位，合并单元格展开静默跳过；`formula_text` 策略每个公式误报无缓存，`cached_values` 无缓存时公式文本作为值写入 | `ingestion/files.py:124,129-135`；`preparation/structure.py:102,259` |
| P1 | 5 | `pdf_bbox` 按页列表下标取页，配合 `pages` 子集时 IndexError → `execution_unknown`；PDF 行定位失败时退回游标，生成错误字符区间；OCR 像素坐标与 PDF point 坐标混用 | `runtime/anchors.py:45,167`；`adapters/parsers/pdf.py:55-57` |
| P1 | 6 | 契约命名空间用 `:`，05 规定 `.`（`da02.weighted` 被拒、`acme:w` 被接受）；`extensions` 键、`Issue.code` 不校验；开放枚举在 JSON Schema 中导出为封闭枚举；开放枚举缓存无上限 | `contracts/core/vocab.py:116-120`；`_base.py:20`；`envelope.py:58`；`scripts/generate_schema.py:93` |
| P1 | 7 | 必填字段带默认值而变为可选：`Issue.severity`、`Issue.retryable`、`FieldValue.value_type`、`SchemaRef.inference_basis`、`RuleDefinition.combination`、`SemanticDraft.status`；0.1.x 冻结后不能再收紧 | `contracts/core/envelope.py:59,63`；`data.py:44,126`；`semantics.py:51,126` |
| P1 | 8 | 缺约束：`failed` 无 issue 可通过；`extracted` 且 `value=None` 可通过；`AcceptanceReport` 不检查判据 `active`、样本 `unseen_acceptance`；接受无时区 `datetime`；schema 无带版本的 `$id`；`VersionedRef` 解析与 pattern 不一致 | `contracts/core/envelope.py:127-145`；`data.py:134`；`evaluation.py:144-150`；`refs.py:46,58` |
| P1 | 9 | 并发只靠进程内 `threading.Lock`：版本号按“条数 + 1”、轨迹 cursor 先查后插，多进程写入主键冲突 → `execution_unknown` | `adapters/storage/sqlite.py:133-178,202-245` |
| P1 | 10 | 存储层版本冲突抛 `ValueError`，`invoke` 映射为 `invalid_input`；README 称返回 `version_conflict` | `adapters/storage/sqlite.py:144`；`runtime/invoke.py:124` |
| P1 | 11 | `read_from` 把任务流与内核会话的事件合并后按 cursor 排序，偏离 `StoreContract` 按会话游标的语义；同 `event_id` 不同内容静默返回首条 | `adapters/storage/sqlite.py:219-221,260-275` |
| P2 | 12 | `invoke` 把处理函数内的所有 `ValueError` 归为 `invalid_input`，内部缺陷被报成用户输入错误 | `runtime/invoke.py:124-137` |
| P2 | 13 | `OperationSpec.writes` 未使用，MCP 审批弹窗问题未处理；`InferencePort` 未接入任何原子；抽取记录与可判定性结果未写入 VersionedRepository | `runtime/registry.py`；`interfaces/mcp_server.py`；`preparation/extraction.py`；`semantics/decidability.py` |
| P2 | 14 | 可判定性：`auto` 带 `unknowns` 不降级；缓存键不含 statement 与需求修订号；无修订号时补 `r1`；适用性前置条件规范化去掉 `.`，`1.5万` 与 `15万` 合并；`is` 比较字符串 | `semantics/decidability.py:94,109,261`；`semantics/applicability.py:270,315` |
| P2 | 15 | 解析细节：CSV 回退 latin-1 无警告、列数不符的行仍留在表中；JSON 路径未按 RFC 6901 转义；`dedupe_names` 仍可能重名；带引号的 sheet 名区域被忽略；文档标题正则误判、`1.` 与 `1.1` 无法关联；找不到位置时伪造 `(1,0,0)` 锚点 | `adapters/parsers/delimited.py:23,49,68-71`；`json_records.py:33`；`excel.py:114-124`；`ingestion/files.py:243`；`preparation/documents.py:155,158,201` |
| P2 | 16 | 工程卫生：`test_schema.py` 运行时改写 `schema/generated`；包目录残留运行数据 `.dataagent/`，`.gitignore` 未排除；`_materialize` 临时文件不清理；`extract_irregular_excel`、`extract_fields_to_schema` 各约 200 行；降级逻辑约 4 处重复 | `dataagent-contracts/tests/test_schema.py:29-34`；`dataagent-data/.gitignore`；`ingestion/files.py:216-392` |
| — | 17 | 方案 §10 第 4 项（隔离 `MINT_HOME` 安装并列出工具、`mint run --json`）未验证 | — |
