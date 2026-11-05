//! 事件类别与**五类终止**（不得互相冒充；规范 §6.1.3 / D96 修正 3）。

use super::types::{ConfigRevision, InputId, ModelSessionId, ResponseId};

/// 事件类别（可靠输出按 `event_seq` 回读；订阅者有独立 cursor）。
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum EventKind {
    /// 模型会话真正就绪（open 返回后异步到达；ready 之前拒绝生成输入）。
    SessionReady,
    InputAccepted,
    InputForwarded,
    InputConsumed,
    InputDropped {
        reason: String,
    },
    ConfigApplied {
        revision: ConfigRevision,
    },
    ResponseStarted,
    /// 可靠输出内容增量（文字/结构化；实现不得等整次生成结束才输出）。
    ContentDelta {
        bytes: Vec<u8>,
        content_type: String,
    },
    ToolCallDelta {
        tool_call_id: String,
        arguments_delta: String,
    },
    ToolCallCompleted {
        tool_call_id: String,
        name: String,
        arguments_json: String,
    },
    ToolCallAbandoned {
        tool_call_id: String,
        reason: String,
    },
    /// 用量（估算值与服务端报告值分别标记；估算不得当累计计费）。
    Usage {
        usage_json: String,
        estimated: bool,
    },
    /// 回答**正常完成**（≠ 会话关闭、≠ 订阅结束）。
    ResponseCompleted,
    /// 回答**被打断**（≠ 媒体片段正常结束）；两态分别表达。
    ResponseInterrupted {
        delivery_stopped: bool,
        backend_stop: BackendStopStatus,
    },
    /// 媒体片段正常结束（一个 response 可有多个；不等于回答完成）。
    MediaSegmentEnd {
        media_seq: u64,
    },
    /// 媒体缺口（**必须**报告，不能静默丢帧）。
    MediaGap {
        from_seq: u64,
        to_seq: u64,
        reason: String,
    },
    /// 模型会话关闭（`failed`/`unknown` 如实记录；不自动取消工具）。
    SessionClosed {
        terminal: SessionTerminal,
    },
    /// 会话失败（不可继续；资源是否回收另行记录）。
    SessionFailed {
        reason: String,
        resource_released: bool,
    },
    /// 订阅连接结束（**无推理语义**；≠ 回答完成、≠ 会话关闭）。
    SubscriptionClosed,
}

/// 打断的后端停止确认状态（不能确认就保留 unknown，禁止谎报 stopped）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum BackendStopStatus {
    Stopped,
    Unsupported,
    Unknown,
}

/// 模型会话终态（`failed`/`unknown` 的业务不可用 ≠ 资源已回收）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum SessionTerminal {
    Closed,
    Failed,
    Unknown,
}

/// **五类终止事件**的显式分类（供消费者/测试断言"谁结束了什么"）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum EndKind {
    /// 媒体片段正常结束（`EventKind::MediaSegmentEnd`）。
    MediaSegment,
    /// 回答正常完成（`EventKind::ResponseCompleted`）。
    ResponseCompleted,
    /// 回答被打断（`EventKind::ResponseInterrupted`）。
    ResponseInterrupted,
    /// 模型会话关闭（`EventKind::SessionClosed`/`SessionFailed`）。
    ModelSessionClosed,
    /// 订阅连接结束（`EventKind::SubscriptionClosed`）。
    SubscriptionClosed,
}

impl EventKind {
    /// 该事件是否属于五类终止之一；返回分类便于消费者**区分**而非合并。
    pub fn end_kind(&self) -> Option<EndKind> {
        match self {
            Self::MediaSegmentEnd { .. } => Some(EndKind::MediaSegment),
            Self::ResponseCompleted => Some(EndKind::ResponseCompleted),
            Self::ResponseInterrupted { .. } => Some(EndKind::ResponseInterrupted),
            Self::SessionClosed { .. } | Self::SessionFailed { .. } => Some(EndKind::ModelSessionClosed),
            Self::SubscriptionClosed => Some(EndKind::SubscriptionClosed),
            _ => None,
        }
    }
}

/// 共同事件头 + 类别（`event_seq` 64 位；JSON 线格式用十进制字符串）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelSessionEvent {
    pub session_id: String,
    pub model_session_id: ModelSessionId,
    pub event_seq: u64,
    pub config_revision: ConfigRevision,
    pub input_id: Option<InputId>,
    pub response_id: Option<ResponseId>,
    pub tool_call_id: Option<String>,
    pub kind: EventKind,
}
