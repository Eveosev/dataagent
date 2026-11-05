---
version: v0.1.1
date: 2026-11-05
status: 待评审
kernel: agent-kernel@f0fa521
basis: 03-governance-layer.md；05-contracts.md；06-data-layer-build-plan.md
---

# 评测与治理层能力建设方案

## 1. 范围

| 项 | 内容 |
|-|-|
| 模块 | DA11 评测与验证、DA12 治理与资产维护 |
| 原子 | 非 FDE 54 项：S0 6 项（阶段 1）；按需 48 项（阶段 2） |
| 不含 | FDE 能力组 DA11.7 影子运行、DA11.8 双轨评测、DA11.9 上线门禁、DA12.9 跨租户经验、DA12.10 证据链与审计、DA12.11 爆炸半径（19 项） |
| 包 | `packages/capabilities/dataagent-governance/`，Mint `kind = "bundle"` |
| 运行路径与 LLM | 同 [06](06-data-layer-build-plan.md) §1：Python 核心 + MCP 入口；LLM 在 Agent 侧，按两段式调用 |

S0 原子：

| 族 | 原子 | operation |
|-|-|-|
| 骨干 | DA11.5.1 业务验收判据定义 | `draft_acceptance_criteria` |
| 骨干 | DA11.5.5 端到端业务验收 | `evaluate_business_acceptance` |
| 骨干 | DA11.5.6 验收样本隔离 | `isolate_acceptance_samples` |
| 骨干 | DA12.1.1 访问范围检查 | `check_access_scope` |
| 骨干 | DA12.1.4 模型上下文可见性与外发控制 | `check_model_context_egress` |
| 计算族 | DA11.2.3 结果粒度与合并检查 | `check_result_grain_and_merge` |

## 2. 前置条件

与执行应用层（[07](07-application-layer-build-plan.md) §2）共用：

| 项 | 内容 | 状态 |
|-|-|-|
| 共享运行时 | `packages/capabilities/dataagent-runtime/`：`invoke`、注册表、存储端口与适配器、`InferencePort`、MCP/CLI 入口骨架；本层另向其中加入访问复检与外发检查（§4.3） | 待做 |
| 共享 `data_root` | 与数据层、应用层共用；本层另有样本库子目录（§5.2） | 随共享运行时 |
| P2 | 采用 C：经内核时以 guard 为准，DA12.1 为策略源；无内核路径与缓存命中、导出由 DA12.1 判定并由运行时复检 | 待定案；阻塞 DA12.1 |
| 契约字段 | `ExecutableSpec` 迁入 core（07 §4.2），供 DA11.2.3 消费 | 阶段 1 开工前 |

## 3. 包结构

```text
dataagent-governance/
  pyproject.toml  uv.lock  mint.toml  .mcp.json  README.md  packaging/source-ref.toml
  skills/dataagent-acceptance/SKILL.md     # 判据起草、确认、样本冻结、验收
  skills/dataagent-access/SKILL.md         # 访问判定与外发判定的调用时机
  src/dataagent_governance/
    contracts/       # 本层特有类型：AcceptanceCriteriaDraft、EvaluationCaseDraft、GrainMergeReport、SensitivityReport、MaskedArtifactRef
    evaluation/      # DA11
    governance/      # DA12
    policy/          # 策略文档模型与求值器
    ports/           # sample_vault、policy_store、execution、dependencies、observation、evaluators
    adapters/        # local_split_vault、local_policy、mcp_execution、deterministic_evaluators
    interfaces/      # mcp_server.py、cli.py（基于 dataagent-runtime）
  tests/{contracts,evaluation,samples,governance,interfaces,scenarios}/
  fixtures/          # 仅开发与回归样本；验收金标不入仓库
```

- 组文件与 operation 以[总 Catalog](catalog/atomic-capability-catalog.json) 为准；注册表启动时校验。
- 依赖：`dataagent-contracts`、`dataagent-runtime`；不导入 `dataagent_data`、`dataagent_application`。执行其他层能力经 MCP 客户端适配器（阶段 2，DA11.4）。

