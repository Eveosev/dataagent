//! D93（additive）：模型**流式**契约与**显式完成结果**。
//!
//! 背景（用户核对结论）：
//! - 现有 `ModelContract::call` 是一次性调用，**没有流式方法**；真流式不能靠"把 completed 结果切片"伪造；
//! - `ModelResponse.bytes` 的契约语义是"已抽取的 completion 内容"，**不能**偷偷改成完整响应信封；
//!   因此 `usage` / 结构化 `tool_calls` 需要**单独的显式类型**表达（本文件）。
//!
//! 兼容策略（全部 additive，旧实现零改动）：
//! - 新 trait [`ModelStreamContract`]：实现方额外实现即可，不实现就不声明流式能力；
//! - `ModelContract::call_completion`（`model.rs` 的**默认方法**）：默认把 `call` 的结果包装成
//!   [`ModelCompletion`]（usage/tool_calls 为空），旧实现无需改；
//! - 新类型均为普通 `Clone/Debug/PartialEq/Eq`，`ModelDeltaKind` 为 `#[non_exhaustive]`。
//!
//! 边界：本契约**不**规定模型协议/厂商；实现方（如 runtime）负责把真实 SSE/流式协议映射成
//! [`ModelDelta`]，并保证"只声明已实现的能力"。

use std::sync::mpsc::Sender;

use super::BoxFuture;
use super::model::ModelRequest;
use super::types::Error;

/// 一次 completion 的用量（字段为 `Option`：实现不提供时不得伪造）。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ModelUsage {
    pub input_tokens: Option<u64>,
    pub output_tokens: Option<u64>,
    pub total_tokens: Option<u64>,
}

/// 模型返回的一次结构化工具调用（`tool_calls`），与 `content` 并列表达。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelToolCall {
    /// 上游调用 id（用于工具结果回填配对；不允许由 loop 近似重建）。
    pub id: String,
    pub name: String,
    /// 参数 JSON 文本（原样保留上游编码；不做有损转换）。
    pub arguments_json: String,
}

/// **显式完成结果**（D93）：`content` 仍是抽取后的 completion 内容；`usage`/`tool_calls` 单独字段。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelCompletion {
    pub content: Vec<u8>,
    /// 响应里观察到的模型名（实现不暴露时为 `None`，不得伪造）。
    pub model: Option<String>,
    pub finish_reason: Option<String>,
    pub usage: Option<ModelUsage>,
    pub tool_calls: Vec<ModelToolCall>,
}

/// 流式增量类别（`#[non_exhaustive]`：后续可加，不破坏匹配方）。
#[non_exhaustive]
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ModelDeltaKind {
    /// 文本增量（`text` 必有值）。
    Text,
    /// 工具调用开始（`tool_call_id`/`tool_name`）。
    ToolCallStart,
    /// 工具调用参数 JSON 增量（`arguments_delta`）。
    ToolCallArgs,
    /// 用量上报（`usage`）。
    Usage,
    /// 结束（`finish_reason`）。
    Finish,
}

/// 一帧流式增量。字段按 `kind` 使用，未使用字段为 `None`/空。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelDelta {
    pub kind: ModelDeltaKind,
    pub text: Option<String>,
    pub tool_call_id: Option<String>,
    pub tool_name: Option<String>,
    pub arguments_delta: Option<String>,
    pub usage: Option<ModelUsage>,
    pub finish_reason: Option<String>,
}

/// **模型流式契约**（D93 additive）。
///
/// 语义：
/// - 实现方在 `stream` 内**同步**把 [`ModelDelta`] 通过 `events` 发出（std `mpsc`），
///   最后一个 delta 之后返回**汇总**的 [`ModelCompletion`]（与 `call_completion` 同形）；
/// - `Sender` 发送失败（接收方关闭）→ 实现方应尽快停止并返回错误/已聚合结果；
/// - 宿主只在绑定实现声明了本契约时开启 L-C 流式；否则显式 `unsupported`（不切片伪造）。
pub trait ModelStreamContract: Send + Sync {
    fn stream(
        &self,
        request: ModelRequest,
        events: Sender<ModelDelta>,
    ) -> BoxFuture<'_, Result<ModelCompletion, Error>>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{ModelContract, ModelResponse};

    /// 只实现 `call` 的旧式实现：默认 `call_completion` 必须能工作且不伪造 usage。
    struct OldModel;

    impl crate::model::ModelContract for OldModel {
        fn call(&self, _request: ModelRequest) -> BoxFuture<'_, Result<ModelResponse, Error>> {
            Box::pin(async {
                Ok(ModelResponse {
                    bytes: b"hello".to_vec(),
                    endpoint: "test".to_string(),
                    capabilities: Vec::new(),
                    model: Some("m".to_string()),
                    finish_reason: Some("stop".to_string()),
                })
            })
        }
        fn capabilities(&self) -> BoxFuture<'_, Vec<(String, String)>> {
            Box::pin(async { Vec::new() })
        }
    }

    /// 测试内最小的阻塞执行器（iface 无 async 运行时；这里的 future 都是立即就绪的）。
    fn block_on<F: std::future::Future>(future: F) -> F::Output {
        use std::task::{Context, Poll};
        let mut cx = Context::from_waker(std::task::Waker::noop());
        let mut future = Box::pin(future);
        loop {
            if let Poll::Ready(output) = future.as_mut().poll(&mut cx) {
                return output;
            }
            std::thread::yield_now();
        }
    }

    #[test]
    fn default_call_completion_wraps_call_without_faking_metadata() {
        let completion = block_on(OldModel.call_completion(ModelRequest {
            session: "s".to_string(),
            turn: 1,
            endpoint: "e".to_string(),
            payload: Vec::new(),
        }))
        .expect("default call_completion");
        assert_eq!(completion.content, b"hello");
        assert_eq!(completion.model.as_deref(), Some("m"));
        assert_eq!(completion.finish_reason.as_deref(), Some("stop"));
        assert_eq!(completion.usage, None, "旧实现没有 usage，不得伪造");
        assert!(completion.tool_calls.is_empty());
    }
}
