//! lineage: agent-kernel:kernel/iface/src/lib.rs:1404 (B, move-only 拆分自单文件 lib.rs)
//!
//! `iface-env`（**D55 第 9 个 iface**）：跨设备对象契约。
//!
//! 三件事：
//! 1. **环境归属**：`EnvId` + `Environment`（Local / Remote + 连接描述 + 能力）；
//! 2. **带环境归属的路径**：`PathUri { environment, path }`——路径规范化与"在哪台机器执行"是两件事
//!    （规范 §6.7），所以路径必须显式带 environment，**不能**只靠字符串；
//! 3. **后端契约**：`FsBackend` / `ExecBackend`（进程内 L-A；跨进程由 `environment-registry` 走 L-C 适配）。
//!
//! 边界（诚实）：本模块**只定义形状**，不做安全通道（Noise/抗量子）、不做 overlay、
//! 不读文件系统、不启动进程；本地实现见后续包（S2+）。
//!
//! 参照：codex `exec-server-protocol` 的 `EnvironmentInfo/Capabilities/Status` + `Exec/Read/Write/
//! Signal/Terminate/FsReadFile`、`utils/path-uri` 的 `PathUri`——**只取形状，不复制代码**（R4）。
//! 字段级对照见 `notes/kernel-env-contract.md`。

use crate::types::{Error, ErrorCategory};

pub mod environment;
pub mod exec_backend;
pub mod fs_backend;
pub mod id;
pub mod path_uri;

pub use environment::Environment;
pub use environment::EnvironmentCapabilities;
pub use environment::EnvironmentKind;
pub use exec_backend::ExecBackend;
pub use exec_backend::ExecOutput;
pub use exec_backend::ExecRequest;
pub use exec_backend::ExecutionHandle;
pub use exec_backend::Signal;
pub use fs_backend::DirEntry;
pub use fs_backend::FileStat;
pub use fs_backend::FsBackend;
pub use id::EnvId;
pub use path_uri::PathUri;

fn env_error(message: impl Into<String>) -> Error {
    Error::new(ErrorCategory::Protocol, super::ERR_INVALID_PARAMS, message)
}
