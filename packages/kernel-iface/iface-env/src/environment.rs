//! lineage: agent-kernel:kernel/iface/src/lib.rs:1646 (B, move-only 拆分自单文件 lib.rs)
//!
use super::EnvId;
use super::env_error;
use crate::types::Error;

/// 环境类型。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum EnvironmentKind {
    /// 本机（进程内 fs/exec）。
    Local,
    /// 远端（通过 `url` 连接；本轮不做真实连接）。
    Remote,
}

impl EnvironmentKind {
    pub fn as_str(self) -> &'static str {
        match self {
            EnvironmentKind::Local => "local",
            EnvironmentKind::Remote => "remote",
        }
    }
}

/// 环境能力声明（**粗粒度四开关**；codex 的细粒度 flag 收敛见 note 对照表）。
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct EnvironmentCapabilities {
    /// 是否提供文件系统后端（read/write/list/stat）。
    pub fs: bool,
    /// 是否提供进程执行后端。
    pub exec: bool,
    /// 是否支持对已启动进程发信号（`signal`）。
    pub signals: bool,
    /// 是否支持流式输出/长连接（codex 的 `process/read` 流；本轮只声明）。
    pub streams: bool,
}

impl EnvironmentCapabilities {
    /// 全不支持（安全默认）。
    pub fn none() -> Self {
        Self::default()
    }

    /// 本机骨架默认：fs + exec 可用；信号/流式未实现（诚实：本地实现仍可 `Unsupported`）。
    pub fn local_default() -> Self {
        Self {
            fs: true,
            exec: true,
            signals: false,
            streams: false,
        }
    }

    /// 是否声明了任何能力。
    pub fn any(self) -> bool {
        self.fs || self.exec || self.signals || self.streams
    }
}

/// 环境描述（注册/发现的最小形状）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Environment {
    pub id: EnvId,
    pub kind: EnvironmentKind,
    /// 远端连接地址（`Remote` 必填；`Local` 应为 None）。
    pub url: Option<String>,
    /// 远端公钥（可选；本轮只做格式校验，不做握手）。
    pub public_key: Option<String>,
    /// 附加声明（键值对；如 `root`/`profile`/`os`，供 L-D 装配参考）。
    pub profile: Vec<(String, String)>,
    pub capabilities: EnvironmentCapabilities,
}

impl Environment {
    /// 本机环境（保留 id `local`）。
    pub fn local() -> Self {
        Self {
            id: EnvId::local(),
            kind: EnvironmentKind::Local,
            url: None,
            public_key: None,
            profile: Vec::new(),
            capabilities: EnvironmentCapabilities::local_default(),
        }
    }

    pub fn profile_value(&self, key: &str) -> Option<&str> {
        self.profile
            .iter()
            .find(|(name, _)| name == key)
            .map(|(_, value)| value.as_str())
    }

    /// 校验：id 合法、`Remote` 必须有 `url`、`Local` 不得带 `url`、
    /// `public_key` 字符集/长度、profile 键值字符集。
    ///
    /// 返回 `Err(Protocol/-32602)`（参数非法）——**不**静默修正。
    pub fn validate(&self) -> Result<(), Error> {
        EnvId::new(self.id.as_str())?;
        match self.kind {
            EnvironmentKind::Remote => {
                let Some(url) = &self.url else {
                    return Err(env_error(format!(
                        "remote environment {:?} must declare `url`",
                        self.id.as_str()
                    )));
                };
                if url.is_empty() || url.len() > 512 || url.chars().any(char::is_control) {
                    return Err(env_error(format!(
                        "environment url must be 1..=512 printable chars, got {url:?}"
                    )));
                }
            }
            EnvironmentKind::Local => {
                if self.url.is_some() {
                    return Err(env_error(format!(
                        "local environment {:?} must not declare `url`",
                        self.id.as_str()
                    )));
                }
            }
        }
        if let Some(key) = &self.public_key {
            // 本轮只做形状校验：base64-ish 字符集 + 长度上限（真实握手/指纹属后续）。
            let valid_len = (16..=512).contains(&key.len());
            let valid_chars = key
                .chars()
                .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '+' | '/' | '=' | '-' | '_'));
            if !valid_len || !valid_chars {
                return Err(env_error(format!(
                    "environment public_key must be 16..=512 base64-like chars, got {} chars",
                    key.len()
                )));
            }
        }
        for (name, value) in &self.profile {
            if name.is_empty()
                || name.len() > 64
                || !name
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '.' | '_' | '-'))
            {
                return Err(env_error(format!(
                    "profile key {name:?} must be 1..=64 chars of [A-Za-z0-9._-]"
                )));
            }
            if value.len() > 1024 || value.chars().any(char::is_control) {
                return Err(env_error(format!(
                    "profile value for {name:?} must be <=1024 printable chars"
                )));
            }
        }
        Ok(())
    }
}
