# agentcpm/iface-tool

AgentCPM 接口契约包 `iface-tool`（`kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-tool（M26/M28/M29/M32；执行上下文必须带环境归属 §6.7）；决策 D55
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/tool.rs`（74 行，1 个文件）
- **共享依赖**：所有契约统一 `use super::types::*`（`SessionId`/`TurnId`/`Cursor`/`Error`/`ErrorCategory`/`BoxFuture` 等），
  共享类型另见包 `agentcpm/iface-types`

## 契约摘要

**类型**：ToolSpec, ToolCall, ToolResult

**trait**：- `ToolContract` — register/list/invoke/abort
- `ToolStaging` — contains/register_stub/remove_stub（装配期暂存注册；D83③ staging 契约）

**消费方**：kernel/runtime/src/tool.rs, kernel/host/src/transport/model*, kernel/accept

机器可读形状见 [schema.json](schema.json)。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
