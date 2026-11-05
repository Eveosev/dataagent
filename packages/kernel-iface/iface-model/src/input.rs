//! 输入信封：可靠输入（请求快照/文字/工具结果）与接受/消费三态。

use super::types::{ConfigRevision, InputId, ModelSessionId};

/// 输入内容类别（**只区分数据格式**；不得夹带更新/取消/执行命令）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InputKind {
    /// request 模式的完整请求快照（含 role/多内容块/工具定义，见 `content_type`）。
    RequestSnapshot,
    /// 文本增量。
    Text,
    /// 工具结果（必须关联已登记的 `tool_call_id`）。
    ToolResult,
    /// 实时媒体帧（带序号/时间轴；由媒体通道承载）。
    Media,
}

/// 输入状态三态（**不得混用**）：accepted（已登记）→ forwarded（已交后端）→ consumed（后端证明消费）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InputStatus {
    Accepted,
    Forwarded,
    Consumed,
    Dropped,
}

/// 接受确认（`input_append` 返回；被拒时不分配 `input_seq`）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ConsumptionStatus {
    /// 后端能证明已消费。
    Consumed,
    /// 后端无确认能力（不是"已消费"）。
    Unacknowledged,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InputAccepted {
    pub input_id: InputId,
    /// 会话内单调序号（被拒的输入不占号）。
    pub input_seq: u64,
    /// 已接受的可靠性类别三态中的第一阶段。
    pub status: InputStatus,
    /// 剩余额度（发送方据此流水发送，不等一次网络往返）。
    pub remaining_items: u32,
    pub remaining_bytes: u64,
}

/// 可靠输入信封（`model.input_append` 的语义载体）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InputEnvelope {
    pub model_session_id: ModelSessionId,
    /// 客户端生成的消息 id（幂等/去重作用域：主体 + 会话 + 方法）。
    pub client_message_id: String,
    /// 提交时客户端看到/期望的配置版本（旧输入按旧配置解释）。
    pub expected_config_revision: Option<ConfigRevision>,
    pub input_id: InputId,
    /// 分段序号（从 0 起；同一 `input_id` 内单调）。
    pub chunk_seq: u32,
    /// 是否为该输入组的最后一段（等价于随后 `input_commit`，二者择一）。
    pub last_chunk: bool,
    pub kind: InputKind,
    /// `content_type` 必须与实际编码一致（如 `application/json`、`text/plain`、媒体编码）。
    pub content_type: String,
    /// 原始字节（语义由 `content_type` + `kind` 决定；不得用"不透明字节"规避共同 schema）。
    pub content: Vec<u8>,
    /// 媒体帧序号/时间轴（仅 `Media`；其它为 `None`）。
    pub media_seq: Option<u64>,
    pub media_time_ms: Option<u64>,
    pub media_duration_ms: Option<u32>,
}

/// 工具结果信封（`model.tool_result_append`；必须关联已登记 `tool_call_id`，
/// 且只允许获授权执行者或其 Agent 控制方提交——授权检查在宿主，不在本类型）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ToolResultEnvelope {
    pub model_session_id: ModelSessionId,
    pub client_message_id: String,
    pub expected_config_revision: Option<ConfigRevision>,
    pub tool_call_id: String,
    pub chunk_seq: u32,
    pub last_chunk: bool,
    pub content_type: String,
    pub content: Vec<u8>,
    /// 该结果是否来自真实执行记录（伪造结果必须被拒绝）。
    pub execution_ref: Option<String>,
}
