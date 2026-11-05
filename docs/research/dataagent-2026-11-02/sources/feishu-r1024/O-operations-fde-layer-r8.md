<title>DataAgent 持续运行与 FDE 交付：模块与原子能力接口设计 v0.1</title>

本篇整合本地 v0.1 分层设计的模块接口、共享契约、代码目录及组合示例。能力编号基于主规划 revision 1022；本文为设计稿，尚未创建运行时代码。

[返回 Pluggable DataAgent 总规划与分层索引](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)

# DataAgent 持续运行与 FDE 交付扩展层 v0.1

本草案将持续任务、受控动作、委托与人在环、业务环境及交付拆成可独立调用与替换的能力。目标是在真实业务条件下持续完成可验收结果，并将有效方法和能力组合交给客户自行运行。**范围为 DA14–DA18，5 个模块、29 个能力组、91 项原子能力**；编号及名称按 revision 1022 保留，未新增或删除。DA13 已归[数据层建模扩展](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)，本层仅消费物化结果与作业引用。

本地文稿包括本文件、[机器可读目录](https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke)与[代码目录提案](https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke)。全部调用名、对象和目录均为提案，尚未建立运行时代码。本次仅依据本地规划快照设计，无既有平台兼容结论；正式发行包、运行平台适配与发布手续在实现时另行验证。

其他层级及跨层交接见 [DataAgent 分层设计总导航](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)。

## 1. 模块总输入输出

| 模块 | 总输入 | 总输出 | 能力组 / 原子 |
|-|-|-|-|
| DA14 持续运行与监控 | 时间/事件、数据到达与质量观测、指标序列、预算/失败记录、持久等待点、环境基线 | 触发定义和运行请求、观测/漂移/告警、降级决策、等待/续跑回执、角色和接管计划 | 8 / 20 |
| DA15 动作契约 | DA03 动作含义、实现接口、正式分档/授权策略、参数/条件/影响/补偿要求 | 可校验且可发布的动作契约、执行要求、适用范围、弃用/替代目录记录 | 4 / 14 |
| DA16 委托、审批与人在环 | 独立主体、委托链、有效授权策略、待决动作及证据、实际审批/澄清事件、执行观测 | 有界委托、审批/免审决定、监督视图、复核/撤销请求、权责检查、审批负担指标 | 5 / 17 |
| DA17 业务环境配置与协作上下文 | 资源/租户/责任人绑定、默认版本、DA04.5 任务真实修订、子目标/权限/预算、裁定、部署约束 | 环境及默认配置修订、按任务装配上下文、仲裁/传播报告、部署包/实例/健康及回退回执 | 5 / 18 |
| DA18 交付与交接 | 已验证组合、目标/输出/验收要求、环境与依赖、客户角色、基线/上线记录、授权/门禁 | Runbook、自助入口契约、知识/评测移交材料、运营协议、效果报告、Skill 与已验收组合交付清单 | 7 / 22 |

本层按任务装配，DA15–18 是 FDE 扩展，DA14.6–8 也可按需启用；不要求每次查询、文件分析或只读报告全量部署。

## 2. 共用调用、状态与新增对象

统一形式沿用数据层：`invoke(operation, input, CallContext) -> CapabilityResult<T>`。公共 `CallContext / CapabilityResult / Issue / ExecutionRef / Continuation`、`AssetRef / SnapshotRef / EvidenceRef / TaskContextRef / DeliveryRef` 的含义以[共享输入输出契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)为基础，不在本层另起一套身份、引用或版本系统。跨层类型的唯一权威与依赖方向按[总体跨层约定](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)收敛。原子表中输入为业务参数，仍须附 `request_id, scope_ref, authorization_ref`；有任务时带真实 `task_ref`，写入提供 `expected_revision`，可重复副作用请求提供 `idempotency_key`。

`ok / partial / needs_input / pending / failed` 表示本次能力处理状态，不能当作作业生命周期、审批决定或业务验收结论。`pending` 必须返回等待/作业/订阅引用与后续入口。大内容通过受控引用传递，小内容可内联；上下文装配允许按需携带真实内容和必要摘要。按 ID/版本读取属于 RepositoryPort 基础操作，相关性检索归 DA05。

