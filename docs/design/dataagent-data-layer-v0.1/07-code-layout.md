# 代码目录与实现组织 v0.1

以下目录均为拟议结构，当前仅创建本设计文档。实现语言先选 Python：文件、表格和数据处理生态成熟，便于端侧及服务部署；调用契约保持 JSON 可序列化，允许其他语言实现适配器。Python 包划分、注册描述和文件名均为本草案约定，不代表 MintHub 正式包规范。

## 1. 推荐结构

在 `packages/capabilities/dataagent-data/` 下建立一个可独立演进的工作区。一级模块用目录隔离，二级能力组先用文件组织，三级能力用独立函数及请求/响应类型注册。复杂度增加后可以将某组文件展开为子包，不改变能力 ID。

```text
packages/capabilities/dataagent-data/       # 拟议工作区
├── README.md
├── pyproject.toml                         # Python 运行时与可选依赖组
├── uv.lock
├── contracts/                            # 跨进程契约源；若导出 schema 则从类型生成
│   ├── README.md
│   └── generated/                        # 派生 JSON Schema，不再手工维护一份
├── src/dataagent_data/
│   ├── __init__.py
│   ├── contracts/                        # 共享类型的实现权威源
│   │   ├── common.py                     # CallContext、Result、Issue、Continuation
│   │   ├── references.py                 # 来源、连接、版本、凭据代理引用
│   │   ├── data.py                       # 表、文档、批次、锚点、快照
│   │   ├── semantics.py                  # 定义、候选、映射、评估
│   │   ├── lineage.py                    # 不同含义的边类型
│   │   ├── memory.py                     # 轨迹、经验、程序资产、任务修订
│   │   └── modeling.py                   # 模型、转换及物化回执
│   ├── ports/                            # 行为协议，不绑定具体数据库或模型
│   │   ├── source.py                     # 连接、结构读取、有限批次读取
│   │   ├── credentials.py                # 密钥代理、轮换与撤销
│   │   ├── repositories.py               # 版本对象、内容、关系、事件的读写
│   │   ├── inference.py                  # 结构化模型调用，保留实现与来源
│   │   ├── execution.py                  # 消费执行层的作业、回执与结果协议
│   │   └── validation.py                 # 消费 DA11 验证服务
│   ├── ingestion/                        # DA01
│   │   ├── connections.py                # DA01.1
│   │   ├── schemas.py                    # DA01.2
│   │   ├── reads.py                      # DA01.3
│   │   ├── files.py                      # DA01.4
│   │   ├── ocr.py                        # DA01.5
│   │   ├── catalog.py                    # DA01.6
│   │   ├── changes.py                    # DA01.7
│   │   ├── resources.py                  # DA01.8
│   │   ├── capabilities.py               # DA01.9
│   │   └── credentials.py                # DA01.10
│   ├── preparation/                      # DA02
│   │   ├── regions.py                    # DA02.1
│   │   ├── structure.py                  # DA02.2
│   │   ├── reshape.py                    # DA02.3
│   │   ├── profiles.py                   # DA02.4
│   │   ├── joins.py                      # DA02.5
│   │   ├── cleaning.py                   # DA02.6
│   │   ├── lineage.py                    # DA02.7 数据处理血缘
│   │   ├── documents.py                  # DA02.8
│   │   ├── schema_changes.py             # DA02.9
│   │   ├── repairs.py                    # DA02.10
│   │   ├── snapshots.py                  # DA02.11
│   │   ├── extraction.py                 # DA02.12
│   │   ├── processes.py                  # DA02.13 FDE 扩展
│   │   ├── roles.py                      # DA02.14 FDE 扩展
│   │   └── baselines.py                  # DA02.15 FDE 扩展
│   ├── semantics/                        # DA03
│   │   ├── entities.py                   # DA03.1
│   │   ├── identity.py                   # DA03.2
│   │   ├── relationships.py              # DA03.3 业务对象关联
│   │   ├── metrics_rules.py              # DA03.4
│   │   ├── time_units.py                 # DA03.5
│   │   ├── mappings.py                   # DA03.6 存储与物理实现映射
│   │   ├── lineage.py                    # DA03.7 业务定义依赖
│   │   ├── history.py                    # DA03.8
│   │   ├── bootstrap.py                  # DA03.9
│   │   ├── conflicts.py                  # DA03.10
│   │   ├── actions.py                    # DA03.11
│   │   ├── authority.py                  # DA03.12
│   │   ├── evidence.py                   # DA03.13
│   │   ├── lifecycle.py                  # DA03.14
│   │   ├── decidability.py               # DA03.15
│   │   └── applicability.py              # DA03.16
│   ├── memory/                           # DA04
│   │   ├── traces.py                     # DA04.1
│   │   ├── distillation.py               # DA04.2
│   │   ├── memories.py                   # DA04.3
│   │   ├── artifacts.py                  # DA04.4
│   │   ├── contexts.py                   # DA04.5
│   │   ├── promotion.py                  # DA04.6
│   │   └── deliveries.py                 # DA04.7
│   ├── modeling/                         # DA13，可选依赖安装
│   │   ├── models.py                     # DA13.1
│   │   ├── transformations.py            # DA13.2
│   │   └── materialization.py            # DA13.3
│   ├── adapters/                         # 替换实现，避免业务能力直接依赖厂商 SDK
│   │   ├── sources/
│   │   │   ├── postgres.py
│   │   │   ├── mysql.py
│   │   │   ├── http_api.py
│   │   │   ├── mcp.py
│   │   │   └── filesystem.py
│   │   ├── parsers/
│   │   │   ├── excel.py
│   │   │   ├── delimited.py
│   │   │   ├── json_records.py
│   │   │   └── pdf.py
│   │   ├── ocr/                          # 本地与远程 OCR 实现
│   │   ├── storage/
│   │   │   ├── local_content.py
│   │   │   ├── sqlite_metadata.py
│   │   │   └── object_storage.py
│   │   ├── inference/                    # 模型提供方实现；Prompt 与结构化约束分开管理
│   │   └── services/                     # 验证、授权、执行等外部端口绑定
│   ├── registry/
│   │   ├── catalog.py                    # 能力 ID → handler、I/O 类型、实现、依赖
│   │   └── loader.py                     # 按需装配；不全量加载可选后端
│   └── interfaces/                       # 同一业务契约的不同传输入口
│       ├── python_api.py
│       ├── cli.py
│       ├── http.py
│       └── mcp.py
├── component-specs/                      # 拟议能力描述，可按二级组聚合
│   ├── ingestion.yaml
│   ├── preparation.yaml
│   ├── semantics.yaml
│   ├── memory.yaml
│   └── modeling.yaml
├── packaging/                            # 后续绑定实际发行平台的适配描述
├── presets/                              # 示例组合；不是唯一执行主链
│   ├── irregular-workbook.yaml
│   ├── enterprise-semantic-bootstrap.yaml
│   └── policy-document-preparation.yaml
├── examples/                             # 可运行示例及小型去标识数据
├── tests/
│   ├── contracts/                        # 同契约不同实现的共同行为验证
│   ├── ingestion/                        # 多表、分页、事件水位及凭据不泄露
│   ├── preparation/                      # 锚点、结构歧义、样本统计与数据保真
│   ├── semantics/                        # 定义冲突、时态、映射与 UNKNOWN
│   ├── memory/                           # 版本并发、范围隔离及来源追踪
│   ├── adapters/                         # 源端真实特性与声明一致
│   └── scenarios/                        # 独立样本上的端到端业务结果
└── fixtures/                             # 小型测试原件、预期锚点和对照结果
```

