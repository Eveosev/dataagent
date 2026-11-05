---
version: v0.2
date: 2026-11-03
baseline: 总规划 r1045 编号
changes: 新增 DA11.2.5、DA11.5.7、DA11.6.4、DA12.1.4、DA12.2.6、DA12.10.5，改写 DA11.4.1、DA11.4.5（67 → 73 项）
---

# DataAgent 评测与治理层：模块与原子能力接口设计

> [返回 Pluggable DataAgent 总规划与分层索引](00-pluggable-dataagent.md)

# DataAgent 评测与治理层设计

目标：为动态组合的 DataAgent 能力提供可复核的业务验收、过程评测、访问约束和资产变更治理，让方法、代码与中间路径可以替换，同时守住正式业务目标、证据和权限边界。令才规则审核等场景按制度提取、规则审核、UNKNOWN 处理与交付的端到端效果验收，不要求固定某个表达式、提示词或工具序列。

其他层级及跨层交接见 [Pluggable DataAgent 总规划与分层索引](00-pluggable-dataagent.md)。

## 1. 模块总输入输出

| 模块 | 模块输入 | 模块输出 | 责任边界 |
|-|-|-|-|
| DA11 评测与验证 | 版本化计划/结果/程序/模型/规则，已确认判据，分角色样本，真实执行/授权轨迹，生产旁路输入 | 质量/方法/回归/验收报告，独立样本清单，质量与覆盖/UNKNOWN/人工/成本/时延指标束，分环节门禁与熔断判定 | 判断结果对不对、过程合不合规；不产出正式业务计算结果，不决定正式发布，不颁发权限 |
| DA12 治理与资产维护 | 当前主体/委托与访问请求，资产和依赖版本，反馈/漂移，变更目标，验证报告，实际动作/授权回执 | 数据访问与脱敏决策，资产生命周期/生效回执，影响与可逆性评估，变更/补偿计划，重现清单，审计链与受控导出 | 管谁能用、版本是什么、改了什么；复用平台/源端鉴权及 DA16 委托审批，不执行业务计算 |

DA11.9 名为“上线门禁”，输出的是绑定范围、环节、版本和期限的技术/业务条件判断。正式发布由 DA12.5 按既定发布策略控制，委托和动作审批由 DA16/平台承担。这三种结果分别保存，不能将一份通过报告当作可写生产系统的授权。

## 2. 共用契约与新增对象

所有能力沿用数据层的 [CallContext、CapabilityResult 与基础引用](01-data-layer.md)：

```text
invoke(operation, input, CallContext) -> CapabilityResult<T>
```

以下原子表只列业务输入与 `data` 输出。请求身份、作用域、授权引用、预算、deadline、`expected_revision`、幂等键沿用公共上下文；返回 `status=ok/partial/needs_input/pending/failed`、`issues`、实际 `execution_ref`、`provenance`、`completeness`、`continuation`。`ok` 表示执行完成，报告内仍可是失败或未知；访问决策的 `deny` 也是业务结论，不应伪装为成功读取空数据。策略不可取得时 `indeterminate` 默认不放行受控访问。

复用 `AssetRef/ResourceRef/SourceAnchor/SnapshotRef/SemanticRef/ArtifactRef/TraceEventRef/ValidationReportRef`；大内容经受控引用传递。所有报告至少固定目标/依赖版本、判据/策略版本、样本范围、执行实现版本与时间、实际证据、分母和局限。不得把时间戳或 digest 当作可重跑快照。新增类型如下，精确 JSON Schema 待实现前冻结：

| 对象 | 最小字段草案 | 关键含义 |
|-|-|-|
| `AcceptanceCriteriaDraft / CriteriaRef` | id/revision、业务交付、预期/证据要求、覆盖域与分层、容差、质量及成本门槛、unknown_policy、owner/confirmation_ref、状态与生效区间 | 草案可修改；正式版本由有权主体确认。修复可提出新版本，旧版本验收结果仍保留，不用候选标准替换当前正式标准 |
| `EvaluationCase / EvaluationSetRef` | 输入/预期/证据引用、来源与修订、分组键、split_role、内容指纹、授权、暴露台账、标注状态 | split_role 为 development/regression/unseen_acceptance；实体/时间/来源簇隔离，修复者不可读取未见金标。暴露过的样本不再是未见样本 |
| `ValidationReportRef / RegressionReport / AcceptanceReport` | 目标与基线、criteria_ref、sample_set_ref、依赖/实现版本、逐项 verdict、metrics、evidence_refs、limits、run_ref | 统一报告封套，各方法保留专属指标；verdict 为 pass/fail/unknown/not_applicable，not_applicable 必须给范围依据。报告不是发布或访问许可 |
| `MetricBundle` | quality 指标与分母、coverage、unknown、human_count/time、cost/currency、latency 分位数、分层与样本数、缺失记录 | 六类指标并报；质量指标可采用 precision/recall/数值误差等业务定义，不把不可判定、失败、未覆盖样本排出总体以美化结果 |
| `PolicyRef / AccessDecision` | policy_kind/version、issuer/scope、有效时间、主体/动作/资源/用途绑定、allow/deny/indeterminate、字段/行约束、脱敏义务、理由与来源决策 | 复用已有身份与源端控制，引用本身无权限；决策必须绑定请求范围，必要时在读取、检索、缓存命中、导出及执行点重新校验 |
| `GateAssessment / CircuitBreakerDecision` | 环节、当前/建议档位、目标版本、证据窗口、触发阈值、条件、有效期、撤销/恢复条件、实际控制回执（若有） | 门禁评估与权限授予分离；各环节单独给档，旧报告不永久有效。受授权的安全降档可直接执行并留回执 |
| `ChangeRequest / ChangeDecision` | 目标类型/作用域、base/expected_revision、patch_ref、原因、授权/验证引用、直接允许/拒绝/待澄清/待审阅、义务/期限 | 写入前检查版本冲突及实际授权。满足现有授权和策略即可生效，不要求所有治理动作再次人工确认 |
| `ChangePlan / ImpactReport / ReversibilityAssessment` | 当前/目标版本、破坏性、依赖路径与 basis、影响范围/不确定上界、回填区间/成本、前置条件、dry_run、回滚/补偿与残留影响 | 计划与风险评估无副作用；依赖缺口不视为零影响，资产回滚与外部补偿是不同操作 |
| `VersionGovernanceReceipt / ActivationReceipt / RollbackReceipt` | 对象及旧/新版本、生命周期状态、授权/政策/验证引用、实际保存/切换回执、作用域/时间、部分失败与后续项 | 生命周期状态 draft/validated/active/deprecated/invalidated 是共享 `LifecycleStatus`（总文档 §2.4）的治理子集，后续与实际仓储状态适配；发布状态与内容存储分开 |
| `ReproductionManifest / ReplayabilityAssessment` | 结果 run_ref、数据/语义/程序/模型/提示/参数/环境版本、随机条件、解析/保留能力、缺项、可重现级别 | 记录实际运行条件。只有当前可取的版本才可重读；不具备模型或来源历史时明确条件性或不可重现 |
| `AuditChainRef / DecisionBasisLink / RetentionReceipt` | 实际事件与输入/授权/结果/依据关联、后端来源、rule/condition/field 等实际粒度、断链、保留策略/保证等级、导出权限 | DA04.1 提供事实轨迹，后端提供判定细节。只做真实关联，不由审计器生成不存在的表达式 trace；不可篡改依赖真实后端能力 |

正式验收前冻结判据和未见集版本，并记录执行器读取范围。若修复需要查看失败用例，该用例降为回归样本，再用未暴露样本验收。正式标准确需变更时，由有权主体确认新版本，保留新旧标准与差异；不得用调优或归因流程暗中放宽。

## 3. 能力组与拟议代码文件

每个组的文件位于拟议工作区 `packages/capabilities/dataagent-governance/` 的 `src/dataagent_governance/` 下。表中是组级汇总；每个原子入口、详细输入输出见下一节。一个组文件可在复杂后展开为子包，稳定 ID 不变。

