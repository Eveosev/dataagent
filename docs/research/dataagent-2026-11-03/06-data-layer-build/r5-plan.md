---
round: 5
date: 2026-11-04
status: 已执行（B1–B3、P1/P2 修复；见 r5-fixes.md）
basis: r4-review.md
kernel: agent-kernel@f0fa521
---

# Round 5 优化方案

按序执行。每项的完成标准：新增反例测试通过，原有测试不回退，`scripts/verify_local.sh` 退出 0；不放宽既有断言。问题编号对应 [Round 3 评审](r3-review.md) §2，现状见 [Round 4 评审](r4-review.md) §1。

## 1. 修复项

| 序 | 级 | 范围 | 修复 | 验收 |
|-|-|-|-|-|
| 1 | P1 | 规则条件（#1） | `runtime/anchors.py` `anchor_supports_text`：<br>• 删除子串快路径；子串命中也须通过数字与方向核对。<br>• 比较词（above、below、over、under、more、less、at least、at most、exceed；超过、不超过、以上、以下、低于、不低于）移出 `_STOPWORDS`（`:622`），与相邻数字组成（方向，数值）对，条件与锚点逐对一致。<br>• 否定按子句核对，不按整句有无。<br>• 中文按标点切分子句、按字符二元组计覆盖。 | 锚点 “Claims above 5000 CNY require department head approval.”：`below 5000`、`less than 5000`、`approval` 均拒绝；中文 “超过 5000 元” 对 “低于 5000 元” 拒绝；`test_semantics.py` 现有正例保持通过 |
| 2 | P1 | 锚点粒度（#1） | • `record_key` 须带字段名，取单元格值比对。<br>• 单值抽取的 `json_pointer` 必须指向标量，拒绝 `""`。<br>• 单值抽取的 `excel_cell` 只接受单个单元格，拒绝 `A1:B3` 这类区域。<br>• 字符串按整值或词边界比对。<br>• 数字 token 允许后接标点。 | “Acm” 对 “Acme” 拒绝；“200,” 中的 200 接受；根指针、区域锚点、无字段的 `record_key` 均拒绝 |
| 3 | P1 | 乐观并发（#10） | `register_extraction_schema_version`（`preparation/extraction.py:565`）去掉先 `current()` 再写的检查，把 `expected_revision` 交给 `versions.save(expected_revision=)`，在同一事务内完成；该函数的 digest 改用存储层的计算方式。其余带 `expected_revision` 的 handler 同样改。 | 两进程用屏障同时以 `expected_revision=r1` 写入，重复 20 次，每次恰好一个成功、另一个返回 `version_conflict` |
| 4 | P1 | 表头与区域（#3、#4） | `preparation/structure.py:88` `_detect_header_rows`：<br>• 表头行：非空单元格全部为文本，且非空占比不低于下一行。<br>• 数据行：类型模式与其后两行一致。<br>• 识别为多行表头时给出 issue，附行号。<br>• 区域自动识别保留空行之后的单行片段，并给出 issue。 | 稀疏首行、`N/A` 首行均不丢行；纯文本表、两行表头、合并表头回归通过；空行后的单行片段保留 |
| 5 | P1 | 轨迹读取（#11） | • `trace_events` 增加全局自增 `seq`，`read_by_kernel_session`（`adapters/storage/sqlite.py:338`）按 `seq` 分页，并返回 `next_seq`。<br>• 幂等比较不包含 `authorization_ref`；重复提交时只追加记录授权引用。<br>• `event_id` 冲突检查放在 `content.put` 之前。 | 两个会话交错写入，按 `seq` 分页时无漏读、无重读；换 `authorization_ref` 重试返回首次结果；冲突时不产生孤儿内容 |
| 6 | P1 | 契约（#6、#8） | • 生成的 schema：`extensions` 加 `propertyNames` 的点分 pattern；`Issue.code` 导出为 `anyOf[enum, pattern]`。<br>• `VersionedRef` 的 id 禁止含 `@`，对象形式与字符串形式往返一致。<br>• `validate_acceptance_report` 的判据参数改为必填。 | 用 `jsonschema` 校验：非法 `extensions` 键、非法 `Issue.code`、含 `@` 的 id 均被拒绝；省略判据参数时报 `TypeError` |
| 7 | P2 | 可判定性与适用性（#14） | • 可判定性缓存键由工具从存储读取 statement digest 与需求修订号，不依赖调用方传 `prior_statement` / `requirement_ref`。<br>• `applicability.py:374` 的 `is` 改为 `==`。<br>• 前置条件的数值规范化：把 “1,5万” 判为有歧义并给出 issue，不与 “15万” 合并。 | 调用方不传 `prior_statement` 时，statement 变化仍使缓存失效；“1,5万” 返回 issue |
| 8 | P2 | 错误映射（#12） | `ingestion/ocr.py:166`、`adapters/parsers/excel.py:43`：只把已知的格式、加密、文件类异常归 `invalid_input`，其余归 `execution_unknown`。 | 注入内部异常时结果为 `execution_unknown`；损坏文件仍为 `invalid_input` |
| 9 | P2 | 推理端口（#13） | 7 个两段式原子统一通过 `runtime.inference`（`agent_provided` 适配器）生成 `inference_request` 并接收 `proposal`；handler 不再自行拼装。 | 7 个原子都调用端口；换成测试桩端口后，两段式用例通过 |
| 10 | — | Mint 验证（#17） | 在隔离的 `MINT_HOME` 中：<br>• 用 `uv sync --frozen` 按 `uv.lock` 安装。<br>• `mint install` 安装 `dataagent-data-layer-0.1.0.mint.tar.zst`。<br>• 确认 mint-core 加载 `.mcp.json` 并列出 32 个工具。<br>• 调用一次只读工具，记录是否弹出审批。<br>• 模型端点有凭据时再跑 `mint run --json`。 | 日志写入 `evidence/round5/`；未执行的步骤标为未验证，并写明原因 |
| 11 | P2 | 存储与测试（#9、#16） | • 写入守卫改为存储层埋点：`content.put`、`versions.save*`、`traces.append` 计数，按运行时观测断言 `writes`；删除 `inspect.getsource` 扫描和硬编码计数（21、24、18）。<br>• 并发测试加屏障，每个进程至少写 100 次。<br>• SQLite 连接用 `contextlib.closing` 关闭，WAL 只在初始化时设置一次。<br>• `conftest` 统一注入临时 `data_root`；测试中一旦用到默认 `cwd/.dataagent` 即失败。 | 测试中无硬编码的操作计数；`-W error::ResourceWarning` 下全部测试通过 |
| 12 | P3 | 代码整理 | • 删除 `_read_primary`（`sqlite.py:351`）、`PACKAGE_ROOT`（`registry.py:20`）、`store_json`（`helpers.py:183`）。<br>• `find_file_ref`（`helpers.py:145`）按 revision 读取，不再写死 `r1`。<br>• `_materialize` 与 `AnchorResolver._workbook` 合并；openpyxl 直接读 `BytesIO`。<br>• semantics 层的锚点错误码从 `da02.*` 改为 `da03.*`。<br>• handler 的 `runtime` 参数加类型注解；`Runtime` 字段按端口 Protocol 声明。<br>• 魔数提为具名常量。<br>• 拆分 100 行以上的函数：`define_business_rules`、`_evaluate_field`、`segment_document`、`extract_irregular_excel`、`define_metric_formula`、`anchor_extracted_values`、`parse_regular_excel`。 | 被拆分的函数均不超过 80 行；错误码与所在层一致；行为测试不变 |
| 13 | — | 文档 | • 方案 §6.2 写明按 `seq` 分页。<br>• 05 回写 #6、#8 的约束。<br>• 新建 `r5-fixes.md`；方案 §12 索引加一行。 | 文档与实现一致 |

## 2. 门禁

`scripts/verify_local.sh` 新增以下检查：

- handler 层乐观并发测试；
- 写声明的存储层观测；
- 以 `-W error::ResourceWarning` 运行测试；
- `evidence/round5/` 中存在 mint 安装日志。

完成后，按 [Round 4 评审](r4-review.md) §3 的维度复评。
