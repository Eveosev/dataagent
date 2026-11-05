# DA13｜数据建模与物化（扩展）：输入输出与代码划分 v0.1

定位：将已定义的业务语义落实为可维护的物理数据模型与物化数据。

**模块输入**：业务需求、语义与源结构版本、目标后端、转换约束、获准变更计划和历史区间。

**模块输出**：模型/数据契约草案、转换与依赖、物化/回填回执、校验报告和结果引用。

**模块边界**：该模块按需建设。生成复用 DA06/DA08.6，执行复用 DA07，验证复用 DA11；不在数据层另建计算引擎。

本文件与 [共享契约](06-shared-contracts.md) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/modeling/`。共 3 个能力组、7 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
| --- | --- | --- | --- | --- |
| DA13.1 目标模型设计 | 根据业务语义和来源结构设计目标表及其契约。 | 分析需求 | 维度/事实模型与数据契约 | `models.py` |
| DA13.2 转换构建 | 生成从来源到目标表的转换 SQL 或程序，并维护依赖顺序。 | 模型 | 转换逻辑与依赖 | `transformations.py` |
| DA13.3 物化与回填 | 执行转换并写入目标库，按区间补算历史数据。 | 转换 | 物化结果与校验报告 | `materialization.py` |

## 原子能力契约

### DA13.1 目标模型设计

边界：模型与 DA03 的实体、指标对应；设计结果是草案，确认后生效。

实现位置：`src/dataagent_data/modeling/models.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA13.1.1 主题/维度模型设计 | `design_analytical_model` | 业务需求、SemanticRef、源 SchemaRef、数据规模与查询模式 | ModelDraft；事实/维度/主题设计、粒度与映射依据 | 设计草案，不自行改变业务口径或创建物理表。 |
| DA13.1.2 数据契约定义：字段、约束、粒度、新鲜度承诺 | `define_data_contract` | ModelDraft、字段/约束/粒度/新鲜度要求、责任人 | DataContractDraft；校验条款、生效范围与来源 | 数据契约与 DA15 动作调用契约不同；正式承诺按策略确认。 |

### DA13.2 转换构建

边界：SQL 生成复用 DA06，程序生成复用 DA08.6；不另建一套编译能力。

实现位置：`src/dataagent_data/modeling/transformations.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA13.2.1 转换逻辑生成 | `generate_transformations` | 模型草案、来源映射、目标后端、转换要求 | TransformationDraft；SQL/程序引用、依赖与未支持项 | SQL 生成复用 DA06，通用程序生成复用 DA08.6。 |
| DA13.2.2 转换依赖维护 | `maintain_transform_dependencies` | TransformationDraft 列表、输入输出版本、expected_revision | 转换依赖图版本；拓扑关系、环路和缺口 | 依赖维护不执行调度；数据血缘观测仍归 DA02.7。 |

### DA13.3 物化与回填

边界：执行前须有 DA12.7 变更计划，写入走 DA07.4；校验复用 DA11.1 与 DA11.2。

实现位置：`src/dataagent_data/modeling/materialization.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA13.3.1 增量物化 | `materialize_increment` | 获准变更计划、转换版本、目标引用、已提交水位、幂等键 | MaterializationReceipt；写入分区/行数、结果引用、候选水位 | 经 DA07 执行写入；提交与校验成功后推进水位，未知副作用先对账。 |
| DA13.3.2 历史回填 | `backfill_history` | 获准变更计划、转换版本、历史区间、快照与目标引用、幂等键 | 回填作业引用；分区逐项状态、结果与部分失败 | 区间与源历史必须可用；不将重新取最新数据称作历史重现。 |
| DA13.3.3 物化结果校验 | `validate_materialization` | 物化回执、DataContractRef、对照数据/语义版本、验证范围 | ValidationReportRef；约束/对账结果、范围及未验证项 | 调用 DA11，执行返回成功不等于物化业务正确。 |