| 编号 / 能力组 | 形态 | 组级输入 → 输出 | 作用边界 | 拟议文件 | 原子数 |
|-|-|-|-|-|-|
| DA11.1 数据质量检查 | 软 | 版本化表/画像、字段约束、对账键/口径 → 逐字段违规/重复缺失/差额报告与未检查范围 | 检查缺失、重复、类型、约束及跨源对账。 调用 DA02 的画像，不重复做数据准备。 | `evaluation/data_quality.py` | 3 |
| DA11.2 计算计划与结果验证 | 软 | SQL/接口/表达式计划、结果、语义版本与对照来源 → 表达有效性、口径/粒度/合并差异及正确性报告 | 检查 SQL、接口参数或表达式的有效性，以及时间、单位、分页完整性、Join 膨胀和结果一致性。 执行成功不等于业务正确。 | `evaluation/computation.py` | 5 |
| DA11.3 方法效果评估 | 软 | 统计/预测/仿真/方案版本、数据分布、验证窗口与资源约束 → 方法专属诊断、回测/校准误差及可行性条件 | 检查统计方法、预测回测、仿真校准和方案可行性。 按方法分别评估，不统一成一个正确率。 | `evaluation/methods.py` | 4 |
| DA11.4 回归评测 | 硬 | 候选/基线组件或组合、分角色样本、冻结依赖与判据 → 逐样本/分层回归差异及质量和资源指标束 | 对候选组件、程序和组合运行回归，比较业务质量、覆盖率、UNKNOWN、人工量、成本与时延。 固定必要版本，不能复原时说明限制。 | `evaluation/regression.py` | 5 |
| DA11.5 评测判据与样本 | 软·定 | 业务交付要求、确认主体、历史纠正/基线、样本来源与划分策略 → 判据草案/正式引用、分角色评测集、暴露台账及验收报告 | 围绕业务交付定义预期结果、覆盖范围、证据、容差及成本要求，构建开发与独立验收样本。 正式标准由有权主体确认，不随修复自动放宽；开发样本与未见验收样本分开。可按业务分层定位，不规定固定中间实现。 | `evaluation/criteria_samples.py` | 7 |
| DA11.6 持续改进度量 | 软 | 分租户/任务运行、纠正/澄清、启停对照、计费和人工记录 → 趋势/贡献证据、六类交付指标与样本局限 | 判断系统是否随使用变好，以及哪些记忆和配置起了作用。 按租户和任务类型分别统计；样本不足时说明，不用个例代表整体。 | `evaluation/improvement.py` | 4 |
| DA11.7 影子运行 〔FDE〕 | 软 | 受控生产输入、隔离影子配置、人工结果与对齐规则 → 旁路回执、逐条差异与有证据的归因 | 在不影响生产的前提下积累证据。 不把影子结果当成已生效。 | `evaluation/shadow.py` | 3 |
| DA11.8 双轨评测 〔FDE〕 | 软 | 结果、独立预期、真实调用轨迹、当时授权/审批政策 → 正确性/合规双报告、义务级轨迹回归及观测缺口 | 同时评「对不对」和「该不该」。 不只测最终答案。 | `evaluation/dual_track.py` | 3 |
| DA11.9 上线门禁 〔FDE〕 | 软·定 | 回归/影子/双轨报告、分环节风险门槛、变更差异与失败窗口 → 范围/版本/期限绑定的门禁、档位建议与熔断决定 | 决定能否扩大自主度，且分环节而非整体判断。 不用一次评审永久放行；某一环节的自主度不得外溢到下一环节。 | `evaluation/gates.py` | 3 |
| DA12.1 权限与敏感信息管理 | 硬 | 主体/委托、资源/动作/用途与有效策略、受控内容 → allow/deny/indeterminate、敏感标记、脱敏产物及义务 | 管理数据、记忆、检索及导出的访问与脱敏要求。 复用平台和源端控制，并在各使用环节生效；执行权限与“数据可进入模型上下文”分别判定（DA12.1.4）。 | `governance/access.py` | 4 |
| DA12.2 资产版本管理 | 硬 | 数据/语义/记忆/沉积物变更、依赖/验证/生命周期政策 → 版本治理回执、状态/生效范围、回滚点与实际重放结果 | 管理数据引用、语义、记忆和分析资产的版本、失效及发布状态。 包版本不能替代数据版本；不承诺任意历史都可重算。 | `governance/versions.py` | 6 |
| DA12.3 反馈与更新建议 | 软 | 反馈/错误/漂移、真实轨迹与资产依赖版本 → 归集记录、原因候选、失效评估及待执行更新提案 | 汇总用户纠正、错误和漂移，提出资产更新建议。 建议与共享资产更新分开，重要变更可交业务审阅。 | `governance/feedback.py` | 4 |
| DA12.4 变更影响分析 | 软 | 数据/口径/权限差异、版本化血缘与使用关系 → 受影响查询/指标/报表/访问点、传播路径与覆盖缺口 | 使用血缘和资产使用关系，评估字段变更、规则修订或撤权对查询、指标和报表的影响。 依赖查找复用 DA05.7；不自动认定所有下游都失效或执行回滚。 | `governance/impact.py` | 3 |
| DA12.5 交互变更控制 | 软 | 变更对象/范围/当前版本、授权与验证依据 → 允许/拒绝/待澄清/待审阅、实际生效/撤销回执与补偿计划 | 检查修改对象、作用域、当前版本、权限及必要验证，决定直接写入、待澄清或待审阅。 明确授权且满足策略时即时生效，不默认追加一次确认；源系统写入与共享资产发布分别记录结果。 | `governance/change_control.py` | 3 |
| DA12.6 重现条件管理 | 软 | 结果与实际运行、历史快照/语义/程序/模型/参数/环境引用 → 实际版本清单、可重现级别及缺失条件 | 汇总已有快照、口径、代码、模型及参数引用，判断一次计算能否重现。 存储复用数据与资产能力，缺少历史条件时明确标注。 | `governance/reproduction.py` | 2 |
| DA12.7 变更计划 | 软 | 目标/当前版本、影响/可逆性、回填预算与策略 → 可审阅步骤、前置授权、隔离试运行差异与未模拟范围 | 为接入新源、改结构、改语义、改权限、回填、写回和发布生成可审阅的计划。 影响范围复用 DA12.4；是否执行由 DA12.5 决定，计划本身不产生写入。 | `governance/change_plans.py` | 2 |
| DA12.8 配置调优 | 软 | 候选/基线 Preset、固定样本/判据、回归与持续指标、灰度授权 → 配置对比报告、调优建议和经允许的生效/回退回执 | 根据回归评测和持续改进度量调整 Preset 配置。 仅在 DA11.4 回归通过后生效，可回退；不借调优修改业务语义。 | `governance/tuning.py` | 2 |
| DA12.9 跨租户经验沉淀 〔FDE〕 | 软 | 租户经验、明确跨租户用途授权、敏感/专有信息规则与领域包基线 → 脱敏通用经验和维护者待审领域包补丁 | 在租户授权后，把通用的方法、模板和术语沉淀到领域包。 不回流原始数据、企业专有口径或可识别信息；更新经领域包维护者审阅后发布。 | `governance/cross_tenant.py` | 2 |
| DA12.10 证据链与审计 〔FDE〕 | 硬 | 实际动作/结果、输入版本、授权回执、DA04事件与后端真实依据 → 有粒度/断链声明的审计链、实际保留回执和受控导出 | 按审计要求关联实际调用、输入版本、授权、结果与判定依据，并管理保留和导出。 执行依据复用 DA04.1；条件级轨迹来自后端实际记录，无法提供时标注粒度和缺口，不由审计器推断补造。 | `governance/audit.py` | 5 |
| DA12.11 爆炸半径评估 〔FDE〕 | 软·定 | 动作契约、目标范围、影响图、回滚/补偿能力与风险政策 → 影响等级、可逆条件/残留影响、待确认分级阈值政策 | 在执行前判断影响范围。 执行前影响面评估以本组为唯一产出方，DA07.7.3 预演差异为输入；不替代审批，审批归 DA16。 | `governance/blast_radius.py` | 3 |

## 4. DA11 评测与验证：逐项原子契约

表内返回类型均包裹于 `CapabilityResult<T>`。调用注册格式为 `dataagent_governance.<模块>.<组文件>:<operation>`；表中每组给出完整文件位置，原子行给出 operation，与 JSON 目录逐项一致。

### DA11.1 数据质量检查

