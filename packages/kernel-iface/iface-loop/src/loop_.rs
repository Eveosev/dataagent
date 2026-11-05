//! lineage: agent-kernel:kernel/iface/src/lib.rs:745 (B, move-only 拆分自单文件 lib.rs)；task-79 补载荷
//!
//! `iface-loop`：推进/中断/查状态（M01/M02/M04）；**实现者是核外 loop**（Rust/Node）。
//!
//! ## 同步立即 Ready（D74）
//!
//! 本契约的方法返回 `BoxFuture`，但**实现必须"立即 Ready"**：future 在第一次 poll 时就返回
//! `Ready`，不得真正 `.await` 任何 I/O、定时器或跨进程调用。`BoxFuture` 只是为将来
//! streaming（`streaming_events` 能力）预留的**形状**，不代表允许在 `step` 里做长阻塞。
//! 需要 I/O 的实现要把 I/O 放在自己的执行器里推进，`step` 只做"推进一步状态机"。
//!
//! ## 可替换性（规范 `## 可替换性契约`，D73）
//!
//! 一个 loop 实现「可替换」= 存在第二个实现且**内核侧零改动**可切换。判定只认可执行测试
//! （同调用点换实现、行为变、调用方不变）。因此本契约的载荷必须覆盖内核真实依赖面：
//! 见 [`TurnInput`]/[`StepOutcome`]/[`LoopStatus`]/[`InterruptOutcome`]——这些类型在
//! [`super::types::loop_payload`] 里，本文件只定义 trait 与 `describe`/`step` 的返回枚举。
//!
//! 载荷即契约：字段只增不改（AIP-180）；`#[non_exhaustive]` 的枚举允许将来加变体。
use super::BoxFuture;
use super::types::*;

/// loop 能力声明（§6.8 交接要求：step 语义、交接点、是否可暂停）。
///
/// 原 `handoff_ready` / `can_pause` 两个独立布尔已**归一**进 [`LoopCapabilities`]
/// （`handoff_ready` / `pausable`），避免"同一概念两套字段"（违反可替换性契约第 2 条）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LoopDescriptor {
    pub id: String,
    pub language: String,
    /// step 的粒度语义（实现方声明，内核不得假定）。
    pub step_semantics: StepSemantics,
    /// 9 个能力位（默认全 false = fail-closed）。
    pub capabilities: LoopCapabilities,
}

/// `step` 的结果。原实现的 `Idle` 已删除（内核无需知道"空闲"，那是 `status` 的事）。
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum StepOutcome {
    /// 推进成功：本步产生了这些事件（`seq` 为该批最后一条的序号）。
    Advanced {
        turn: TurnId,
        events: Vec<LoopEvent>,
        seq: u64,
    },
    /// 需要人介入才能继续（D63 G1 的 `blocked_on` 派生投影）。
    WaitingHuman { blocked_on: Vec<BlockedOn> },
    /// 该 turn 已结束。
    Finished { outcome: TurnOutcome },
    /// 失败（可重试性由 `Error`/`code` 决定；**副作用未知**时用 `Unknown` 而非 `Failed`）。
    Failed {
        code: String,
        message: String,
        stop_reason: Option<String>,
    },
    /// 副作用**未确认**：禁止自动重放，只能 `status`/对账（对齐 M04 与 L-C 的 `status:unknown`）。
    Unknown { reconcile: bool },
}

pub trait LoopContract: Send + Sync {
    /// 声明自己是谁、什么粒度、支持哪些能力。**必须立即 Ready**（D74）。
    fn describe(&self) -> BoxFuture<'_, LoopDescriptor>;

    /// 推进一步（粒度由 [`LoopDescriptor::step_semantics`] 决定）。
    ///
    /// `input.execution` 是必需的可归因身份；重复的 `idempotency_key` 不得重复产生副作用。
    /// **必须立即 Ready**（D74）：不得在此 future 内 `.await` I/O。
    fn step(
        &self,
        session: &SessionId,
        turn: TurnId,
        input: TurnInput,
    ) -> BoxFuture<'_, Result<StepOutcome, Error>>;

    /// 请求中断。四态可辨：[`InterruptOutcome`]——"太晚" ≠ "不支持" ≠ "已终态"。
    /// `detail` 承载自由文本说明；M04 的 6 类意图走 `types::interrupt::InterruptIntent`。
    fn interrupt(
        &self,
        session: &SessionId,
        kind: InterruptKind,
        detail: &str,
    ) -> BoxFuture<'_, Result<InterruptOutcome, Error>>;

    /// 只读状态投影（权威状态在会话记录；此处是派生视图）。
    fn status(&self, session: &SessionId) -> BoxFuture<'_, Result<LoopStatus, Error>>;
}
