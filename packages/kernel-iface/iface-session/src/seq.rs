//! lineage: agent-kernel:kernel/iface/src/session.rs:1 (A, Session v2 · V0 纯类型；D56 证据：zeroclaw/dsh 分离)
//!
//! **两个品牌类型**：`SessionSeq`（事件身份）与 `LogOffset`（日志游标）。
//!
//! 为什么要分开（D56 证据）：把两者当同一个 `u64` 用时，会出现
//! 「按偏移当事件号重放」或「按事件号当字节偏移 seek」这类**静默错位**。
//! 品牌类型让编译器替我们拦住这类混用；确需转换时必须**显式**调用转换函数。
//!
//! - [`SessionSeq`]：会话内事件的**逻辑身份**（第 n 条事件，从 0 起）；
//! - [`LogOffset`]：日志文件/流的**位置**（字节或条目偏移，按存储后端定义）。
//!
//! 两者**不实现**互相的 `From`：只提供命名明确的转换函数，便于 review 时看出"这里为什么能转"。

/// 会话事件身份（逻辑序号，从 0 起）。
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct SessionSeq(u64);

impl SessionSeq {
    pub const ZERO: SessionSeq = SessionSeq(0);

    pub const fn new(raw: u64) -> Self {
        Self(raw)
    }

    pub const fn get(self) -> u64 {
        self.0
    }

    /// 下一条事件的序号（到顶 `None`，不回绕）。
    pub fn next(self) -> Option<Self> {
        self.0.checked_add(1).map(Self)
    }

    /// **显式**转成日志偏移。
    ///
    /// 仅当该事件已在日志中且"事件序号 == 偏移"成立时才有意义；
    /// 存储后端若采用变长编码/delta，不得使用本函数（应由后端给出 offset）。
    pub fn to_log_offset(self) -> LogOffset {
        LogOffset(self.0)
    }
}

/// 日志位置（由存储后端定义语义：字节偏移 / 条目偏移）。
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct LogOffset(u64);

impl LogOffset {
    pub const ZERO: LogOffset = LogOffset(0);

    pub const fn new(raw: u64) -> Self {
        Self(raw)
    }

    pub const fn get(self) -> u64 {
        self.0
    }

    /// **显式**转成事件序号（语义同 [`SessionSeq::to_log_offset`]，方向相反）。
    pub fn to_session_seq(self) -> SessionSeq {
        SessionSeq(self.0)
    }
}
