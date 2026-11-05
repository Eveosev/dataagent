# StaffDeck application package

这是 StaffDeck 接入 AgentOS 的应用包脚手架。StaffDeck 产品源码继续由独立仓库维护；当前 AgentOS 只先建立包边界、适配器边界和验证入口。

当前状态：StaffDeck 仓库尚未连接，因此这里没有源码路径、revision 或构建入口。连接仓库后，先补 [`packaging/source-ref.toml`](packaging/source-ref.toml)，再实现 `integrations/staffdeck/` 和对应 conformance。
