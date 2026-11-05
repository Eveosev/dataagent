//! lineage: agent-kernel:kernel/core/src/event_io.rs:21 (A, 事件 IO 能力面; task-105 上移 iface)
//! lineage: agent-kernel:notes/DECISIONS.md:789 (A, D83: iface 是唯一契约源)
//!
//! **事件 IO 的最小契约面**（`read_all` / `append` / `last_cursor`）。
//!
//! ## 为什么在 iface（D83）
//! `EventIo` 的**消费方跨 crate**：`core` 的机制实现（账本/幂等/M04）、`runtime`（租约增量刷新/
//! handoff 端口）、`host`（契约事件的同步适配 `ContractEventIo`）。契约型 trait 住在
//! `core`/`runtime` 里会让"谁定义契约"随实现漂移——D83 定：**iface 是唯一契约源**，
//! core/runtime 内的 trait 只允许是内部 SPI。
//!
//! ## 边界
//! - **同步**面（core 不做 async；async 只在宿主门面处消化，D74）；
//! - 只追加、按会话寻址；不做检查点/命名空间/节点身份（那是 `StoreContract` 的事）；
//! - **实现留在实现方**：`KernelStore` 的 impl 在 `core`，`ContractEventIo` 在 `host`
//!   （trait 在 iface、类型在本地实现 crate → 不违反孤儿规则）。
//!
//! 本文件**零外部依赖**（只用 `std`）：iface 不反向依赖 core/runtime。

use std::io;

/// 事件游标（会话内单调递增；`0` = 无事件）。
pub type Cursor = u64;

/// **落盘行 / 内部投影**（**不是**契约面事件模型——契约面是
/// [`crate::store::EventRecord`]）。
///
/// 为什么保留本类型：它是 L-D 文本行格式（`events.tsv`）的直接映射，被投影/检查点/统计等
/// 内部逻辑大量使用；**唯一**对外转换点是 core 的 `record_to_event` / `event_to_record`
/// （D73 M-b：两套模型不允许各自演化）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Record {
    pub cursor: Cursor,
    pub kind: String,
    pub payload: String,
    pub ts_ms: u64,
    /// 事件头：生成该事件的节点（D68）。`None` = **旧 4 列日志**（本列引入前写入）。
    pub node_id: Option<String>,
}

/// 机制实现需要的**事件读写能力**（同步、只追加）。
pub trait EventIo {
    /// 读会话全部事件（投影/校验用）。
    ///
    /// # Errors
    /// 落盘行损坏 / 底层 I/O 失败。
    fn read_all(&self, session: &str) -> io::Result<Vec<Record>>;

    /// 追加一条文本事件，返回新游标。
    ///
    /// # Errors
    /// 值非法（kind 空或含分隔符）/ 命名空间不可写 / 底层 I/O 失败。
    fn append(&self, session: &str, kind: &str, payload: &str) -> io::Result<Cursor>;

    /// 会话最后一条事件的游标（0 = 无事件）。
    ///
    /// # Errors
    /// 底层 I/O 失败。
    fn last_cursor(&self, session: &str) -> io::Result<Cursor>;
}

/// `&T` 也可以直接当能力面用（`Vec<&KernelStore>` 之类场景解引用更自然）。
///
/// 为什么这个 impl 在 iface（而不是 core）：trait 现在属 iface，`&T` 不是本地类型 →
/// 只有**定义 trait 的 crate** 能写这条 blanket impl（孤儿规则）。语义与上移前完全一致。
impl<T: EventIo + ?Sized> EventIo for &T {
    fn read_all(&self, session: &str) -> io::Result<Vec<Record>> {
        (**self).read_all(session)
    }

    fn append(&self, session: &str, kind: &str, payload: &str) -> io::Result<Cursor> {
        (**self).append(session, kind, payload)
    }

    fn last_cursor(&self, session: &str) -> io::Result<Cursor> {
        (**self).last_cursor(session)
    }
}
