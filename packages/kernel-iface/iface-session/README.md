# agentcpm/iface-session

AgentCPM 接口契约包 `iface-session`（Mint `kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-session（创建 / 推进 / 恢复 / 归档）+ `lease.rs`（推进权与围栏，D56）+ `handoff.rs`（§6.8 跨 loop 交接，D79）；决策 D55、D56、D79、D83
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/session/` + `kernel/iface/src/lease.rs` + `kernel/iface/src/handoff.rs`（1571 行，12 个文件）
- **分发形态**：Mint 扁平分发（无 Cargo.toml / 无 lib.rs）；`lib.rs` 与 `tests/` 按分发纪律不分发

## 契约摘要

**类型**：SessionHeader, SessionLease, SessionIdentity, Epoch, NodeId, PlacementMode, SessionSeq, LogOffset, TenantId, EffectLevel, OP_EFFECT_MAP, LOCAL_NODE,
Lease, LeaseStatus, LeaseError, ERR_LEASE_*,
KernelError, AuthzRequest, BlockedKind, BlockedOnItem, SessionStatus, WatchRequest, WatchEvent, WatchTerminal, WatchPage,
DeliverRequest, DeliverResult, CloseRequest, CloseResult, KernelTaskState, TaskSnapshot

**trait**：
- `SessionContract` — create/attach/detach/drain_inbox/…（`session/`）
- `LeaseStore` — acquire/renew/release/status（epoch 围栏；时间由调用方注入，实现不得读系统时钟）（`lease.rs`）
- `HandoffAuthorizer` — authorize（**fail-closed** 鉴权端口）（`handoff.rs`）
- `HandoffKernel` — session.create/get/watch/close/deliver + operation.get/list/cancel（L-C 方法 1:1 镜像）（`handoff.rs`）

**契约依赖**：`agentcpm/iface-types`（共享类型）、`agentcpm/iface-store`（`EventIo`，`LeaseStore` 方法签名用）

**消费方**：kernel/host/src/transport/{session*,lease_gate,a2a}.rs, kernel/core, kernel/runtime/src/{session,lease/*,handoff/*}.rs

机器可读形状见 [schema.json](schema.json)。

## 为什么 `lease.rs` / `handoff.rs` 归本包（本轮归属决策）

- `lease.rs`：租约管的是**会话推进权**（D56 跨宿主推进权 + epoch 围栏），与已有的
  `session/{epoch,node,placement,header(SessionLease)}` 同一语义域；§4.2 对 iface-session 的定义
  含"**推进**"，围栏正是推进的合法性判定。依赖 `EventIo`（iface-store）单向。
- `handoff.rs`：其契约面就是 **L-C session 方法的 1:1 镜像**（`session.create/get/watch/close/deliver`、
  `operation.get/list/cancel`）+ `blocked_on` 续跑语义，属 §6.8「跨 loop 会话互通与执行交接」，
  归会话域最贴近；该文件**零 `crate::` 引用**（全 `String`/自有 DTO）。
- 归属约束：按 D96 §6「纳入既有包，不因新增源文件而另增接口包」。

## 依赖关系

| 方向 | 内容 |
|---|---|
| 本包依赖 | `agentcpm/iface-types`、`agentcpm/iface-store`（`EventIo`） |
| 被依赖 | `agentcpm/iface-policy`（`audit.rs` 用 `session::effect::EffectLevel`） |

## 完成阶段

- **本轮已完成**：`lease.rs` + `handoff.rs` verbatim 分发 + schema + 本 README。
- **后续（跨包依赖落地）**：Mint `mint.toml` 的 `[requires]` 目前只声明 `api = ">=0.1"`，不含
  `interfaces` 级依赖；本表依赖关系已写进 `schema.json` 的 `contract_deps`，是否让 mint 校验
  interface 级依赖需 Mint 侧决策，本轮不改 `mint.toml` 语义。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
