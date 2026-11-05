# agentcpm/iface-policy

AgentCPM 接口契约包 `iface-policy`（Mint `kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-policy（含 egress / delegation / review / **audit**，D49/D83）；决策 D49、D55、D83
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/policy/` + `kernel/iface/src/audit.rs`（808 行，5 个文件）
- **分发形态**：Mint 扁平分发（无 Cargo.toml / 无 lib.rs）；`lib.rs` 与 `tests/` 按分发纪律不分发

## 契约摘要

**类型**：DelegationRequest, DelegationGrant, DelegationLimits, DelegationDenyReason, DelegationDecision,
EgressRequest, EgressDenyReason, EgressDecision, ApprovalRequest, ReviewPosition, ReviewVerdict, ReviewRequest,
AuditEvent, EgressAuditEvent, DelegationAuditEvent, RevocationAuditEvent, ReviewAuditEvent, EffectAuditEvent

**trait**：
- `PolicyContract` — authorize / authorize_egress / authorize_delegation / review（`policy/mod.rs`）
- `AuditSink` — record（append-only；实现失败必须按 **fail-closed** 处理，`audit.rs`）

**契约依赖**：`agentcpm/iface-types`（`Decision`）、`agentcpm/iface-session`（`EffectLevel`）

**消费方**：kernel/core/src/guard/*, kernel/runtime/src/{policy,net_guard,delegate,review,egress}.rs,
kernel/host/src/transport/policy.rs

机器可读形状见 [schema.json](schema.json)。

## 为什么 `audit.rs` 归本包（本轮归属决策）

- 职责同域：审计是**裁决的强制面**——`audit.rs` 的事件类型逐条对应 policy 的判决对象
  （`EgressAuditEvent` ↔ `egress`、`DelegationAuditEvent`/`RevocationAuditEvent` ↔ `delegation`、
  `ReviewAuditEvent` ↔ `review`、`EffectAuditEvent` ↔ `EffectLevel`），拒绝原因串复用
  `EgressDenyReason`/`DelegationDenyReason::as_str()`。
- 既有 schema 已声明 `AuditEvent` 类型（此前由 `policy/mod.rs` 的同名结构满足）；包职责描述中
  "问这个操作允不允许"必然包含"判决必须留痕"，故并入 rather than 新增包。
- 依赖：`ReviewPosition`（同包）、`EffectLevel`（iface-session）、`Decision`（iface-types），均为单向。

## 依赖关系

| 方向 | 内容 |
|---|---|
| 本包依赖 | `agentcpm/iface-types`（`Decision`）、`agentcpm/iface-session`（`EffectLevel`） |
| 被依赖 | 无 |

## 完成阶段

- **本轮已完成**：`audit.rs` verbatim 分发 + schema + 本 README。
- **后续（需改 kernel，本轮禁止）**：`AuditEvent` 在 `policy/mod.rs:8` 与 `audit.rs:13` **重复定义**
  （字段不同：前者 `session: SessionId/call: CallId`，后者全 `String` + `ts_ms`/`principal`）。
  契约源应为 `audit.rs`，收敛需改 `kernel/iface/src` 并由实现侧跟随，列为后续项。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
