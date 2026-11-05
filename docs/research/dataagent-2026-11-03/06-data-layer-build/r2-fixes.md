---
round: 2
date: 2026-11-03
---

# Round 2 修复

| 项 | 修复 |
|-|-|
| 轨迹字段 | `TraceEventRef` 增加 `kernel_session_id`；SQLite 增加该列 + 索引，旧库启动时自动 `ALTER TABLE`；三个轨迹原子共用 `_append`，统一写入 `kernel_session_id / kernel_call_id / invocation_id / invocation_ref / authorization_ref`；纠正重复事件返回已存储的 `payload_ref` |
| 错误映射 | 只有意外异常落 `execution_unknown`；`ValueError / ValidationError` 一律 `invalid_input`；`event_type` 用枚举类型在输入校验阶段收口，`define_business_rules` 的 `combination` 显式转 `invalid_input` |
| 源摘要 | 解析/OCR 输出显式携带 `source_content_digest`；`content_digest` 非 `sha256:<64hex>` 直接 `invalid_input`，摘要不匹配仍为 `source_changed` |
| 锚点校验 | 数值改为 `Decimal` 精确匹配（区分 `15/1.5`、`-500/500`，支持千分位）；归一化兜底返回真实字符区间，不再退化为整页 |
| OCR | 块偏移计入 `\n` 分隔符；`pages=` 选择保留原始页码；`region` / `orientation` 生效并校验非法值 |
| 契约扩展 | core 模型统一继承 `ExtModel`，新增可选 `extensions: map[str,json]`；`VersionedRef` 仍只序列化为字符串 |
