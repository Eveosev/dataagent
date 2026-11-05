//! lineage: agent-kernel:kernel/iface/src/lib.rs:256 (B, move-only 拆分自单文件 lib.rs)
//!
// ── M04 打断规格（规范 §3.1，唯一的 kept-by-spec）───────────────────────
//
// 三层结构：`被打断任务 → 打断点 → 打断意图`（外加「作用对象」）。
// kernel 只负责**表达与记录**这套语义（N≤2 配额、三元组、取消≠撤销、半成品），
// 「打断检测用什么信号 / 什么阈值」是实现包的事（规范 §3 M04「非职责」列）。

/// M04 硬约束：任一时刻最多保留 2 个**待交付**任务（N ≤ 2）。
///
/// 计入 N 的状态见 [`InterruptTaskState::counts_toward_quota`]；**暂停不释放名额**。
/// 这是 M32 容量/预算的具体形态（规范 §3.1 硬要求 1）。
pub const INTERRUPT_MAX_PENDING: usize = 2;

/// 第一层：被打断任务类型（规范 §3.1）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InterruptTaskKind {
    /// T：工具任务 —— 垫话或交付都能被打断。
    ToolTask,
    /// R：直接回答任务 —— **只能**在交付段（O/M/L）被打断。
    DirectAnswer,
}

impl InterruptTaskKind {
    pub fn as_str(self) -> &'static str {
        match self {
            InterruptTaskKind::ToolTask => "T",
            InterruptTaskKind::DirectAnswer => "R",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        match raw {
            "T" => Some(InterruptTaskKind::ToolTask),
            "R" => Some(InterruptTaskKind::DirectAnswer),
            _ => None,
        }
    }

    /// 该类型的任务能否在给定打断点被打断：T 全允许；R 不允许 P（垫话）。
    pub fn can_interrupt_at(self, point: InterruptPoint) -> bool {
        !matches!(
            (self, point),
            (InterruptTaskKind::DirectAnswer, InterruptPoint::Filler)
        )
    }
}

/// 第二层：打断点（按**用户需求被满足程度**划分，**不按秒数或字数比例**，规范 §3.1）。
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
#[non_exhaustive]
pub enum InterruptPoint {
    /// P 垫话中（接单未交付，仅 T）。
    Filler,
    /// O 交付开头（核心信息未说）。
    DeliveryStart,
    /// M 交付中段（部分核心已说）。
    DeliveryMiddle,
    /// L 交付尾部（核心已满足，补充/收尾中）。
    DeliveryTail,
}

impl InterruptPoint {
    pub fn as_str(self) -> &'static str {
        match self {
            InterruptPoint::Filler => "P",
            InterruptPoint::DeliveryStart => "O",
            InterruptPoint::DeliveryMiddle => "M",
            InterruptPoint::DeliveryTail => "L",
        }
    }

    /// 是否属于交付段（O/M/L）；R 类任务只能在这里被打断。
    pub fn is_delivery(self) -> bool {
        !matches!(self, InterruptPoint::Filler)
    }

    pub fn parse(raw: &str) -> Option<Self> {
        match raw {
            "P" => Some(InterruptPoint::Filler),
            "O" => Some(InterruptPoint::DeliveryStart),
            "M" => Some(InterruptPoint::DeliveryMiddle),
            "L" => Some(InterruptPoint::DeliveryTail),
            _ => None,
        }
    }
}

/// 第三层：打断意图的 6 个类（规范 §3.1）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InterruptIntentClass {
    /// A 追加任务。
    Append,
    /// B 修改任务。
    Modify,
    /// C 取消或替换。
    CancelOrReplace,
    /// D 暂停或重排。
    PauseOrReorder,
    /// E 澄清或质疑。
    Clarify,
    /// F 调整交付。
    AdjustDelivery,
}

