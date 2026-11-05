# agentcpm/iface-store

AgentCPM 接口契约包 `iface-store`（Mint `kind = "bundle"`（契约语义 = iface，Hub 兼容形态），**只定义形状，不含实现**）。

- **规范**：§4.2 iface-store（M06/M07/M10；只追加、确定性投影）；决策 D55、D83
- **源码**：`src/` **verbatim 复制**自 `kernel/iface/src/store.rs` + `kernel/iface/src/event_io.rs`（283 行，2 个文件）
- **分发形态**：Mint 扁平分发（无 Cargo.toml / 无 lib.rs）；`lib.rs` 与 `tests/` 按分发纪律不分发

## 契约摘要

**类型**：EventRecord, Record, Cursor（本包内部事件游标 `u64`）

**trait**：
- `StoreContract` — append / read / checkpoint（**异步**事件流抽象，`store.rs`）
- `EventIo` — append / read_all / last_cursor（**同步**事件读写能力面，core 机制内部使用，`event_io.rs`）

**契约依赖**：无（`event_io.rs` 零 `crate::` 引用；`store.rs` 仅用同 crate 基座类型）

**消费方**：kernel/runtime/src/session.rs, kernel/core/src/log.rs, kernel/runtime/src/delivery.rs,
kernel/core/src/{ledger,idempotency,interrupt/*}.rs, kernel/runtime/src/lease/*, kernel/host/src/transport/store_facade.rs

机器可读形状见 [schema.json](schema.json)。

## 为什么 `event_io.rs` 归本包（本轮归属决策）

- 职责完全同域：§4.2 iface-store 的措辞是"**追加 / 读历史 / 打检查点**"，`EventIo` 的三方法正是
  `append / read_all / last_cursor`；两者都是"事件事实层"的契约，只是一个 async（`StoreContract`）、
  一个 sync（`EventIo`），分别服务宿主与 core 内部机制。
- 依赖：`event_io.rs` 无代码级 `crate::` 引用（仅 doc 提及 `crate::store::EventRecord`），并入不引入新跨包依赖。
- 归属约束：按 D96 §6「新增源文件纳入既有包，不因新增源文件而另增接口包」。

## 依赖关系

| 方向 | 内容 |
|---|---|
| 本包依赖其他 iface 包 | 无 |
| 被依赖 | `agentcpm/iface-session`（`lease.rs` 的 `LeaseStore` 方法签名用 `&dyn EventIo`） |

## 完成阶段

- **本轮已完成**：`event_io.rs` verbatim 分发 + schema + 本 README。
- **命名说明（诚实标注，不在本轮修）**：`event_io::Cursor` 是 `u64`，而 `iface-types::types::Cursor` 是 `String`；
  两者不同模块、不冲突编译，但同名异义易误读。修它需改 `kernel/iface/src`（本轮禁止），列为后续契约治理项。

## 边界

只定义形状：不读文件系统、不启动进程、不做安全通道；实现见 kernel 侧各包。
