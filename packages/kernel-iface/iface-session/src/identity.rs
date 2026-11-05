//! lineage: agent-kernel:kernel/iface/src/session.rs:1 (A, Session v2 · V0 纯类型；D55/D56/D57)
//!
//! 会话身份（**不可变标识**；纯数据，不做 I/O、不做权限判定）。
//!
//! 字段来源：
//! - `session_id` / `generation`：既有 M01/M36 语义（generation 是**单宿主**显式换代）；
//! - `epoch`：D56 跨宿主推进权围栏（与 generation **严格分离**，见 [`Epoch`]）；
//! - `tenant_id`：D57（可选、**先只透传**，不做租户隔离）；
//! - `environment`：D55 会话权威执行环境（`EnvId`；本机用 [`EnvId::local()`]）。

use crate::env::EnvId;
use crate::types::{Error, ErrorCategory, Generation, PrincipalId, SessionId};

use super::{Epoch, TenantId};

/// 会话身份（session v2）。
///
/// 这是**记录身份**，不是会话状态机：推进权/租约、事件序号、日志偏移分别由
/// [`SessionLease`](super::SessionLease)、[`SessionSeq`](super::SessionSeq)、
/// [`LogOffset`](super::LogOffset) 表达。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionIdentity {
    /// 会话 id（宿主分配，非空、无控制字符）。
    pub session_id: SessionId,
    /// 单宿主显式换代（M36）。
    pub generation: Generation,
    /// 跨宿主围栏代次（D56）；`None` = 记录早于 epoch 引入（V0 兼容）。
    pub epoch: Option<Epoch>,
    /// 租户（D57，先透传）；`None` = 单租户 / 未声明。
    pub tenant_id: Option<TenantId>,
    /// 会话权威执行环境（D55）。
    pub environment: EnvId,
    /// 发起主体（M18）。
    pub principal: PrincipalId,
}

impl SessionIdentity {
    /// 构造最简身份（`epoch` / `tenant_id` 为 `None`）。
    ///
    /// # Errors
    /// `session_id` 为空/超 128/含控制字符，或 `principal` 为空 → `Error`（`Protocol`/`-32602`）。
    pub fn new(
        session_id: impl Into<SessionId>,
        generation: Generation,
        environment: EnvId,
        principal: impl Into<PrincipalId>,
    ) -> Result<Self, Error> {
        let session_id = session_id.into();
        if session_id.is_empty() || session_id.len() > 128 || session_id.chars().any(char::is_control) {
            return Err(identity_error(format!(
                "session id must be 1..=128 printable chars, got {session_id:?}"
            )));
        }
        let principal = principal.into();
        if principal.is_empty() {
            return Err(identity_error("principal must not be empty"));
        }
        Ok(Self {
            session_id,
            generation,
            epoch: None,
            tenant_id: None,
            environment,
            principal,
        })
    }

    /// 带上跨宿主 epoch（D56）。
    pub fn with_epoch(mut self, epoch: Epoch) -> Self {
        self.epoch = Some(epoch);
        self
    }

    /// 带上租户（D57，先透传）。
    pub fn with_tenant(mut self, tenant_id: TenantId) -> Self {
        self.tenant_id = Some(tenant_id);
        self
    }

    /// 是否同一会话（只看 `session_id`；身份可能因换代/夺权而变化）。
    pub fn is_same_session(&self, other: &SessionIdentity) -> bool {
        self.session_id == other.session_id
    }

    /// 本会话权威执行环境是否本机（D55）。
    pub fn is_local_environment(&self) -> bool {
        self.environment.is_local()
    }

    /// `incoming` epoch 是否**过期**（旧 epoch 写入必须被拒）。
    ///
    /// `epoch = None`（V0 兼容记录）时**不做拒绝**：围栏落地在 core/lease（D56），
    /// 这里只表达判定规则，不伪造"已经围栏"。
    pub fn is_stale_epoch(&self, incoming: Epoch) -> bool {
        match self.epoch {
            Some(current) => current.is_stale(incoming),
            None => false,
        }
    }
}

fn identity_error(message: impl Into<String>) -> Error {
    Error::new(ErrorCategory::Protocol, crate::ERR_INVALID_PARAMS, message)
}