## 4. 调用约定与跨层

### 4.1 调用

- `invoke(operation, input, CallContext) -> CapabilityResult[T]`；MCP 工具名 = operation；注解按操作显式声明。
- 业务结论与运行状态分开：`deny`、验收 `fail` 都是 `status=ok` 的业务结论；策略不可取得时 `indeterminate`，按拒绝处理。
- 两段式推理：DA11.5.1。工具提供交付目标、现有判据版本、样本概况；Agent 提交判据草案；工具校验阈值、证据要求、`unknown_policy` 完整后保存为 `draft`。

### 4.2 产出的 core 类型

| 类型 | 原子 | 消费方 |
|-|-|-|
| `AccessDecision` | DA12.1.1 | 全部读取；运行时复检 |
| `EgressDecision` | DA12.1.4 | `InferencePort`；全部两段式原子 |
| `CriteriaRef` | DA11.5.1 | DA11.5.5 |
| `EvaluationSetRef` | DA11.5.6 | DA11.5.5 |
| `AcceptanceReport`、`CaseResult`、`MetricBundle` | DA11.5.5 | DA10.3 报告；S1 的 DA18.7 |

字段以 05 §3.3.6、§3.3.7 为准；`validate_acceptance_report` 已在契约包中，DA11.5.5 输出前必须通过。

### 4.3 运行时钩子（加入 `dataagent-runtime`，三层共用）

| 钩子 | 规则 | 模式 |
|-|-|-|
| 访问复检 | `invoke` 读取输入资源前解析 `authorization_ref` → `AccessDecision`：`allow`、未过期、`resource_ref` 覆盖本次输入、用途一致；否则返回 `failed`，code `da12.access_denied` | `enforcement = off / warn / enforce`；开发默认 `warn`，S0 验收以 `enforce` 运行 |
| 外发检查 | `InferencePort` 生成 `inference_request` 前，要求覆盖其中全部内容的 `EgressDecision`：`allow` 原样附带；`allow_masked` 只附 `masking_ref` 指向的脱敏内容；`deny` 或缺失时不附内容，返回 `needs_input`，code `da12.egress_required` | 同上 |
| 内核路径 | 经内核调用（`kernel_session_id` 存在且宿主声明 guard 生效）时访问复检只校验决策存在，以 guard 结论为准 | — |

数据层现状：只校验 `authorization_ref` 非空，`inference_request` 未经外发检查。钩子接入后数据层门禁重跑。

## 5. S0 实现

### 5.1 访问与外发（DA12.1.1、DA12.1.4）

| 项 | 规则 |
|-|-|
| 策略 | 本地策略文档（JSON），存于 VersionedRepository，`PolicyRef` 带版本；规则按主体、资源（`VersionedRef` 前缀或资产类型）、动作（S0 为 `read`）、用途匹配；显式 `deny` 优先；无匹配为 `indeterminate` |
| 主体 | 取自 `CallContext` 的主体与请求者；不建身份系统；S0 不做请求者 ∩ 执行主体（S1 起） |
| 访问输出 | `AccessDecision`：字段与行约束、脱敏义务、`valid_until`、`reasons`；保存后其 `decision_id` 作为后续调用的 `authorization_ref` |
| 外发输入 | 内容引用、`destination`（`model_ref`、`deployment = local / private_cloud / vendor_api`、`terms_ref`）、依据的 `AccessDecision` |
| 外发规则 | 策略按部署位置与敏感级别给出 `allow / allow_masked / deny`；`vendor_api` 且内容含敏感字段时至少 `allow_masked` |
| 敏感识别 | S0 内置确定性识别：身份证号、手机号、邮箱、银行卡号、按策略声明的字段名；输出 `SensitivityReport`（本层类型） |
| 脱敏 | 按义务替换或截断，脱敏产物内容寻址保存为 `MaskedArtifactRef`，`EgressDecision.masking_ref` 指向它 |
| 策略后端 | 端口预留 Cedar 等策略引擎适配器；S0 只实现本地求值器 |

