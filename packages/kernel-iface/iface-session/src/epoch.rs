//! lineage: agent-kernel:kernel/iface/src/session.rs:1 (A, Session v2 · V0 纯类型；D56)
//!
//! 跨宿主**推进权代次**（epoch fence）：与 [`Generation`](crate::types::Generation) **严格分离**。
//!
//! - `Generation`（M36）= 单宿主内"显式换代"（`session/bump`）；旧代次请求被拒；
//! - `Epoch`（D56）= **跨宿主夺权围栏**：租约 `SessionLease{key, epoch}` 的 epoch 单调递增，
//!   旧 epoch 的 attach / 写入 / 事件追加一律拒绝（`-32010` 家族语义，落地在 core/lease，本模块只给类型）。
//!
//! 两者**不提供互相转换**：把 generation 当 epoch 用是跨宿主双写的根因（D56 证据：三份自有实现均无 epoch）。

/// 跨宿主推进权代次（**单调**；`u64::MAX` 之后不再递增，避免回绕导致旧租约"复活"）。
///
/// 语义：
/// - 只有**严格更新**的 epoch 才能夺权（`is_stale` 判定旧值）；
/// - 相等 epoch = 同一持有者（幂等重连，不算 stale）；
/// - 与 [`Generation`](crate::types::Generation) 是不同概念、不同类型，**不能混用**。
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Epoch(u64);

impl Epoch {
    /// 初始代次（尚无任何租约时）。
    pub const INITIAL: Epoch = Epoch(0);

    /// 从原始数值构造（**不加一**；用于从持久化记录恢复）。
    pub const fn new(raw: u64) -> Self {
        Self(raw)
    }

    /// 原始数值。
    pub const fn value(self) -> u64 {
        self.0
    }

    /// 下一个代次；`u64::MAX` 时返回 `None`（**fail-closed：不回绕**）。
    pub fn next(self) -> Option<Self> {
        self.0.checked_add(1).map(Self)
    }

    /// `incoming` 是否严格更新（夺权条件）。
    pub fn is_newer_than(self, incoming: Epoch) -> bool {
        incoming.0 > self.0
    }

    /// `incoming` 是否是**过期**的（旧 epoch 必须被拒）。
    pub fn is_stale(self, incoming: Epoch) -> bool {
        incoming.0 < self.0
    }
}

impl Default for Epoch {
    fn default() -> Self {
        Self::INITIAL
    }
}

impl std::fmt::Display for Epoch {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "epoch:{}", self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::Epoch;

    #[test]
    fn epoch_is_monotonic_and_rejects_stale_values() {
        let current = Epoch::new(7);
        assert!(current.is_stale(Epoch::new(6)), "旧 epoch 必须判 stale");
        assert!(
            !current.is_stale(Epoch::new(7)),
            "同一 epoch 不算 stale（幂等重连）"
        );
        assert!(!current.is_stale(Epoch::new(8)));
        assert!(current.is_newer_than(Epoch::new(8)));
        assert!(!current.is_newer_than(Epoch::new(7)));
        assert_eq!(current.next(), Some(Epoch::new(8)));
        assert_eq!(Epoch::default(), Epoch::INITIAL);
        assert_eq!(Epoch::INITIAL.value(), 0);
    }

    #[test]
    fn epoch_next_fails_closed_at_max() {
        // 回绕会让旧租约"复活"，所以到顶必须 None（调用方据此拒绝夺权）。
        assert_eq!(Epoch::new(u64::MAX).next(), None);
    }
}
