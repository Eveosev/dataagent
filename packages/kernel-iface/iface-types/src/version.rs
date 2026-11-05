//! lineage: agent-kernel:notes/kernel-iface-versioning.md:1 (A, L-A 契约版本协商)
//! lineage: agent-kernel:notes/DECISIONS.md (A, D83: iface 是唯一契约源)
//!
//! **L-A 契约语义版本**（iface 的版本机制）。
//!
//! ## 为什么需要它（与 L-C `abi_version` 是**两个层级**）
//! - **L-C `abi_version`（线协议版本）**：JSON-RPC **消息形状**的版本（方法名/字段/封套），
//!   在 `initialize` 握手协商（当前 `1..=2`）。换版本 → 客户端解析方式变。
//! - **L-A `contract_version`（契约语义版本，本文件）**：**Rust trait 语义**的版本
//!   （方法集、参数含义、错误契约），在**装配期/注册期**协商。换版本 → 链上代码能否编过、语义是否一致。
//!
//! 两者**不可混用**：同一进程可以 `abi_version=1`（旧线协议客户端）同时 `contract=1.x`（新组件）。
//! 版本矩阵见 `notes/kernel-iface-versioning.md` §2。
//!
//! ## 规则（fail-closed）
//! - **major 必须相等**：major 是"不兼容变更"，跨 major 拒绝（不尝试兼容层）；
//! - **provided.minor >= required.minor**：minor 只做"向后兼容的新增"（内核要求 ^1.0，组件 1.2 可用）；
//! - **patch 忽略**：补丁不改变能力面；
//! - **解析失败 → 拒绝**（不接受 `""`、`"1"`、`"1.x"`、带 pre-release/build 的串——零依赖下不猜语义）。
//!
//! ## 边界
//! 本文件**只定义版本语义与判定**：不含任何 I/O、不读环境、不引外部 crate（iface 零依赖）。
//! "谁来校验、拒绝时用什么 wire 码"属宿主（`host/src/startup` 与 `transport/{loop_runner,env}.rs`）。

/// 当前 iface 的契约版本（**编译期**取自 `iface/Cargo.toml` 的 `version`，因此天然对齐；
/// 测试 `iface_version_matches_cargo_manifest` 再钉一层）。
pub const IFACE_VERSION: &str = env!("CARGO_PKG_VERSION");

/// 解析后的三段式版本（`patch` 只用于展示/诊断，不参与兼容判定）。
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version {
    pub major: u64,
    pub minor: u64,
    pub patch: u64,
}

/// 一个契约的自我描述（组件在装配/注册时上报）。
///
/// 字段是 `&'static str`/静态切片：契约描述是**编译期常量**，不需要运行时分配。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ContractDescriptor {
    /// 契约名（如 `iface-loop`、`iface-env`；与 mint 包/机制名对齐便于诊断）。
    pub name: &'static str,
    /// 该契约实现所满足的版本（`M.m` 或 `M.m.p`）。
    pub version: &'static str,
    /// 可选能力标签（minor 内的**增量能力**；缺一个就不兼容，见 [`require_capabilities`]）。
    pub capabilities: &'static [&'static str],
}

/// 契约的自我描述能力（**default 实现**：既有 8 个契约无需改动即可获得"crate 级"描述）。
pub trait ContractMeta {
    /// 返回本实现的契约描述。默认给"crate 级"描述；具体契约应覆盖为自己的名字/能力。
    fn describe(&self) -> ContractDescriptor {
        ContractDescriptor {
            name: "agentcpm-iface",
            version: IFACE_VERSION,
            capabilities: &[],
        }
    }
}

/// iface 自身（crate 级契约）的描述。
pub fn current() -> ContractDescriptor {
    ContractDescriptor {
        name: "agentcpm-iface",
        version: IFACE_VERSION,
        capabilities: &[],
    }
}

/// 版本不兼容的原因（**稳定 `reason()` 串**；wire 码由宿主决定，见模块文档）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CompatError {
    /// 版本串非法（空/缺 minor/非数字/多余段）——fail-closed，不猜。
    InvalidVersion { side: &'static str, raw: String },
    /// major 不同（不兼容变更，拒绝）。
    MajorMismatch {
        required_major: u64,
        provided_major: u64,
    },
    /// provided.minor < required.minor（内核要求了更新的 minor 能力）。
    MinorTooOld {
        required_minor: u64,
        provided_minor: u64,
    },
    /// 缺少必需能力标签。
    MissingCapability { capability: String },
}

