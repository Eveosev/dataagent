# agentcpm/iface-context

AgentCPM 接口契约包 `iface-context`（Mint `kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-context（M08/M09/**M37 留痕**：组装 / 重建能力清单 / 留痕）；决策 D55、D83
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/context.rs` + `kernel/iface/src/trace.rs`（188 行，2 个文件）
- **分发形态**：Mint 扁平分发（无 Cargo.toml / 无 lib.rs）；`lib.rs` 与 `tests/` 按分发纪律不分发

## 契约摘要

**类型**：ContextSnapshot, NoopTraceSink

**trait**：
- `ContextContract` — assemble / rebuild_capabilities / trace_input（`context.rs`）
- `TraceSink` — record_input：M37「先写后执行」的能力面；比事件面多一个**文件内容面**
  （原始输入要原子落盘成文件，不只是写一条事件）（`trace.rs`）

**契约依赖**：`agentcpm/iface-types`（`CallMeta`/`Cursor`/`Error`/`SessionId`/`TraceId`）

**消费方**：kernel/runtime/src/context.rs, kernel/runtime/src/compact/*, kernel/core/src/trace.rs, kernel/host/src/startup/context_factory.rs

机器可读形状见 [schema.json](schema.json)。

## 为什么 `trace.rs` 归本包（本轮归属决策）

- 规范 §4.2 对 iface-context 的定义即"组装 / 重建能力清单 / **留痕**"，`TraceSink` 正是 M37 留痕能力面；
- 同包 `ContextContract` 已声明 `trace_input` 方法——留痕本就是本包职责，此前仅被 allowlist 豁免、未分发；
- 依赖仅 `crate::types`（同 crate 基座 = 本包声明的 `agentcpm/iface-types`），无反向依赖。

## 依赖关系

| 方向 | 内容 |
|---|---|
| 本包依赖 | `agentcpm/iface-types`（共享类型） |
| 被依赖 | 无（其他包不引用 `TraceSink` 类型；实现方实现该 trait） |

## 完成阶段

- **本轮已完成**：`trace.rs` verbatim 分发 + schema + 本 README。
- **后续**：无契约缺口；`record_input` 的实现属实现包（core `log` / `TraceSink` impl），不在分包范围。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