拟议文件：`src/dataagent_governance/evaluation/data_quality.py`；入口前缀：`dataagent_governance.evaluation.data_quality:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.1.1 字段约束检查 | `check_field_constraints` | TableRef/SchemaRef、已确认约束版本、检查范围与画像引用 | ConstraintReport；逐字段违规计数/记录键/源锚点、未检查约束 | 复用 DA02.4 画像和源端约束；不自动清洗，也不把样本零违规外推为全量合格。 |
| DA11.1.2 重复/缺失检查 | `check_duplicates_and_missing` | 数据批次或快照、业务键定义、必填字段、空值语义及统计预算 | CompletenessReport；重复键组、缺失分布、分母、采样范围及估计误差 | 缺失与合法空值分开；仅报告问题，不静默删重或填值。 |
| DA11.1.3 跨源对账 | `reconcile_sources` | 两侧数据版本、对账键/指标、时间与币种口径、允许容差 | ReconciliationReport；匹配/单边/差额明细、汇总差异、未匹配原因 | 对齐口径必须显式；源端不可同快照时报告时间差，不补造一致性。 |

### DA11.2 计算计划与结果验证

拟议文件：`src/dataagent_governance/evaluation/computation.py`；入口前缀：`dataagent_governance.evaluation.computation:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.2.1 执行表达检查 | `check_execution_expression` | 计划中的 SQL/API 参数/表达式、声明的方言或后端、输入结构、动作契约 | ExpressionCheckReport；语法/类型/参数诊断、支持范围、可执行性未知项 | 仅调用解析或无副作用校验；需要试运行时经执行端口，检查通过不代表业务正确或获准执行。 |
| DA11.2.2 业务口径检查 | `check_business_definition` | 计划与结果引用、指标/规则语义版本、时间/单位/过滤条件、验收判据 | DefinitionCheckReport；口径逐项匹配、偏差锚点、缺失定义及影响 | 只能按已确认定义检查；不在修复时重定义正式业务口径。 |
| DA11.2.3 结果粒度与合并检查 | `check_result_grain_and_merge` | 输入/输出表引用、声明粒度、Join 键/基数、聚合与分页回执 | GrainMergeReport；实际键重复、Join 膨胀、粒度冲突、分页缺口 | 源端未提供总量或一致快照时保留未知；不以行数接近认定合并正确。 |
| DA11.2.4 结果对照验证 | `validate_against_reference` | 待验证结果、独立参考结果/来源、对齐规则、容差与比较范围 | ComparisonReport；逐项一致/差异/不可比、参考来源版本与覆盖 | 参考来源自身可信度另记；多数一致不能覆盖已知反例，缺少参考不判通过。 |
| DA11.2.5 语义陷阱反例检查 | `check_semantic_counterexamples` | 计划与结果引用、反例集版本（跨租户同 ID、复合键缺列、迟到/退款、join 膨胀、SCD 边界）、语义版本 | CounterexampleReport；逐反例通过/失败/不适用、最小失败样本 | 反例集由 DA11.5 管理；通过反例不等于业务正确，未覆盖的陷阱类型显式列出。 |

### DA11.3 方法效果评估

拟议文件：`src/dataagent_governance/evaluation/methods.py`；入口前缀：`dataagent_governance.evaluation.methods:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.3.1 统计方法适用性检查 | `assess_statistical_method` | 统计方法/参数、数据画像与采样设计、业务问题、前提假设 | MethodAssessment；假设检查、适用/不适用/证据不足、诊断统计与替代建议 | 相关性与因果性分别解释；小样本、选择偏差与多重检验限制须保留。 |
| DA11.3.2 预测回测 | `backtest_forecast` | 模型与训练窗口版本、时序样本、滚动切分方案、预测周期及损失指标 | BacktestReport；按窗口/分层误差、基线比较、泄漏检查和失败区间 | 时间切分不能让未来信息进入训练；回测不保证未来收益或替代上线批准。 |
| DA11.3.3 仿真校准检查 | `check_simulation_calibration` | 仿真模型/参数、观测基线、校准集与独立验证集、容差、随机种子 | CalibrationReport；拟合与验证误差、敏感性、不可辨识参数及偏差范围 | 校准集效果与未见样本效果分报；拟合良好不自动证明机制或外推成立。 |
| DA11.3.4 方案可行性检查 | `check_solution_feasibility` | 候选方案、资源/成本/时限约束、动作前置条件、环境事实版本 | FeasibilityReport；约束满足度、冲突、依赖缺口、风险与条件性结论 | 评估可行性，不发起采购/修改或审批；环境未知时输出条件与待核查项。 |

### DA11.4 回归评测

拟议文件：`src/dataagent_governance/evaluation/regression.py`；入口前缀：`dataagent_governance.evaluation.regression:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.4.1 检索回归评测 | `evaluate_retrieval_regression` | 候选/基线检索配置、查询集与相关性标注、索引/语义快照、TopK 与预算 | RegressionReport；必要集合全召回、误选后恢复与停止正确性（DA05.9）、Recall/Precision/排序指标、覆盖、UNKNOWN、人工量、成本时延及分层差异 | 固定可固定的索引与依赖版本；未标注相关性不可算零相关，不能只报命中样本。 |
| DA11.4.2 问数回归评测 | `evaluate_question_answering_regression` | 候选/基线组合版本、历史问题与预期值/容差、数据和语义版本、运行预算 | RegressionReport；答案正确性、口径/证据质量、覆盖、UNKNOWN、人工量、成本时延 | 允许查询路径不同；数据历史不可重读时注明不可比范围，不把执行成功计为答对。 |
| DA11.4.3 分析任务回放评测 | `replay_analysis_tasks` | 历史任务输入/上下文、候选程序或组合、预期交付与判据、重跑条件清单 | RegressionReport；交付质量、关键差异、步骤回执、资源指标和重现缺口 | 经 DA07 隔离重放；历史外部写入默认禁用，无法恢复的条件不能以当前状态代替。 |
| DA11.4.4 规则库回归：改规则或改提示后重跑历史报文 | `evaluate_rule_library_regression` | 规则/提示/程序候选与基线、历史报文版本、金标/判据、后端版本 | RuleRegressionReport；逐规则/业务分层混淆项、UNKNOWN/漏判、覆盖、人工量、成本时延 | 不为候选改金标或放宽验收阈值；历史纠正用于回归后不能仍声称未见验收。 |
| DA11.4.5 引擎一致性回归编排 | `orchestrate_engine_consistency_regression` | 固定版本化样本集、子集与权威引擎版本、规则语义映射、支持边界 | RegressionReport；引用 DA07.10.2 的 EngineConsistencyReport，一致/不一致/不支持/执行未知汇总、最小差异样本 | 比对本身由 DA07.10.2 产出，本原子只编排样本与汇总；权威引擎由业务配置确认，禁止猜测权威结果或补造子条件 trace。 |

### DA11.5 评测判据与样本

