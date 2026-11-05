//! lineage: agent-kernel:kernel/iface/src/lib.rs:1053 (B, move-only 拆分自单文件 lib.rs)
//!
use crate::types::*;

// ── M22 能力委派（实现包 `authz-delegate`；规范 §3 M22）──
//
// 硬语义：**交给子代理只能缩小不能扩大**，带深度与生命期上限；撤销必须级联撤到所有下游。
// 这里定义契约数据；判决点/审计在 `core::guard`，登记与级联撤销在 `runtime::delegate`。

/// 一次委派请求（父作用域 → 子作用域）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DelegationRequest {
    /// 父作用域的能力集合（委派来源；根委派 = 调用方自身能力）。
    pub parent_scope: Vec<String>,
    /// 期望的子作用域能力集合（**必须 ⊆ parent_scope**）。
    pub child_scope: Vec<String>,
    /// **父的深度**（根委派 = 0）；新 grant 的深度 = `depth + 1`。
    pub depth: u32,
    /// 生命期（毫秒；`0` = 立即过期 → 拒绝）。
    pub ttl_ms: u64,
    /// 委派主体（审计必填）。
    pub principal: String,
    /// 关联 ID（审计必填字段之一；如触发委派的 act/call）。
    pub correlation_id: Option<String>,
    /// 父 grant（根委派为 `None`）；用于级联撤销的父子链与"不得超出父 grant"校验。
    pub parent_grant: Option<String>,
}

impl DelegationRequest {
    /// `child_scope - parent_scope`（排序去重的越权能力；审计/错误信息用）。
    pub fn excess_ops(&self) -> Vec<String> {
        use std::collections::BTreeSet;
        let parent: BTreeSet<&str> = self.parent_scope.iter().map(String::as_str).collect();
        let excess: BTreeSet<&str> = self
            .child_scope
            .iter()
            .map(String::as_str)
            .filter(|op| !parent.contains(op))
            .collect();
        excess.into_iter().map(str::to_string).collect()
    }

    /// **子集判定**：`child_scope ⊆ parent_scope`（只看集合语义，重复项不影响结论）。
    pub fn is_subset(&self) -> bool {
        self.excess_ops().is_empty()
    }

    /// 基本合法性：父/子作用域都不得为空。
    pub fn is_well_formed(&self) -> bool {
        !self.parent_scope.is_empty() && !self.child_scope.is_empty()
    }
}

/// 一条委派授予（登记表里的一条；后续用它与撤销都以它为准）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DelegationGrant {
    pub grant_id: String,
    /// 实际授予的能力集合（⊆ 父作用域；根委派 ⊆ 调用方能力）。
    pub scope: Vec<String>,
    /// 还能继续委派的层数（`0` = 叶子，不能再往下委派）。
    pub depth_remaining: u32,
    /// 过期时间（毫秒时间戳；`0` = 不限期，但正常路径不会产生 0）。
    pub expires_at_ms: u64,
    /// 父 grant（根委派为 `None`）。
    pub parent_grant: Option<String>,
}

impl DelegationGrant {
    /// 该 grant 是否覆盖某个操作。
    pub fn allows(&self, op: &str) -> bool {
        self.scope.iter().any(|item| item == op)
    }

    /// 是否已过期（`expires_at_ms == 0` 视为不限期，避免"忘设 ttl 反而永不过期"之外的歧义）。
    pub fn is_expired(&self, now_ms: u64) -> bool {
        self.expires_at_ms != 0 && now_ms >= self.expires_at_ms
    }
}

/// 委派/使用被拒绝的原因（稳定串进审计与 L-C 错误体）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum DelegationDenyReason {
    /// 策略不允许委派（`allow=false` / 上限为 0）。
    NoPolicy,
    /// 子作用域超出父作用域（**只能缩小不能扩大**）。
    ScopeEscalation,
    /// 深度超上限（含父 grant 已无剩余深度）。
    DepthExceeded,
    /// `ttl_ms == 0`（立即过期）。
    TtlZero,
    /// `ttl_ms` 超上限。
    TtlExceeded,
    /// 父/目标 grant 不存在。
    GrantNotFound,
    /// 已被撤销（含被上级级联撤销）。
    Revoked,
    /// 已过期。
    Expired,
    /// 使用 grant 时操作不在其作用域内。
    OpNotInScope,
    /// 审计写失败 → 拒绝（fail-closed）。
    AuditUnavailable,
    /// 请求本身非法（空作用域等）。
    InvalidRequest,
}

impl DelegationDenyReason {
    pub fn as_str(self) -> &'static str {
        match self {
            DelegationDenyReason::NoPolicy => "no-policy",
            DelegationDenyReason::ScopeEscalation => "scope-escalation",
            DelegationDenyReason::DepthExceeded => "depth-exceeded",
            DelegationDenyReason::TtlZero => "ttl-zero",
            DelegationDenyReason::TtlExceeded => "ttl-exceeded",
            DelegationDenyReason::GrantNotFound => "grant-not-found",
            DelegationDenyReason::Revoked => "revoked",
            DelegationDenyReason::Expired => "expired",
            DelegationDenyReason::OpNotInScope => "op-not-in-scope",
            DelegationDenyReason::AuditUnavailable => "audit-unavailable",
            DelegationDenyReason::InvalidRequest => "invalid-request",
        }
    }
}

/// 委派判决：**复用 [`Decision`]**，拒绝时带明确原因。
///
/// 「未决即拒」：只有 `Decision::Allow` 才允许建立委派/使用 grant。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DelegationDecision {
    pub decision: Decision,
    pub reason: Option<DelegationDenyReason>,
    pub detail: String,
}

impl DelegationDecision {
    pub fn allow() -> Self {
        Self {
            decision: Decision::Allow,
            reason: None,
            detail: "allowed".to_string(),
        }
    }

    pub fn deny(reason: DelegationDenyReason, detail: impl Into<String>) -> Self {
        Self {
            decision: Decision::Deny,
            reason: Some(reason),
            detail: detail.into(),
        }
    }

    pub fn is_allowed(&self) -> bool {
        self.decision == Decision::Allow
    }
}

/// M22：委派上限（策略意图数据；**default = 不允许委派**，fail-closed）。
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct DelegationLimits {
    /// 是否允许委派（默认 `false`）。
    pub allow: bool,
    /// 最大深度（根委派 depth=0 → 新 grant 深度 1）。
    pub max_depth: u32,
    /// 最大 TTL（毫秒）。
    pub max_ttl_ms: u64,
}