`__init__.py` 等常规文件在树中省略。`component-specs/` 为本项目自拟描述，不等于正式 Mint manifest。实际运行时数据放在工作区以外，由显式 `data_root` 配置：原文件/快照、元数据、语义/关系、轨迹与资产内容分别管理；企业部署可以替换为源端或集中式存储，不把用户数据提交到代码仓库。

## 2. 一项能力如何落到代码

以 `DA02.2.1` 为例：

| 组成 | 拟定位置 | 职责 |
| --- | --- | --- |
| 稳定 ID 和调用注册 | `registry/catalog.py` | `DA02.2.1 -> dataagent_data.preparation.structure:recover_headers` |
| 业务参数类型 | `preparation/structure.py` 中 `RecoverHeadersInput/Output` | 定义表块、策略、结果表头及歧义，不把整个模块写成万能字典 |
| 共享对象 | `contracts/data.py` | 复用 `TableRegion / TableRef / SourceAnchor` |
| 能力处理函数 | `preparation/structure.py` | 验证输入、选择已装配实现、规范返回与来源记录 |
| 算法实现 | 初期同文件私有实现；复杂后 `preparation/header_recovery/` | 规则法与模型法可替换，重型依赖按需加载 |
| 发行描述 | `component-specs/preparation.yaml` | 声明入口、契约版本、实现与依赖；实际包粒度另决定 |
| 验证 | `tests/preparation/` 与 `tests/contracts/` | 多行/重名表头、歧义不丢失、原值及锚点正确 |

