//! lineage: agent-kernel:kernel/iface/src/lib.rs:839 (B, move-only 拆分自单文件 lib.rs)
//!
//! `iface-tool`：注册/执行/取结果（M26/M28/M29/M32）；执行上下文必须带环境归属（§6.7）。
use super::BoxFuture;
use super::types::*;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub parameters: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ToolCall {
    pub meta: CallMeta,
    pub tool: String,
    pub environment: Option<EnvironmentId>,
    /// 工具入参：**不透明字节**。编码规则（D93）：
    /// - 必须是 UTF-8 字节；
    /// - 若工具约定为 JSON，则必须是合法 UTF-8 JSON（宿主/传输**不解析**，解释权在工具实现）；
    /// - 结构化参数不做 iface 形状变更（承载能力已足够）。
    pub args: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ToolResult {
    pub ok: bool,
    /// 工具结果：**任意字节**（文本/二进制都可以）。D93：二进制承载能力已足够，不改结构；
    /// 动态内容类型（`content_type`）属"每次结果自描述"的独立契约问题，当前不在此结构表达。
    pub bytes: Vec<u8>,
    /// 未知结果必须显式标出（不得当成功/失败）。
    pub unknown: bool,
}

pub trait ToolContract: Send + Sync {
    fn register(&self, spec: ToolSpec) -> BoxFuture<'_, Result<(), Error>>;
    fn list(&self) -> BoxFuture<'_, Vec<ToolSpec>>;
    fn invoke(&self, call: ToolCall) -> BoxFuture<'_, Result<ToolResult, Error>>;
    fn abort(&self, call: &CallId) -> BoxFuture<'_, Result<(), Error>>;
}

/// **装配暂存能力**（D83 窄能力面，task-107）。
///
/// ## 为什么单独成契约（而不是塞进 [`ToolContract`]）
/// 装配期（如 `SelfAssembly::commit`）需要先把工具**登记为 stub**，任一步失败要**回滚已登记的**
/// （"不留半装"）。这件事 `ToolContract` 表达不了：
/// - `register` 是 **async** 且吃完整 `ToolSpec`（装配期只有名字）；
/// - `abort` 撤的是**一次调用**，不是**一条注册**；
/// - `list` 虽可异步判断存在性，但**删不掉刚注册的**（无法回滚）。
///
/// 因此它单独成一个**窄**契约：只有装配器需要它，不该为它污染主工具契约。
/// 这与 `EventIo`（core 同步事件面）、`TraceSink`（留痕面）是同一种"按能力切分"的做法。
///
/// ## 实现约定（"不留半装"）
/// - `register_stub` 失败时**不得留下半个注册**；
/// - `remove_stub` 对不存在的名字 → `Ok`（幂等，便于回滚循环）；
/// - 三个方法都是**同步**（装配期不引入 async 复杂度）。
pub trait ToolStaging: Send + Sync {
    /// 该名字是否已登记（stub 或完整规格都算）。
    fn contains(&self, name: &str) -> bool;

    /// 按名字登记一个 stub（装配期占位；工具表可见性由实现决定）。
    ///
    /// # Errors
    /// 名字非法 / 重复登记 / 存储不可用。
    fn register_stub(&self, name: &str) -> Result<(), Error>;

    /// 撤销一个 stub 登记（回滚用；不存在 → `Ok`，幂等）。
    ///
    /// # Errors
    /// 底层存储不可用。
    fn remove_stub(&self, name: &str) -> Result<(), Error>;
}
