# AgentOS packages

这里存放 AgentOS 自己维护的包定义和应用包组装入口。

- `agent-kernel/`：Kernel 源码仓库（独立 git clone）。**iface 契约以这里为准**：权威源 `agent-kernel/kernel/iface/src/`，10 个可读分发包 `agent-kernel/packages/iface-*`（0.1.2，由 `scripts/sync-iface-packages.sh` 生成并校验）。
- `kernel-iface/`：⚠ 0.1.0 历史冻结快照（同步至 kernel master `d950766`，2026-10-29），见 [DEPRECATED.md](kernel-iface/DEPRECATED.md)。已过时，缺少之后的契约，**不要作为对比基线**；仅在追溯 0.1.0 发布史时参考。
- `capabilities/`：跨应用复用的能力包。
- `applications/`：面向用户交付的应用包脚手架和 Mint 组装描述。

PilotDeck、StaffDeck 的产品实现不复制到这里。应用目录只引用外部源码仓库、固定 revision 和 AgentOS 侧的适配规则。
