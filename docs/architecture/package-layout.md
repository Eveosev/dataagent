# AgentOS package layout

## 边界

AgentOS 维护四类内容：

1. `packages/agent-kernel/packages/iface-*`：Kernel 的稳定接口契约和机器可读 schema（权威源 `packages/agent-kernel/kernel/iface/src`）。`packages/kernel-iface/` 是 0.1.0 历史快照，[已废弃](../../packages/kernel-iface/DEPRECATED.md)，勿作对比基线。
2. `packages/capabilities/`：多个应用共同消费的能力包。
3. `packages/applications/<app>/`：应用包的 Mint 清单、外部源码引用和构建映射。
4. `integrations/`、`conformance/`、`compatibility/`：AgentOS 侧接入、验证和版本证据。

运行边界遵循：AgentOS 组合发行，cpmrt 运行 Agent，AgentCPM Kernel 定义 IFace 机制契约，Mint/MintHub 管安装与分发。RSI 的模块化目标与源码迁移映射见 [RSI IFace v2 设计](../superpowers/specs/2026-10-28-rsi-iface-v2-design.md) 和 [模块清单](rsi-toolkit-modules.toml)。

当前过渡期继续使用 `mint run` 执行 RSI 实验；cpmrt 已随 `mint/core` 0.1.14 发布（见 [Mint 指南梳理](../mint/2026-10-28-Mint指南梳理.md)），RSI 接入 cpmrt 安排在独立迁移阶段，不作为公共能力拆分和当前交付的前置条件。

PilotDeck、StaffDeck 的产品实现继续在独立仓库中维护。应用包目录不复制业务源码，只引用一个可审计的 repository/path + revision。

RSI 公共能力采用相同的版本化来源方式：第一阶段实现位于 RSI Git 仓库的目标 `modules/<module>/`，独立构建与发布，AgentOS 的 `packages/capabilities/<module>/` 保存发布投影。当前只完成设计，没有创建这些包。包内构建描述随源码跟踪，外层固定完整 revision、subdir 和制品 digest；公共模块不得反向导入 RSI 应用。

## 交付链路

```text
外部产品源码
    ↓ 固定 revision
packages/applications/<app>/packaging/source-ref.toml
    ↓ AgentOS integration + build mapping
Mint agent 工程
    ↓ build / release
Mint kind="app" 制品
    ↓ 安装后验证
conformance/applications/<app>/
```

`mint.toml` 当前用于记录应用工程阶段的组装入口，使用 `0.1.0-dev` 和 `kind = "agent"` 表示尚未发布。完成真实构建、安装和 conformance 后，才生成并发布 `kind = "app"` 产物。

## 当前连接状态

- PilotDeck：本地 checkout 已登记，revision 固定为 `4ebfa745754373117da6ed46c522c5d8d74d60ef`。
- StaffDeck：尚未连接，目录只保留脚手架。
- mint：尚未连接源码仓库，AgentOS 只保留 Mint 文档和应用包入口。

详细路径登记见 [`workspace/projects.yaml`](../../workspace/projects.yaml)。
