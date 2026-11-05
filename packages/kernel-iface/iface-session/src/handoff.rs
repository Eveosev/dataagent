//! lineage: agent-kernel:kernel/runtime/src/handoff/guard.rs:26 (A, 鉴权端口; task-105 上移 iface)
//! lineage: agent-kernel:kernel/runtime/src/handoff/port.rs:1 (B, kernel 错误形状)
//! lineage: agent-kernel:notes/DECISIONS.md:789 (A, D83: iface 是唯一契约源)
//!
//! **handoff（agent-handoff 插件）契约面**：鉴权端口 + kernel 错误形状 + 稳定错误码。
//!
//! ## 为什么在 iface（D83）
//! `HandoffAuthorizer` 的消费方跨 crate：插件侧（runtime `handoff/plugin.rs`）与适配器侧
//! （runtime `handoff/guard.rs` 的 `GuardAuthorizer` 依赖 core `Guard`），而 host 的 `a2a`
//! 面也要构造鉴权上下文。契约留在 runtime → 插件被迫依赖实现层 crate → 违反 D83。
//!
//! ## 已上移（本文件）
//! - [`HandoffAuthorizer`] + [`AuthzRequest`]（**全部字段是 `String`**，零外部依赖）；
//! - [`KernelError`] + `ERR_*` 稳定错误码（V1 L-C 码的 1:1 镜像）。
//!
//! ## ⚠️ 未上移：`HandoffKernel`（阻塞项，需 D83 后续决策）
//! `HandoffKernel` 的 DTO 图里有 **2 个 `serde_json::Value` 字段**
//! （`BlockedOnItem.response_schema`、`DeliverRequest.payload`），而 **iface 必须零外部依赖**
//! （`iface/Cargo.toml` 为空）。可选方案（需 Lead 定，本任务不擅自改契约形状）：
//! 1. iface 引入自有 `JsonValue` 枚举（~60 行，零依赖），runtime 在边界做 `serde_json ↔ JsonValue` 转换；
//! 2. 字段降级为 `String`（已序列化 JSON 文本），契约更弱但零转换；
//! 3. iface 依赖 `serde_json`（**与"iface 零依赖"冲突，需 D83 明确豁免**）。
//!
//! 本文件**零外部依赖**（只用 `std`）。

// ── kernel 错误码（V1；与 host 的 L-C 码一致，见 notes/kernel-session-v2-v1.md §6） ──

/// 会话不存在（V1 复用 `-32004`；与 A2A 的 `UnsupportedOperationError` **同号异义**，插件必须翻译）。
pub const ERR_SESSION_NOT_FOUND: i32 = -32004;
/// 无读/写权限（`SESSION_FORBIDDEN`）。
pub const ERR_SESSION_FORBIDDEN: i32 = -32013;
/// 旧代次（围栏）。
pub const ERR_STALE_GENERATION: i32 = -32010;
/// 方法已登记但本轮未实现（如 `operation.*`），与"未知方法" `-32601` 区分。
pub const ERR_METHOD_NOT_IMPLEMENTED: i32 = -32085;
/// SideEffect 方法缺幂等键。
pub const ERR_IDEMPOTENCY_REQUIRED: i32 = -32086;
/// 会话已关闭后写操作。
pub const ERR_SESSION_CLOSED: i32 = -32087;
/// watch 游标早于保留窗口。
pub const ERR_CURSOR_EXPIRED: i32 = -32088;
/// `resource_version` 不匹配（乐观并发）。
pub const ERR_VERSION_CONFLICT: i32 = -32089;
/// 参数非法（含续跑 `response_schema` 不符）。
pub const ERR_INVALID_PARAMS: i32 = -32602;
/// 未知方法。
pub const ERR_METHOD_NOT_FOUND: i32 = -32601;
/// 内部错误。
pub const ERR_INTERNAL: i32 = -32603;

/// 内核错误：`code` 是 V1 L-C 稳定码；`reason` 是 AIP-193 风格的机器可读原因（可选）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KernelError {
    pub code: i32,
    pub message: String,
    pub reason: Option<String>,
}

