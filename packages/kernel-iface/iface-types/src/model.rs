//! lineage: agent-kernel:kernel/runtime/src/model/openai/payload.rs:12 (B, move-only 上移：DTO 进契约)
//!
//! `ChatMessage`：L-C 编解码的**公共词汇**（不是实现细节）→ 放 iface，宿主/运行时共用一个类型。
//!
//! 为什么上移（task-95 / D73）：
//! - 宿主此前通过 `pub(crate) use agentcpm_runtime::model::ChatMessage` 拿它 → replaceability R1-a
//!   （re-export 放大泄漏面）；
//! - DTO 进契约后，宿主 `use agentcpm_iface::…` 不触发 R1；runtime 侧保留 `pub use` 兼容旧路径。

/// 一条 chat 消息（`role` + `content` 都是字符串；多模态 content 数组暂不支持）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ChatMessage {
    /// 必须 ∈ `system` / `user` / `assistant` / `tool`（校验在解码侧，本 DTO 不重复校验）。
    pub role: String,
    /// 文本内容（UTF-8）。
    pub content: String,
}

impl ChatMessage {
    pub fn new(role: impl Into<String>, content: impl Into<String>) -> Self {
        Self {
            role: role.into(),
            content: content.into(),
        }
    }

    pub fn system(content: impl Into<String>) -> Self {
        Self::new("system", content)
    }

    pub fn user(content: impl Into<String>) -> Self {
        Self::new("user", content)
    }

    pub fn assistant(content: impl Into<String>) -> Self {
        Self::new("assistant", content)
    }
}