impl CompatError {
    /// 稳定 reason（客户端/装配日志按它匹配；不随措辞变化）。
    pub fn reason(&self) -> &'static str {
        match self {
            Self::InvalidVersion { .. } => "CONTRACT_VERSION_INVALID",
            Self::MajorMismatch { .. } => "CONTRACT_MAJOR_MISMATCH",
            Self::MinorTooOld { .. } => "CONTRACT_MINOR_TOO_OLD",
            Self::MissingCapability { .. } => "CONTRACT_CAPABILITY_MISSING",
        }
    }
}

impl std::fmt::Display for CompatError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidVersion { side, raw } => {
                write!(formatter, "{side} contract version {raw:?} is not M.m[.p]")
            }
            Self::MajorMismatch {
                required_major,
                provided_major,
            } => write!(
                formatter,
                "contract major mismatch: required {required_major}, provided {provided_major}"
            ),
            Self::MinorTooOld {
                required_minor,
                provided_minor,
            } => write!(
                formatter,
                "contract minor too old: required >= {required_minor}, provided {provided_minor}"
            ),
            Self::MissingCapability { capability } => {
                write!(formatter, "missing contract capability {capability:?}")
            }
        }
    }
}

impl std::error::Error for CompatError {}

/// **解析 `M.m` 或 `M.m.p`**（严格；≤40 行，零依赖）。
///
/// fail-closed：任何不符合 `digit+ ('.' digit+){1,2}` 的输入都拒绝——包括 `1`、`1.2.3.4`、
/// `v1.2.0`、`1.2.0-beta`、`1.2.0+build`（pre-release/build 的排序语义需要完整 semver，
/// 零依赖下**不猜**；需要时由调用方先规范化）。
pub fn parse_version(raw: &str) -> Result<Version, CompatError> {
    let invalid = || CompatError::InvalidVersion {
        side: "provided",
        raw: raw.to_string(),
    };
    let mut numbers: [u64; 3] = [0; 3];
    let mut count = 0_usize;
    for piece in raw.split('.') {
        if count >= 3 || piece.is_empty() || !piece.bytes().all(|byte| byte.is_ascii_digit()) {
            return Err(invalid());
        }
        numbers[count] = piece.parse::<u64>().map_err(|_| invalid())?;
        count += 1;
    }
    if count < 2 {
        return Err(invalid());
    }
    Ok(Version {
        major: numbers[0],
        minor: numbers[1],
        patch: numbers[2],
    })
}

/// **兼容判定**：major 相等 && provided.minor >= required.minor（patch 忽略）。
///
/// # Errors
/// [`CompatError::InvalidVersion`]（任一侧解析失败，fail-closed）/
/// [`CompatError::MajorMismatch`] / [`CompatError::MinorTooOld`]。
pub fn is_compatible(required: &str, provided: &str) -> Result<(), CompatError> {
    let required = parse_version(required).map_err(|error| with_side(error, "required"))?;
    let provided = parse_version(provided)?;
    if required.major != provided.major {
        return Err(CompatError::MajorMismatch {
            required_major: required.major,
            provided_major: provided.major,
        });
    }
    if provided.minor < required.minor {
        return Err(CompatError::MinorTooOld {
            required_minor: required.minor,
            provided_minor: provided.minor,
        });
    }
    Ok(())
}

/// 能力标签校验：`required` 中的每一项都必须出现在 `provided` 中。
///
/// # Errors
/// 缺任一项 → [`CompatError::MissingCapability`]（fail-closed：不因"多数满足"放行）。
pub fn require_capabilities(required: &[&str], provided: &[&str]) -> Result<(), CompatError> {
    for capability in required {
        if !provided.contains(capability) {
            return Err(CompatError::MissingCapability {
                capability: (*capability).to_string(),
            });
        }
    }
    Ok(())
}

/// 组合判定：版本 + 能力（装配期/注册期的**单入口**，避免两处各写一遍）。
///
/// # Errors
/// 版本不兼容或能力缺失（见 [`is_compatible`] / [`require_capabilities`]）。
pub fn negotiate(required: &ContractDescriptor, provided: &ContractDescriptor) -> Result<(), CompatError> {
    is_compatible(required.version, provided.version)?;
    require_capabilities(required.capabilities, provided.capabilities)
}

