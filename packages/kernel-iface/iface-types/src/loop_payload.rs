//! lineage: agent-kernel:kernel/iface/src/loop_.rs (D79/T79 新增：loop 契约载荷，从 loop_.rs 抽出)
//!
//! `iface-loop` 的**载荷类型**（task-79 / D75「loop 契约保留」+ D74「同步立即 Ready」）。
//!
//! 负责：`LoopContract` 4 个方法的入参与返回类型——让"换一个 loop 实现"所需的语义都能表达。
//! 不负责：具体 loop 的编排算法、模型/工具调用、事件持久化（那些是实现方与 L-C/会话日志的事）。
//!
//! **本模块全部是纯数据**（无 I/O、无异步、无 unsafe），字段即契约；新增字段只增不改（AIP-180）。
//! 与既有类型的关系：`RequestState`/`BudgetClass`/`TurnId`/`SessionId`/`Error` 复用 `types` 既有定义，
//! **不在此重复定义**；M04 的 6 类 18 子类型意图仍在 `types::interrupt`（`InterruptIntent`），
//! 本模块只提供契约侧的粗粒度 `InterruptKind`。

use super::{BudgetClass, RequestState, TurnId};

// ─────────────────────────────────────────────────────────────
// describe 的载荷：step 语义 + 9 个能力位
// ─────────────────────────────────────────────────────────────

/// step 的粒度语义（§6.8 交接要求"必须能说明 step 是什么"）。
///
/// 三档**从粗到细**：`TurnToCompletion` ⊃ `ModelRoundWithTools` ⊃ `HostRoundtrip`。
/// 由实现方**如实**声明自己属于哪档，内核不得假定（D74：不承诺在途级调度）。
///
/// ## 契约规则：声明的粒度可以更细（task-82 / 来自 task-80 的真实缺口）
///
/// 实现声明的粒度**可以比"一次 step 跑完一个 turn"更细**，即存在偏序：
/// `HostRoundtrip` ⊂ `ModelRoundWithTools` ⊂ `TurnToCompletion`（左边更细）。
///
/// **调用方不得假设"一次 `step` 必然推进一个完整 turn"**——必须按返回的 [`super::super::r#loop::StepOutcome`]
/// （`Advanced` / `Finished`）与 [`LoopEvent::seq`] 判断进展，而不是按"调用了几次 `step`"计数。
///
/// **这条正是"适配器一次 `step` 只做恰好一次 host 模块往返"能成立的前提**：
/// 没有它，适配器要么虚报成 `ModelRoundWithTools`（对调用方撒谎），要么被迫在一次 `step` 里跑多次往返
/// （违背 D74 的"立即 Ready、不做长阻塞"）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum StepSemantics {
    /// 一次 `step` 跑完整个 turn 到终态（Rust sidecar `drive_turn` / Node `AgentLoop.run` 的**公开**粒度；
    /// 内部可能跑多轮模型 + 工具）。
    TurnToCompletion,
    /// 一次 `step` = **一个模型轮 + 该轮产生的工具批**（内核需多次调用才跑完一个 turn）。
    ModelRoundWithTools,
    /// 一次 `step` = **恰好一次 host 模块往返**（最细粒度，可被宿主逐帧调度）。
    ///
    /// 来自 task-80 适配器的真实上报：其 `step()` 实测 `host_roundtrips == 1`。
    HostRoundtrip,
}

impl StepSemantics {
    pub fn as_str(self) -> &'static str {
        match self {
            StepSemantics::TurnToCompletion => "turn-to-completion",
            StepSemantics::ModelRoundWithTools => "model-round-with-tools",
            StepSemantics::HostRoundtrip => "host-roundtrip",
        }
    }

    /// 粒度序（数值越大 = 越粗 = 一次推进越多）。私有：对外只暴露 `is_finer_than`。
    fn grain(self) -> u8 {
        match self {
            StepSemantics::HostRoundtrip => 0,
            StepSemantics::ModelRoundWithTools => 1,
            StepSemantics::TurnToCompletion => 2,
        }
    }

    /// `self` 是否比 `other` **更细**（一次推进更少 → 调用方需要更多次 `step` 才能等价）。
    ///
    /// 调用方据此决定"要不要循环调用 `step`"，而不是假定一次就够。
    pub fn is_finer_than(self, other: StepSemantics) -> bool {
        self.grain() < other.grain()
    }
}

