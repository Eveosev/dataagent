# 持续运行与 FDE 交付层代码目录提案 v0.1

本文件仅定义拟议代码归属，**未创建以下工作区或实现**。Python 命名空间为 `dataagent_operations.*`，业务逻辑只依赖共享类型与注入端口；跨层通过契约和端口协作，不导入数据、执行、治理层内部 runtime。基础对象复用[数据层共享契约](../dataagent-data-layer-v0.1/06-shared-contracts.md)，跨层集成在[总体约定](../dataagent-design-v0.1/cross-layer-contracts.md)收敛。

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

原子 ID、逻辑调用名、源文件和完整 `module:function` 入口以 [atomic-capability-catalog.json](atomic-capability-catalog.json)逐项对应。29 个组文件分别容纳显式 `OperationInput/Output` 类型和 handler；复杂实现可展开子包，ID 保持稳定。包级导入只暴露公开类型和注册入口，不借助万能字典掩盖逐项 I/O。

## 2. 端口调用与权威状态

| 设计端口 | 消费者与交换对象 | 实现/权威边界 |
| --- | --- | --- |
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

先完成可检查的 I/O 类型、真实回执与版本解析，再按 [README 场景切片](README.md#5-两个业务场景与建设切片)形成可运行闭环。实现验证优先覆盖“证据够但无授权”“免审政策有效无需额外签字”“任务固定版本不随环境默认变化”“未知副作用不重放”“只对受影响结果重验”“方法替换后端到端效果仍验收”这些会改变业务结果的边界。
