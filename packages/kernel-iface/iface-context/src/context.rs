//! lineage: agent-kernel:kernel/iface/src/lib.rs:779 (B, move-only 拆分自单文件 lib.rs)
//!
//! `iface-context`：组装/重建能力清单/留痕（M08/M09/M37）。
use super::BoxFuture;
use super::types::*;

/// 组装结果（形状待 L-D 定稿；这里只保证可留痕、可复现）。
///
/// `content_type` 声明 `bytes` 的编码（D84 不透明载荷口径：**内核不解释快照内容**，
/// 只透传给模型/消费者；L-D 定稿后若改为结构化字段，本字段可作为迁移锚点）。
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub struct ContextSnapshot {
    pub session: SessionId,
    pub turn: TurnId,
    /// 快照载荷（编码由 [`Self::content_type`] 声明；形状待 L-D）。
    pub bytes: Vec<u8>,
    pub capabilities_versions: Vec<(String, String)>,
    /// `bytes` 的媒体类型（`None` = 未声明）。
    pub content_type: Option<String>,
}

impl ContextSnapshot {
    /// 构造快照（**`content_type` 默认未声明**；形状待 L-D）。
    pub fn new(
        session: SessionId,
        turn: TurnId,
        bytes: Vec<u8>,
        capabilities_versions: Vec<(String, String)>,
    ) -> ContextSnapshot {
        ContextSnapshot {
            session,
            turn,
            bytes,
            capabilities_versions,
            content_type: None,
        }
    }

    /// 声明快照编码（D84：内核不解释内容）。
    pub fn with_content_type(mut self, content_type: Option<impl Into<String>>) -> ContextSnapshot {
        self.content_type = content_type.map(Into::into);
        self
    }
}

pub trait ContextContract: Send + Sync {
    fn assemble(&self, session: &SessionId, turn: TurnId) -> BoxFuture<'_, Result<ContextSnapshot, Error>>;
    fn rebuild_capabilities(&self, session: &SessionId) -> BoxFuture<'_, Result<Vec<String>, Error>>;
    /// M37：**先写后执行**——act 前把实际输入原子落盘。
    fn trace_input(
        &self,
        session: &SessionId,
        turn: TurnId,
        meta: &CallMeta,
        payload: &[u8],
    ) -> BoxFuture<'_, Result<TraceId, Error>>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snapshot_new_keeps_content_type_unset_and_builder_sets_it() {
        // 兼容构造器：内容类型默认未声明（既有实现不受影响）。
        let snapshot = ContextSnapshot::new("s_1".to_string(), 3, b"ctx".to_vec(), Vec::new());
        assert_eq!(snapshot.session, "s_1");
        assert_eq!(snapshot.turn, 3);
        assert_eq!(snapshot.bytes, b"ctx".to_vec());
        assert!(snapshot.content_type.is_none(), "默认不声明编码");

        // D84：内核不解释内容，只透传 + 声明媒体类型。
        let typed = snapshot.clone().with_content_type(Some("application/json"));
        assert_eq!(typed.content_type.as_deref(), Some("application/json"));
        assert_eq!(typed.bytes, snapshot.bytes, "bytes 形状不变（待 L-D 定稿）");
        // 清空也合法（显式未声明）。
        assert!(typed.with_content_type(None::<String>).content_type.is_none());
    }
}
