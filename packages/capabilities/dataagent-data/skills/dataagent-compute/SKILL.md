---
name: dataagent-compute
description: 用 DataAgent 数据层的计算族原子，把不规则 Excel/CSV/JSON 变成可复用的规整表、结构画像与指标定义。涉及 DA01.4、DA01.5、DA02.1、DA02.2、DA02.4、DA03.4.1 时使用。
---

# DataAgent 计算族

计算族负责“先把表弄对，再谈指标”。不要跳过规整步骤直接从原始工作簿算数。

## 推荐链路

1. `inspect_workbook_calc_state`：先看 1900/1904 日期系统、公式与缓存值；`needs_recalc` 非空时不要相信公式结果。
2. `parse_regular_excel`：表头明确、无合并歧义时用；xlsx/xlsm。
3. `extract_irregular_excel`：标题行、多行表头、合并单元格、合计行时用；返回逻辑表与区域。
4. `detect_workbook_regions`：需要先看区域划分时单独调用；区域坐标是 `A1:C6` 形式。
5. `recover_headers`：从区域恢复表头与列名；`header_rows > 1` 时要检查列名拼接是否符合业务。
6. `expand_merged_cells`：把纵向/横向合并值填充到明细行，`expanded_ranges` 记录来源，便于回溯。
7. `classify_table_rows`：区分 `detail / subtotal / total / title`；合计行绝不能进入明细聚合。
8. `profile_table_structure` + `infer_field_types`：看空值、基数、类型冲突；`conflict` 字段不要强行选类型。
9. `parse_delimited_file` / `parse_json_records`：CSV 编码、分隔符、坏行；JSON 嵌套字段用 JSON Pointer 路径。
10. `define_metric_formula`：两段式。第一次不带 `proposal` 拿词表与字段候选，第二次带 `measure_field / aggregation / filters / dimensions / time`。

## 计算规则

- 指标口径必须显式：度量字段、聚合方式、过滤、维度、时间字段与粒度。
- `sum` 只用于可加指标；去重人数用 `count_distinct`，`custom` 必须附说明。比率不是合法 `Aggregation`，要用分子/分母两个派生指标表达。
- 单位与币种写进 `unit`；跨币种不自动换算。
- `profile` 的方法 `exact` / `sampled` 必须如实回传；采样时 completeness 是 `sampled`。
- 类型推断冲突时保留 `observed_types`，让下游决定，不要静默取多数。
- 合并单元格展开后要保留 `merged_ranges` 与 `source.origin`，否则审计断链。

## 常见坑

- 1904 日期系统会把日期整体偏移 1462 天；先读 `date_system`。
- 合计行/小计行混在明细里会重复计数；先 `classify_table_rows`。
- 多行表头直接当数据会生成 `Unnamed` 列；用 `recover_headers`。
- CSV 坏行被截断/补齐时看 `bad_rows`，不要假设 0 丢失。
- OCR 结果低置信度会返回 `partial`；数字位必须人工复核后再入账。

## 工具入口

- MCP：`dataagent-data`；CLI：`python -m dataagent_data.interfaces.cli <operation>`，失败退出码非 0。
- 所有 `context` 必填 `request_id / scope_ref / authorization_ref`。
