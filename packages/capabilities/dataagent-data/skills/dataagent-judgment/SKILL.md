---
name: dataagent-judgment
description: 用 DataAgent 数据层的判定族原子，把制度 PDF/单据转成有原文锚点的规则、可判定性结论与适用性草案。涉及 DA02.8、DA02.12、DA03.4.3、DA03.15、DA03.16 时使用。
---

# DataAgent 判定族

判定族负责“这句话能不能自动判、依据在哪、缺什么”。所有结论必须能回到原文锚点。

## 两段式协议（强制）

涉及原子：`segment_document`（可选）、`extract_fields_to_schema`、`define_business_rules`、`assess_automatic_decidability`、`define_rule_applicability`、`define_rule_preconditions`。

1. **先不带 `proposal` 调一次。** 工具返回 `status=needs_input`，`issues[].inference_request` 里给出候选片段、候选锚点、目标字段/词表。不要跳过这一步。
2. **只在候选范围内生成 proposal。** 锚点必须来自各原子实际的 `inference_request` 结构，不要自己算偏移、不要编造页码/单元格：
   - `extract_fields_to_schema`：`candidate_spans[]`（`page / char_start / char_end / text`）与 `fields[]`，用候选区间构造 `SourceAnchor`；
   - `define_business_rules`：`clauses[].anchor`；
   - `define_metric_formula`：`available_fields` / `aggregations`；
   - `segment_document`：`unit.anchors`。
3. **带 `proposal` 再调同一个工具。** 工具会逐条验证锚点；锚点不存在的值降为 `missing`，不要用“看起来像”的理由绕过。

## 反捏造规则

- 没有锚点的值 = `missing`，不是 `extracted`。
- 原文没有的字段不补默认值。
- `unknown` 不折算成 `false` 或 `failed`；前置条件缺事实时是 `unknown`，不是“不适用”。
- 同一事实有多个冲突来源时标 `conflict`，不要选一个好看的。
- 低置信度 OCR 值可以 `low_confidence`，但必须保留锚点并提示人工复核。

## 推荐链路

1. `parse_text_pdf` / `ocr_pdf` → `DocumentRef`。
2. `segment_document` 得到条款单元及 `anchors`；`maintain_source_anchors` 在文件换版后判断 `valid/remapped/expired`。
3. `register_extraction_schema_version` 固定字段 schema（同内容幂等，改字段升 revision）。
4. `extract_fields_to_schema` 两段式抽字段；单据 JSON 直接走 `parse_json_records`。
5. `define_business_rules` 两段式生成带锚点的条件；`combination` 只引用已存在的条件 id。
6. `assess_automatic_decidability` 两段式给出 `auto / needs_evidence / needs_human`；`basis_refs` 为空时工具会把 `auto` 降级，不要硬报 auto。
7. `identify_evidence_or_human_gaps` 把缺口变成 `GapPlan`；`mark_automation_coverage` 汇总覆盖率（分母是全部要求，不是已自动项）。
8. `define_rule_applicability` / `define_rule_preconditions` 两段式定义适用性与前置；`resolve_unknown_applicability` 只能保持 `unknown`，绝不能输出“适用”。

## 输出检查清单

- 每个 `extracted` 值都有 `evidence[].source_anchor`，且 revision 与源文件一致。
- `needs_input` 时必须读取 `inference_request`，而不是重试原调用。
- `partial` 时逐条读 `issues[]`；warning 不等于失败。
- 不要把 `execution_unknown` 当作可重试错误盲目重放；先查轨迹（`append_invocation_record`）。

## 工具入口

- MCP：`dataagent-data` 服务，工具名即 operation 名；`context` 放在参数或 `_meta`。
- CLI：`python -m dataagent_data.interfaces.cli <operation>`，stdin 传 `{"input": {...}, "context": {...}}`。