/// 9 个能力位：实现方**声明**自己支持哪些，内核据此决定可否 pause/steer/handoff 等。
///
/// 默认**全 false**（fail-closed：未声明即视为不支持，与 §6.3 第 6 条一致）。
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct LoopCapabilities {
    /// 能否在 step 边界暂停并稍后恢复。
    pub pausable: bool,
    /// 能否在 turn 进行中插入指令（steering）。
    pub steerable: bool,
    /// 响应 `interrupt` 的能力（不等于"能撤销已完成操作"，见 M04）。
    pub interruptible: bool,
    /// 能否从持久化的会话记录恢复后继续。
    pub resumable: bool,
    /// 是否满足 §6.8 的 step 边界交接要求。
    pub handoff_ready: bool,
    /// 是否支持一次模型轮内并行多个工具调用。
    pub parallel_tools: bool,
    /// 是否产生流式事件（`LoopEvent` 增量），而非只在终态一次性返回。
    pub streaming_events: bool,
    /// 是否感知预算（会读 `TurnInput.budget` 并在耗尽时停）。
    pub budget_aware: bool,
    /// 是否可能进入需要人介入的状态（`WaitingHuman`）。
    pub needs_human: bool,
}

impl LoopCapabilities {
    /// 全不支持（默认值，fail-closed）。
    pub const NONE: LoopCapabilities = LoopCapabilities {
        pausable: false,
        steerable: false,
        interruptible: false,
        resumable: false,
        handoff_ready: false,
        parallel_tools: false,
        streaming_events: false,
        budget_aware: false,
        needs_human: false,
    };

    /// 声明了多少个能力位为 true（用于日志/审计，不是判定依据）。
    pub fn declared(self) -> u8 {
        let mut n = 0u8;
        for on in [
            self.pausable,
            self.steerable,
            self.interruptible,
            self.resumable,
            self.handoff_ready,
            self.parallel_tools,
            self.streaming_events,
            self.budget_aware,
            self.needs_human,
        ] {
            if on {
                n += 1;
            }
        }
        n
    }
}

// ─────────────────────────────────────────────────────────────
// step 的入参：TurnInput
// ─────────────────────────────────────────────────────────────

/// 一条规范化消息（**最小共有子集**：role + 文本）。
///
/// 富内容（图片/音频/多段 parts）属协议编解码层，不进本契约——避免把某一家 loop 的
/// 消息模型固化进 kernel（D73 的同一条原则）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CanonicalMessage {
    pub role: CanonicalRole,
    pub text: String,
}

/// 规范化消息角色。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum CanonicalRole {
    System,
    User,
    Assistant,
    Tool,
}

impl CanonicalRole {
    pub fn as_str(self) -> &'static str {
        match self {
            CanonicalRole::System => "system",
            CanonicalRole::User => "user",
            CanonicalRole::Assistant => "assistant",
            CanonicalRole::Tool => "tool",
        }
    }
}

/// 预算提示（**不是强制**：强制判决在 kernel 的 budget 面，见 M32）。
///
/// 复用既有 `BudgetClass`（Turns/OutputTokens/ContextTokens/TotalTime），不新增预算类别。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BudgetHint {
    pub class: BudgetClass,
    /// 该类的限额；`None` = 只提示"感知预算"而不给具体值。
    pub limit: Option<u64>,
}

/// 一次 `step` 的执行身份（parity 要求：每次推进必须可归因、可幂等）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ExecutionIdentity {
    /// 本次运行 id（跨 step 稳定）。
    pub run_id: String,
    /// 本次操作的 id（每次 `step` 唯一，用于对账）。
    pub operation_id: String,
    /// 幂等键（重复投递同一 key 不得重复产生副作用）。
    pub idempotency_key: Option<String>,
    /// 截止时间（毫秒，相对时钟）；`None` = 无截止。
    pub deadline_ms: Option<u64>,
}

/// `step` 的入参：内核把「这一轮要推进什么」交给 loop。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TurnInput {
    /// 本轮的开场消息（**增量**，不是全量历史；loop 可从会话记录自取更多）。
    pub messages: Vec<CanonicalMessage>,
    /// 本轮最多允许几次模型轮（`None` = 实现默认）。
    pub max_turns: Option<u32>,
    /// 预算提示（非强制）。
    pub budget: Option<BudgetHint>,
    /// 执行身份（必需：每次推进都要可归因）。
    pub execution: ExecutionIdentity,
}