impl KernelError {
    pub fn new(code: i32, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            reason: None,
        }
    }

    pub fn with_reason(mut self, reason: impl Into<String>) -> Self {
        self.reason = Some(reason.into());
        self
    }

    /// `operation.*` 尚未实现（V1 登记未实现）：插件据此回退到会话投影，而不是伪造成功。
    pub fn method_not_implemented(method: impl Into<String>) -> Self {
        Self::new(
            ERR_METHOD_NOT_IMPLEMENTED,
            format!("MethodNotImplemented: {}", method.into()),
        )
    }

    pub fn session_not_found(session: &str) -> Self {
        Self::new(ERR_SESSION_NOT_FOUND, format!("SessionNotFound: {session}"))
    }

    pub fn forbidden(message: impl Into<String>) -> Self {
        Self::new(ERR_SESSION_FORBIDDEN, format!("Forbidden: {}", message.into()))
    }
}

/// 一次 A2A 操作的鉴权上下文（全部是可审计的最小字段）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AuthzRequest {
    /// kernel 逻辑操作名（如 `session.deliver`），不是 A2A 方法名。
    pub op: String,
    pub principal: String,
    pub session: String,
    pub call: String,
}

/// **鉴权端口**：插件只依赖这个 trait（测试 fake / 真实 Guard 适配器都实现它）。
///
/// 实现留在 runtime（`AllowAll` / `GuardAuthorizer`，后者依赖 core `Guard`）——
/// 契约在 iface、实现随实现层，符合 D83。
pub trait HandoffAuthorizer: Send + Sync {
    /// # Errors
    /// 非 `Allow` 一律返回 [`ERR_SESSION_FORBIDDEN`]（fail-closed，未决即拒）。
    fn authorize(&self, request: &AuthzRequest) -> Result<(), KernelError>;
}

// ───────────────────────────── HandoffKernel 及其 DTO（task-105 上移；D84/B′ 不透明载荷） ──

// ── 阻塞态（V1 G1 派生投影；不新增持久态） ──

/// `blocked_on[].kind`（V1 只有 `interrupt` 有真实来源；`approval`/`auth` 预留）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BlockedKind {
    Interrupt,
    Approval,
    Auth,
}

impl BlockedKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Interrupt => "interrupt",
            Self::Approval => "approval",
            Self::Auth => "auth",
        }
    }
}

/// 一条阻塞项（`session.get{view:"status"}.blocked_on[]` 的元素）。
#[derive(Clone, Debug, PartialEq)]
pub struct BlockedOnItem {
    pub kind: BlockedKind,
    /// 阻塞对象 id（`interrupt` 时为 M04 打断任务 id，续跑时作为 `correlation_id`）。
    pub id: String,
    /// 续跑所需的最小 JSON Schema（G2；`None` = 提交时未声明）。
    ///
    /// **不透明载荷（D84/B′）**：已序列化的 JSON 文本。**内核不解释其内容**——只透传给
    /// A2A 客户端；校验（`session.deliver` 的 resume 比对）由需要语义的一方自己做。
    /// 格式声明见 [`Self::response_schema_content_type`]（`None` = 约定 `application/json`）。
    pub response_schema: Option<String>,
    /// [`Self::response_schema`] 的媒体类型（如 `application/json`）。`None` = 未声明。
    pub response_schema_content_type: Option<String>,
    /// 该阻塞最早出现的墙钟毫秒（`None` = 无事件可依）。
    pub since_ms: Option<u64>,
}

/// 会话状态投影（`session.get{view:"status"}` 的子集；只读、派生）。
#[derive(Clone, Debug, Default, PartialEq)]
pub struct SessionStatus {
    pub session_id: String,
    pub generation: u64,
    pub resource_version: u64,
    pub closed: bool,
    pub live_turns: u32,
    pub blocked_on: Vec<BlockedOnItem>,
    pub waiting_human: bool,
}

// ── watch（V1 G3：三终止条件 + 不透明游标） ──

/// `session.watch` 请求。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WatchRequest {
    pub session_id: String,
    /// 不透明游标（客户端原样回传；插件不解析）。
    pub cursor: Option<String>,
    pub wait_ms: u64,
    pub limit: usize,
}