### 5.2 判据与样本（DA11.5.1、DA11.5.6）

| 项 | 规则 |
|-|-|
| 判据状态 | DA11.5.1 只产出 `draft`；转 `active` 需 `confirmation_ref`（有权主体的确认记录），由单独确认调用写入新 revision；修复流程不能改写已 `active` 的判据 |
| 划分 | 按分组键（实体、时间段、来源簇）整组划入 `development / regression / unseen_acceptance`；内容指纹去重，近重复跨组时告警 |
| 冻结 | 冻结后 `EvaluationSetRef.revision` 不可变；新增样本生成新 revision |
| 样本库 | `data_root/vault/`：输入与预期分开存放；预期（金标）只经 DA11.5.5 读取；其他操作或 CLI 读取金标时写入暴露台账，该样本降为 `regression` |
| 本地限制 | 本地样本库是约定隔离，不是安全边界；报告 `limits` 写明。需要强隔离时通过 `SampleVaultPort` 接远程验收执行器（阶段 2） |

### 5.3 验收（DA11.5.5）

- 输入：`active` 判据、冻结的评测集、被验收交付（`Assessment` 或 `ComputedResult` 集合）、依赖版本。
- 只取 `unseen_acceptance` 样本；逐样本按判据比较：
  - 判定族：逐记录逐规则比较判定值；`unknown` 按 `unknown_policy` 计分；依据须能定位到条款与字段，否则该样本 `fail`，原因 `evidence_missing`；
  - 计算族：数值按判据容差比较；口径、粒度、过滤与预期不一致判 `fail`；
  - 失败、超时、预算耗尽的样本计入分母。
- 输出 `AcceptanceReport`：逐样本 `CaseResult`、`MetricBundle` 六类指标、分层差异（`strata`）、`coverage_scope`、`limits`。
- 比较器为确定性实现；模型辅助评分不进入 S0。

### 5.4 粒度与合并（DA11.2.3）

- 输入：`ExecutableSpec`（SQL 或计划）、输入与输出 `TableRef`、声明粒度、`ComputedResult`。
- 检查：
  - 声明粒度键在输出中是否唯一；
  - Join 键在两侧的基数，一对多或多对多导致的行数膨胀；
  - 聚合前后度量总和是否守恒（可计算时）；
  - 分页或截断回执是否完整。
- 实现：DuckDB 读取 `TableRef` 计算；SQL 的 Join 与分组结构由 sqlglot 解析。
- 输出 `GrainMergeReport`；源端无总量或一致快照时对应项记 `unknown`，不以行数接近判定正确。

## 6. 阶段 2：按需能力

两个流并行；流内按依赖排序。