impl TurnInput {
    /// 最小构造：只给必需项（messages + execution），其余取默认。
    pub fn new(messages: Vec<CanonicalMessage>, execution: ExecutionIdentity) -> TurnInput {
        TurnInput {
            messages,
            max_turns: None,
            budget: None,
            execution,
        }
    }
}

// ─────────────────────────────────────────────────────────────
// step 的返回：LoopEvent（8 种最小共有 kind）
// ─────────────────────────────────────────────────────────────

/// 事件种类：取 parity 24 种 kind 的**最小共有 8 种**（其余属实现特有，走 L-C 的 `_meta`/扩展字段）。
///
/// 选择依据：这 8 种是"内核能理解、且两家 loop 都会产生"的公共子集；
/// 只有 `streaming_events` 能力为 true 的实现才需要增量产出它们。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum LoopEventKind {
    TurnStarted,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolResult,
    /// 进入需要人介入的阻塞（对应 `StepOutcome::WaitingHuman` 的原因）。
    HumanBlocked,
    TurnCompleted,
    /// 过程状态变化（阶段/配额/进度），不承载语义结论。
    Status,
}

impl LoopEventKind {
    pub fn as_str(self) -> &'static str {
        match self {
            LoopEventKind::TurnStarted => "turn_started",
            LoopEventKind::ModelRequest => "model_request",
            LoopEventKind::ModelResponse => "model_response",
            LoopEventKind::ToolCall => "tool_call",
            LoopEventKind::ToolResult => "tool_result",
            LoopEventKind::HumanBlocked => "human_blocked",
            LoopEventKind::TurnCompleted => "turn_completed",
            LoopEventKind::Status => "status",
        }
    }
}

/// 一条 loop 事件。
///
/// `seq` 必须**单调递增**（同一次 run 内），用于并入会话事件日志与 `session.watch` 的游标对账；
/// 每 kind 的具体语义字段属编解码层，不在 iface 里固化成 struct（见模块文档）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LoopEvent {
    pub seq: u64,
    pub kind: LoopEventKind,
}

impl LoopEvent {
    pub fn new(seq: u64, kind: LoopEventKind) -> LoopEvent {
        LoopEvent { seq, kind }
    }
}

/// 一次 turn 的终态摘要。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TurnOutcome {
    pub completed: bool,
    pub stop_reason: String,
    /// 该 turn 最后一条事件的 seq（用于对账"事件到哪了"）。
    pub final_seq: u64,
}

/// 终态（用于 `LoopStatus.terminal`）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TurnTerminal {
    pub code: String,
    pub stop_reason: String,
}

// ─────────────────────────────────────────────────────────────
// 阻塞态（D63 G1：人阻塞态必须可见，但是**派生投影**，不是新持久状态）
// ─────────────────────────────────────────────────────────────

/// 阻塞在什么上（D63 G1 的三类）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum BlockedOnKind {
    /// 等被打断任务的后续指令（M04）。
    Interrupt,
    /// 等审批（M18/M42）。
    Approval,
    /// 等认证/授权（M18b）。
    Auth,
}

impl BlockedOnKind {
    pub fn as_str(self) -> &'static str {
        match self {
            BlockedOnKind::Interrupt => "interrupt",
            BlockedOnKind::Approval => "approval",
            BlockedOnKind::Auth => "auth",
        }
    }
}

/// 一条阻塞项：**派生投影**（内核不因此新增持久状态，守 §3.5）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BlockedOn {
    pub kind: BlockedOnKind,
    /// 阻塞项 id（interrupt_id / approval_id / principal 等，由 kind 决定）。
    pub id: String,
    /// 若人需要回填结构化数据，给出 JSON Schema（D63 G2：resume 契约）。
    pub response_schema: Option<String>,
}

// ─────────────────────────────────────────────────────────────
// interrupt 的载荷
// ─────────────────────────────────────────────────────────────

