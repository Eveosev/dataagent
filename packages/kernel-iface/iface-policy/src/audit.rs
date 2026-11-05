//! lineage: agent-kernel:kernel/core/src/guard/audit.rs (B, move-only 上移：审计是**强制面**，属契约)
//! lineage: agent-kernel:notes/kernel-policy-seam.md (A, D83②：iface 唯一契约源)
//!
//! `AuditSink`：审计落地契约（append-only；实现失败必须按 fail-closed 处理）。
//! 事件类型随契约一起上移——它们是 L-A 面的**公共词汇**，不是 core 实现细节。
//!
//! core 侧保留 `FileAuditSink`（文件实现）并通过 `pub use` 兼容旧路径。

use crate::policy::ReviewPosition;
use crate::session::effect::EffectLevel;
use crate::types::Decision;

pub struct AuditEvent {
    pub ts_ms: u64,
    pub principal: String,
    pub session: String,
    pub call: String,
    pub op: String,
    pub decision: Decision,
    pub reason: String,
}

/// **出网审计事件**（M21）：必填字段 = 请求（`target`）、判决、原因、来源（`principal`/`session`）、
/// 关联（`correlation`）；`purpose` 记录"谁要出网"。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EgressAuditEvent {
    pub ts_ms: u64,
    pub principal: String,
    pub session: String,
    pub correlation: String,
    /// `scheme://host:port`（不含凭据）。
    pub target: String,
    pub purpose: String,
    pub decision: Decision,
    /// 允许 = `allowed`；拒绝 = [`EgressDenyReason::as_str`] 的稳定串。
    pub reason: String,
}

/// **委派审计事件**（M22）：必填字段 = 父/子作用域、深度、TTL、判决、原因、主体、关联。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DelegationAuditEvent {
    pub ts_ms: u64,
    pub principal: String,
    pub session: String,
    pub correlation: String,
    /// 父作用域（逗号分隔；不含凭据）。
    pub parent: String,
    /// 子作用域（逗号分隔）。
    pub child: String,
    /// 请求里的父深度（新 grant 深度 = depth + 1）。
    pub depth: u32,
    pub ttl_ms: u64,
    pub decision: Decision,
    /// 允许 = `allowed`；拒绝 = [`DelegationDenyReason::as_str`]。
    pub reason: String,
}

/// **撤销审计事件**（M22）：级联撤销必须留下"撤了谁"的事实。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RevocationAuditEvent {
    pub ts_ms: u64,
    pub principal: String,
    pub session: String,
    pub correlation: String,
    /// 被撤销的目标 grant。
    pub grant_id: String,
    /// 实际被撤销的 grant 集合（含目标自身与所有后代；逗号分隔）。
    pub cascaded: String,
    pub reason: String,
}

/// **审核审计事件**（M42）：必填 = 位置、被审对象、策略、结论、原因、关联、来源。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReviewAuditEvent {
    pub ts_ms: u64,
    pub position: ReviewPosition,
    /// 被审对象引用（不含原文）。
    pub subject: String,
    /// 策略引用（`-` = 默认策略）。
    pub policy: String,
    /// 结论稳定串（approve / reject / needs-human / revise）。
    pub verdict: String,
    /// 结论理由/指导（Approve 为 `-`）。
    pub reason: String,
    pub correlation: String,
    pub session: String,
}

/// **effect 审计事件**（`effect.decided` / `effect.replayed-rejected`）。
///
/// 必填 = 来源（`principal`/`session`）、act 身份、op、effect、判决、原因；
/// `act` 用 `-` 表示请求未带 act（此时 `SideEffect` 会被 fail-closed 拒绝）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EffectAuditEvent {
    pub ts_ms: u64,
    pub principal: String,
    pub session: String,
    /// act 身份（`-` = 请求未带 act）。
    pub act: String,
    pub op: String,
    pub effect: EffectLevel,
    pub decision: Decision,
    pub reason: String,
}

/// 审计落地（append-only）。实现失败时调用方必须按 fail-closed 处理。
pub trait AuditSink: Send + Sync {
    fn append(&self, event: &AuditEvent) -> Result<(), String>;

