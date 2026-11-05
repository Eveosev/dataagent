//! lineage: agent-kernel:kernel/iface/src/lib.rs:42 (B, move-only 拆分自单文件 lib.rs)
//!
//! 跨契约共享的最小类型。凡规范已固定的字段不另造名字。

/// 训练侧固定字段（§3.2）：工具调用时必须可读到；走 L-C 协议层，**不得进工具参数 schema**。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CallMeta {
    pub session_id: String,
    pub call_id: String,
    pub turn: u64,
}

pub type SessionId = String;
pub type CallId = String;
pub type ActId = String;
pub type EnvironmentId = String;
pub type PrincipalId = String;
pub type TurnId = u64;
pub type Generation = u64;
pub type Cursor = u64;
pub type CheckpointId = String;
pub type AssemblyHandle = String;
pub type TraceId = String;

/// M18 裁决：**未决即拒**——`Unknown` 不得当作 `Allow`。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum Decision {
    Allow,
    Deny,
    NeedsHuman,
    Unknown,
}

impl Decision {
    pub fn as_str(self) -> &'static str {
        match self {
            Decision::Allow => "allow",
            Decision::Deny => "deny",
            Decision::NeedsHuman => "needs-human",
            Decision::Unknown => "unknown",
        }
    }
}

/// M24 完成判定。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum Verdict {
    Completed,
    Incomplete,
    Unknown,
}

/// M32 四类预算。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum BudgetClass {
    Turns,
    OutputTokens,
    ContextTokens,
    TotalTime,
}

/// A4 请求状态机。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum RequestState {
    Accepted,
    Running,
    NeedsHuman,
    Rejected,
    Completed,
    Failed,
    Cancelled,
    /// 副作用未知：**禁止自动重放**，只能查询/对账。
    Unknown,
}

impl RequestState {
    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            RequestState::Rejected | RequestState::Completed | RequestState::Failed | RequestState::Cancelled
        )
    }
    pub fn as_str(self) -> &'static str {
        match self {
            RequestState::Accepted => "accepted",
            RequestState::Running => "running",
            RequestState::NeedsHuman => "needs-human",
            RequestState::Rejected => "rejected",
            RequestState::Completed => "completed",
            RequestState::Failed => "failed",
            RequestState::Cancelled => "cancelled",
            RequestState::Unknown => "unknown",
        }
    }
}

/// A4 错误分类（L-C 错误体的 `category`）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ErrorCategory {
    Transport,
    Protocol,
    Policy,
    Execution,
    Environment,
    Resource,
    Internal,
}

/// 统一错误。`code` 用于 L-C 错误码（如 `-32006`）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Error {
    pub category: ErrorCategory,
    pub code: i32,
    pub message: String,
    pub retryable: bool,
}

impl Error {
    pub fn new(category: ErrorCategory, code: i32, message: impl Into<String>) -> Self {
        Self {
            category,
            code,
            message: message.into(),
            retryable: false,
        }
    }
    pub fn retryable(mut self, yes: bool) -> Self {
        self.retryable = yes;
        self
    }
    pub fn unsupported_abi(supported: u32) -> Self {
        Self::new(
            ErrorCategory::Protocol,
            super::ERR_UNSUPPORTED_ABI,
            format!("unsupported abi_version; supported={supported}"),
        )
    }
}

/// 一次需要裁决的调用（M18 输入形状）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KernelRequest {
    pub principal: PrincipalId,
    pub session: SessionId,
    pub call: CallId,
    pub environment: Option<EnvironmentId>,
    pub act: Option<ActId>,
    /// 逻辑操作名（如 `tool.exec` / `net.connect` / `package.install`）。
    pub op: String,
    /// 负载（形状待 L-C 定稿；策略只看 op + 摘要）。
    pub payload: Vec<u8>,
}

/// 握手五字段（12-ABI §3.5；三条线同构）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Handshake {
    pub abi_version: u32,
    pub api_version: String,
    pub flavor: Option<String>,
    /// 能力位（只增不减）；`None` = 不支持该维度。
    pub capabilities: Option<Vec<(String, bool)>>,
    pub features: Vec<String>,
    pub meta: Vec<(String, String)>,
}

impl Handshake {
    /// 本端默认宣告。
    pub fn local() -> Self {
        Self {
            abi_version: super::HANDSHAKE_ABI_VERSION,
            api_version: super::API_VERSION.to_string(),
            flavor: None,
            capabilities: None,
            features: Vec::new(),
            meta: Vec::new(),
        }
    }
}

/// 握手回应。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HandshakeReply {
    pub abi_version: u32,
    pub features: Vec<String>,
}

/// 协商：被叫方回**它支持的最高版本 ≤ 请求值**；否则 `-32006`。
pub fn negotiate(requested: u32, supported: u32) -> Result<u32, Error> {
    if supported >= 1 && requested >= 1 && supported <= requested {
        Ok(supported)
    } else {
        Err(Error::unsupported_abi(supported))
    }
}

/// 状态迁移是否合法（A4；`Unknown` 只能经对账离开，不能直接重试）。
pub fn transition_allowed(from: RequestState, to: RequestState) -> bool {
    use RequestState::*;
    match from {
        Accepted => matches!(to, Running | Rejected | Completed | Failed | Cancelled),
        Running => matches!(to, NeedsHuman | Completed | Failed | Cancelled | Unknown),
        NeedsHuman => matches!(to, Running | Rejected | Cancelled | Unknown),
        Rejected | Completed | Failed | Cancelled => false,
        Unknown => matches!(to, Completed | Failed),
    }
}

pub mod interrupt;
pub mod loop_payload;
pub mod model;

pub use loop_payload::BlockedOn;
pub use loop_payload::BlockedOnKind;
pub use loop_payload::BudgetHint;
pub use loop_payload::BudgetLeft;
pub use loop_payload::CanonicalMessage;
pub use loop_payload::CanonicalRole;
pub use loop_payload::ExecutionIdentity;
pub use loop_payload::InterruptKind;
pub use loop_payload::InterruptOutcome;
pub use loop_payload::LoopCapabilities;
pub use loop_payload::LoopEvent;
pub use loop_payload::LoopEventKind;
pub use loop_payload::LoopStatus;
pub use loop_payload::StepSemantics;
pub use loop_payload::TurnInput;
pub use loop_payload::TurnOutcome;
pub use loop_payload::TurnTerminal;
pub use model::ChatMessage;

pub use interrupt::INTERRUPT_MAX_PENDING;
pub use interrupt::InterruptEffectState;
pub use interrupt::InterruptIntent;
pub use interrupt::InterruptIntentClass;
pub use interrupt::InterruptPoint;
pub use interrupt::InterruptTarget;
pub use interrupt::InterruptTaskKind;
pub use interrupt::InterruptTaskState;
pub use interrupt::InterruptTriad;
