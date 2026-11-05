//! lineage: agent-kernel:kernel/iface/src/lib.rs:875 (B, move-only 拆分自单文件 lib.rs)
//! lineage: agent-kernel:notes/DECISIONS.md:789 (A, D73: 契约面必须覆盖宿主真实能力面)
//!
//! `iface-store`：**事件存储契约**（M06 追加 / M07 确定性投影 / M10 检查点）。
//!
//! # 契约面：宿主为什么需要这些方法（D73：可替换性是一等属性）
//!
//! 原契约只有 3 个方法（append/read/checkpoint），而宿主真实依赖 `KernelStore` 的 12 个公开方法
//! → 宿主**只能绕过契约持具体类型**，换实现必破。这里补齐宿主**确实依赖**的能力：
//!
//! | 方法 | 宿主为什么需要 |
//! |---|---|
//! | `append` | 唯一写入点；append-only 是 M06/M07 的全部前提 |
//! | `read` / `read_from` | `session/events`、`session/watch` 的**增量分页**（watch 多取 1 条判 `has_more`） |
//! | `last_cursor` | `resource_version`/CAS 的**唯一单调来源**（契约 §5 第 2 条：零新存储） |
//! | `checkpoint` | 完整性锚点（B9/D2）：钉住"当前 cursor + 摘要" |
//! | `verify_checkpoint` | 重启/对账时**发现截断与篡改**（M07：状态只能由可信日志重导） |
//! | `create_session` | 命名空间就绪（`session.create` 先就绪再写 spec 事件） |
//! | `contains_session` | 重启后 known-session 判定（**替代**实现细节 `root()+is_dir()`） |
//! | `list_sessions` | 旧面 `session/list`（D60 运维/UI 面，但仍是已发布方法） |
//! | `node` | 事件头 `node_id` 的来源（D68）；构造期确定、不可变 |
//!
//! # 构造：**由装配层构造，不进 trait**
//!
//! 理由：① Rust 惯例——对象 trait 表达**行为**，不表达构造/生命周期（构造需要 root、权限、
//! 节点身份等装配期参数）；② 当前只有一个真实现 + 一个计划中的替身（M-c `InMemoryStore`），
//! 装配点按配置选一个即可；③ async factory 会引入 `BoxFuture<Arc<dyn …>>` 的额外生命周期复杂度，
//! 收益为零。若将来需要"按配置打开远程 store"（跨机 L-D），再加 `StoreFactory`（草案见
//! `notes/kernel-iface-store-contract.md`）——**只有那时**才进契约。
//!
//! # 数据模型（D73 M-b：本类型 = 唯一事件模型）
//!
//! [`EventRecord`] 是契约面**唯一**事件模型；`core::Record` 是**内部投影/落盘行**（分区布局 +
//! 单行文本 payload），**不是**契约面。两者之间只有一处转换：
//! `agentcpm_core::log::{record_to_event, event_to_record}`（含往返无损测试）。
//!
//! **payload 编码约定**：契约面永远是**原始 bytes**（不假定 UTF-8）；由实现负责落盘成"单行、
//! 无分隔符冲突"且**可逆**的形式（`core` 用 `t:`/`h:` 前缀编码，见 `core/src/log.rs`）。
//!
//! # 执行模型
//!
//! 契约是 **async**（`BoxFuture`，std-only）；同步实现（如 `KernelStore` 的 `std::io::Result`）
//! 由**适配器**在同一处消化（`runtime/src/store.rs::CoreStore`）。
//!
//! **执行模型约束（D74）**：别名期实现**必须立即就绪**（返回的 future 首次 poll 即 `Ready`）；
//! 异步签名是**为将来传输层预留的形状**，不代表允许"真异步"实现——宿主同步路径遇到 `Pending`
//! 会 fail-fast（视为实现违约），不阻塞等待。

use crate::session::NodeId;

use super::BoxFuture;
use super::types::*;

/// 一条事件（**契约面唯一事件模型**；D68 起含事件头 `ts_ms`/`node_id`）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EventRecord {
    /// 会话 id（事件所属分区；带在记录里以便单条事件自描述、跨实现传递）。
    pub session: SessionId,
    /// 事件序号（会话内从 1 起、严格单调；**读取时由存储给出**）。
    ///
    /// 写入（[`StoreContract::append`]）时该字段被忽略——序号由存储分配并作为返回值。
    pub cursor: Cursor,
    /// 事件类型（`session.spec` / `op.accepted` …）；由上层定义，存储不解释。
    pub kind: String,
    /// 事件载荷**原始字节**（不假定 UTF-8；编码由实现负责且对契约面透明）。
    pub payload: Vec<u8>,
    /// 事件墙钟毫秒（D68 事件头；不必单调，只作时间参考）。
    pub ts_ms: u64,
    /// 生成该事件的节点（D68 事件头）；`None` = 该列引入前的旧事件 / 未声明节点的实现。
    pub node_id: Option<NodeId>,
}

impl EventRecord {
    /// 新建待追加事件（`cursor=0`、`ts_ms=0`、`node_id=None`——三者由存储/时钟决定）。
    pub fn new(session: impl Into<SessionId>, kind: impl Into<String>, payload: impl Into<Vec<u8>>) -> Self {
        Self {
            session: session.into(),
            cursor: 0,
            kind: kind.into(),
            payload: payload.into(),
            ts_ms: 0,
            node_id: None,
        }
    }

