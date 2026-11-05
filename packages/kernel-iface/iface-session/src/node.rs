//! lineage: agent-kernel:notes/kernel-distributed-semantics-compat-20261026.md:1 (A, ID 全局化 D68)
//! lineage: agent-kernel:notes/DECISIONS.md:703 (A, D68: node_id + uuidv7)
//!
//! 节点标识（D68）：**谁生成的 id**——会话/作业 id 前缀、事件头、握手声明都用它。
//!
//! 为什么需要（D68 依据）：`s_%04` 每宿主独立计数、5 套作业 id 家族 → **跨机必然撞号**。
//! 把 `node_id` 放进 id 前缀（`{node_id}-{uuidv7}`）后，id 的唯一性不再依赖"同机不并发"，
//! 而是 `node_id` 的唯一性——这是可运维的（节点注册表），单机则退化为固定的 `local`。
//!
//! 边界：
//! - 本类型**只是标识**，不做认证（D67：传输层信任边界不在 id 上；`node_id` 由握手声明）；
//! - 字符集刻意窄（`[a-z0-9-]`）：它会被拼进 id，而 id 会被用作**目录名**（`sessions/<id>/`），
//!   所以不允许 `/`、`.`、大写等需要跨平台转义/大小写不敏感文件系统上会撞的字符；
//! - 不做 DNS/主机名解析：`node_id` 是运维给的稳定别名（如 `node-a`），不是 hostname。

use std::fmt;
use std::str::FromStr;

use crate::types::{Error, ErrorCategory};

/// 单机/未声明的默认节点名（旧客户端不传 `node_id` 时用它，**行为与 D68 之前等价**）。
pub const LOCAL_NODE: &str = "local";

/// 节点标识最大长度（拼进 id 后仍要满足会话 id `≤128` 与目录名限制）。
pub const MAX_NODE_ID_LEN: usize = 64;

/// 节点标识（字符串 newtype；字符集 `[a-z0-9-]`、长度 1..=64）。
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct NodeId(String);

impl NodeId {
    /// 单机默认节点（兼容旧客户端：不传 `node_id` 时一律按此处理）。
    pub fn local() -> Self {
        Self(LOCAL_NODE.to_string())
    }

    /// 校验并构造。
    ///
    /// # Errors
    /// 空串、超过 [`MAX_NODE_ID_LEN`] 字符、或含 `[a-z0-9-]` 之外的字符 → `Error`
    /// （`Protocol` / `-32602`，与既有参数错误口径一致）。
    pub fn new(raw: impl Into<String>) -> Result<Self, Error> {
        let raw = raw.into();
        if raw.is_empty() || raw.len() > MAX_NODE_ID_LEN {
            return Err(node_error(format!(
                "node id must be 1..={MAX_NODE_ID_LEN} chars, got {} chars",
                raw.len()
            )));
        }
        if !raw
            .chars()
            .all(|ch| ch.is_ascii_lowercase() || ch.is_ascii_digit() || ch == '-')
        {
            return Err(node_error(format!(
                "node id {raw:?} must match [a-z0-9-] (it is used as a file-name-safe id prefix)"
            )));
        }
        if raw.starts_with('-') || raw.ends_with('-') || raw.contains("--") {
            return Err(node_error(format!(
                "node id {raw:?} must not start/end with '-' nor contain '--' \
                 (keeps `{{node_id}}-{{uuidv7}}` unambiguously splittable)"
            )));
        }
        Ok(Self(raw))
    }

    /// 是否单机默认节点（用于"legacy 兼容路径"判定）。
    pub fn is_local(&self) -> bool {
        self.0 == LOCAL_NODE
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl Default for NodeId {
    fn default() -> Self {
        Self::local()
    }
}

fn node_error(message: impl Into<String>) -> Error {
    Error::new(ErrorCategory::Protocol, crate::ERR_INVALID_PARAMS, message)
}

impl fmt::Display for NodeId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl FromStr for NodeId {
    type Err = Error;

    fn from_str(text: &str) -> Result<Self, Self::Err> {
        Self::new(text)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn local_node_is_the_single_machine_default() {
        assert_eq!(NodeId::local().as_str(), "local");
        assert_eq!(NodeId::default(), NodeId::local());
        assert!(NodeId::local().is_local());
        assert!(!NodeId::new("node-a").unwrap().is_local());
        assert_eq!(NodeId::local().to_string(), "local");
    }

    #[test]
    fn accepts_and_roundtrips_valid_node_ids() {
        for raw in ["local", "node-a", "n1", "a-b-c", "0123456789"] {
            let node = NodeId::new(raw).unwrap_or_else(|_| panic!("{raw}: invalid node id"));
            assert_eq!(node.as_str(), raw);
            assert_eq!(node, raw.parse::<NodeId>().unwrap());
        }
        // 64 字符上限。
        let max = "a".repeat(MAX_NODE_ID_LEN);
        assert!(NodeId::new(max.clone()).is_ok());
        assert!(NodeId::new(format!("{max}a")).is_err());
    }

    #[test]
    fn rejects_ids_that_would_break_the_session_id_prefix() {
        for bad in [
            "",        // 空
            "Node-A",  // 大写（大小写不敏感文件系统会撞）
            "node_a",  // 下划线不在 char 集内
            "node/a",  // 路径分隔符（id 会被当目录名）
            "node.a",  // 点（`.`/`..` 会被路径校验拒）
            "-node",   // 前导 '-'：`{node}-{uuid}` 无法无歧义切分
            "node-",   // 尾随 '-'
            "node--a", // 连续 '-'：同上
            "no de",   // 空白
            "节点一",  // 非 ASCII
        ] {
            assert!(NodeId::new(bad).is_err(), "must reject {bad:?}");
        }
    }

    #[test]
    fn errors_carry_the_invalid_params_code() {
        let error = NodeId::new("Node-A").unwrap_err();
        assert_eq!(error.code, crate::ERR_INVALID_PARAMS);
    }
}
