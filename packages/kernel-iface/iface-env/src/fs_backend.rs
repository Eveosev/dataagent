//! lineage: agent-kernel:kernel/iface/src/lib.rs:1797 (B, move-only 拆分自单文件 lib.rs)
//!
use crate::BoxFuture;
use crate::types::Error;

use super::PathUri;

/// 目录项（`list_dir` 的元素）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DirEntry {
    pub name: String,
    pub path: PathUri,
    pub is_dir: bool,
}

/// 文件/目录元数据（`stat` 的结果）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FileStat {
    pub path: PathUri,
    pub is_dir: bool,
    /// 字节数（目录可为 0）。
    pub len: u64,
    /// 修改时间（unix ms；`None` = 实现不提供）。
    pub modified_ms: Option<u64>,
}

/// 文件系统后端（L-A）。**所有路径都带环境归属**，实现方不得假设"本地"。
pub trait FsBackend: Send + Sync {
    fn read_file(&self, path: PathUri) -> BoxFuture<'_, Result<Vec<u8>, Error>>;
    fn write_file(&self, path: PathUri, bytes: Vec<u8>) -> BoxFuture<'_, Result<(), Error>>;
    fn list_dir(&self, path: PathUri) -> BoxFuture<'_, Result<Vec<DirEntry>, Error>>;
    fn stat(&self, path: PathUri) -> BoxFuture<'_, Result<FileStat, Error>>;
}
