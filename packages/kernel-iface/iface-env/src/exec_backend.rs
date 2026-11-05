//! lineage: agent-kernel:kernel/iface/src/lib.rs:1824 (B, move-only 拆分自单文件 lib.rs)
//!
use crate::BoxFuture;
use crate::types::Error;

use super::PathUri;

/// 逻辑执行句柄（**不是** OS pid；由实现方分配）。
#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct ExecutionHandle(pub String);

impl ExecutionHandle {
    pub fn new(raw: impl Into<String>) -> Self {
        Self(raw.into())
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// 进程信号（最小形态；codex 的 `ProcessSignal` 目前也只有 `Interrupt`）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum Signal {
    /// 打断/中断（对应 codex `process/signal` 的 `interrupt`）。
    Interrupt,
}

/// 一次进程执行请求。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ExecRequest {
    /// 可执行程序（`PATH` 语义由环境决定）。
    pub program: String,
    pub args: Vec<String>,
    /// 工作目录（带环境归属；`None` = 实现默认目录）。
    pub cwd: Option<PathUri>,
    /// 环境变量（键值对，顺序保留）。
    pub env: Vec<(String, String)>,
    /// 超时（毫秒；`None` = 实现默认/不超时）。
    pub timeout_ms: Option<u64>,
}

/// 同步执行结果（最小形态；codex 是"启动 + 流式读"，本契约先给同步收尾形态）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ExecOutput {
    pub code: i32,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
}

/// 进程执行后端（L-A）。
///
/// 契约包含 `signal`/`terminate`（M04 双工必须能中止）；**实现可以返回 `Unsupported`**，
/// 但不能没有这两个入口（能力声明里 `signals=false` 时调用方应据此降级）。
pub trait ExecBackend: Send + Sync {
    fn exec(&self, request: ExecRequest) -> BoxFuture<'_, Result<ExecOutput, Error>>;
    fn signal(&self, handle: &ExecutionHandle, signal: Signal) -> BoxFuture<'_, Result<(), Error>>;
    fn terminate(&self, handle: &ExecutionHandle) -> BoxFuture<'_, Result<(), Error>>;
}
