//! 后端接口：`ModelSessionFactory` 与 `ModelSession`（P1 的两个新 trait，trait 数 20→22）。
//!
//! 设计约束（规范 §6.1.3 / D96）：
//! - 输入与事件读取**必须能并发**：控制不被事件读取阻塞；
//! - 这些接口**不直接暴露给无授权业务调用者**——宿主完成共同管理（授权/预算/调度/记录）后才调用；
//! - 未声明能力的方法必须返回 `Unsupported`，不得静默降级或伪造成功。

use std::sync::Arc;

use super::capabilities::SessionCapabilities;
use super::config::ModelSessionConfig;
use super::event::ModelSessionEvent;
use super::input::{InputAccepted, InputEnvelope, ToolResultEnvelope};
use super::types::{ConfigRevision, ModelSessionId, ResponseId};
use crate::BoxFuture;
use crate::types::Error;

/// 会话状态（正常路径 opening → ready → closing → closed；更新时 ready → updating → ready）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum SessionState {
    Opening,
    Ready,
    Updating,
    Closing,
    Closed,
    Failed,
    /// 无法确认后端工作状态（不得写成成功关闭）。
    Unknown,
}

/// `session_open` 的申请结果：会话 id + opening operation 引用 + 实际采用限额。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OpenAck {
    pub model_session_id: ModelSessionId,
    pub operation_id: String,
    /// 实际采用的限额（宿主可收紧；必须回显，不能只返回配置原值）。
    pub limits: super::config::SessionLimits,
    /// 初始状态（通常 `Opening`；后端已就绪时可 `Ready`）。
    pub state: SessionState,
    /// 实际生效的配置版本（requested/effective 分离）。
    pub effective_revision: ConfigRevision,
}

/// 配置更新结果（未获后端确认前 effective 不得变化）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConfigUpdate {
    pub requested_revision: ConfigRevision,
    /// `None` = 尚未生效（pending）。
    pub effective_revision: Option<ConfigRevision>,
    pub operation_id: String,
    /// 需要重建会话时的显式理由（不得暗中关旧连接）。
    pub requires_reopen: bool,
}

/// 打断结果：**本地停止交付**与**后端停止**分别表达。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InterruptAck {
    pub response_id: ResponseId,
    pub delivery_stopped: bool,
    pub backend_stop: super::event::BackendStopStatus,
    pub operation_id: String,
}

/// 后端工厂：能力查询 + 按有效配置打开会话。
pub trait ModelSessionFactory: Send + Sync {
    /// 声明的能力（**只声明已实现**；未实现的必须 false/空）。
    fn capabilities(&self) -> SessionCapabilities;

    /// 打开一个后端会话；`Unsupported`/`InvalidParams` 必须显式返回，不静默降级。
    fn open(&self, config: ModelSessionConfig) -> BoxFuture<'_, Result<Arc<dyn ModelSession>, Error>>;
}

/// 一个已打开的模型后端会话（输入与事件读取可并发）。
pub trait ModelSession: Send + Sync {
    fn model_session_id(&self) -> &ModelSessionId;

    fn state(&self) -> SessionState;

    /// 追加可靠输入（返回 accepted/forwarded；消费确认另见事件）。
    fn append_input(&self, input: InputEnvelope) -> BoxFuture<'_, Result<InputAccepted, Error>>;

    /// 结束一个输入组；request 模式下由宿主触发生成（duplex 下只提交输入边界）。
    fn commit_input(&self, input_id: super::types::InputId) -> BoxFuture<'_, Result<(), Error>>;

    /// 工具结果回填（分段；非增量后端在 commit 时才接收聚合结果）。
    fn append_tool_result(&self, result: ToolResultEnvelope) -> BoxFuture<'_, Result<InputAccepted, Error>>;

    /// 明确工具结果结束。
    fn commit_tool_result(&self, tool_call_id: &str) -> BoxFuture<'_, Result<(), Error>>;

    /// 整份配置替换（`expected_revision` 为 CAS）；未确认生效前 effective 不变。
    fn update_config(
        &self,
        config: ModelSessionConfig,
        expected_revision: ConfigRevision,
    ) -> BoxFuture<'_, Result<ConfigUpdate, Error>>;

    /// 打断指定 response（不得替代工具取消）。
    fn interrupt(&self, response_id: &ResponseId) -> BoxFuture<'_, Result<InterruptAck, Error>>;

    /// 正常收尾：停止新输入、排空已接受工作、期限内收尾。
    fn close(&self) -> BoxFuture<'_, Result<(), Error>>;

    /// 显式终止在途工作（结果未知必须如实保留）。
    fn abort(&self) -> BoxFuture<'_, Result<(), Error>>;

    /// 异步读取下一个事件（`None` = 本订阅已结束；订阅结束不等于会话关闭）。
    fn next_event(&self) -> BoxFuture<'_, Result<Option<ModelSessionEvent>, Error>>;
}