/// 一页事件（kernel 事件：`kind` + 不透明载荷）。
#[derive(Clone, Debug, PartialEq)]
pub struct WatchEvent {
    pub seq: u64,
    pub kind: String,
    /// **不透明载荷（D84/B′）**：已序列化的文本。**内核不解释**——只透传给核外 loop 的消费者；
    /// 内容的语义/校验由消费者定义。传统事件载荷是 JSON，见 [`Self::payload_content_type`]。
    pub payload: String,
    /// [`Self::payload`] 的媒体类型（`None` = 约定 `application/json`）。
    pub payload_content_type: Option<String>,
    pub ts_ms: u64,
}

/// watch 终止标记：`blocked`（进入阻塞态）或 `closed`（会话关闭）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WatchTerminal {
    Blocked,
    Closed,
}

/// `session.watch` 的一页返回。
#[derive(Clone, Debug, Default, PartialEq)]
pub struct WatchPage {
    pub events: Vec<WatchEvent>,
    pub cursor: String,
    pub has_more: bool,
    pub terminal: Option<WatchTerminal>,
    /// 裸 `SessionSeq`（只读诊断；对 A2A 客户端不暴露，`cursor` 才是不透明契约）。
    pub next_seq: u64,
}

// ── deliver（V1 G2：续跑入口） ──

/// `session.deliver` 请求。`idempotency_key` 必填（SideEffect）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DeliverRequest {
    pub target_session: String,
    pub payload: String,
    /// G2 续跑：指向一个已受理的打断（`blocked_on[].id`）。
    pub correlation_id: Option<String>,
    pub idempotency_key: String,
}

/// `session.deliver` 结果（V1 回包子集）。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct DeliverResult {
    pub delivered: bool,
    pub resume_checked: bool,
    pub resume_completed: bool,
    pub cursor: u64,
    /// kernel task id：**V1 `deliver` 回包不含该字段**（note §8 G2），故为 `Option`。
    pub task_id: Option<String>,
}

// ── close（V1） ──

/// `session.close` 请求。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CloseRequest {
    pub session_id: String,
    pub generation: u64,
    pub reason: Option<String>,
}

/// `session.close` 结果。
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct CloseResult {
    pub closed: bool,
    pub already_closed: bool,
}

// ── operation.*（V2b；V1 已登记未实现 → `-32085`） ──

/// kernel 任务状态（V2b `operation.get` 的子集；V1 无真实实现）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KernelTaskState {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
    Rejected,
}

/// kernel 任务快照（`operation.get` 的返回；V1 不可用）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TaskSnapshot {
    pub task_id: String,
    pub session_id: String,
    pub state: KernelTaskState,
}

/// **内核端口**：`agent-handoff` 使用的最小抽象面（V1 L-C 的 1:1 镜像）。
///
/// 所有方法都可能失败；错误码见本模块常量。实现方（host 接线）负责把每个方法映射到
/// 对应 L-C 方法（`session.create/get/watch/close/deliver`、`operation.get/list/cancel`）。
///
/// # Errors
/// 每个方法返回 [`KernelError`]；调用方不得把错误当成功（fail-closed）。
pub trait HandoffKernel: Send + Sync {
    /// `session.create{parent_session_id?}` → 新 `session_id`。
    fn session_create(&self, parent_session_id: Option<&str>) -> Result<String, KernelError>;

    /// `session.get{view:"status"}`。
    fn session_status(&self, session_id: &str) -> Result<SessionStatus, KernelError>;

    /// `session.deliver{target_session,payload,correlation_id?,idempotency_key}`。
    fn session_deliver(&self, request: DeliverRequest) -> Result<DeliverResult, KernelError>;

    /// `session.watch{view?,cursor?,wait_ms?,limit?}`（三终止条件）。
    fn session_watch(&self, request: WatchRequest) -> Result<WatchPage, KernelError>;

    /// `session.close{reason?,generation}`（幂等）。
    fn session_close(&self, request: CloseRequest) -> Result<CloseResult, KernelError>;

    /// `operation.get`（V1 未实现 → `-32085`）。
    fn operation_get(&self, task_id: &str) -> Result<TaskSnapshot, KernelError>;

    /// `operation.list`（V1 未实现 → `-32085`）。
    fn operation_list(&self, session_id: Option<&str>) -> Result<Vec<TaskSnapshot>, KernelError>;

    /// `operation.cancel`（V1 未实现 → `-32085`；M04 取消≠撤销语义由 kernel 保证）。
    fn operation_cancel(&self, task_id: &str) -> Result<TaskSnapshot, KernelError>;
}
