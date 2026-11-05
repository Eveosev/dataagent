//! 能力声明：**只声明已实现的能力**；未知必需能力/字段 → 直接拒绝（不得静默忽略）。

/// 能力字段名（错误里点名"缺哪项能力"；新增字段必须同步文档与测试）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum CapabilityField {
    Completion,
    StreamingOutput,
    DuplexInput,
    ToolCalls,
    ToolResultStreaming,
    InputConsumptionAck,
    MediaInput,
    MediaOutput,
    ConfigHotUpdate,
    InterruptBackendStop,
    StateRecovery,
}

impl CapabilityField {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Completion => "completion",
            Self::StreamingOutput => "streaming_output",
            Self::DuplexInput => "duplex_input",
            Self::ToolCalls => "tool_calls",
            Self::ToolResultStreaming => "tool_result_streaming",
            Self::InputConsumptionAck => "input_consumption_ack",
            Self::MediaInput => "media_input",
            Self::MediaOutput => "media_output",
            Self::ConfigHotUpdate => "config_hot_update",
            Self::InterruptBackendStop => "interrupt_backend_stop",
            Self::StateRecovery => "state_recovery",
        }
    }
}

/// 后端能力声明（第一版：未实现的后端必须显式 false）。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SessionCapabilities {
    pub completion: bool,
    pub streaming_output: bool,
    /// 是否支持就绪后**持续输入**（duplex 模式必需）。
    pub duplex_input: bool,
    pub tool_calls: bool,
    /// 工具结果是否可作为**增量输入**回填（非增量后端只能在 commit 时接收聚合结果）。
    pub tool_result_streaming: bool,
    /// 是否能证明后端**实际消费**了输入（不能证明就必须 false，禁止伪造 consumed）。
    pub input_consumption_ack: bool,
    pub media_input: bool,
    pub media_output: bool,
    /// 可热更且**可确认生效**的配置字段名（空 = 不支持热更，必须 reopen）。
    pub config_hot_update_fields: Vec<String>,
    /// 打断能否确认"后端已停止"（false 时只能声明本地交付已停止）。
    pub interrupt_backend_stop: bool,
    /// 第一版对未实现后端必须 false（不得把重连谎报为状态恢复）。
    pub state_recovery: bool,
    /// 支持的输入/输出媒体编码（与 `MediaFormat.codec` 对应）。
    pub input_codecs: Vec<String>,
    pub output_codecs: Vec<String>,
}

impl SessionCapabilities {
    /// 该能力是否被声明为支持（用于 open 时的 fail-closed 校验）。
    pub fn supports(&self, field: CapabilityField) -> bool {
        match field {
            CapabilityField::Completion => self.completion,
            CapabilityField::StreamingOutput => self.streaming_output,
            CapabilityField::DuplexInput => self.duplex_input,
            CapabilityField::ToolCalls => self.tool_calls,
            CapabilityField::ToolResultStreaming => self.tool_result_streaming,
            CapabilityField::InputConsumptionAck => self.input_consumption_ack,
            CapabilityField::MediaInput => self.media_input,
            CapabilityField::MediaOutput => self.media_output,
            CapabilityField::ConfigHotUpdate => !self.config_hot_update_fields.is_empty(),
            CapabilityField::InterruptBackendStop => self.interrupt_backend_stop,
            CapabilityField::StateRecovery => self.state_recovery,
        }
    }
}
