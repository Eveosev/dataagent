# iface-tool（接口契约包）

AgentCPM `iface-tool` 契约：只定义形状/规则，不含实现。源码 `src/` verbatim 自 `kernel/iface/src`，
机器可读形状见 `schema.json`。

## 用法

消费方（Kernel host/组件实现）按本契约提供实现；实现可替换，使用方不改代码。

## 边界

不读文件系统、不启动进程、不做安全通道；实现与授权由 Kernel 侧完成。
