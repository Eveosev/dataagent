# dataagent-contracts

DataAgent S0 应用级能力协议层（`core`）。本包只依赖 `pydantic>=2`，不导入任何能力实现包。

- 类型：37 个 = 35 个具体类型 + 2 个泛型（`CapabilityResult<T>`、`Assessment<V>`）；`ExecutableSpec`、`EngineBinding` 由 07 §4.2 迁入 `semantics`。
- 模块：`vocab`、`envelope`、`refs`、`data`、`semantics`、`task`、`evaluation`、`governance`。
- `schema/generated/` 由 `scripts/generate_schema.py` 生成，提交后不得手改。
- `examples/s0/` 为 `05-contracts.md` §3.5 示例及补充，作为 schema/类型校验夹具。

## 使用

```bash
uv sync --extra dev
uv run python scripts/generate_schema.py
uv run pytest
```

pytest 与 jsonschema 都在可选 `dev` extra 中，冻结锁默认不安装；`dataagent-data`
的 `scripts/verify_local.sh` 会先检查两包的 dev 依赖并在缺失时直接失败。完整
门禁前提见该包 README「发布门禁前提」。

## 序列化约定

- `VersionedRef` 在 JSON 中序列化为 `"<id>@<revision>"`。
- 封闭枚举遇到未知值报错；开放枚举（`Aggregation`、`EvidenceType`、`TraceEventType`）接受点分命名空间的扩展值（`<ns>.<name>`，不接受 `:`），如 `"acme.weighted_mean"`。
- 所有模型 `extra="forbid"`，未知顶层字段仍被拒绝；跨厂商扩展统一放在可选的 `extensions: map[str, json]` 字段（05 §2.1），核心逻辑不解释其内容。`VersionedRef` 是唯一例外：它只序列化为字符串，不带 `extensions`。
