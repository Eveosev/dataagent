//! lineage: agent-kernel:kernel/iface/src/session.rs:1 (A, Session v2 · V0 纯类型；D57)
//!
//! 租户/组织标识（D57：**先只透传**——写入会话记录、attach/state 返回、事件头；
//! **暂不做租户隔离判定**，M18b 仍是最小多租户，隔离权限单独一轮再加）。
//!
//! 为什么现在就加：三份产品实现 grep 全无 tenant 概念；现在加是**可选字段零成本**，
//! 后加是破坏性变更 + 数据迁移（D57 调查 A 建议 1）。

use std::fmt;
use std::str::FromStr;

use crate::types::{Error, ErrorCategory};

/// 租户标识（字符串 newtype；字符集 `[A-Za-z0-9._:@-]`、长度 1..=128）。
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct TenantId(String);

impl TenantId {
    /// 校验并构造。
    ///
    /// # Errors
    /// 空串、超过 128 字符、或含 `[A-Za-z0-9._:@-]` 之外的字符 → `Error`（`Protocol`/`-32602`）。
    pub fn new(raw: impl Into<String>) -> Result<Self, Error> {
        let raw = raw.into();
        if raw.is_empty() || raw.len() > 128 {
            return Err(tenant_error(format!(
                "tenant id must be 1..=128 chars, got {} chars",
                raw.len()
            )));
        }
        if !raw
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '.' | '_' | ':' | '@' | '-'))
        {
            return Err(tenant_error(format!(
                "tenant id {raw:?} must match [A-Za-z0-9._:@-]"
            )));
        }
        Ok(Self(raw))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

fn tenant_error(message: impl Into<String>) -> Error {
    Error::new(ErrorCategory::Protocol, crate::ERR_INVALID_PARAMS, message)
}

impl fmt::Display for TenantId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl FromStr for TenantId {
    type Err = Error;

    fn from_str(text: &str) -> Result<Self, Self::Err> {
        Self::new(text)
    }
}