| 流 | 能力组 | 实现要点 | 依赖 |
|-|-|-|-|
| 评测 | DA11.1 数据质量（3） | 复用 DA02 画像；字段约束、重复缺失、跨源对账 | 数据层 `ProfileRef` |
| 评测 | DA11.2.1–2.2、2.4–2.5（4） | 表达式检查、口径检查、结果对照、语义陷阱反例 | `ExecutableSpec`、`MetricDefinition` |
| 评测 | DA11.5.2–5.4、5.7（4） | 纠正转样本（消费 `CorrectionRef`）、边界与反例、接入基线、多角色越权用例 | DA11.5.7 需 DA12.1 |
| 评测 | DA11.4 回归（5） | `ExecutionPort` 经 MCP 客户端拉起被测 bundle，候选与基线在同一冻结样本上运行；DA11.4.5 消费 `EngineBinding` | 应用层 DA07.10 |
| 评测 | DA11.3 方法效果（4） | 统计前提检查、预测回测、仿真校准、方案可行性 | 应用层 DA08、DA09 |
| 评测 | DA11.6 持续改进（4） | 读取轨迹与人工、成本记录，按租户与任务类型统计；样本不足时说明 | 数据层 DA04 |
| 治理 | DA12.1.2–1.3（2） | 敏感识别与脱敏独立成原子（S0 中作为内部函数） | — |
| 治理 | DA12.2 资产版本（6） | 生命周期政策；实际保存与切换由资产拥有者端口按 `expected_revision` 完成，返回实际回执 | 共享运行时版本库 |
| 治理 | DA12.6 重现条件（2） | 汇总数据、语义、程序、引擎、模型版本；缺项时标注可重现级别 | `EngineBinding` |
| 治理 | DA12.3 反馈与更新建议（4） | 归集纠正与错误，产出更新提案，不直接改共享资产 | 数据层 DA04 |
| 治理 | DA12.4 变更影响（3） | 消费 DA05.7 依赖边，保留 `basis` 与覆盖；未观测边不视为不存在 | 应用层 DA05.7；core `LineageEdge` 字段 |
| 治理 | DA12.5 交互变更控制（3） | 版本冲突与授权检查后直接生效、待澄清或待审阅；源系统写入与共享资产发布分别记录 | DA12.1、DA12.2 |
| 治理 | DA12.7 变更计划（2） | 计划与试运行差异，无副作用 | DA12.4 |
| 治理 | DA12.8 配置调优（2） | DA11.4 回归通过后才生效，可回退 | DA11.4 |

## 7. 第三方依赖

| 用途 | 依赖 | 许可 |
|-|-|-|
| 粒度检查与质量统计 | duckdb | MIT |
| SQL 结构解析 | sqlglot | MIT |
| 方法评估（阶段 2） | scipy、statsmodels | BSD-3-Clause |
| 策略引擎（可选） | cedarpy | Apache-2.0 |

## 8. Mint 打包与 S0 组合

| 项 | 内容 |
|-|-|
| kind | `bundle`，名称 `dataagent/governance-layer` |
| `.mcp.json` | `uv run --frozen --project $PKG python -m dataagent_governance.interfaces.mcp_server` |
| `[capabilities]` | `exec = ["uv"]`、`fs.read = ["*"]`、`fs.write = [".dataagent/**"]`；无网络 |
| Skills | `dataagent-acceptance`、`dataagent-access` |
| S0 Preset | `dataagent-s0`（`kind = "preset"`）：`[dependencies]` 列数据层、应用层、本层三个 bundle；附判定族、计算族两个端到端 Skill，覆盖访问判定 → 接入 → 抽取或规整 → 规则或指标 → 执行 → 验收 → 报告 |
| 端到端测试 | `packages/capabilities/dataagent-scenarios/`（仅测试）：依赖三个包，按 Skill 顺序经 MCP 调用，以 `enforcement = enforce` 运行 |

## 9. 分步实施

| 步 | 内容 | 产出 | 可并行 |
|-|-|-|-|
| 0 | 共享运行时（与 07 步 0 共同完成）；P2 定案 | `dataagent-runtime` | — |
| 1 | 本层特有类型；包骨架与注册表；策略文档模型 | 空服务 | — |
| 2 | DA12.1.1、DA12.1.4；运行时访问复检与外发检查钩子（`warn`）；数据层门禁重跑 | 访问与外发判定 | 与步 3 并行 |
| 3 | DA11.5.1、DA11.5.6；样本库与暴露台账 | 判据与评测集 | 与步 2 并行 |
| 4 | DA11.5.5、DA11.2.3 | 验收报告、粒度报告 | 步 3 完成；DA11.2.3 需应用层 `ExecutableSpec` |
| 5 | bundle、Skills、`dataagent-s0` Preset、`dataagent-scenarios`；切换 `enforce` | S0 端到端 | 应用层步 5 完成后 |
| 6 | 阶段 2 评测流与治理流 | 按需能力 | 两流并行 |
| 7 | 文档回写：05 §3.3.6–3.3.7 字段校准；03 字段校准 | 文档一致 | — |

## 10. 验证

