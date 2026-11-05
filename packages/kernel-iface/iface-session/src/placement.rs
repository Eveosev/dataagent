//! lineage: agent-kernel:kernel/iface/src/session.rs:1 (A, Session v2 · V0 纯类型；D55/D56)
//!
//! 运行位置声明（**包/会话应当跑在哪台环境上**）。
//!
//! 注意：这是**声明**（L-D 语义的形状），不是执行；真正的"选哪个环境执行"由宿主/调度决定。
//! 与 `iface-env` 的关系：`PlacementMode` 只表达允许范围，具体环境由 `EnvId` 指定。

use std::fmt;

/// 运行位置偏好。
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord)]
#[non_exhaustive]
pub enum PlacementMode {
    /// 只在**本地**环境运行（不跨设备）。
    LocalOnly,
    /// **跟随工作区**所在环境（工作区在 B 就在 B 执行）。
    FollowWorkspace,
    /// 本地或远端**都可以**（由调度按能力/负载决定）；**默认值**。
    #[default]
    Either,
}

impl PlacementMode {
    pub fn as_str(self) -> &'static str {
        match self {
            PlacementMode::LocalOnly => "local-only",
            PlacementMode::FollowWorkspace => "follow-workspace",
            PlacementMode::Either => "either",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        Some(match raw {
            "local-only" => PlacementMode::LocalOnly,
            "follow-workspace" => PlacementMode::FollowWorkspace,
            "either" => PlacementMode::Either,
            _ => return None,
        })
    }

    /// 是否允许在远端执行。
    pub fn allows_remote(self) -> bool {
        !matches!(self, PlacementMode::LocalOnly)
    }
}

impl fmt::Display for PlacementMode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}