能力组不强制一个文件永久容纳全部实现；原子能力不要求独立进程。对于 `DA01.4.2` 不规则 Excel 等组合能力，handler 可以显式调用表块检测、表头恢复等已注册原子能力。组合必须保留每步实现版本和结果引用，不复制一份底层算法。

完整的 **编号 → 调用名 → 源码文件 → 入口** 映射见 [atomic-capability-catalog.json](atomic-capability-catalog.json)。160 项编号均有明确入口，目录树可以直接反查。

## 3. 依赖方向

```text
传输入口 / Registry
        ↓
DA01 / DA02 / DA03 / DA04 / DA13 的能力函数
        ↓
共享契约 + Ports
        ↑
源端 / 解析器 / 模型 / 存储 / 外部服务 Adapters 实现 Ports
```

模块间可以通过显式调用端口协作，但不得形成相互导入的循环：DA02 消费 DA01 的数据契约；DA03 消费 DA01/02 结果；DA04 存储各模块的实际事件和资产引用；其他模块通过轨迹端口发事件，不导入 DA04 内部存储。DA01.4.2 组合入口通过注入的处理端口使用 DA02 的结构恢复；DA02 的数据读取也通过 source 端口，避免 DA01/DA02 在源码层互相导入。

DA13 在调用边界消费执行和验证端口；共享类型放 `contracts`，不得靠导入执行应用层内部实现获得类型。治理负责正式发布与访问决策，数据层只检查决策并按允许范围持久化；不在每个模块另写一套审批系统。

## 4. 存储端口和最小后端

| 端口 | 首版建议 | 后续替换边界 |
| --- | --- | --- |
| ContentStore | 本地受控文件存储、内容 digest、原子写入 | 对象存储或企业文件服务；稳定引用和内容校验不变 |
| VersionedRepository | SQLite 元数据与显式修订，乐观并发检查 | PostgreSQL 或企业服务；保持版本读写含义 |
| RelationRepository | 关系表记录 typed edges、版本、来源与覆盖 | 可替换图数据库；不强制依赖图库 |
| TraceRepository | 追加事件、event_id 去重、可分页读取 | 外部轨迹服务；事实事件和修改记录不可静默改写 |
| SourcePort | 数据库/API/MCP/文件系统适配器 | 保持源端特性声明，不做全源通用 SQL 幻觉 |
| InferencePort | 结构化输入、输出验证、模型/提示词版本与来源记录 | 替换模型或规则算法时复用能力契约和验收样本 |
| ValidationPort / ExecutionPort | 调用方注入 DA11/DA07 的实现 | 尚未接入时返回依赖不可用，不能假返回通过或已执行 |

不先引入独立的向量库、图库或事件总线作为全部能力的硬依赖。按 ID/版本的读取由 repository 完成，向量/关键词检索索引由 DA05 消费资产变更后按需建立。SQLite 在本地适用并不代表所有企业并发、保留或审计要求已满足，部署时按实际约束替换端口实现。

## 5. 编号、工具和包粒度

`DAxx.y.z` 是稳定能力标识；函数名是当前 API 草案；适配实现是同能力的不同做法；发行包是带依赖的一组可安装内容；Agent 工具是面向任务的调用入口。这五种粒度分别管理。

首版工作区可以产生共享契约与运行支撑、接入、准备、语义、记忆、建模六类构建产物，但不预先规定每项原子能力独立发包。包内注册细分能力供 Agent 按需发现；面向某任务，只暴露候选或 Preset 需要的入口，避免将 160 项全部放进每轮工具上下文。

原子能力可按独立依赖和实际复用需求拆成包；例如 OCR 与大型模型后端作为可选依赖，不让只读 CSV 的用户安装整个推理运行时。任何拆包都需要保留能力 ID、契约版本和可验证的行为范围。

## 6. 备选结构与本版取舍

| 方案 | 优点 | 代价 | 本版选择 |
| --- | --- | --- | --- |
| 每项原子一个独立项目/包 | 替换与分发直接 | 160 项初期会产生大量构建、版本和重复契约维护 | 仅在已有独立部署或合作方交付需求时拆 |
| 单个万能数据服务 | 起步文件少 | 边界、依赖和替换点不清楚，难做组合 | 保持模块和原子入口清晰 |
| 一个工作区，按模块组织，可选适配器，可逐步拆包 | 共享类型与测试，同时保留替换和发布空间 | 需要约束依赖方向和注册规范 | 推荐作为 v0.1 |
