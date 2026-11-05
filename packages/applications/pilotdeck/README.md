# PilotDeck application package

这是 PilotDeck 接入 AgentOS 的应用包脚手架。PilotDeck 产品源码仍位于独立仓库，AgentOS 只维护 Mint 清单、源码 revision、构建映射和接入验证。

当前状态：已登记本地 PilotDeck checkout；尚未生成可发布的 Mint 应用制品。源码位置和固定 revision 见 [`packaging/source-ref.toml`](packaging/source-ref.toml)。

接入顺序：

1. 在 `packaging/source-ref.toml` 中确认源码 revision。
2. 在 `integrations/pilotdeck/` 中实现 AgentOS 适配器。
3. 补齐 `conformance/applications/pilotdeck/` 的安装、启动和生命周期验证。
4. 通过验证后，再将构建输出作为 Mint `kind = "app"` 发布。
