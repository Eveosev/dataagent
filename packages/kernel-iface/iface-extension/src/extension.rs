//! lineage: agent-kernel:kernel/iface/src/lib.rs:1879 (B, move-only 拆分自单文件 lib.rs)
//!
//! `iface-extension`：装配协议/状态机/快照/作用域（M11/M12/M13/M17）。
use super::BoxFuture;
use super::types::*;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ComponentContract {
    pub name: String,
    pub version: String,
    /// 声明的 `[requires] api`（semver）。
    pub requires_api: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AssemblyIntent {
    pub session: SessionId,
    pub act: Option<ActId>,
    /// 声明式装配数据（L-D；不是代码）。
    pub payload: Vec<u8>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum AssemblyState {
    Pending,
    Ready,
    Failed,
    RolledBack,
}

pub trait ExtensionContract: Send + Sync {
    fn describe(&self) -> ComponentContract;
    /// 提交即返回句柄（D21：act 是触发，不是完成点）。
    fn on_assembly_intent(&self, intent: AssemblyIntent) -> BoxFuture<'_, Result<AssemblyHandle, Error>>;
    fn assembly_status(&self, handle: &AssemblyHandle) -> BoxFuture<'_, Result<AssemblyState, Error>>;
    fn deactivate(&self, handle: &AssemblyHandle) -> BoxFuture<'_, Result<(), Error>>;
}