    /// 文本事件（UTF-8）快捷构造；二进制请用 [`Self::new`] 传 bytes。
    pub fn text(session: impl Into<SessionId>, kind: impl Into<String>, text: impl AsRef<str>) -> Self {
        Self::new(session, kind, text.as_ref().as_bytes().to_vec())
    }

    /// 链式设置游标（适配器构造回读记录 / 测试用）。
    pub fn with_cursor(mut self, cursor: Cursor) -> Self {
        self.cursor = cursor;
        self
    }

    /// 链式设置事件头节点。
    pub fn with_node(mut self, node: NodeId) -> Self {
        self.node_id = Some(node);
        self
    }

    /// payload 当 UTF-8 文本看（失败 = 不是文本事件；**不**做有损替换）。
    pub fn payload_str(&self) -> Result<&str, std::str::Utf8Error> {
        std::str::from_utf8(&self.payload)
    }
}

impl Default for EventRecord {
    fn default() -> Self {
        Self::new(String::new(), String::new(), Vec::new())
    }
}

/// 事件存储契约（追加 + 增量读 + 游标 + 完整性 + 命名空间 + 节点身份）。
///
/// 对象安全：可存为 `Arc<dyn StoreContract>`（装配层选实现、依赖方不变——D73 M-c）。
pub trait StoreContract: Send + Sync {
    /// 追加一条事件，返回**存储分配**的 cursor（会话内从 1 起、严格单调）。
    ///
    /// # Errors
    /// 命名空间不可写 / 值非法（如 `kind` 为空）/ 底层 I/O 失败。
    fn append(&self, record: EventRecord) -> BoxFuture<'_, Result<Cursor, Error>>;

    /// 从 `from`（含）起读至多 `limit` 条（增量/分页）。
    ///
    /// # Errors
    /// 日志损坏（行无法解析）/ 底层 I/O 失败。
    fn read(
        &self,
        session: &SessionId,
        from: Cursor,
        limit: usize,
    ) -> BoxFuture<'_, Result<Vec<EventRecord>, Error>>;

    /// [`Self::read`] 的**规范名**（与 `KernelStore::read_from` 同名，适配器一眼对应）。
    ///
    /// 默认实现委托给 [`Self::read`]：实现者只写一个，契约面同时覆盖两个名字。
    fn read_from(
        &self,
        session: &SessionId,
        from: Cursor,
        limit: usize,
    ) -> BoxFuture<'_, Result<Vec<EventRecord>, Error>> {
        self.read(session, from, limit)
    }

    /// 会话最后一条事件的 cursor（`0` = 尚无事件）= `resource_version`/CAS 的期望值来源。
    ///
    /// # Errors
    /// 底层 I/O 失败。
    fn last_cursor(&self, session: &SessionId) -> BoxFuture<'_, Result<Cursor, Error>>;

    /// 打检查点（返回 checkpoint id，供审计/对账引用）。
    ///
    /// # Errors
    /// 命名空间不存在 / 底层 I/O 失败。
    fn checkpoint(&self, session: &SessionId) -> BoxFuture<'_, Result<CheckpointId, Error>>;

    /// 校验已有检查点：`Ok(None)` = 无检查点；`Ok(Some((cursor, digest)))` = 通过；
    /// `Err(..)` = **与检查点不一致（截断/篡改），必须显式失败**。
    ///
    /// # Errors
    /// 检查点格式坏 / 日志与检查点不一致 / 底层 I/O 失败。
    fn verify_checkpoint(
        &self,
        session: &SessionId,
    ) -> BoxFuture<'_, Result<Option<(Cursor, String)>, Error>>;

    /// 确保会话命名空间就绪（幂等：已存在即成功）。
    ///
    /// # Errors
    /// 权限不足 / 底层 I/O 失败。
    fn create_session(&self, session: &SessionId) -> BoxFuture<'_, Result<(), Error>>;

    /// 会话是否已存在（重启后 known-session 判定）。
    ///
    /// **为什么进契约**：宿主现在探 `store.root().join("sessions").join(id).is_dir()`——那是
    /// **实现细节**（把"有没有这个会话"泄漏成"磁盘上有没有这个目录"）；能力化后远程/内存实现
    /// 不必伪造文件系统布局。
    ///
    /// # Errors
    /// 底层 I/O 失败。
    fn contains_session(&self, session: &SessionId) -> BoxFuture<'_, Result<bool, Error>>;

    /// 列出全部会话 id（旧面 `session/list`；D60 归运维/UI 面）。
    ///
    /// # Errors
    /// 底层 I/O 失败。
    fn list_sessions(&self) -> BoxFuture<'_, Result<Vec<SessionId>, Error>>;

    /// 本实现写入事件时**声明**的节点身份（D68 事件头来源）；`None` = 未声明。
    ///
    /// 同步访问器：节点身份在构造期确定、之后不可变，不需要 async。
    fn node(&self) -> Option<&NodeId>;
}

// ── 刻意**不进契约**的 `KernelStore` 能力（D73 原则：「宁可少，不要泄漏实现」）──────────────
//
// | `KernelStore` 能力 | 为什么不进契约 | 契约面替代 |
// |---|---|---|
// | `open` / `open_with_node` | **构造**不是行为（见模块头「构造：由装配层构造」） | 装配层直接调实现构造器 |
// | `root()` | 泄漏存储布局（本地目录） | `contains_session` / `list_sessions` 能力化 |
// | `read_all` | 纯便利，等价 `read(session, 1, usize::MAX)` | 调用方传参即可 |
// | 行格式/列数/分隔符 | 落盘格式是**实现细节**（换后端可完全不同） | 只通过 [`EventRecord`] 字段暴露 |
