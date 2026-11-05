//! lineage: agent-kernel:kernel/iface/src/lib.rs:1426 (B, move-only 拆分自单文件 lib.rs)
//!
use std::fmt;
use std::str::FromStr;

use crate::types::*;

use super::env_error;

/// 环境标识的**强类型**（校验 + 保留 `local`）。
///
/// 与 [`crate::types::EnvironmentId`]（= `String`，B6 时期的线上别名，`KernelRequest.environment`
/// 用它）**互不冲突**：本类型是进程内强校验形态，二者可互相转换
/// （`From<EnvId> for EnvironmentId` / `TryFrom<EnvironmentId> for EnvId`）。
///
/// 字符集 `[A-Za-z0-9._-]`、长度 1..=64；`local` 是**保留字**（本机环境）。
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct EnvId(String);

impl EnvId {
    /// 本机环境的保留标识。
    pub const LOCAL: &'static str = "local";

    /// 校验并构造。
    pub fn new(raw: impl Into<String>) -> Result<Self, Error> {
        let raw = raw.into();
        if raw.is_empty() || raw.len() > 64 {
            return Err(env_error(format!(
                "environment id must be 1..=64 chars, got {} chars",
                raw.len()
            )));
        }
        if !raw
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '.' | '_' | '-'))
        {
            return Err(env_error(format!(
                "environment id {raw:?} must match [A-Za-z0-9._-]"
            )));
        }
        Ok(Self(raw))
    }

    /// 本机环境。
    pub fn local() -> Self {
        Self(Self::LOCAL.to_string())
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }

    pub fn is_local(&self) -> bool {
        self.0 == Self::LOCAL
    }
}

impl fmt::Display for EnvId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl FromStr for EnvId {
    type Err = Error;

    fn from_str(text: &str) -> Result<Self, Self::Err> {
        Self::new(text)
    }
}

// ── 与既有线上别名 `types::EnvironmentId`（= String）互转 ──
// 说明：`types::EnvironmentId` 是 B6 时期就有的 `String` 别名，`KernelRequest.environment`
// 用它走 L-C/L-A 边界；`EnvId` 是本轮新增的**强校验**形态。两者不重复定义。

impl From<EnvId> for EnvironmentId {
    fn from(id: EnvId) -> Self {
        id.0
    }
}

impl TryFrom<EnvironmentId> for EnvId {
    type Error = Error;

    fn try_from(raw: EnvironmentId) -> Result<Self, Self::Error> {
        Self::new(raw)
    }
}

impl<'a> TryFrom<&'a EnvironmentId> for EnvId {
    type Error = Error;

    fn try_from(raw: &'a EnvironmentId) -> Result<Self, Self::Error> {
        Self::new(raw.clone())
    }
}
