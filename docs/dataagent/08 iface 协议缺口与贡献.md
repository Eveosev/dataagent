---
doc_id: iface-contrib
title: 08 iface 协议缺口与贡献
answers: DataAgent 用到的 iface 协议哪里不够；哪些我们可以贡献、贡献什么、找谁
status: 草稿 v0.1（2026-11-18；条目以飞书「iface 贡献清单」表为准）
feishu_node: RW30wDtqsi8WM0ksq1Wc3hG8nuf
feishu_obj: FFAcdsj2jo3H9HxP6rDcPGzqneg
---
# 08 iface 协议缺口与贡献

> 基线：agent-kernel@ae6c3d5（2026-11-17）；DataAgent feat/p1-intake@9c4c941。依据 [01 多源接入与本体的 iface 依赖与分工](<01 多源接入与本体的 iface 依赖与分工.md>)、[03 平台方案与 iface 共建](<03 平台方案与 iface 共建.md>) 和盘点材料 `iface-对齐盘点-2026-11-17.md`。
> 条目的源是飞书工作表「iface 贡献清单」（工作表链接见文档集首页）；本篇只讲怎么读、怎么维护，下面的列表是 11-18 的快照。

## 1 为什么单独维护

1. DataAgent 团队同时是 iface 的开发者：发现协议不够时，除了「提需求」，也可以直接贡献契约草案或参考实现。
2. 03 的 PR-1 至 PR-8 是「P1 要什么」的视角，且 P1 已拍不提 PR（03 的 Q5）；本篇换成「iface 缺什么、我们能补什么」的视角，覆盖 P1 到 P6，供 payne 与 iface 负责人逐条沟通。
3. 贡献什么、谁来做，由 payne 与 iface 负责人沟通后定；本篇和表只负责把缺口、证据、建议形状列清楚。

## 2 怎么读这张表

| 列 | 含义 |
|---|---|
| 类别 | iface 契约缺口（改 `kernel/iface/src` 或身份包）；Kernel 实现（契约够，宿主没实现或没接线）；Mint 实现（Mint 加载器、GUI 的问题）；DataAgent 可回馈实现（我们已有、可作参考实现的部分） |
| 需要的阶段 | DataAgent 哪一期开始依赖它（P1 到 P6，见 [05](<05 分期路线与 MVP 范围.md>)） |
| 贡献方式 | 提需求、契约 PR（改契约）、实现 PR（改宿主实现）、参考实现（我们的代码作为样板）、缺陷报告 |
| 优先级 | P0 卡 P1 验收或设计；P1 在 P2–P3 用到；P2 在 P5–P6 用到 |
| 状态 | 待沟通 → 沟通中 → 已认领 → 已提交 → 已合入，或「不做」（写明原因） |
| 沟通记录 | 每次沟通后追加：日期、对象、结论 |

## 3 概览（快照）