拟议文件：`src/dataagent_governance/evaluation/criteria_samples.py`；入口前缀：`dataagent_governance.evaluation.criteria_samples:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.5.1 业务验收判据定义 | `draft_acceptance_criteria` | 业务交付目标、有权主体要求、任务分层、质量/覆盖/资源约束、现有判据版本 | AcceptanceCriteriaDraft；预期结果、证据、容差、分母、阈值、样本角色与待确认项 | 形成草案并附确认引用后冻结正式版本；修复方不能自行降低标准，也不固定中间实现。 |
| DA11.5.2 人工纠正转评测样本 | `convert_corrections_to_cases` | 用户纠正事件、原问题/输入版本、纠正依据、可用授权与冲突标注 | EvaluationCaseDraft；输入、预期、证据、来源纠正引用、角色建议及待审歧义 | 人工纠正不天然是真值；去标识并核对依据，已暴露样本标为开发或回归。 |
| DA11.5.3 边界与反例构建 | `build_boundary_and_counterexamples` | 业务定义/规则版本、已知失败模式、有效输入域、生成预算与样本策略 | EvaluationCaseDraft 列表；边界/反例标签、预期推导、分层覆盖和有效性检查 | 合成样本与真实样本分别统计；不以不合法输入制造虚假覆盖，候选预期需确认。 |
| DA11.5.4 接入基线构建：将伙伴提供的历史问答、报表数字整理为初始评测集 | `build_onboarding_baseline` | 伙伴历史问答/报表版本、统计窗口、字段映射、口径与来源证明 | EvaluationSetDraft；对齐后的初始用例、金标候选、数据条件、冲突与基线摘要 | 接入基线用于对齐和回归；历史答案可能过时，已向开发公开者不能算未见样本。 |
| DA11.5.5 端到端业务验收〔定〕 | `evaluate_business_acceptance` | 冻结且获确认的判据版本、隔离验收集、交付结果、证据与依赖版本、执行回执 | AcceptanceReport；逐判据通过/失败/未知、业务分层差异、完整指标束和验收范围 | 判据和独立样本不得随修复放宽或泄露；允许方法流程不同，通过不授予发布或业务动作权限。 |
| DA11.5.6 验收样本隔离 | `isolate_acceptance_samples` | 用例来源/内容指纹、分组键、开发/回归/未见验收划分策略、访问与暴露事件 | EvaluationSetRef；不可变划分清单、角色/曝光台账、近重复/关联泄漏告警及可用状态 | 按实体/时间/来源簇防泄漏；验收执行器受控读金标，开发仅获汇总，暴露后降为回归并补充独立样本。 |
| DA11.5.7 多角色越权用例构建 | `build_cross_role_cases` | 角色与权限策略版本、同题问题集、敏感字段/行规则 | 多角色评测用例；每个角色的期望可见范围与结果差异 | 使用受控测试身份，不以真实用户凭据构造；用例只存期望范围，不存敏感值。 |

### DA11.6 持续改进度量

拟议文件：`src/dataagent_governance/evaluation/improvement.py`；入口前缀：`dataagent_governance.evaluation.improvement:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.6.1 使用效果趋势：同类问题首答正确率、澄清次数、纠正率随时间的变化 | `measure_usage_trends` | 按租户/任务类型分层的运行记录、首答/纠正/澄清定义、时间窗口与分母 | TrendReport；首答正确率、澄清/纠正趋势、样本数、置信区间与流量构成变化 | 按相同比较口径统计，未知真值不算正确；不能用单个成功任务证明整体改善。 |
| DA11.6.2 经验贡献评估：启用与不启用某类经验或配置的对照 | `assess_experience_contribution` | 启用/禁用经验或配置的对照运行、分配机制、版本绑定、质量与资源指标 | ContributionReport；配对或分组差异、混杂因素、效应区间与证据强度 | 观测相关与受控实验结论区分；未隔离模型/流量变化时不宣称单一经验导致改进。 |
| DA11.6.3 覆盖与交付成本度量 | `measure_coverage_and_delivery_cost` | 声明业务总体、逐样本判定/未覆盖/UNKNOWN、人工介入记录、计费与延迟回执 | MetricBundle；业务质量、覆盖率、UNKNOWN率、人工次数/工时、成本、P50/P95时延及分母 | 六类指标并报并按任务分层；失败和预算耗尽计入总体，计费或人工记录缺失显式报告。 |
| DA11.6.4 接入与维护成本度量 | `measure_onboarding_and_maintenance_cost` | 接入任务与变更记录、人工工时记录、首个可信答案时间点、专家介入记录 | CostMetricBundle；首个可信答案耗时、首次接入工时、每次变更修复工时、专家处理比例及分母 | 缺失记录显式报告；不以对话量或 SQL 执行率替代。 |

### DA11.7 影子运行 〔FDE〕

拟议文件：`src/dataagent_governance/evaluation/shadow.py`；入口前缀：`dataagent_governance.evaluation.shadow:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.7.1 旁路执行 | `run_shadow_execution` | 生产输入受控引用、影子实现/配置、只读或模拟动作端口、隔离预算 | ShadowRunRef；旁路结果、实际调用回执、隔离证明范围与失败项 | 生产写入端口不可直连；无法隔离的动作返回不支持，影子结果不作为已生效事实。 |
| DA11.7.2 与人工结果比对 | `compare_with_human_results` | 影子输出、人工处置结果与时间版本、对齐键、判据和不可比条件 | ShadowComparisonReport；逐条一致/差异/未知、覆盖与人工标签可信度 | 人工结果可被复核；后续补录与影子当时可见信息分别记录，避免事后信息偏差。 |
| DA11.7.3 差异归因 | `attribute_shadow_differences` | 影子/人工差异、输入/配置/轨迹版本、参考依据、可核查假设 | DifferenceAttribution；数据/口径/程序/权限/时序等原因候选、证据与未确认项 | 证据不足时保留归因候选；不通过改生产结果消除差异。 |

### DA11.8 双轨评测 〔FDE〕

拟议文件：`src/dataagent_governance/evaluation/dual_track.py`；入口前缀：`dataagent_governance.evaluation.dual_track:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.8.1 结果正确性 | `evaluate_result_correctness` | 交付结果、独立预期/判据、证据引用、业务适用范围 | CorrectnessReport；正确/错误/未知、证据支撑度、覆盖及分层错误 | 与过程合规报告分开；过程合规不能替代正确，缺数据不强行二值判定。 |
| DA11.8.2 过程合规性：越权、审批纪律、工具正确性 | `evaluate_process_compliance` | 实际调用轨迹、当时授权/审批记录、动作契约、工具限制、有效策略版本 | ComplianceReport；越权/缺审批/工具误用事件、符合项、轨迹缺口与严重度 | 复用平台鉴权与 DA16 事实；缺事件标不可审计，不把有证据当有权限，不强设每步人工审批。 |
| DA11.8.3 轨迹级回归 | `evaluate_trace_regression` | 候选/基线实际轨迹、过程合规判据、任务等价关系、输入与环境版本 | TraceRegressionReport；义务满足差异、越权回归、新增等待/人工/成本和观测缺口 | 比较业务义务与约束，不要求工具序列逐字相同；未记录的内部推理不可补生成事实轨迹。 |

### DA11.9 上线门禁 〔FDE〕

拟议文件：`src/dataagent_governance/evaluation/gates.py`；入口前缀：`dataagent_governance.evaluation.gates:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA11.9.1 按环节分档的自主度：沟通 / 修改 / 审核 / 测试 / 发布 / 观测，每环节四档（人工 → 人工确认 → 自动+抽检 → 自动） | `assess_stage_autonomy` | 回归/影子/双轨报告、环节清单、当前档位、风险/样本门槛及有效政策 | GateAssessment；沟通/修改/审核/测试/发布/观测各自建议档位、放行/拦截条件、有效期 | 每环节人工→人工确认→自动+抽检→自动；仅评估门禁，实际授权由 DA16/平台承载，档位不向后续环节外溢。 |
| DA11.9.2 契约与模型变更回归 | `evaluate_contract_model_change` | 契约/模型变更差异、受影响能力/任务范围、冻结判据、回归/独立实测集 | ChangeGateReport；兼容与业务回归、受影响环节、拦截项及重验条件 | 签名兼容不等于业务可靠；报告绑定变更版本，不能凭旧模型报告永久放行。 |
| DA11.9.3 失败率熔断 | `apply_failure_circuit_breaker` | 分环节运行窗口、失败/UNKNOWN分母、已授权熔断阈值、最小样本及恢复策略 | CircuitBreakerDecision；触发范围、降档/暂停建议或受控回执、原因和恢复验证条件 | 只按既定授权执行熔断控制；稀疏样本显式处理，恢复需新证据，不能自动扩大既有权限。 |

## 5. DA12 治理与资产维护：逐项原子契约

### DA12.1 权限与敏感信息管理

拟议文件：`src/dataagent_governance/governance/access.py`；入口前缀：`dataagent_governance.governance.access:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.1.1 访问范围检查 | `check_access_scope` | 当前主体/委托引用、资源版本、请求动作、用途、租户/项目范围、有效策略 | AccessDecision；allow/deny/indeterminate、允许字段/行/用途、脱敏义务、有效期及依据 | 复用平台身份与源端鉴权，不新建身份系统；数据/记忆/检索/导出均需适用检查，证据不等于授权。 |
| DA12.1.2 敏感信息识别 | `identify_sensitive_information` | 获准读取的数据/文档引用、字段结构、租户分类规则、检测范围与预算 | SensitivityReport；敏感字段/片段锚点、分类、方法置信度、未扫描范围 | 检测在授权域内运行；不得因检测任务扩大读取范围，也不把未检出宣称无敏感信息。 |
| DA12.1.3 数据脱敏 | `mask_sensitive_data` | 原内容受控引用、敏感标记、AccessDecision、脱敏策略版本、接收方与用途 | MaskedArtifactRef；替换后内容、转换摘要、剩余风险与脱敏回执 | 脱敏不自动许可跨租户共享；保留原件隔离、键映射受控，日志和错误输出同样遵守限制。 |
| DA12.1.4 模型上下文可见性与外发控制 | `check_model_context_egress` | 拟送入模型的内容引用、模型/服务部署位置与数据处理条款、AccessDecision、脱敏策略 | EgressDecision；允许/脱敏后允许/拒绝、可见字段范围、外发目的地与回执 | 执行权限与“数据可进模型”分别判定；日志、缓存、提示词同样受限。 |

