# 执行应用层代码目录与适配端口 v0.1

本文件只提出源码布局，没有创建下述实现文件。推荐 Python 工作区 `packages/capabilities/dataagent-application/`；数据框架、统计库、沙盒和引擎均按任务可选装配。共享基础类型沿用 [数据层共享契约](../dataagent-data-layer-v0.1/06-shared-contracts.md)，未来提取到共同契约包或采用端口生成类型；本层 `contracts` 只持有应用层特有对象，不让治理层为了使用回执类型导入整个应用层实现。

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

常规 `__init__.py` 省略。39 个能力组文件及其每个函数入口都可由 [JSON 目录](atomic-capability-catalog.json) 反查。初期组内多个算法可共处一个文件，复杂后展开子包；不改变能力 ID。能力 ID、目录、Python 包、进程、发行包分别决定，不能以编号数推导部署单元数。

## 2. 适配端口与实现边界

| 端口 | 关键操作草案 | 必须保留的事实 |
| --- | --- | --- |
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
