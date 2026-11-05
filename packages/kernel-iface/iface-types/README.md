# agentcpm/iface-types

AgentCPM 接口契约包 `iface-types`（Mint `kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§6 共享类型（被 9 个 iface 引用）+ L-A 契约版本协商（§6.3 装载/握手兼容检查）；决策 D55、D83
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/types/` + `kernel/iface/src/version.rs`（1786 行，5 个文件）
- **分发形态**：Mint 扁平分发（无 Cargo.toml / 无 lib.rs）；`lib.rs` 与 `tests/` 按分发纪律不分发
- **共享依赖**：本包是其余 9 个 iface 包的共同基座（`SessionId`/`TurnId`/`Cursor`/`Error`/`ErrorCategory`/`BoxFuture` 等）

## 契约摘要

**类型**：SessionId, TurnId, Cursor, CheckpointId, ActId, CallId, TraceId, EnvironmentId, PrincipalId, Generation, AssemblyHandle, CallMeta, Error, ErrorCategory, RequestState, Decision, Verdict, BudgetClass, KernelRequest, Handshake, Interrupt*（打断三元组 / 6 类 18 子类型）, Version, ContractDescriptor, CompatError, IFACE_VERSION

**trait / 函数**：
- `ContractMeta` — default 实现，使既有 8 个契约无需改动即获得 crate 级自述
- `parse_version` / `is_compatible` / `require_capabilities` / `negotiate` — L-A 契约语义版本判定（fail-closed）

**消费方**：所有 9 个 iface 模块, kernel/host/src/startup/contract_check.rs, kernel/host/src/startup/kernel.rs, kernel/cli, kernel/core

机器可读形状见 [schema.json](schema.json)。

## 为什么 `version.rs` 归本包（本轮归属决策）

- 职责：定义**契约自身的元数据与兼容判定**（`ContractDescriptor{name,version,capabilities}`；major 相等、
  minor 向后兼容、patch 忽略），9 个 iface 包都用它自述版本 → 属"共同基座"而非某个能力域。
- 依赖：**零外部依赖、零 `crate::` 引用**（只用 std），与 iface-types 作为底层基座一致。
- 归属约束：按 D96 §6「新增源文件纳入既有包，不因新增源文件而另增接口包」，故并入既有包不改包数。

## 依赖关系

| 方向 | 内容 |
|---|---|
| 本包依赖其他 iface 包 | 无 |
| 被依赖 | iface-context / iface-session / iface-policy / iface-store / iface-tool / iface-model / iface-loop / iface-env / iface-extension |

## 完成阶段

- **本轮已完成**：`version.rs` verbatim 分发 + schema（files/lines/类型/trait/依赖）+ 本 README。
- **后续（契约治理，非分包）**：`ContractMeta` 目前只有 default 实现与单测覆盖；`is_compatible` 的真实消费方是
  `host/src/startup/contract_check.rs`。是否逐契约实现 `ContractMeta` 由后续决策定，本轮不虚构消费方。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