impl InterruptIntentClass {
    /// 6 个类各 1 个字母码。
    pub fn as_str(self) -> &'static str {
        match self {
            InterruptIntentClass::Append => "A",
            InterruptIntentClass::Modify => "B",
            InterruptIntentClass::CancelOrReplace => "C",
            InterruptIntentClass::PauseOrReorder => "D",
            InterruptIntentClass::Clarify => "E",
            InterruptIntentClass::AdjustDelivery => "F",
        }
    }

    /// 全部 6 个类（按 A–F 顺序）。
    pub const ALL: [InterruptIntentClass; 6] = [
        InterruptIntentClass::Append,
        InterruptIntentClass::Modify,
        InterruptIntentClass::CancelOrReplace,
        InterruptIntentClass::PauseOrReorder,
        InterruptIntentClass::Clarify,
        InterruptIntentClass::AdjustDelivery,
    ];
}

/// 第三层：打断意图子类型（6 类）。
///
/// **计数口径**：规范 §3.1 原文标题误写「17」，同节表格逐项枚举实为 **18**（A–F 各 3 个）；
/// v9.4 已按 [DECISIONS D52] 更正为 **18**。本实现按 18 个枚举变体落盘。
///
/// [DECISIONS D52]: ../../../../notes/DECISIONS.md
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
#[non_exhaustive]
pub enum InterruptIntent {
    /// A1 并列追加。
    A1,
    /// A2 新任务优先。
    A2,
    /// A3 基于当前结果追加。
    A3,
    /// B1 纠正已有条件。
    B1,
    /// B2 增加约束。
    B2,
    /// B3 调整范围或重点。
    B3,
    /// C1 完全取消。
    C1,
    /// C2 部分取消。
    C2,
    /// C3 取消并替换。
    C3,
    /// D1 暂停当前口播。
    D1,
    /// D2 暂缓任务。
    D2,
    /// D3 调整已有任务优先级（仅 N=2）。
    D3,
    /// E1 要求重复。
    E1,
    /// E2 要求解释。
    E2,
    /// E3 要求核实。
    E3,
    /// F1 改变表达方式。
    F1,
    /// F2 压缩交付。
    F2,
    /// F3 提前结束交付。
    F3,
}

impl InterruptIntent {
    /// 表格列出的全部子类型（A–F 各 3 个 = 18；见上面的计数口径说明）。
    pub const ALL: [InterruptIntent; 18] = [
        InterruptIntent::A1,
        InterruptIntent::A2,
        InterruptIntent::A3,
        InterruptIntent::B1,
        InterruptIntent::B2,
        InterruptIntent::B3,
        InterruptIntent::C1,
        InterruptIntent::C2,
        InterruptIntent::C3,
        InterruptIntent::D1,
        InterruptIntent::D2,
        InterruptIntent::D3,
        InterruptIntent::E1,
        InterruptIntent::E2,
        InterruptIntent::E3,
        InterruptIntent::F1,
        InterruptIntent::F2,
        InterruptIntent::F3,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            InterruptIntent::A1 => "A1",
            InterruptIntent::A2 => "A2",
            InterruptIntent::A3 => "A3",
            InterruptIntent::B1 => "B1",
            InterruptIntent::B2 => "B2",
            InterruptIntent::B3 => "B3",
            InterruptIntent::C1 => "C1",
            InterruptIntent::C2 => "C2",
            InterruptIntent::C3 => "C3",
            InterruptIntent::D1 => "D1",
            InterruptIntent::D2 => "D2",
            InterruptIntent::D3 => "D3",
            InterruptIntent::E1 => "E1",
            InterruptIntent::E2 => "E2",
            InterruptIntent::E3 => "E3",
            InterruptIntent::F1 => "F1",
            InterruptIntent::F2 => "F2",
            InterruptIntent::F3 => "F3",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        Some(match raw {
            "A1" => InterruptIntent::A1,
            "A2" => InterruptIntent::A2,
            "A3" => InterruptIntent::A3,
            "B1" => InterruptIntent::B1,
            "B2" => InterruptIntent::B2,
            "B3" => InterruptIntent::B3,
            "C1" => InterruptIntent::C1,
            "C2" => InterruptIntent::C2,
            "C3" => InterruptIntent::C3,
            "D1" => InterruptIntent::D1,
            "D2" => InterruptIntent::D2,
            "D3" => InterruptIntent::D3,
            "E1" => InterruptIntent::E1,
            "E2" => InterruptIntent::E2,
            "E3" => InterruptIntent::E3,
            "F1" => InterruptIntent::F1,
            "F2" => InterruptIntent::F2,
            "F3" => InterruptIntent::F3,
            _ => return None,
        })
    }

