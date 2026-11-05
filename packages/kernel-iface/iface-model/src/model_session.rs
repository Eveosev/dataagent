//! D96（additive）：**模型会话契约**（持续输入、持续输出、独立控制、可验证配置）。
//!
//! 职责：定义模型交互的**共同契约**（三对象、两模式、能力声明、输入信封、事件类别、两端接口）；
//! 不负责：具体模型协议/厂商映射（实现在 runtime 等包）、宿主调度与权限（在 host）。
//!
//! 与既有契约的关系（全部 additive，旧实现零改动）：
//! - `ModelContract` / `ModelStreamContract`（D93/D94）保留为 **request 模式兼容适配器**；
//! - 本模块新增 [`ModelSessionFactory`] / [`ModelSession`] 两个 trait（若实现不提供 duplex 能力，
//!   **必须**在 [`SessionCapabilities`] 里显式声明 false，不能静默假装支持）；
//! - 旧路径（`model.request`/`model.stream`/旧 view）继续可用，但**必须与新的模型会话共用**
//!   授权、调度、预算与执行记录（规范 §6.1.3；不得出现第二套模型执行系统）。
//!
//! 终止事件必须五类分明（规范 §6.1.3）：媒体片段结束 / 回答完成 / 回答被打断 / 模型会话关闭 /
//! 订阅连接结束——见 [`EndKind`]，禁止互相冒充。
//!
//! lineage: agent-kernel:notes/kernel-model-session-execution-plan-20261028.md:1 (D96, 2026-10-28)

mod capabilities;
mod config;
mod event;
mod input;
mod operations;
mod types;

pub use capabilities::{CapabilityField, SessionCapabilities};
pub use config::{
    GenerationSettings, MediaFormat, ModelBinding, ModelSessionConfig, SessionLimits, SessionTimeouts,
};
pub use event::{BackendStopStatus, EndKind, EventKind, ModelSessionEvent, SessionTerminal};
pub use input::{
    ConsumptionStatus, InputAccepted, InputEnvelope, InputKind, InputStatus, ToolResultEnvelope,
};
pub use operations::{ConfigUpdate, InterruptAck, ModelSession, ModelSessionFactory, OpenAck, SessionState};
pub use types::{ConfigRevision, InputId, ModelSessionId, ResponseId, SessionMode};

#[cfg(test)]
mod tests {
    use super::event::{BackendStopStatus, SessionTerminal};
    use super::*;

    #[test]
    fn end_kinds_are_distinct_and_exhaustive_for_terminals() {
        // 五类终止各自映射到不同分类（禁止互相冒充）。
        let kinds = [
            EventKind::MediaSegmentEnd { media_seq: 7 },
            EventKind::ResponseCompleted,
            EventKind::ResponseInterrupted {
                delivery_stopped: true,
                backend_stop: BackendStopStatus::Unknown,
            },
            EventKind::SessionClosed {
                terminal: SessionTerminal::Closed,
            },
            EventKind::SubscriptionClosed,
        ];
        let ends: Vec<EndKind> = kinds.iter().filter_map(EventKind::end_kind).collect();
        assert_eq!(
            ends,
            vec![
                EndKind::MediaSegment,
                EndKind::ResponseCompleted,
                EndKind::ResponseInterrupted,
                EndKind::ModelSessionClosed,
                EndKind::SubscriptionClosed,
            ]
        );
        // 非终止事件不得被判为终止。
        assert_eq!(EventKind::SessionReady.end_kind(), None);
        assert_eq!(EventKind::ResponseStarted.end_kind(), None);
        assert_eq!(
            EventKind::Usage {
                usage_json: "{}".into(),
                estimated: true
            }
            .end_kind(),
            None
        );
        // 会话失败也算模型会话关闭（但语义由 SessionClosed/SessionFailed 区分）。
        assert_eq!(
            EventKind::SessionFailed {
                reason: "boom".into(),
                resource_released: false
            }
            .end_kind(),
            Some(EndKind::ModelSessionClosed)
        );
    }

    #[test]
    fn capabilities_are_fail_closed_by_default() {
        let caps = SessionCapabilities::default();
        for field in [
            CapabilityField::Completion,
            CapabilityField::StreamingOutput,
            CapabilityField::DuplexInput,
            CapabilityField::ToolCalls,
            CapabilityField::ToolResultStreaming,
            CapabilityField::InputConsumptionAck,
            CapabilityField::MediaInput,
            CapabilityField::MediaOutput,
            CapabilityField::ConfigHotUpdate,
            CapabilityField::InterruptBackendStop,
            CapabilityField::StateRecovery,
        ] {
            assert!(!caps.supports(field), "默认必须 fail-closed：{field:?}");
        }
        // 只有显式声明才 true（热更 = 非空字段列表）。
        let declared = SessionCapabilities {
            completion: true,
            streaming_output: true,
            duplex_input: true,
            config_hot_update_fields: vec!["generation.max_tokens".into()],
            ..SessionCapabilities::default()
        };
        assert!(declared.supports(CapabilityField::Completion));
        assert!(declared.supports(CapabilityField::DuplexInput));
        assert!(declared.supports(CapabilityField::ConfigHotUpdate));
        assert!(
            !declared.supports(CapabilityField::StateRecovery),
            "未实现恢复必须 false"
        );
    }

    #[test]
    fn default_limits_match_spec_6_2() {
        let limits = SessionLimits::default();
        assert_eq!(limits.control_queue_items, 32);
        assert_eq!(limits.control_queue_bytes, 256 * 1024);
        assert_eq!(limits.reliable_input_items, 64);
        assert_eq!(limits.reliable_input_bytes, 4 * 1024 * 1024);
        assert_eq!(limits.inline_block_bytes, 64 * 1024);
        assert_eq!(limits.output_record_bytes, 64 * 1024 * 1024);
    }
}
