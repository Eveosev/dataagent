//! lineage: agent-kernel:kernel/iface/src/lib.rs:811 (B, move-only 拆分自单文件 lib.rs)
//!
//! `iface-model`：调用/问能力（M27/M30）；跨模型轨迹连续由本契约保证（§3.2-5）。
use super::BoxFuture;
use super::model_stream::ModelCompletion;
use super::types::*;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelRequest {
    pub session: SessionId,
    pub turn: TurnId,
    /// 端点逻辑名（不暴露厂商鉴权）。
    pub endpoint: String,
    pub payload: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelResponse {
    /// 已抽取的 completion 内容（**不是**原始 HTTP body）。
    pub bytes: Vec<u8>,
    pub endpoint: String,
    /// 能力描述符（不用硬编码模型名单）。
    pub capabilities: Vec<(String, String)>,
    /// 响应里观察到的模型名（服务端可能改写）；实现不暴露时 `None`，**不得伪造**。
    pub model: Option<String>,
    /// 响应里观察到的 `finish_reason`（如 `stop`/`length`）；不可得时 `None`。
    pub finish_reason: Option<String>,
}

pub trait ModelContract: Send + Sync {
    fn call(&self, request: ModelRequest) -> BoxFuture<'_, Result<ModelResponse, Error>>;
    fn capabilities(&self) -> BoxFuture<'_, Vec<(String, String)>>;

    /// **显式完成结果**（D93 additive，带默认实现）：`usage`/结构化 `tool_calls` 不能塞进
    /// `ModelResponse.bytes`（其契约语义是"已抽取的 completion 内容"）。
    ///
    /// 默认实现调用 [`ModelContract::call`] 并返回 `usage=None, tool_calls=[]`——
    /// 旧实现零改动；支持元数据的实现覆盖本方法。**不得**为缺失字段伪造值。
    fn call_completion(&self, request: ModelRequest) -> BoxFuture<'_, Result<ModelCompletion, Error>> {
        Box::pin(async move {
            let response = self.call(request).await?;
            Ok(ModelCompletion {
                content: response.bytes,
                model: response.model,
                finish_reason: response.finish_reason,
                usage: None,
                tool_calls: Vec::new(),
            })
        })
    }
}

/// 模型**健康探测**能力（D77「硬边界适配」通道；与 `ModelContract`（推理）职责分离）。
///
/// 为什么独立小契约而不是往 `ModelContract` 塞 `health()`：
/// - 推理与探测是两种职责（探测可能要 `/models` 等非推理端点；有的实现只做推理）；
/// - 独立 trait 是 **additive**：既有 4 个 `ModelContract` 实现零改动（不实现本 trait 即可）；
/// - 宿主只需要 `Arc<dyn ModelProbe>` 就能做 `model/health`，不接触具体端点类型。
///
/// D74：实现必须**立即 Ready**（宿主同步路径用 `poll_ready` 调）。
pub trait ModelProbe: Send + Sync {
    /// 端点**描述**（探测所需的地址/模型/超时；不含凭证）。
    ///
    /// 为什么在契约里：宿主 `model/health` 要做「/api/status + /v1/models」双层探测，
    /// 需要 base_url/model/timeout 这些参数；走契约后宿主不再持有具体端点类型。
    fn endpoint_info(&self) -> ModelEndpointInfo;

    /// 端点健康与能力（不产生推理副作用）。
    fn health(&self) -> BoxFuture<'_, Result<ModelHealth, Error>>;

    /// 端点可用模型列表（`/models`；不支持的实现返回 `Unsupported`）。
    fn models(&self) -> BoxFuture<'_, Result<Vec<String>, Error>>;
}

/// 健康探测结果（最小面：就绪与否 + 细节 + 可用模型）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelHealth {
    /// 端点是否可用（连接成功 + 协议应答可解析）。
    pub ready: bool,
    /// 人类可读细节（失败原因/服务端信息；成功可为空）。
    pub detail: String,
    /// 服务端报告的模型名（实现不支持则为空）。
    pub models: Vec<String>,
}

/// 端点描述（探测用；**不含** api_key/凭证）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ModelEndpointInfo {
    /// 形如 `http://127.0.0.1:8080/v1`。
    pub base_url: String,
    /// 逻辑模型名（服务端可能改写，仅作观察/匹配）。
    pub model: String,
    /// 请求超时（毫秒）。
    pub timeout_ms: u64,
}
