# iface-types（接口契约包）

AgentCPM 的共享类型契约：`SessionId` / `TurnId` / `Cursor` / `Error` / `ErrorCategory` / `BoxFuture` 等。
本包只定义形状，不含实现。

## 用法

- 契约源码：`src/`（verbatim 自 `kernel/iface/src/types`）
- 机器可读形状：`schema.json`
- 消费方：其余 9 个 iface 包、`kernel/host`、`kernel/cli`、`kernel/core`

## 边界

不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
