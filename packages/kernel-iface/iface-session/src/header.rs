//! lineage: agent-kernel:kernel/iface/src/session.rs:1 (A, Session v2 · V0 纯类型；M39/M40 相关)
//!
//! 会话层级头与推进权租约（**纯数据**）。
//!
//! - [`SessionHeader`]：会话的派生关系（根/子、是否 seed、深度）——供团队编排/派生图投影使用；
//! - [`SessionLease`]：跨宿主推进权（D56：`key=session_id` + 单调 `epoch`），只有严格更新的 epoch 才能夺权。

use crate::types::SessionId;

use super::Epoch;

/// 会话层级头（派生关系的**声明**，不是派生图本身）。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SessionHeader {
    /// 父会话（根会话为 `None`）。
    pub parent: Option<SessionId>,
    /// 是否由 seed（预置内容）初始化。
    pub is_seeded: bool,
    /// 派生深度（根 = 0）。
    pub depth: u32,
}

impl SessionHeader {
    /// 根会话头（`parent=None` / `is_seeded=false` / `depth=0`）。
    pub fn root() -> Self {
        Self::default()
    }

    /// 根会话的直接子头（固定 `depth=1`）。更深层请用 [`Self::child`] 以免深度写错。
    pub fn child_of(parent: impl Into<SessionId>) -> Self {
        Self {
            parent: Some(parent.into()),
            is_seeded: false,
            depth: 1,
        }
    }

    pub fn is_root(&self) -> bool {
        self.parent.is_none()
    }

    /// 标为 seeded（预置内容初始化）。
    pub fn seeded(mut self) -> Self {
        self.is_seeded = true;
        self
    }

    /// 以当前深度为基准构造子头（`depth + 1`；到顶 `None`，fail-closed）。
    pub fn child(&self, session: impl Into<SessionId>) -> Option<Self> {
        self.depth.checked_add(1).map(|depth| Self {
            parent: Some(session.into()),
            is_seeded: false,
            depth,
        })
    }
}

/// 推进权租约（D56）：同一会话同一时刻只应有一个有效租约。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionLease {
    /// 会话键。
    pub key: SessionId,
    /// 租约代次（单调）。
    pub epoch: Epoch,
}

impl SessionLease {
    pub fn new(key: impl Into<SessionId>, epoch: Epoch) -> Self {
        Self {
            key: key.into(),
            epoch,
        }
    }

    /// 相对当前 epoch 是否**过期**（旧 epoch 必须被拒）。
    pub fn is_stale(&self, current: Epoch) -> bool {
        current.is_stale(self.epoch)
    }

    /// 本租约是否夺走 `other` 的推进权（**同会话**且 epoch 严格更新）。
    pub fn supersedes(&self, other: &SessionLease) -> bool {
        self.key == other.key && other.epoch.is_newer_than(self.epoch)
    }
}