    pub fn class(self) -> InterruptIntentClass {
        use InterruptIntent::*;
        match self {
            A1 | A2 | A3 => InterruptIntentClass::Append,
            B1 | B2 | B3 => InterruptIntentClass::Modify,
            C1 | C2 | C3 => InterruptIntentClass::CancelOrReplace,
            D1 | D2 | D3 => InterruptIntentClass::PauseOrReorder,
            E1 | E2 | E3 => InterruptIntentClass::Clarify,
            F1 | F2 | F3 => InterruptIntentClass::AdjustDelivery,
        }
    }

    /// A 类（A1/A2/A3）：原任务保留、**增加**新独立需求 → 受 N≤2 配额约束（N=2 拒绝）。
    pub fn is_append(self) -> bool {
        matches!(
            self,
            InterruptIntent::A1 | InterruptIntent::A2 | InterruptIntent::A3
        )
    }

    /// C3 取消并替换：N=2 时**允许**（不允许「保留原任务又开第三个」，但替换不算追加）。
    pub fn is_replace(self) -> bool {
        matches!(self, InterruptIntent::C3)
    }

    /// D3 调整已有任务优先级：**仅 N=2 允许**。
    pub fn requires_two_pending(self) -> bool {
        matches!(self, InterruptIntent::D3)
    }

    /// C 类：取消或替换（被打断任务会进入 `Cancelled`）。
    pub fn cancels(self) -> bool {
        matches!(
            self,
            InterruptIntent::C1 | InterruptIntent::C2 | InterruptIntent::C3
        )
    }

    /// D1/D2：暂停（任务仍占用名额 —— 暂停不释放名额）。
    pub fn pauses(self) -> bool {
        matches!(self, InterruptIntent::D1 | InterruptIntent::D2)
    }

    /// 该意图是否要**打开一个新任务**（A 类追加 / C3 替换）。
    pub fn opens_task(self) -> bool {
        self.is_append() || self.is_replace()
    }
}

/// 作用对象（规范 §3.1）：S 当前任务 / O 另一件 / B 两件 / 任务内子项。
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InterruptTarget {
    /// S：当前任务。
    CurrentTask,
    /// O：另一件任务（引用其 task id）。
    Other(String),
    /// B：两件（当前 + 引用的另一件）。
    Both(String),
    /// 任务内子项（引用子项名）。
    SubItem(String),
}

impl InterruptTarget {
    /// 单行编码（append-only 事件用，不得含 tab/newline/`|`）：`S` / `O:<id>` / `B:<id>` / `I:<item>`。
    pub fn encode(&self) -> String {
        match self {
            InterruptTarget::CurrentTask => "S".to_string(),
            InterruptTarget::Other(task) => format!("O:{task}"),
            InterruptTarget::Both(task) => format!("B:{task}"),
            InterruptTarget::SubItem(item) => format!("I:{item}"),
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        if raw == "S" {
            return Some(InterruptTarget::CurrentTask);
        }
        let (tag, value) = raw.split_once(':')?;
        if value.is_empty() {
            return None;
        }
        Some(match tag {
            "O" => InterruptTarget::Other(value.to_string()),
            "B" => InterruptTarget::Both(value.to_string()),
            "I" => InterruptTarget::SubItem(value.to_string()),
            _ => return None,
        })
    }

    /// 需要引用的「另一件」任务 id（O/B）。
    pub fn referenced_task(&self) -> Option<&str> {
        match self {
            InterruptTarget::Other(task) | InterruptTarget::Both(task) => Some(task.as_str()),
            _ => None,
        }
    }
}

/// 任务状态：**前 5 个计入 N**（规范 §3.1「计入 N 的状态」），后 3 个是终态（不计入）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InterruptTaskState {
    /// 尚未执行。
    Pending,
    /// 正在执行。
    Running,
    /// 结果已返回但未交付。
    ResultReady,
    /// 正在交付。
    Delivering,
    /// 暂停后仍需恢复（**暂停不释放名额**）。
    Paused,
    /// 已交付（终态）。
    Delivered,
    /// 已取消（终态）。**≠ 撤销已完成操作**（已完成的外部操作保留）。
    Cancelled,
    /// 失败（终态）。
    Failed,
}

