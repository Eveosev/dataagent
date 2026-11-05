---
round: 5
date: 2026-11-04
status: 已执行
basis: r5-plan.md、r5-review B1–B3
---

# Round 5 修复记录

本轮的阻断口径来自 Reviewer 的 B1–B3，并按 r5-plan 第 1–6 项补齐 P1/P2：

| # | 级 | 问题 | 修复 | 回归 |
|-|-|-|-|-|
| B1 | P1 | 字符串值按子串匹配，`"Acm"`/`"cme"` 可锚定 `"Acme Inc."` | `runtime/anchors.py` 新增 `_match_text`/`_whole_token_index`，`anchor_value_mismatch` 与 `find_text_span` 都要求整 token；`anchor_extracted_values` 的兜底重定位同样收紧 | `test_round6_reviewer_findings.py::test_string_value_fragments_are_not_grounded_by_a_longer_token`、`test_extract_fields_rejects_a_truncated_string_value`、`test_anchor_extracted_values_does_not_relocate_a_fragment` |
| B2 | P1 | 规则准备固定取 5 页/40 条/300 字，却报 `complete` | `semantics/metrics_rules.py` 提取 `_rule_prep_clauses`，返回截断原因与观测值；`helpers.truncated` 写入 `Completeness.extent=truncated`，并追加 `da03.inference_scope_truncated` issue（含 `suggested_action`） | `test_rule_preparation_declares_page_truncation`、`test_rule_preparation_declares_clause_and_text_truncation` |
| B3 | P1 | 条件 `"... require approval"` 丢掉锚点的 `"department head"` 仍通过 | `anchor_supports_text` 在覆盖度通过后增加“部分条件必须是锚点的连续片段”判据；全量覆盖的改述仍允许词序变化 | `test_rule_condition_may_not_drop_an_anchor_qualifier`；既有 `claims above 5000 CNY` 正例保持通过 |
| P2 | 否定极性按整段而不是按子句判断 | 同一锚点含正句 + 负例外时，正条件被“not”误伤 | `anchor_supports_text` 先用 `_support_clause` 选出覆盖全部条件词与数字、且否定极性一致的子句；仅当没有这样的子句时才用整段 | `test_negation_is_checked_per_clause_not_per_anchor`；`test_judgment_chain_policy_to_coverage` |
| P2 | 重复条款的锚点都指向第一次出现 | `page.text.find(text, line_start)` 从当前行起点搜索，重复文本各自定位 | 手工核对 3 行相同文本 → `(0,17)/(18,35)/(36,53)` |
| P1 | 数字 token 后的标点 | `200.`、`200, net`、JSON `200, ...` 被拒 | `_NUMBER_TOKEN` 允许尾随 `.`/`,`，同时用 `(?![.,]\d)` 排除 `2024.05.01`、`200,00` | `test_numeric_tokens_may_be_followed_by_punctuation` |
| P1 | `record_key` 无字段维度 | 行内任意字段都能“证明”任意值 | `RecordKeySelector` 增加必填 `field`；`AnchorResolver._resolve_record_key` 只返回该字段值，字段缺失显式失败 | `test_record_key_anchors_one_field_not_the_whole_row`、`test_record_key_requires_a_field_name` |
| P2 | MCP `context` 未进 `required` | 严格客户端会漏传 | `interfaces/mcp_server.py` 把 `context` 并入每个 `inputSchema.required` | `test_round4_storage.py::test_tools_list_carries_write_annotations` 全量断言 |
| P2 | 跨会话轨迹按每任务 cursor 分页会漏读 | `read_by_kernel_session` 改用全局 `seq` 分页；`TraceRecord.seq` 暴露下一页游标；旧库迁移时按 rowid 回填 | `test_kernel_session_view_paginates_by_global_seq` |
| P2 | 换 `authorization_ref` 重试被判冲突 | 幂等比较排除 `authorization_ref` | `test_trace_retry_with_a_new_authorization_ref_is_idempotent` |
| P2 | 冲突时先写内容留下孤儿 | `_append` 先用 `get_event` 查事件身份，再决定是否 `content.put` | `test_conflicting_trace_retry_does_not_write_orphan_content` |
| P2 | `VersionedRef(id="a@b")` 无法往返 | `refs.py` 禁止 id/revision 含 `@` 或空白 | `test_round4_contracts.py::test_versioned_ref_parser_matches_pattern` |
| P2 | `validate_acceptance_report` 省略判据不校验 | `criteria`/`evaluation_set` 改为必填 | `test_acceptance_helper_checks_criteria_and_samples` 的 `TypeError` 断言 |

## 验证

```bash
cd packages/capabilities/dataagent-contracts
uv run --frozen pytest -o addopts="" -q        # 111 passed
uv run --frozen python scripts/generate_schema.py --check   # schema OK: 66 files

cd packages/capabilities/dataagent-data
uv run --frozen pytest -o addopts="" -q        # 211 passed
uv run --frozen python scripts/export_catalog_snapshot.py --check  # 32 atoms
```

`verify_local.sh` 覆盖 contracts/data 测试、schema、catalog、CLI/MCP 32、bundle 69 文件、mint dry-run、manifest 与隔离 wheel 冷启动。

## 仍未关闭

- P3 代码卫生：长函数、宽口径 `except Exception`、部分 handler 的 `runtime` 未注解。
- P3 `mint install` / mint-core 加载 `.mcp.json` 仍未实测（`mint publish --dry-run` 通过）。
- P3 内核基线 `agent-kernel@f0fa521` 未随上游 HEAD 刷新。
