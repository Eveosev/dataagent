//! lineage: agent-kernel:notes/kernel-rust-agent-doc-alignment-20261026.md:§2.1 (B, CallEffect 三级对齐)
//! lineage: agent-kernel:kernel/iface/src/session.rs:1 (A, Session v2 · V0 纯类型)
//!
//! **操作的副作用等级**（`EffectLevel`）——来自《Rust Agent 框架架构设计 V0.1》的 `CallEffect` 三级的对齐结论
//! （见 `notes/kernel-rust-agent-doc-alignment-20261026.md` §2.1）。
//!
//! 三级含义（写死，不得含糊）：
//!
//! | 级别 | 含义 | 重放规则 |
//! |---|---|---|
//! | [`EffectLevel::ReadOnly`] | **不改变任何状态**（纯读） | 可安全重试/重放 |
//! | [`EffectLevel::Advance`] | **只改变本会话状态**（不产生外部副作用） | 会话日志确认后才可重放（避免重复推进） |
//! | [`EffectLevel::SideEffect`] | **产生外部副作用**（写文件/发请求/起进程…） | **未收到确认不得重放** |
//!
//! 为什么"SideEffect 未确认不得重放"：外部世界已经可能被改变，重放会产生**重复副作用**；
//! 这与三条既有语义对齐：M04「取消 ≠ 撤销」（已发生的外部操作不能因取消被描述成撤销）、
//! M28 epoch 围栏（旧持有者不得继续写）、delivery 幂等（同内容不重复投递）。
//!
//! # 为什么这样映射（op 分类 → 等级）
//! - `tool.execute` → `SideEffect`：工具可能写文件/发网络请求（外部副作用）；
//! - `model.stream` → `SideEffect`：**启动一次模型推理**（消耗额度、占用并发、可能产生外部调用），
//!   与 `model.request` 同属"开始执行"；不因"输出是流式读"而降级为只读（D94 修正）；
//! - `store.set` → `Advance`：只改本会话存储，不触达外部世界；
//! - `store.get` → `ReadOnly`；
//! - `env.exec` → `SideEffect`：起进程/远端执行（外部副作用）；
//! - `session.advance` → `Advance`：推进会话本身（只改本会话状态）；
//! - `session.read` → `ReadOnly`。
//!
//! **未知 op 一律按 `SideEffect` 处理**（[`effect_for_op`]）：最严格的等级，避免"漏配即放行"。

use std::fmt;

/// 操作副作用等级（`CallEffect` 三级对齐）。
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
#[non_exhaustive]
pub enum EffectLevel {
    /// 不改变任何状态。
    ReadOnly,
    /// 只改变本会话状态（无外部副作用）。
    Advance,
    /// 产生外部副作用。
    SideEffect,
}

impl EffectLevel {
    pub fn as_str(self) -> &'static str {
        match self {
            EffectLevel::ReadOnly => "read-only",
            EffectLevel::Advance => "advance",
            EffectLevel::SideEffect => "side-effect",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        Some(match raw {
            "read-only" => EffectLevel::ReadOnly,
            "advance" => EffectLevel::Advance,
            "side-effect" => EffectLevel::SideEffect,
            _ => return None,
        })
    }

    /// 未收到确认时是否允许重放（**只有 `ReadOnly` 允许**）。
    pub fn may_replay_unconfirmed(self) -> bool {
        matches!(self, EffectLevel::ReadOnly)
    }

    /// 是否必须在重放前拿到确认（`SideEffect` 必须；`Advance` 需日志确认，见 [`Self::requires_ack_before_replay`] 说明）。
    pub fn requires_ack_before_replay(self) -> bool {
        matches!(self, EffectLevel::SideEffect)
    }

    /// 按 op 分类查表（未配置 → `None`；保守调用方应使用 [`effect_for_op`]）。
    pub fn from_op_class(op_class: &str) -> Option<Self> {
        OP_EFFECT_MAP
            .iter()
            .find(|(name, _)| *name == op_class)
            .map(|(_, level)| *level)
    }
}

impl fmt::Display for EffectLevel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