| 编号 | 缺口 | 类别 | 模块 | 阶段 | 方式 | 优先级 | 对接 |
|---|---|---|---|---|---|---|---|
| IF-01 | 工具效果分级 | iface 契约缺口 | tool / policy | P1 | 契约 PR | P0 | 李奕杉（tool）、李鹏越（policy）；评审 pengyue.li、luyaxi |
| IF-02 | 调用元数据下发给 MCP 组件的线上约定 | iface 契约缺口 | types | P1 | 契约 PR | P0 | 李奕杉；评审 luyaxi |
| IF-03 | 会话身份（主体、租户）投影给组件 | iface 契约缺口 | session · identity | P3 | 契约 PR | P1 | 彭淳毅；评审 pengyue.li |
| IF-04 | 组件进程凭据注入的用途域 | iface 契约缺口 | policy · secret | P1 | 提需求 | P0 | 李鹏越 |
| IF-05 | 后台任务：会话外寿命与定时、变更触发 | iface 契约缺口 | scheduler_protocol | P5 | 契约 PR | P1 | pengyue.li |
| IF-06 | 进程外组件注册为调度服务 | Kernel 实现 | scheduler_protocol / extension | P3 | 实现 PR | P1 | pengyue.li；Mint 清单找 Mint 负责人 |
| IF-07 | Scheduler 生产装配接线断开 | Kernel 实现 | scheduler（host） | P3 | 缺陷报告 | P1 | pengyue.li |
| IF-08 | 组件把后台结果推回会话 | iface 契约缺口 | session · inbox | P3 | 契约 PR | P1 | 彭淳毅；Mint 负责人 |
| IF-09 | 工具中途向人要输入 | iface 契约缺口 | policy · human | P2 | 提需求 | P1 | 李鹏越 |
| IF-10 | 组件事件追加与命名空间 | iface 契约缺口 | store | P3 | 契约 PR | P1 | 郑达奇、魏耀全；评审 luyaxi |
| IF-11 | 模型端点本机 / 远端标记 | iface 契约缺口 | model | P3 | 契约 PR | P1 | 魏耀全；评审 pengyue.li |
| IF-12 | 运行期按依赖名定位包、path 依赖发布 | iface 契约缺口 | extension | P6 | 提需求 | P2 | 李鹏越 |
| IF-13 | 打包桌面版不装配项目包的 MCP 工具 | Mint 实现 | Mint GUI（kernel-stdio-v1） | P1 | 提需求 | P0 | Mint GUI 负责人 |
| IF-14 | Mint GUI 项目模式启动问题 | Mint 实现 | Mint GUI | P1 | 缺陷报告 | P1 | Mint GUI 负责人 |
| IF-15 | 副作用台账与「结果未知只对账」 | DataAgent 可回馈实现 | session · effect | P6 | 参考实现 | P2 | 彭淳毅 |
| IF-16 | 出网判决与审计记录的组件侧实现 | DataAgent 可回馈实现 | policy · egress / audit | P3 | 参考实现 | P2 | 李鹏越 |
| IF-17 | 用户级 `approval_policy=never` + `full-access` 时，项目沙箱片段收紧到 `workspace-write` 后所有需审批工具被拒，`--approve all` 不覆盖 `never` | Mint 实现 | 审批策略 · `core.sandbox`（agent-kernel@8439ec8） | P1 | 缺陷报告 | P0 | Mint 负责人：`--approve all` 应把用户级 `never` 抬到 `on-request`，或提供项目级审批开关；复现：`mint config set core.approval_policy never` + `core.sandbox.policy full-access`，项目追加 preset-intake `sandbox.toml` 后 `mint run --approve all` 调 MCP 工具，全部 `tool/policy-denied … never`；临时做法见 mint-offline-quickstart §1.5/§2 |

先谈的三件：IF-01（工具效果分级，卡 G1.5）、IF-04（凭据注入用途域，卡 G1.6 的 GUI 部分）、IF-13（打包桌面版看不到 MCP 工具，卡 G1.4）。IF-05、IF-06、IF-07、IF-08 合成一次「后台任务」沟通。

## 4 条目详情（快照）

### IF-01 工具效果分级

1. 现状与证据：ToolSpec 只有名字、描述、参数（kernel/iface/src/tool.rs:35-39）；EffectLevel 三级已有但按 op 类别给值，tool.execute 一律算副作用（session/effect.rs:193、:256）
2. DataAgent 需要：只读工具免确认，默认审批下全流程人工确认不超过 3 次（G1.5、V1.5）（P1）
3. 建议贡献：ToolSpec 增加可选 Option<EffectLevel>（复用现有三级，不另造枚举）；PolicyContract::effect_of 对已声明工具读取它；约定 MCP readOnlyHint/destructiveHint/idempotentHint 到 EffectLevel 的映射。DataAgent 平台层 MCP 框架（T12a）可作参考实现
4. 方式与对接：契约 PR，李奕杉（tool）、李鹏越（policy）；评审 pengyue.li、luyaxi
5. 关联：03 PR-1；07 T40（暂缓）；盘点 C1