### DA12.2 资产版本管理

拟议文件：`src/dataagent_governance/governance/versions.py`；入口前缀：`dataagent_governance.governance.versions:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.2.1 数据版本引用管理 | `govern_data_version_references` | 数据/快照引用、源版本与可读性、版本政策、期望当前修订及变更原因 | VersionGovernanceReceipt；数据引用新修订、状态/保留/失效依赖、实际保存回执 | 定义版本与生命周期政策，具体快照存储复用 DA02.11；包版本或 digest 不能代替可重读数据。 |
| DA12.2.2 语义版本管理 | `govern_semantic_versions` | 语义候选/已有版本、有效期、依赖定义、版本/发布政策、验证与授权引用 | VersionGovernanceReceipt；新语义版本状态、生效区间、前驱/冲突和保存回执 | 语义正文实际保存复用 DA03.6；保存、验证、正式发布分开，不能由版本登记暗中改变业务口径。 |
| DA12.2.3 记忆/分析资产版本管理 | `govern_memory_and_analysis_versions` | 记忆/程序/模板/组合引用、适用范围、依赖版本、验证报告与生命周期政策 | VersionGovernanceReceipt；新版本/停用/发布状态、回滚点、依赖失效范围和保存回执 | 实际内容保存复用 DA04；共享发布仍经有效策略，不因本地保存而自动晋升企业经验。 |
| DA12.2.4 决策缓存版本化：判定缓存、预筛规则、模板等沉积物的版本 | `version_decision_residue` | 判定缓存/预筛规则/模板内容引用、适用域、输入指纹、依赖版本、到期与验证策略 | DecisionResidueRef；不可变版本、依赖绑定、命中限制、失效条件与登记回执 | 缓存只在依赖及范围仍有效时复用；禁止把旧判定当永久事实，具体内容存储由资产端口承担。 |
| DA12.2.5 沉积物回滚：撤回错误沉积并重放受影响样本 | `rollback_decision_residue` | 错误沉积版本、目标回滚点、受影响样本/命中记录、授权与重放预算 | RollbackReceipt；停用/恢复版本、缓存失效范围、重放作业/结果及未修复项 | 重放经 DA11/DA07 隔离执行；回滚资产不保证逆转已发生外部副作用，必要时生成补偿计划。 |
| DA12.2.6 规范与转换器版本登记 | `register_spec_and_converter_versions` | 外部规范名与版本、转换器版本、关联语义发布版本 | SpecVersionRecord；规范/转换器/语义版本三元关联 | 与本方语义发布版本分开登记；草案规范标记为草案，不当作稳定规范引用。 |

### DA12.3 反馈与更新建议

拟议文件：`src/dataagent_governance/governance/feedback.py`；入口前缀：`dataagent_governance.governance.feedback:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.3.1 用户反馈归集 | `collect_user_feedback` | 反馈/纠正事件、原任务/结果/资产引用、主体与时间、归集范围及保留策略 | FeedbackCollectionRef；去重反馈、可追溯来源、冲突意见、脱敏与权限标记 | 归集不改写原轨迹，也不把反馈直接当金标或正式资产修订。 |
| DA12.3.2 任务错误归因 | `attribute_task_errors` | 失败任务轨迹、输入/语义/代码版本、反馈/参考结果、环境变化 | ErrorAttributionReport；原因候选、责任边界、证据、可复现条件和未知因素 | 事实与推测分开，避免把模型自述当实际调用证据；不自动惩罚或修改来源数据。 |
| DA12.3.3 资产失效检测 | `detect_asset_invalidation` | 资产依赖、期限/适用域、来源变化/撤权/质量事件、当前验证状态 | InvalidationAssessment；需复核/失效候选、受影响版本与证据、范围和紧急程度 | 检测复用实际依赖与 DA05.7；不因任意上游变化使全部历史结果永久失效，停用按既有政策执行。 |
| DA12.3.4 更新建议生成 | `propose_asset_updates` | 反馈归因、失效评估、资产当前版本、业务目标及约束 | AssetUpdateProposal；建议补丁/新版本、影响范围、验证需求、优先级与未决问题 | 仅输出建议；写入与共享发布交 DA12.5，正式判据修改另由有权主体确认。 |

### DA12.4 变更影响分析

拟议文件：`src/dataagent_governance/governance/impact.py`；入口前缀：`dataagent_governance.governance.impact:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.4.1 数据变更影响分析 | `assess_data_change_impact` | 字段/结构/数据差异、版本化数据血缘、使用记录、待变更范围 | ImpactReport；受影响查询/指标/报表、依赖路径、破坏性候选、覆盖缺口 | 依赖查找复用 DA05.7，声明/推断/观测边分开；不自动认定下游全部失败或执行回滚。 |
| DA12.4.2 业务口径变更影响分析 | `assess_semantic_change_impact` | 指标/规则/实体定义差异、语义依赖/物理映射、调用和产物使用记录 | ImpactReport；口径变化传播、受影响资产/历史解释、需重验任务及依据 | 业务生效时间与记录时间分开；历史结果保留当时定义，不静默重释。 |
| DA12.4.3 权限变更影响分析 | `assess_permission_change_impact` | 撤权/范围/用途策略差异、主体绑定、资产与导出/缓存使用记录 | ImpactReport；可访问性变化、缓存/检索/导出受影响点、可撤回与不可收回范围 | 不直接代替平台撤权；已离域副本未必可撤回，记录未观测流转和访问传播缺口。 |

### DA12.5 交互变更控制

拟议文件：`src/dataagent_governance/governance/change_control.py`；入口前缀：`dataagent_governance.governance.change_control:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.5.1 写入授权与冲突检查 | `check_write_authorization_and_conflicts` | ChangeRequest、目标当前版本、expected_revision、现有授权/委托、必要验证报告 | ChangeDecision；直接允许/拒绝/待澄清/待审阅、冲突位置、执行义务与有效期 | 明确授权且条件满足时可直接写；读权限不等于写权限，正式验收报告也不替代发布授权。 |
| DA12.5.2 共享修订生效控制 | `control_shared_revision_activation` | 获准 ChangeRequest、候选/当前资产版本、验证与发布政策、目标作用域/灰度范围 | ActivationReceipt；已生效/待条件/冲突、实际版本、作用域、时间及发布回执 | 通过资产端口原子切换并检查并发；源端写入回执与共享发布回执分别记录，不默认再加人工确认。 |
| DA12.5.3 变更撤销与补偿计划 | `plan_revocation_and_compensation` | 已执行变更/发布回执、当前外部状态、回滚目标、可逆性评估、授权约束 | RevocationResult；可安全撤销部分的回执、补偿计划、不可逆影响与待授权动作 | 撤销资产可调用保存端口；外部补偿交 DA07/DA16 按权限执行，不将计划当已补偿或保证完全恢复。 |

### DA12.6 重现条件管理