impl InterruptTaskState {
    pub fn as_str(self) -> &'static str {
        match self {
            InterruptTaskState::Pending => "pending",
            InterruptTaskState::Running => "running",
            InterruptTaskState::ResultReady => "result-ready",
            InterruptTaskState::Delivering => "delivering",
            InterruptTaskState::Paused => "paused",
            InterruptTaskState::Delivered => "delivered",
            InterruptTaskState::Cancelled => "cancelled",
            InterruptTaskState::Failed => "failed",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        Some(match raw {
            "pending" => InterruptTaskState::Pending,
            "running" => InterruptTaskState::Running,
            "result-ready" => InterruptTaskState::ResultReady,
            "delivering" => InterruptTaskState::Delivering,
            "paused" => InterruptTaskState::Paused,
            "delivered" => InterruptTaskState::Delivered,
            "cancelled" => InterruptTaskState::Cancelled,
            "failed" => InterruptTaskState::Failed,
            _ => return None,
        })
    }

    /// 是否计入 N（尚未执行 / 正在执行 / 结果已返回未交付 / 正在交付 / 暂停待恢复）。
    pub fn counts_toward_quota(self) -> bool {
        matches!(
            self,
            InterruptTaskState::Pending
                | InterruptTaskState::Running
                | InterruptTaskState::ResultReady
                | InterruptTaskState::Delivering
                | InterruptTaskState::Paused
        )
    }

    pub fn is_terminal(self) -> bool {
        !self.counts_toward_quota()
    }

    /// 状态迁移是否合法（M04 账本侧；终态不可离开）。
    ///
    /// `Delivered` 必须先有结果（只能从 `ResultReady`/`Delivering` 进入），
    /// 否则「交付」会凭空出现。
    pub fn transition_allowed(from: Self, to: Self) -> bool {
        use InterruptTaskState::*;
        match from {
            Pending => matches!(
                to,
                Running | ResultReady | Delivering | Paused | Cancelled | Failed
            ),
            Running => matches!(to, ResultReady | Delivering | Paused | Cancelled | Failed),
            ResultReady => matches!(to, Delivering | Paused | Delivered | Cancelled | Failed),
            Delivering => matches!(to, ResultReady | Paused | Delivered | Cancelled | Failed),
            Paused => matches!(
                to,
                Pending | Running | ResultReady | Delivering | Cancelled | Failed
            ),
            Delivered | Cancelled | Failed => false,
        }
    }
}

/// 已完成外部操作的状态：**取消 ≠ 撤销**（规范 §3.1 硬要求 3）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InterruptEffectState {
    /// 外部操作已完成且不可撤回 —— 取消任务**不得**把它改成 `Undone`。
    Completed,
    /// 已撤销：只能由**显式撤销事件**写入（kernel 不因一句取消就假造撤销）。
    Undone,
}

impl InterruptEffectState {
    pub fn as_str(self) -> &'static str {
        match self {
            InterruptEffectState::Completed => "completed",
            InterruptEffectState::Undone => "undone",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        match raw {
            "completed" => Some(InterruptEffectState::Completed),
            "undone" => Some(InterruptEffectState::Undone),
            _ => None,
        }
    }
}

/// 三元组：`被打断任务 → 打断点 → 打断意图`（+ 作用对象），规范 §3.1 硬要求 2。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InterruptTriad {
    pub task: String,
    pub point: InterruptPoint,
    pub intent: InterruptIntent,
    pub target: InterruptTarget,
}
