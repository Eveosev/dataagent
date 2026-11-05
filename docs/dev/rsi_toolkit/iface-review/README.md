# IFace 模块化方案入口

当前推荐使用 **v2 修订方案**，已纳入 2026-10-28 的源码、Mint 探针及相关 session 审阅结果：

- [新版设计](../../../superpowers/specs/2026-10-28-rsi-iface-v2-design.md)：架构、兼容策略、契约声明、分发路线、M0-pre 到 M6 的门禁。
- [首批实施计划](../../../superpowers/plans/2026-10-28-rsi-iface-v2-m0-m1.md)：M0-pre、M0、M1 的任务、文件、接口、测试、依赖与验收。
- [包使用文档与测试用例](../../../superpowers/specs/2026-10-28-rsi-package-pages-and-tests.md)：5 包 README 初稿、宿主要求、49 条用例、报告与文档命令校验。
- [workspace 直接 cpmrt 测试指南](../../../../workspace/rsi-iface-v2-cpmrt/final-source-retry2/README.md)：保留安装、调用、实际技能读取、12 项检查及证据。
- [历史两方案评审](../2026-10-28-iface-plans-review.md)：保留原始分析和核验证据。

v2 替代附录 A、C、E、E1、E2 中冲突的执行决策。附录 B 的 C1-C7 继续作为契约需求输入；附录 D 是历史证据，不替代新制品验收。

**2026-10-29 上游复核**：[附录 F](F-upstream-delta-2026-10-29.md)（拉取 kernel master `d950766`，对照 cpmrt 0.1.14）。要点：C1–C7 没有一条被上游完整满足；`runtime-executor` / `execution_id` 在上游**不存在**（最接近的是 `LoopContract.ExecutionIdentity` 与 `ModelSession.client_message_id`）；C6 应并入 `iface-env` 而不是新契约；C2 应改为“在 `MemoryProvider` 上加快照”；hub 上的 `agentcpm/iface-*@0.1.0` 已落后 master，不能再当权威来源。同日 `packages/kernel-iface/` 已按 master 同步为 22 个 trait（`kind` 改为 `bundle`），比线上制品新。

**2026-10-29 对外版本**：[B 修订版](B-revised-2026-10-29.md) 把 B 的架构与 F 的结论合并成一份可直接沟通的文档，已发布到飞书
<https://modelbest.feishu.cn/docx/GNDkdtF2goAAopx8Nxtc2ylGnKb>（仓库内同名文件是源稿，改完需重新上传）。

2026-10-28 更新：M0-pre/M0/M1 实现及 G4-W 已独立审阅通过；G5 执行检查和最终全分支审阅已通过。活动分支 `codex/rsi-iface-v2-cpmrt`，实际源码 `d7c84f3`，证据 `ba9a23c`。入口见
[`ACCEPTANCE.md`](../../../../.worktrees/rsi-iface-v2-cpmrt/conformance/iface-v2/ACCEPTANCE.md)
和 [`workspace-report.md`](../../../../.worktrees/rsi-iface-v2-cpmrt/conformance/iface-v2/workspace-report.md)。
G4-W 的 12 项检查全部通过；49 条正式用例为 45 通过 + ID-02 blocked + 3 条 source-only。
Mint 管理包，实际直接执行专用 home 的 cpmrt0.1.14/core；公开 std 制品实为 core，std 仍 blocked。M6 ACP 适配器未实现，不声明 MintHub 发布或学习收益。