拟议文件：`src/dataagent_governance/governance/reproduction.py`；入口前缀：`dataagent_governance.governance.reproduction:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.6.1 数据/语义/程序版本绑定 | `bind_reproduction_versions` | 结果与实际执行引用、数据快照、语义/程序/模型/提示/参数/环境版本 | ReproductionManifest；完整依赖组合、随机性/时间条件、缺失版本及解析状态 | 记录真实使用版本而非当前最新；实际保存复用数据层，不伪造不可取得的模型快照。 |
| DA12.6.2 历史重跑条件检查 | `check_historical_replay_conditions` | ReproductionManifest、目标重跑范围、现有解析能力/保留期、授权与运行环境 | ReplayabilityAssessment；可精确/条件性/不可重现、缺失条件、替代范围与风险 | 引用和 digest 存在不等于仍可读取；重新取得权限后才可运行，检查本身不执行重跑。 |

### DA12.7 变更计划

拟议文件：`src/dataagent_governance/governance/change_plans.py`；入口前缀：`dataagent_governance.governance.change_plans:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.7.1 变更计划生成：目标与版本、变更类型、是否破坏性、受影响资产、回填区间与成本、回退方式 | `draft_change_plan` | 变更目标/类型、当前与目标版本、ImpactReport、回填区间、成本预算、可逆性与政策 | ChangePlan；步骤/依赖/前置条件、破坏性标记、试运行、回填成本、回退方式与所需授权 | 生成可审阅计划，不产生写入；影响分析复用 DA12.4，执行许可由 DA12.5 与 DA16/平台负责。 |
| DA12.7.2 试运行与差异预览 | `preview_change_diff` | ChangePlan、隔离快照/测试环境、dry-run 能力声明、比较基线和预算 | DryRunReport；预期/实测差异、影响行/对象、回执、未模拟步骤与资源估计 | 复用 DA07 试运行；不支持真实 dry-run 的步骤禁止伪装执行，模拟差异不保证生产完全相同。 |

### DA12.8 配置调优

拟议文件：`src/dataagent_governance/governance/tuning.py`；入口前缀：`dataagent_governance.governance.tuning:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.8.1 Preset 配置对比评测：适配实现、阈值、检索参数等 | `compare_preset_configurations` | 基线/候选 Preset、实现/阈值/检索参数差异、固定回归集与版本、指标束 | ConfigurationComparisonReport；DA11.4 报告引用、分层质量/资源差异及候选适用范围 | 调优阈值不能偷换业务验收阈值或语义；沿用冻结判据，不用未见验收集反复搜索配置。 |
| DA12.8.2 调优建议与灰度生效 | `propose_and_activate_tuning` | 配置对比报告、通过的 DA11.4 回归、持续改进指标、灰度/回退条件及授权 | TuningDecision；调优建议、经允许的灰度配置版本/生效回执、观测窗口与回退触发 | 未回归通过不得生效；实际激活复用 DA12.5，灰度范围不扩大权限，异常可按既定策略回退。 |

### DA12.9 跨租户经验沉淀 〔FDE〕

拟议文件：`src/dataagent_governance/governance/cross_tenant.py`；入口前缀：`dataagent_governance.governance.cross_tenant:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.9.1 可共享经验筛选与脱敏 | `select_and_sanitize_shared_experience` | 租户经验候选、明确的跨租户用途授权、专有信息分类、共享政策及来源范围 | ShareableExperienceDraft；通用方法/模板/术语、脱敏检查、来源授权与剩余泄漏风险 | 原始数据、企业专有口径、可识别信息不得回流；脱敏成功不替代租户授权。 |
| DA12.9.2 领域包更新提案 | `propose_domain_package_update` | 可共享经验草案、领域包当前版本、冲突/适用性与回归报告、租户授权引用 | DomainPackageProposal；补丁、适用域、维护者审阅要求、来源限制与验证清单 | 只提交领域包提案；由维护者审阅后按发布政策生效，不自动跨租户安装或复用原始材料。 |

### DA12.10 证据链与审计 〔FDE〕