fn with_side(error: CompatError, side: &'static str) -> CompatError {
    match error {
        CompatError::InvalidVersion { raw, .. } => CompatError::InvalidVersion { side, raw },
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── 0) 版本常量与 Cargo.toml 对齐（钉住）────────────────────────────────────────
    #[test]
    fn iface_version_matches_cargo_manifest() {
        // 编译期 `env!("CARGO_PKG_VERSION")` 已取自 Cargo.toml；这里再钉语义形状 + 与手写常量一致。
        assert_eq!(
            IFACE_VERSION, "0.1.0",
            "iface 版本变更必须同步本断言（版本协商的锚点）"
        );
        let parsed = parse_version(IFACE_VERSION).expect("IFACE_VERSION 必须是合法 M.m.p");
        assert_eq!(
            parsed,
            Version {
                major: 0,
                minor: 1,
                patch: 0
            }
        );
    }

    // ── 1) 同 major、provided minor 更高 → 兼容 ──
    #[test]
    fn same_major_newer_minor_is_compatible() {
        assert!(is_compatible("1.0", "1.2").is_ok());
        assert!(is_compatible("1.0.0", "1.0.7").is_ok(), "patch 忽略");
        assert!(is_compatible("1.3", "1.3").is_ok());
    }

    // ── 2) major 不同 → 拒绝（不尝试兼容层）──
    #[test]
    fn different_major_is_rejected() {
        let error = is_compatible("1.0", "2.0").expect_err("跨 major 必须拒绝");
        assert_eq!(error.reason(), "CONTRACT_MAJOR_MISMATCH");
        assert!(matches!(
            error,
            CompatError::MajorMismatch {
                required_major: 1,
                provided_major: 2
            }
        ));
        // 反向也拒（内核要求 2.x，组件只给 1.x）。
        assert!(is_compatible("2.0", "1.9").is_err());
    }

    // ── 3) minor 不足 → 拒绝 ──
    #[test]
    fn older_minor_is_rejected() {
        let error = is_compatible("1.3", "1.2").expect_err("minor 不足必须拒绝");
        assert_eq!(error.reason(), "CONTRACT_MINOR_TOO_OLD");
        assert!(matches!(
            error,
            CompatError::MinorTooOld {
                required_minor: 3,
                provided_minor: 2
            }
        ));
    }

    // ── 4) 非法 semver → fail-closed 拒绝（不猜）──
    #[test]
    fn invalid_version_strings_are_rejected() {
        for raw in [
            "",
            "1",
            "1.",
            ".1",
            "1.x",
            "v1.2.0",
            "1.2.0-beta",
            "1.2.0+build",
            "1.2.3.4",
            "-1.0",
            " 1.0",
            "1.0 ",
        ] {
            assert!(parse_version(raw).is_err(), "{raw:?} 必须被判非法（fail-closed）");
            assert!(is_compatible("1.0", raw).is_err(), "{raw:?}");
            assert!(is_compatible(raw, "1.0").is_err(), "{raw:?}");
        }
        // required 侧非法时 reason 仍可判读（side 标记）。
        let error = is_compatible("1.x", "1.0").expect_err("required 非法");
        assert_eq!(error.reason(), "CONTRACT_VERSION_INVALID");
        assert!(error.to_string().contains("required"));
    }

    // ── 5) 缺 capability → 拒绝 ──
    #[test]
    fn missing_capability_is_rejected() {
        assert!(require_capabilities(&["a", "b"], &["a", "b", "c"]).is_ok());
        let error = require_capabilities(&["a", "z"], &["a", "b"]).expect_err("缺能力必须拒绝");
        assert_eq!(error.reason(), "CONTRACT_CAPABILITY_MISSING");
        assert!(matches!(error, CompatError::MissingCapability { capability } if capability == "z"));
        // 空需求恒通过。
        assert!(require_capabilities(&[], &[]).is_ok());
    }

    // ── 6) negotiate 组合入口 + ContractMeta 默认实现不破坏既有契约 ──
    #[test]
    fn negotiate_combines_version_and_capabilities() {
        let required = ContractDescriptor {
            name: "iface-loop",
            version: "1.0",
            capabilities: &["stream"],
        };
        let compatible = ContractDescriptor {
            name: "loop-a",
            version: "1.4.2",
            capabilities: &["stream", "cancel"],
        };
        assert!(negotiate(&required, &compatible).is_ok());
        let old = ContractDescriptor {
            version: "1.4.2",
            capabilities: &[],
            ..compatible
        };
        assert_eq!(
            negotiate(&required, &old).expect_err("缺能力").reason(),
            "CONTRACT_CAPABILITY_MISSING"
        );
    }

    #[test]
    fn contract_meta_default_matches_crate_version() {
        struct Bare;
        impl ContractMeta for Bare {}

        let described = Bare.describe();
        assert_eq!(described.version, IFACE_VERSION);
        assert_eq!(described.name, "agentcpm-iface");
        assert!(described.capabilities.is_empty());
        // `current()` 与默认实现同一口径（crate 级）。
        assert_eq!(current(), described);
    }
}
