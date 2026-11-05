<title>DataAgent 数据层：模块与原子能力接口设计 v0.1</title>

本篇整合本地 v0.1 分层设计的模块接口、共享契约、代码目录及组合示例。能力编号基于主规划 revision 1022；本文为设计稿，尚未创建运行时代码。

[返回 Pluggable DataAgent 总规划与分层索引](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)

# DataAgent 数据层设计草案 v0.1

目标：建设可独立调用、验证与替换的数据能力，供 Agent 在业务探索中动态组合，并沉淀为 Skill / Preset / Bundle。令才场景按制度提取、单据准备、规则审核与交付的端到端业务效果验收；方法、程序和中间流程允许不同。数据层为该过程提供原始数据、结构、业务语义、真实轨迹及可复用资产。

本版依据 2026-11-02 更新后的飞书 revision 1022，保留原编号，拟定 **4 个核心模块 + 1 个扩展模块、51 个能力组、160 项原子能力**的输入输出、边界及代码归属。所有接口和目录均为设计提案；当前交付是本地文档与可检查的能力目录，尚未创建运行时代码。这里不做 Mint/iface 实现兼容结论。

其他层级与跨层交接见 [DataAgent 分层设计总导航](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)。

## 1. 模块范围与总体输入输出

| 范围 | 模块 | 模块输入 | 模块输出 | 能力组 / 原子能力 |
|-|-|-|-|-|
| 核心 | [DA01 数据接入](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) | 连接配置、凭据引用、原文件、资源地址、读取范围 | 连接/资源引用、原始内容、结构、数据批次及接入状态 | 10 / 31 |
| 核心 | [DA02 数据准备与探查](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) | 原始表/文档/记录、转换规则、画像预算、实际执行记录 | 规整数据、结构与关系候选、文档单元、数据血缘、快照和现状基线 | 15 / 48 |
| 核心 | [DA03 业务语义与关系](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) | 业务材料、探查结果、已有定义、作用域和可用条件 | 实体/指标/规则草案、版本化语义、物理映射、定义依赖和未决问题 | 16 / 50 |
| 核心 | [DA04 任务轨迹与记忆](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) | 实际任务事件、程序与结果引用、纠正、验证报告、获准修订 | 轨迹、任务上下文版本、经验候选、程序/模板/组合资产及适用条件 | 7 / 24 |
| 按需扩展 | [DA13 数据建模与物化](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) | 语义与结构版本、目标模型要求、获准变更计划 | 模型/契约草案、转换依赖、物化结果及验证报告 | 3 / 7 |

各模块文档先给出能力组的作用与输入输出，再逐项定义原子能力的输入、输出、作用边界、调用名和源码文件。完整映射亦保存为 [atomic-capability-catalog.json](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)。

DA05 召回检索、DA06 计算计划、DA07 执行、DA08/09 分析预测等属于执行应用层。它们消费数据层资产；DA11/12 提供评测、权限与版本治理。DA15–18 的动作契约、授权、业务环境和交付能力按需协作。本版仅定义与这些模块的调用边界，不把它们整体并入数据层。

数据层目录保留现有 DA01–DA04 中的 FDE 扩展项，例如资源探测、流程勘查、权限语义、交付物记忆。这些是环境事实和语义资产的建设能力，可选启用；不意味着每次文件分析都必须完整部署。

## 2. 共用契约与实现组织

- [共享输入输出契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)：调用上下文、返回状态、引用/版本、表与文档、语义候选、血缘、记忆和任务修订。
- [代码目录与实现组织](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)：拟议 Python 工作区、各能力组文件、端口与后端适配器、存储和发布粒度。
- [组合示例与建设切片](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)：不规则 Excel、企业语义冷启动、令才准备等输入输出如何串接，失败后如何动态调整。

统一逻辑调用方式：`invoke(operation, input, CallContext) -> CapabilityResult<T>`。各原子能力表只写业务参数，共用的身份、作用域、请求标识、任务引用、预算和并发检查参数集中定义。大内容通过受控资源引用传递，少量结构可内联；输出明确草案、事实、已验证记录、缺口及分页范围，避免只约定“输入数据、输出结果”。

## 3. 关键边界

| 容易重叠的对象 | 本版处理 |
|-|-|
| 原始内容与规整数据 | DA01 保存并读取来源结构；DA02 产生新结构及来源映射。不规则 Excel 是组合入口，底层表块/表头能力维护一套 |
| 数据画像与业务语义 | 画像、类型和 Join 探查都是候选；业务定义由 DA03 表达并按对应策略生效 |
| 数据血缘与业务语义血缘 | DA02.7 记录表列变换；DA03.7 记录定义依赖；DA03.6 连接语义与物理实现。实体关联与产物来源另用不同边类型 |
| 原始轨迹与经验 | DA04.1 记录真实事件；DA04.2 提炼候选；DA04.6 调用验证并控制作用域晋升；检索仍归 DA05 |
| 资产修订与任务修订 | 资产保存产生版本引用，通用版本政策归 DA12；DA04.5 维护本次任务选用的版本，环境默认配置归 DA17 |
| 模型推断与正式定义 | 生成/推断先输出草案或候选；保存与正式发布分开，不能以模型置信度代替业务验收 |
| 数据层操作与 SQL/程序执行 | 数据层可发读取或转换请求；通用 SQL/代码执行复用 DA07；DA13 不另建计算引擎 |
| 元数据读取与相关性召回 | 按 ID/版本解析是存储和来源端口基础操作；按用户问题找表、值、语义或经验由 DA05 负责 |

## 4. 目录与包粒度建议

推荐在 `packages/capabilities/dataagent-data/` 建一个工作区：`contracts` 定义共享对象，`ingestion / preparation / semantics / memory / modeling` 实现能力，`ports` 声明后端依赖，`adapters` 提供具体来源、解析器、模型与存储实现，`registry` 按需发现和装配能力。

同一原子能力的多个算法或后端沿用相同能力 ID。源码按模块组织，发布可以按依赖拆包；不要求“一个编号一个仓库/进程/发行包”。适配实现替换后仍须满足接口含义和业务验收要求。正式 MintHub 包描述与安装机制在后续兼容工作中确认。

## 5. 本版细化与保留项

本版不新增能力编号。对现有目录的接口含义作以下细化，后续整体讨论时一并考虑：

- `DA03.1.3` 负责状态词表，`DA03.14` 复用该词表定义生命周期，避免重复维护状态集合。
- `DA03.14.3` 先定义业务状态与执行观测的关联，不预先依赖某个内核状态枚举；实际平台映射由适配工作处理。
- `DA03.12.1` 描述角色与档位权限关系，`DA15.1` 分类动作入口，两者共享档位词表。
- `DA04.5.3` 对依赖受影响的结果标记需重验，而不是让所有历史结果无差别永久失效。
- `DA01.10.3` 用同一个操作入口接收轮换或撤销指令，后续可按凭据提供方和发布粒度拆分；这两个动作不能因重试重复生效。

v0.1 先明确语义契约和目录映射；JSON Schema 的精确字段、类型系统、实际后端组合和生产容量在实现前收敛。保留这些选择不影响本版逐项判断“谁输入什么、产出什么、由哪里实现”。

## 6. 依据

