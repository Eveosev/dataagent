//! lineage: agent-kernel:kernel/iface/src/lib.rs:1206 (B, move-only 拆分自单文件 lib.rs)
//!
use crate::types::*;

// ── M42 审核覆盖位置（实现包 `review-gates`；规范 §3 M42，K7 演化与审核）──
//
// 机制要回答的不是"谁能审"，而是：**审核覆盖哪些位置、每个位置必须产出什么结论、
// 结论如何影响后续动作**。这里定契约；判决点/审计在 `core::guard`，编排在 `runtime::review`。

/// 审核覆盖的位置（四段；顺序即执行顺序）。
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
#[non_exhaustive]
pub enum ReviewPosition {
    /// 输入（用户消息 / 上下文进入之前）。
    Input,
    /// 计划（模型给出的行动计划、工具选择）。
    Plan,
    /// 工具参数（真正执行前的参数）。
    ToolParams,
    /// 最终结果（交付给用户之前）。
    FinalResult,
}

impl ReviewPosition {
    /// 四个位置（按执行顺序）。
    pub const ALL: [ReviewPosition; 4] = [
        ReviewPosition::Input,
        ReviewPosition::Plan,
        ReviewPosition::ToolParams,
        ReviewPosition::FinalResult,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            ReviewPosition::Input => "input",
            ReviewPosition::Plan => "plan",
            ReviewPosition::ToolParams => "tool-params",
            ReviewPosition::FinalResult => "final-result",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        Some(match raw {
            "input" => ReviewPosition::Input,
            "plan" => ReviewPosition::Plan,
            "tool-params" => ReviewPosition::ToolParams,
            "final-result" => ReviewPosition::FinalResult,
            _ => return None,
        })
    }

    /// 顺序秩（0..3）；用于"不可跳位/不能倒退"的判定。
    pub fn rank(self) -> u8 {
        match self {
            ReviewPosition::Input => 0,
            ReviewPosition::Plan => 1,
            ReviewPosition::ToolParams => 2,
            ReviewPosition::FinalResult => 3,
        }
    }
}

/// 审核结论（**决定后续动作**：通过继续 / 拒绝阻断 / 挂起等人证 / 退回重做）。
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ReviewVerdict {
    /// 通过：允许继续到下一位置/交付。
    Approve,
    /// 拒绝：**阻断**（不可继续，必须改完重新走审核）。
    Reject { reason: String },
    /// 挂起：**需要人证**（唯一合法阻塞路径；不是自动放行）。
    NeedsHuman { reason: String },
    /// 退回：**带指导回到上一位置重做**（不是阻断，也不是通过）。
    Revise { guidance: String },
}

impl ReviewVerdict {
    pub fn as_str(&self) -> &'static str {
        match self {
            ReviewVerdict::Approve => "approve",
            ReviewVerdict::Reject { .. } => "reject",
            ReviewVerdict::NeedsHuman { .. } => "needs-human",
            ReviewVerdict::Revise { .. } => "revise",
        }
    }

    pub fn is_approve(&self) -> bool {
        matches!(self, ReviewVerdict::Approve)
    }

    pub fn is_blocking(&self) -> bool {
        matches!(self, ReviewVerdict::Reject { .. })
    }

    pub fn is_suspending(&self) -> bool {
        matches!(self, ReviewVerdict::NeedsHuman { .. })
    }

    pub fn is_revising(&self) -> bool {
        matches!(self, ReviewVerdict::Revise { .. })
    }

    /// 结论里带的人读理由/指导（Approve 为 None）。
    pub fn reason(&self) -> Option<&str> {
        match self {
            ReviewVerdict::Approve => None,
            ReviewVerdict::Reject { reason } => Some(reason.as_str()),
            ReviewVerdict::NeedsHuman { reason } => Some(reason.as_str()),
            ReviewVerdict::Revise { guidance } => Some(guidance.as_str()),
        }
    }

    /// 稳定字符串（审计人读列；不随 reason 变化）。
    pub fn tag(self) -> &'static str {
        self.as_str()
    }
}

/// 一次审核请求。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReviewRequest {
    /// 审核位置。
    pub position: ReviewPosition,
    /// 被审对象引用（输入摘要 / 计划 id / 工具调用 id / 结果 id；**不含原文**）。
    pub subject_ref: String,
    /// 用哪份审核策略/门（`None` = 默认策略）。
    pub policy_ref: Option<String>,
    /// 关联 ID（审计必填字段之一）。
    pub correlation_id: Option<String>,
    /// 发起会话（审计必填；`None` = 内核自身）。
    pub session: Option<SessionId>,
}

impl ReviewRequest {
    /// 引用串合法性：非空、≤256、无控制字符/分隔符（避免污染审计单行与日志）。
    pub fn is_well_formed(&self) -> bool {
        fn valid_ref(text: &str) -> bool {
            !text.is_empty()
                && text.len() <= 256
                && !text.contains(['|', '\t', '\n', '\r'])
                && !text.chars().any(char::is_control)
        }
        valid_ref(&self.subject_ref) && self.policy_ref.as_deref().map(valid_ref).unwrap_or(true)
    }
}
