//! lineage: agent-kernel:kernel/runtime/src/lease/store.rs:35 (A, 租约契约; task-105 上移 iface)
//! lineage: agent-kernel:kernel/runtime/src/lease/fence.rs:1 (B, 租约 DTO/错误)
//! lineage: agent-kernel:notes/DECISIONS.md:789 (A, D83: iface 是唯一契约源)
//!
//! **租约契约**（`LeaseStore`）与其 DTO（`Lease` / `LeaseStatus` / `LeaseError` / `ERR_LEASE_*`）。
//!
//! ## 为什么在 iface（D83）
//! `LeaseStore` 的消费方跨 crate：`host`（`lease_gate` 门面、围栏检查、D56 跨宿主推进权）
//! 与 `runtime`（`LocalLeaseStore` 本机实现）。契约型 trait 留在 runtime 会让宿主
//! "持 runtime 的 trait object"，契约源与实现层混在一起 → D83 定：**iface 是唯一契约源**。
//!
//! ## 边界
//! - **只定义契约与数据形状**，不含任何实现（`LocalLeaseStore` 仍在 runtime；hot-path 优化、
//!   增量位点、跨进程文件锁属实现细节）；
//! - `io: &dyn EventIo` 用 iface 自己的 [`EventIo`](crate::event_io::EventIo)（**唯一事件 IO 契约**）；
//! - 时间始终由调用方注入（`now_ms`），实现**不得**读系统时钟（可测性/确定性）。
//!
//! 本文件**零外部依赖**（只用 `std`）。

use crate::event_io::EventIo;

// ── 稳定错误 reason（D66：应用级错误 `code=-32000` + `data.reason`）───────────────────────
/// 审计写失败（fail-closed：操作失败且不改变内存状态）。
pub const ERR_LEASE_AUDIT: &str = "LEASE_AUDIT";
/// `ttl_ms` 非法（0 或超过上限）。
pub const ERR_LEASE_TTL: &str = "LEASE_TTL";
/// 资源被占用（已有有效租约）。
pub const ERR_LEASE_BUSY: &str = "LEASE_BUSY";
/// 旧 generation 被围栏挡住（`StaleFence`）。
pub const ERR_LEASE_STALE: &str = "LEASE_STALE";
/// 租约已过期。
pub const ERR_LEASE_EXPIRED: &str = "LEASE_EXPIRED";
/// 租约已释放（重复 release / check 已释放租约）。
pub const ERR_LEASE_RELEASED: &str = "LEASE_RELEASED";
/// 租约不存在。
pub const ERR_LEASE_NOT_FOUND: &str = "LEASE_NOT_FOUND";
/// 事件记录损坏（replay/read 解析失败）。
pub const ERR_LEASE_CORRUPT: &str = "LEASE_CORRUPT";
/// 字段非法（resource/holder 为空）。
pub const ERR_LEASE_FIELD: &str = "LEASE_FIELD";

/// 租约状态（`Expired` 由注入时钟推导后落状态；未观察到的过期仍是 `Active` + 时间越界）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LeaseStatus {
    Active,
    Expired,
    Released,
}

impl LeaseStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Active => "active",
            Self::Expired => "expired",
            Self::Released => "released",
        }
    }
}

/// 租约（占用某个资源的凭证）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Lease {
    /// 租约 id（确定性：`<resource>#g<generation>`，同资源同代唯一）。
    pub id: String,
    /// 被占用的资源名（会话推进权场景下 = `session_id`）。
    pub resource: String,
    /// 持有者节点 id（**必须**来自连接身份，不是兜底 `local`；见 task-103）。
    pub holder: String,
    /// 易主围栏代次：每次成功 acquire 递增。
    pub generation: u64,
    /// 过期时间（毫秒；由调用方注入的 `now_ms + ttl_ms` 得到）。
    pub expires_at_ms: u64,
    pub status: LeaseStatus,
}

impl Lease {
    /// 在注入时钟下是否已过期（未观察到的过期仍算 `Active` + 时间越界）。
    pub fn is_expired(&self, now_ms: u64) -> bool {
        self.status == LeaseStatus::Active && now_ms >= self.expires_at_ms
    }
}

/// 租约错误（含稳定 reason；不实现 `code()`——码由 iface `Error` 统一给）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LeaseError {
    /// 审计写失败 → 操作被拒绝（fail-closed）。
    Audit { message: String },
    /// ttl 非法（0 或超上限）。
    InvalidTtl { ttl_ms: u64, max_ttl_ms: u64 },
    /// 字段非法（resource/holder 空）。
    InvalidField { field: &'static str },
    /// 资源被占用。
    Busy { resource: String, holder: String },
    /// 旧 generation 被围栏挡住。
    StaleFence {
        lease_id: String,
        generation: u64,
        current_generation: u64,
    },
    /// 已过期。
    Expired { lease_id: String },
    /// 已释放。
    Released { lease_id: String },
    /// 不存在。
    NotFound { lease_id: String },
    /// 事件流损坏。
    Corrupt { message: String },
}

