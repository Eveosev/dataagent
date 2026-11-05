//! lineage: agent-kernel:kernel/iface/src/lib.rs:727 (B, move-only 拆分自单文件 lib.rs)
//!
//! `iface-session`：创建/推进/恢复/归档（M01/M03/M05）；实现者通常是 kernel core。
//!
//! 本模块再分两层：
//! - **契约**：[`SessionContract`]（异步、L-A 调用面）；
//! - **session v2 · V0 纯类型**（D55/D56/D57 + Rust Agent 文档对齐）：
//!   [`SessionIdentity`] / [`Epoch`] / [`TenantId`] / [`NodeId`] / [`PlacementMode`] /
//!   [`SessionSeq`] / [`LogOffset`] / [`SessionHeader`] / [`SessionLease`] / [`EffectLevel`]。
//!   这些**只有类型与不变量，没有行为**：推进权围栏（D56）与 effect 判决在 core 落地（另任务）。

use super::BoxFuture;
use super::types::*;

pub mod effect;
pub mod epoch;
pub mod header;
pub mod identity;
pub mod node;
pub mod placement;
pub mod seq;
pub mod tenant;
pub mod view;

pub use effect::{EffectLevel, OP_EFFECT_MAP, effect_for_op};
pub use epoch::Epoch;
pub use header::{SessionHeader, SessionLease};
pub use identity::SessionIdentity;
pub use node::{LOCAL_NODE, MAX_NODE_ID_LEN, NodeId};
pub use placement::PlacementMode;
pub use seq::{LogOffset, SessionSeq};
pub use tenant::TenantId;
pub use view::{SessionFactsView, SessionStatusView};

pub trait SessionContract: Send + Sync {
    fn create(&self, parent: Option<SessionId>) -> BoxFuture<'_, Result<SessionId, Error>>;
    fn advance(&self, session: &SessionId, turn: TurnId) -> BoxFuture<'_, Result<(), Error>>;
    fn suspend(&self, session: &SessionId) -> BoxFuture<'_, Result<(), Error>>;
    fn resume(&self, session: &SessionId) -> BoxFuture<'_, Result<(), Error>>;
    fn archive(&self, session: &SessionId) -> BoxFuture<'_, Result<(), Error>>;
    /// 会话代次（M36）：旧代次请求必须被拒。
    fn generation(&self, session: &SessionId) -> BoxFuture<'_, Result<Generation, Error>>;
    /// 收件箱排空时机（M05）：返回下一次被模型看到的输入条数。
    fn drain_inbox(&self, session: &SessionId) -> BoxFuture<'_, Result<usize, Error>>;

    /// **读视图**（D76 接缝切片）：合并"内存事实 + 事件投影"后的可观察视图；会话不存在 → `None`。
    ///
    /// 为什么要它：宿主 71 处字段读取全部围绕"读视图"展开（`spec`/`status` 子集），
    /// 把这些字段直接暴露成方法会让契约爆炸；一个视图对象即可覆盖。
    ///
    /// default impl = `None`（fail-closed：**"不支持读视图"不等于"会话不存在"**，
    /// 调用方必须区分 `Ok(None)` 与"未实现"——因此实现方若要支持读视图**必须重写本方法**）。
    fn facts(&self, _session: &SessionId) -> BoxFuture<'_, Result<Option<SessionFactsView>, Error>> {
        // 复用已登记的 `-32085 METHOD_NOT_IMPLEMENTED`（**不新增错误码**，遵守 D66）。
        Box::pin(async {
            Err(Error::new(
                ErrorCategory::Protocol,
                -32085,
                "METHOD_NOT_IMPLEMENTED: facts",
            ))
        })
    }

    /// 会话 id 列表（`session/list` 用；**顺序不承诺**）。
    ///
    /// default impl = 空表（"不支持枚举"）；调用方不得把它当作"没有任何会话"。
    fn list_ids(&self) -> BoxFuture<'_, Result<Vec<SessionId>, Error>> {
        Box::pin(async {
            Err(Error::new(
                ErrorCategory::Protocol,
                -32085,
                "METHOD_NOT_IMPLEMENTED: list_ids",
            ))
        })
    }

    /// 会话计数（判空/健康检查用）。
    fn count(&self) -> BoxFuture<'_, Result<usize, Error>> {
        Box::pin(async {
            Err(Error::new(
                ErrorCategory::Protocol,
                -32085,
                "METHOD_NOT_IMPLEMENTED: count",
            ))
        })
    }
}
