# Reusable capability packages

此目录放置可被 PilotDeck、StaffDeck 或其他 AgentOS 应用复用的能力包。

每个能力包应自包含 `mint.toml`、README、真实入口和必要的 conformance 证据。应用专属逻辑放在对应的 `packages/applications/<app>/` 或外部产品仓库，不要把应用专属代码混入这里。

实现源码可以来自独立版本化仓库；此目录的包入口通过 `packaging/source-ref.toml` 固定完整 commit、subdir、包内构建描述和制品 digest。没有真实制品时不创建可发布清单。RSI 第一阶段拟在当前 RSI 仓库内拆出独立 `modules/`，本目录保留可重建的发布投影，详见 [模块化设计](../../docs/superpowers/specs/2026-10-28-rsi-iface-modularization-design.md)。
