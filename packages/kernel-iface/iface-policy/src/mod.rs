//! lineage: agent-kernel:kernel/iface/src/lib.rs:900 (B, move-only 拆分自单文件 lib.rs)
//!
//! `iface-policy`：问「这个操作允不允许」（M18/M19/M21/M22）；**含出网 egress 判决**（D49）。
use super::BoxFuture;
use super::types::*;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AuditEvent {
    pub session: SessionId,
    pub call: CallId,
    pub op: String,
    pub decision: Decision,
    pub reason: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ApprovalRequest {
    pub session: SessionId,
    pub call: CallId,
    pub summary: String,
    /// 唯一合法阻塞路径（M19）；超时策略由实现决定，默认拒绝。
    pub timeout_ms: Option<u64>,
}

pub mod delegation;
pub mod egress;
pub mod review;

pub use delegation::DelegationDecision;
pub use delegation::DelegationDenyReason;
pub use delegation::DelegationGrant;
pub use delegation::DelegationLimits;
pub use delegation::DelegationRequest;
pub use egress::EgressDecision;
pub use egress::EgressDenyReason;
pub use egress::EgressRequest;
pub use review::ReviewPosition;
pub use review::ReviewRequest;
pub use review::ReviewVerdict;

pub trait PolicyContract: Send + Sync {
    /// 未决即拒：实现不可用 / 未知必须回 `Decision::Unknown` 或 `Deny`。
    fn check(&self, request: KernelRequest) -> BoxFuture<'_, Result<Decision, Error>>;

    /// **op → 副作用等级**（同步；policy 意图，不是判决点）。
    ///
    /// 默认 = iface 的 `effect_for_op`（未知 op → `SideEffect` = fail-closed）。
    /// 判决/台账/不重放在 `core::guard`；本方法只表达"这个 op 属于哪类副作用"。
    fn effect_of(&self, op: &str) -> crate::session::effect::EffectLevel {
        crate::session::effect::effect_for_op(op)
    }

    /// M22：委派上限（**default = 不允许委派**；fail-closed）。
    fn delegation_limits(&self) -> delegation::DelegationLimits {
        delegation::DelegationLimits::default()
    }

    /// **同步快路径**（D74）：能保证"判决不阻塞"的实现才返回 `Some`。
    ///
    /// 为什么需要它：宿主有 28 个授权闸门在**同步写路径**上（`-> Json` 的 handler、
    /// 持有全局状态锁），必须**立即**得到判决；而 [`Self::check`] 是 `BoxFuture`。
    /// 若无此快路径，宿主只能二选一：把 async 传染整条 dispatch 链，或阻塞等（持锁会自锁）。
    ///
    /// 约定（硬约束，D74）：
    /// - `None` = 本实现**不支持**同步判决，调用方必须按 **fail-closed** 处理
    ///   （**不得**自行 `block_on` 等待）；
    /// - 返回 `Some(d)` 时，`d` 必须与 `check` 对**同一 `KernelRequest`** 的判决**一致**
    ///   （两路不一致视为实现 bug；契约测试钉住这一点）。
    ///
    /// default impl 返回 `None`：既有实现**无需改动**，宿主自动回落到"就绪即用、未就绪即拒"。
    fn check_sync(&self, _request: &KernelRequest) -> Option<Decision> {
        None
    }
    /// 记录一条审计事件。
    ///
    /// **default = Unsupported 错误**（不是静默成功）：策略实现通常不拥有 audit sink，
    /// 真实审计由判决门（`core::guard::Guard`）负责；若某个实现声称要自己记审计，必须覆盖本方法。
    fn record_audit(&self, _event: AuditEvent) -> BoxFuture<'_, Result<(), Error>> {
        Box::pin(async move {
            Err(Error::new(
                crate::types::ErrorCategory::Internal,
                -32603,
                "record_audit not implemented by this policy (audit is enforced at the guard)",
            ))
        })
    }

    /// M19：请求人类审批（唯一合法阻塞路径）。
    ///
    /// **default = 直接拒绝**（fail-closed）：不实现审批通道的策略不能把请求"挂起"。
    fn request_approval(&self, _request: ApprovalRequest) -> BoxFuture<'_, Result<Decision, Error>> {
        Box::pin(async move { Ok(Decision::NeedsHuman) })
    }

    /// M21：出网判决（L-A 侧的异步入口）。
    ///
    /// **default impl = 拒绝**（fail-closed）：既有实现不写这个方法，就**不会**意外放行出网。
    /// 真正的"网络判决点"在 `agentcpm_core::guard::Guard::authorize_egress`（统一门 + 审计），
    /// 这里只是让 L-A 契约能表达出网请求。
    fn check_egress(&self, request: EgressRequest) -> BoxFuture<'_, Result<EgressDecision, Error>> {
        Box::pin(async move {
            Ok(EgressDecision::deny(
                EgressDenyReason::NoPolicy,
                format!("no egress policy for {}", request.target()),
            ))
        })
    }

    /// M22：委派判决（L-A 侧异步入口）。
    ///
    /// **default impl = 拒绝**（fail-closed）：既有实现不写这个方法就不会意外放大权限。
    /// 真正的登记与级联撤销在 `runtime::delegate::DelegationRegistry`；
    /// 委派判决点在 `agentcpm_core::guard::Guard::authorize_delegation`（统一门 + 审计）。
    fn check_delegation(
        &self,
        request: DelegationRequest,
    ) -> BoxFuture<'_, Result<DelegationDecision, Error>> {
        Box::pin(async move {
            Ok(DelegationDecision::deny(
                DelegationDenyReason::NoPolicy,
                format!(
                    "no delegation policy for principal {:?} (+{} ops)",
                    request.principal,
                    request.child_scope.len()
                ),
            ))
        })
    }

    /// M42：审核判决（L-A 侧异步入口）。
    ///
    /// **default impl = `Reject`**（fail-closed）：既有实现不写这个方法，审核就不会被"默认放行"。
    /// 真正的判决点 + 审计在 `agentcpm_core::guard::Guard::review`；
    /// 四位置编排/必需位置断言在 `runtime::review::ReviewPipeline`。
    fn review(&self, request: ReviewRequest) -> BoxFuture<'_, Result<ReviewVerdict, Error>> {
        Box::pin(async move {
            Ok(ReviewVerdict::Reject {
                reason: format!("no review policy for position {}", request.position.as_str()),
            })
        })
    }
}
