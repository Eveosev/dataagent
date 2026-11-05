# agentcpm/iface-model

AgentCPM 接口契约包 `iface-model`（`kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-model（M27/M30；跨模型轨迹连续 §3.2-5）；决策 D55
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/`（934 行，9 个文件）：`model.rs`、`model_stream.rs`、`model_session.rs` + `model_session/*`（D96；同一既有包，不新增包）
- **共享依赖**：所有契约统一 `use super::types::*`（`SessionId`/`TurnId`/`Cursor`/`Error`/`ErrorCategory`/`BoxFuture` 等），
  共享类型另见包 `agentcpm/iface-types`

## 契约摘要

**类型**：ModelRequest, ModelResponse

**trait**：- `ModelContract` — call/capabilities

**消费方**：kernel/runtime/src/model/*, kernel/runtime/src/gateway/*, kernel/host/src/model_probe.rs

机器可读形状见 [schema.json](schema.json)。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
