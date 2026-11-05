# AgentOS integrations

这里放 AgentOS 与外部产品源码之间的适配器。适配器负责启动、协议转换、配置映射、生命周期和错误归一化；它不拥有 PilotDeck 或 StaffDeck 的业务源码。

每个应用使用独立目录，并与 `packages/applications/<app>/` 和 `conformance/applications/<app>/` 一一对应。