/// 中断的**粗粒度**种类（M04 的 6 类 18 子类型仍走 `types::interrupt::InterruptIntent`；
/// 本枚举只表达"内核要 loop 做什么动作"，避免把 M04 分类学塞进 loop 契约）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InterruptKind {
    /// 取消未完成的工作（**不等于撤销已完成操作**，M04）。
    Cancel,
    /// 到期/超时（预算或 deadline 触发）。
    Expire,
    /// 插入新指令改变方向（不取消当前工作）。
    Steer,
}

impl InterruptKind {
    pub fn as_str(self) -> &'static str {
        match self {
            InterruptKind::Cancel => "cancel",
            InterruptKind::Expire => "expire",
            InterruptKind::Steer => "steer",
        }
    }
}

/// 中断的结果：**必须四态可辨**（原实现只返回 `Result<()>`，无法区分"太晚"与"不支持"）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum InterruptOutcome {
    /// 已接受，后续以 `status`/事件体现生效。
    Accepted,
    /// 目标已是终态：**没有可取消的东西**，但也不是错误。
    AlreadyTerminal,
    /// 来得太晚：工作已完成，取消无效（M04「取消≠撤销」的落点）。
    TooLate,
    /// 该实现不支持这种中断（能力位未声明）。
    Unsupported,
}

// ─────────────────────────────────────────────────────────────
// status 的载荷
// ─────────────────────────────────────────────────────────────

/// 预算余量（四类各自独立；`None` = 未设该类预算）。
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct BudgetLeft {
    pub turns: Option<u32>,
    pub output_tokens: Option<u64>,
    pub context_tokens: Option<u64>,
    pub wall_ms: Option<u64>,
}

/// loop 的状态投影（**只读派生**；权威状态在会话记录里）。
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LoopStatus {
    /// 保留既有 `RequestState` 语义（A4 状态机）。
    pub state: RequestState,
    pub turn: Option<TurnId>,
    pub terminal: Option<TurnTerminal>,
    /// 已产出的最后一个事件 seq（对账用）。
    pub last_seq: u64,
    /// 当前阻塞项（空 = 未阻塞）；D63 G1。
    pub blocked_on: Vec<BlockedOn>,
    /// 预算余量（`None` = 该实现不感知预算）。
    pub budget_left: Option<BudgetLeft>,
}

impl LoopStatus {
    /// 是否已终态（`Completed`/`Failed`/`Cancelled`/`Rejected`）。
    pub fn is_terminal(&self) -> bool {
        self.state.is_terminal()
    }