拟议文件：`src/dataagent_governance/governance/audit.py`；入口前缀：`dataagent_governance.governance.audit:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.10.1 证据到结果的全链追踪 | `trace_evidence_to_results` | 结果/动作引用、DA04.1 实际事件、输入版本、授权回执、后端输出与来源锚点 | AuditChainRef；调用→输入→授权→结果→依据的有向链、断链与可追踪粒度 | 审计只链接真实事实；缺参数/子条件记录须标缺口，证据链完整也不能推导动作获权。 |
| DA12.10.2 不可篡改与保留期 | `enforce_audit_retention` | 审计链/事件集合、保留/冻结/删除政策、存储后端能力、授权与时间条件 | RetentionReceipt；追加/校验/保留锁状态、到期安排、法律保留冲突、实际保证等级 | 不可篡改保证来自具备能力的后端与控制；本地哈希仅可验变更，不能冒充 WORM 或完整合规承诺。 |
| DA12.10.3 合规报告导出 | `export_compliance_report` | 审计范围/时间、AuditChainRef、报告模板、接收方/用途、访问与脱敏决策 | ComplianceExportRef；报告/证据清单、签名或校验信息、脱敏回执、缺口及导出事件 | 导出前复检权限、保留与脱敏；报告仅覆盖实际记录，不把审计导出当新授权。 |
| DA12.10.4 判定依据关联 | `link_decision_basis` | 判定结果、后端实际规则/字段/子条件依据、后端能力声明、输入/规则版本 | DecisionBasisLink；依据锚点、实际粒度、覆盖/缺失字段、来源引擎及原记录引用 | 只能关联后端真实记录；仅规则级则标规则级，禁止由审计器推断补造表达式或逐子条件 trace。 |
| DA12.10.5 请求者与执行身份双记录 | `record_requester_and_executor` | 调用/动作回执、请求者主体、Agent 执行主体与委托引用 | IdentityPairRecord；请求者、执行者、委托链、权限交集依据 | 共享凭据场景仍逐请求者记录；缺请求者身份时标注断链，不补造。 |

### DA12.11 爆炸半径评估 〔FDE〕

拟议文件：`src/dataagent_governance/governance/blast_radius.py`；入口前缀：`dataagent_governance.governance.blast_radius:`。

| 编号 / 名称 | 调用名 | 输入 | 输出 | 作用边界 |
|-|-|-|-|-|
| DA12.11.1 影响面分级 | `classify_blast_radius` | 动作草案、目标/作用域、ImpactReport、估计影响行/对象/用户、分级政策 | BlastRadiusAssessment；影响面等级、直接/间接范围、估计依据、上界与未知项 | 分级阈值由有权主体确认；未枚举范围不算零影响，风险等级本身不代替 DA16 审批。 |
| DA12.11.2 可逆性判定 | `assess_action_reversibility` | 动作契约、外部系统能力、已知副作用、回滚/补偿路径、时间与依赖条件 | ReversibilityAssessment；可逆/有条件/不可逆/未知、恢复步骤、窗口、残留影响 | 资产指针能回滚不代表消息/付款/外部修改可逆；验证恢复能力而非依据动作名猜测。 |
| DA12.11.3 分级授权阈值 | `draft_risk_authorization_thresholds` | 业务风险容忍度、影响面/可逆性分级、既有 DA16/平台政策、授权主体要求 | RiskThresholdPolicyDraft；分级阈值、所需授权档位、例外与生效/复审条件 | 只定义并经有权主体确认政策；实际委托/审批归 DA16，不能借设阈值自行授予权限。 |

## 6. 跨层责任与依赖

| 协作方 | 输入给评测/治理层 | 本层输出或消费方式 | 不应重复承担的职责 |
|-|-|-|-|
| DA01/DA02 接入与准备 | 版本化来源、数据画像、锚点、实际快照、源端能力 | DA11 质量检查复用画像；DA12 限定读取范围、登记版本政策与可重现条件 | 本层不另写解析器、清洗链或快照存储 |
| DA03 语义 | 已确认定义/适用范围、typed 语义依赖、物理映射 | DA11 按版本验证口径，DA12 评估变更并控制正式生效 | 正文及映射实际保存由 DA03；不能用调优/版本登记偷偷改业务定义 |
| DA04 轨迹与资产 | 真实事件、纠正、资产内容与实际保存回执 | DA12 做生命周期政策、链路关联和保留要求；DA11 消费实际执行依据 | 内容、记忆和轨迹事实保存复用 DA04；治理不复制一套经验库，不补造调用 |
| DA05 检索 | DA05.7 返回版本化依赖与使用关系，及实际召回结果 | 影响分析消费 typed edges；访问限制需在召回和输出两端生效 | 不以治理遍历代替相关性检索，也不只在最终展示才过滤敏感命中 |
| DA06/DA07 计划与执行 | 计划/动作契约、真实调用和幂等回执、dry-run/隔离能力 | DA11 通过执行端口跑回归/影子，DA12 提供约束/变更决策与补偿计划 | 不建第二套 SQL/程序/动作执行器；超时副作用先对账，禁止盲重试 |
| DA08–DA10 分析/预测/交付 | 方法、预测与仿真结果、交付物、资源记录 | DA11 按方法独立评测并验收业务交付；DA12 约束导出与资产使用 | 本层不替代业务分析产物生成 |
| DA14 观测 | 失败率、环境/数据/权限漂移、运行窗口 | DA11.6/.9 形成趋势与熔断，DA12.3 提出失效/更新建议 | 观测事实不自动改变正式标准；熔断恢复有独立验证条件 |
| DA15/DA16 动作契约与委托审批 | 动作范围/风险语义、真实委托/审批事实、有效授权政策 | DA12.1 检查数据访问与脱敏，DA12.11 评估风险；DA11 检查过程合规 | DA16 承担动作委托/审批；本层不新建身份或授权发行系统，不把证据当许可 |
| DA17/DA18 环境与交付 | 环境版本、配置、验收要求及责任主体 | 本层输出重现条件、业务验收报告、变更/发布记录；实际交付另留回执 | 不把报告导出等同环境部署或业务正式交付 |

版本生命周期治理依赖资产拥有模块的保存端口：先取得有效决策，再由拥有者校验 `expected_revision` 并保存/切换，返回实际回执。不同后端无法事务提交时记录分步状态、补偿或待对账，不能声称已跨系统原子完成。声明依赖、静态推断与实际观测依赖保留各自 `basis` 与覆盖，影响评估不保证发现全部下游。

数据访问决策用于约束资源使用；动作委托审批用于约束代表谁做什么。它们可消费同一平台身份与策略事实，但拥有不同对象和责任边界。治理按风险和既有授权决定直接执行、抽检、待澄清或待审阅，不将“治理”固化为每个步骤强制人工审批。

## 7. 典型调用切片

### 切片 A：令才规则或提示词修复后的正式验收

1. 业务主体用 DA11.5.1 确认并冻结结果/覆盖/UNKNOWN/人工/成本/时延判据；DA11.5.6 按业务实体与来源簇隔离 development、regression、unseen_acceptance，并记录曝光。
2. 修复方基于开发样本更换解析、规则、提示或程序；DA11.4.4 重跑历史报文，并按业务独立样本比较候选效果；仅在需要明确兼容既有表达式语义时，才启用 DA11.4.5 对同一输入比较子集与所指定权威后端。一般业务验收不要求接入旧引擎。后端只提供规则级依据时 DA12.10.4 明确规则级，不生成条件 trace。
3. DA11.8 同时报告业务正确性与真实权限/工具纪律。UNKNOWN、遗漏、人工接管、成本和时延进入 DA11.6.3 总体指标；参考结果不可比时保留缺口。
4. 受控验收执行器经 DA11.5.5 在未见集运行，开发侧仅见约定汇总。若必须暴露失败样本以修复，则把它转回归并补充新的未见集，正式阈值保持冻结版本。
5. 验收通过形成报告；DA11.9 对审核/发布等每个环节独立判断门槛。DA12.5 检查实际发布授权后才激活候选资产；外部动作还需 DA16/平台许可与 DA07 回执。

每一步都可替换实现；正式业务验收不要求与基线使用相同中间代码。回归、验收、发布与执行授权引用分别留存。

### 切片 B：交互纠正共享业务口径

用户指出某指标口径错误 → DA12.3.1/.2 归集反馈并保留事实/假设 → DA12.3.4 生成更新建议 → DA12.4.2 复用 DA05.7 查定义依赖和下游使用 → DA12.7 形成目标版本、影响范围、dry-run 与回退计划。DA11 检查候选正确性及必要回归，DA12.5.1 检查用户现有权限、当前版本和验证义务；满足条件即可由 DA03 保存新版本并由 DA12.5.2 控制范围/时间生效。

若用户只有本任务修订权限，则只更新本任务上下文，不推成企业共享口径；若版本已并发更新返回 `version_conflict`。需要正式业务主体确认的定义变更保留待审阅状态，但不无差别追加确认步骤。

### 切片 C：错误缓存沉积物回滚与外部副作用

监控或反馈发现缓存错误 → DA12.2.5 停用指定版本，并按命中记录定位受影响样本 → DA12.4 分析下游而不无差别作废全部历史 → DA11.4 隔离重放形成更正报告。旧缓存指针回滚不代表已经发送的通知、支付或源端写入已撤回：DA12.11.2 列可逆窗口和残留影响，DA12.5.3 输出补偿计划，DA16/平台授权后由 DA07 实际补偿并对账。

跨系统部分失败返回 `partial` 及未完成清单；超时写入不直接重试，先按幂等键查实际回执。审计链保存原动作、撤回/补偿与新结果，不能覆盖历史轨迹伪装“从未发生”。

### 切片 D：影子运行后逐环节扩大自主度

DA11.7.1 使用旁路输入与隔离动作端口，DA11.7.2 与人工处置逐条对齐，DA11.7.3 对数据、时序和口径差异做有证据的归因。DA11.8 验证结果与过程；DA11.9.1 可能建议“审核自动+抽检、发布人工确认”，授权主体按现有策略分别授予，审核档位不会传递给发布。

新模型或契约版本触发 DA11.9.2 重验；DA14 的真实失败率触发 DA11.9.3 既有熔断策略，返回控制回执及恢复条件。影子结果始终与生产生效结果分开。

### 切片 E：跨租户经验与审计导出

DA04 经验候选先经 DA12.1 与 DA12.9.1 校验租户明确授权、剔除原始数据/专有口径/可识别信息；DA12.9.2 向领域包维护者提出可共享补丁。维护者审阅与发布策略满足后才能生效，脱敏通过本身无共享许可。

审计方通过 DA12.10.1 关联真实事件，再由 DA12.10.2 按后端真实能力执行保留。导出前 DA12.1 重新检查接收方和用途，DA12.10.3 生成受控报告及导出事件；无法取得的参数/条件级依据、外部副本撤回能力或历史版本都在报告中显式列缺。

## 8. 目录、验证与保留选择

实现时优先保证：正式标准不被修复自动放宽；未见集访问和泄漏台账可核查；六类指标并报；版本绑定真实且缺口明确；权限拒绝和发布冲突不被掩盖；影子/回放无生产副作用；审计粒度不超出后端事实。

正式 schema、具体策略引擎、生产审计存储、统计置信方法、部署容量与实际发行规范在实现前收敛。

# 评测与治理层代码目录提案

推荐工作区 `packages/capabilities/dataagent-governance/`，Python 命名空间 `dataagent_governance.*`。共享引用与调用封套沿用 [数据层共享契约](01-data-layer.md)。共享契约在实现时提取为可独立依赖的契约包或版本化 schema，不以导入数据/应用模块内部业务代码来共享类型。

## 1. 拟议目录树

```text
packages/capabilities/dataagent-governance/
├── README.md
├── pyproject.toml
├── uv.lock
├── contracts/
│   ├── README.md                    # schema 导出规则
│   └── generated/                   # 从类型生成，非第二份手工权威源
├── src/dataagent_governance/
│   ├── contracts/
│   │   ├── common.py                # 引用共享 CallContext/CapabilityResult
│   │   ├── evaluation.py            # criteria、case、split、report、MetricBundle
│   │   ├── policies.py              # PolicyRef、AccessDecision、gate 与阈值
│   │   ├── changes.py               # request、decision、plan、impact、receipts
│   │   ├── lifecycle.py             # 版本状态、复现清单、回滚与补偿
│   │   └── audit.py                 # 证据链、后端实际粒度、保留与导出
│   ├── ports/
│   │   ├── profiles.py              # DA02 画像与约束统计
│   │   ├── repositories.py          # 版本解析、持久化和原子切换，复用资产拥有者
│   │   ├── sample_vault.py          # 分角色样本读取、隔离、暴露审计
│   │   ├── execution.py             # DA07 隔离运行、dry-run、回执与对账
│   │   ├── identity_policy.py       # 平台/源端身份鉴权与 DA16 授权审批事实
│   │   ├── dependencies.py          # DA05.7 typed 依赖与使用关系
│   │   ├── observation.py           # DA04 实际事件与 DA14 运行窗口
│   │   ├── evaluators.py            # 各类比较/打分/方法诊断与推断实现
│   │   └── audit_storage.py         # 保留锁、追加存储、完整性校验与受控导出
│   ├── evaluation/                  # DA11
│   │   ├── data_quality.py          # DA11.1 字段约束、重复/缺失、跨源对账
│   │   ├── computation.py           # DA11.2 执行表达、口径、粒度合并、对照验证
│   │   ├── methods.py               # DA11.3 统计、预测、仿真与方案适用性
│   │   ├── regression.py            # DA11.4 检索、问数、分析、规则库、引擎一致性
│   │   ├── criteria_samples.py      # DA11.5 正式判据与分角色评测集
│   │   ├── improvement.py           # DA11.6 趋势、贡献、覆盖与交付成本
│   │   ├── shadow.py                # DA11.7 隔离旁路、人工比对、差异归因
│   │   ├── dual_track.py            # DA11.8 结果正确性与真实过程合规
│   │   └── gates.py                 # DA11.9 分环节档位、变更回归、熔断
│   ├── governance/                  # DA12
│   │   ├── access.py                # DA12.1 访问检查、敏感识别、脱敏
│   │   ├── versions.py              # DA12.2 版本政策、决策沉积物与回滚
│   │   ├── feedback.py              # DA12.3 反馈、归因、失效与更新建议
│   │   ├── impact.py                # DA12.4 数据、语义、权限影响
│   │   ├── change_control.py        # DA12.5 写入冲突、生效、撤销/补偿
│   │   ├── reproduction.py          # DA12.6 实际版本绑定与历史可重现性
│   │   ├── change_plans.py          # DA12.7 可审阅变更计划、隔离差异预览
│   │   ├── tuning.py                # DA12.8 Preset 比较、灰度与回退
│   │   ├── cross_tenant.py          # DA12.9 获准通用经验与领域包提案
│   │   ├── audit.py                 # DA12.10 真实证据链、保留、导出、判定依据
│   │   └── blast_radius.py          # DA12.11 影响分级、可逆性、授权阈值草案
│   ├── adapters/
│   │   ├── assets/                  # 数据层版本仓储与内容端口绑定
│   │   ├── samples/
│   │   │   ├── local_split_vault.py # 本地样本角色与访问边界
│   │   │   └── remote_vault.py      # 远程独立验收执行器
│   │   ├── evaluators/
│   │   │   ├── deterministic.py    # 字段/数值/规则确定性比较
│   │   │   ├── retrieval.py        # 排序/召回指标
│   │   │   ├── statistical.py      # 回测、诊断与区间
│   │   │   ├── rubric_model.py     # 模型辅助评分，固定 rubric/模型/提示版本
│   │   │   └── engine_reference.py # 真实权威引擎对照，保留实际粒度
│   │   ├── policies/               # 平台、源端与 DA16 策略/事实适配
│   │   ├── execution/              # 隔离执行、dry-run、回执查询
│   │   ├── observation/            # 实际轨迹、运行窗口、计费/人工记录
│   │   └── audit/
│   │       ├── local_append_store.py # 本地追加与哈希校验，显式有限保证
│   │       └── retention_backend.py  # 具备保留锁等能力的实际后端
│   ├── registry/
│   │   ├── catalog.py              # 67 ID→入口、I/O 类型、依赖/副作用声明
│   │   └── loader.py               # 按需加载组和适配器
│   └── interfaces/
│       ├── python_api.py
│       ├── cli.py
│       ├── http.py
│       └── mcp.py
├── component-specs/
│   ├── evaluation.yaml             # 自拟组级描述，非平台正式 manifest
│   └── governance.yaml
├── presets/
│   ├── rule-library-acceptance.yaml
│   ├── staged-shadow-release.yaml
│   └── asset-change-review.yaml
├── examples/                       # 去标识小样例，不含独立验收金标
├── tests/
│   ├── contracts/                  # 同契约不同实现的共同语义
│   ├── evaluation/                 # 分母、UNKNOWN、不可比、证据不足
│   ├── samples/                    # 关联泄漏、暴露降级、验收金标隔离
│   ├── governance/                 # 权限/用途、版本冲突、范围和幂等
│   ├── audit/                      # 真实粒度、断链、保留保证和脱敏导出
│   └── scenarios/                  # 冻结标准+独立样本的端到端业务结果
└── fixtures/                       # 仅开发/回归 fixture，验收金标不入开发仓库
```

`__init__.py` 等常规文件省略。运行时原件、报告、样本、轨迹、策略副本和导出位于显式配置的受控 `data_root` 或外部后端，不写入源码仓库。独立验收集的金标与开发进程分域；单纯把两个文件夹命名为 train/test 不能提供隔离保证，本地可信边界不足时必须选外部受控执行器或明确其限制。

## 2. 端口和适配边界

| 端口 | 最小职责 | 不可隐含的能力 |
|-|-|-|
| `ProfilePort` | 按版本取 DA02 画像/约束统计，声明采样与覆盖 | 样本统计不等于全量质量证明 |
| `AssetRepositoryPort` | 解析精确版本、写草案、CAS 生效/停用、返回实际回执；由 DA03/04 等资产拥有者适配 | 未保存不能返版本成功；生命周期政策不等于实际内容已存在 |
| `SampleVaultPort` | 角色划分、关联去重、受控读取、曝光台账；验收器专有金标权限 | 修复者不能用验收金标调参；已暴露样本不能继续充作未见样本 |
| `ExecutionPort` | 提交隔离运行/dry-run、声明生产写入禁用、取消与回执对账 | 缺少隔离则拒绝影子副作用；没有 dry-run 就不能返回已试运行 |
| `IdentityPolicyPort` | 解析真实平台主体/源端权限/DA16 委托审批事实，检查用途/资源/动作及决策期限 | 不自己建用户库或发委托；访问允许不等于允许修改或发布 |
| `DependencyPort` | 消费 DA05.7 的 typed edges，保留 basis、版本和覆盖 | 未观测边不当作不存在，不假设遍历结果全量 |
| `ObservationPort` | 读取 DA04 实际事件、DA14 窗口、计费与人工量回执 | 不以模型推理或模拟步骤代替真实已发生事实 |
| `EvaluatorPort` | 方法专属比较/评分/置信区间，记录实现、rubric、模型版本及可比范围 | 模型评分仅辅助，不能自行改正式标准或将无参考案例判真 |
| `AuditStoragePort` | 追加、完整性校验、保留/法律冻结、受控读取与导出、能力等级声明 | 普通文件+哈希不具备 WORM；不宣称不可篡改超出真实后端保证 |

初版可用本地仓储适配器与 SQLite 保存非独立验收元数据；评价程序按需调用统计库或模型，避免把全部评测变成单一模型裁判。正式样本隔离、生产级保留锁和外部授权要求由部署选用满足要求的后端。不可用依赖返回 `dependency_unavailable` 或明确受限报告，不能假返回通过、已发布或已保留。

## 3. 一项能力如何落地

以 `DA11.4.4` 为例：`registry/catalog.py` 注册 `dataagent_governance.evaluation.regression:evaluate_rule_library_regression`，业务输入/输出类型由 `contracts/evaluation.py` 定义；组函数验证冻结判据和样本角色，经 `SampleVaultPort` 取获准回归样本，用 `ExecutionPort` 隔离运行候选/基线，`EvaluatorPort` 计算逐规则/业务分层差异，经 `ObservationPort` 汇总人工与资源记录，再通过资产端口保存实际报告。

报告注明真实运行的样本、依赖与后端版本、未执行范围和未知项。需要条件级依据时只消费后端真实明细，不能由报告器重建一份假 trace。规则库回归结果可供 DA12.8/DA11.9 消费，但不直接调用生产激活。

## 4. 依赖方向与发行粒度

```text
Python/CLI/HTTP/MCP + Registry
                 ↓
      evaluation / governance handlers
                 ↓
      共享契约 + 本层 Port 协议
                 ↑
  资产 / 样本 / 策略 / 执行 / 观测 / 审计 Adapters
```

应用层可消费本层验证/策略接口，本层可通过端口调用应用执行器；二者共同依赖共享契约，各自适配器完成注入，不互相导入应用 handler/runtime 内部模块。DA12.5 消费 DA11 报告或显式验证端口，DA11 读取已经发布的策略事实；避免门禁评估再次触发完整发布控制而循环调用。

`DAxx.y.z` 稳定 ID、Python operation、可替换实现、安装包、Agent 工具和 Preset 是不同粒度。一个工作区可先产出契约、评测、治理等构建产物，重型模型裁判、统计库、权威引擎适配器和生产审计存储作为可选依赖。无需为 73 个 ID 各建一个仓库、进程或发行包；可按独立依赖/维护/部署需要拆包，保留相同 ID 与业务语义。
