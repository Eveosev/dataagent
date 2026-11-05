# agentcpm/iface-loop

AgentCPM 接口契约包 `iface-loop`（`kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-loop（M01/M02/M04；实现者是核外 loop）；决策 D55
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/loop_.rs`（87 行，1 个文件）
- **共享依赖**：所有契约统一 `use super::types::*`（`SessionId`/`TurnId`/`Cursor`/`Error`/`ErrorCategory`/`BoxFuture` 等），
  共享类型另见包 `agentcpm/iface-types`

> **文件名映射**：kernel 侧是 `kernel/iface/src/loop_.rs`（`loop` 是 Rust 关键字），
> 本包保留同名 `src/loop_.rs` 以保证 verbatim 同源；Rust 模块声明为 `#[path = "loop_.rs"] pub mod r#loop;`。

## 契约摘要

**类型**：LoopDescriptor, StepOutcome

**trait**：- `LoopContract` — describe/step/interrupt/status

**消费方**：核外 loop 实现（Rust/Node）, kernel/host（L-C 接线）

机器可读形状见 [schema.json](schema.json)。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