    /// 追加出网审计（M21）。
    ///
    /// **default impl** 把它压成一条普通 [`AuditEvent`]（`op = net.egress:<purpose>`，
    /// reason 里带 target）——这样既有实现（含测试里的失败 sink）**无需改动**就继续可用，
    /// 且仍然"审计必填字段齐全"。`FileAuditSink` 会覆盖它写独立的 `egress.tsv`。
    fn append_egress(&self, event: &EgressAuditEvent) -> Result<(), String> {
        self.append(&AuditEvent {
            ts_ms: event.ts_ms,
            principal: event.principal.clone(),
            session: event.session.clone(),
            call: event.correlation.clone(),
            op: format!("net.egress:{}", event.purpose),
            decision: event.decision,
            reason: format!("{} target={}", event.reason, event.target),
        })
    }

    /// 追加委派审计（M22）。default impl 压成普通 [`AuditEvent`]（`op = delegation`），
    /// 既有实现无需改动；`FileAuditSink` 覆盖为独立 `delegation.tsv`。
    fn append_delegation(&self, event: &DelegationAuditEvent) -> Result<(), String> {
        self.append(&AuditEvent {
            ts_ms: event.ts_ms,
            principal: event.principal.clone(),
            session: event.session.clone(),
            call: event.correlation.clone(),
            op: "delegation".to_string(),
            decision: event.decision,
            reason: format!(
                "{} depth={} ttl_ms={} parent=[{}] child=[{}]",
                event.reason, event.depth, event.ttl_ms, event.parent, event.child
            ),
        })
    }

    /// 追加撤销审计（M22）。default impl 压成普通 [`AuditEvent`]（`op = delegation.revoke`）。
    fn append_revocation(&self, event: &RevocationAuditEvent) -> Result<(), String> {
        self.append(&AuditEvent {
            ts_ms: event.ts_ms,
            principal: event.principal.clone(),
            session: event.session.clone(),
            call: event.correlation.clone(),
            op: "delegation.revoke".to_string(),
            decision: Decision::Deny,
            reason: format!(
                "revoked grant {} (cascaded=[{}]): {}",
                event.grant_id, event.cascaded, event.reason
            ),
        })
    }

    /// 追加审核审计（M42）。default impl 压成普通 [`AuditEvent`]（`op = review:<position>`），
    /// 既有实现无需改动；`FileAuditSink` 覆盖为独立 `review.tsv`。
    fn append_review(&self, event: &ReviewAuditEvent) -> Result<(), String> {
        self.append(&AuditEvent {
            ts_ms: event.ts_ms,
            principal: "reviewer".to_string(),
            session: event.session.clone(),
            call: event.correlation.clone(),
            op: format!("review:{}", event.position.as_str()),
            decision: if event.verdict == "approve" {
                Decision::Allow
            } else {
                Decision::Deny
            },
            reason: format!(
                "subject={} policy={} verdict={} reason={}",
                event.subject, event.policy, event.verdict, event.reason
            ),
        })
    }

    /// 追加 effect 判决审计（`effect.decided`）。
    ///
    /// **default impl** 压成普通 [`AuditEvent`]（`op = effect.decided`，reason 带 act/effect），
    /// 既有实现（含测试里的失败 sink）无需改动；`FileAuditSink` 覆盖为独立 `effect.tsv`。
    fn append_effect_decided(&self, event: &EffectAuditEvent) -> Result<(), String> {
        self.append(&AuditEvent {
            ts_ms: event.ts_ms,
            principal: event.principal.clone(),
            session: event.session.clone(),
            call: event.act.clone(),
            op: "effect.decided".to_string(),
            decision: event.decision,
            reason: format!(
                "{} effect={} act={}",
                event.reason,
                event.effect.as_str(),
                event.act
            ),
        })
    }

    /// 追加「SideEffect 未确认重放被拒」审计（`effect.replayed-rejected`）。
    ///
    /// default impl 同样压成普通 [`AuditEvent`]；`FileAuditSink` 覆盖为 `effect.tsv`。
    fn append_effect_replayed_rejected(&self, event: &EffectAuditEvent) -> Result<(), String> {
        self.append(&AuditEvent {
            ts_ms: event.ts_ms,
            principal: event.principal.clone(),
            session: event.session.clone(),
            call: event.act.clone(),
            op: "effect.replayed-rejected".to_string(),
            decision: event.decision,
            reason: format!(
                "{} effect={} act={}",
                event.reason,
                event.effect.as_str(),
                event.act
            ),
        })
    }
}
