# agentcpm/iface-extension

AgentCPM 接口契约包 `iface-extension`（`kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-extension（L-B 装配协议/状态机/快照/作用域，M11/M12/M13/M17）；决策 D55
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/extension.rs`（38 行，1 个文件）
- **共享依赖**：所有契约统一 `use super::types::*`（`SessionId`/`TurnId`/`Cursor`/`Error`/`ErrorCategory`/`BoxFuture` 等），
  共享类型另见包 `agentcpm/iface-types`

## 契约摘要

**类型**：ComponentContract, AssemblyIntent, AssemblyState

**trait**：- `ExtensionContract` — describe/on_assembly_intent/assembly_status/deactivate

**消费方**：kernel/runtime/src/self_assembly.rs, kernel/host（装配入口）

机器可读形状见 [schema.json](schema.json)。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
