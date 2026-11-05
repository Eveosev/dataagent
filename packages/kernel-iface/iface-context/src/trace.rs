//! `iface-trace`：**轨迹留痕能力契约**（M37「先写后执行」的能力面）。
//!
//! ## 为什么在 iface
//! D83：**iface 是唯一契约源**。轨迹留痕是「core 实现、runtime/host 消费」的**跨 crate 能力**，
//! 因此契约必须定义在 iface，而不能定义在实现层（放 runtime 就是"契约定义在实现层"，D83 明禁）。
//!
//! ## 与 `StoreContract` / `EventIo` 的分工
//! - `StoreContract`（iface，async）：**事件流**抽象——追加/读/游标/检查点；
//! - `EventIo`（core，sync）：core 机制内部的**同步事件读写能力面**；
//! - **`TraceSink`（本模块）**：轨迹**留痕**能力——它比事件面多一个"**文件内容面**"
//!   （`record_input` 要把原始输入原子落盘成文件，不只是写一条事件），所以不能由
//!   `StoreContract`/`EventIo` 表达（它们没有文件根的概念）。
//!
//! ## 边界（不做什么）
//! - 不规定落盘格式/目录布局（实现自定：`KernelStore` 用 `<root>/sessions/<sid>/traces/`）；
//! - 不做接受/拒绝判决（那是 `PolicyContract`）；不做压缩/归档；
//! - 不依赖任何具体实现类型（本文件只 `use crate::types::*`）。
//!
//! lineage: agent-kernel:kernel/core/src/trace.rs:61 (B, `TraceLog` 的能力面抽离)

use crate::types::{CallMeta, Cursor, Error, SessionId, TraceId};

/// **轨迹留痕能力**（M37：`act` 前把实际输入原子落盘；分支/回滚点可追溯）。
///
/// 实现方（如 `core::KernelStore`）负责真正的原子写与事件追加；消费方（如 `BasicContext`）
/// 只依赖本契约，**不知道、也不需要知道**底下是文件还是别的后端。
pub trait TraceSink: Send + Sync {
    /// **先写后执行**：把本回合的实际输入原子落盘，并记一条 input 事件；返回轨迹 id。
    ///
    /// # Errors
    /// 落盘失败（磁盘满/权限）或事件追加失败 → 显式错误（**不得假装已留痕**）。
    fn record_input(&self, meta: &CallMeta, endpoint: &str, input: &[u8]) -> Result<TraceId, Error>;

    /// 记一个**分支/回滚点**（如压缩边界、子代理派生），返回事件游标。
    ///
    /// # Errors
    /// 事件追加失败 → 显式错误。
    fn record_branch(&self, session: &SessionId, turn: u64, kind: &str) -> Result<Cursor, Error>;
}

/// 什么都不做的 `TraceSink`（**第二实现**，用于证明可替换性与离线/骨架模式）。
///
/// 语义：`record_input`/`record_branch` 都**返回明确错误**（`Unsupported`），
/// 而不是假装成功——M37 要求"先写后执行"，静默成功等于伪造留痕。
#[derive(Debug, Default, Clone, Copy)]
pub struct NoopTraceSink;

impl NoopTraceSink {
    pub fn new() -> Self {
        Self
    }
}

fn unsupported(what: &str) -> Error {
    Error::new(
        crate::types::ErrorCategory::Execution,
        -32036,
        format!("trace sink unsupported: {what} (noop sink does not persist traces)"),
    )
}

impl TraceSink for NoopTraceSink {
    fn record_input(&self, _meta: &CallMeta, _endpoint: &str, _input: &[u8]) -> Result<TraceId, Error> {
        Err(unsupported("record_input"))
    }

    fn record_branch(&self, _session: &SessionId, _turn: u64, _kind: &str) -> Result<Cursor, Error> {
        Err(unsupported("record_branch"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::ErrorCategory;

    fn meta() -> CallMeta {
        CallMeta {
            session_id: "s-1".to_string(),
            call_id: "c-1".to_string(),
            turn: 1,
        }
    }

    #[test]
    fn noop_sink_fails_closed_instead_of_pretending() {
        // 关键：Noop 不能"假装留痕成功"——否则 M37「先写后执行」形同虚设。
        let sink = NoopTraceSink::new();
        let err = sink
            .record_input(&meta(), "ep", b"payload")
            .expect_err("noop 必须显式失败");
        assert_eq!(err.category, ErrorCategory::Execution);
        assert!(err.message.contains("unsupported"), "message: {}", err.message);

        let err = sink
            .record_branch(&"s-1".to_string(), 1, "compact")
            .expect_err("noop 必须显式失败");
        assert_eq!(err.category, ErrorCategory::Execution);
    }

    #[test]
    fn trace_sink_is_object_safe() {
        // 消费方要持 `Arc<dyn TraceSink>`，这里钉住对象安全。
        let sinks: Vec<std::sync::Arc<dyn TraceSink>> = vec![std::sync::Arc::new(NoopTraceSink::new())];
        assert_eq!(sinks.len(), 1);
        assert!(sinks[0].record_branch(&"s".to_string(), 0, "x").is_err());
    }
}