### IF-02 调用元数据下发给 MCP 组件的线上约定

1. 现状与证据：CallMeta{session_id, call_id, turn}（types/mod.rs:7-11）只在 Kernel 内；Mint 不把它下发给 MCP 服务；_meta 里用原名还是加前缀没有约定
2. DataAgent 需要：组件按调用上下文判定权限、留痕（G1.10，T11a 已按原名读取）（P1）
3. 建议贡献：写一份 MCP _meta 映射约定（键名、类型、缺省时行为），并在 Mint MCP 客户端下发；DataAgent 的 resolve_context() 可作消费方参考实现
4. 方式与对接：契约 PR，李奕杉；评审 luyaxi
5. 关联：03 PR-2；07 T41（暂缓）；盘点 C4

### IF-03 会话身份（主体、租户）投影给组件

1. 现状与证据：SessionIdentity 已有 principal、tenant_id（session/identity.rs:37-41），但组件拿不到；CallMeta 没有 #[non_exhaustive]，直接加字段是破坏性变更
2. DataAgent 需要：关闭主体自报（S0 评审 X1–X3），访问控制与多人协作（P3）
3. 建议贡献：定义会话身份的只读投影（SessionIdentityView），随 _meta 下发，不改 CallMeta；约定组件侧校验方式
4. 方式与对接：契约 PR，彭淳毅；评审 pengyue.li
5. 关联：03 PR-8；盘点 C3

### IF-04 组件进程凭据注入的用途域

1. 现状与证据：SecretPurpose 只有 EgressAuth、StateEncryption（policy/secret.rs:137-158），原则是值不出宿主（:161）；01 的 Q1 已拍「拉起 MCP 进程时注入明文」
2. DataAgent 需要：数据库、REST、远程 OCR 凭据只按逻辑名进子进程，不进对话、日志、结果（G1.6）（P1）
3. 建议贡献：二选一后落地：新增 SecretPurpose::ProcessEnv 一类用途域并登记打码规则；或明确只在 Mint MCP 加载器实现、不进契约。DataAgent T14 的逻辑名解析（env:/keychain:/file:）可作参考
4. 方式与对接：提需求，李鹏越
5. 关联：03 PR-3；07 T42（暂缓）、T14；盘点 C5

### IF-05 后台任务：会话外寿命与定时、变更触发

1. 现状与证据：Scheduler 契约有状态机、Wait、取消、幂等键、截止时间（scheduler_protocol/model.rs:31、:139、:234、:287）；会话关闭即取消执行树（kernel/docs/scheduler.md:34）；没有定时或变更触发
2. DataAgent 需要：持续接入、监控告警在关闭会话后继续（P5 G5.4）；长探查不受单次调用 60 秒限制（P5）
3. 建议贡献：起草「脱离会话的执行（detached execution）+ 触发器（定时、数据变更）」契约，复用现有 State、Wait、ControlOutcome；说明与会话关闭语义的关系
4. 方式与对接：契约 PR，pengyue.li
5. 关联：03 PR-7；盘点 C2、§7.1

### IF-06 进程外组件注册为调度服务

1. 现状与证据：组件实现只有 native{program, args, sha256}（kernel/host/src/transport/scheduler.rs:50-51），协议是 agentcpm-scheduler/1 NDJSON；子进程 env_clear()（kernel/core/src/scheduler/adapters/native.rs:60）；SDK 只有 Rust；Mint 清单 provides 没有 scheduler 项
2. DataAgent 需要：DataAgent 的 Python / MCP 组件把长任务交给 Scheduler（P3）
3. 建议贡献：增加 mcp 或 command 实现类型（把 MCP 工具桥接成 Capability/Service）；Mint 清单增加 provides.scheduler_bindings；环境变量白名单；脚本本身的校验；Python 版协议 SDK（DataAgent 可贡献）
4. 方式与对接：实现 PR，pengyue.li；Mint 清单找 Mint 负责人
5. 关联：盘点 §7.1

