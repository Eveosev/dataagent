//! 模型会话标识与基础枚举（不含负载形状）。

use std::fmt;

/// 模型会话 id（新增；不复用、不携带可解析业务含义）。
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ModelSessionId(pub String);

impl ModelSessionId {
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for ModelSessionId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

/// 一次生成的 id（关联既有 operation；一个模型会话可有多次 response）。
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ResponseId(pub String);

impl ResponseId {
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// 输入组 id（一次 `input_commit` 的边界单位）。
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct InputId(pub String);

impl InputId {
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// 有效配置版本（`session_get` 同时返回 requested / effective）。
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct ConfigRevision(pub u64);

impl ConfigRevision {
    pub fn get(self) -> u64 {
        self.0
    }
}

/// 会话模式（请求式 / 双工式）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum SessionMode {
    /// 每次提交完整请求快照；`completion` 必需，`streaming_output` 可选。
    Request,
    /// 就绪后持续处理输入、输出同时进行；`duplex_input` + `streaming_output` 必需。
    Duplex,
}