| 新增或细化对象 | 最小字段草案 | 约束 |
|-|-|-|
| `TriggerSpecRef / RunRequestRef` | 版本化触发定义；`target_ref, schedule_or_event, readiness_predicate, dedupe_key, window, selected_context_ref`；运行请求另带 `request_id, trigger_event_ref, requested_at` | 触发/就绪判定与提交作业分开；一个触发可能因缺数据保持等待，不制造已提交事实 |
| `JobRef / JobSnapshot`（消费应用层共享特化） | 复用[应用层共用契约](https://modelbest.feishu.cn/docx/ReDXdJzLWoihZDxqaO0clUxInKf)：`job_id, submission_key, status/read/cancel_refs`；快照含 `observed_state, progress, partial_result_refs, final_refs, continuation`，可附提供方原生状态、观测时间与回执 | 由 DA07 提供/查询；观测态沿用 `accepted/queued/running/waiting/succeeded/failed/cancelled/unknown`，适配映射保留原生值和未知；本层不造同名异义对象或第二套状态权威 |
| `WaitRef / CheckpointRef / ResumeDecision` | `wait_id, task_revision, correlation_id, predicate, allowed_responders, deadline, event_cursor`；断点含 `control_point, completed_receipts, selected_versions, unresolved_effects`；续跑含一次性消费令牌和下一步请求 | 持久等待与租约分开；恢复前复核任务修订/授权/事件身份，副作用未知须 DA07 对账；续跑可转重规划而非机械重放 |
| `AlertRef / DriftReportRef / CostLedgerRef` | 目标版本、观察窗口、规则/方法、实际依据、严重度/差异或用量、去重键、缺口、责任方 | 告警现象与原因假设分开；成本估计与实际回执分开；通知记录 queued/sent/delivered/failed，不能用登记成功冒充送达 |
| `ResultSubscriptionRef` | `subscription_id, subscriber_ref, selector, notification_channel_ref, filter, cadence, disclosure_scope, revision, status` | 结果/告警通知订阅，区别于数据层 DA01.7 源端 CDC/事件的 `SubscriptionRef`；通知生命周期不改变源端水位或数据订阅 |
| `AgentIdentityRef / DelegationRef` | 主体/身份提供方、委托人和受托人、父授权链、资源/动作/档位范围、有效期、撤销状态引用、转委托深度 | 独立身份不复制人凭据；权限只可在父授权范围内约束；每次执行复核有效期/撤销，不因环境绑定产生权限 |
| `ActionContractDraft / ActionContractRef` | 业务语义版本、实现入口绑定、参数 schema、A0/A1/A2、前/后置条件、影响/可逆性、幂等/预演/补偿要求、策略引用、适用环境、状态/版本 | 草案、发布、授权、执行四件事分开；一个编号可有多个等价实现，均需满足契约和业务验收 |
| `EvidencePackageRef / ApprovalRequestRef` | 动作/参数 digest、目标/影响范围、契约/数据/策略版本、预演/验证依据、证据缺口；审批请求含所需角色、截止和回应关联 | 证据可充分而未授权；请求的动作/参数/范围变化使原决定需重查，审批事件必须可校验主体 |
| `AuthorizationDecision / ApprovalResolution` | `decision, subject, action_digest, target_scope, constraints, valid_from, expires_at, policy_revision, basis_refs, approval_or_exemption_ref, audit_ref` | 区分允许/拒绝/待补证与审批批准/拒绝/超时；免审也有正式政策依据；执行时由 DA07 复核有效决定，证据不是授权令牌 |
| `SupervisionView / AdjudicationInputRef` | 当前观测、差异、候选、证据、可操作范围、开放说明/澄清入口、回应主体/时间、关联版本 | 界面供人判断和介入；回应不能自动改口径/授予权限，暂停/撤销必须有执行回执 |
| `BusinessEnvironmentRef / EnvironmentDefaultsRef` | 环境 ID/修订、所属租户、业务运行条件、资源/责任绑定；默认数据/语义/程序/契约/策略/评测/预算精确引用、生效范围 | 环境非租户或物理地点；默认配置供任务选择，任务真实选用及修订归 DA04.5；历史可重现检查归 DA12.6，缺快照明确限制 |
| `ContextSelection / ContextEnvelopeRef` | `task_ref@revision, subgoal, recipient, selected_refs, contents_or_summaries, source_versions, policy_refs, omissions, budget_used` | 装配结果绑定任务修订；必要约束不得被预算裁掉；不再保存独立任务状态，不假定引用即已加载 |
| `TaskRevisionReceipt`（消费共享特化） | 复用应用层定义：`parent/new_context, actual_change_receipts, affected_outputs, revalidation_set`；指向 DA04.5 实际持久化修订 | 默认变更、仲裁意见和传播请求均不等于已产生新任务版本；只接受所属模块返回的真实回执 |
| `ArbitrationRecordRef / PropagationReport` | 冲突、裁决角色/身份、时间、依据、明确决定、生效范围；影响依赖、任务修订回执、需重验结果及失败项 | 裁定事实与正式定义更新分开；传播只处理受依赖影响的对象，历史回执和先前结论保留审计可读 |
| `DeploymentBundleRef / InstanceRef / DeploymentReceipt` | 内容 digest、依赖/校验和、目标特性、安装/探针/回退入口；实例实际版本、环境、操作/启动回执、部分失败 | 部署包不同于业务组合验收清单；升级依赖 DA12.7 变更计划，包安装成功不等于业务效果合格，代码回退不自动撤销数据 |
| `BusinessSkillDraft / PresetBundleDraft` | Skill 记录业务问题、输出、验收、方法指导、能力引用、探索/替换规则；组合记录实现/版本依赖、端口/环境参数绑定和替换点 | Skill 可指导动态改方法；Preset/Bundle 固定可检查的依赖装配而非唯一调用顺序，变更后需相应重验 |
| `DeliveryCandidate / DeliveryRef / OutcomeComparisonReport` | 复用基础 DeliveryRef；候选/正式交付另关联已验证范围、组合/环境版本、DA07 回执、DA11 验收报告、归属/接管条件；效果报告记录基线、窗口、分母、样本与归因限制 | 候选不冒充已验收交付；封装的是声明范围内通过验收的组合，端到端业务效果不要求复刻历史代码或过程 |

所有写操作返回实际保存修订及回执；同一幂等键的不同参数须报冲突。超时或 `execution_unknown` 不允许默认重放有副作用调用，应先查询真实回执、对账。审批/委托/等待事件持久化并按事件 ID 去重；恢复对事件消费和控制点更新做并发检查，避免两个恢复者重复续跑。缺实现/权限/证据时返回相应 Issue，不伪造已部署、已批准、已撤销或已验收。

## 3. 模块与逐原子契约

每组的表先列出组作用与总输入输出，随后逐项定义。表中 `operation` 是逻辑调用名；每组文件映射给出共同源文件，入口为 `dataagent_operations.<模块目录>.<组文件>:<operation>`。全部精确入口同时保存在 JSON；源文件路径相对拟议工作区 `packages/capabilities/dataagent-operations/`，均尚未创建。

### DA14 持续运行与监控

| 能力组 | 作用与总输入 → 输出 | 组边界 | 拟议源文件 |
|-|-|-|-|
| DA14.1 运行触发 | 声明报表、物化表、监控任务在什么条件下重新运行。 时间或事件 → 运行请求 | 调度器复用平台；DataAgent 负责判断数据是否就绪。 | `src/dataagent_operations/continuity/triggers.py` |
| DA14.2 数据监控 | 持续检查数据是否按时到达、质量是否符合约定、结构是否变化。 数据源 → 新鲜度/质量/结构告警 | 检查规则复用 DA11.1 与 DA02.9。 | `src/dataagent_operations/continuity/data_monitors.py` |
| DA14.3 业务指标监控 | 监测关键指标的异常波动，必要时调用 DA08 生成原因假设。 指标序列 → 异常信号 | 告警只说明现象和已验证信息，不把假设当作原因。 | `src/dataagent_operations/continuity/metric_monitors.py` |
| DA14.4 订阅与告警 | 按订阅推送报告和告警，合并重复告警，按规则升级。 异常 → 通知与升级 | 推送渠道复用平台和交付能力。 | `src/dataagent_operations/continuity/notifications.py` |
| DA14.5 运行预算与降级 | 记录每个持续任务的成本，超出预算或连续失败时降级或暂停，并通知维护者。 运行成本 → 预算约束与降级决策 | 配额机制复用平台。 | `src/dataagent_operations/continuity/budgets.py` |
| DA14.6 等待与恢复 〔FDE〕 | 支撑跨天流程。 阻塞点 → 恢复后的续跑 | 不假设流程在一轮对话内完成。 | `src/dataagent_operations/continuity/waits.py` |
| DA14.7 多 Agent 编队与接管 〔FDE〕 | 分工与接管。 目标 → 角色分工与接管 | 不让子 Agent 各自持有独立口径。 | `src/dataagent_operations/continuity/teams.py` |
| DA14.8 环境漂移监控 〔FDE〕 | FDE 场景的主要失效源。 环境状态 → 漂移告警 | 不自动修改契约。 | `src/dataagent_operations/continuity/drift.py` |

#### DA14.1 运行触发

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.1.1 定时刷新定义 | `define_refresh_schedule` | 目标产物/监控定义引用、时区、日历表达式、数据就绪谓词、错过窗口策略 | TriggerSpecRef；下次候选时点、调度登记回执 | 声明触发条件并交平台调度端口登记；未产生 DA07 作业，时点到达仍须检查数据就绪。 |
| DA14.1.2 数据到达/事件触发 | `evaluate_arrival_trigger` | 事件包及来源偏移、TriggerSpecRef、已处理事件游标、数据就绪观察 | RunRequestRef 或未就绪原因；事件去重键、消耗游标建议 | 判定是否发运行请求；不提交作业，不把事件到达等同数据完整，游标提交与持久请求原子关联。 |

#### DA14.2 数据监控

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.2.1 新鲜度监控：对照 DA01.6.3 的更新承诺 | `monitor_freshness` | 资源版本/最近到达时间、DA01.6.3 更新承诺版本、观察窗口、容忍延迟 | FreshnessObservation；迟到/未知状态、偏差时长、AlertRef 候选 | 对照登记承诺与真实观测；源端不可访问输出未知，不能把未知判为按时。 |
| DA14.2.2 质量规则持续检查 | `monitor_quality_rules` | 数据快照或声明范围、质量规则版本、检查周期、采样预算 | DA11.1 检查报告引用、规则失败与覆盖、告警候选 | 复用 DA11.1 实际校验；未跑或样本不足不能称全量质量合格。 |
| DA14.2.3 结构漂移监控 | `monitor_schema_drift` | 资源结构观测、结构基线版本、兼容性规则、观察时间 | DA02.9 结构差异报告、受影响依赖、告警候选 | 复用 DA02.9 比较；只记录漂移，不自动修 schema、映射或契约。 |

#### DA14.3 业务指标监控

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.3.1 指标阈值与异常检测 | `detect_metric_anomaly` | 指标语义版本、时序数据引用、阈值/统计方法版本、观察窗口 | AnomalySignal；异常区间、得分/越限幅度、依据和数据缺口 | 检测现象；季节性/缺数限制显式记录，不据异常推断因果。 |
| DA14.3.2 异常分析触发 | `request_anomaly_analysis` | AnomalySignal、指标与数据版本、允许分析范围、预算 | AnalysisRequestRef；DA08 分析请求回执、候选假设引用或待运行状态 | 通过分析端口触发 DA08；假设与已验证原因区分，异步执行仍归 DA07。 |

#### DA14.4 订阅与告警

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.4.1 结果订阅与推送 | `manage_result_subscription` | 订阅者/渠道引用、产物或告警选择器、过滤/频率策略、订阅或投递指令、可发送内容范围 | ResultSubscriptionRef 或 DeliveryNotificationReceipt；投递状态、失败和重试位置 | 通过通知端口登记/投递；检查收件范围，配置订阅不代表已送达，不自行扩展通知对象。 |
| DA14.4.2 告警合并与升级 | `coalesce_and_escalate_alerts` | AlertRef 集合、合并窗口/指纹、严重度规则、升级路径、既往投递回执 | 合并 AlertRef、被合并来源、升级决策及通知回执 | 按既定规则合并并请求平台投递；合并保留原证据，升级不授予执行权限。 |

#### DA14.5 运行预算与降级

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.5.1 运行成本记录与预算 | `record_run_cost_and_budget` | 任务/运行引用、实际用量回执、价格版本、预算周期/上限、已记账游标 | CostLedgerRef、已用/剩余额度、超限 Assessment、预算事件 | 事实用量与估计分列且按回执去重；硬配额由平台实施，不以本地账本假定已限流。 |
| DA14.5.2 失败降级与暂停 | `decide_degradation_or_pause` | 持续任务引用、失败序列、预算 Assessment、允许降级策略、维护者引用 | 降级/暂停决策、平台控制回执、通知回执、恢复条件 | 只选已授权降级档位；不放宽业务验收或转为未授权实现，控制失败明确未暂停。 |

#### DA14.6 等待与恢复 〔FDE〕

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.6.1 等人：审批与回复 | `wait_for_human_response` | 任务修订引用、审批/澄清请求引用、可回复主体、截止时间、恢复谓词 | WaitRef；持久等待回执、订阅位置、超时升级条件 | 跨天等待审批或开放回复；回复到达不等于批准，批准有效性由 DA16 判断。 |
| DA14.6.2 等系统：外部回执 | `wait_for_external_receipt` | 任务修订引用、外部 correlation_id、预期回执类型、验签/匹配要求、截止时间 | WaitRef；回执匹配条件、等待回执、超时/未知处理条件 | 等待外部事件，不代替 DA07 作业状态查询；只在可关联且验证的回执到达后满足恢复条件。 |
| DA14.6.3 断点恢复 | `resume_from_checkpoint` | CheckpointRef、WaitRef 的满足事件、最新任务修订、DA07 幂等/对账回执 | ResumeDecision；已消费事件、恢复游标、续跑请求或重规划原因 | 原子消费恢复令牌并恢复控制点；未知副作用先经 DA07 对账，禁止盲目重放已执行动作。 |

#### DA14.7 多 Agent 编队与接管 〔FDE〕

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.7.1 角色与子目标划分 | `partition_roles_and_goals` | 总目标、验收条件、依赖图、可用角色/Agent、委托范围、资源预算 | RoleAssignmentPlan；子目标、责任角色、依赖/交接条件、预算分配 | 只分工；不另造业务口径或权限，未授权角色不因被分配而可执行。 |
| DA14.7.2 上下文派发，走 DA17 | `dispatch_collaboration_context` | RoleAssignmentPlan、DA04.5 任务修订、子目标、接收者身份/委托、上下文预算 | DA17.3 ContextEnvelopeRef 集合、派发回执与不足项 | 上下文装配委托 DA17；本项负责派发，不复制任务状态或自行读取越权资源。 |
| DA14.7.3 人工接管与终止 | `request_human_takeover_or_stop` | 任务/编队引用、请求主体、接管或终止原因、当前运行/等待引用、允许控制范围 | TakeoverReceipt；控制权归属、冻结/取消回执、未终止副作用清单 | 停止编排经平台控制、作业取消经 DA07；取消请求不等于外部动作已撤回，保留待对账项。 |

#### DA14.8 环境漂移监控 〔FDE〕

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA14.8.1 系统版本与 UI 变化 | `monitor_system_and_ui_drift` | 环境引用、系统版本/UI 结构基线、当前探测结果、受依赖入口 | DriftReportRef；版本/控件差异、受影响动作、告警候选 | 记录 UI/系统变化；不自动改动作契约或宣称已有适配器继续可用。 |
| DA14.8.2 权限与角色变化 | `monitor_authority_drift` | 环境引用、角色/权限基线、当前权限观测、委托与策略版本 | 权限漂移报告、失效委托/动作候选、复核或暂停建议 | 观测与授权决策区分；实际拒绝由 DA16/DA07 复核，监控不得自动补权限。 |
| DA14.8.3 流程与制度变化 | `monitor_process_and_policy_drift` | 流程/制度基线版本、最新材料/事件、依赖规则及任务引用 | 流程/制度漂移报告、影响范围、修订建议和告警 | 识别变化并通知；正式口径修订走 DA03/DA17，不以文本差异直接改生效规则。 |

### DA15 动作契约

| 能力组 | 作用与总输入 → 输出 | 组边界 | 拟议源文件 |
|-|-|-|-|
| DA15.1 动作分档 | 任何能力入口先判档：A0 读、A1 提议、A2 执行。 动作 → A0/A1/A2 档位 | 不允许「一档通吃」的万能工具；档位不得由 Agent 依据运行效果自行调整。 | `src/dataagent_operations/action_contracts/tiers.py` |
| DA15.2 契约声明与发布 | 将业务动作绑定到具体工具或接口，声明可校验的调用契约和执行要求，并按授权策略发布版本。 动作定义 → 可发布的契约版本 | 业务含义复用 DA03.11；正式授权边界不得自行改变，发布与执行分开。 | `src/dataagent_operations/action_contracts/declarations.py` |
| DA15.3 安全执行要求声明 | 声明动作的幂等、预演、影响面及补偿要求。 契约 → 幂等/预演/补偿声明 | 只描述执行要求；具体执行控制归 DA07.7/07.8。不可逆动作显式标注，不能默认可重跑。 | `src/dataagent_operations/action_contracts/execution_requirements.py` |
| DA15.4 能力目录 | 登记动作契约、适用条件与替代关系，提供统一可检索目录。 契约库 → 可检索的动作清单 | 动作检索由 DA05.8 复用本目录；运行时授权判定归 DA16 及执行控制。 | `src/dataagent_operations/action_contracts/catalog.py` |

#### DA15.1 动作分档

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA15.1.1 A0/A1/A2 判定 | `classify_action_tier` | 动作语义引用、实现调用说明、副作用声明、权威分档规则版本 | TierAssessment；A0/A1/A2、判档依据或未知项 | 使用正式规则判档；含写入的入口不得靠名称归 A0，未知档位不默认为低风险。 |
| DA15.1.2 档位与审批策略映射 | `map_tier_to_approval_policy` | TierAssessment、业务场景/作用域、授权与审批策略版本 | TierPolicyBindingDraft；必检条件、审批/免审策略引用 | 声明档位与策略关联；不能改授权边界，运行时决策仍由 DA16/DA07 给出。 |
| DA15.1.3 越权拒绝 | `reject_out_of_contract_request` | 待调用动作/参数、发布契约版本、声明允许档位/作用域、已知授权限制引用 | ContractAdmissibility；拒绝原因及越界字段，或可继续判权标记 | 契约入口做静态越界拒绝；可继续不等于获授权，运行时 DA16/DA07 必须重查有效授权。 |

#### DA15.2 契约声明与发布

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA15.2.1 参数 schema | `define_action_parameter_schema` | DA03.11 动作语义、工具/API 实现引用、参数路径/类型/约束、凭据绑定槽位 | ActionContractDraft；参数 schema、语义到实现映射、未绑定项 | 建立可校验实现绑定；不重新定义业务含义，不把密钥内联进 schema。 |
| DA15.2.2 前置/后置条件 | `define_action_conditions` | 动作契约草案、DA03 前置/后置语义、机器可检验谓词、检查来源 | 条件声明；前/后置谓词、检查入口、UNKNOWN 处理约定 | 声明可执行检查要求；不在声明时假定条件成立，实际检查归 DA07。 |
| DA15.2.3 影响面与可逆性 | `declare_action_impact_and_reversibility` | 契约草案、目标资源/字段范围、副作用种类、已知回滚条件 | 影响面与可逆性声明；不可逆/有条件可逆标记、证据及未知项 | 描述潜在作用域；声明可逆须有条件，不等于已经回滚或影响估算已验证。 |
| DA15.2.4 契约评审与版本发布 | `review_and_publish_action_contract` | 完整契约草案、评审/校验报告、有效发布策略与所需决策引用、expected_revision | ActionContractRef、发布回执、状态/生效范围和审阅记录 | 按授权策略完成评审发布并复用 DA12 版本管理；发布不授予调用权，不强加一律人工签字。 |

#### DA15.3 安全执行要求声明

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA15.3.1 幂等键 | `declare_idempotency_requirements` | 契约引用、业务唯一键来源、作用域/有效期、重复冲突与对账要求 | IdempotencyRequirement；键生成规范、冲突语义、执行方要求 | 只声明 DA07 必须满足的去重/对账要求；不把生成一个 UUID 等同幂等已保证。 |
| DA15.3.2 dry-run | `declare_dry_run_requirements` | 契约引用、预演实现绑定、可用参数、隔离/残余副作用约束、差异格式 | DryRunRequirement；支持/不支持/受限状态、预演输入输出及限制 | 声明预演能力和限制；不执行预演，不将只做参数校验称零副作用演练。 |
| DA15.3.3 影响面预估 | `estimate_declared_action_impact` | 契约影响声明、候选参数、DA07 预演结果或有界只读估算依据、估算范围 | ImpactEstimate；目标数/范围、估算方法、上界/未知、来源版本 | 可计算影响估计但仅消费预演/只读观测；不实施动作，也不以估计取代 DA07 执行前复核。 |
| DA15.3.4 补偿动作声明 | `declare_compensation_action` | 原动作契约、补偿动作契约版本、参数/回执映射、触发条件、不可补偿范围 | CompensationRequirement；反向动作绑定、适用窗口、失败升级与残余风险 | 补偿作为新动作声明且独立判权；不承诺所有动作可逆，不在声明阶段执行补偿。 |

#### DA15.4 能力目录

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA15.4.1 动作目录索引 | `index_action_contract` | 发布契约及实现引用、目录元数据、分档、环境适用条件、版本事件 | ActionCatalogEntryRef、索引登记回执、可检索字段与版本 | 登记供 DA05.8 检索；不在此实现相关性召回，不以被收录代表已授权或已部署。 |
| DA15.4.2 适用范围与限制 | `resolve_action_applicability` | 动作目录 ID/版本、目标环境条件、资源/档位约束、已有观测引用 | 适用条件与限制、匹配 Assessment、缺失前提及替代引用 | 按已知契约解析范围；未知环境返回待核验，相关动作发现仍由 DA05.8。 |
| DA15.4.3 弃用与替代 | `deprecate_or_replace_action` | 现有契约版本、弃用原因/生效窗口、替代版本、兼容/迁移依据、变更决策 | 弃用/替代关系版本、受影响调用方清单、目录更新回执 | 不静默替换运行中任务固定版本；迁移与重验按 DA12/DA04.5 显式进行。 |

### DA16 委托、审批与人在环

| 能力组 | 作用与总输入 → 输出 | 组边界 | 拟议源文件 |
|-|-|-|-|
| DA16.1 身份与委托 | 给 Agent 独立身份，明确代表谁、到什么时候。 主体与场景 → 可用权限范围 | 不复用人的凭据，不允许无限期继承。 | `src/dataagent_operations/delegation/identities.py` |
| DA16.2 审批 | 让审批人在可接受时间内判断。 待决动作与证据 → 批准/拒绝/超时结论 | 只有授权策略允许且证据达标时才可免审；证据充分不等于获得授权。免审条件不得由 Agent 自行放宽。 | `src/dataagent_operations/delegation/approvals.py` |
| DA16.3 监督界面 | 让人看见执行状态，能够澄清、纠正、暂停或接管。 执行状态 → 可视与可介入的界面 | 优先提供候选方案与依据，同时允许自由补充和开放澄清，不将沟通限制为是/否选择。 | `src/dataagent_operations/delegation/supervision.py` |
| DA16.4 权责分离 | 让提议者不等于批准者。 组织约束 → 审批权与执行权的分配 | 不允许 Agent 自批自执。 | `src/dataagent_operations/delegation/separation.py` |
| DA16.5 审批负担度量 | 度量人是否被 Agent 累死。 审批记录 → 量与质指标 | 不把审批量当作价值。 | `src/dataagent_operations/delegation/burden.py` |

#### DA16.1 身份与委托

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA16.1.1 Agent 身份 | `register_agent_identity` | 身份提供方引用、Agent 实例/实现标识、责任主体、作用域、认证证明引用 | AgentIdentityRef；独立主体标识、验证状态、有效期 | 使用可验证 Agent 主体，凭据由代理保存；不借用人的身份令牌假作 Agent 身份。 |
| DA16.1.2 委托范围与时限 | `define_scoped_delegation` | 委托人权限依据、AgentIdentityRef、资源/动作/档位范围、起止时间、撤销条件 | DelegationRef；有效范围、期限、上级授权链、登记回执 | 不得超出委托人可委托权限；期限有限且执行时复核撤销/过期，不凭证据包扩大范围。 |
| DA16.1.3 转委托限制 | `check_redelegation_constraints` | 父 DelegationRef、受托主体、拟转委托范围/期限/深度、转委托策略 | 转委托允许/拒绝 Assessment、约束后的委托草案或拒绝原因 | 范围/期限只能按政策收窄；父委托未允许转委托时拒绝，不自行创建无限授权链。 |

#### DA16.2 审批

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA16.2.1 触发判据 | `evaluate_approval_requirement` | 动作/参数与影响面、有效委托、策略版本、场景条件、现有证据状态 | ApprovalRequirementDecision；必须审批/可按免审判据继续/拒绝/信息不足、所需角色 | 判定审批路径且保留依据；可继续检查不等于已批准，证据充分不能覆盖禁止执行的策略。 |
| DA16.2.2 证据包组装 | `assemble_approval_evidence` | 待决动作与参数、契约/任务版本、预演/影响/验证报告、证据要求、可披露范围 | EvidencePackageRef；可定位证据、缺口、参数 digest、预览及脱敏说明 | 组装且评估证据覆盖，不签发执行授权；脱敏导致信息不足要显式说明。 |
| DA16.2.3 超时升级与拒绝处理 | `handle_approval_timeout_or_rejection` | ApprovalRequestRef、截止时间/时钟、有效拒绝或未决状态、升级规则、通知路径 | ApprovalResolution；拒绝/超时/升级状态、后续等待条件、通知回执 | 超时不默认批准；仅按既定规则升级，拒绝后不绕过审批另发等效动作。 |
| DA16.2.4 批量与抽样审批 | `apply_batch_or_sample_approval` | 待决动作集合及逐项参数 digest、批量/抽样策略、样本选择与覆盖、有效审批决定 | BatchApprovalDecision；逐项适用结论、样本清单、可外推范围、未覆盖项 | 抽样是否覆盖未抽样项必须有正式策略依据；任何参数/范围变更须重新核对授权绑定。 |
| DA16.2.5 免审判据〔定〕 | `evaluate_approval_exemption` | 动作/参数 digest、有效委托/授权策略版本、正式免审条件、证据包及完整性报告 | AuthorizationDecision；免审允许/拒绝/待补证、约束/有效期、依据及 audit_ref | 仅授权允许且证据达标时免审；无需再加人工签字，Agent 不可自改免审门槛或用证据替代授权。 |

#### DA16.3 监督界面

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA16.3.1 执行前预览 | `build_pre_execution_preview` | 动作参数、契约版本、影响估计/预演报告、审批需求、用户可见范围 | SupervisionView；目标/变更差异、证据、限制、可选操作及开放回复槽位 | 呈现事实和候选；界面预览不执行、不授权，提交选择另经有效身份和政策验证。 |
| DA16.3.2 执行中监控 | `build_execution_monitor_view` | 任务/作业引用、DA07 状态与事件游标、等待点、用户控制权限 | 监督视图/事件流引用、观测时间、可暂停/接管入口、未知运行项 | 消费 DA07 实际状态；不发明第二套作业状态，UI 控制经端口传给对应模块。 |
| DA16.3.3 执行后复核与撤销 | `review_execution_and_request_reversal` | DA07 执行回执、后置验证、人工复核意见、补偿契约、请求主体/授权 | 复核记录、需重验项、补偿/撤销请求及处理回执或不可撤销原因 | 撤销需独立授权并由 DA07 执行；用户点击不表示已撤销，不可逆动作只能披露后续措施。 |
| DA16.3.4 差异裁定入口 | `capture_difference_adjudication` | 差异对象/版本、候选及依据、具备裁定权的主体、选择/纠正/自由补充内容 | AdjudicationInputRef；裁定意见、依据、未决澄清及正式修订请求 | 接收开放输入；意见与生效修订分开，语义口径裁定交 DA17.4/DA03，不静默覆盖原值。 |

#### DA16.4 权责分离

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA16.4.1 审批权与执行权分离 | `assign_separated_authority` | 组织角色策略、动作风险档位、提议/审批/执行主体、委托链 | SeparationAssessment；职责矩阵、冲突/禁配项、允许分配引用 | 有审批要求时提议与批准主体必须符合分离政策；Agent 不可自批自执，既有策略免审无需虚造批准人。 |
| DA16.4.2 双人复核 | `validate_two_person_review` | 高风险动作 digest、双人复核策略、两位审阅者身份/独立性、实际决定记录 | TwoPersonDecision；独立性检查、逐人结论、绑定范围/期限 | 仅在政策要求双人复核的范围实施；同人双账号不算两人，不将其扩为所有动作一律双签。 |
| DA16.4.3 紧急豁免与留痕 | `record_emergency_exception` | 紧急事件、正式紧急政策、具豁免权主体的决定、受限动作/期限、补审和通知要求 | EmergencyExceptionRef；边界/到期、实际决策依据、审计与通知回执 | 豁免须源于正式权限，Agent 不自宣紧急放权；保留补审义务和执行时复核。 |

#### DA16.5 审批负担度量

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA16.5.1 审批量与耗时 | `measure_approval_volume_and_latency` | 审批事件日志范围、流程/风险分组、工作时间定义、统计窗口 | 审批量、等待/处理时长分布、分母、超时/未决项、质量限制 | 区分人工处理和系统等待；不以审批越多越好，免审调用与未发起审批分别计数。 |
| DA16.5.2 通过率与改写率 | `measure_approval_outcomes` | 去重审批结论/改写记录、动作与风险分组、统计窗口、关联运行结果 | 通过/拒绝/改写率、分母与样本数、风险分层、未知关联 | 描述审批负担与质量线索；通过率不等于授权可靠性，不据统计自动放宽政策。 |

### DA17 业务环境配置与协作上下文

| 能力组 | 作用与总输入 → 输出 | 组边界 | 拟议源文件 |
|-|-|-|-|
| DA17.1 业务环境注册 | 标识一组实际业务运行条件，关联资源、租户及责任人。 业务运行条件 → 环境标识与绑定 | 同一租户可有多个业务环境；不承担租户计费。 | `src/dataagent_operations/environments/registry.py` |
| DA17.2 环境版本配置 | 维护业务环境默认使用的数据、语义、程序、契约及策略版本引用，供任务选择和固定。 业务环境 → 默认版本组合 | 本次任务实际选用及修订归 DA04.5；历史可重现性由 DA12.6 检查，缺快照时说明限制。 | `src/dataagent_operations/environments/defaults.py` |
| DA17.3 上下文派发 | 依据 DA04.5 的任务修订、子目标和权限范围，按需解析引用并装配子 Agent 所需上下文。 任务 → 子任务的最小充分上下文 | 按需传入实际内容和必要摘要，不要求只传引用；不另存一套独立任务状态。 | `src/dataagent_operations/environments/contexts.py` |
| DA17.4 口径仲裁 | 口径冲突由指定角色裁决。 冲突口径 → 裁决结论与传播影响 | 不让子 Agent 各自修改口径；改口径必须走显式修订。 | `src/dataagent_operations/environments/arbitration.py` |
| DA17.5 能力部署与运行环境 | 把能力包部署进客户环境并保持可运行，覆盖离线安装、依赖与网络受限环境、升级与回退。 能力包 + 环境约束 → 可运行实例与部署清单 | 不管客户基础设施本身；引擎离线包复用 DA07.10.1；升级前须有 DA12.7 变更计划。 | `src/dataagent_operations/environments/deployment.py` |

#### DA17.1 业务环境注册

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA17.1.1 业务环境标识 | `register_business_environment` | 运行条件描述、所属租户引用、业务范围、环境责任人、环境标识策略 | BusinessEnvironmentRef；稳定 environment_id、注册修订和作用域 | 环境是一组真实业务条件，同租户可多环境；不是租户计费单元或物理现场标签。 |
| DA17.1.2 环境绑定 | `bind_environment_resources` | BusinessEnvironmentRef、系统/地址/资源引用、连接及凭据绑定引用、可用条件 | 环境绑定修订、资源映射、校验状态、未就绪项 | 保存代理引用且不暴露密钥；绑定不等于可访问/已部署，源资源发现复用 DA01。 |
| DA17.1.3 责任人与联系人 | `maintain_environment_contacts` | 环境引用、责任角色与联系人标识、值班/升级渠道、适用期限、变更依据 | OwnershipContactRef；责任与联系矩阵版本、更新回执 | 记录归属与路径；联系人不是当然审批人，审批资格从授权策略解析。 |

#### DA17.2 环境版本配置

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA17.2.1 数据快照引用 | `configure_default_data_snapshot` | 环境默认配置版本、数据槽位、SnapshotRef 或源端 as-of 能力、有效范围 | EnvironmentDefaultsRef 新修订；默认快照引用、缺失/过期/可重读限制 | 维护环境默认，不改既有任务；本次任务选用归 DA04.5，digest/时点不等于可重读快照。 |
| DA17.2.2 本体与契约版本 | `configure_default_semantic_and_contract_versions` | 环境默认配置、语义/本体/动作契约版本及程序实现引用、兼容检查报告 | 默认版本组合新修订、依赖锁定表、未兼容项 | 配置供后续任务选用；不重新发布资产，不静默更新任务已固定语义、程序或契约。 |
| DA17.2.3 权限策略版本 | `configure_default_policy_versions` | 环境默认配置、有效授权策略/委托约束版本、策略适用范围、生效时间 | 默认权限策略引用新修订、作用域匹配报告 | 仅保存默认引用，不能授予或放宽权限；执行时仍核对当时有效政策及撤销状态。 |
| DA17.2.4 评测集与预算版本 | `configure_default_evaluation_and_budget_versions` | 环境默认配置、评测集/验收口径版本、预算定义/价格版本、适用窗口 | 默认评测/预算配置修订、版本依赖与缺口 | 选定默认不代表已评测通过或预算已预留；正式验收/配额分别由 DA11/平台实施。 |

#### DA17.3 上下文派发

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA17.3.1 子任务裁剪 | `slice_subtask_context` | DA04.5 TaskContextRef、子目标、角色/委托、依赖清单、最小信息要求 | ContextSelection；保留/剔除引用、必要内容选择、缺失与权限缺口 | 以真实任务修订为基准裁剪，不另存任务状态；信息不足必须上报，不能剪掉必要业务约束。 |
| DA17.3.2 引用解析与上下文装配 | `resolve_and_assemble_context` | ContextSelection、请求身份/授权、精确版本引用、解析选项、内容预算 | ContextEnvelopeRef；实际内容/受控引用、来源版本、拒绝/缺失项与完整性 | 按需加载实际内容而非只传引用；按 ID/版本解析由 repository 完成，问题相关性召回归 DA05。 |
| DA17.3.3 摘要与预算 | `summarize_context_with_budget` | 已装配上下文、子目标、token/字节预算、必须保留约束、摘要实现版本 | 有来源映射的摘要/保留内容、使用预算、遗漏清单、补取引用 | 预算不足输出 partial/needs_input；不摘要掉权限/验收红线，不将摘要当作完整原始证据。 |

#### DA17.4 口径仲裁

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA17.4.1 冲突检测 | `detect_collaboration_semantic_conflict` | 任务/子任务实际修订、语义定义版本、各结论/引用、比较作用域 | ConflictSetRef；冲突定义、来源、受影响任务、候选消解路径 | 复用 DA03.10 定义冲突识别并聚合协作冲突；不让各子 Agent 各改一套口径。 |
| DA17.4.2 仲裁记录 | `record_semantic_arbitration` | ConflictSetRef、具裁决权角色的实际选择/说明、证据、拟生效范围/时间 | ArbitrationRecordRef；谁在何时依据什么裁定、修订提案和未决项 | 忠实记录实际裁决；不伪造角色决定，正式语义保存/发布交 DA03/DA12，任务采用交 DA04.5。 |
| DA17.4.3 修订传播与旧结果失效 | `propagate_arbitrated_revision` | 有效裁定/新定义版本、依赖与产物来源图、受影响任务清单、传播策略 | PropagationReport；DA04.5 修订回执、需重验结果标记、通知与未更新清单 | 只按依赖标记受影响旧结果需重验/当前不适用，保留历史事实；不把所有结果永久失效，不绕过 DA04.5。 |

#### DA17.5 能力部署与运行环境

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA17.5.1 部署包构建 | `build_deployment_bundle` | 已选能力/实现版本、依赖锁、目标平台与离线限制、许可/分发约束、引擎离线包引用 | DeploymentBundleRef；依赖清单、校验和、安装/健康/回退入口、未闭合依赖 | 构建部署载体；引擎离线产物复用 DA07.10.1，不因打包宣称业务验收通过或运行平台兼容。 |
| DA17.5.2 环境预检 | `preflight_target_environment` | DeploymentBundleRef、目标环境绑定、网络/权限/资源约束、探测许可 | PreflightReport；逐项满足/不满足/未知、容量与受限项、部署前提 | 做有界预检；不治理客户基础设施，不因测试端点可达推定业务接口有权执行。 |
| DA17.5.3 实例部署 | `deploy_capability_instance` | BundleRef、预检报告、目标环境、部署权限、DA12.7 变更计划、目标版本/幂等键 | DeploymentReceipt；InstanceRef、实际版本/位置、启动状态、失败与回退点 | 通过部署端口安装启动；升级须有效变更计划，副作用经执行控制，成功安装不等于业务验收。 |
| DA17.5.4 健康检查 | `check_instance_health` | InstanceRef、环境钉定版本、健康探针/只读烟测约束、观测窗口 | HealthReport；存活/就绪、实际依赖版本、钉定差异、观测依据 | 检查运行可用和版本一致；健康不代替端到端效果验证，未知探针明确报未知。 |
| DA17.5.5 版本回退 | `rollback_capability_instance` | InstanceRef、上个可用部署版本、回退/变更计划、数据/契约兼容依据、执行权限 | RollbackReceipt；实际恢复版本、健康结果、未回滚数据/副作用清单 | 只恢复明确可回退内容；数据变更不自动随代码回滚，不可逆项披露并交补偿/人工处置。 |

### DA18 交付与交接

| 能力组 | 作用与总输入 → 输出 | 组边界 | 拟议源文件 |
|-|-|-|-|
| DA18.1 Runbook | 让客户能自己跑。 已验证配置 → 可执行的操作手册 | 不假设客户会读代码。 | `src/dataagent_operations/delivery/runbooks.py` |
| DA18.2 自助界面 | 客户日常操作的入口。 能力与流程 → 客户可用的入口 | 不替代客户的专业系统。 | `src/dataagent_operations/delivery/self_service.py` |
| DA18.3 知识移交 | 把「为什么这么做」交出去。 交付物 → 说明与培训材料 | 不保留隐性知识作为议价筹码。 | `src/dataagent_operations/delivery/knowledge_transfer.py` |
| DA18.4 运营协议 | 明确服务边界与退出方式，并把自主度分档移交。 双方约定 → SLA、值班与退出条款 | 不承诺不可验证的 SLA；不移交未验证的环节。 | `src/dataagent_operations/delivery/operating_agreements.py` |
| DA18.5 交付效果度量 | 对照 DA02.15 基线，度量上线后客户侧的工时、错误率与成本变化。 基线 + 上线后运行记录 → 改进幅度与置信说明 | 不把系统指标（DA11.6）当作客户收益；基线缺失或样本不足时说明，不外推。 | `src/dataagent_operations/delivery/outcomes.py` |
| DA18.6 业务 Skill 构建 | 将业务问题、方法指导、输出要求和验收条件组织为 Skill，引用可用能力，并根据验证结果提出修订。 业务要求与能力 → Skill 草案或修订 | 约束业务目标与交付要求；允许 Agent 调整求解方法，不将 Skill 写成唯一工具调用顺序。正式口径变更按对应机制处理。 | `src/dataagent_operations/delivery/skills.py` |
| DA18.7 Preset/Bundle 组装 | 选择组件、实现与 Skill，配置依赖、业务环境绑定和可替换点，形成可验证的组合包。 候选能力组合 → 可试运行与交付的组件包 | 复用 DA05.8 检索、DA08.6 程序生成、DA11 验证及 DA12 版本发布；不在本模块重建执行引擎。 | `src/dataagent_operations/delivery/bundles.py` |

#### DA18.1 Runbook

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA18.1.1 日常操作手册 | `draft_daily_runbook` | 已验证组合/环境配置、目标用户角色、日常任务入口、验证报告、运行限制 | RunbookDraft；操作步骤、输入样例、预期输出、检查点、版本引用 | 面向无需读代码的用户；只写经验证可运行的路径，无法验证步骤标为待验证。 |
| DA18.1.2 异常处置流程 | `draft_exception_runbook` | 已观测失败/等待/未知回执、告警规则、允许重试/对账/接管路径、责任人 | ExceptionRunbookDraft；症状到诊断/处置/升级、停止条件与待对账项 | 不建议盲重放有副作用动作；引用 DA07 对账与 DA14 恢复，不扩大授权。 |
| DA18.1.3 责任矩阵 | `draft_delivery_responsibility_matrix` | 交付范围、客户/交付方角色、运行/审批/维护任务、权责政策 | 责任矩阵草案；负责/批准/协作/知会角色、空缺与冲突 | 责任分配草案不授予系统权限；正式职责按有权主体约定生效并复用 DA16 权责约束。 |

#### DA18.2 自助界面

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA18.2.1 任务发起与查看 | `provide_task_self_service` | 界面会话主体、Skill/Preset 版本、发起参数或任务查询条件、可见/可操作权限 | 任务发起回执或状态视图；task_ref、所选版本、缺失参数/权限提示 | GUI/TUI 仅经 TaskControlPort；发起不代表作业已执行，既有任务状态由 DA04.5/DA07/DA14 提供。 |
| DA18.2.2 审批与例外申请 | `provide_approval_and_exception_entry` | 界面主体、待决请求/异常引用、候选依据、选择/自由说明、授权策略 | DA16 请求/回应回执、当前待决状态、下一等待条件 | 经监督/授权端口交 DA16；提供开放澄清，界面点击或例外申请均不自动成为批准。 |
| DA18.2.3 指标与报表 | `provide_metrics_and_reports_entry` | 界面主体、报告/指标选择、窗口/过滤、可披露范围、分页游标 | 授权范围内报表/指标视图、来源版本、完整性与后续游标 | 经 ReportPort 消费 DA10/DA18.5 结果；不在 UI 重算一套口径，不泄露受限样本。 |

#### DA18.3 知识移交

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA18.3.1 契约与本体说明 | `prepare_contract_and_ontology_handover` | 交付清单、已选语义/动作契约版本、角色词表、适用范围、未决问题 | 知识说明资产；术语/参数/条件/例子、版本依赖、来源和限制 | 解释已交付定义，不另定客户口径；材料指向精确版本，未决问题不得写为正式事实。 |
| DA18.3.2 评测集移交 | `prepare_evaluation_set_handover` | 评测集版本、样本使用/隐私权限、预期结果与判据、验证实现、运行说明 | 评测移交清单、受控样本/标签引用、复跑入口、覆盖和限制 | 按授权移交可用材料；保留开发/回归/验收样本角色，不以训练样本效果冒充独立验收。 |
| DA18.3.3 培训材料 | `prepare_training_materials` | Runbook、责任矩阵、目标角色、已验证样例、异常场景、交接要求 | 培训材料/演练计划、预期表现、讲解来源和待补知识清单 | 交出使用与判断依据；生成材料不表示客户已掌握，实操结果另存验证记录。 |

#### DA18.4 运营协议

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA18.4.1 SLA 定义 | `draft_service_level_agreement` | 双方服务边界、可观测指标/来源、窗口/分母、已验证容量、例外与责任 | SLA 草案；可测目标、测量方式、违约/例外条件、待确认项 | 目标由有权主体约定；缺证据不承诺可用率/时延，系统指标与客户收益分开。 |
| DA18.4.2 值班与升级 | `draft_oncall_and_escalation` | 服务范围、严重度词表、值班角色/时区、响应约定、升级/接管路径 | 值班与升级协议草案、联络/交接矩阵、覆盖空缺 | 协议不等于已建立外部值班服务；通知渠道实际绑定交平台，权限仍由 DA16 检查。 |
| DA18.4.3 变更窗口与退出 | `draft_change_window_and_exit` | 维护窗口、变更/回退规则、资产/数据归属、导出/停用/销毁约定、退出责任 | 变更窗口与退出条款草案、依赖清单、退出检查点与可验证完成条件 | 约定退出不立即停服务或删数据；实际变更经 DA12.7 与受控执行，保留依法/依约须留记录。 |
| DA18.4.4 自主度移交：从我们代跑到客户自跑的分级 | `plan_autonomy_handover` | 按环节验证/上线门禁报告、客户能力与委托、当前代跑模式、风险/接管条件 | AutonomyHandoverPlan；逐环节自主档位、达标依据、未开放项、回退和移交回执要求 | 仅按已验证环节移交；自主度变化需既有授权/门禁有效，不因整体可运行就全自动放权。 |

#### DA18.5 交付效果度量

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA18.5.1 上线后指标采集 | `collect_post_launch_business_metrics` | DA02.15 基线口径版本、上线运行记录、工时/错误/成本采集窗口、样本范围 | BusinessOutcomeObservation；同口径指标、分母、采集证据、缺失及样本量 | 采集客户侧变化，系统延迟等 DA11.6 指标不可代替收益；缺基线口径保留不可比标记。 |
| DA18.5.2 基线对比 | `compare_business_outcome_baseline` | 基线数据/口径版本、上线指标、可比样本/窗口、统计方法和混杂观察 | OutcomeComparisonReport；绝对/相对变化、区间/样本量、可比性与限制 | 未满足可比条件则不可判定；不将一次小样本的提升外推全部业务，也不自动声称因果。 |
| DA18.5.3 不可归因部分标注 | `annotate_outcome_attribution_limits` | 对比报告、同期流程/人员/数据量变化、对照设计/缺失情况、证据 | AttributionAssessment；可归因范围、混杂因素、无法归因部分和补证建议 | 明确统计相关与归因强度；不能用主观猜测抹去混杂，证据不足不编造提升百分比。 |

#### DA18.6 业务 Skill 构建

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA18.6.1 业务问题与交付要求组织 | `organize_business_skill_requirements` | 业务问题、目标用户/任务范围、输出形式、正式验收条件/权限边界、已有案例 | BusinessSkillDraft；目标、输入条件、交付要求、验收判据、开放问题 | 约束业务目标和输出；缺正式口径提出澄清，不让 Agent 自行放宽验收标准。 |
| DA18.6.2 方法指导与能力引用 | `compose_skill_guidance_and_capabilities` | Skill 要求草案、DA05.8 候选能力、已验证方法/失败经验、可替换约束 | 方法指导草案、能力引用、探索/验证循环、替代点及选择依据 | 指导允许动态换方法/代码/中间流程；不写成唯一工具顺序，不以能力推荐替代实际授权。 |
| DA18.6.3 Skill 修订生成 | `propose_business_skill_revision` | 当前 Skill 版本、真实探索轨迹、DA11 验证反馈、失败/改进证据、约束不变项 | SkillRevisionDraft；指导/能力组合差异、修订理由、重验要求及 DA04.4 保存引用 | 修改候选与生效分开；资产保存复用 DA04.4，正式口径改动走对应治理，候选不得冒充已验收。 |

#### DA18.7 Preset/Bundle 组装

| 编号 / 名称 | operation | 输入 | 输出 | 原子边界 |
|-|-|-|-|-|
| DA18.7.1 组件依赖装配 | `assemble_component_dependencies` | Skill/候选能力与实现版本、依赖约束、目标平台特性、允许替换点 | PresetBundleDraft；实现锁定表、依赖图、入口/端口绑定、冲突与未闭合项 | 复用 DA05.8 找候选，检查装配一致性；可装配不代表运行或业务验收通过，发布粒度不等于原子编号。 |
| DA18.7.2 业务环境参数绑定 | `bind_bundle_environment_parameters` | Bundle 草案、业务环境默认版本、数据/工具/凭据/策略引用、参数映射、替换限制 | EnvironmentBoundBundleDraft；已绑定/未绑定槽位、精确依赖、替换点和权限缺口 | 环境绑定不授予权限；任务实际版本由 DA04.5 固定，敏感凭据仅代理引用，缺快照不承诺复现。 |
| DA18.7.3 组合试运行与交付封装 | `trial_validate_and_package_delivery` | 已绑定组合、业务验收样本/判据、有效授权/预算、目标环境、交付范围 | DeliveryCandidate 或 DeliveryRef；DA07 运行与 DA11 验收报告、封装清单、DA12 发布/DA04 保存引用 | 经执行/验证端口试运行，仅对通过的声明范围封装交付；端到端业务效果为准，允许不同方法，不重建引擎或要求复刻代码。 |

## 4. 跨层职责与可替换边界

| 协作关系 | 本层负责 | 外层保持的权威职责 |
|-|-|-|
| DA14 ↔ DA07 | 定义何时运行、判断就绪、持久等待、消费恢复事件、组织续跑请求 | DA07 提交/查询/取消作业、实际调用、幂等去重、外部未知副作用对账；DA14 观察可引用 DA07 状态，不接管其生命周期 |
| DA15 ↔ DA03 / DA07 / DA05.8 | 将既有业务动作含义绑定到实现，声明参数与执行要求，发布/索引契约 | DA03 定义业务含义；DA07 执行预演/检查/写入/补偿；DA05.8 搜索和排序候选动作/组件 |
| DA16 ↔ DA12 / DA07 | 有界委托、依策略决定审批/免审路径、接收有效决定、开放监督与权责检查 | DA12 治理正式政策、访问约束、版本和审计；DA07 在实际执行点复核身份、有效授权和条件；监督视图不能绕过执行网关 |
| DA17 ↔ DA04.5 / DA12.6 | 环境默认版本、依任务真实修订装配上下文、组织裁决传播 | DA04.5 保存任务实际选用和修订；DA12.6 检查历史可重现；环境默认改变不自动改已有任务，也不将缺失快照说成已固定可重读 |
| DA17 ↔ DA01 / DA12.7 / DA07.10 | 资源绑定、部署/预检/健康/回退组织 | DA01 接入/探测真实资源、代理凭据；DA12.7 变更计划；DA07.10.1 引擎离线包及引擎实际接入验证；本层不管理客户基础设施 |
| DA18 ↔ DA04 / DA05.8 / DA08.6 / DA11 / DA12 | 写业务指导、依赖装配、环境参数、移交及效果材料 | DA04 存真实轨迹/程序/交付资产；DA05.8 检索；DA08.6 生成/修复程序；DA11 验证/门禁；DA12 版本发布。不可复制另一套执行/评测引擎 |
| DA18 ↔ DA02.15 / DA11.6 | 按同口径比较客户工时/错误/成本、声明混杂与归因限制 | DA02.15 记录业务现状基线，DA11.6 维护系统指标；系统响应快不自动代表客户工时减少 |
| DA13 ↔ 本层 | 对物化任务配置触发/监控，引用建模产物与执行回执 | [DA13 数据建模与物化](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)保留唯一能力定义，不在本层重复编号 |

A0/A1/A2 是入口分档，非自证权限：同一工具入口要显式区分读、提议、执行，权限和审批仍以正式政策为准。策略允许且证据达标可免审，不增加“一律人工签字”；要求审批的动作由符合权责分离规则的主体批准，Agent 不得制造授权或自批自执。两人复核、紧急豁免均按既定范围实施。

业务探索允许反复检索、补数据、改程序或换实现。已验收 Skill/Preset 的引用是可复用起点；变更方法后保留真实轨迹和依赖版本，并按受影响范围重新验证。正式目标、口径和权限的修改仍须按对应机制生效，不由一次运行效果好坏自动调整。

## 5. 两个业务场景与建设切片

### 场景 A：令才规则审核，从制度变化到可交接组合

输入是制度修订版、审核单据样本、既有规则/证据要求、客户权限和上线前工时/错误率基线。数据层提供制度条款、单据字段、语义规则及真实快照；DA03.15/16 保留不可判定和不适用项。DA18.6 组织“提取制度、准备单据、输出带依据审核意见”的目标和验收条件；方法指导可先用结构化抽取，再根据验证不足改解析方法或替换规则执行实现，过程和代码允许不同。

DA15 为读取、生成审核意见、回写结果分别声明档位与实现契约。DA18.7 经 DA05.8 选组件、配置依赖和环境槽位；DA17 维护审核环境默认制度/规则/引擎/策略版本，DA04.5 固定本次实际选择。DA07 试运行、DA11 比较独立验收样本中的结果、证据定位和过程合规；失败返回探索循环。只有验收覆盖的范围由 DA18.7.3 封装，报告列清未覆盖票据类型与不可判定项，不将“程序复刻一致”作为业务验收标准。

上线后 DA14.8.3 发现制度变化，DA17.4 将口径冲突交指定角色裁决；新定义发布后 DA04.5 形成实际任务修订，传播报告只标记受影响结果需重验。回写环节若有效策略允许免审且证据达标，DA16.2.5 返回受限允许决定；必须审批的异常通过 DA16 开放候选、证据和补充说明。跨天审批由 DA14.6 等待，事件到达后复核决定、版本及 DA07 回执再续跑。DA18 移交 Runbook/评测集/接管方式，并与 DA02.15 基线比较同口径工时、错误和成本，明确样本不足及无法归因部分。

建设切片：先交付离线只读审核与证据/验收闭环（DA18.6/7 + DA15 A0/A1）；再加入带有效策略的回写、审批/免审与跨天恢复（DA15/16 + DA14.6）；最后部署健康、制度漂移、客户自助与效果度量（DA17.5 + DA14.8 + DA18.1–5）。每片以实际业务输出、拒绝/未知处理和可接管性验收，不要求一次启用全部模块。

### 场景 B：每日经营报表刷新，数据迟到与系统升级

输入为经营指标正式定义、数据更新承诺、报表范围、事件/日历、预算、通知对象和已验证组合。DA14.1 定义每日触发和数据就绪谓词；到点但流水迟到时输出未就绪及 DA14.2 新鲜度告警，不提交假定完整的数据计算。数据到达事件经持久去重后生成 RunRequest，DA07 实际提交计算/物化作业；涉及物化复用数据层 DA13。DA14 查询展示引用 DA07 状态，外部报表服务回执跨天则存 WaitRef。

DA17 的默认指标/程序/策略组合用于新任务装配，任务实际版本写入 DA04.5。系统升级改变 UI 或 API 时，DA14.8.1 产生漂移报告并按允许策略暂停受影响入口；不能自动改契约。指定新实现经 DA15 声明、DA18 装配、DA11 重验，通过 DA12.7 变更计划后 DA17 预检、部署、健康核对。回退如只覆盖代码，回执必须列出未回退数据。已有断点恢复前先核对旧作业是否已完成，DA07 对账已发送的报表，避免再次发同一份。

输出为带实际数据/语义/程序版本的报表、真实作业/投递回执、迟到或漂移说明、成本账本及可读操作手册。DA18.5 以基线比较客户制表工时和错误率；刷新速度属于系统指标，单独报告。建设先实现“定时/事件就绪→真实作业→报告/通知”的切片，再补齐迟到/重复事件/恢复与预算暂停，最后加入受控升级和客户接管；每片核验未就绪不运行、重复事件不重放、副作用未知先对账。

## 6. 代码与交付组织

推荐拟议 Python 工作区 `packages/capabilities/dataagent-operations/`，命名空间 `dataagent_operations.*`。模块目录为 `continuity / action_contracts / delegation / environments / delivery`，二级组先对应一个文件，原子对应显式请求/返回类型及 handler。共用类型和端口隔离平台/存储/执行/GUI/TUI 适配；详见[目录树、端口和依赖规则](https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke)。当前仅创建设计文稿，没有实现或注册运行工具。

编号、handler、Agent 工具、算法后端、安装发行包各自管理。一个发布包可聚合多项原子；同原子可有多个等价实现；重型部署/模型/渠道适配按需安装。实际发行平台描述后续验证，本目录 JSON 是本项目注册草案。

## 7. 核对与依据

- 权威范围：[revision 1022 完整 XML 快照](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)，对应[飞书规划](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)。本地初稿未向飞书回写；本导入版由用户授权发布。
- 基础约定：[数据层总览](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)、[共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)、[代码目录](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)。
- 目录覆盖：DA14 20、DA15 14、DA16 17、DA17 18、DA18 22，共 91；能力组分别 8/4/5/5/7，共 29。逐项 ID/名称、唯一 operation、I/O、边界、组文件与入口由机器清单可复核。

精确字段类型、正式 JSON Schema、后端事务与性能容量在实现前收敛。需要保留的契约已经明确：真实执行/决定/观测可追溯，草案/发布/授权/执行/验收分别表达，任务修订只有 DA04.5 一份权威状态。

# 持续运行与 FDE 交付层代码目录提案 v0.1

本文件仅定义拟议代码归属，**未创建以下工作区或实现**。Python 命名空间为 `dataagent_operations.*`，业务逻辑只依赖共享类型与注入端口；跨层通过契约和端口协作，不导入数据、执行、治理层内部 runtime。基础对象复用[数据层共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)，跨层集成在[总体约定](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)收敛。

## 1. 推荐目录树

```text
packages/capabilities/dataagent-operations/        # 拟议 Python 工作区
├── README.md
├── pyproject.toml                                # contracts + 按需功能/后端依赖
├── uv.lock
├── contracts/generated/                         # 从权威类型生成 schema
├── src/dataagent_operations/
│   ├── contracts/
│   │   ├── common.py                            # 引用共享 CallContext/Result，避免重定义
│   │   ├── continuity.py                        # Trigger/RunRequest/Wait/Checkpoint/Alert/ResultSubscription
│   │   ├── action_contracts.py                  # ActionContract、执行要求、影响估计
│   │   ├── delegation.py                        # Identity/Delegation/Decision/EvidencePackage
│   │   ├── environments.py                      # EnvironmentDefaults/ContextEnvelope/Deployment
│   │   └── delivery.py                          # Skill/Bundle/Runbook/Outcome/交付清单
│   ├── continuity/                              # DA14
│   │   ├── triggers.py                          # DA14.1 2 原子
│   │   ├── data_monitors.py                     # DA14.2 3 原子
│   │   ├── metric_monitors.py                   # DA14.3 2 原子
│   │   ├── notifications.py                     # DA14.4 2 原子
│   │   ├── budgets.py                           # DA14.5 2 原子
│   │   ├── waits.py                             # DA14.6 3 原子
│   │   ├── teams.py                             # DA14.7 3 原子
│   │   └── drift.py                             # DA14.8 3 原子
│   ├── action_contracts/                        # DA15
│   │   ├── tiers.py                             # DA15.1 3 原子
│   │   ├── declarations.py                      # DA15.2 4 原子
│   │   ├── execution_requirements.py            # DA15.3 4 原子
│   │   └── catalog.py                           # DA15.4 3 原子；动作元数据，非相关性检索
│   ├── delegation/                              # DA16
│   │   ├── identities.py                        # DA16.1 3 原子
│   │   ├── approvals.py                         # DA16.2 5 原子
│   │   ├── supervision.py                      # DA16.3 4 原子
│   │   ├── separation.py                        # DA16.4 3 原子
│   │   └── burden.py                            # DA16.5 2 原子
│   ├── environments/                            # DA17
│   │   ├── registry.py                          # DA17.1 3 原子
│   │   ├── defaults.py                          # DA17.2 4 原子
│   │   ├── contexts.py                          # DA17.3 3 原子
│   │   ├── arbitration.py                       # DA17.4 3 原子
│   │   └── deployment.py                        # DA17.5 5 原子
│   ├── delivery/                                # DA18
│   │   ├── runbooks.py                          # DA18.1 3 原子
│   │   ├── self_service.py                      # DA18.2 3 原子
│   │   ├── knowledge_transfer.py                # DA18.3 3 原子
│   │   ├── operating_agreements.py              # DA18.4 4 原子
│   │   ├── outcomes.py                          # DA18.5 3 原子
│   │   ├── skills.py                            # DA18.6 3 原子
│   │   └── bundles.py                           # DA18.7 3 原子
│   ├── ports/                                  # 行为协议；不包含跨层内部实现
│   │   ├── repositories.py                     # 版本对象、内容、事件、关系与并发控制
│   │   ├── scheduling.py                       # 平台调度、持久等待/事件、任务控制
│   │   ├── execution.py                        # DA07 提交/查询/取消/预演/对账与回执
│   │   ├── governance.py                       # DA12 政策/授权约束、版本发布/审计/变更
│   │   ├── identity.py                         # 身份校验、委托链/撤销状态、凭据代理
│   │   ├── data_and_semantics.py               # DA01/02/03 来源/结构/定义/基线服务
│   │   ├── task_context.py                     # DA04.5 真实任务修订、影响标记与资产保存
│   │   ├── discovery.py                        # DA05.8 组件/动作召回
│   │   ├── analysis_and_generation.py           # DA08 分析与程序生成
│   │   ├── validation.py                       # DA11 实际评测/验收/门禁
│   │   ├── notifications.py                    # 平台投递/回执，渠道受控绑定
│   │   ├── deployment.py                       # 包构建/探测/安装/健康/回退
│   │   └── interaction.py                      # GUI/TUI 自拟任务/监督/报告交互端口
│   ├── adapters/
│   │   ├── storage/                            # 本地 SQLite/内容存储，后续企业存储
│   │   ├── platform/                           # 时钟/调度/事件/任务控制/投递提供方
│   │   ├── services/                           # 跨层服务客户端，严格经公开契约
│   │   ├── deployment/                         # 离线包、进程/容器等可选执行后端
│   │   └── interaction/                        # GUI/TUI 桥接，尚无平台绑定承诺
│   ├── registry/
│   │   ├── catalog.py                          # ID → operation、handler、I/O 类型和依赖
│   │   └── loader.py                           # 按任务与环境装配依赖和可替换实现
│   └── interfaces/
│       ├── python_api.py
│       ├── cli.py
│       ├── http.py
│       └── mcp.py
├── component-specs/                            # 项目自拟描述，非正式发行平台 manifest
│   ├── continuity.yaml
│   ├── action-contracts.yaml
│   ├── delegation.yaml
│   ├── environments.yaml
│   └── delivery.yaml
├── presets/                                    # 可调整组合示例，不是唯一执行主链
│   ├── lingcai-audit-delivery.yaml
│   └── daily-report-refresh.yaml
├── packaging/                                  # 实际发行平台后续适配
├── examples/
└── tests/
    ├── contracts/                              # 同能力不同后端的共同契约
    ├── continuity/                             # 事件去重、迟到/等待、并发恢复与未知副作用
    ├── action_contracts/                       # 分档/绑定、发布、执行要求不越界
    ├── delegation/                             # 过期/撤销、证据与授权、免审/权责分离
    ├── environments/                           # 默认/任务修订、缺快照、部署部分失败
    ├── delivery/                               # Skill 可替换、依赖闭合、验收/效果限制
    ├── adapters/                               # 真实提供方特性及失败回执
    └── scenarios/                              # 独立业务样本端到端验收
```

原子 ID、逻辑调用名、源文件和完整 `module:function` 入口以 [atomic-capability-catalog.json](https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke)逐项对应。29 个组文件分别容纳显式 `OperationInput/Output` 类型和 handler；复杂实现可展开子包，ID 保持稳定。包级导入只暴露公开类型和注册入口，不借助万能字典掩盖逐项 I/O。

## 2. 端口调用与权威状态

| 设计端口 | 消费者与交换对象 | 实现/权威边界 |
|-|-|-|
| `SchedulerPort / EventWaitPort / TaskControlPort` | DA14 的 TriggerSpec、WaitRef、Checkpoint、控制/恢复回执；DA18 自助发起与查询 | 平台负责计时、投递和编排控制；DA14 决定数据是否就绪、等待条件是否满足，DA07 独占作业生命周期权威 |
| `ExecutionPort` | JobRef、真实状态/回执、预演结果、对账/补偿请求 | 跨层 DA07 服务；调用失败或未知不能在本层填造成功，恢复不得绕过幂等/对账 |
| `PolicyPort / AuthorizationPort / IdentityPort` | 正式政策/版本、有效主体/委托链、授权决定和撤销状态 | DA12/身份服务提供治理约束，DA16 做政策约束下的审批/免审与证据装配；执行点 DA07 重查有效授权 |
| `RepositoryPort / ContentPort / TracePort` | 精确版本、条件写入、真实事件/来源、持久引用解析 | 复用存储契约；Wait/Approval 的事件消费、决定绑定与恢复令牌须可去重/并发保护，禁止静默覆盖历史 |
| `TaskContextPort / ArtifactPort` | TaskContextRef、修订提案/回执、受影响结果标记、已验证资产 | DA04.5 权威维护任务状态，DA04 保存轨迹/资产；DA17 只保存环境默认及装配产物 |
| `DataObservationPort / SemanticPort / BaselinePort` | 数据到达/结构、规则/定义、口径冲突与业务基线 | DA01/02/03 实际能力；不导入其存储或解析器内部模块，保留来源版本和观测局限 |
| `DiscoveryPort / AnalysisPort / GenerationPort` | 动作/组件候选、分析请求、程序草案和失败修复 | DA05.8 与 DA08；目录登记不兼做召回，代码生成不兼做正式业务验收 |
| `ValidationPort / PublicationPort / ChangePlanPort` | 独立验收报告/门禁、正式发布与变更计划、可重现检查 | DA11/DA12；本层消费可核验报告与回执，不伪造通过，不声明缺快照的历史可重现 |
| `NotificationPort` | 订阅、允许披露范围、去重键、实际投递回执 | 平台渠道适配；通知与升级本身不授予业务权限，订阅登记与已送达分开 |
| `DeploymentPort` | 锁定依赖/离线包、环境预检、安装/健康/回退回执 | 受控部署后端；引擎离线产物复用 DA07.10.1，升级需要 DA12.7 计划，不承诺管理客户基础设施 |
| `SupervisionPort / ReportPort` | 执行观察、差异候选、开放回复、审批/撤销请求、报告视图 | 自拟交互协议；GUI/TUI 适配器只调端口，正式决策、任务修订与执行控制仍由权威模块处理 |

## 3. 依赖装配与界面边界

```text
GUI/TUI 或 Python/HTTP/MCP 入口
                ↓
Registry + 自拟 Interaction Ports
                ↓
DA14 / DA15 / DA16 / DA17 / DA18 handlers
                ↓
共享契约 + 注入的服务/存储/执行/平台端口
                ↑
平台、跨层服务、存储、部署、投递等适配器
```

组合根负责注入，能力函数不得主动创建别层 runtime。DA14.7 调用上下文派发端口取得 DA17.3 装配结果；DA17 装配调用 DA04.5 公开任务修订端口；DA18 自助请求经 TaskControl/Supervision/Report 端口分发。DA16 监督视图也通过这些端口消费真实状态和提交请求，不能直接写 DA07/DA04 数据表，避免 UI 或本层成为第二个状态机权威。

首版可共用本地版本对象库和追加事件日志，保留条件写入、事件 ID 去重、审批参数 digest 和恢复令牌原子消费。外部副作用无法纳入本地事务时，使用持久请求/回执关联及 DA07 对账；不要声称跨系统 exactly-once。运行数据在显式受控 `data_root` 或企业存储，敏感原件/凭据不入代码仓库或普通日志。

动作业务含义、执行要求和实际执行沿不同端口协作；ActionContract 发布后仍不创建执行许可。GUI/TUI 可显示候选、依据、限制，并接收选择、纠正和自由说明；这些是交互数据，实际授权、生效修订、撤销执行分别验证。这里未验证任何既有 GUI/TUI 或发行平台接口，接入需独立适配测试。

## 4. 发布粒度与建设顺序

建议先一个工作区，以五个模块为依赖/测试分组。共享契约、持续运行、动作契约、人在环、环境部署、交付可按实际部署边界产生多个安装产物；重型模型、部署后端和渠道 SDK 均可选加载。能力 ID、函数、工具暴露、实现后端与发行包不同粒度，一个包可包含多项能力，同一能力可替换实现。

先完成可检查的 I/O 类型、真实回执与版本解析，再按 [README 场景切片](https://modelbest.feishu.cn/docx/NqS0dcV0CoaatHxJTTFc7amnnke)形成可运行闭环。实现验证优先覆盖“证据够但无授权”“免审政策有效无需额外签字”“任务固定版本不随环境默认变化”“未知副作用不重放”“只对受影响结果重验”“方法替换后端到端效果仍验收”这些会改变业务结果的边界。

# 机器可读能力目录

附本地接口与源码入口映射 JSON；本项目自拟目录，不是发行平台正式 manifest。

<figure view-type="Preview"><source name="dataagent-operations-fde-layer-v0.1-atomic-capability-catalog.json" mime="application/json" size="62731" token="O50db93TEoEq2ux47sgcIGCDnId"/></figure>