### IF-07 Scheduler 生产装配接线断开

1. 现状与证据：--components-config → startup/scheduler::install → Server::install_components 一链在生产组合根断线，按 dead_code 留档，只有测试在用（kernel/host/src/transport/scheduler.rs:4-8；kernel/host/src/startup/scheduler.rs:12-13）
2. DataAgent 需要：IF-05、IF-06 的前提（P3）
3. 建议贡献：报告缺陷并确认恢复排期；无需 DataAgent 写代码
4. 方式与对接：缺陷报告，pengyue.li
5. 关联：盘点 §7.1

### IF-08 组件把后台结果推回会话

1. 现状与证据：InboxKind 有 SystemNote（session/inbox.rs:51-60），但契约边界写明 hook/MCP 入口不在范围；宿主 session.deliver（kernel/host/src/transport/session_deliver.rs:4-23）要 Kernel 连接与会话授权，MCP 组件拿不到；cpmrt 没有处理 MCP 通知
2. DataAgent 需要：后台探查、OCR、审批等待完成后通知会话并让模型继续（P3 长流程、P5 告警）（P3）
3. 建议贡献：约定 MCP 服务端通知（notifications/resources/updated 或 notifications/message）到 InboxKind::SystemNote 的映射，可配置「只记下」或「唤起回合」；或给组件发按会话限权的投递凭证。DataAgent 侧先做发件箱加游标（P2）
4. 方式与对接：契约 PR，彭淳毅；Mint 负责人
5. 关联：盘点 §7.2；推送设计（03 待补）

### IF-09 工具中途向人要输入

1. 现状与证据：HumanChannel 由独立通道给答复和主体（policy/human.rs:3、:154）；Mint 把 MCP input_required 当错误
2. DataAgent 需要：本体审核、令才澄清不必绕回网页（P2）（P2）
3. 建议贡献：约定 MCP input_required 到 HumanChannel 的接入与答复格式，组件能读到答复主体
4. 方式与对接：提需求，李鹏越
5. 关联：03 PR-5；盘点 C7

### IF-10 组件事件追加与命名空间

1. 现状与证据：StoreContract（store.rs:119）只管会话事件；Scheduler 有 Permissions.state_namespace（scheduler_protocol/model.rs:57）；组件写入专用 kind 前缀没有约定
2. DataAgent 需要：审核、发布留痕进宿主事件流（P3 G3.4）（P3）
3. 建议贡献：约定组件事件 kind 前缀（如 ext.<组件>.<事件>）与 Scheduler 状态命名空间统一为一套；StoreContract 接受组件写入的规则
4. 方式与对接：契约 PR，郑达奇、魏耀全；评审 luyaxi
5. 关联：03 PR-6；盘点 C8

### IF-11 模型端点本机 / 远端标记

1. 现状与证据：ModelEndpointInfo 只有地址、模型名、超时（model.rs:155），只能从 base_url 推断是否出境
2. DataAgent 需要：远端模型下不知情外发样本（S0 评审 X4）；推断请求最小披露（T24）（P3）
3. 建议贡献：ModelEndpointInfo 增加部署位置标记（local / private_cloud / vendor），或由出网判决给出；DataAgent OCR 的 deployment 字段可作参考
4. 方式与对接：契约 PR，魏耀全；评审 pengyue.li
5. 关联：01 Q3；盘点 C6

### IF-12 运行期按依赖名定位包、path 依赖发布

