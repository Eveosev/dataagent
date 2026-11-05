//! 会话**读视图**（D76 接缝的最小白切片）：让宿主/调用方经契约拿到"读投影"，而不是摸内存表。
//!
//! 设计取舍：
//! - 复用 V0 已有类型 [`SessionIdentity`]/[`SessionHeader`]，只补一个极小的 `SessionStatusView`；
//! - **不含** `epoch` 权威值（`spec.epoch` 在宿主是 `LeaseGate` 的投影缓存，权威在 lease 门面）；
//! - **不含** `live_turns` 之外的宿主内部计数，避免把"非持久内存态"写进 ABI。
//!
//! lineage: agent-kernel:notes/kernel-session-seam-plan.md:1 (A, session 接缝 Phase 2)

use super::{SessionHeader, SessionIdentity};

/// 会话状态视图：宿主 `SessionStatus` 中**可观察、可投影**的子集。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SessionStatusView {
    /// 生命周期任务 id（M02 关联；用 `String` 避免把宿主 `TaskId` 类型抬进契约）。
    pub tasks: Vec<String>,
    /// 读游标（"已完成任务数"语义；**不是**事件游标）。
    pub read_cursor: u64,
    /// 是否已关闭（`true` = 归档/终止；读取投影仍可返回它）。
    pub closed: bool,
}

/// 一个会话的完整读视图（身份 + 层级 + 状态）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionFactsView {
    /// 会话身份（`SessionIdentity`）。
    ///
    /// # ⚠️ 语义：**装配方注入，不得由日志推导**
    ///
    /// 事件日志里**没有** principal / tenant / 环境信息——它们是**运行环境事实**，不是会话历史。
    /// 因此：
    /// - **权威来源 = 装配方**（宿主/适配层在构造视图时注入）；
    /// - 若实现方从日志重导，**只能给占位值**（本仓 `CoreSessions` 用 `principal="kernel"` +
    ///   本地环境），并在文档/装配层标注"这是占位"；
    /// - 消费者**不得**把占位值当真实身份使用（授权判定必须用传输层身份，见 D67/D70）。
    ///
    /// 预留：后续可加 `identity_source: Option<String>`（`"transport"` / `"assembler"` /
    /// `"placeholder"`）让占位态**显式可判**；本轮 additive 不加字段（避免破坏既有构造点）。
    /// 见 `notes/kernel-session-seam-plan.md` §9.2 的"已知简化"。
    pub identity: SessionIdentity,
    pub header: SessionHeader,
    pub status: SessionStatusView,
}
