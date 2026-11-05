//! lineage: agent-kernel:kernel/iface/src/lib.rs:923 (B, move-only 拆分自单文件 lib.rs)
//!
use crate::types::*;

// ── M21 出网管控（D49：网络契约并入 `iface-policy`，**不新增第 9 个 iface**）──
//
// 「任何对外网络连接都必须经过判定，不允许旁路」——所以这里定义的是**唯一**的出网请求类型：
// 实现包（`net-guard` / `net-proxy`）只接受本类型走判定，不提供"直接连"的旁路 API。

/// 一次出网请求（M21 判决输入）。
///
/// **不做 DNS 解析**：`host` 是调用方声明要去的主机名/IP 字面量。解析后的 IP 再判一次
/// （防 DNS rebinding）属实现包/后续工作，见 `notes/kernel-m21-net-guard.md` 未做项。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EgressRequest {
    /// 本次出网尝试的标识（审计与对账用；调用方生成，唯一）。
    pub id: String,
    /// 目标主机（域名或 IP 字面量）。
    pub host: String,
    /// 目标端口。
    pub port: u16,
    /// 协议 scheme（如 `http` / `https` / `tcp`）。
    pub scheme: String,
    /// 逻辑用途（如 `model.call` / `tool.exec`）——审计必填，用来区分"谁要出网"。
    pub purpose: String,
    /// 发起会话（审计必填字段；`None` = 内核自身发起）。
    pub session: Option<SessionId>,
    /// 关联 ID（引用触发这次出网的 act/call；审计必填字段之一，`None` = 无关联）。
    pub correlation_id: Option<String>,
}

impl EgressRequest {
    /// 审计/日志用目标描述（**不含凭据**）：`scheme://host:port`。
    pub fn target(&self) -> String {
        format!("{}://{}:{}", self.scheme, self.host, self.port)
    }

    /// 是否本机回环目标（`localhost` / `127.0.0.0/8` / `::1`）。
    ///
    /// 回环**不是出网**（本机模型 `127.0.0.1:8080` 属内部）；是否允许由策略的
    /// 「允许回环」开关决定（见 `net-guard` 的 `allow_loopback`）。
    pub fn is_loopback(&self) -> bool {
        let host = self.host.trim().to_ascii_lowercase();
        host == "localhost" || host == "::1" || host == "[::1]" || host.starts_with("127.")
    }

    /// 基本合法性：空 host / 空 scheme / 端口 0 → 非法（判决必须拒绝）。
    pub fn is_well_formed(&self) -> bool {
        !self.host.trim().is_empty() && !self.scheme.trim().is_empty() && self.port != 0
    }
}

/// 出网拒绝原因（明确分类；审计与排障都要能回答"为什么不让连"）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum EgressDenyReason {
    /// 没有可用策略 / 策略为空（allow 列表为空）→ 默认拒绝。
    NoPolicy,
    /// host 命中 deny 列表（**deny 优先于 allow**）。
    DeniedHost,
    /// host 不在 allow 列表（默认 deny 的形态）。
    HostNotAllowed,
    /// 端口不在允许集合。
    PortNotAllowed,
    /// 协议不在允许集合。
    SchemeNotAllowed,
    /// 目标是回环，但策略不允许回环。
    LoopbackNotAllowed,
    /// 请求本身非法（空 host/scheme、端口 0）。
    InvalidRequest,
    /// 审计写失败 → 不允许放行（fail-closed）。
    AuditUnavailable,
}

impl EgressDenyReason {
    /// 稳定字符串（进审计与 L-C 错误体，**不得随意改**）。
    pub fn as_str(self) -> &'static str {
        match self {
            EgressDenyReason::NoPolicy => "no-policy",
            EgressDenyReason::DeniedHost => "denied-host",
            EgressDenyReason::HostNotAllowed => "host-not-allowed",
            EgressDenyReason::PortNotAllowed => "port-not-allowed",
            EgressDenyReason::SchemeNotAllowed => "scheme-not-allowed",
            EgressDenyReason::LoopbackNotAllowed => "loopback-not-allowed",
            EgressDenyReason::InvalidRequest => "invalid-request",
            EgressDenyReason::AuditUnavailable => "audit-unavailable",
        }
    }
}

/// 出网判决：**复用 [`Decision`]**（Allow / Deny / NeedsHuman / Unknown），Deny 时带明确原因。
///
/// 「未决即拒」同样适用：只有 `Decision::Allow` 才允许真正连接；
/// `NeedsHuman` / `Unknown` 都不放行（[`Self::is_allowed`] 返回 false）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EgressDecision {
    pub decision: Decision,
    /// Deny 时的分类原因（非 Deny 时为 None）。
    pub reason: Option<EgressDenyReason>,
    /// 人读原因（审计/日志；不含凭据）。
    pub detail: String,
}

impl EgressDecision {
    pub fn allow() -> Self {
        Self {
            decision: Decision::Allow,
            reason: None,
            detail: "allowed".to_string(),
        }
    }

    pub fn deny(reason: EgressDenyReason, detail: impl Into<String>) -> Self {
        Self {
            decision: Decision::Deny,
            reason: Some(reason),
            detail: detail.into(),
        }
    }

    pub fn needs_human(detail: impl Into<String>) -> Self {
        Self {
            decision: Decision::NeedsHuman,
            reason: None,
            detail: detail.into(),
        }
    }

    /// **只有 Allow 为 true**（NeedsHuman / Unknown / Deny 都不放行）。
    pub fn is_allowed(&self) -> bool {
        self.decision == Decision::Allow
    }
}
