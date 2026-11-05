//! lineage: agent-kernel:kernel/iface/src/lib.rs:1518 (B, move-only 拆分自单文件 lib.rs)
//!
use std::fmt;
use std::str::FromStr;

use super::EnvId;
use super::env_error;
use crate::types::Error;

/// **带环境归属的路径**（不是 OS 路径；本模块不读文件系统）。
///
/// 语法：`env://<environment_id>/<path>`，例如 `env://local/tmp/a.txt`、`env://dev-box/work/repo`。
/// - `environment` = 在哪台机器/执行环境上解析这个路径（决定"谁去读"）；
/// - `path` = 该环境内的**绝对路径**（以 `/` 开头；不保留尾随 `/`，根为 `/`）；
/// - **不接受** `..` 段（防上跳）、空路径、控制字符、反斜杠；
/// - 归一化（词法，不碰文件系统）：折叠重复 `/`、去掉 `.` 段、去掉尾随 `/`。
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct PathUri {
    pub environment: EnvId,
    pub path: String,
}

impl PathUri {
    /// 本机路径。
    pub fn local(path: impl Into<String>) -> Result<Self, Error> {
        Self::new(EnvId::local(), path)
    }

    /// 在指定环境里构造路径（做归一化与上跳校验）。
    pub fn new(environment: EnvId, path: impl Into<String>) -> Result<Self, Error> {
        let path = normalize_env_path(&path.into())?;
        Ok(Self { environment, path })
    }

    /// 解析 `env://<id>/<path>`。
    pub fn parse(text: &str) -> Result<Self, Error> {
        let rest = text.strip_prefix("env://").ok_or_else(|| {
            env_error(format!(
                "path uri {text:?} must start with `env://<environment_id>/`"
            ))
        })?;
        let (id_raw, path_raw) = match rest.split_once('/') {
            Some((id, path)) => (id, format!("/{path}")),
            None => {
                return Err(env_error(format!(
                    "path uri {text:?} is missing the path part (`env://<id>/<path>`)"
                )));
            }
        };
        let environment = EnvId::new(id_raw)?;
        Self::new(environment, path_raw)
    }

    /// 追加一段**相对**路径（拒绝绝对路径与 `..`）。
    pub fn join(&self, segment: &str) -> Result<Self, Error> {
        if segment.starts_with('/') {
            return Err(env_error(format!(
                "path uri join expects a relative segment, got {segment:?}"
            )));
        }
        if segment.split('/').any(|part| part == "..") {
            return Err(env_error(format!(
                "path uri join rejects parent traversal (`..`): {segment:?}"
            )));
        }
        let joined = if self.path.ends_with('/') {
            format!("{}{segment}", self.path)
        } else {
            format!("{}/{segment}", self.path)
        };
        Self::new(self.environment.clone(), joined)
    }

    /// 是否本机环境。
    pub fn is_local(&self) -> bool {
        self.environment.is_local()
    }

    /// 换环境、保留路径（跨设备"同一路径不同执行者"）。
    pub fn with_environment(&self, environment: EnvId) -> Self {
        Self {
            environment,
            path: self.path.clone(),
        }
    }
}

impl fmt::Display for PathUri {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "env://{}{}", self.environment, self.path)
    }
}

impl FromStr for PathUri {
    type Err = Error;

    fn from_str(text: &str) -> Result<Self, Self::Err> {
        Self::parse(text)
    }
}

/// 路径归一化（**纯词法**）：折叠 `//`、去掉 `.` 段、去尾随 `/`、拒绝 `..`。
fn normalize_env_path(raw: &str) -> Result<String, Error> {
    if raw.is_empty() {
        return Err(env_error("path uri path must not be empty"));
    }
    if !raw.starts_with('/') {
        return Err(env_error(format!(
            "path uri path must be absolute (start with '/'), got {raw:?}"
        )));
    }
    if raw.contains('\\') {
        return Err(env_error(format!(
            "path uri path must not contain backslashes: {raw:?}"
        )));
    }
    if raw.chars().any(char::is_control) {
        return Err(env_error("path uri path must not contain control chars"));
    }
    let mut parts: Vec<&str> = Vec::new();
    for part in raw.split('/') {
        match part {
            "" | "." => continue,
            ".." => {
                return Err(env_error(format!(
                    "path uri rejects parent traversal (`..`): {raw:?}"
                )));
            }
            other => parts.push(other),
        }
    }
    if parts.is_empty() {
        return Ok("/".to_string());
    }
    Ok(format!("/{}", parts.join("/")))
}