1. 现状与证据：ExtensionContract 有安装期接口检查（extension/*），运行期按依赖名定位与 path 依赖发布没有约定；分工表写「实施范围空白」
2. DataAgent 需要：多包之间互相定位（P6）（P6）
3. 建议贡献：起草运行期依赖定位约定；DataAgent 的 dataagent-cli 分发器是现有消费方
4. 方式与对接：提需求，李鹏越
5. 关联：03 PR-8 相关；盘点 §3 extension 行

### IF-13 打包桌面版不装配项目包的 MCP 工具

1. 现状与证据：Mint Agent 0.1.40 在装了 preset-intake 的项目里能起会话、能加载 4 个 DataAgent 技能，但模型只有 6 个内核工具，没有 dataagent-* MCP 工具；命令行 mint run 同工作区 73 个（16-local-ingestion-workflow-build/gui-channel-check.md）
2. DataAgent 需要：GUI 完成一次文件接入和一次数据库或 API 接入（G1.4、T51）（P1）
3. 建议贡献：kernel-stdio-v1 布局把项目包声明的 MCP 服务接进工具面，或提供非 Kernel 布局 + command 组件通道；DataAgent 可提供复现工作区与验收脚本
4. 方式与对接：提需求，Mint GUI 负责人
5. 关联：03 PR-4、Q1；07 T02（已核实）、T43、T51

### IF-14 Mint GUI 项目模式启动问题

1. 现状与证据：Finder / open -a 不打开项目目录（只认 --cwd）；--cwd 含 /var 软链时报安装路径含软链；用户配置 provider=openai-compatible 时 provider_unsupported，报错指向错误的配置文件
2. DataAgent 需要：用户能从 GUI 打开 DataAgent 项目（P1）
3. 建议贡献：缺陷报告与复现脚本（$PRIVATE_DIR/t02-mint-gui-issue.md）
4. 方式与对接：缺陷报告，Mint GUI 负责人
5. 关联：07 T02

### IF-15 副作用台账与「结果未知只对账」

1. 现状与证据：iface 有 EffectLevel、EffectLedger（session/effect.rs:70-81、:167），纯契约、组件无通道；DataAgent operations 动作网关已实现结果未知只对账、不重复提交（dataagent_operations/action_gateway.py:49-50、:119）
2. DataAgent 需要：写回业务系统时不重复提交（P6 G6.2）（P6）
3. 建议贡献：把 operations 动作网关作为 EffectLedger 的组件侧参考实现，字段与状态名对齐后回馈；同时提出组件写台账的通道需求
4. 方式与对接：参考实现，彭淳毅
5. 关联：盘点 §5 第 5 条

### IF-16 出网判决与审计记录的组件侧实现

1. 现状与证据：iface 有 EgressRequest（policy/egress.rs:15）、AuditEvent（audit.rs）；组件只有进程级出网，没有通道；DataAgent runtime 有 egress_check（dataagent_runtime/enforcement.py:255）与 OCR 的 EgressDecision
2. DataAgent 需要：远程 OCR、REST 出网可审计（P3 G3.3、T15）（P3）
3. 建议贡献：DataAgent 的出网闸门按 EgressRequest 字段对齐后，作为 Python 组件侧参考实现；提出组件把出网请求交给宿主判决的通道需求
4. 方式与对接：参考实现，李鹏越
5. 关联：07 T15；盘点 §5 第 7 条

## 5 维护规则

1. 改 iface 结论前先更新 agent-kernel 并写 `agent-kernel@<sha>`（workspace AGENTS.md）；基线变了，在表里改「基线」列，并复核「现状与证据」的行号。
2. 新缺口先加进表（编号顺延 IF-17 起），再在本篇第 3 节补一行；条目来源写「关联」列（卡号、盘点条目、评审编号）。
3. 沟通结论写进表的「沟通记录」列；状态由沟通人改。确定要做的，在 03 §8.3 的 PR 表登记，并在 07 建卡。
4. 本篇随文档集发布；只在 main 合并后发布。

## 待拍决策

| 编号 | 决策 | 选项 | 推荐 | 影响 |
|---|---|---|---|---|
| Q1 | 先和 iface 负责人谈哪几条 | A：IF-01、IF-04、IF-13；B：全部 P0 与 P1 一次过 | A | P1 验收的三个外部阻断 |
| Q2 | 契约 PR 由谁写 | A：DataAgent 起草、iface 负责人评审；B：只提需求，iface 组实现 | 逐条定 | 贡献节奏 |