- [飞书规划](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)，revision 1022。
- [本地完整 XML 快照](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)。
- [此前数据层/应用层/治理层分类](https://modelbest.feishu.cn/docx/TlN4dygs9oJR3Qx1FaictiPEn3c)。

能力覆盖以 revision 1022 为基线；早期草稿仅用于分类背景。本文档未向飞书回写。

# DA01｜数据接入：输入输出与代码划分 v0.1

定位：外部来源、文件与业务环境资源的连接、读取和引用管理。

**模块输入**：来源连接配置、凭据引用、文件/资源引用、读取范围、目录与增量配置。

**模块输出**：可用连接引用、源结构、原始内容或记录批次、来源位置、完整性与接入状态。

**模块边界**：与业务系统交互只承担连接、读取和声明探测；SQL 运行归 DA07，业务语义归 DA03。凭据与增量订阅由专门端口承接。

本文件与 [共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/ingestion/`。共 10 个能力组、31 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
|-|-|-|-|-|
| DA01.1 来源连接 | 接入数据库、API、MCP 等来源，管理连接与身份引用。 | 连接配置与凭据引用 | 可用连接句柄 | `connections.py` |
| DA01.2 结构读取 | 获取数据库表列、类型、键，以及 API/MCP 返回对象的数据结构。 | 连接 | 表/字段/类型/键清单 | `schemas.py` |
| DA01.3 数据读取 | 按字段、条件、分页或采样读取数据。 | 表+字段+条件 | 行集合 | `reads.py` |
| DA01.4 文件解析 | 读取 Excel、CSV、JSON 和 PDF 文本层，保留 sheet、公式、坐标等结构。 | 文件字节 | 结构化记录 + 版面坐标 | `files.py` |
| DA01.5 OCR | 识别扫描 PDF 和图片中的文字、位置。 | 图像或扫描页 | 文本与位置 | `ocr.py` |
| DA01.6 资产目录登记 | 记录资产位置、责任人、适用范围及更新承诺。复用现有目录；登记承诺与实际新鲜度分别记录。 | 资产 | 目录条目（位置/维护者/新鲜度） | `catalog.py` |
| DA01.7 增量与事件接入 | 持续接收变化，保留顺序、水位及补采位置。依赖来源能力；任务调度和通用重试复用平台。 | 水位或变更流 | 增量记录 | `changes.py` |
| DA01.8 环境资源接入 〔FDE〕 | 复用 DA01.1 的连接，枚举并读取文件系统、SaaS、业务系统、消息、工单、代码仓和 Web 等资源。 | 业务环境 | 资源引用、内容与元数据 | `resources.py` |
| DA01.9 能力探测 〔FDE〕 | 获取资源能做什么、参数约束与调用限制。与 DA01.2 的区别是「能做什么」而非「有什么字段」；不把接口存在当作可安全使用。 | 资源引用 | 可执行动作与限制清单 | `capabilities.py` |
| DA01.10 凭据代理与归属 〔FDE〕 | 绑定凭据但不暴露给模型，登记资源归谁所有。 | 凭据引用 | 代调用能力（密钥不出域） | `credentials.py` |

## 原子能力契约

### DA01.1 来源连接

边界：负责建立可用连接；环境对象的枚举和读取由 DA01.8 复用本能力完成。连接成功不代表支持 SQL。

实现位置：`src/dataagent_data/ingestion/connections.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.1.1 数据库连接 | `connect_database` | 数据库类型、地址、库名、连接选项、credential_ref | ConnectionRef；后端类型、连接状态、可用特性 | 只建立连接，不执行用户 SQL；凭据由代理解析。 |
| DA01.1.2 API 连接 | `connect_api` | base_url、鉴权引用、超时、接口说明引用 | ConnectionRef；API 描述引用、连接诊断 | 不将 HTTP 连接成功视为数据完整或业务授权。 |
| DA01.1.3 MCP 连接 | `connect_mcp` | 服务地址或启动配置、传输类型、凭据引用 | ConnectionRef；服务身份、工具目录引用 | 目录是能力声明，动作探测由 DA01.9 完成。 |

### DA01.2 结构读取

边界：描述数据结构；动作参数、可执行操作和调用限制归 DA01.9，不推断业务含义。

实现位置：`src/dataagent_data/ingestion/schemas.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.2.1 数据库 Schema 读取 | `read_database_schema` | ConnectionRef、catalog/schema/table 选择范围 | SchemaRef；表列、类型、键、源端声明及读取时间 | 外键未声明时保留未知，不推断业务 Join。 |
| DA01.2.2 API 返回结构读取 | `read_api_response_schema` | ConnectionRef、端点描述或已授权响应样本 | SchemaRef；字段路径、类型、嵌套与可空信息 | 从样本推断与正式 schema 分开标记；不为探测发起副作用调用。 |
| DA01.2.3 MCP 返回结构读取 | `read_mcp_response_schema` | ConnectionRef、工具标识、输出声明或已有结果样本 | SchemaRef；返回内容类型及结构、覆盖缺口 | 返回结构与输入参数契约分开。 |

### DA01.3 数据读取

边界：SQL 执行统一使用 DA07.1。

实现位置：`src/dataagent_data/ingestion/reads.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.3.1 条件读取 | `read_filtered_data` | 资源引用、字段投影、已支持的条件、分页起点 | DataBatchRef；实际条件、cursor、completeness | 不支持的条件返回 unsupported；SQL 请求转 DA07.1。 |
| DA01.3.2 分页读取 | `read_data_page` | 资源引用、读取条件、cursor、page_size、快照约束 | DataBatchRef；next_cursor、has_more、快照一致性说明 | 逐页返回；页取完不等于存在全局一致快照。 |
| DA01.3.3 采样读取 | `sample_data` | 资源引用、采样方法、样本量或比例、可用随机种子 | DataBatchRef；采样方法、样本数、总体估计与局限 | 头部截取须标明非随机，不伪装代表性抽样。 |

### DA01.4 文件解析

边界：不规则 Excel 入口复用 DA02 的表块检测和结构恢复；PDF 表格提取也复用 DA02，扫描件先使用 OCR。

实现位置：`src/dataagent_data/ingestion/files.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.4.1 规整 Excel 解析：提取明确表头的单表或多 sheet 表 | `parse_regular_excel` | FileRef、sheet/range 选择、表头行与公式读取策略 | WorkbookRef；TableRef 列表、坐标映射、公式与缓存值 | 多 sheet 分表输出，不自动 Join；无公式引擎时不宣称重算。 |
| DA01.4.2 不规则 Excel 提取：从混合布局中恢复逻辑表 | `extract_irregular_excel` | FileRef、候选区域、布局提示、恢复策略 | TableRef 列表；SourceAnchor、结构候选、待确认问题 | 组合 DA02.1/2；保留原文件，不把歧义布局静默定为唯一表。 |
| DA01.4.3 CSV/TSV 解析：处理分隔符与编码 | `parse_delimited_file` | FileRef、分隔符、编码、转义与表头选项 | TableRef；SchemaRef、行位置、坏行清单 | 编码或分隔符探测可返回候选；坏行不静默丢弃。 |
| DA01.4.4 JSON/JSONL 解析：保留嵌套记录 | `parse_json_records` | FileRef、JSON/JSONL 格式、记录路径、容错策略 | DocumentRef 或 DataBatchRef；嵌套 schema、JSON Pointer、坏记录 | 嵌套结构先保留；展开为列由 DA02.3.3 完成。 |
| DA01.4.5 文本型 PDF 解析：读取文字与版面位置 | `parse_text_pdf` | FileRef、页范围、版面提取选项 | DocumentRef；文字块、页坐标、阅读顺序候选 | 无文本层的页标注需 OCR；表格恢复复用 DA02。 |

### DA01.5 OCR

边界：保留识别不确定性，不纠正业务数字。

实现位置：`src/dataagent_data/ingestion/ocr.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.5.1 扫描 PDF OCR | `ocr_pdf` | FileRef、页范围、语言、渲染与识别配置 | DocumentRef；逐页文字、bbox、置信度与引擎版本 | 识别结果与原页关联，低置信数字保留问题标记。 |
| DA01.5.2 图片 OCR | `ocr_image` | FileRef、区域、方向、语言与识别配置 | DocumentRef；文字块、图像坐标、置信度 | 不自动把识别近似值改成业务认可值。 |

### DA01.6 资产目录登记

边界：—。

实现位置：`src/dataagent_data/ingestion/catalog.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.6.1 资产目录登记 | `register_asset` | AssetRef、名称、位置、内容类型、作用域、expected_revision | CatalogEntryRef；登记回执、条目版本 | 登记引用不复制全量数据；修改已有条目须做版本冲突检查。 |
| DA01.6.2 维护者与使用条件登记 | `register_asset_stewardship` | CatalogEntryRef、责任人、使用条件、策略引用、expected_revision | 更新后 CatalogEntryRef；变更回执 | 使用条件是声明，实际访问仍由授权机制检查。 |
| DA01.6.3 更新承诺与新鲜度登记 | `register_refresh_commitment` | CatalogEntryRef、刷新承诺、观测来源、expected_revision | 更新承诺引用；与实际新鲜度分列的目录版本 | 承诺不能当成数据已更新的事实。 |

### DA01.7 增量与事件接入

边界：—。

实现位置：`src/dataagent_data/ingestion/changes.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.7.1 游标/水位增量读取 | `read_incremental_cursor` | 资源引用、已提交水位、读取上限、源端快照条件 | ChangeBatchRef；候选新水位、源端一致性与缺口 | 下游持久化成功后才提交水位，读取本身不推进已提交位置。 |
| DA01.7.2 CDC/事件接入 | `subscribe_change_events` | ConnectionRef、订阅范围、起始 offset、消费配置 | SubscriptionRef；事件批次读取句柄、起始位置与租约 | 长流通过句柄分批拉取；不承诺源端没有提供的 exactly-once。 |
| DA01.7.3 迟到与重复事件处理 | `reconcile_change_events` | ChangeBatchRef、事件键、时序键、迟到窗口、状态引用 | 规整事件批次；去重清单、迟到标记、候选水位与状态版本 | 源内时序不能无依据升级为跨源全局时序。 |

### DA01.8 环境资源接入 〔FDE〕

边界：统一资源引用与元数据，保留表、文档、图像、嵌套对象和事件等内容类型，以及分页、快照、权限等来源语义。

实现位置：`src/dataagent_data/ingestion/resources.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.8.1 资源枚举 | `enumerate_resources` | ConnectionRef、父资源、类型过滤、cursor | ResourceRef 列表；层级、next_cursor、可见范围 | 复用连接，按授权枚举；不可见对象不作为不存在的结论。 |
| DA01.8.2 资源读取 | `read_resource` | ResourceRef、所需视图、版本条件、读取范围 | 内容 AssetRef；原始元数据、实际版本和内容类型 | 保留来源结构；不要求文档、图像都转二维表。 |
| DA01.8.3 资源引用与元数据归一 | `normalize_resource_metadata` | 源端对象描述、source_id、源端版本与定位信息 | ResourceRef；标准元数据和来源扩展字段 | 统一寻址与类型，不抹掉分页、快照或权限语义。 |

### DA01.9 能力探测 〔FDE〕

边界：—。

实现位置：`src/dataagent_data/ingestion/capabilities.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.9.1 动作能力枚举 | `enumerate_action_capabilities` | ConnectionRef 或 ResourceRef、工具目录或端点声明 | CapabilityDescriptor 列表；只读/副作用声明、可用状态 | 仅发现声明，不试执行写操作，也不授予执行权限。 |
| DA01.9.2 参数与约束探测 | `inspect_action_constraints` | CapabilityDescriptor、接口规范、已有调用诊断 | 入参约束、返回条件、前置要求及未知项 | 缺失规范标注未知，不能通过危险探测补齐。 |
| DA01.9.3 限流与配额探测 | `inspect_rate_limits` | ConnectionRef、能力标识、文档或响应头、观测窗口 | LimitProfile；速率、配额、重置时间、可信来源 | 发现限制不等于分配预算；不通过压测探测生产限额。 |

### DA01.10 凭据代理与归属 〔FDE〕

边界：不在上下文中出现明文密钥。

实现位置：`src/dataagent_data/ingestion/credentials.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA01.10.1 凭据代理与不落地 | `bind_credential_proxy` | CredentialRef、目标连接、允许的调用范围、有效期 | CredentialBindingRef；代理句柄与绑定回执 | 模型与普通结果中不出现明文密钥；实际调用仍走对应适配器。 |
| DA01.10.2 资源归属登记 | `register_resource_owner` | ResourceRef、所属主体、责任依据、expected_revision | OwnershipRef；主体关联及版本回执 | 资源归属不自动授予主体或 Agent 权限。 |
| DA01.10.3 轮换与失效 | `rotate_or_revoke_credential` | CredentialBindingRef、rotate/revoke、新凭据引用或失效条件 | 绑定新版本或撤销回执；受影响连接、状态 | 需要凭据系统提供相应操作，旧值不写入返回或轨迹。 |

# DA02｜数据准备与探查：输入输出与代码划分 v0.1

定位：将原始表格、文档和记录整理为可分析的数据，并保留结构、画像与技术依赖。

**模块输入**：原始文件解析结果、表/文档引用、结构、画像预算、变换规则、已有运行记录。

**模块输出**：结构恢复结果、数据集新版本、画像/关系候选、数据血缘、文档单元、快照和现状基线。

**模块边界**：探查产出候选；正式业务定义交 DA03。表格/文档处理保留原文锚点，变换产生新数据。现状流程、角色与基线属于按需启用的 FDE 扩展。

本文件与 [共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/preparation/`。共 15 个能力组、48 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
|-|-|-|-|-|
| DA02.1 表格区域识别 | 从页面或 sheet 中定位一个或多个表块。 | 页面或工作表 | 表块坐标 | `regions.py` |
| DA02.2 表格结构恢复 | 识别多行表头、合并单元格、分节、重复表头、合计行及续表结构。 | 表块 | 规整二维表（表头/类型/明细） | `structure.py` |
| DA02.3 数据结构转换 | 按指定规则转置、宽长转换、展开嵌套或拼接表格。 | 二维表 | 目标结构记录 | `reshape.py` |
| DA02.4 数据画像 | 统计结构、空值、基数、分布，推断字段类型、时间和记录粒度。 | 表 | 字段统计与语义角色 | `profiles.py` |
| DA02.5 Join 关系发现 | 根据键、覆盖率、基数和历史查询寻找关联候选。 | 两表 | 候选键与 Join 基数 | `joins.py` |
| DA02.6 数据清洗 | 按选定规则执行去重、类型转换、标准化和缺失处理。 | 脏记录 | 清洗后记录 + 改动清单 | `cleaning.py` |
| DA02.7 数据血缘 | 说明数据从哪里来、经过什么处理。 | SQL 或任务 | 表级列级依赖 | `lineage.py` |
| DA02.8 文档加工 | 将解析后的文档整理成保留上下文和原文位置的检索单元。 | 文档 | 章节/条款切分 + 原文锚点 | `documents.py` |
| DA02.9 结构变化适配 | 识别字段、接口及编码变化，判断既有读取和映射是否失效。 | 新旧结构 | 差异与映射建议 | `schema_changes.py` |
| DA02.10 修复建议与复核 | 根据质量问题提出方案，将接受、驳回和修改原因沉淀为有范围的规则。 | 问题清单 | 修复方案 + 验证结果 | `repairs.py` |
| DA02.11 历史数据保留 | 保留可重算数据或有效的源端历史引用。 | 查询或文件 | 可回溯快照引用 | `snapshots.py` |
| DA02.12 文档信息抽取 | 从合同、单据、病历等文档中按指定结构抽取字段和记录，形成可入表的数据。 | 文档 | 目标字段值 + 原文锚点 | `extraction.py` |
| DA02.13 流程勘查 〔FDE〕 | 还原 as-is 流程，包含不写在文档里的非正式做法。 | 访谈与材料 | 步骤、分支与例外 | `processes.py` |
| DA02.14 角色与审批链还原 〔FDE〕 | 记录「谁实际决定」而不只是组织架构上谁负责。 | 材料 | 角色表与审批链 | `roles.py` |
| DA02.15 现状基线 〔FDE〕 | 建立改动前可对比的基线。 | 现场数据 | 工时/错误率/成本基线 | `baselines.py` |

## 原子能力契约

### DA02.1 表格区域识别

边界：不判断业务对象是什么。

实现位置：`src/dataagent_data/preparation/regions.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.1.1 工作簿表块检测 | `detect_workbook_regions` | WorkbookRef、sheet 范围、布局提示 | TableRegion 列表；单元格范围、候选置信度与重叠问题 | 只定位表块，不决定跨块业务关系。 |
| DA02.1.2 文档页面表格检测 | `detect_page_tables` | DocumentRef、页范围、文字/图像布局 | TableRegion 列表；页 bbox、单元格候选及原页锚点 | 模型检测结果是候选，不自动产生认证业务记录。 |

### DA02.2 表格结构恢复

边界：保留原值；不能确认的拼接保留待确认状态。

实现位置：`src/dataagent_data/preparation/structure.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.2.1 多行表头恢复 | `recover_headers` | TableRegion、单元格或文字网格、表头策略 | 表头路径与目标列映射；TableRef、歧义列表 | 保留多层表头原路径，不能为同名列任意合并。 |
| DA02.2.2 合并单元格展开 | `expand_merged_cells` | 表块或 TableRef、合并区域、允许传播的范围 | 新 TableRef；展开映射与变换记录 | 只按结构规则传播合并值，不填补非合并空值。 |
| DA02.2.3 明细/合计行识别 | `classify_table_rows` | TableRef、标签及公式线索、识别配置 | 行角色标注；明细/合计/小计/标题/未知、依据 | 只标注，不删除合计行或改动金额。 |
| DA02.2.4 跨页续表拼接 | `stitch_continued_tables` | TableRef 列表、页序、列对齐与续表提示 | 拼接候选 TableRef；来源映射、冲突与未拼接块 | 不确定的续表关系返回候选，保持原块可追溯。 |

### DA02.3 数据结构转换

边界：不替用户决定跨表业务关系。

实现位置：`src/dataagent_data/preparation/reshape.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.3.1 表格转置 | `transpose_table` | TableRef、目标表头与索引规则 | 新 TableRef；字段/单元格映射、变换记录 | 转置不重新解释业务实体或粒度。 |
| DA02.3.2 宽长表转换 | `reshape_table` | TableRef、宽转长或长转宽、id/value 字段、冲突规则 | 新 TableRef；目标 SchemaRef、映射与冲突 | 长转宽遇多值必须显式给聚合规则，不静默取首值。 |
| DA02.3.3 嵌套字段展开 | `flatten_nested_records` | DataBatchRef、字段路径、展开深度、数组展开策略 | TableRef 或表集合；父子键、路径映射、行膨胀统计 | 保留数组顺序和父记录标识，不默认做笛卡尔积。 |
| DA02.3.4 同结构表追加 | `append_compatible_tables` | TableRef 列表、列对齐、类型兼容与来源列选项 | 新 TableRef；schema 差异、来源映射、行数对账 | 仅追加同构记录，业务 Join 由 DA03/DA06 决定。 |

### DA02.4 数据画像

边界：推断是候选，不直接成为业务定义。

实现位置：`src/dataagent_data/preparation/profiles.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.4.1 表结构画像 | `profile_table_structure` | TableRef 或 SchemaRef、统计预算与采样计划 | ProfileRef；字段形态、行列规模、约束与统计覆盖 | 区分 schema 声明、精确统计和采样估计。 |
| DA02.4.2 字段取值画像 | `profile_field_values` | TableRef、字段集合、采样与敏感值输出策略 | ProfileRef；空值、基数、分布、受限样例与覆盖 | 遵守值访问与脱敏要求；样本统计不声明全量结论。 |
| DA02.4.3 字段类型推断 | `infer_field_types` | SchemaRef、ProfileRef、允许的类型词表 | 类型候选；置信度、依据和冲突 | 这是数据/语义类型候选，不修改源 schema 或认证实体定义。 |
| DA02.4.4 时间角色识别 | `infer_time_roles` | 字段结构、取值画像、相关说明 | 时间角色候选；事件/入库/生效等、依据与歧义 | 字段名相近不等于业务时间相同。 |
| DA02.4.5 记录粒度识别 | `infer_record_grain` | TableRef、键与重复画像、来源说明 | 粒度候选；唯一性统计、反例和限定范围 | 样本唯一不代表全量主键，不自动确立业务粒度。 |

### DA02.5 Join 关系发现

边界：业务关系确认归 DA03。

实现位置：`src/dataagent_data/preparation/joins.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.5.1 键关系发现 | `discover_key_candidates` | SchemaRef 列表、ProfileRef、候选字段范围 | 主键/外键候选；对应字段、统计依据与缺口 | 与源端正式约束区分，不直接写入合法业务 Join。 |
| DA02.5.2 取值覆盖匹配 | `compare_value_coverage` | 两组字段引用、标准化规则、采样/精算预算 | 交叠率、覆盖方向、空值比例、未匹配样例引用 | 取值重叠是候选证据，不证明实体相同。 |
| DA02.5.3 Join 基数探查 | `profile_join_cardinality` | 候选 Join、TableRef、过滤条件、统计预算 | 一对一/多对多等基数报告；膨胀率、覆盖与反例 | 限定到实际快照及过滤范围；业务合法性归 DA03。 |

### DA02.6 数据清洗

边界：保留原件和变换记录，不静默补造事实。

实现位置：`src/dataagent_data/preparation/cleaning.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.6.1 重复记录处理 | `deduplicate_records` | TableRef、重复判定键、保留或合并规则 | 新 TableRef；重复分组、保留映射、改动记录 | 模糊匹配须明确阈值；不覆盖原件。 |
| DA02.6.2 类型转换 | `cast_field_types` | TableRef、目标类型、locale、失败处理策略 | 新 TableRef；转换失败、溢出与精度损失清单 | 不能转换的值保留问题，不静默变为 null。 |
| DA02.6.3 取值标准化 | `normalize_field_values` | TableRef、字段、映射字典与标准化规则版本 | 新 TableRef；值映射、未命中项与变换记录 | 应用指定字典，不自行修改正式业务枚举。 |
| DA02.6.4 缺失值处理 | `handle_missing_values` | TableRef、缺失定义、标记/填补策略及依据 | 新 TableRef；缺失掩码、填补值来源与统计 | 填补值与观测事实分开标识，默认不凭模型补造事实。 |

### DA02.7 数据血缘

边界：区分静态推断与实际执行记录；动态 SQL、存储过程或未覆盖的代码需标注缺口，不据此推断业务口径。

实现位置：`src/dataagent_data/preparation/lineage.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.7.1 源端血缘导入：接入数据目录、ETL 或数据库已有血缘 | `import_source_lineage` | 源端目录/ETL 血缘、资产标识映射、版本范围 | 数据血缘候选边；来源、覆盖范围、无法解析项 | 保存源端声明来源，不当成实际执行观测。 |
| DA02.7.2 SQL 血缘提取：解析表、视图和列的读取与派生关系 | `extract_sql_lineage` | SQL 文本或 AssetRef、方言、SchemaRef、作用域 | 数据血缘边；表/列依赖、表达式引用、解析缺口 | 动态 SQL 或未知 UDF 标注覆盖缺口；不推导业务口径。 |
| DA02.7.3 转换血缘采集：记录文件处理、代码和数据转换的来源及去向 | `collect_transformation_lineage` | 实际执行事件、输入/输出 AssetRef、列映射或代码引用 | observed 数据血缘边；run_id、变换版本及缺口 | 只采集实际提供的信息，不用模型补造已观测列级映射。 |
| DA02.7.4 数据血缘维护：保存和更新带版本的表级、列级依赖 | `upsert_data_lineage` | 数据血缘边、依赖版本、expected_revision | LineageRef；新增/替代/失效边及存储回执 | 保存表列处理关系；资产通用版本政策复用 DA12。 |

### DA02.8 文档加工

边界：复用 DA01 解析，不承担检索或业务结论判断。

实现位置：`src/dataagent_data/preparation/documents.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.8.1 章节/表格切分 | `segment_document` | DocumentRef、章节/条款/表格分块策略、上下文窗口 | DocumentUnitRef 列表；层级、原文锚点、跨块上下文 | 划分检索单元，不执行检索或形成业务判定。 |
| DA02.8.2 原文引用锚点维护 | `maintain_source_anchors` | 文档单元或字段引用、SourceAnchor、源版本、修订映射 | 锚点映射版本；可解析/过期/无法定位状态 | 原文件变化后不能沿用相同坐标并声称仍有效。 |

### DA02.9 结构变化适配

边界：修订建议不自动改变业务定义。

实现位置：`src/dataagent_data/preparation/schema_changes.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.9.1 Schema 差异检测 | `diff_schemas` | 旧/新 SchemaRef、兼容规则 | SchemaDiff；新增/删除/改名候选/类型变更 | 重命名是候选，不能仅凭位置认定同一字段。 |
| DA02.9.2 接口兼容检查 | `check_interface_compatibility` | 旧/新接口描述、已用参数与返回字段、兼容标准 | CompatibilityReport；破坏项、受影响调用点与缺口 | 静态兼容不保证运行成功或业务等价。 |
| DA02.9.3 字段映射修订建议 | `propose_field_remapping` | SchemaDiff、旧 MappingRef、取值画像与说明 | 映射修订候选；依据、冲突及验证需求 | 不直接替换正式语义映射。 |

### DA02.10 修复建议与复核

边界：执行复用 DA02.6，验证复用 DA11，不自动覆盖原数据。

实现位置：`src/dataagent_data/preparation/repairs.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.10.1 修复方案生成 | `propose_data_repairs` | 质量问题、ProfileRef、允许修复策略、原始数据引用 | RepairProposal；步骤、受影响范围、预期变化与风险 | 仅给方案；执行复用 DA02.6，验证复用 DA11。 |
| DA02.10.2 修复前后验证 | `compare_repair_results` | 原/修复后 TableRef、修复计划、验证判据引用 | ValidationReportRef；差异、对账及未解决问题 | 复用 DA11 检查，不自建另一套正确性判据。 |
| DA02.10.3 复核反馈转修复规则 | `derive_repair_rule` | 复核决定、对应问题与改动、适用范围、样本引用 | 修复规则候选；正反例、适用与失效条件 | 人工接受一次不等于可跨企业自动应用。 |

### DA02.11 历史数据保留

边界：仅有时间戳、digest 或最新数据不能保证历史重现。

实现位置：`src/dataagent_data/preparation/snapshots.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.11.1 文件/查询结果快照保存 | `save_data_snapshot` | FileRef 或查询结果引用、保留要求、目标存储 | SnapshotRef；digest、字节/记录范围、实际保存状态 | 必须保有内容或有效历史读取能力，digest 本身不是快照。 |
| DA02.11.2 源端 as-of/快照引用 | `bind_source_snapshot` | 资源引用、as-of/版本 token、源端能力、可选校验请求 | SnapshotRef；解析方式、有效期及可重读能力 | 时间戳不自动等价于可重现；无法保证时明确限制。 |

### DA02.12 文档信息抽取

边界：复用 DA01 解析与 OCR；每个值关联原文位置和置信度，低置信结果保留待确认，不补造缺失值。

实现位置：`src/dataagent_data/preparation/extraction.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.12.1 按目标结构抽取字段 | `extract_fields_to_schema` | DocumentRef、目标字段定义、上下文与提取策略 | ExtractedRecordRef；字段值、置信度、SourceAnchor、缺失项 | 按目标结构抽取，结构草案由调用方提供，不补造缺失值。 |
| DA02.12.2 表单/单据键值抽取 | `extract_form_key_values` | DocumentRef、表单区域、可选字段字典 | 键值记录；重复键、键值区域、置信度及歧义 | 跨页或一键多值不强制压成单值。 |
| DA02.12.3 抽取结果原文锚定 | `anchor_extracted_values` | ExtractedRecordRef、原 DocumentRef、候选原文位置 | 字段到 SourceAnchor 的映射；可核验匹配与未定位项 | 不能定位的值标注缺口，不编造引用。 |

### DA02.13 流程勘查 〔FDE〕

边界：不直接给 to-be 方案。

实现位置：`src/dataagent_data/preparation/processes.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.13.1 步骤与触发条件提取 | `extract_process_steps` | 访谈/流程文档单元引用、业务范围 | 步骤与触发条件候选；来源锚点及待确认项 | 记录现状，不直接生成未来改造流程。 |
| DA02.13.2 分支与例外路径记录 | `record_process_exceptions` | 流程步骤、访谈/案例引用、分支描述 | 分支与例外路径；触发条件、证据和覆盖缺口 | 文档规定与实际做法不一致时分别记录。 |
| DA02.13.3 人工步骤识别 | `identify_manual_steps` | 流程图或步骤集合、角色与操作材料 | 人工步骤标记；人工原因、交接点与待确认项 | 人工环节不自动等同不可自动化。 |

### DA02.14 角色与审批链还原 〔FDE〕

边界：不替代授权系统。

实现位置：`src/dataagent_data/preparation/roles.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.14.1 角色与权限现状 | `describe_current_roles` | 组织/权限材料引用、业务环境范围、观测记录 | 角色与实际权限现状；时点、声明/观测差异 | 描述现状，不授予或撤销权限。 |
| DA02.14.2 事实上的决定者识别 | `identify_actual_deciders` | 流程轨迹、访谈、角色现状、业务事项 | 决定者候选；事项、依据和分歧 | 实际影响力不等于正式审批权限。 |
| DA02.14.3 审批链还原 | `reconstruct_approval_chain` | 流程步骤、角色信息、审批历史或制度引用 | 审批链候选；条件分支、角色和例外 | 观测审批链与正式授权策略分别标识。 |

### DA02.15 现状基线 〔FDE〕

边界：不承诺改进幅度。

实现位置：`src/dataagent_data/preparation/baselines.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA02.15.1 人工耗时与频次 | `measure_manual_effort` | 业务事件/人工记录、时间窗口、计量规则 | 人工耗时/频次基线；样本量、缺口与统计口径 | 自报耗时与自动测量分开，不做收益承诺。 |
| DA02.15.2 错误率与返工率 | `measure_rework_baseline` | 处理记录、错误/返工定义、样本范围 | 错误率/返工率基线；分母、区间与来源 | 跨期比较必须使用一致判据与分母。 |
| DA02.15.3 成本基线 | `measure_cost_baseline` | 人工与系统成本记录、分摊规则、时间/币种 | 成本基线；成本项、假设、区间和未覆盖项 | 估算与实付分列，收益比较交 DA18.5。 |

# DA03｜业务语义与关系：输入输出与代码划分 v0.1

定位：表达业务实体、关系、指标、规则和定义依赖，连接到物理数据、文档或接口。

**模块输入**：业务材料、结构与探查结果、既有语义版本、目标作用域与生效时间、工具与数据可用条件。

**模块输出**：语义草案或获准保存的版本、物理映射、定义依赖、历史版本解析、冲突和可判定性评估。

**模块边界**：生成、推断默认产出草案；保存不等于发布。权限和证据模型是业务定义，运行时授权及最终验证由对应模块负责。

本文件与 [共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/semantics/`。共 16 个能力组、50 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
|-|-|-|-|-|
| DA03.1 实体建模 | 定义客户、订单等实体及其属性、状态和粒度。 | 结构+画像 | 实体与属性定义 | `entities.py` |
| DA03.2 身份对齐 | 识别跨系统的同一对象，维护编码和别名映射。 | 多源实体 | 统一实体标识 | `identity.py` |
| DA03.3 关系建模 | 表达实体关系、合法 Join、基数、时态和租户条件。 | 实体 | 关系与 Join 规则 | `relationships.py` |
| DA03.4 指标与规则定义 | 定义指标公式、维度、业务规则及适用范围。 | 业务需求 | 指标公式/维度/规则 | `metrics_rules.py` |
| DA03.5 时间与单位定义 | 定义业务时间、财务日历、币种、单位及换算规则。 | 业务日历 | 时间与单位换算规则 | `time_units.py` |
| DA03.6 语义映射与存储 | 保存业务定义及其物理实现、说明来源，连接业务语义血缘与数据血缘。 | 语义定义 | 语义库 + 表列映射 | `mappings.py` |
| DA03.7 业务语义血缘 | 说明业务定义依赖什么，物理实现通过 DA03.6 关联。 | 语义定义 | 指标与规则依赖图 | `lineage.py` |
| DA03.8 历史口径解析 | 选择历史时点适用的定义，区分业务生效时间与系统记录时间。 | 时点 | 该时点生效的语义版本 | `history.py` |
| DA03.9 语义导入与冷启动 | 在没有现成语义层时尽快形成可用语义。 | 外部语义与历史 SQL | 语义草案 + 待确认项 | `bootstrap.py` |
| DA03.10 语义冲突识别 | 发现不同部门、来源或版本之间的定义冲突，并给出可选方案。 | 语义库 | 冲突清单 + 协调方案 | `conflicts.py` |
| DA03.11 动作语义 〔FDE〕 | 定义业务对象上的动作含义、业务参数、前后状态和影响。 | 业务动作 | 动作类型/参数/前后置/影响面 | `actions.py` |
| DA03.12 权属模型 〔FDE〕 | 声明谁在什么条件下可以做什么。 | 业务角色 | 三档权限与审批策略 | `authority.py` |
| DA03.13 证据模型 〔FDE〕 | 定义各类结论需要什么证据，以及正式的证据充分性标准。 | 结论类型 | 所需证据与充分性判据 | `evidence.py` |
| DA03.14 状态与生命周期 | 定义业务状态及其迁移。 | 业务对象 | 状态机 | `lifecycle.py` |
| DA03.15 可判定性评估 | 依据当前数据、工具、方法和业务要求，评估某项要求能否自动判断、需要补证还是需要人工裁量。 | 要求与可用条件 | 可自动判断 / 待补证 / 需人工及原因 | `decidability.py` |
| DA03.16 适用范围建模 | 定义规则或方法适用于哪些对象、业务场景及生效前提，判断是否适用于本次对象。 | 条款 | 适用范围与前置条件 | `applicability.py` |

## 原子能力契约

### DA03.1 实体建模

边界：不等同于物理表定义。

实现位置：`src/dataagent_data/semantics/entities.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.1.1 实体类型定义 | `define_entity_types` | 业务描述、结构/画像引用、来源材料、作用域 | EntityDraft；类型标识、业务定义、来源与歧义 | 产出草案，不将物理表直接认定为业务实体。 |
| DA03.1.2 实体属性定义 | `define_entity_attributes` | 实体版本引用、属性需求、类型/单位候选、来源 | 实体属性草案；类型、可空、粒度及依据 | 属性含义与物理列绑定分开，绑定由 DA03.6 完成。 |
| DA03.1.3 对象状态定义 | `define_entity_state_vocabulary` | 实体引用、状态字段样例、业务说明 | 状态词表草案；编码、含义及未知值 | 仅定义词表，迁移规则归 DA03.14。 |

### DA03.2 身份对齐

边界：不直接覆盖业务主数据。

实现位置：`src/dataagent_data/semantics/identity.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.2.1 编码映射 | `build_code_mapping` | 两个编码体系、对照依据、适用范围与时间 | MappingDraft；编码对应、未匹配与冲突 | 保存映射候选，不覆盖源端主数据。 |
| DA03.2.2 别名匹配 | `match_entity_aliases` | 名称/别名集合、实体范围、上下文、匹配阈值 | 别名关系候选；匹配依据、分数与歧义 | 同名不等于同一对象，默认不强制合并身份。 |
| DA03.2.3 跨源实体匹配 | `match_cross_source_entities` | 多源实体记录引用、匹配键/方法、验证样本 | EntityMatchProposal；统一 ID 候选、映射、未决项 | 个人身份或敏感字段按授权使用；不直接写回主数据。 |

### DA03.3 关系建模

边界：使用探查候选，但不把值重合直接认作合法关系。

实现位置：`src/dataagent_data/semantics/relationships.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.3.1 实体关系定义 | `define_entity_relationships` | 实体版本引用、关系描述、探查候选与业务依据 | RelationshipDraft；方向、基数、作用域及来源 | 业务对象关系与派生依赖血缘区分。 |
| DA03.3.2 Join 规则定义 | `define_join_rules` | 实体/表映射、键候选、业务粒度、租户与过滤约束 | JoinRuleDraft；连接条件、基数、限制及验证需求 | 不以值重合直接认证 Join 合法。 |
| DA03.3.3 时态关系定义 | `define_temporal_relationships` | 关系引用、有效期字段、时态匹配规则 | 时态关系草案；as-of/区间条件、边界与冲突处理 | 不执行时态 Join，正式计算归 DA06/07。 |

### DA03.4 指标与规则定义

边界：不执行查询；未经确认的定义保留草案。

实现位置：`src/dataagent_data/semantics/metrics_rules.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.4.1 指标公式定义 | `define_metric_formula` | 指标业务描述、基础指标引用、时间/粒度/单位要求 | MetricDraft；公式、依赖、过滤、聚合与来源 | 定义口径，不生成执行 SQL；依赖缺失保留未绑定项。 |
| DA03.4.2 维度层级定义 | `define_dimension_hierarchy` | 维度描述、层级样例、成员与有效期要求 | DimensionDraft；层级、成员关系、非严格层级约束 | 不默认为树或允许任意汇总，记录多父级与不可加性。 |
| DA03.4.3 业务规则定义 | `define_business_rules` | 制度条款/业务要求、实体与指标引用、例外说明 | RuleDraft；条件、约束、例外、范围及原文来源 | 自然语言或结构化规则均可，不能强制所有规则编译成同一种 DSL。 |

### DA03.5 时间与单位定义

边界：实际计算由执行能力完成。

实现位置：`src/dataagent_data/semantics/time_units.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.5.1 业务时间定义 | `define_business_time` | 时间角色、时区、期间边界、业务依据 | BusinessTimeDraft；时间口径、时区与边界规则 | 不以入库时间替代业务事件时间。 |
| DA03.5.2 财务日历定义 | `define_fiscal_calendar` | 财务制度、起始月、周/假期规则、适用年份 | CalendarDraft；期间映射及生效范围 | 历法规则与生成的具体日期表区分；计算复用执行层。 |
| DA03.5.3 单位换算定义 | `define_unit_conversions` | 源/目标单位、转换规则、汇率来源、有效时间 | ConversionDraft；换算规则、精度、依赖及时间条件 | 汇率引用须有时点，不能静默使用当前值重算历史。 |

### DA03.6 语义映射与存储

边界：映射注明版本和适用范围；映射到某列不等于业务定义已经验证。

实现位置：`src/dataagent_data/semantics/mappings.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.6.1 业务语义存储 | `save_semantic_objects` | 语义草案或获准修订、对象标识、expected_revision、来源 | SemanticRef；保存版本、状态及写入回执 | 存储不等于发布认证；生效策略由 DA12 决定。 |
| DA03.6.2 语义与表列映射 | `map_semantics_to_columns` | SemanticRef、SchemaRef、字段路径、转换与适用范围 | MappingDraft 或版本化 MappingRef；映射、歧义与依据 | 模型建议默认是草案；获准保存也不意味着业务定义已验证。 |
| DA03.6.3 语义与 API/文档映射 | `map_semantics_to_resources` | SemanticRef、API/文档/函数等资源引用、访问路径及范围 | MappingDraft 或 MappingRef；资源路径、字段/锚点、可用限制 | 保留多种物理实现，不伪装成均支持 SQL。 |

### DA03.7 业务语义血缘

边界：实体间“客户拥有订单”等关系仍归 DA03.3，不作为派生血缘。

实现位置：`src/dataagent_data/semantics/lineage.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.7.1 指标依赖提取：识别派生指标对基础指标、维度和时间口径的引用 | `extract_metric_dependencies` | MetricDraft/SemanticRef、语义符号表与定义版本 | semantic_dependency 边；基础指标、维度、时间口径及缺口 | 这里表达定义依赖，实际表列处理血缘归 DA02.7。 |
| DA03.7.2 规则依赖提取：识别指标、规则对其他规则及例外定义的引用 | `extract_rule_dependencies` | 规则定义、被引用指标/规则/例外及版本 | 规则依赖边；引用类型、原文锚点、未解析引用 | 定义间引用与本次求值命中路径分开。 |
| DA03.7.3 语义血缘维护：按定义版本保存和更新依赖 | `upsert_semantic_lineage` | 语义依赖边、定义版本、expected_revision | LineageRef；语义依赖版本及保存回执 | 不能将实体关联关系直接当作派生血缘。 |

### DA03.8 历史口径解析

边界：历史计算还需对应数据和程序版本。

实现位置：`src/dataagent_data/semantics/history.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.8.1 业务生效时间解析 | `parse_business_effective_time` | 条款或定义材料、适用区域、时间解析上下文 | 有效时间候选；起止、追溯条件、依据与歧义 | 生效时间与系统保存时间分开。 |
| DA03.8.2 指定时点语义版本解析 | `resolve_semantic_as_of` | 语义标识、业务时点、可选记录时点、作用域 | SemanticRef 或未决结果；匹配版本、来源及冲突 | 同时匹配多个版本时返回冲突，不任意挑一个。 |

### DA03.9 语义导入与冷启动

边界：产出均为草案，确认后按 DA12.5 生效；导入保留来源和无法转换的部分。

实现位置：`src/dataagent_data/semantics/bootstrap.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.9.1 外部语义层导入：读取 dbt、MetricFlow、Cube、BI 数据集等已有定义 | `import_external_semantics` | dbt/MetricFlow/Cube/BI 等导出物、映射配置、源版本 | 语义草案集合；来源标识映射、无法转换项与转换损失 | 保留原定义引用，不声称不同语义系统完全等价。 |
| DA03.9.2 历史口径挖掘：从历史 SQL、报表、Excel 模板和公式中反推指标、过滤与 Join | `mine_historical_definitions` | 历史 SQL/报表/Excel 公式引用、相关 schema 与范围 | 指标、过滤和 Join 草案；频次、依据与冲突 | 历史做法是证据，不能直接当作权威业务定义。 |
| DA03.9.3 语义草案生成：结合结构、画像、文档和领域模板生成实体、指标与关系草案 | `generate_semantic_drafts` | 结构、画像、文档单元、领域模板和任务约束 | 实体/指标/关系草案集合；待绑定项和依据 | 生成只产生候选，确认和发布走对应机制。 |
| DA03.9.4 待确认项排序：按影响范围和不确定性列出需要业务确认的定义 | `rank_semantic_questions` | 语义草案、歧义项、使用频率与影响范围 | 待确认清单；排序、影响说明与候选问题 | 不通过低优先级掩盖影响本次验收的未决问题。 |

### DA03.10 语义冲突识别

边界：不自动裁决认证口径；结论以作用域或新版本表达。

实现位置：`src/dataagent_data/semantics/conflicts.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.10.1 定义冲突检测：同名异义、异名同义、口径重叠 | `detect_semantic_conflicts` | 语义版本集合、作用域、时间重叠与等价判据 | 冲突列表；同名异义/异名同义/口径重叠及依据 | 识别候选冲突，不自动裁决认证定义。 |
| DA03.10.2 冲突说明与协调方案：并存、按作用域区分或合并 | `propose_semantic_resolution` | 冲突列表、业务约束、可选范围与版本策略 | 协调方案；并存/分域/合并候选、影响与待裁决项 | 有权角色裁决后再修订，原定义保留。 |

### DA03.11 动作语义 〔FDE〕

边界：描述业务含义；具体工具、接口绑定与执行要求归 DA15.2，实际执行归 DA07。

实现位置：`src/dataagent_data/semantics/actions.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.11.1 动作类型定义（Action Type） | `define_action_types` | 业务对象、动作需求、来源材料 | ActionSemanticDraft；动作含义、对象与业务目的 | 不绑定具体工具，执行契约归 DA15。 |
| DA03.11.2 业务参数定义 | `define_action_business_parameters` | 动作语义引用、参数业务说明、单位/范围 | 业务参数定义草案；对象类型、单位和解释 | 接口参数名、传输 schema 与实现约束由 DA15 绑定。 |
| DA03.11.3 业务前后状态定义 | `define_action_business_states` | 动作语义引用、业务前提、预期状态、例外 | 业务前后状态草案；可观测指标与未决条件 | 描述业务要求，不执行运行时前置检查。 |
| DA03.11.4 业务影响描述 | `describe_action_business_impact` | 动作语义、受影响对象、恢复条件与来源 | 业务影响草案；对象范围、可逆条件、未知项 | 是语义描述，单次影响面评估归 DA12.11。 |

### DA03.12 权属模型 〔FDE〕

边界：不做运行时鉴权，鉴权归 DA16。

实现位置：`src/dataagent_data/semantics/authority.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.12.1 读/提议/执行三档 | `define_action_authority_tiers` | 角色、动作语义、正式授权要求 | 权限模型草案；读/提议/执行权限关系及正式依据 | 与 DA15 的动作入口分类复用同一档位词表，不重复定义含义。 |
| DA03.12.2 委托关系 | `define_delegation_relationships` | 委托主体、代理主体、动作范围、期限及正式依据 | DelegationDraft；可代理关系和限制 | 只定义业务委托关系，令牌或身份签发归授权层。 |
| DA03.12.3 审批策略 | `define_approval_policy` | 动作/角色、审批条件、分权要求、正式制度 | ApprovalPolicyDraft；审批主体、条件和例外 | 默认草案，正式免审或放权须有权主体确定。 |

### DA03.13 证据模型 〔FDE〕

边界：候选判据可由 Agent 起草；正式验收或授权相关判据须由有权主体确定。证据充分不等于获得执行授权。

实现位置：`src/dataagent_data/semantics/evidence.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.13.1 证据类型定义 | `define_evidence_types` | 结论类型、业务材料类型、可信来源要求 | EvidenceTypeDraft；证据类别、来源及关联要求 | 定义什么算证据，不保存全部原文。 |
| DA03.13.2 充分性判据定义〔定〕 | `define_evidence_sufficiency` | 结论类型、证据类型、业务验收要求、决策主体 | 充分性判据草案或已确认版本；阈值、依据与确认引用 | 正式判据不得由 Agent 自行放宽；证据不替代授权。 |
| DA03.13.3 证据与结论绑定 | `bind_conclusion_evidence` | 结论引用、实际 EvidenceRef、判据版本 | 结论—证据关联；缺失项与待验证状态 | 绑定引用不宣称证据真实或结论正确，检查归 DA11。 |

### DA03.14 状态与生命周期

边界：不复用内核的请求/任务状态语义。

实现位置：`src/dataagent_data/semantics/lifecycle.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.14.1 业务对象状态定义 | `define_business_states` | 实体引用、状态词表、业务生命周期描述 | StateModelDraft；业务状态及约束 | 复用 DA03.1.3 词表，避免再维护一套状态名称。 |
| DA03.14.2 状态迁移与回退 | `define_state_transitions` | StateModelDraft、事件、迁移条件、回退要求 | 状态迁移草案；允许边、条件与不可逆标记 | 定义迁移，不执行对象状态变更。 |
| DA03.14.3 与执行状态机的映射 | `map_business_to_execution_states` | 业务状态模型、通用执行阶段描述、观测依据 | MappingDraft；业务状态到执行观测的关联、非等价项 | 是观察关联，不将业务状态替换为某平台任务状态；平台绑定后续单独适配。 |

### DA03.15 可判定性评估

边界：可在探索或试算后重评，不限定先拆解还是先评估；不能自动缩小覆盖范围，也不能把需看附件等同于必须人工。

实现位置：`src/dataagent_data/semantics/decidability.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.15.1 自动判断能力评估 | `assess_automatic_decidability` | 业务要求、可用数据、工具/方法描述、目标质量 | DecidabilityAssessment；可自动/待补证/需人工、依据和依赖 | 可在试算后重评，不限表达式编译。 |
| DA03.15.2 补证与人工需求识别 | `identify_evidence_or_human_gaps` | 要求、当前评估、缺失材料与可用处理方法 | GapPlan；补数/附件分析/人工裁量需求及原因 | 看附件不必然需要人工；补证路线不是已完成判定。 |
| DA03.15.3 自动处理范围标注 | `mark_automation_coverage` | 要求全集、逐项评估、允许处理范围 | CoverageMap；已覆盖、待补证、人工项及分母 | 保留未自动覆盖项，不让规则从业务验收中消失。 |
| DA03.15.4 判定缓存与依赖失效 | `resolve_decidability_cache` | 既有评估、当前原文/映射/语义/工具/模型版本 | 缓存命中或失效结论；变化依赖、重评项与版本引用 | 缓存依赖不完整则保守失效，不只比较原文 digest。 |

### DA03.16 适用范围建模

边界：与 DA03.15 的可自动判断能力分开；适用性可独立判断或嵌入程序。UNKNOWN 应补证或转人工，不能按满足或不适用直接跳过。

实现位置：`src/dataagent_data/semantics/applicability.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA03.16.1 适用范围表达：本条管哪些单据与场景 | `define_rule_applicability` | 规则或方法、对象类型、场景与制度依据 | ApplicabilityDraft；范围表达、依赖及未知项 | 定义适用范围，实际判断可独立或嵌入执行程序。 |
| DA03.16.2 生效前提表达：前置条件及其组合 | `define_rule_preconditions` | 规则引用、生效前提、组合逻辑与来源 | 前置条件草案；逻辑组合、依赖与来源 | 使用可保持 UNKNOWN 的逻辑，避免把缺失值当作 false。 |
| DA03.16.3 前置引用与去重：同义前置只留一条 | `normalize_precondition_references` | 前置条件集合、语义版本、等价候选依据 | 规范化前置引用；去重候选与冲突 | 未经证明的同义不合并，保留原始条件引用。 |
| DA03.16.4 适用性未知处置 | `resolve_unknown_applicability` | 适用性求值记录、缺失证据、既定处置策略 | 补证/等待/人工处理请求；待判定项与原因 | UNKNOWN 不转满足或不适用，不能直接跳过本单规则。 |

# DA04｜任务轨迹与记忆：输入输出与代码划分 v0.1

定位：保存真实执行记录、任务修订与可复用资产，并从轨迹提炼有适用条件的经验。

**模块输入**：任务事件与调用回执、纠正、程序和模型内容、验证记录、上下文版本与获准修订。

**模块输出**：轨迹/记忆/程序资产引用、任务上下文修订、经验候选和晋升记录、交付版本与归属。

**模块边界**：存储、提炼与检索分开；检索归 DA05。候选不自动成为认证经验，验证复用 DA11，审计保留策略归 DA12，子任务装配归 DA17。

本文件与 [共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/memory/`。共 7 个能力组、24 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
|-|-|-|-|-|
| DA04.1 任务轨迹存储 | 保存任务中的问题、计划、工具调用、SQL、结果引用和用户纠正。 | 任务事件 | 可追溯执行记录 | `traces.py` |
| DA04.2 任务经验提炼 | 从轨迹提炼有效查询、方法、组件组合、程序、Skill 修订及其适用条件。 | 多次成功轨迹 | 经验与模板候选 | `distillation.py` |
| DA04.3 记忆存储 | 按用户、任务或企业范围保存已选择的经验和历史结论。 | 经验 | 分作用域记忆库 | `memories.py` |
| DA04.4 程序与分析资产存储 | 保存查询、程序、模型、报表、组件组合及 Skill/Preset 修订，关联适用条件、验证记录和依赖版本。 | 查询/模型/报表 | 可复用资产 + 来源关联 | `artifacts.py` |
| DA04.5 任务上下文 | 维护本次任务选用的数据、语义、程序与经验版本，以及假设、权限范围和修订状态。 | 任务与修订 | 一致的任务上下文 | `contexts.py` |
| DA04.6 经验验证与晋升 | 决定哪些候选经验可以进入哪个范围。 | 候选经验 | 验证结果与生效作用域 | `promotion.py` |
| DA04.7 交付物记忆 〔FDE〕 | 保存交付物的版本与归属。 | 交付物 | 版本与归属记录 | `deliveries.py` |

## 原子能力契约

### DA04.1 任务轨迹存储

边界：可复用平台轨迹机制，保存实际执行记录和结果引用；不保证任意轨迹均能重放，不将完整轨迹当作可信经验。审计保留策略归 DA12.10。

实现位置：`src/dataagent_data/memory/traces.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA04.1.1 任务事件记录 | `append_task_event` | task_id、event_id、事件类型、时间、前后修订引用 | TraceEventRef；事件序号与持久化回执 | 按 event_id 去重；事件存储不能替代任务调度状态机。 |
| DA04.1.2 查询/工具调用记录 | `append_invocation_record` | invocation_id、工具/实现版本、实参引用、结果/错误、时间 | TraceEventRef；输入输出引用、实际状态与耗时 | 默认存受控引用并脱敏，不将模型计划当成实际执行。 |
| DA04.1.3 用户纠正记录 | `append_user_correction` | 用户反馈、目标对象/字段、旧新值或解释、作用域 | CorrectionRef；原文、变更目标、来源事件与修订关联 | 原始纠正与正式修订分开保存，不默认改全企业口径。 |

### DA04.2 任务经验提炼

边界：产出候选经验或修订；不自动升级为业务规则。存储归 DA04.4，效果验证归 DA11。

实现位置：`src/dataagent_data/memory/distillation.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA04.2.1 成功查询提炼 | `distill_successful_queries` | 轨迹切片、查询程序、验证记录、问题与环境约束 | MemoryCandidate；查询模板、适用/失效条件和来源 | 执行成功不等于正确；无验证时保留未验证状态。 |
| DA04.2.2 分析方法提炼 | `distill_analysis_methods` | 分析轨迹、方法参数、效果报告、适用场景 | 方法经验候选；步骤指导、依赖、正反例与限制 | 保存方法与适用条件，不将一次相关性结论沉淀为因果规则。 |
| DA04.2.3 失败经验提炼 | `distill_failure_lessons` | 失败轨迹、错误归因、修复与复测记录 | 失败经验候选；触发条件、避坑建议和反证 | 区分暂时故障、方法不适用和业务定义问题。 |
| DA04.2.4 组合与 Skill 修订提炼 | `distill_component_combinations` | 有效轨迹、组件版本、代码/Skill 修订、验证记录 | 组合或 Skill 修订候选；可替换点、适用条件及来源 | 提炼候选；组装交付归 DA18，验证归 DA11。 |

### DA04.3 记忆存储

边界：管理存储与作用域；如何找回交给 DA05。

实现位置：`src/dataagent_data/memory/memories.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA04.3.1 个人记忆存储 | `save_personal_memory` | MemoryCandidate、user_id、适用条件、expected_revision | MemoryRef；个人作用域、版本和保存回执 | 个人纠正不自动覆盖企业认证语义。 |
| DA04.3.2 任务共享记忆存储 | `save_task_memory` | 经验或中间结论、task_id、task_revision、共享范围 | MemoryRef；任务作用域版本与状态 | 子任务读取受权限约束，未验证结论要保留标记。 |
| DA04.3.3 企业经验存储 | `save_enterprise_memory` | 记忆候选、企业作用域、验证记录、获准生效依据 | MemoryRef；企业范围版本和状态 | 无晋升或发布依据时只能保存候选，不自动认证。 |

### DA04.4 程序与分析资产存储

边界：复用 MintHub 或现有资产存储机制；保留可执行内容或有效引用，依赖关系复用已有血缘。

实现位置：`src/dataagent_data/memory/artifacts.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA04.4.1 查询/代码资产保存 | `save_query_code_asset` | SQL/程序内容或可靠引用、语言、依赖、适用条件、验证引用 | ArtifactRef；内容 digest、实现版本、依赖清单 | 保留可执行内容或可解析引用，不把临时路径当长期资产。 |
| DA04.4.2 模型资产保存 | `save_model_asset` | 模型内容引用、参数、运行依赖、数据/语义版本、评测引用 | ArtifactRef；模型版本、配置、来源与限制 | 模型二进制与 prompt/参数版本分别可定位。 |
| DA04.4.3 模板与组合资产保存 | `save_template_combination_asset` | 报表模板或组件组合/Skill/Preset 修订、依赖及适用范围 | ArtifactRef；类型、内容、可替换点与验证关联 | 保存不等于发布包已安装可用；发布格式后续适配。 |
| DA04.4.4 产物来源关联：记录结果、模型和报表使用的数据、语义、代码与参数 | `link_artifact_provenance` | 产物引用、实际数据/语义/程序/参数引用、run_id | 产物来源边引用；已知依赖与缺口 | 复用血缘标识，区分实际使用与计划依赖。 |

### DA04.5 任务上下文

边界：任务级状态由本能力维护；业务环境默认配置归 DA17.2，子任务上下文装配归 DA17.3。修订后标记受影响结果并重新验证。

实现位置：`src/dataagent_data/memory/contexts.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA04.5.1 任务上下文创建：固定数据与语义版本、已选经验和权限范围 | `create_task_context` | task_id、选定版本引用、已选经验、假设、权限引用 | TaskContextRef；任务修订、绑定与未固定项 | 不强求所有数据已有快照；未固定处明确标注。 |
| DA04.5.2 子任务上下文引用维护 | `bind_subtask_context` | 子任务标识、父 TaskContextRef、选用修订、绑定说明 | 子任务—任务修订引用；关联回执 | 实际裁剪装配归 DA17.3，不另建独立口径副本。 |
| DA04.5.3 任务修订同步：口径或数据变化时生成新修订，并使旧结果失效 | `revise_task_context` | TaskContextRef、expected_revision、获准变更、影响引用 | 新 TaskContextRef；变更差异、受影响结果与复验请求 | 旧结果标记需重验，不把一切下游永久失效；权限不得自行放宽。 |

### DA04.6 经验验证与晋升

边界：晋升到团队或企业范围须有验证记录，验证复用 DA11.4；与认证语义冲突时不覆盖，转 DA03.10 或 DA12.3 处理。

实现位置：`src/dataagent_data/memory/promotion.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA04.6.1 候选经验验证：在相关样本上回放比较 | `validate_memory_candidate` | 候选经验、相关开发/回归样本、固定依赖、比较基线 | ValidationReportRef；适用范围、效果及失败样例 | 调用 DA11，候选本身不能给自己出具独立验收结论。 |
| DA04.6.2 作用域晋升：个人、团队、企业逐级生效 | `promote_memory_scope` | MemoryRef、目标作用域、验证记录、授权依据、expected_revision | 记忆新版本；目标范围、状态与晋升回执 | 范围扩大按策略执行；不是必须逐级人工确认。 |
| DA04.6.3 冲突与污染检查：与认证语义、已有经验及其他用户纠正比对 | `check_memory_conflicts` | 候选记忆、认证语义、已有经验、用户纠正及反例 | 冲突/污染报告；冲突来源、范围与建议 | 不能以记忆优先级静默盖过正式语义。 |
| DA04.6.4 经验失效与淘汰：数据或语义变更、出现反例或长期未用时降级 | `retire_or_demote_memory` | MemoryRef、变化依赖或反例、降级/淘汰策略、expected_revision | 新状态版本；原因、受影响引用和回执 | 低使用率可触发复核，不能单凭未用断言内容错误。 |

### DA04.7 交付物记忆 〔FDE〕

边界：记录交付物与业务环境的关联；不替代 DA04.5 的任务状态或 DA17 的环境配置。

实现位置：`src/dataagent_data/memory/deliveries.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA04.7.1 契约与 Runbook 版本 | `record_delivery_versions` | 交付标识、契约/Runbook/组合包 ArtifactRef、expected_revision | DeliveryRef；版本清单与记录回执 | 复用 DA04.4 资产内容，不复制维护另一份版本实体。 |
| DA04.7.2 交接材料归属 | `record_handover_ownership` | DeliveryRef、接收主体、材料引用、交接依据、expected_revision | 交接归属记录；责任与材料版本 | 记录交接不等于自动授予数据或运行权限。 |
| DA04.7.3 业务环境范围记忆 | `record_delivery_environment_scope` | DeliveryRef、业务环境标识、适用/排除条件、版本约束 | 适用范围记录；环境引用、边界与变更回执 | 引用 DA17 环境配置，不保存其完整副本。 |

# DA13｜数据建模与物化（扩展）：输入输出与代码划分 v0.1

定位：将已定义的业务语义落实为可维护的物理数据模型与物化数据。

**模块输入**：业务需求、语义与源结构版本、目标后端、转换约束、获准变更计划和历史区间。

**模块输出**：模型/数据契约草案、转换与依赖、物化/回填回执、校验报告和结果引用。

**模块边界**：该模块按需建设。生成复用 DA06/DA08.6，执行复用 DA07，验证复用 DA11；不在数据层另建计算引擎。

本文件与 [共享契约](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/modeling/`。共 3 个能力组、7 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
|-|-|-|-|-|
| DA13.1 目标模型设计 | 根据业务语义和来源结构设计目标表及其契约。 | 分析需求 | 维度/事实模型与数据契约 | `models.py` |
| DA13.2 转换构建 | 生成从来源到目标表的转换 SQL 或程序，并维护依赖顺序。 | 模型 | 转换逻辑与依赖 | `transformations.py` |
| DA13.3 物化与回填 | 执行转换并写入目标库，按区间补算历史数据。 | 转换 | 物化结果与校验报告 | `materialization.py` |

## 原子能力契约

### DA13.1 目标模型设计

边界：模型与 DA03 的实体、指标对应；设计结果是草案，确认后生效。

实现位置：`src/dataagent_data/modeling/models.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA13.1.1 主题/维度模型设计 | `design_analytical_model` | 业务需求、SemanticRef、源 SchemaRef、数据规模与查询模式 | ModelDraft；事实/维度/主题设计、粒度与映射依据 | 设计草案，不自行改变业务口径或创建物理表。 |
| DA13.1.2 数据契约定义：字段、约束、粒度、新鲜度承诺 | `define_data_contract` | ModelDraft、字段/约束/粒度/新鲜度要求、责任人 | DataContractDraft；校验条款、生效范围与来源 | 数据契约与 DA15 动作调用契约不同；正式承诺按策略确认。 |

### DA13.2 转换构建

边界：SQL 生成复用 DA06，程序生成复用 DA08.6；不另建一套编译能力。

实现位置：`src/dataagent_data/modeling/transformations.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA13.2.1 转换逻辑生成 | `generate_transformations` | 模型草案、来源映射、目标后端、转换要求 | TransformationDraft；SQL/程序引用、依赖与未支持项 | SQL 生成复用 DA06，通用程序生成复用 DA08.6。 |
| DA13.2.2 转换依赖维护 | `maintain_transform_dependencies` | TransformationDraft 列表、输入输出版本、expected_revision | 转换依赖图版本；拓扑关系、环路和缺口 | 依赖维护不执行调度；数据血缘观测仍归 DA02.7。 |

### DA13.3 物化与回填

边界：执行前须有 DA12.7 变更计划，写入走 DA07.4；校验复用 DA11.1 与 DA11.2。

实现位置：`src/dataagent_data/modeling/materialization.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
|-|-|-|-|-|
| DA13.3.1 增量物化 | `materialize_increment` | 获准变更计划、转换版本、目标引用、已提交水位、幂等键 | MaterializationReceipt；写入分区/行数、结果引用、候选水位 | 经 DA07 执行写入；提交与校验成功后推进水位，未知副作用先对账。 |
| DA13.3.2 历史回填 | `backfill_history` | 获准变更计划、转换版本、历史区间、快照与目标引用、幂等键 | 回填作业引用；分区逐项状态、结果与部分失败 | 区间与源历史必须可用；不将重新取最新数据称作历史重现。 |
| DA13.3.3 物化结果校验 | `validate_materialization` | 物化回执、DataContractRef、对照数据/语义版本、验证范围 | ValidationReportRef；约束/对账结果、范围及未验证项 | 调用 DA11，执行返回成功不等于物化业务正确。 |

# 共享输入输出契约 v0.1

本文件定义原子能力之间交换什么，以及实现应保持哪些含义。采用可序列化对象和资源引用作为边界；Python、HTTP、MCP 可以承载同一业务契约。这里的命名与结构是 DataAgent 自拟草案，尚未对应任何平台 iface，也不假设已有组件已经实现。

## 1. 调用和返回

所有能力采用同一个逻辑形式：

```text
invoke(operation, input, CallContext) -> CapabilityResult<T>
```

| 对象 | 字段草案 | 含义 |
|-|-|-|
| `CallContext` | `request_id, task_ref?, scope_ref, authorization_ref, deadline?, budget?, expected_revision?, idempotency_key?` | 请求标识、任务关联、作用域和实际授权引用；预算、超时及写入并发控制按能力需要提供 |
| `CapabilityResult<T>` | `status, data?, issues[], execution_ref?, provenance[], completeness?, continuation?` | 业务结果与运行状态分开，携带缺口、实际执行依据及后续取数方式 |
| `Issue` | `code, message, severity, target?, source_anchor?, retryable, suggested_action?` | 错误或歧义可定位，调用方可决定补数、换实现、重规划或询问 |
| `ExecutionRef` | `invocation_id, implementation_ref, input_versions[], started_at, finished_at?, receipt_ref?` | 指向实际发生的调用；计划不作为已执行记录 |
| `Continuation` | `cursor?, job_ref?, subscription_ref?, resume_condition?` | 分页、异步作业或持续订阅的后续入口；不是将完整长任务塞进单次响应 |

`status` 暂定为 `ok / partial / needs_input / pending / failed`：`ok` 表示当前声明范围的能力执行成功，不意味着业务结论正确；`partial` 必须列缺口；`needs_input` 可以携带候选和澄清项；`pending` 必须有作业或等待引用。不能将空结果、权限拒绝、解析失败混成同一种 `[]`。

错误码先统一：`unauthorized, unsupported, invalid_input, version_conflict, not_found, source_changed, rate_limited, timeout, execution_unknown, dependency_unavailable`。对具有副作用的调用，`timeout` 或 `execution_unknown` 不允许默认重放；通过回执和幂等键查询、对账后决定下一步。

## 2. 引用、版本与内容

| 对象 | 最小信息 | 使用约定 |
|-|-|-|
| `AssetRef` | `id, kind, scope_ref, revision, resolver, locator, digest?, media_type?` | 长期对象引用；`resolver/locator` 是受权限保护的解析描述，不是明文凭据或永久公开下载链接 |
| `ResourceRef` | `source_ref, native_id, kind, source_version?, metadata` | 源端资源身份；源端没有版本时明确缺失，不给它编造一个可重现版本 |
| `FileRef` | `AssetRef + filename?, size?, content_digest` | 已进入受控存储的原件；不依赖 Agent 进程的临时文件路径 |
| `ConnectionRef` | `id, source_type, endpoint_ref, credential_binding_ref?, capabilities_ref?, expires_at?` | 可解析的连接引用；进程内 socket/driver 对象由适配器管理，不跨 API 序列化 |
| `CredentialRef / CredentialBindingRef` | `secret_provider_ref, binding_id, allowed_target, expires_at?, revision` | 只传代理引用，日志、模型上下文及普通输出均不携带明文密钥 |
| `SchemaRef` | `AssetRef + fields[], keys[], native_schema_ref?, inference_basis?` | 字段用稳定 ID 与源路径；区分源端声明、样本推断与人工确认 |
| `SourceAnchor` | `source_ref, source_revision, selector, extraction_ref?` | selector 为 Excel sheet/cell、PDF page/bbox、JSON Pointer、记录键或文档字符区间；必须可回到相同源版本 |
| `SnapshotRef` | `asset_ref 或 source_ref + native_snapshot_token, captured_at, readable_range, retention?, replayability` | 真实副本或有效 as-of 访问机制；digest、时间戳本身不能保证历史重读 |

`revision` 是 DataAgent 资产修订，`source_version` 是源端版本，`digest` 校验内容，`effective_time` 是业务生效时间，四者分别表达。源端资源只能读最新时，其引用可被管理，但不能据此声明其内容不可变。所有写入类原子能力返回实际保存版本及回执；支持 `expected_revision` 做乐观并发检查。

对引用的按 ID 读取、按 revision 解析和容器分页由 Repository/Source 端口提供，是完成存储契约所必需的访问方法。它们不另增 DA 编号，也不承担语义召回或相关性排序；面向问题的检索仍由 DA05 提供。输入若收到版本化引用，实现必须校验实际读到的版本，不能用当前内容替代历史内容。

## 3. 结构化和非结构化数据

| 对象 | 最小信息 | 边界 |
|-|-|-|
| `WorkbookRef` | 原文件引用、sheet 列表、单元格/合并/公式数据解析引用 | 区分公式表达式、缓存值与经过重算的值 |
| `TableRegion` | `source_anchor, cell_range 或 bbox, layout_ref, confidence?, alternatives?` | 表块候选，尚未必形成稳定字段和记录 |
| `TableRef` | `AssetRef, schema_ref, data_ref, row_identity?, source_map_ref, transform_ref?` | 可读取的表；来源映射与数据分存，避免将全量单元格血缘塞进响应 |
| `DataBatchRef` | `asset_ref, schema_ref?, source_ref, cursor?, row_count, completeness` | 有限的一批记录；小批可内联，大批返回引用，调用方采用相同 schema 解析 |
| `DocumentRef` | `AssetRef, content_type, blocks_ref, page_refs?, original_ref` | 文字、图像、嵌套文档均保留原内容类型，不强制转表 |
| `DocumentUnitRef` | `AssetRef, parent_document_ref, unit_type, content_ref, anchors[], context_refs[]` | 章节/条款/表格单元，拆分不丢父章节和跨块上下文 |
| `ExtractedRecordRef` | `AssetRef, target_schema_ref, values_ref, field_evidence_ref, issues[]` | 每个字段可关联多个原文锚点；缺失、冲突、低置信结果分别表达 |
| `ProfileRef` | `AssetRef, dataset_ref, field_stats_ref, method, sample_spec?, observed_at` | 精确统计和估计分开，保存采样范围、预算耗尽和访问限制 |
| `ChangeBatchRef` | `AssetRef, events_ref, source_partition, start_offset, end_offset, watermark_candidate` | 事件保留主键、操作类型、源版本和时间；水位候选不代表已提交 |
| `SubscriptionRef` | `subscription_id, source_ref, partitions, start_offsets, lease?, poll_ref, cancel_ref` | 生命周期由源适配器管理；下一批数据和取消有明确入口 |

`completeness` 至少表达：`extent（complete_in_declared_scope / page / sampled / truncated / unknown）`、声明的读取范围、实际行/页数、未完成原因、源端快照一致性。`complete_in_declared_scope` 也不等于企业全量数据。例如当前页完整、总分页未知，不得写为整个数据集完整。

解析和变换不覆盖原件。输出新数据引用及可追踪的来源映射；聚合、转置和嵌套展开可以有多对多来源关系，不能假定每个目标单元格只来自一个原始单元格。

## 4. 语义、候选和关系

| 对象 | 最小信息 | 边界 |
|-|-|-|
| `SemanticDraft` | `draft_id, kind, definition, scope_ref, sources[], unresolved[], confidence?` | 模型生成/推断默认草案；`EntityDraft / MetricDraft / RuleDraft / RelationshipDraft` 等是它的特化 |
| `SemanticRef` | `AssetRef, semantic_kind, definition_ref, status, valid_time?, recorded_at, sources[]` | 按版本保存的定义；发布状态由治理控制，保存版本不等于认证口径 |
| `MappingDraft / MappingRef` | `semantic_ref, physical_refs[], path_or_binding, transform_ref?, valid_time?, sources[]` | 语义到表列、API、函数、文档的实现绑定，保留来源与未解析符号 |
| `Assessment` | `target_ref, verdict, basis_refs[], dependency_refs[], unknowns[], next_actions[]` | 可判定性、适用性、冲突、兼容检查等共用模式；判定词表由各能力定义 |
| `EvidenceRef` | `asset_ref, evidence_type, source_anchors[], obtained_by, verification_ref?` | 原文、计算结果或执行回执等实际依据；引用存在不自动证明可靠性 |
| `LineageEdge` | `from_ref, to_ref, edge_kind, basis, definition_or_run_ref, coverage` | `basis=declared / inferred / observed` 区分声明、静态推断、实际观测 |

关系采用共享标识，但不同含义分开保存和查询：

| 关系种类 | 例子 | 归属 |
|-|-|-|
| 数据处理依赖 `data_dependency` | `orders.amount -> daily_sales.total` | DA02.7；描述表列及变换 |
| 业务定义依赖 `semantic_dependency` | “净收入”引用“含税收入”“税额” | DA03.7；描述定义派生 |
| 业务对象关系 `entity_relationship` | “客户拥有订单” | DA03.3；可带时态及基数 |
| 语义实现映射 `semantic_mapping` | “净收入”绑定某视图或接口结果 | DA03.6；连接语义与物理来源 |
| 产物来源 `artifact_provenance` | 本次报告使用哪些数据/口径/程序 | DA04.4.4；实际运行依据关联 |

v0.1 可在同一个关系存储后端中按类型分区，业务逻辑不得混用边类型；不要求先搭建图数据库。依赖边到具体资产版本，避免“对象名字没变”时误判上下游仍然有效。

草案构造、版本保存、正式发布是三个不同动作。多数 `define_*` 只返回草案；`save_semantic_objects` 负责持久化已允许保存的版本；正式发布复用治理机制。`confidence` 仅是带方法说明的估计，不充当自动认证门槛。

## 5. 轨迹、记忆与任务修订

| 对象 | 最小信息 | 边界 |
|-|-|-|
| `TraceEventRef / CorrectionRef` | `event_id, task_ref, event_type, timestamp, actor_ref, payload_ref, source_revision?` | 保存实际事件，敏感参数受控保存；模型建议与已执行动作分开 |
| `MemoryCandidate / MemoryRef` | `kind, content_ref, scope_ref, applicability, dependencies[], validation_refs[], status, source_traces[]` | 原始轨迹提炼后仍是候选；共享范围与可信状态是两个维度 |
| `ArtifactRef` | `AssetRef, artifact_kind, content_ref, dependencies[], runtime_requirements?, validation_refs[], applicability` | 查询、程序、模型、模板及组合配置的通用保存对象，不等于安装包运行句柄 |
| `TaskContextRef` | `task_id, revision, selected_refs[], assumptions[], policy_refs[], parent_revision?, unresolved[]` | 本次任务选用版本与假设，允许有显式未固定项；不是客户环境全局配置 |
| `ValidationReportRef` | `AssetRef, criteria_ref, sample_set_ref, dependency_versions[], results_ref, limits` | 指向 DA11 的实际验证报告，记录开发/回归/验收样本角色 |
| `DeliveryRef` | `delivery_id, artifact_refs[], environment_refs[], ownership_ref, revision` | 交付清单与归属，正文和代码复用资产存储 |

经验的 `status` 暂用 `candidate / validated / active / deprecated`，与用户、任务、团队、企业等 `scope` 分开。是否晋升、何时生效受验证和既有授权策略控制；不固化为每一步必有人工签字。

## 6. 建模扩展对象

`ModelDraft` 保存事实/维度/主题模型、粒度和语义引用；`DataContractDraft/Ref` 保存字段、约束、时效要求；`TransformationDraft` 保存 SQL/程序引用、输入输出和依赖；`MaterializationReceipt` 保存实际写入目标、分区、行数、版本、作业、幂等与部分失败。三类草案不意味着物理数据已经创建，物化回执也不意味着业务验证通过。

## 7. 典型调用示例

下面只示意关键字段；字段名在实现前可以调整。

```json
{
  "operation": "extract_irregular_excel",
  "input": {
    "file_ref": {"id": "file:expense", "revision": "sha256:abc"},
    "sheets": ["报销明细"],
    "recovery_policy": "preserve_ambiguity"
  },
  "context": {
    "request_id": "req:parse-01",
    "task_ref": "task:a@r2",
    "scope_ref": "tenant:demo/project:expenses",
    "authorization_ref": "policy-binding:read-files"
  }
}
```

```json
{
  "status": "partial",
  "data": {
    "tables": [{"id": "table:expense-detail", "revision": "r1"}],
    "source_map_ref": "mapping:expense-cells@r1"
  },
  "issues": [{
    "code": "ambiguous_header",
    "message": "第 2 个表块有两个可能的表头，保留为候选",
    "severity": "warning",
    "target": "region:2",
    "retryable": false,
    "suggested_action": "补充表头提示或选择替代恢复实现"
  }],
  "provenance": [{"source_ref": "file:expense@sha256:abc"}],
  "completeness": {"extent": "truncated", "declared_scope": "报销明细全部表块", "reason": "region:2 未恢复"}
}
```

调用方可修改提示或更换实现后重试第 2 个表块；无需重新连接、重复解析全部文件，也不能把已经恢复的一张表等同于完整业务交付。

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
|-|-|-|
| 稳定 ID 和调用注册 | `registry/catalog.py` | `DA02.2.1 -> dataagent_data.preparation.structure:recover_headers` |
| 业务参数类型 | `preparation/structure.py` 中 `RecoverHeadersInput/Output` | 定义表块、策略、结果表头及歧义，不把整个模块写成万能字典 |
| 共享对象 | `contracts/data.py` | 复用 `TableRegion / TableRef / SourceAnchor` |
| 能力处理函数 | `preparation/structure.py` | 验证输入、选择已装配实现、规范返回与来源记录 |
| 算法实现 | 初期同文件私有实现；复杂后 `preparation/header_recovery/` | 规则法与模型法可替换，重型依赖按需加载 |
| 发行描述 | `component-specs/preparation.yaml` | 声明入口、契约版本、实现与依赖；实际包粒度另决定 |
| 验证 | `tests/preparation/` 与 `tests/contracts/` | 多行/重名表头、歧义不丢失、原值及锚点正确 |

能力组不强制一个文件永久容纳全部实现；原子能力不要求独立进程。对于 `DA01.4.2` 不规则 Excel 等组合能力，handler 可以显式调用表块检测、表头恢复等已注册原子能力。组合必须保留每步实现版本和结果引用，不复制一份底层算法。

完整的 **编号 → 调用名 → 源码文件 → 入口** 映射见 [atomic-capability-catalog.json](https://modelbest.feishu.cn/docx/NXe7dMEEQoJ5wqxcPsRczoebn4d)。160 项编号均有明确入口，目录树可以直接反查。

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
|-|-|-|
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
|-|-|-|-|
| 每项原子一个独立项目/包 | 替换与分发直接 | 160 项初期会产生大量构建、版本和重复契约维护 | 仅在已有独立部署或合作方交付需求时拆 |
| 单个万能数据服务 | 起步文件少 | 边界、依赖和替换点不清楚，难做组合 | 保持模块和原子入口清晰 |
| 一个工作区，按模块组织，可选适配器，可逐步拆包 | 共享类型与测试，同时保留替换和发布空间 | 需要约束依赖方向和注册规范 | 推荐作为 v0.1 |

# 组合示例与建设切片 v0.1

这些示例说明契约如何组合，不规定所有业务的唯一执行顺序。Agent 可以从已有表、某个值、业务规则、文档单元或历史经验进入；验证失败后补数据、换组件、修程序或澄清，再继续当前子任务。数据层提供可复用对象和能力，不用固定链路代替 Agent 的探索。

## 1. 不规则 Excel

业务输入：一份含多个不规则表块的工作簿，问题为“按部门统计差旅费，明细与合计分开”。

| 阶段 | 选择的能力 | 交换对象 | 调整方式 |
|-|-|-|-|
| 文件入口 | DA01.4.2 不规则 Excel 提取 | `FileRef -> TableRef[] + SourceAnchor + issues` | 组合入口内部选择表块和结构恢复，不重复维护解析算法 |
| 布局探索 | DA02.1.1、DA02.2.1/2/3 | 原文件布局 -> 表块、表头、行角色与来源映射 | 表头有歧义时换实现、修改提示，或只澄清受影响表块 |
| 数据准备 | DA02.3.4、DA02.4.2、DA02.6.2 | 表集合 -> 同构明细表、取值画像、类型转换结果 | 列名相同但单位不一致时停止直接追加，先补单位语义 |
| 语义绑定 | DA03.4.1、DA03.5.3、DA03.6.2 | 指标要求 + 画像 -> 指标草案、单位规则、字段映射 | 已有认证指标时直接复用；没有时只确认影响结果的定义 |
| 应用层计算 | DA05/06/07/11/10 | 表与语义引用 -> 计算计划、验证报告、交付表 | 金额对不上时回到行角色/范围识别，不能仅修改最终数字 |
| 保存有效组合 | DA04.1/2/4，调用 DA18 | 实际轨迹 + 验证 -> 经验候选和组合资产 | 记录哪些布局适用，保留可替换表头恢复实现 |

数据层交付的最终资产：原件、规整表新版本、原文映射、指标/字段定义、运行记录和组合候选。工作簿中一张表恢复失败时，既保留成功结果，也明确未覆盖部分，避免“工具成功”掩盖业务覆盖缺口。

## 2. 企业数据库或业务 API 的语义冷启动

业务输入：一个数据库连接或业务 API，用户从一个客户名/产品编码开始提问，尚无完整语义层。

| 场景 | 数据层选择 | 给后续检索/计算的输出 |
|-|-|-|
| 来源探查 | DA01.1/2/9，DA02.4 | `ConnectionRef + SchemaRef + ProfileRef + CapabilityDescriptor`；标明是否支持 SQL、过滤与分页 |
| 用户从某个值进入 | 由 DA05 按需调用值/字段查找；数据读取复用 DA01.3 | 值所在表列候选及对应版本，不先强制全库建模 |
| 关系发现 | DA02.5，必要时 DA03.2/3 | Join 候选、覆盖统计与业务关系草案，保留歧义 |
| 利用已有知识 | DA03.9.1/2 | 导入 dbt 等定义或历史 SQL 的口径草案，列出不可转换项 |
| 保存业务定义 | DA03.6/7/8 | 定义与映射版本、语义依赖、时点解析，后续任务按需复用 |

只有 API 时，“最大值是多少”可以是 `DA01.3 分页取数 -> DA07 代码/函数计算 max -> DA11 完整性与结果检查`。数据层必须返回分页进度、过滤范围和完整性；如果只读到前 100 条，不能让后续计算把样本最大值表述为全量最大值。代码生成属于应用层复用能力，数据层不因此新增一个通用代码引擎。

## 3. 令才：制度与单据的准备

业务输入：制度 PDF/附件、历史单据 JSON、业务审核要求和参考结果。目标是得到可追溯的规则、字段与审核交付效果，处理方法允许调整。

| 数据层任务 | 选择的能力 | 输出及验收关注 |
|-|-|-|
| 原文入库与解析 | DA01.4.4/5、DA01.5，DA02.8 | 原件、文档单元、表格和原文位置；扫描页漏字应可发现 |
| 单据与附件准备 | DA02.3.3、DA02.12 | 明细记录、父子关系、附件抽取值与原文依据；不丢嵌套明细或凭空补值 |
| 规则与适用范围 | DA03.4.3、DA03.8、DA03.16 | 规则草案、历史生效口径和范围条件；不把 UNKNOWN 当作不适用 |
| 评估处理方法 | DA03.15 | 可自动、待补证或人工项及原因；附件可由 OCR/文档方法处理，未必人工 |
| 规则到数据/工具绑定 | DA03.6 | 字段、附件或 API 的映射；缺失接口和未知字段保持未决 |
| 记录真实结果并积累 | DA04.1/2/4/5/6 | 实际调用、修订、程序与组合、验证样本关联；新经验经验证后才扩大范围 |

审核程序生成与修复使用 DA08.6，运行使用 DA07，业务验收使用 DA11，交付组装使用 DA18。现有引擎可作为可替换实现；若要求保持其表达式语义，则补做一致性验证。若只要求业务效果一致，则按约定独立样本验证结果、覆盖率、UNKNOWN、人工量、成本与时延，不强制还原旧代码路径。

## 4. 建议建设切片

| 切片 | 先实现的能力范围 | 可检查的交付 |
|-|-|-|
| A：共享引用与文件准备 | 通用契约和存储端口；DA01.4/5；DA02.1/2/3/8/11/12；DA04.1/4/5 基础保存 | Excel/PDF/JSON 的内容、结构及来源可复用；失败与缺口可定位；形成文件准备组合示例 |
| B：业务语义与实际验收闭环 | DA03.4/5/6/7/8/15/16；按业务补充实体/关系；DA04.2/6 | 针对一类制度和单据完成语义、映射、实际执行与独立业务验收，允许换方法修程序 |
| C：企业连接和增量 | DA01.1/2/3/6/7/8/9/10；DA02.4/5/7/9/10；DA03.2/3/9/10 | 支持数据库/API/MCP，保留完整性、权限及来源差异，按问题按需探索和补语义 |
| D：按实际需求扩展 | 流程/角色/基线、动作/权属/证据/生命周期语义、交付物记忆、DA13 | 针对具体业务补齐资产和物化能力，不将扩展项列为所有场景启动前置条件 |

切片并非能力编号的线性实施顺序。比如令才需要先验证 PDF 制度与 JSON 单据的闭环，不必等全数据库连接器齐备；即席 Excel 分析也不必先建设动作授权模型或物化平台。每个切片应贯通实际输入、必要应用层能力与业务验收，避免只交付目录和函数数量。

## 5. 后续验证重点

共享契约检查引用、版本和错误语义；适配实现验证对源端分页、快照和能力声明是否忠实；文件用多表块、跨页、公式缓存、嵌套数组与低置信数字的独立样本检查保真；语义用历史口径冲突、依赖变化和 UNKNOWN 检查边界；记忆用范围隔离、并发修订和污染反例检查。

端到端验证同时衡量业务结果、覆盖率、未知项、人工负担与运行成本。开发时暴露的样本与未见验收样本分开，修复程序不自动放宽判据。这里列的是后续实现应提供的验证，不表示当前已经运行这些能力或通过业务验收。

# 机器可读能力目录

附本地接口与源码入口映射 JSON；本项目自拟目录，不是发行平台正式 manifest。

<figure view-type="Preview"><source name="dataagent-data-layer-v0.1-atomic-capability-catalog.json" mime="application/json" size="90438" token="UKenbr0AtoreDqxR0x1cqbRjnBg"/></figure>