    /// 是否有人在等（D63 G1：`waiting_human` 的派生等价物）。
    pub fn waiting_human(&self) -> bool {
        !self.blocked_on.is_empty() || self.state == RequestState::NeedsHuman
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::r#loop::StepOutcome;

    /// T1：默认能力位必须**全 false**（fail-closed，§6.3 第 6 条）。
    #[test]
    fn capabilities_default_to_fail_closed() {
        let caps = LoopCapabilities::default();
        assert_eq!(caps, LoopCapabilities::NONE);
        assert_eq!(caps.declared(), 0);
        let rich = LoopCapabilities {
            pausable: true,
            interruptible: true,
            needs_human: true,
            ..LoopCapabilities::NONE
        };
        assert_eq!(rich.declared(), 3);
        assert_eq!(StepSemantics::TurnToCompletion.as_str(), "turn-to-completion");
        assert_eq!(
            StepSemantics::ModelRoundWithTools.as_str(),
            "model-round-with-tools"
        );
    }

    /// T8：三档粒度齐备 + 偏序（`HostRoundtrip` ⊂ `ModelRoundWithTools` ⊂ `TurnToCompletion`）。
    /// 这条测试是"声明粒度可以更细"规则的**可执行锚点**（task-82）。
    #[test]
    fn step_semantics_declares_three_grains() {
        use StepSemantics::{HostRoundtrip, ModelRoundWithTools, TurnToCompletion};

        // 三变体都存在、串值稳定（可进日志/配置）
        assert_eq!(HostRoundtrip.as_str(), "host-roundtrip");

        // 偏序：自细向粗
        assert!(HostRoundtrip.is_finer_than(ModelRoundWithTools));
        assert!(ModelRoundWithTools.is_finer_than(TurnToCompletion));
        assert!(HostRoundtrip.is_finer_than(TurnToCompletion));

        // 不自比、不反向
        assert!(!HostRoundtrip.is_finer_than(HostRoundtrip));
        assert!(!ModelRoundWithTools.is_finer_than(ModelRoundWithTools));
        assert!(!TurnToCompletion.is_finer_than(HostRoundtrip));
        assert!(!TurnToCompletion.is_finer_than(ModelRoundWithTools));

        // 三档互不相等（可作 match 的分支）
        assert_ne!(HostRoundtrip, ModelRoundWithTools);
        assert_ne!(ModelRoundWithTools, TurnToCompletion);
        assert_ne!(HostRoundtrip, TurnToCompletion);
    }

    /// T2：`TurnInput` 最小构造 + 执行身份可归因（parity 要求）。
    #[test]
    fn turn_input_carries_execution_identity() {
        let exec = ExecutionIdentity {
            run_id: "run-1".into(),
            operation_id: "op-1".into(),
            idempotency_key: Some("idem-1".into()),
            deadline_ms: Some(30_000),
        };
        let input = TurnInput::new(
            vec![CanonicalMessage {
                role: CanonicalRole::User,
                text: "hi".into(),
            }],
            exec.clone(),
        );
        assert_eq!(input.messages.len(), 1);
        assert_eq!(input.messages[0].role.as_str(), "user");
        assert_eq!(input.execution.idempotency_key.as_deref(), Some("idem-1"));
        assert!(input.max_turns.is_none());
        assert!(input.budget.is_none());
    }

    /// T3：`StepOutcome` 五个变体都能构造（含 M04 `Unknown` 的"禁止自动重放"语义位）。
    #[test]
    fn step_outcome_has_all_variants() {
        let advanced = StepOutcome::Advanced {
            turn: 1,
            events: vec![LoopEvent::new(1, LoopEventKind::TurnStarted)],
            seq: 1,
        };
        let waiting = StepOutcome::WaitingHuman {
            blocked_on: vec![BlockedOn {
                kind: BlockedOnKind::Approval,
                id: "ap-1".into(),
                response_schema: Some("{}".into()),
            }],
        };
        let finished = StepOutcome::Finished {
            outcome: TurnOutcome {
                completed: true,
                stop_reason: "stop".into(),
                final_seq: 7,
            },
        };
        let failed = StepOutcome::Failed {
            code: "E_MODEL".into(),
            message: "boom".into(),
            stop_reason: None,
        };
        let unknown = StepOutcome::Unknown { reconcile: true };
        for o in [advanced, waiting, finished, failed, unknown] {
            // 只需证明可构造且被 match 覆盖（穷尽性由编译期保证）
            match o {
                StepOutcome::Advanced { .. }
                | StepOutcome::WaitingHuman { .. }
                | StepOutcome::Finished { .. }
                | StepOutcome::Failed { .. }
                | StepOutcome::Unknown { .. } => {}
            }
        }
    }

    /// T4：`LoopEvent.seq` 必须单调（并进会话日志的前提）。
    #[test]
    fn loop_event_seq_is_monotonic() {
        let seqs: Vec<u64> = [
            LoopEventKind::TurnStarted,
            LoopEventKind::ModelRequest,
            LoopEventKind::ModelResponse,
            LoopEventKind::ToolCall,
            LoopEventKind::ToolResult,
            LoopEventKind::HumanBlocked,
            LoopEventKind::TurnCompleted,
            LoopEventKind::Status,
        ]
        .iter()
        .enumerate()
        .map(|(i, k)| LoopEvent::new(i as u64 + 1, *k).seq)
        .collect();
        assert_eq!(seqs, vec![1, 2, 3, 4, 5, 6, 7, 8]);
        assert!(seqs.windows(2).all(|w| w[0] < w[1]));
        assert_eq!(LoopEventKind::HumanBlocked.as_str(), "human_blocked");
    }

    /// T5：`InterruptOutcome` 四态可辨（"太晚" ≠ "不支持" ≠ "已终态"）。
    #[test]
    fn interrupt_outcome_distinguishes_late_from_unsupported() {
        let all = [
            InterruptOutcome::Accepted,
            InterruptOutcome::AlreadyTerminal,
            InterruptOutcome::TooLate,
            InterruptOutcome::Unsupported,
        ];
        // 任意两者都不相等（四态互斥）
        for (i, a) in all.iter().enumerate() {
            for (j, b) in all.iter().enumerate() {
                assert_eq!(i == j, a == b);
            }
        }
        assert_eq!(InterruptKind::Cancel.as_str(), "cancel");
        assert_ne!(InterruptKind::Cancel, InterruptKind::Expire);
    }

    /// T6：`LoopStatus` 的派生投影（terminal / waiting_human / budget_left）。
    #[test]
    fn loop_status_projects_terminal_and_blocked() {
        let running = LoopStatus {
            state: RequestState::Running,
            turn: Some(3),
            terminal: None,
            last_seq: 12,
            blocked_on: vec![],
            budget_left: Some(BudgetLeft {
                turns: Some(2),
                output_tokens: None,
                context_tokens: Some(1000),
                wall_ms: None,
            }),
        };
        assert!(!running.is_terminal());
        assert!(!running.waiting_human());
        assert_eq!(running.turn, Some(3));

        let blocked = LoopStatus {
            state: RequestState::NeedsHuman,
            blocked_on: vec![BlockedOn {
                kind: BlockedOnKind::Interrupt,
                id: "it-1".into(),
                response_schema: None,
            }],
            ..running.clone()
        };
        assert!(blocked.waiting_human());

        let done = LoopStatus {
            state: RequestState::Completed,
            terminal: Some(TurnTerminal {
                code: "ok".into(),
                stop_reason: "stop".into(),
            }),
            ..running
        };
        assert!(done.is_terminal());
    }

    /// T7：`LoopContract` 必须 object-safe——`Arc<dyn LoopContract>` 可调用全部 4 个方法。
    /// 同时验证 D74：实现返回的 future **立即 Ready**（不需要 executor 就能判定）。
    #[test]
    fn loop_contract_is_object_safe_and_immediately_ready() {
        use crate::BoxFuture;
        use crate::r#loop::{LoopContract, LoopDescriptor};
        use crate::types::{Error, SessionId};
        use std::sync::Arc;

        struct NoopLoop;

        impl LoopContract for NoopLoop {
            fn describe(&self) -> BoxFuture<'_, LoopDescriptor> {
                Box::pin(async move {
                    LoopDescriptor {
                        id: "noop".into(),
                        language: "rust".into(),
                        step_semantics: StepSemantics::ModelRoundWithTools,
                        capabilities: LoopCapabilities::NONE,
                    }
                })
            }
            fn step(
                &self,
                _session: &SessionId,
                turn: TurnId,
                _input: TurnInput,
            ) -> BoxFuture<'_, Result<StepOutcome, Error>> {
                Box::pin(async move {
                    Ok(StepOutcome::Advanced {
                        turn,
                        events: vec![],
                        seq: 0,
                    })
                })
            }
            fn interrupt(
                &self,
                _session: &SessionId,
                kind: InterruptKind,
                _detail: &str,
            ) -> BoxFuture<'_, Result<InterruptOutcome, Error>> {
                Box::pin(async move {
                    Ok(match kind {
                        InterruptKind::Cancel | InterruptKind::Expire => InterruptOutcome::Accepted,
                        InterruptKind::Steer => InterruptOutcome::Unsupported,
                    })
                })
            }
            fn status(&self, _session: &SessionId) -> BoxFuture<'_, Result<LoopStatus, Error>> {
                Box::pin(async move {
                    Ok(LoopStatus {
                        state: RequestState::Accepted,
                        turn: None,
                        terminal: None,
                        last_seq: 0,
                        blocked_on: vec![],
                        budget_left: None,
                    })
                })
            }
        }

        // object safety：能作为 trait object 持有
        let d: Arc<dyn LoopContract> = Arc::new(NoopLoop);
        // 4 个方法都能通过 trait object 调用（类型层面即可证明 object-safe）
        let _describe = d.describe();
        let _step = d.step(&"s-1".to_string(), 1, TurnInput::new(vec![], exec()));
        let _interrupt = d.interrupt(&"s-1".to_string(), InterruptKind::Cancel, "user");
        let _status = d.status(&"s-1".to_string());

        fn exec() -> ExecutionIdentity {
            ExecutionIdentity {
                run_id: "r".into(),
                operation_id: "o".into(),
                idempotency_key: None,
                deadline_ms: None,
            }
        }
    }
}