/// **op 分类 → 副作用等级**映射表（`(op, level)`；**按名精确匹配，不做前缀匹配**）。
///
/// 查找语义（[`EffectLevel::from_op_class`]）：对 `op_class` 做**全等比较**，因此
/// `session.get` 不会命中 `session.getX` / `session.ge` / `session` / `session.`；
/// 反过来 `session.` 这样的前缀也不会"顺带"命中本表条目。表内顺序不影响结果
/// （线性查找，键唯一由测试保证）。
///
/// 新增 op 时：优先映射到**更严格**的等级；确实无法判定就映射为 `SideEffect`（fail-closed）。
/// **新增条目必须同时补测试**：登记值正确 / 未登记仍 fallback / 键唯一 / 精确匹配不被前缀误配。
pub const OP_EFFECT_MAP: &[(&str, EffectLevel)] = &[
    // —— 早期通用 op 分类（M34 宿主能力面）——
    ("tool.execute", EffectLevel::SideEffect),
    // D90：L-C 工具执行方法（v2b-2）。执行可能改文件/进程/网络 → SideEffect（禁止未确认重放）。
    ("tool.exec", EffectLevel::SideEffect),
    // D94：启动一次模型推理（消耗额度/占用并发、可能产生外部调用）→ SideEffect。
    ("model.stream", EffectLevel::SideEffect),
    // D96/F09：`model.request` 同样**启动推理**（入队真实执行、消耗预算），ReadOnly 与事实不符。
    // 兼容影响：分类修正本身不改线协议；幂等键强制留待迁移窗口（见 D96 §兼容）。
    ("model.request", EffectLevel::SideEffect),
    ("store.set", EffectLevel::Advance),
    ("store.get", EffectLevel::ReadOnly),
    ("env.exec", EffectLevel::SideEffect),
    ("session.advance", EffectLevel::Advance),
    ("session.read", EffectLevel::ReadOnly),
    // —— V1 资源面方法名（`e6f7066`）；登记后本表为权威，host 过渡分类表可后续移除 ——
    // 只读：读投影 / 长轮询（长轮询也只是读，不改变任何状态）。
    ("session.get", EffectLevel::ReadOnly),
    ("session.watch", EffectLevel::ReadOnly),
    ("operation.get", EffectLevel::ReadOnly),
    ("operation.watch", EffectLevel::ReadOnly),
    ("interrupt.get", EffectLevel::ReadOnly),
    // 只推进本会话状态、无外部副作用。
    ("session.create", EffectLevel::Advance),
    ("session.close", EffectLevel::Advance),
    ("interrupt.submit", EffectLevel::Advance),
    // 投递是**外部可见**副作用（V1 的 G2 resume 入口：`correlation_id` 会触发对端续跑），
    // 与 host `V1_METHOD_DECLS`（`requires_ack: true`）及 v2b 设计表的 `S` 一致：
    // 未确认不得重放、需 idempotency_key。
    ("session.deliver", EffectLevel::SideEffect),
    // 显式**不登记**、靠 fallback SideEffect 保守处理的（等 V2 定案）：
    // `env.*`、`tool.*`（外部副作用）、`session.lease_*`、`session.handoff_*`（跨宿主夺权/迁移）。
];

/// 查 op 的副作用等级；**未配置的 op 按 `SideEffect`**（fail-closed：宁严不宽）。
pub fn effect_for_op(op_class: &str) -> EffectLevel {
    EffectLevel::from_op_class(op_class).unwrap_or(EffectLevel::SideEffect)
}

#[cfg(test)]
mod tests {
    use super::{EffectLevel, OP_EFFECT_MAP, effect_for_op};

    #[test]
    fn op_mapping_is_conservative_and_ordered() {
        assert_eq!(
            EffectLevel::from_op_class("tool.execute"),
            Some(EffectLevel::SideEffect)
        );
        assert_eq!(
            EffectLevel::from_op_class("tool.exec"),
            Some(EffectLevel::SideEffect)
        );
        assert_eq!(
            EffectLevel::from_op_class("model.stream"),
            Some(EffectLevel::SideEffect)
        );
        assert_eq!(
            EffectLevel::from_op_class("model.request"),
            Some(EffectLevel::SideEffect),
            "D96/F09：model.request 启动推理，必须 SideEffect"
        );
        assert_eq!(
            EffectLevel::from_op_class("store.set"),
            Some(EffectLevel::Advance)
        );
        assert_eq!(
            EffectLevel::from_op_class("store.get"),
            Some(EffectLevel::ReadOnly)
        );
        // 未知 op → 显式 None；保守入口按 SideEffect。
        assert_eq!(EffectLevel::from_op_class("mystery.op"), None);
        assert_eq!(effect_for_op("mystery.op"), EffectLevel::SideEffect);
        // 映射表无重复 key。
        let mut names: Vec<&str> = OP_EFFECT_MAP.iter().map(|(name, _)| *name).collect();
        names.sort_unstable();
        let total = names.len();
        names.dedup();
        assert_eq!(names.len(), total, "op 映射表存在重复 key");
        // 等级有序：ReadOnly < Advance < SideEffect（可用作"取更严"）。
        assert!(EffectLevel::ReadOnly < EffectLevel::Advance);
        assert!(EffectLevel::Advance < EffectLevel::SideEffect);
    }

