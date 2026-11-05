# agentcpm/iface-env

AgentCPM 接口契约包 `iface-env`（`kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-env / §6.7 跨设备缺口；决策 D55
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/env`（523 行，6 个文件）
- **共享依赖**：所有契约统一 `use super::types::*`（`SessionId`/`TurnId`/`Cursor`/`Error`/`ErrorCategory`/`BoxFuture` 等），
  共享类型另见包 `agentcpm/iface-types`

## 契约摘要

**类型**：EnvId, EnvironmentKind, EnvironmentCapabilities, Environment, PathUri, DirEntry, FileStat, ExecRequest, ExecOutput, ExecutionHandle, Signal

**trait**：- `FsBackend` — read_file/write_file/list_dir/stat
- `ExecBackend` — exec/signal/terminate

**消费方**：kernel/runtime/src/environment_registry.rs, kernel/runtime/src/env_codex.rs, kernel/host/src/transport/env*

机器可读形状见 [schema.json](schema.json)。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
