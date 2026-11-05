---
round: 4.3
date: 2026-11-04
subject: Round 4.3 后的实现
score: 6.5/10
---

# Round 4 评审

范围：`packages/capabilities/dataagent-contracts`、`packages/capabilities/dataagent-data`（不含 `packaging/bundle/` 复制品）。

| 项 | 结果 |
|-|-|
| 测试 | contracts 111 passed；data 187 passed |
| 入口 | CLI 32、MCP 32；注解 8 只读 / 26 幂等 / 0 破坏性，与存储层埋点观测一致 |
| 打包 | bundle 与源码一致；manifest 184/184 OK |
| 卫生 | 包目录无 `.dataagent/`；独立 TMPDIR 下跑完测试残留 0 |
| 并发 | 2、4 个进程同时起跑，各写 150 次：0 异常，revision r1..r600、cursor 1..750 连续无重复 |

## 1. 问题完成情况

编号对应 [Round 3 评审](r3-review.md) §2。

| # | 级 | 结论 | 剩余 |
|-|-|-|-|
| 1 | P0 | 部分修复 | 规则条件：锚点 “Claims above 5000 CNY require department head approval.” 下，`below 5000`、`less than 5000` 通过（above/below/less/more/least 在停用词表中）；`approval` 单词走子串快路径通过，绕过“不得丢弃锚点数字”（`runtime/anchors.py:682`）。`record_key` 比对整行，无字段维度；`json_pointer ""` 与 `A1:B3` 区域可作锚点；字符串按子串匹配（“Acm” 命中 “Acme”）；数字后接逗号时真实值 200 被拒 |
| 2 | P0 | 已修复 | — |
| 3 | P0 | 已修复，引入新缺陷 | 首个数据行稀疏或为文本时并入表头：`[["name","q1","q2"],["Alice",None,None],["Bob",1,2]]`、`[["name","amount"],["Alice","N/A"],["Bob",5]]` 得 `header_rows=2`，该行丢失，状态 `ok`、无 issue（`preparation/structure.py` `_detect_header_rows`） |
| 4 | P0 | 已修复 | 区域自动识别丢弃空行后的单行片段 |
| 5 | P1 | 已修复 | — |
| 6 | P1 | 部分修复 | 生成的 JSON Schema 未约束 `extensions` 键与 `Issue.code` 的命名空间 |
| 7 | P1 | 已修复 | — |
| 8 | P1 | 部分修复 | `VersionedRef` 对象形式、id 含 `@` 时不能往返；`validate_acceptance_report` 的判据参数可省略 |
| 9 | P1 | 已修复 | 连接不关闭，每次调用重复 `PRAGMA journal_mode=WAL`；包内并发测试每进程 5 次、无屏障，强度不足 |
| 10 | P1 | 部分修复 | `register_extraction_schema_version`（`preparation/extraction.py:565`）先 `current()` 后 `save_content_addressed()`，不在同一事务；两进程同以 `expected_revision=r1` 写入，15 次中 15 次均成功（r2、r3），丢失更新。存储层 `save(expected_revision=)` 无 handler 使用 |
| 11 | P1 | 已修复 | `read_by_kernel_session` 按各会话 cursor 排序，跨会话分页漏读或重读；payload 含 `authorization_ref`，换授权引用重试报 `version_conflict`；冲突前已 `content.put`，留下孤儿内容 |
| 12 | P2 | 已修复 | `ocr.py:166` 渲染、`excel.py:43` `open_workbook` 以 `except Exception` 归 `invalid_input` |
| 13 | P2 | 部分修复 | 写声明与观测一致；`InferencePort` 未接入任何原子 |
| 14 | P2 | 部分修复 | 缓存失效依赖调用方传 `prior_statement` / `requirement_ref`；`applicability.py:374` 仍以 `is` 比较字符串；“1,5万” 与 “15万” 合并 |
| 15 | P2 | 已修复 | — |
| 16 | P2 | 基本修复 | 默认 `data_root` 仍为 `cwd/.dataagent`，靠门禁事后检查；长函数与死代码见 §2 |
| 17 | — | 部分证明 | 已证：`mint publish --dry-run` 退出 0；wheel 装入干净 venv 后 `tools/list=32`。未证：mint-core 加载 `.mcp.json`、`mint install`、`mint run --json`（401）、宿主按注解审批。隔离安装未用 `uv.lock` |

## 2. 代码质量

| 类别 | 问题 |
|-|-|
| 重复与死代码 | `_read_primary` 与 `read_from` 相同；`PACKAGE_ROOT`、`helpers.store_json` 无引用；`register_extraction_schema_version` 另算 digest，序列化参数与存储层不同；`_materialize` 与 `AnchorResolver._workbook` 两套临时文件逻辑（openpyxl 可直接读 `BytesIO`） |
| 正确性 | `find_file_ref` 写死读 `"r1"`，同一 id 内容变化后仍读旧版本 |
| 错误码 | semantics 层发 `da02.anchor_value_mismatch`、`da02.anchor_not_found`；`da02.inference_required` 与 `da03.inference_required` 并存 |
| 类型 | 30 个 handler 的 `runtime` 参数无注解；`Runtime.inference`、`ocr_engine` 为 `Any`；端口 Protocol 未约束 `Runtime` |
| 魔数 | `1_000_000`、`timeout=10`、`[:12]`/`[:16]`/`[:40]` 截断，共 31 处 |
| 长函数 | `define_business_rules` 239 行；`_evaluate_field` 161；`segment_document` 151；`extract_irregular_excel` 137；`define_metric_formula` 134；`anchor_extracted_values` 129；`parse_regular_excel` 126 |
| 测试 | 反例覆盖明显扩大，未发现断言放宽。`test_registry` 以 `inspect.getsource` 扫描 handler，不追踪 helper，且硬编码 `== 21`；`test_round4_storage` 硬编码 24、18；矩阵测试有以 `or` 匹配消息的断言；无 handler 层 TOCTOU、规则方向反转用例 |

## 3. 评分

| 维度 | 分 | 主要扣分 |
|-|-|-|
| 契约包 | 7.5 | #6、#8 各剩一处 |
| 证据与锚点可信度 | 5.5 | 规则条件方向反转、子串旁路；`record_key` 无字段维度 |
| 能力正确性（表结构） | 6 | 稀疏首行并入表头，静默丢行 |
| 运行时 | 7 | handler 层乐观并发不原子；两处宽口径异常 |
| 存储 | 7 | 跨会话分页；`find_file_ref` 写死 `r1`；连接不关闭 |
| 接口与打包 | 7 | 注解准确；mint 宿主加载未验证 |
| 卫生与测试 | 6.5 | 守卫靠扫源码、计数硬编码；并发测试弱 |
| **综合** | **6.5** | Round 3 评审为 5.5 |

## 4. 后续

修复方案见 [Round 5 优化方案](r5-plan.md)。
