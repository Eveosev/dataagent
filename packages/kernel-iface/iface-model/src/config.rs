//! 模型会话配置与能力相关的基础形状（**整份替换**语义，无 JSON Patch）。

use super::types::{ConfigRevision, SessionMode};

/// 模型逻辑绑定（避免把厂商密钥放进公开配置：这里只放**引用**）。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ModelBinding {
    /// 逻辑模型名（宿主解析到具体端点；不是厂商 SDK 类型）。
    pub model: String,
    /// 端点/环境引用（宿主侧解析；不得内联密钥）。
    pub endpoint_ref: Option<String>,
    /// 厂商扩展（带命名空间与版本，由后端适配器校验）。
    pub extensions: Vec<(String, String)>,
}

/// 媒体格式（实时输入/输出用；空 = 该方向不支持的显式声明）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MediaFormat {
    /// 编码名（如 `pcm16`/`opus`/`jpeg`；由能力声明决定合法集合）。
    pub codec: String,
    /// 采样率或帧率（音频 Hz / 视频 fps；不适用的方向为 `None`）。
    pub rate_hz: Option<u32>,
    /// 通道数（音频；视频为 `None`）。
    pub channels: Option<u16>,
}

/// 生成设置（与 `model.request` 的输入保持一致，不引入第二套含义）。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct GenerationSettings {
    pub max_tokens: Option<u32>,
    pub temperature_milli: Option<u32>,
    pub top_p_milli: Option<u32>,
    pub stop_sequences: Vec<String>,
}

/// 队列/内容限额（**实际采用值**在 `session_open`/`media_attach` 返回；此处是请求值，
/// 宿主可收紧，不得放宽到配置声明的上限之外）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SessionLimits {
    pub control_queue_items: u32,
    pub control_queue_bytes: u64,
    pub reliable_input_items: u32,
    pub reliable_input_bytes: u64,
    pub inline_block_bytes: u64,
    pub output_record_bytes: u64,
}

impl Default for SessionLimits {
    fn default() -> Self {
        Self {
            control_queue_items: 32,
            control_queue_bytes: 256 * 1024,
            reliable_input_items: 64,
            reliable_input_bytes: 4 * 1024 * 1024,
            inline_block_bytes: 64 * 1024,
            output_record_bytes: 64 * 1024 * 1024,
        }
    }
}

/// 超时（毫秒；`0` = 显式不设该超时，禁止静默套默认值改变语义）。
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SessionTimeouts {
    pub open_ms: u64,
    pub generate_ms: u64,
    pub close_drain_ms: u64,
}

/// 建立模型会话的**整份配置**（`session_update` 亦用整份替换 + `expected_revision`）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelSessionConfig {
    pub binding: ModelBinding,
    pub mode: SessionMode,
    /// 输入格式（可靠文本不受限；媒体方向在此声明）。
    pub input_formats: Vec<MediaFormat>,
    /// 输出格式（实时输出方向）。
    pub output_formats: Vec<MediaFormat>,
    /// 工具目录引用（快照 id/版本；**不得**在会话内静默扩权）。
    pub tool_catalog_ref: Option<String>,
    pub generation: GenerationSettings,
    pub limits: SessionLimits,
    pub timeouts: SessionTimeouts,
    /// 厂商/部署扩展（命名空间 + 值；未知必需项由后端拒绝）。
    pub extensions: Vec<(String, String)>,
    /// 请求的配置版本（`session_update` 必须携带 `expected_revision` 作 CAS）。
    pub expected_revision: Option<ConfigRevision>,
}