impl LeaseError {
    /// D66：应用级错误的稳定 reason（客户端按它匹配；不再用负数码）。
    pub fn app_reason(&self) -> &'static str {
        match self {
            Self::Audit { .. } => ERR_LEASE_AUDIT,
            Self::InvalidTtl { .. } => ERR_LEASE_TTL,
            Self::InvalidField { .. } => ERR_LEASE_FIELD,
            Self::Busy { .. } => ERR_LEASE_BUSY,
            Self::StaleFence { .. } => ERR_LEASE_STALE,
            Self::Expired { .. } => ERR_LEASE_EXPIRED,
            Self::Released { .. } => ERR_LEASE_RELEASED,
            Self::NotFound { .. } => ERR_LEASE_NOT_FOUND,
            Self::Corrupt { .. } => ERR_LEASE_CORRUPT,
        }
    }

    /// 可审计的简短原因串（写 `lease.event` 用）。
    pub fn reason(&self) -> &'static str {
        match self {
            Self::Audit { .. } => "audit_write_failed",
            Self::InvalidTtl { .. } => "invalid_ttl",
            Self::InvalidField { .. } => "invalid_field",
            Self::Busy { .. } => "resource_busy",
            Self::StaleFence { .. } => "stale_fence",
            Self::Expired { .. } => "ttl_expired",
            Self::Released { .. } => "already_released",
            Self::NotFound { .. } => "not_found",
            Self::Corrupt { .. } => "corrupt_event",
        }
    }
}

impl std::fmt::Display for LeaseError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Audit { message } => write!(formatter, "lease audit write failed: {message}"),
            Self::InvalidTtl { ttl_ms, max_ttl_ms } => {
                write!(formatter, "invalid ttl {ttl_ms}ms (must be 1..={max_ttl_ms})")
            }
            Self::InvalidField { field } => write!(formatter, "invalid lease field: {field}"),
            Self::Busy { resource, holder } => {
                write!(formatter, "resource {resource:?} is held by {holder:?}")
            }
            Self::StaleFence {
                lease_id,
                generation,
                current_generation,
            } => write!(
                formatter,
                "stale fence for lease {lease_id:?}: generation {generation} < current {current_generation}"
            ),
            Self::Expired { lease_id } => write!(formatter, "lease {lease_id:?} expired"),
            Self::Released { lease_id } => write!(formatter, "lease {lease_id:?} already released"),
            Self::NotFound { lease_id } => write!(formatter, "lease not found: {lease_id:?}"),
            Self::Corrupt { message } => write!(formatter, "corrupt lease event: {message}"),
        }
    }
}

impl std::error::Error for LeaseError {}

/// 宿主使用的**租约契约**（D73：依赖方持 trait object；D83：契约在 iface）。
///
/// 方法集 = 宿主实际用到的全部能力（`acquire/renew/release/check/current_holder/generation/status`
/// + 跨进程增量刷新 `refresh`）。`io` 是 iface 的事件 IO 窄接口（不是具体 store）。
pub trait LeaseStore: Send + Sync {
    /// 取得租约（先记账再改内存；失败 fail-closed）。
    ///
    /// # Errors
    /// `Busy` / `InvalidTtl` / `InvalidField` / `Audit`。
    fn acquire(
        &self,
        io: &dyn EventIo,
        session: &str,
        resource: &str,
        holder: &str,
        ttl_ms: u64,
        now_ms: u64,
    ) -> Result<Lease, LeaseError>;

    /// 续约（旧代次 → `StaleFence`）。
    ///
    /// # Errors
    /// `StaleFence` / `Released` / `Expired` / `NotFound` / `Audit`。
    fn renew(
        &self,
        io: &dyn EventIo,
        session: &str,
        lease_id: &str,
        ttl_ms: u64,
        now_ms: u64,
    ) -> Result<Lease, LeaseError>;

    /// 释放（幂等语义由调用方定义；已释放 → `Released`）。
    ///
    /// # Errors
    /// `Released` / `Expired` / `NotFound` / `StaleFence` / `Audit`。
    fn release(
        &self,
        io: &dyn EventIo,
        session: &str,
        lease_id: &str,
        now_ms: u64,
    ) -> Result<Lease, LeaseError>;

    /// 围栏检查（写方法/续约前）。
    ///
    /// # Errors
    /// `StaleFence` / `Expired` / `Released` / `NotFound`。
    fn check(
        &self,
        io: &dyn EventIo,
        session: &str,
        lease_id: &str,
        now_ms: u64,
    ) -> Result<Lease, LeaseError>;

    /// 当前有效持有者（过期/释放 → `None`）。
    fn current_holder(&self, resource: &str, now_ms: u64) -> Option<Lease>;

    /// 当前 generation（无历史 → 0）。
    fn generation(&self, resource: &str) -> u64;

    /// **增量刷新**：把该会话尚未消费的 `lease.event` 应用到内存表（O(Δ)；跨进程即时可见）。
    ///
    /// 首次触碰等价于全量重放；已对齐则空操作。
    ///
    /// # Errors
    /// `Audit` / `Corrupt`。
    fn refresh(&self, io: &dyn EventIo, session: &str) -> Result<(), LeaseError>;

    /// **全量兜底**：从事件流重建（损坏恢复/首次触碰的保守路径）。
    ///
    /// # Errors
    /// `Audit` / `Corrupt`。
    fn reload(&self, io: &dyn EventIo, session: &str) -> Result<(), LeaseError>;
}
