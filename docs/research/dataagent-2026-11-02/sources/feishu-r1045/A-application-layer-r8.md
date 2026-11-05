<title>DataAgent 执行应用层：模块与原子能力接口设计 v0.1</title>

本篇整合本地 v0.1 分层设计的模块接口、共享契约、代码目录及组合示例。能力编号基于主规划 revision 1022；本文为设计稿，尚未创建运行时代码。

[返回 Pluggable DataAgent 总规划与分层索引](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)

# DataAgent 执行应用层设计草案 v0.1

目标：让 Agent 从问题、表、列、值、文档、经验或已有组合任意入口出发，按实际发现检索、编译、执行、分析、预测和交付；方法、代码与组件允许更换，业务目标、正式验收和权限边界由有权主体确定。本版是供整体讨论的本地设计文稿，不创建实现代码，也不向飞书回写。

本版依据 [revision 1022 XML 快照](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)，保留 **DA05–DA10，6 个模块、39 个能力组、116 项原子能力**。新增的是接口与代码归属提案，没有新增能力编号。完整机器可读映射见 [atomic-capability-catalog.json](https://modelbest.feishu.cn/docx/ReDXdJzLWoihZDxqaO0clUxInKf)；工作区、适配端口与依赖方向见 [code-layout.md](https://modelbest.feishu.cn/docx/ReDXdJzLWoihZDxqaO0clUxInKf)。本版不作实际 Mint/iface 兼容判断。

其他层级及跨层交接见 [DataAgent 分层设计总导航](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)。

## 1. 模块范围与总体输入输出

| 模块 | 总输入 | 总输出 | 能力组 / 原子 |
|-|-|-|-|
| DA05 召回检索 | 问题或表/列/值/文档/对象种子、可见域、版本/时间、候选适用条件 | 带来源、版本、匹配依据与覆盖范围的候选；依赖路径和适用性判断 | 8 / 24 |
| DA06 语义查询与计算计划 | 问题、召回候选、固定语义、后端事实、执行/验证反馈和业务约束 | 绑定需求、逻辑/执行计划及修订、SQL/API/表达式、动作与契约草案 | 7 / 25 |
| DA07 计算执行 | 已确定表达/程序/计划、输入版本、运行目标、授权/审批、幂等键与预算 | 实际执行回执、结果/产物、逐项变更状态、作业/对账/一致性报告 | 10 / 28 |
| DA08 分析 | 问题、结果表/关系、统计前提、程序要求、执行/评测反馈 | 分析计划、描述/统计/关系结果、解释与假设、程序/公式/检查草案 | 6 / 18 |
| DA09 预测、仿真与优化 | 历史数据、外生情景、模型假设、目标/约束、偏好与资源预算 | 条件预测/区间、情景结果、可行解/不可行依据、方案比较与权衡 | 4 / 9 |
| DA10 表格、可视化与交互 | 结果及依据、展示/导出要求、用户纠正、当前任务版本与授权 | 工作簿/图表/报告/看板、纠正定位、实际任务修订与刷新结果 | 4 / 12 |

DA06.6/7、DA07.7/8/9 保留原规划的 FDE 适用标记，按任务启用，不要求普通文件分析部署全套动作治理。DA07.10 是通用引擎接入与一致性能力，不限定某一种规则表达式或某个旧引擎。

## 2. 共享契约与新增业务对象

统一调用：`invoke(operation, input, CallContext) -> CapabilityResult<T>`。每项原子表格中的输入只列业务参数；共同身份、作用域、授权、请求、任务、预算、截止时间、并发检查及幂等参数沿用 [数据层共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)。`status=ok/partial/needs_input/pending/failed` 表示本次能力运行状态，不等于结论被验证、动作已生效或方案获业务批准。

`AssetRef / TableRef / DataBatchRef / SourceAnchor / SemanticRef / MappingRef / EvidenceRef / ArtifactRef / MemoryRef / TaskContextRef / ValidationReportRef` 等基础引用只复用数据层定义；本层不再复制一套。大内容通过受控资源引用传递，版本、来源和完整性随中间结果传递。未命中、无权限、未知、空结果、执行失败分别表达；采样/首屏/截断不能标记全量。检索的相关性分数、模型置信度和统计显著性均不能充当业务认证。

以下对象是本草案新增的业务协议，不宣称已有平台实现；实现类型拟置于 `src/dataagent_application/contracts/`。对象内的业务词表与 `CapabilityResult.status` 分开，正式 JSON Schema 留待实现前细化。

| 对象 | 字段草案 | 状态与边界 |
|-|-|-|
| `FieldRef / ValueHit` | `table_ref, field_id, source_path, schema_revision`；取值另含 `value, match_mode, anchors, coverage` | 值可脱敏或受控引用；反查返回实际位置，不创造完整结构 |
| `SearchHit<T>` | `target, source_revision, score?, scoring_method?, match_reasons[], anchors[], applicability?, index_as_of, coverage` | 相关性不代表可信；返回对象保持其候选/草案/已验证原状态 |
| `DependencyPath` | `start_ref, end_ref, edges[], edge_kinds[], coverage, missing_or_hidden` | 区分数据/语义依赖、实体关系、物理映射、产物来源；只读已存关系 |
| `ComponentCandidate` | `coordinate, version, capability_ids[], implementation_ref, io_contract_refs[], dependencies[], runtime_requirements, permission_requirements, validation_refs[]` | 适用性 `applicable/inapplicable/needs_confirmation` 是匹配结果，不是安装或授权许可 |
| `RequirementSpec / Ambiguity` | `metrics[], dimensions[], time, filters, grain, bindings[], assumptions[], unresolved[]`；歧义含 `alternatives, result_impact, blocking` | 显式假设可先算，正式口径不得私自生效；澄清支持自由回答 |
| `LogicalPlan / ExecutableSpec` | `steps, dependencies, semantic_versions, source_bindings, output_schema`；执行表达另含 `backend_kind, expression_or_call, parameters, required_capabilities` | 计划与表达是待执行产物；不是已经发生的调用，不限定 SQL 后端 |
| `ExecutionPlan / PlanRevision` | `plan_id, revision, parent_revision?, dag, target_bindings, intermediate_schemas, completeness_gates, failure_policy, change_reasons[], invalidated_results[]` | 方法、实现、子任务可替换；必须保留原业务目标/验收引用及差异 |
| `ActionPlanDraft / ContractDraft` | `actions_or_states, transitions, preconditions, postconditions, human_steps, waits, branches, criteria_ref, unresolved[]` | `draft/proposed` 与已发布契约分开；授权/确认由 DA15/16，不能据草案直接写入 |
| `ExecutionReceipt / MutationReceipt / ActionReceipt` | `invocation_id, request_id, implementation_ref, input_versions, target_ref, remote_request_id?, per_item[], observed_before_after, result_refs[], verification_refs[]` | 领域执行态 `accepted/running/succeeded/failed/partially_succeeded/unknown`；受理/工具成功不等于业务完成 |
| `ReconciliationReport / TaskRevisionReceipt` | 对账含 `request_keys, observations, per_item_effects, as_of, allowed_next_steps`；任务修订含 `parent/new_context, actual_change_receipts, affected_outputs, revalidation_set` | 对账态 `applied/not_applied/partial/unknown`；修订只在实际持久化后有新版本，未知副作用不重放 |
| `JobRef / JobSnapshot` | `job_id, submission_key, status/read/cancel_refs`；快照含 `observed_state, progress, partial_result_refs, final_refs, continuation` | 作业态 `accepted/queued/running/waiting/succeeded/failed/cancelled/unknown` 是观测，不是业务状态；跨轮恢复归 DA14.6 |
| `EngineBinding / EngineConsistencyReport / DegradationRecord` | 实际坐标/版本/digest、运行要求；样本/标准版本、逐项 diff；替代原因/已知差异/覆盖 | 引擎可运行、一致性通过与业务验收是三个结论；降级记录不豁免正式标准 |
| `AnalysisPlanDraft / Explanation / AnalysisResult` | 子问题/方法/前提/验证步骤；事实/假设分栏、数值/依据/局限；结果含方法、样本范围、单位和不确定性 | 计划/假设/已验证结论分别表达，关系分析不完成实体对齐 |
| `ProgramDraft / ValidationProgramDraft` | `content_ref, language, input_output_contracts, dependencies, component_bindings, requirements_ref, revision_parent?, change_summary, validation_status` | `generated/executed/validated/rejected` 为程序成熟度；生成检查程序不等于独立验收通过 |
| `ForecastResult / ScenarioResult / OptimizationResult` | 数据/模型版本、跨度/情景/种子、输出/区间；求解另含目标/约束、solution、bound/gap、solver_status | 预测/仿真受假设约束；求解态 `optimal/feasible/infeasible/unbounded/unknown` 不等于业务方案已选或执行 |
| `ChartSpec / ReportDraft / DashboardSpec` | 数据/语义/计算引用、编码/布局、过滤/联动、时间/完整性、格式/部署需求、可访问性说明 | 生成、导出、部署、公开分享分别表达；草案不自动发布 |
| `CorrectionIntent / ChangeProposal` | 原话/锚点、候选目标/旧版本、拟改字段/口径、作用域、实际影响、确认/授权依据 | `proposed/needs_clarification/confirmed/applied/rejected` 与任务修订、执行态分开；定位后仍需真正更新资产/任务 |

SQL、代码、函数和 API 按实际副作用分类；写 SQL、存储过程、可写代码/函数与 API 写回统一经过 DA07.7 执行控制。代码通过受限挂载、网络/工具能力和受控动作代理落实权限，无法确认副作用边界不得视为只读。基础协议未来可提取到共同契约包；本层 contracts 只持有特有类型，治理层不导入应用层实现。

通用重试只用于已确认可安全重试的只读操作。副作用请求遇到 `timeout/execution_unknown`、作业受理未知或部分成功时，先用请求号、幂等键和目标状态查询/对账；不存在“超时就没写入”的默认假设。幂等保存请求 digest，重复同键返回原回执，同键异参拒绝。所有改动保留预期旧版本与逐项结果。

## 3. 模块、能力组与原子接口

每个能力组先列职责、边界及拟议文件；每个原子分别列业务输入、输出、作用边界和调用名。代码文件相对拟议工作区 `packages/capabilities/dataagent-application/`。函数入口完整规则是 `dataagent_application.<模块目录>.<能力组文件>:<operation>`，精确逐项值已在 JSON 中列出。

### DA05 召回检索

#### DA05.1 表格/数据库检索（软）

职责：检索数据集、表、列和取值，支持值反查列或表。 边界：可从表、列、值任意入口检索并按需扩展关联；血缘仅是可选线索，不假定能补出完整结构。

组输入输出：问题或条件 → 候选表/字段/取值。拟议文件：`src/dataagent_application/retrieval/tables.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.1.1 表/数据集召回  <br/>`retrieve_tables` | 问题文本或 table_ref/field_ref/value_seed、来源范围、时间范围、top_k | SearchHit<TableRef/ResourceRef>[]；匹配理由、结构摘要、命中字段/值与可选关系线索 | 允许从表、列或值开始；只召回可见候选，不假设血缘能补齐全库结构。 |
| DA05.1.2 字段召回  <br/>`retrieve_fields` | 问题或字段名/样例值、可选 table_refs、字段类型/单位约束、top_k | SearchHit<FieldRef>[]；所属表、稳定字段 ID、类型、语义候选与匹配依据 | 无需先选表；字段相似性不代表业务口径相同，权限过滤在排序前生效。 |
| DA05.1.3 取值召回与反查  <br/>`retrieve_values_and_locations` | 值字面量或 value_ref、精确/模糊匹配模式、可选来源/表/列范围、类型与归一化规则 | ValueHit[]；实际值、表列位置、受控样例锚点、匹配方式和扫描覆盖范围 | 支持值反查列和表；采样未命中不等于值不存在，不输出越权敏感值。 |

#### DA05.2 业务语义检索（软）

职责：查找实体、指标、规则、业务关系和对应数据映射。 边界：不创建或修改业务定义。

组输入输出：问题 → 候选实体/指标/规则。拟议文件：`src/dataagent_application/retrieval/semantics.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.2.1 实体召回  <br/>`retrieve_entities` | 问题、实体别名/类型、业务域、有效时间、top_k | SearchHit<SemanticRef>[]；实体定义版本、别名、适用域、来源与匹配解释 | 读取已有定义，不创建实体、不做实体记录对齐。 |
| DA05.2.2 指标召回  <br/>`retrieve_metrics` | 问题、度量对象、维度/单位/时间粒度约束、有效时间 | SearchHit<SemanticRef>[]；指标公式摘要、口径版本、适用范围与未决冲突 | 候选指标不自动成为当前任务正式口径，绑定由 DA06/任务上下文完成。 |
| DA05.2.3 业务规则召回  <br/>`retrieve_rules` | 问题、业务对象类型、规则主题、适用条件、有效时间 | SearchHit<SemanticRef>[]；规则版本、条件摘要、例外与来源锚点 | 检索规则不执行规则，也不裁决冲突规则的优先级。 |
| DA05.2.4 关系与映射召回  <br/>`retrieve_relationships_and_mappings` | 实体/指标/规则引用或问题、关系类型、目标来源和有效时间 | 关系与 MappingRef 候选；端点版本、物理绑定、路径和覆盖缺口 | 只读已有关系与映射；语义关联、数据依赖和物理绑定分类型返回。 |

#### DA05.3 记忆检索（软）

职责：找回历史任务、经验、用户纠正及已验证查询。 边界：区分原始轨迹、候选经验和已确认记忆。

组输入输出：当前任务 → 相关历史与经验。拟议文件：`src/dataagent_application/retrieval/memories.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.3.1 历史任务召回  <br/>`retrieve_historical_tasks` | 当前问题、任务类型、来源/业务域、历史时间窗、top_k | SearchHit<TraceEventRef/TaskContextRef>[]；相似任务、实际结果引用和可复用原因 | 历史成功不能保证本次成功；隐藏不可见任务内容，保留历史版本和当时约束。 |
| DA05.3.2 经验召回  <br/>`retrieve_experiences` | 任务摘要、失败症状/方法需求、作用域、允许的记忆可信状态 | SearchHit<MemoryCandidate/MemoryRef>[]；经验、适用条件、依赖和验证引用 | 候选经验、已确认记忆分别标记；不在检索中晋升可信状态。 |
| DA05.3.3 用户纠正召回  <br/>`retrieve_user_corrections` | 当前对象/口径引用、用户/租户作用域、纠正主题、有效时间 | SearchHit<CorrectionRef>[]；原话引用、修正对象、范围及后续处理记录 | 个人偏好不得自动传播为企业规则；原始纠正与已生效修订分开。 |
| DA05.3.4 已验证查询召回  <br/>`retrieve_validated_queries` | 计算需求、来源 schema/方言、指标版本、验证要求 | SearchHit<ArtifactRef>[]；查询版本、参数槽、依赖版本、ValidationReportRef 和适用限制 | 必须有可解析验证依据；历史查询仍须检查本次 schema、权限与口径。 |

#### DA05.4 文档检索（软）

职责：从制度、手册、数据说明等内容中查找相关段落。 边界：不把相似段落直接当作业务结论。

组输入输出：查询 → 相关段落 + 锚点。拟议文件：`src/dataagent_application/retrieval/documents.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.4.1 文档关键词检索  <br/>`search_document_keywords` | 关键词/布尔条件、文档集合、语言、章节/时间过滤、分页游标 | SearchHit<DocumentUnitRef>[]；命中片段、SourceAnchor、上下文引用和续页信息 | 保留实际词项与定位；检索片段不直接构成制度判断或证据存储动作。 |
| DA05.4.2 文档语义检索  <br/>`search_document_semantics` | 自然语言问题、文档集合、语义模型要求、上下文窗口与 top_k | SearchHit<DocumentUnitRef>[]；相关片段、锚点、父章节和相似度方法 | 相似度是相关性估计；跨段条件/例外需连同上下文读取，不确认最终答案。 |

#### DA05.5 分析资产检索（软）

职责：查找代码、模型、函数、报表和方法模板。 边界：检索已有程序、模型和分析产物；组件包与业务 Skill/Preset 入口归 DA05.8，可复用相同索引。

组输入输出：问题 → 可复用代码/模型/模板。拟议文件：`src/dataagent_application/retrieval/analysis_assets.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.5.1 分析代码/函数召回  <br/>`retrieve_analysis_programs` | 任务要求、输入输出 schema、运行语言/环境、依赖限制 | SearchHit<ArtifactRef>[]；代码/函数、签名、依赖、适用条件与验证记录 | 只查既有程序；不安装、生成或执行，参数兼容仍需检查。 |
| DA05.5.2 模型召回  <br/>`retrieve_models` | 预测/分析目标、特征 schema、目标频率、模型类型与运行环境 | SearchHit<ArtifactRef>[]；模型版本、训练范围、特征约束、评测和限制 | 模型可被召回不代表适用于新分布，不承诺预测效果。 |
| DA05.5.3 报表/模板召回  <br/>`retrieve_reports_and_templates` | 交付问题、目标格式、受众、已有结果 schema、适用域 | SearchHit<ArtifactRef>[]；报表/模板、参数槽、依赖指标和来源 | 报表内容沿用其时点与口径；不把旧数值填充为本次结果。 |

#### DA05.6 检索重排（软）

职责：对多个检索来源的候选去重、排序和筛选。 边界：不承担证据存储或最终答案验证。

组输入输出：候选集 → 排序后候选。拟议文件：`src/dataagent_application/retrieval/ranking.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.6.1 候选去重  <br/>`deduplicate_candidates` | 来自各召回源的 SearchHit[]、身份/版本键、去重策略 | 去重候选列表、合并来源、重复簇和保留代表说明 | 不合并不同版本或口径冲突对象；候选去重不删除源资产。 |
| DA05.6.2 相关性重排  <br/>`rerank_candidates` | 问题、候选列表、相关性准则、任务约束、重排预算 | 排序候选、分项评分、筛除原因、截断范围和方法版本 | 不以排序代替业务验证；不存储证据，不修改候选授权或可信状态。 |

#### DA05.7 血缘查询（软）

职责：按授权范围查询数据、语义和产物的依赖路径。 边界：只读取已有关系，注明版本与覆盖范围，不采集血缘，也不判定业务影响。

组输入输出：对象 → 上下游依赖。拟议文件：`src/dataagent_application/retrieval/lineage.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.7.1 上游来源追溯  <br/>`trace_upstream_dependencies` | 对象版本引用、允许的 edge_kind、深度、时间/范围限制 | DependencyPath[]；上游端点版本、声明/推断/观测依据和缺边说明 | 只查已有边，不采集血缘、不根据缺边推断来源不存在。 |
| DA05.7.2 下游依赖查找  <br/>`find_downstream_dependencies` | 对象版本引用、边类型、深度、可见域、分页参数 | DependencyPath[]；下游对象版本、路径、覆盖范围和不可见边提示 | 结果表示可见依赖，不自动判定业务影响或使资产失效。 |
| DA05.7.3 语义到物理实现追溯  <br/>`trace_semantic_implementations` | SemanticRef、目标来源/运行环境、有效时间、映射版本要求 | MappingRef[] 与物理表列/API/函数端点；未绑定项与覆盖缺口 | 只解析已有语义映射，不临时创造业务定义或假定绑定可执行。 |

#### DA05.8 组件与 Skill/Preset 检索（软）

职责：按任务、业务环境与适用条件检索组件包、Skill、Preset 及其可替换实现。 边界：复用能力目录及包元数据；只检索筛选，不安装执行，不承担目录存储或授权判定。

组输入输出：任务与环境约束 → 候选组件与适用说明。拟议文件：`src/dataagent_application/retrieval/components.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA05.8.1 组件与实现召回  <br/>`retrieve_components_and_implementations` | 任务能力需求、I/O 类型、运行环境、允许实现与版本约束 | ComponentCandidate[]；组件坐标、能力 ID、替代实现、依赖和验证元数据 | 能力 ID 不等于发行包；检索不安装、不执行、不决定授权。 |
| DA05.8.2 Skill/Preset 召回  <br/>`retrieve_skills_and_presets` | 业务问题、交付/验收要求、已有能力、环境和复用范围 | Skill/Preset 候选；方法指导、组合引用、可替换点、依赖和适用说明 | Skill 指导允许调整方法，不把历史调用次序当成唯一流程。 |
| DA05.8.3 适用条件筛选  <br/>`filter_component_applicability` | ComponentCandidate[]、实际来源能力、运行环境、依赖版本、已有授权决策引用 | 候选适用性 Assessment[]；适用/不适用/待确认、缺失依赖与权限需求 | 比较声明和事实，不自行授予权限；权限需求匹配不替代 DA12/DA16 授权。 |

### DA06 语义查询与计算计划

#### DA06.1 计算需求解析（软）

职责：识别计算目标、业务对象、条件和结果粒度。 边界：所需数据、语义和函数由 DA05 召回。只对影响结果的歧义发起澄清；可以按明确标注的默认假设先算，用户回答后更新绑定。

组输入输出：问题 → 指标/维度/过滤/时间。拟议文件：`src/dataagent_application/planning/requirements.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.1.1 指标与维度绑定  <br/>`bind_metrics_and_dimensions` | 问题、召回的指标/实体/字段候选、目标粒度、已有 TaskContextRef | RequirementSpec；指标/维度绑定、候选未定项、单位、采用假设与来源 | 只绑定已有定义；多义未定不得伪装成正式指标，后续回答可更新绑定。 |
| DA06.1.2 时间与过滤解析  <br/>`parse_time_and_filters` | 问题、时区/日历、业务时间字段、字段 schema、默认时间政策 | 时间区间、边界开闭、过滤 AST、参数值与明确标注的默认假设 | 区分业务时间与记录时间；默认值须可追溯，不能暗中缩小任务范围。 |
| DA06.1.3 计算歧义识别  <br/>`identify_calculation_ambiguities` | RequirementSpec、候选口径/映射、数据覆盖与现有假设 | Ambiguity[]；受影响结果、候选解释、差异依据和阻塞级别 | 只报告会影响结果的歧义；允许安全且显式的假设，不强制所有未知都阻塞。 |
| DA06.1.4 澄清问题生成  <br/>`generate_clarification_questions` | 关键 Ambiguity[]、候选解释及证据、受众、已问问题 | 澄清问题、可选解释、各自影响、开放补充入口与可暂用假设 | 选项不能封死自由回答；不代用户决定正式口径或反复询问已知信息。 |

#### DA06.2 业务语义编译（软）

职责：将已有指标、规则、关系和单位展开为计算步骤。 边界：物理实现可以是表列、业务接口或函数，不临时创造业务定义。

组输入输出：需求 → 语义展开后的逻辑计划。拟议文件：`src/dataagent_application/planning/semantic_compilation.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.2.1 指标计算展开  <br/>`expand_metric_calculation` | RequirementSpec、固定版本指标定义、物理映射、单位与时间规则 | LogicalPlan；基础计算 DAG、源绑定、派生公式、依赖版本和未解析符号 | 展开已有语义，可落表列/API/函数；缺定义回 DA03，不凭模型编造。 |
| DA06.2.2 关系与约束展开  <br/>`expand_relationships_and_constraints` | LogicalPlan、关系定义版本、基数/时态/过滤/单位约束 | 扩展 LogicalPlan；连接/约束步骤、键映射、基数风险及检查要求 | 不把候选 Join 当确认关系；保留时态、行级范围与多对多风险。 |

#### DA06.3 执行表达生成（软）

职责：根据目标后端生成 SQL、接口参数、函数调用或表达式；需要 Python 等程序时复用 DA08.6，不另建代码生成能力。 边界：不执行，只使用已知接口和可用运行环境。

组输入输出：逻辑计划 → SQL / API 调用 / 表达式。拟议文件：`src/dataagent_application/planning/expressions.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.3.1 单表 SQL 生成  <br/>`generate_single_table_sql` | 单表 LogicalPlan、schema 版本、目标 SQL 方言、参数绑定约束 | ExecutableSpec；参数化 SQL、输出 schema、读取范围和不支持项 | 只生成不执行；目标后端实际支持 SQL，参数不以内联拼接代替绑定。 |
| DA06.3.2 多表 SQL 生成  <br/>`generate_multi_table_sql` | 多表 LogicalPlan、关系/Join 版本、目标方言、授权可读范围 | 参数化 SQL、连接条件、预期粒度、重复计数风险和输出 schema | 未知 Join 键或口径冲突保持未决；不得静默用笛卡尔积完成查询。 |
| DA06.3.3 SQL 方言转换  <br/>`translate_sql_dialect` | 源 SQL/方言、目标方言与版本、schema/函数能力、等价性要求 | 目标 SQL、变换清单、语义差异与待验证样例要求 | 不支持的函数/NULL/时间语义显式报告，语法可转换不代表语义已等价。 |
| DA06.3.4 API/MCP 调用生成  <br/>`generate_api_mcp_calls` | LogicalPlan、API/MCP 契约版本、连接引用、分页/排序/过滤能力 | API 调用规格、参数映射、分页终止条件、输出 schema 和后续计算需求 | 不把 API 当 SQL；不支持 max 等聚合时输出完整取数及代码计算依赖。 |
| DA06.3.5 函数调用与表达式生成  <br/>`generate_function_expressions` | 逻辑步骤、函数/表达式引擎签名、类型/单位、参数绑定 | 函数调用或表达式 AST、依赖引用、输出类型及不支持算子 | 只用已知签名；任意 Python 等程序转 DA08.6，运行归 DA07。 |

#### DA06.4 计划修正与重组（软）

职责：依据检索、执行、验证或用户反馈，修改计算表达、替换方法、重选组件并重组子任务。 边界：保持正式业务目标与验收要求；涉及口径或权限变更时按对应变更机制处理，不能通过缩小范围掩盖失败。

组输入输出：反馈与当前计划 → 新计划及变更原因。拟议文件：`src/dataagent_application/planning/revision.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.4.1 语法与参数修正  <br/>`repair_syntax_and_parameters` | ExecutableSpec、解析/参数错误、实际 schema/签名版本、原始需求 | 修订 ExecutableSpec、逐处改动、参数校验和待验证项 | 不通过删过滤/换口径掩盖错误；修订未执行，不宣称已修好业务结果。 |
| DA06.4.2 执行错误修正  <br/>`repair_execution_errors` | 当前 PlanRevision、失败执行回执、环境/版本事实、可替代端口 | 修订计划、错误原因假设、受影响步骤与重试/替换条件 | 副作用未知步骤先 DA07 对账；修计划不授权重复写入。 |
| DA06.4.3 计算逻辑修正  <br/>`repair_calculation_logic` | 当前计划、验证差异/用户反馈、固定口径、独立预期引用 | 新 PlanRevision、逻辑差异、受影响结果和重验要求 | 不得改变正式验收标准使结果过关；口径变更提出单独修订。 |
| DA06.4.4 方法替换  <br/>`replace_analysis_method` | 当前方法/计划、效果与资源反馈、候选方法适用性、业务验收要求 | 替代方法 PlanRevision、选择理由、假设变化、重验范围和保留目标 | 方法可换，业务目标与正式判据保持；不承诺新方法一定通过。 |
| DA06.4.5 组件重选  <br/>`reselect_components` | 当前组件绑定、失败/不适用原因、候选实现、依赖与环境约束 | 新组件绑定、依赖检查、契约差异、版本锁定和回归要求 | 可重选组件与实现，不能绕过权限或接受不满足契约的替代品。 |
| DA06.4.6 子任务重组  <br/>`reorganize_subtasks` | 当前 DAG、新检索/执行事实、受影响输出、预算与保留约束 | 新子任务 DAG、依赖/次序差异、可复用结果及失效/待重验集合 | 禁止通过缩小范围掩盖失败；只重算受影响步骤，开放探索由 Agent 组织。 |

#### DA06.5 计算计划组合（软）

职责：依据授权、来源和后端能力选择执行目标，组织取数、合并及派生计算的依赖。 边界：API 不支持的聚合可在完整取数后由可用代码或函数计算；须检查分页、数据规模和运行环境，不能假定 API 等价于 SQL。

组输入输出：多目标 → 编排后的执行序列。拟议文件：`src/dataagent_application/planning/composition.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.5.1 执行目标匹配  <br/>`match_execution_targets` | 逻辑步骤、来源能力声明、后端/沙盒清单、授权决策、规模估计 | 目标绑定、SQL/API/代码/函数/表达式选择理由、能力缺口与资源预算 | 依据实际能力选后端；只读 SQL 不可写回，缺运行环境不能假装可执行。 |
| DA06.5.2 多步计算依赖编排  <br/>`compose_calculation_dependencies` | 目标绑定、分页/快照要求、跨源 schema、派生计算和资源限制 | ExecutionPlan；取数/合并/计算 DAG、中间类型、完整性门禁和失败策略 | API max 必须在声明范围完整分页取数后计算；取不全则阻塞精确聚合或显式 partial。 |

#### DA06.6 动作计划生成 〔FDE〕（软）

职责：把目标拆成含人工步骤与等待的动作序列。 边界：不判定动作能否被执行，归 DA15。

组输入输出：业务目标 → 多步动作序列。拟议文件：`src/dataagent_application/planning/actions.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.6.1 多步动作序列  <br/>`plan_action_sequence` | 业务目标、已有动作契约、前后置状态、依赖及环境约束 | ActionPlanDraft；动作序列、每步输入/预期状态和依赖 | 只起草计划；动作可执行性归 DA15、授权归 DA16，不自行放权。 |
| DA06.6.2 人工步骤与等待点插入  <br/>`insert_human_wait_points` | ActionPlanDraft、人工职责、外部事件、超时/恢复要求 | 含人工步骤/等待点的修订草案、责任角色、恢复条件和超时路径 | 等待不等于已完成；跨轮挂起恢复消费 DA14.6，不能编造人工确认。 |
| DA06.6.3 分支与异常路径  <br/>`plan_action_branches` | 动作计划、已知异常、业务分支条件、可用补偿动作 | 分支/异常 DAG、判定依据、终止/补偿/升级路径 | 补偿不假设等于回滚；异常路径仍受授权及幂等约束。 |

#### DA06.7 契约编译 〔FDE〕（软）

职责：产出待确认的契约草案。 边界：不直接生效，确认与发布归 DA15.2。

组输入输出：目标 → 状态机草案与判据草案。拟议文件：`src/dataagent_application/planning/contracts.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA06.7.1 目标转状态机草案  <br/>`draft_goal_state_machine` | 交付目标、对象生命周期引用、事件、业务约束与完成要求 | ContractDraft；状态/转换/触发条件、未决事项和定义来源 | 草案状态与业务真实状态分开；正式确认与发布归 DA15.2。 |
| DA06.7.2 审批点建议  <br/>`suggest_approval_points` | 状态机草案、动作风险/权限需求、角色职责和治理政策 | 审批点建议、所需角色、触发条件、等待/拒绝分支及理由 | 建议不构成审批；不得自行降低已要求的审批档位。 |
| DA06.7.3 成功判据与回滚草案  <br/>`draft_success_and_rollback_criteria` | 目标、拟议状态机、业务验收约束、补偿能力和不可逆限制 | 成功判据/回滚草案、可观测指标、验证步骤及不可恢复项 | 正式判据须有权主体确认；回滚方案不自动执行或保证完全恢复。 |

### DA07 计算执行

#### DA07.1 sql_execute（硬）

职责：将 SQL 提交给指定执行后端，取回结果及执行状态。 边界：不生成 SQL；后端必须实际支持 SQL。

组输入输出：SQL → 结果集与执行统计。拟议文件：`src/dataagent_application/execution/sql.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.1.1 企业 SQL MCP/API 执行适配  <br/>`execute_enterprise_sql` | 参数化 SQL、实际支持 SQL 的 MCP/API 端点、绑定参数、结果分页与超时预算 | ExecutionReceipt、TableRef/DataBatchRef、后端查询号、行数/耗时与完整性 | 执行已有 SQL；写 SQL 或存储过程的副作用统一经 DA07.7 控制；实际支持 SQL，分页不能首屏当全量。 |
| DA07.1.2 数据库驱动执行适配  <br/>`execute_database_sql` | 数据库 ConnectionRef、参数化 SQL、事务/隔离选项、参数与读取上限 | 结果集引用、查询/事务状态、统计、截断/续读说明和回执 | 按驱动能力运行；写 SQL/有副作用过程统一走 DA07.4/7 控制，不自增连接权限。 |
| DA07.1.3 本地 DuckDB 执行适配  <br/>`execute_duckdb_sql` | SQL、受控本地表/文件引用、挂载规则、内存/行数预算 | 本地结果 TableRef、查询统计、实际输入版本和执行回执 | 只读挂载及授权路径；写文件/数据等实际副作用须走 DA07.7 控制，本地缓存不代表源端当前数据。 |

#### DA07.2 code_execute（硬）

职责：在指定运行环境执行 Python 等程序，返回状态、结果和产物。 边界：依赖现有运行环境和沙盒，不负责选择分析方法。

组输入输出：代码 → 输出与产物文件。拟议文件：`src/dataagent_application/execution/code.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.2.1 本地 Python 执行  <br/>`execute_local_python` | ProgramDraft/ArtifactRef、输入资源引用、依赖锁、沙盒政策、CPU/内存/超时 | ExecutionReceipt、标准输出摘要、结构化结果、产物引用和退出信息 | 指定现有沙盒执行；可能写文件/库或触发外部动作的代码统一经 DA07.7 控制，不能验证副作用边界则拒绝只读通道。 |
| DA07.2.2 远程沙盒代码执行  <br/>`execute_remote_code` | 代码资产版本、远程沙盒引用、输入挂载、依赖/网络政策和资源配额 | 远程运行/作业引用、结果/文件引用、日志摘要和实际环境版本 | 受控挂载/网络/动作代理限制副作用；可能写入的代码经 DA07.7；超时保留查询句柄，未知不重放。 |

#### DA07.3 function_call（硬）

职责：执行已绑定参数的函数或接口调用并获取结果。 边界：限于声明能力和授权范围；有写入副作用的调用走 DA07.4 的变更控制。

组输入输出：函数与参数 → 返回值。拟议文件：`src/dataagent_application/execution/functions.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.3.1 本地函数调用  <br/>`call_local_function` | 已注册函数版本、参数、输入引用、声明的纯度/副作用与环境 | 类型化返回值、函数版本、执行回执和错误详情 | 限已注册签名；有写入副作用必须进入变更网关，不能借函数名绕过。 |
| DA07.3.2 远程领域函数调用  <br/>`call_remote_domain_function` | 远程函数契约/版本、连接引用、参数、响应 schema 与超时 | 领域返回值、远端请求号、实际版本、完整性和执行回执 | 不生成领域定义；副作用按声明与实际行为纳入 DA07.4/7。 |
| DA07.3.3 业务 API/MCP 调用  <br/>`call_business_api_mcp` | API/MCP 契约、连接/授权引用、绑定参数、分页/重试政策 | 响应批次、游标/限流信息、远端请求号与执行回执 | 仅调用授权能力；写方法转变更控制，不能因 HTTP 200 就认定业务已完成。 |

#### DA07.4 变更写入（硬）

职责：将已确定的变更写到指定目标，保留请求标识、旧值/版本和结果。 边界：只读 SQL 后端不能承担写回；部分成功须逐项说明，不能因工具返回成功就认定完成。

组输入输出：变更意图 → 写入回执与前后状态。拟议文件：`src/dataagent_application/execution/mutations.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.4.1 本地文件/数据集变更应用  <br/>`apply_local_changes` | 文件/数据集版本、ChangeSet、预期旧值/digest、授权决策与幂等键 | MutationReceipt；逐项前后版本、成功/冲突/失败、实际新资源引用 | 不覆盖未预期的并发修改；持久化改动走统一网关，部分成功逐项说明。 |
| DA07.4.2 企业 API/MCP 写回  <br/>`write_business_system` | 目标 API/MCP、业务对象键、ChangeSet、预期版本、授权/审批及幂等键 | MutationReceipt；远端请求号、逐项受理/生效状态、前后状态和核对入口 | 不能用只读 SQL 代替写回；网络超时标未知并对账，禁止盲目重试。 |
| DA07.4.3 写入回执与状态核对  <br/>`verify_mutation_receipts` | MutationReceipt、目标对象键、期望后状态、读取一致性/等待窗口 | 逐项核对结果、实际状态、差异、待确认项及对账建议 | 工具成功仅表示工具层回执；必须核对业务状态，尚未可见可标 pending。 |

#### DA07.5 expression_execute（硬）

职责：使用指定表达式引擎完成算术、条件、过滤或聚合。 边界：只支持明确的算子、类型和函数；任意代码使用 DA07.2。

组输入输出：表达式+数据 → 取值（含 UNKNOWN）。拟议文件：`src/dataagent_application/execution/expressions.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.5.1 标量表达式计算  <br/>`evaluate_scalar_expression` | 表达式 AST、类型化参数、引擎版本、NULL/UNKNOWN/单位规则 | 类型化标量、计算轨迹摘要、UNKNOWN 原因与实际引擎引用 | 只执行受支持算子；UNKNOWN 与 false/错误分开，不自动转为未通过。 |
| DA07.5.2 表数据表达式计算  <br/>`evaluate_table_expression` | 表达式 AST、TableRef、字段映射、引擎版本、行身份与预算 | 派生表/字段引用、逐行 UNKNOWN/错误、聚合覆盖和执行回执 | 保持行身份及声明语义；采样表不能产出宣称全量的精确聚合。 |

#### DA07.6 plan_execute（硬）

职责：按已确定的依赖顺序调用 SQL、API、代码、函数或表达式执行器，传递中间结果并记录各步状态。 边界：固定计算计划可做成复合能力；开放式检索、重规划和业务审批仍由 Agent/Preset 组织。

组输入输出：多步计划 → 中间结果与最终结果。拟议文件：`src/dataagent_application/execution/plans.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.6.1 多步计算执行  <br/>`execute_calculation_plan` | 已固定 ExecutionPlan、输入版本、目标绑定、预算与失败/恢复政策 | 各步骤运行状态、结果引用、最终输出、ExecutionReceipt 和阻塞依赖 | 按已确定 DAG 执行；不在执行器暗中开放检索或重规划，写步骤仍经网关。 |
| DA07.6.2 中间结果衔接  <br/>`connect_intermediate_results` | 上下游步骤签名、已完成输出引用、schema/版本映射与完整性要求 | 下游输入绑定、转换/传递回执、schema 差异和阻塞原因 | 不丢列/补造缺值以强配接口；必须保留版本、来源和分页完整性。 |

#### DA07.7 动作网关 〔FDE〕（硬）

职责：对受控动作执行权限、档位、幂等、预演及后置校验，并路由至具体执行适配器。 边界：DA07.4 的写入适配器复用该控制路径；不得绕过授权或临时扩权。安全要求的声明归 DA15.3。

组输入输出：已判定档位的动作 → 执行结果与收据。拟议文件：`src/dataagent_application/execution/action_gateway.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.7.1 分档执行（A0/A1/A2）  <br/>`execute_graded_action` | 动作契约版本、既定 A0/A1/A2 档位、授权/审批决策、参数和环境 | ActionReceipt；准入/拒绝、实际动作、执行状态、收据与后置核验引用 | 档位消费已发布 DA15 契约，权限映射参考 DA03.12；授权消费 DA16/平台及 DA12 约束，不自行放权，所有写适配器复用同一控制路径。 |
| DA07.7.2 幂等键与去重  <br/>`reserve_idempotent_request` | 动作作用域/目标、幂等键、规范化请求 digest、既有收据与保留期限 | 新预留/重复命中/键冲突、原回执引用和可执行性判定 | 同键异参拒绝；重复返回原状态，未知不能视为未执行后重新发起。 |
| DA07.7.3 dry-run 预演  <br/>`dry_run_action` | 动作契约、拟定参数、目标版本、授权决策、适配器预演能力 | 预演差异、受影响对象、前置检查和未覆盖副作用说明 | 预演不产生正式副作用；后端不支持真实预演须明确限制，不能假称可回滚。 |
| DA07.7.4 后置状态校验  <br/>`validate_post_action_state` | ActionReceipt、后置条件版本、目标读取端口、观察窗口 | 后置条件通过/未通过/待确认、实际状态、证据与下一步 | 观察业务状态不修改标准；核验失败不自动授权补写或升级权限。 |

#### DA07.8 补偿与对账 〔FDE〕（硬）

职责：副作用未知时禁止自动重放，只能查询与对账。 边界：不假设重跑等于回滚。

组输入输出：失败或未知 → 补偿动作或对账结论。拟议文件：`src/dataagent_application/execution/reconciliation.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.8.1 反向/补偿动作  <br/>`execute_compensation` | 原 ActionReceipt、获准补偿契约/参数、当前版本、授权与独立幂等键 | 补偿收据、前后状态、未恢复项及后置核验结果 | 反向动作不是重跑原动作；补偿本身可失败/不可逆，仍走动作网关。 |
| DA07.8.2 副作用未知的对账  <br/>`reconcile_unknown_effects` | 未知执行引用、幂等键、远端请求号、目标键、期望状态与对账窗口 | ReconciliationReport；已生效/未生效/部分/仍未知、逐项依据与允许下一步 | 只查询与比对；无证据证明未执行时不得自动重放。 |
| DA07.8.3 部分失败逐项说明  <br/>`describe_partial_failures` | 批量操作回执、每项对象键、预期变更及已观测状态 | 逐项成功/失败/未知表、实际已改内容、剩余项和补偿/人工处理建议 | 不能把混合状态汇总为全成/全败；输出说明不自动实施补偿。 |

#### DA07.9 作业化执行 〔FDE〕（硬）

职责：把超时风险从「请求内完成」变为「受理即返回」。 边界：负责作业提交、状态查询与结果读取；跨轮等待和恢复归 DA14.6。超时或状态未知时先查询与对账。

组输入输出：长任务请求 → 作业号与进度。拟议文件：`src/dataagent_application/execution/jobs.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.9.1 受理与作业号：长任务先受理再推进  <br/>`submit_long_running_job` | 长任务规格、输入版本、目标环境、预算、授权及幂等键 | JobRef、accepted_at、查询/取消/读取结果入口和受理回执 | 受理不等于完成；持久登记后推进，受理状态未知先按键查询。 |
| DA07.9.2 进度与部分结果  <br/>`read_job_progress` | JobRef、已读游标、期望部分结果类型与最大读取量 | JobSnapshot；阶段、已完成/总量估计、部分结果、最终结果引用及 continuation | 进度是执行观测；部分结果标覆盖范围，不能伪装最终完整结果。 |
| DA07.9.3 未知状态不重放：只查询与对账  <br/>`query_unknown_job_state` | JobRef 或提交请求号/幂等键、最后观测状态、对账策略 | 最新作业状态、已有收据/结果、对账引用及仍未知说明 | 仅查询与对账；超时不重新提交，跨轮等待与恢复交 DA14.6。 |

#### DA07.10 引擎接入与一致性验证（硬）

职责：获取并校验业务所需的 SQL、表达式、公式或规则引擎；替换实现时验证约定语义与效果。 边界：兼容既有引擎语义时，以目标实现或独立样本为依据；不要求所有业务复刻某个旧引擎，也不能以自证代替独立验收。

组输入输出：引擎坐标 → 可用引擎 + 一致性报告。拟议文件：`src/dataagent_application/execution/engines.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA07.10.1 引擎获取与版本对齐：坐标、版本、离线包与校验和  <br/>`acquire_and_align_engine` | 引擎坐标/固定版本、离线包或来源、期望校验和、环境/许可约束 | EngineBinding；实际版本/digest、安装位置受控引用、可用算子及获取报告 | 仅在允许环境获取验证指定引擎；不把可下载当已可运行，不替业务选择兼容基准。 |
| DA07.10.2 双引擎一致性校验：同输入 diff，差异分类  <br/>`compare_engine_consistency` | 目标/候选引擎版本、同输入样本引用、固定语义标准、独立预期/容差 | EngineConsistencyReport；逐样本 diff、NULL/类型/精度/错误差异分类与覆盖 | 以目标实现或独立样本为依据；自生成样本自通过不能替代 DA11 独立业务验收。 |
| DA07.10.3 降级留证：降级理由、覆盖范围、已知差异  <br/>`record_engine_degradation` | 原/替代引擎、降级原因、已知差异、验证报告与实际覆盖范围 | DegradationRecord；运行绑定、限制、未覆盖语义、影响结果和后续重验要求 | 留证不豁免验收；不满足关键语义则不可用，不能悄悄换引擎。 |

### DA08 分析

#### DA08.1 分析规划（软）

职责：将开放问题拆成假设、方法和验证步骤。 边界：不把计划当结论。

组输入输出：问题 → 分析步骤与方法选择。拟议文件：`src/dataagent_application/analysis/planning.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA08.1.1 问题分解  <br/>`decompose_analysis_question` | 业务问题、可用数据/语义引用、交付形式、正式验收与预算 | AnalysisPlanDraft；可计算子问题、假设、数据缺口和验证步骤 | 问题分解是计划；不把可算性当结论，也不私自更改业务目标。 |
| DA08.1.2 分析方法选择  <br/>`select_analysis_methods` | 子问题、数据规模/类型、候选方法、适用条件与资源预算 | 方法候选与选择理由、前提检查、预期输出及替换条件 | 允许多种方法与动态替换；不凭方法名称承诺业务效果。 |

#### DA08.2 描述分析（软）

职责：执行同比环比、贡献、漏斗、留存等分析。 边界：各方法可独立发布，不直接推断因果。

组输入输出：数据+口径 → 描述性结论。拟议文件：`src/dataagent_application/analysis/descriptive.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA08.2.1 同比/环比分析  <br/>`analyze_period_changes` | 结果表、指标口径版本、时间粒度/日历、对比周期、缺失处理 | 各期数值、同比/环比/绝对变化、零基数/缺期标记和计算引用 | 保持可比周期与单位；变化描述不推出因果，零基数不硬算百分比。 |
| DA08.2.2 贡献度分析  <br/>`analyze_contributions` | 基期/报告期数据、分解维度、指标公式、分摊方法与交互项政策 | 各因子贡献、总变化核对、残差/交互项和方法假设 | 贡献是选定分解规则下的结果；不等于因果贡献，必须说明未解释部分。 |
| DA08.2.3 漏斗分析  <br/>`analyze_funnel` | 事件表、实体键、步骤顺序、转化时间窗、去重/回流规则 | 各步人数/事件数、转化率、流失与覆盖缺口 | 定义实体和时间窗后计算；不将缺失采集误认为真实流失。 |
| DA08.2.4 留存/Cohort 分析  <br/>`analyze_retention_cohorts` | 事件表、cohort 进入条件、用户键、留存事件/窗口、观察截止日 | cohort×周期留存表、分母、右删失/未成熟周期标记 | 未成熟周期与零留存分开；不混用不同 cohort 定义或跨期口径。 |

#### DA08.3 统计分析（软）

职责：提供统计估计、检验、回归等方法。 边界：说明适用条件和不确定性。

组输入输出：样本 → 统计量与显著性。拟议文件：`src/dataagent_application/analysis/statistics.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA08.3.1 分布与区间估计  <br/>`estimate_distributions_intervals` | 样本引用、变量/权重、抽样设计、估计方法、置信水平 | 分布/参数估计、区间、有效样本数、假设检验检查和局限 | 区间须标方法/抽样前提；非随机样本不自动外推总体。 |
| DA08.3.2 假设检验  <br/>`test_hypotheses` | 样本/分组、预先明确的零/备择假设、检验方法、显著性与多重校正 | 统计量、p 值/校正值、效应量、区间、前提检查和判读 | 显著性不等于业务价值或因果；不因结果不显著而私换假设/阈值。 |
| DA08.3.3 回归分析  <br/>`fit_regression` | 训练表、因变量/自变量、模型族、分割/正则约束与诊断要求 | 模型 ArtifactRef/草案、系数/不确定性、拟合/外样本指标和诊断 | 回归关系不自动识别因果；数据泄漏、共线性和外推限制需呈现。 |

#### DA08.4 关系分析（软）

职责：分析对象间路径、聚集和异常关系。 边界：使用已有对象关系，不做实体对齐。

组输入输出：实体与关系 → 结构与异常。拟议文件：`src/dataagent_application/analysis/relationships.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA08.4.1 关系路径分析  <br/>`analyze_relationship_paths` | 已对齐实体/关系版本、起终点、路径类型/长度、时态/可见域 | 路径列表、节点/边引用、路径指标和覆盖缺口 | 使用已有关系，不执行实体对齐；可见路径不代表全图唯一关系。 |
| DA08.4.2 群组/聚集分析  <br/>`analyze_relationship_clusters` | 实体/关系图引用、权重/方向、聚类方法与参数、时态范围 | 群组成员、聚集指标、稳定性/参数说明和孤立点 | 群组由所选方法产生，不自动成为业务组织或风险标签。 |
| DA08.4.3 异常关系识别  <br/>`detect_anomalous_relationships` | 关系图、正常基线/规则、异常方法、阈值与可见范围 | 异常边/子图候选、评分、触发依据、基线和待核实项 | 异常候选不等于违规或欺诈；阈值正式约束变更走治理。 |

#### DA08.5 结果解释（软）

职责：根据计算结果解释变化、提出原因假设并回答问题。 边界：假设与已验证结论分开，保留来源引用。

组输入输出：结果 → 可读解释与原因假设。拟议文件：`src/dataagent_application/analysis/explanations.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA08.5.1 查询答案解释  <br/>`explain_query_answer` | 计算结果引用、实际计划/执行记录、口径版本、用户问题和受众 | Explanation；答案、计算路径、关键数值、来源引用、限制与未知项 | 只解释有依据的结果；没有执行/来源不能补造可信链或断言。 |
| DA08.5.2 变化原因假设生成  <br/>`generate_change_hypotheses` | 变化分析结果、相关上下文/事件、已知业务机制、可用验证数据 | 原因假设列表、支持/反证引用、替代解释和验证建议 | 假设与已验证结论分列；关联/时间先后不自动构成因果。 |

#### DA08.6 程序生成与修复（软）

职责：按任务要求生成分析、适配、组件组合或验证程序，并依据执行和评测反馈修复。 边界：供其他模块复用；SQL 生成归 DA06，执行归 DA07，业务效果验证归 DA11。程序可变，正式验收标准不得自行放宽。

组输入输出：任务要求与反馈 → 程序或修订版本。拟议文件：`src/dataagent_application/analysis/programs.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA08.6.1 通用任务代码生成  <br/>`generate_task_program` | 任务要求、输入输出契约、适配/分析/组合需求、可用组件与环境约束 | ProgramDraft；代码、依赖锁草案、组件绑定、参数和待验证项 | 可生成分析、适配和组合程序；SQL 归 DA06，执行归 DA07，生成不等于可用。 |
| DA08.6.2 表格公式生成  <br/>`generate_spreadsheet_formulas` | 工作簿 schema/单元格引用、目标公式语义、引擎/方言、单位与错误政策 | 公式草案、目标单元格映射、引用依赖和兼容/重算要求 | 不直接改原工作簿；公式生成和真实重算分离，不能拿缓存值当验证。 |
| DA08.6.3 反馈驱动程序修复  <br/>`repair_task_program` | 当前程序版本、执行错误/评测 diff、固定 I/O/验收要求、实际环境 | 新 ProgramDraft、代码 diff、修复理由、依赖变化和必须重验项 | 允许更换程序/组合方法；不得自改验收标准或用硬编码预期值掩盖失败。 |
| DA08.6.4 验证程序生成  <br/>`generate_validation_program` | 有权确定的验收要求/版本、输入输出契约、允许检查机制、样例接口 | ValidationProgramDraft；可执行检查、判据映射、未覆盖要求和运行依赖 | 程序只实现既定判据；独立样本与验收执行由 DA11 管理，不自证通过。 |

### DA09 预测、仿真与优化

#### DA09.1 预测（软）

职责：根据历史数据和指定模型估计未来，给出预测区间。 边界：不承诺未来结果准确。

组输入输出：历史序列 → 预测值与区间。拟议文件：`src/dataagent_application/prediction/forecasting.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA09.1.1 时间序列预测  <br/>`forecast_time_series` | 历史序列、目标字段/频率、预测跨度、模型/训练窗口、回测要求 | ForecastResult；未来点估计、区间、回测指标、模型版本与数据缺口 | 区间依赖模型假设；历史表现不保证未来，缺期/结构变化需披露。 |
| DA09.1.2 带外生变量预测  <br/>`forecast_with_exogenous_variables` | 历史目标/外生变量、未来外生情景、时间对齐、跨度和模型约束 | 条件预测、区间、外生变量贡献说明、回测和未知未来输入 | 未来外生变量未知须用情景或 needs_input；不得偷用未来真实值造成泄漏。 |
| DA09.1.3 概率预测  <br/>`forecast_probabilities` | 历史/特征数据、目标事件或连续量、分布/分位数要求、校准样本 | 概率/分位数/预测区间、校准与覆盖指标、样本与方法限制 | 区分置信区间和预测区间；概率不是承诺，校准范围外需说明。 |

#### DA09.2 情景仿真（软）

职责：计算不同参数、假设和机制下的情景。 边界：仿真依赖假设，不等同于预测。

组输入输出：假设与参数 → 情景结果。拟议文件：`src/dataagent_application/prediction/simulation.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA09.2.1 参数敏感性分析  <br/>`analyze_parameter_sensitivity` | 模型/计算函数、参数基准/范围、采样设计、输出指标与随机种子 | 敏感度、响应曲线/区间、交互效应和运行覆盖 | 结果只覆盖声明范围/机制；敏感性不自动解释真实因果或未来概率。 |
| DA09.2.2 业务情景模拟  <br/>`simulate_business_scenarios` | 业务机制/模型、情景假设、参数/分布、迭代次数、约束与随机种子 | ScenarioResult[]；各情景输出分布、运行记录、假设和可比较指标 | 仿真是条件推演，不能当预测或业务承诺；不自动执行推荐动作。 |

#### DA09.3 约束求解（硬）

职责：在目标和约束下计算方案。 边界：不替业务决定目标或执行方案。

组输入输出：目标与约束 → 可行解或不可行原因。拟议文件：`src/dataagent_application/prediction/solvers.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA09.3.1 线性/整数规划求解  <br/>`solve_linear_integer_program` | 目标函数/方向、变量与类型、线性约束、求解器/时限/容差 | OptimizationResult；可行解、目标值、界/最优间隙、状态或不可行依据 | 区分 optimal/feasible/infeasible/unknown；不替业务定目标，超时无解不等于不可行。 |
| DA09.3.2 排程与资源约束求解  <br/>`solve_resource_schedule` | 任务/资源日历、持续时间、先后依赖、容量/硬软约束、优化目标与时限 | 排程/分配候选、约束满足情况、目标值、冲突/不可行原因和 gap | 不自行放松硬约束；排程方案不等于已落实资源，执行须另授权。 |

#### DA09.4 方案比较（软）

职责：比较方案的成本、收益、风险等权衡。 边界：使用明确的偏好与权重。

组输入输出：多方案结果 → 比较结论与权衡。拟议文件：`src/dataagent_application/prediction/comparison.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA09.4.1 目标指标比较  <br/>`compare_scenario_metrics` | 方案结果、同口径指标版本、比较基线、成本/收益/风险计算条件 | 对比表、绝对/相对差异、可比性缺口与不确定性 | 口径/情景不同先标不可比；不把估计收益写成保证收益。 |
| DA09.4.2 多目标权衡分析  <br/>`analyze_multiobjective_tradeoffs` | 方案结果、目标方向、偏好/权重来源、硬约束与风险容忍范围 | Pareto 候选、权重敏感性、取舍说明和待业务选择项 | 权重须明确，不代业务选择最终方案；改变偏好需留新版本。 |

### DA10 表格、可视化与交互

#### DA10.1 表格计算（软）

职责：生成结果表、透视表和公式计算。 边界：输入表格规整归 DA02。

组输入输出：结果集 → 工作簿与透视表。拟议文件：`src/dataagent_application/presentation/workbooks.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA10.1.1 结果工作簿生成  <br/>`build_result_workbook` | 结果表引用、sheet/列布局、格式/单位、来源与说明、目标格式 | 工作簿 ArtifactRef、单元格到结果/口径映射、导出限制和验证摘要 | 输入规整归 DA02；展示格式不改值，公式/缓存/重算状态分开。 |
| DA10.1.2 透视计算  <br/>`compute_pivot_table` | 规整 TableRef、行/列维度、聚合指标/口径、过滤与缺失处理 | 透视表引用、总计/小计、实际输入范围、计算步骤和来源映射 | 不在透视中隐式修数据或改变分母；部分输入须标明覆盖。 |
| DA10.1.3 表格公式计算  <br/>`calculate_spreadsheet_formulas` | 工作簿版本、公式/单元格范围、计算引擎版本、外链与错误政策 | 重算工作簿新版本、单元格值/错误、实际计算状态和引擎回执 | 必须实际重算才标 calculated；不支持公式与旧缓存值分开，写回经 DA07。 |

#### DA10.2 图表生成（软）

职责：将结果转换为图表或交互视图。 边界：不改变分析口径。

组输入输出：结果集 → 图表。拟议文件：`src/dataagent_application/presentation/charts.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA10.2.1 静态图表生成  <br/>`render_static_chart` | 结果集、图型/编码、单位/尺度、标题注释、受众与图片格式 | 图像 ArtifactRef、ChartSpec、数据/口径引用、可访问性文本 | 不通过截轴/筛点改变含义；保留过滤、聚合和不确定性说明。 |
| DA10.2.2 交互图表生成  <br/>`build_interactive_chart` | 结果引用、交互编码、允许过滤/钻取、权限范围、前端目标和预算 | 交互视图 ArtifactRef、交互/查询绑定、可见域与部署需求 | 交互取数受同等授权；过滤状态可见，不暗改分析口径或暴露隐含数据。 |

#### DA10.3 报告生成（软）

职责：组织文字、表格、图表和引用，导出报告或看板。 边界：调度与分享由应用组合。

组输入输出：结论与图表 → 报告或 Dashboard。拟议文件：`src/dataagent_application/presentation/reports.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA10.3.1 文档报告生成  <br/>`compose_document_report` | 有依据的结论/假设、表图引用、来源版本、受众、章节/模板要求 | ReportDraft/ArtifactRef；文档、引用清单、图表绑定、限制和待确认项 | 区分事实/假设/预测；不能为版面补造结论，分享与调度由应用组合。 |
| DA10.3.2 Dashboard 生成  <br/>`compose_dashboard` | 指标/图表引用、布局、筛选联动、刷新策略草案、受众与权限引用 | DashboardSpec/ArtifactRef；视图布局、依赖/查询绑定、刷新和部署需求 | 生成规格不代表已部署或已调度；每视图保留指标版本与数据时点。 |
| DA10.3.3 报告格式导出  <br/>`export_report_format` | 源报告/看板版本、目标 PDF/DOCX/HTML 等格式、字体/分页/交互降级政策 | 目标文件 ArtifactRef、转换/布局核验记录、丢失特性和来源对应 | 格式转换保持数值/引用；交互转静态须说明，导出不自动公开分享。 |

#### DA10.4 对话即时修正（软）

职责：将明确纠正转为可定位变更，更新当前任务的绑定、假设、计划或产物并从受影响步骤继续。 边界：持久化使用 DA03/DA04/DA07，跨任务或企业共享更新使用 DA12.5。

组输入输出：用户纠正 → 修正后的任务状态与结果。拟议文件：`src/dataagent_application/presentation/corrections.py`。

| 原子能力 / 调用名 | 业务输入 | 业务输出 | 作用边界 |
|-|-|-|-|
| DA10.4.1 纠正意图识别  <br/>`identify_correction_intent` | 用户原话、当前任务上下文/产物引用、对话位置、已知纠正记录 | CorrectionIntent；拟改内容、候选对象、明确/歧义项和原话锚点 | 意图识别只生成候选；未明确的业务口径不能当已批准变更。 |
| DA10.4.2 修正对象与范围定位  <br/>`locate_correction_targets` | CorrectionIntent、对象/字段/公式/计划依赖、任务选用版本、用户可改范围 | ChangeProposal；精确对象/版本、影响步骤/产物、当前任务或跨任务范围 | 不能只改回答文字；跨企业共享变更转 DA12.5，含糊对象先澄清。 |
| DA10.4.3 当前任务状态更新  <br/>`apply_task_correction` | 明确的 ChangeProposal、授权/确认依据、预期 TaskContextRef、目标资产旧版本 | TaskRevisionReceipt；DA03/DA04/DA07 实际变更回执、新上下文版本、受影响结果及待重验集 | 实际修改绑定/假设/资产/计划；并发检查，持久化走所属模块，不以聊天承诺代替保存。 |
| DA10.4.4 修正后续算与刷新  <br/>`recompute_and_refresh_after_correction` | 已保存任务修订、受影响 DAG/产物、可复用结果、预算与既定验收要求 | 新执行/验证引用、刷新产物新版本、差异、未完成项与当前任务状态 | 从受影响步骤续算并实际刷新；写步骤不得盲目重放，验证不足不得宣称纠正完成。 |

## 4. 跨层依赖与职责分界

| 协作方 | 本层消费/发出 | 边界 |
|-|-|-|
| DA01/02 数据接入与准备 | 读取来源能力、表/文档/schema、快照/批次和画像；按需请求补数/规整 | 本层不重做来源接入、实体规整或数据血缘采集；读取不全要保留完整性 |
| DA03 语义 | 按版本检索/展开实体、指标、规则、关系、映射和状态定义；明确纠正委托语义写入 | DA05 不创造/修改定义；正式口径变更不能借计划修正或程序修复生效 |
| DA04 轨迹与资产 | 实际事件、程序/查询/报告/组合及来源；当前任务上下文版本 | 检索独立归 DA05；证据与轨迹保存由所属存储/资产端口完成，排序器不承担存储 |
| DA11 评测与验证 | 固定验收要求、独立样本、运行/业务效果报告 | DA08.6 可以生成验证程序；样本、判据正式版本与独立验收仍归 DA11/有权主体 |
| DA12 治理 | 实际授权决策、审计、版本/发布政策、跨任务纠正提案 | 本层校验并执行已有决策；检索筛选不发权限，跨企业共享更新不从对话直接广播 |
| DA13 建模物化 | 可读取模型/物化结果；需要转换时消费计划/执行端口 | 不在可视化或分析模块重建物化引擎 |
| DA14 运行编排 | 作业号、等待/恢复条件、已观测状态 | DA07.9 负责受理/进度/结果，跨轮恢复消费 DA14.6，未知状态先查/对账 |
| DA15/16 动作契约/授权审批 | 草案、已发布契约、既定档位、审批决策 | DA06 只起草；DA07 网关不临时扩权，DA07.4 写回统一走网关 |
| DA17/18 环境与交付 | 业务环境约束、版本钉定、可替换组件、经过验证的组合 | 环境默认版本不等于任务修订；本层产物可沉淀为 Skill/Preset/Bundle，不固定唯一方法 |

模块间通过类型与端口协作，不互相导入内部实现。DA05 通过索引/关系读取端口检索；按 ID/版本取对象仍是数据层 repository 的基本读取。DA06 消费检索与执行反馈；DA07 只执行确定计划并返回事实；DA08/09 使用执行端口；DA10 组合结果并提交实际纠正。开放式检索、重规划、生成程序、验证循环由 Agent/Preset 组织，DA07.6 不隐式吞入整个 Agent 循环。

## 5. 动态组合示例

### 例一：从值反查，只有 API 的最大报销金额

1. 用户给出一个供应商值与“上月最大报销金额”。`DA05.1.3` 从值反查可见表列/业务接口，再以 `DA05.1.1/2` 扩展候选；无需先指定表。`DA05.2.2/4` 找到“报销金额”和供应商映射的固定版本，缺口才调用 DA01/02/03 补数据或语义。
2. `DA06.1/2` 绑定金额、上月边界、币种和状态过滤。已知问题可明确标假设先算；若“含撤回单”会改变结果，则 `DA06.1.3/4` 带候选与依据澄清，用户可自由补充。
3. `DA06.3.4` 发现 API 只支持列表/分页，不能 `max`。`DA06.5.1/2` 选择 API 取数加 Python 计算，定义分页耗尽、声明范围、快照/一致性和规模预算门禁；`DA08.6.1` 生成适配及计算程序，`DA07.3.3/2` 执行。页数未知、速率限制未完成或源变化无法保证一致时，结果保持 `partial/needs_input`，不能称全量最大值。
4. 若超出本地内存，则 `DA06.4.4` 改为流式扫描方法，或 `DA06.4.5` 重选远程沙盒实现；仍须完整读取同一声明范围。若上游提供真正 SQL 后端，也可重选 SQL 方案；不能仅因存在 MCP 就假设能执行 SQL。DA11 用独立样本核对金额口径与分页完整性。
5. `DA08.5.1` 解释数值/范围/来源，`DA10.1/3` 生成结果和报告；DA04 保存实际程序、轨迹与通过验证的组合。下次可由 `DA05.8` 召回复用，仍检查环境、版本及权限。

### 例二：规则审核更换引擎并接受用户纠正

1. 从制度文档或已有业务 Skill 进入，`DA05.4/8` 找到相关条款、适用规则和组件；DA03 提供规则版本/适用范围。`DA06.2/5` 编译到可用表达式/函数后端，`DA07.10.1` 获取指定引擎并核实实际版本。
2. 旧引擎在边界值上与固定语义不一致，`DA07.10.2` 通过目标实现或独立样本分类差异。`DA06.4.4/5/6` 可改方法、改引擎、重组检查子任务，`DA08.6.1/3` 生成或修复适配/组合程序；`DA08.6.4` 把既定验收要求转检查程序。DA11 保持独立样本与判据，不能通过放宽验收或硬编码结果完成验证。
3. 用户明确纠正“此任务应按含税金额”。`DA10.4.1/2` 定位指标绑定、任务版本、受影响计算和报告；若只是当前任务绑定，`DA10.4.3` 调用 DA04.5 保存新上下文，若是明确且获准的定义修订则经 DA03/DA12 保存对应版本。返回实际修订回执，不能只回复“已记住”。
4. `DA10.4.4` 只从受影响步骤续算、调用 DA11 重验并刷新工作簿/报告的新版本。若已有业务写回超时，则先 DA07.8.2/9.3 查询/对账，不能因续算重放写入；必要补偿仍须获准并经网关。
5. 验证满足后，DA04 保存有效方法和依赖，DA18 可组装交付。引擎替换、程序不同不影响按同一端到端业务要求验收；报告明确 UNKNOWN、待核实与已验证结论。

## 6. 实施组织与待收敛项

推荐一个 Python 工作区 `packages/capabilities/dataagent-application/`，按模块目录与能力组文件组织，端口隔离具体来源、索引、计算引擎、沙盒和治理服务。推荐方案便于复用表格与科学计算生态，同时契约可序列化，未来可由其他语言实现适配器。另一种按每个 DA 编号拆仓库/进程会增加部署与跨模块协议负担，本版不采用；已有服务可通过端口接入，不需要重建。

**目录 ID 不等于发布包粒度**。同一能力可有多个 SQL/API/代码或算法实现，多个原子也可封装为复合能力与 Skill/Preset/Bundle。正式发行包/安装机制、JSON Schema、生产容量与模型/引擎选择留到实现前收敛，不影响本版逐项判断输入、输出、边界与代码归属。

文档核对要求：XML 中 DA05–DA10 的编号集合与 JSON 完全一致；每项有非空具体 I/O、边界、调用名、相对源码路径与入口；39 个组对应 39 个拟议能力组文件。目录和类型是提案，当前不声称已有实现、平台兼容或业务验收通过。

# 执行应用层代码目录与适配端口 v0.1

本文件只提出源码布局，没有创建下述实现文件。推荐 Python 工作区 `packages/capabilities/dataagent-application/`；数据框架、统计库、沙盒和引擎均按任务可选装配。共享基础类型沿用 [数据层共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)，未来提取到共同契约包或采用端口生成类型；本层 `contracts` 只持有应用层特有对象，不让治理层为了使用回执类型导入整个应用层实现。

## 1. 拟议工作区

```text
packages/capabilities/dataagent-application/
├── pyproject.toml                     # 运行时、可选依赖组与构建声明
├── uv.lock
├── contracts/generated/              # 从类型导出的 schema，不手工重复维护
├── src/dataagent_application/
│   ├── contracts/                    # 仅本层特有协议；基础引用使用共享契约包
│   │   ├── retrieval.py              # SearchHit、ValueHit、DependencyPath、ComponentCandidate
│   │   ├── planning.py               # RequirementSpec、LogicalPlan、ExecutionPlan、PlanRevision
│   │   ├── actions.py                # 动作/状态机草案；消费 DA15/16 已确认契约与决策
│   │   ├── execution.py              # 回执、逐项副作用、作业/对账、引擎核对协议
│   │   ├── analysis.py               # 分析计划、结果/解释、程序草案
│   │   ├── prediction.py             # 预测、情景、求解与比较结果
│   │   └── presentation.py           # 展示规格、纠正意图/提案与任务修订回执
│   ├── retrieval/                    # DA05 8 组
│   │   ├── tables.py                 # DA05.1 表/列/值任意入口
│   │   ├── semantics.py              # DA05.2
│   │   ├── memories.py               # DA05.3
│   │   ├── documents.py              # DA05.4
│   │   ├── analysis_assets.py        # DA05.5
│   │   ├── ranking.py                # DA05.6，不承担证据存储
│   │   ├── lineage.py                # DA05.7，只读已有关系
│   │   └── components.py             # DA05.8，只召回筛选
│   ├── planning/                     # DA06 7 组
│   │   ├── requirements.py           # DA06.1
│   │   ├── semantic_compilation.py   # DA06.2
│   │   ├── expressions.py            # DA06.3 SQL/API/函数表达，不执行
│   │   ├── revision.py               # DA06.4 方法/组件/子任务可替换
│   │   ├── composition.py            # DA06.5 多后端与完整取数门禁
│   │   ├── actions.py                # DA06.6 FDE 草案
│   │   └── contracts.py              # DA06.7 FDE 草案
│   ├── execution/                    # DA07 10 组
│   │   ├── sql.py                    # DA07.1 三种 SQL 适配入口
│   │   ├── code.py                   # DA07.2 本地/远程环境
│   │   ├── functions.py              # DA07.3 本地/领域/API
│   │   ├── mutations.py              # DA07.4 写入与逐项核对
│   │   ├── expressions.py            # DA07.5 类型/UNKNOWN 语义
│   │   ├── plans.py                  # DA07.6 固定 DAG，不吞入开放探索循环
│   │   ├── action_gateway.py         # DA07.7 统一副作用控制
│   │   ├── reconciliation.py         # DA07.8 补偿/对账
│   │   ├── jobs.py                   # DA07.9 受理、查询、结果读取
│   │   └── engines.py                # DA07.10 引擎获取/核对/降级留证
│   ├── analysis/                     # DA08 6 组
│   │   ├── planning.py               # DA08.1
│   │   ├── descriptive.py            # DA08.2
│   │   ├── statistics.py             # DA08.3
│   │   ├── relationships.py          # DA08.4
│   │   ├── explanations.py           # DA08.5
│   │   └── programs.py               # DA08.6 分析/适配/组合/验证程序
│   ├── prediction/                   # DA09 4 组
│   │   ├── forecasting.py            # DA09.1
│   │   ├── simulation.py             # DA09.2
│   │   ├── solvers.py                # DA09.3
│   │   └── comparison.py             # DA09.4
│   ├── presentation/                 # DA10 4 组
│   │   ├── workbooks.py              # DA10.1
│   │   ├── charts.py                 # DA10.2
│   │   ├── reports.py                # DA10.3
│   │   └── corrections.py            # DA10.4 实际资产/任务变更
│   ├── ports/                        # 协议；业务函数只依赖协议与共享类型
│   │   ├── repositories.py           # 按版本解析对象、读取关系、保存回执与幂等记录
│   │   ├── retrieval.py              # 元数据/全文/向量候选读取及重排
│   │   ├── sources.py                # 来源特性、分页/快照取数，不假定 SQL
│   │   ├── execution.py              # SQL、代码、函数、表达式、作业协议
│   │   ├── policy.py                 # DA12/15/16 决策与契约解析，不创建授权
│   │   ├── validation.py             # DA11 固定要求、独立样本和验证报告
│   │   ├── inference.py              # 结构化生成，保留模型/Prompt/输入版本
│   │   ├── scientific.py             # 统计/预测/仿真/求解器
│   │   ├── rendering.py              # 工作簿真实重算、图表、文档导出/渲染
│   │   ├── task_changes.py           # DA03/04/07 实际变更与修订回执
│   │   └── traces.py                 # DA04 实际事件/产物/来源登记
│   ├── adapters/
│   │   ├── retrieval/                # 本地全文/向量/企业搜索；同契约可替换
│   │   ├── execution/                # SQL MCP/API、驱动、DuckDB、Python、远程沙盒
│   │   ├── engines/                  # 公式/表达式/规则；显式算子与版本语义
│   │   ├── scientific/               # 统计、时序、模拟、优化求解器
│   │   ├── rendering/                # Excel 重算、静态/交互图、报告/格式导出
│   │   ├── inference/                # 不同模型实现
│   │   └── services/                 # 数据层、验证、治理、环境、轨迹等端口绑定
│   ├── registry/                     # 能力 ID、operation、I/O 类型、实现、依赖装配
│   └── interfaces/                   # Python API、CLI、HTTP、MCP，同业务契约
├── component-specs/                  # 项目自拟能力描述，可按依赖聚合
├── presets/                          # 可替换点显式的示例组合
├── examples/                         # 去标识数据和动态重规划示例
├── tests/
│   ├── contracts/                    # 不同实现的共同行为与版本/UNKNOWN/完整性
│   ├── execution/                    # 幂等、未知不重放、部分成功、查询与核对
│   ├── adapters/                     # 实际分页/方言/算子/引擎与声明相符
│   └── scenarios/                    # 固定验收要求、独立样本、端到端结果
└── fixtures/                         # 小型输入、边界/独立对照；生产数据不入代码库
```

常规 `__init__.py` 省略。39 个能力组文件及其每个函数入口都可由 [JSON 目录](https://modelbest.feishu.cn/docx/ReDXdJzLWoihZDxqaO0clUxInKf) 反查。初期组内多个算法可共处一个文件，复杂后展开子包；不改变能力 ID。能力 ID、目录、Python 包、进程、发行包分别决定，不能以编号数推导部署单元数。

## 2. 适配端口与实现边界

| 端口 | 关键操作草案 | 必须保留的事实 |
|-|-|-|
| Repository / RelationReader | `resolve(ref,revision)`、`read_edges(kinds,scope,cursor)`、`save_receipt`、`reserve_idempotency` | 读到的实际版本、边类型、权限可见范围、同键请求 digest；此处不承担问题相关性召回 |
| Retrieval | `search_tables/fields/values/documents/assets/components`、`rerank` | 任意种子、索引时点、候选来源、过滤/截断、相关性方法；不保存业务证据 |
| SourceRead | `describe_capabilities`、`read_page`、`read_as_of` | 实际后端能力、页游标/终止证明、范围、快照一致性、未完成原因 |
| SQL / Code / Function / Expression | `execute(spec,context)`、`query_receipt` | 目标版本、参数/输入引用、实际结果/错误、副作用声明与观测、UNKNOWN 语义 |
| ActionControl | `check_decision`、`reserve_key`、`dry_run`、`dispatch`、`verify_postcondition` | 既定档位/授权/审批、请求 digest、前后状态、逐项收据；不临时扩权 |
| Job / Reconciliation | `submit`、`get_status`、`read_results`、`cancel`、`reconcile` | 受理号、提交键、最后观测、部分结果、未知状态与对账依据；取消请求不等于已无副作用 |
| Validation | `resolve_criteria`、`request_validation`、`read_report` | 正式标准版本、独立样本、依赖版本、实际差异/覆盖；生成程序不能自定判据 |
| Scientific | `estimate/fit/forecast/simulate/solve` | 方法/求解器版本、种子、样本/训练与测试切分、假设、区间、解状态/gap |
| Rendering | `recalculate_workbook`、`render_chart`、`compose_report`、`export` | 公式/缓存/实际重算、结果与口径引用、布局核验、降级特性；导出不发布 |
| TaskChange / Trace | `apply_semantic_change`、`revise_task_context`、`apply_asset_change`、`append_actual_event` | 目标/旧新版本、实际写入回执、作用域、受影响依赖、重验集合；不把建议记作已执行 |

SQL、代码、函数和 API 均可能写库、写文件、发消息或触发外部动作。副作用控制按**实际能力与行为**选择，不能按“SQL/代码/函数”入口名称认定只读。执行入口先校验声明和授权：纯读取走受限读取通道；可能有副作用的操作统一使用 DA07.7 的档位、授权/审批、幂等、预演及后置校验，再由相应适配器执行。代码环境通过只读挂载、网络/工具能力限制与受控动作代理落实声明；不能验证副作用边界的代码不得按只读通道执行。数据库写 SQL、本地写文件函数与远端写接口同样适用。未知结果不自动重放，补偿是新的受控动作。

## 3. 依赖方向与装配

```text
传输入口 / Registry / Agent 或 Preset 组合
                    ↓
 DA05 检索 ↔ DA06 计划修订；DA08/09 方法；DA10 展示与纠正
                    ↓
            DA07 已确定计划/表达执行
                    ↓
        特有协议 + 共享契约包 + 注入 Ports
                    ↑
             后端/服务 Adapters
```

图中双向箭头表示运行中的请求/反馈，不表示源码互相导入。规划器通过注入端口请求检索、程序生成或执行反馈；分析能力通过执行端口计算；执行器不导入规划器去选择方法。DA07.4 使用注入的动作控制链，DA07.7 调度写适配器，双方不以相互导入形成环。DA10 纠正器提交所属模块变更并读取新任务版本，再调用计划/执行/验证/渲染端口；不能自己维护第二套业务语义或企业记忆库。

治理层只依赖共同协议、契约/决策引用及事实回执端口，不依赖 `dataagent_application.execution` 等具体实现。数据层与应用层之间同理：按调用边界复用类型及端口，避免为了共享 `TableRef` 或回执而导入整个层。共享类型的提取由后续整体契约工作收敛，不强制本次修改数据层草稿。

引擎装配与替换必须同时检查接口、约定语义和业务效果：指定兼容目标时以目标后端版本或独立样本为依据；允许满足同一要求的等效实现，不要求所有业务复刻某个旧引擎。变更后独立验收由 DA11 实施；DA07.10 的 diff 与降级记录只是依据的一部分，不能靠自身测试声明业务通过。

# 机器可读能力目录

附本地接口与源码入口映射 JSON；本项目自拟目录，不是发行平台正式 manifest。

<figure view-type="Preview"><source name="dataagent-application-layer-v0.1-atomic-capability-catalog.json" mime="application/json" size="75257" token="Y8MSbhAkCoupbRxT2mecNMgqnvU"/></figure>