1. 单元：每个原子正例与反例；注册表与 Catalog 一致；注解与存储层观测一致。
2. 访问与外发：
   - 无匹配规则得 `indeterminate`，读取被拒；过期决策、资源不覆盖、用途不符均被拒；
   - `vendor_api` 加敏感字段得 `allow_masked`，`inference_request` 只含脱敏内容；`deny` 时不含内容；
   - `enforce` 模式下数据层 32 个原子全部经过复检。
3. 判据与样本：
   - `draft` 判据用于验收被拒；无 `confirmation_ref` 不能转 `active`；
   - 同一分组键的样本不跨角色；读取金标后样本降为 `regression`，台账有记录；
   - 冻结评测集不可修改。
4. 验收：失败、超时样本计入分母；`unknown` 按 `unknown_policy` 计分；缺依据样本判 `fail`；报告通过 `validate_acceptance_report`。
5. 粒度：一对多 Join 膨胀、粒度键重复、分页缺口各有反例。
6. S0 端到端：判定族、计算族各一个中性应用样本，在未见验收样本上产出 `AcceptanceReport`，六类指标齐全，报告列出未覆盖范围与不可判定项。

## 11. 风险

| 风险 | 处理 |
|-|-|
| `enforce` 使既有数据层调用失败 | 先 `warn` 运行并统计未通过调用；测试夹具补齐 `AccessDecision` 后切换 |
| 本地样本库隔离不足 | 报告 `limits` 写明；正式验收可接远程验收执行器 |
| 本地策略求值器表达力不足 | 规则不能表达时返回 `indeterminate`（拒绝）；按需接 Cedar 适配器 |
| 内核 guard 生效的判断依赖宿主声明 | 无声明时按无内核路径处理，运行时完整复检 |
| DA12.4 依赖未建的 DA05.7 与 `LineageEdge` 字段 | 治理流中排在最后，或先用符合契约的夹具开发 |

## 12. 修订记录

| 版本 | 日期 | 内容 |
|-|-|-|
| v0.1 | 2026-11-04 | 初稿 |
| v0.1.1 | 2026-11-05 | Reviewer r24 阻断项修复：B1 资产-内容闭包绑定（`data_ref` 必须等于资产 revision/digest，内容寻址资产不可重绑）；B2 敏感识别覆盖数值单元格与 JSON 结构化键，enforce 下应用层推理内容无 EgressDecision 先脱敏；B3 金标暴露改内容寻址索引，跨集重建不可洗白，可用未见样本为零时报告降级并在 `cases_ref`/`limits` 声明；B4 比较器确定性（unit 不匹配、非有限值、金标必达指标未交付、依据不可解析均判 fail）；B5 判定词表对齐 core `Verdict`（pass/fail/unknown），旧 satisfied/violated 作别名映射；B6 DA11.2.3 改共享表编解码（SQL 引用 field_id，未知 payload_version 拒绝）；B7 宿主权威不可被调用方覆盖（`_meta` 上下文优先、host subject/purpose 盖过 wire 身份）；B8 无等值 Join 保守判 unknown；B9 六类指标缺测写 `missing_records` 不写实测零、`source-ref.toml` 增加可重建源码归档与制品 digest；两族真实三 bundle MCP→AcceptanceReport 链路落 `dataagent-scenarios` |

## 13. 实施与评审记录

评审与修复记录在 `08-governance-layer-build/`。范围含 `dataagent-runtime`（§2）与 `dataagent-s0`、`dataagent-scenarios`（§8）。

| 文件 | 轮次 | 日期 | 内容 | 测试（governance / runtime / scenarios） |
|-|-|-|-|-|
| [r41-review.md](08-governance-layer-build/r41-review.md) | 41 评审 | 2026-11-05 | 跨包共性问题 X1–X5；治理层 S0 6 项完成度、方案三项与可行性评审落实、catalog-snapshot 一致性、新缺陷 G1–G10；runtime R1–R6；S0 preset；场景覆盖与 S1–S6；复现脚本 [r41-repro/](08-governance-layer-build/r41-repro/) | 117 / 75 / 12 |