    /// V1（`e6f7066`）新增的资源面方法名必须能直接查表得到期望等级。
    ///
    /// 否则 host 过渡分类表一旦移除/漏配，读操作会 fallback 成 SideEffect（被要求幂等键、拒绝重放）。
    #[test]
    fn v1_resource_ops_are_registered_with_expected_effect() {
        // 只读（含长轮询：watch 只是读）。
        for op in [
            "session.get",
            "session.watch",
            "operation.get",
            "operation.watch",
            "interrupt.get",
        ] {
            assert_eq!(
                EffectLevel::from_op_class(op),
                Some(EffectLevel::ReadOnly),
                "{op} 应为 ReadOnly"
            );
            assert_eq!(effect_for_op(op), EffectLevel::ReadOnly);
            assert!(
                effect_for_op(op).may_replay_unconfirmed(),
                "{op} 应允许未确认重放"
            );
        }
        // 只推进本会话状态、无外部副作用。
        for op in ["session.create", "session.close", "interrupt.submit"] {
            assert_eq!(
                EffectLevel::from_op_class(op),
                Some(EffectLevel::Advance),
                "{op} 应为 Advance"
            );
            assert!(
                !effect_for_op(op).requires_ack_before_replay(),
                "{op} 不应要求 ack"
            );
        }
        // 投递是外部可见副作用（与 host V1 表 / v2b 设计表一致）。
        assert_eq!(
            EffectLevel::from_op_class("session.deliver"),
            Some(EffectLevel::SideEffect),
            "session.deliver 取 SideEffect（G2 resume 会触发对端续跑）"
        );
        assert!(effect_for_op("session.deliver").requires_ack_before_replay());
    }

    /// 未登记的跨宿主/外部副作用方法必须继续 fallback 到最严格等级（fail-closed）。
    #[test]
    fn unregistered_v2_ops_fall_back_to_side_effect() {
        for op in [
            "env.request",
            "env.reconcile",
            "tool.authorize",
            "tool.register",
            "session.lease_acquire",
            "session.lease_renew",
            "session.lease_release",
            "session.handoff_prepare",
            "session.handoff_commit",
            "session.handoff_abort",
        ] {
            assert_eq!(
                EffectLevel::from_op_class(op),
                None,
                "{op} 不应登记（跨宿主/外部影响，保守走 fallback）"
            );
            assert_eq!(
                effect_for_op(op),
                EffectLevel::SideEffect,
                "{op} 必须 fallback 为 SideEffect"
            );
        }
    }

    /// 查找是**精确匹配**：前缀相似的名字不能被误配（否则读操作会拿到错等级）。
    #[test]
    fn op_lookup_is_exact_not_prefix_matched() {
        // 已登记名 → 命中。
        assert_eq!(
            EffectLevel::from_op_class("session.get"),
            Some(EffectLevel::ReadOnly)
        );
        // 只是前缀相同/后缀相似的名字 → 不得命中。
        for op in [
            "session.getX",
            "session.ge",
            "session.get.all",
            "session.",
            "session",
            "operation",
            "operation.getX",
            "interrupt.gett",
            "session.create2",
        ] {
            assert_eq!(
                EffectLevel::from_op_class(op),
                None,
                "{op} 不得被前缀/子串误配为已登记 op"
            );
            assert_eq!(
                effect_for_op(op),
                EffectLevel::SideEffect,
                "{op} 未登记时必须 fallback SideEffect"
            );
        }
    }

    /// 新增条目后表仍无重复键（重复会掩盖优先级问题，且让查找结果依赖顺序）。
    #[test]
    fn registry_has_no_duplicate_keys() {
        let mut names: Vec<&str> = OP_EFFECT_MAP.iter().map(|(name, _)| *name).collect();
        let total = names.len();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), total, "OP_EFFECT_MAP 存在重复 key");
        assert!(total >= 16, "V1 登记后条目数应 ≥16，实际 {total}");
    }
}
