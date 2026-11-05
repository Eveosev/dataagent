# DA01｜数据接入：输入输出与代码划分 v0.1

定位：外部来源、文件与业务环境资源的连接、读取和引用管理。

**模块输入**：来源连接配置、凭据引用、文件/资源引用、读取范围、目录与增量配置。

**模块输出**：可用连接引用、源结构、原始内容或记录批次、来源位置、完整性与接入状态。

**模块边界**：与业务系统交互只承担连接、读取和声明探测；SQL 运行归 DA07，业务语义归 DA03。凭据与增量订阅由专门端口承接。

本文件与 [共享契约](06-shared-contracts.md) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/ingestion/`。共 10 个能力组、31 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
| --- | --- | --- | --- | --- |
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
| --- | --- | --- | --- | --- |
| DA01.1.1 数据库连接 | `connect_database` | 数据库类型、地址、库名、连接选项、credential_ref | ConnectionRef；后端类型、连接状态、可用特性 | 只建立连接，不执行用户 SQL；凭据由代理解析。 |
| DA01.1.2 API 连接 | `connect_api` | base_url、鉴权引用、超时、接口说明引用 | ConnectionRef；API 描述引用、连接诊断 | 不将 HTTP 连接成功视为数据完整或业务授权。 |
| DA01.1.3 MCP 连接 | `connect_mcp` | 服务地址或启动配置、传输类型、凭据引用 | ConnectionRef；服务身份、工具目录引用 | 目录是能力声明，动作探测由 DA01.9 完成。 |

### DA01.2 结构读取

边界：描述数据结构；动作参数、可执行操作和调用限制归 DA01.9，不推断业务含义。

实现位置：`src/dataagent_data/ingestion/schemas.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.2.1 数据库 Schema 读取 | `read_database_schema` | ConnectionRef、catalog/schema/table 选择范围 | SchemaRef；表列、类型、键、源端声明及读取时间 | 外键未声明时保留未知，不推断业务 Join。 |
| DA01.2.2 API 返回结构读取 | `read_api_response_schema` | ConnectionRef、端点描述或已授权响应样本 | SchemaRef；字段路径、类型、嵌套与可空信息 | 从样本推断与正式 schema 分开标记；不为探测发起副作用调用。 |
| DA01.2.3 MCP 返回结构读取 | `read_mcp_response_schema` | ConnectionRef、工具标识、输出声明或已有结果样本 | SchemaRef；返回内容类型及结构、覆盖缺口 | 返回结构与输入参数契约分开。 |

### DA01.3 数据读取

边界：SQL 执行统一使用 DA07.1。

实现位置：`src/dataagent_data/ingestion/reads.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.3.1 条件读取 | `read_filtered_data` | 资源引用、字段投影、已支持的条件、分页起点 | DataBatchRef；实际条件、cursor、completeness | 不支持的条件返回 unsupported；SQL 请求转 DA07.1。 |
| DA01.3.2 分页读取 | `read_data_page` | 资源引用、读取条件、cursor、page_size、快照约束 | DataBatchRef；next_cursor、has_more、快照一致性说明 | 逐页返回；页取完不等于存在全局一致快照。 |
| DA01.3.3 采样读取 | `sample_data` | 资源引用、采样方法、样本量或比例、可用随机种子 | DataBatchRef；采样方法、样本数、总体估计与局限 | 头部截取须标明非随机，不伪装代表性抽样。 |

### DA01.4 文件解析

边界：不规则 Excel 入口复用 DA02 的表块检测和结构恢复；PDF 表格提取也复用 DA02，扫描件先使用 OCR。

实现位置：`src/dataagent_data/ingestion/files.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.4.1 规整 Excel 解析：提取明确表头的单表或多 sheet 表 | `parse_regular_excel` | FileRef、sheet/range 选择、表头行与公式读取策略 | WorkbookRef；TableRef 列表、坐标映射、公式与缓存值 | 多 sheet 分表输出，不自动 Join；无公式引擎时不宣称重算。 |
| DA01.4.2 不规则 Excel 提取：从混合布局中恢复逻辑表 | `extract_irregular_excel` | FileRef、候选区域、布局提示、恢复策略 | TableRef 列表；SourceAnchor、结构候选、待确认问题 | 组合 DA02.1/2；保留原文件，不把歧义布局静默定为唯一表。 |
| DA01.4.3 CSV/TSV 解析：处理分隔符与编码 | `parse_delimited_file` | FileRef、分隔符、编码、转义与表头选项 | TableRef；SchemaRef、行位置、坏行清单 | 编码或分隔符探测可返回候选；坏行不静默丢弃。 |
| DA01.4.4 JSON/JSONL 解析：保留嵌套记录 | `parse_json_records` | FileRef、JSON/JSONL 格式、记录路径、容错策略 | DocumentRef 或 DataBatchRef；嵌套 schema、JSON Pointer、坏记录 | 嵌套结构先保留；展开为列由 DA02.3.3 完成。 |
| DA01.4.5 文本型 PDF 解析：读取文字与版面位置 | `parse_text_pdf` | FileRef、页范围、版面提取选项 | DocumentRef；文字块、页坐标、阅读顺序候选 | 无文本层的页标注需 OCR；表格恢复复用 DA02。 |

### DA01.5 OCR

边界：保留识别不确定性，不纠正业务数字。

实现位置：`src/dataagent_data/ingestion/ocr.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.5.1 扫描 PDF OCR | `ocr_pdf` | FileRef、页范围、语言、渲染与识别配置 | DocumentRef；逐页文字、bbox、置信度与引擎版本 | 识别结果与原页关联，低置信数字保留问题标记。 |
| DA01.5.2 图片 OCR | `ocr_image` | FileRef、区域、方向、语言与识别配置 | DocumentRef；文字块、图像坐标、置信度 | 不自动把识别近似值改成业务认可值。 |

### DA01.6 资产目录登记

边界：—。

实现位置：`src/dataagent_data/ingestion/catalog.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.6.1 资产目录登记 | `register_asset` | AssetRef、名称、位置、内容类型、作用域、expected_revision | CatalogEntryRef；登记回执、条目版本 | 登记引用不复制全量数据；修改已有条目须做版本冲突检查。 |
| DA01.6.2 维护者与使用条件登记 | `register_asset_stewardship` | CatalogEntryRef、责任人、使用条件、策略引用、expected_revision | 更新后 CatalogEntryRef；变更回执 | 使用条件是声明，实际访问仍由授权机制检查。 |
| DA01.6.3 更新承诺与新鲜度登记 | `register_refresh_commitment` | CatalogEntryRef、刷新承诺、观测来源、expected_revision | 更新承诺引用；与实际新鲜度分列的目录版本 | 承诺不能当成数据已更新的事实。 |

### DA01.7 增量与事件接入

边界：—。

实现位置：`src/dataagent_data/ingestion/changes.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.7.1 游标/水位增量读取 | `read_incremental_cursor` | 资源引用、已提交水位、读取上限、源端快照条件 | ChangeBatchRef；候选新水位、源端一致性与缺口 | 下游持久化成功后才提交水位，读取本身不推进已提交位置。 |
| DA01.7.2 CDC/事件接入 | `subscribe_change_events` | ConnectionRef、订阅范围、起始 offset、消费配置 | SubscriptionRef；事件批次读取句柄、起始位置与租约 | 长流通过句柄分批拉取；不承诺源端没有提供的 exactly-once。 |
| DA01.7.3 迟到与重复事件处理 | `reconcile_change_events` | ChangeBatchRef、事件键、时序键、迟到窗口、状态引用 | 规整事件批次；去重清单、迟到标记、候选水位与状态版本 | 源内时序不能无依据升级为跨源全局时序。 |

### DA01.8 环境资源接入 〔FDE〕

边界：统一资源引用与元数据，保留表、文档、图像、嵌套对象和事件等内容类型，以及分页、快照、权限等来源语义。

实现位置：`src/dataagent_data/ingestion/resources.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.8.1 资源枚举 | `enumerate_resources` | ConnectionRef、父资源、类型过滤、cursor | ResourceRef 列表；层级、next_cursor、可见范围 | 复用连接，按授权枚举；不可见对象不作为不存在的结论。 |
| DA01.8.2 资源读取 | `read_resource` | ResourceRef、所需视图、版本条件、读取范围 | 内容 AssetRef；原始元数据、实际版本和内容类型 | 保留来源结构；不要求文档、图像都转二维表。 |
| DA01.8.3 资源引用与元数据归一 | `normalize_resource_metadata` | 源端对象描述、source_id、源端版本与定位信息 | ResourceRef；标准元数据和来源扩展字段 | 统一寻址与类型，不抹掉分页、快照或权限语义。 |

### DA01.9 能力探测 〔FDE〕

边界：—。

实现位置：`src/dataagent_data/ingestion/capabilities.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.9.1 动作能力枚举 | `enumerate_action_capabilities` | ConnectionRef 或 ResourceRef、工具目录或端点声明 | CapabilityDescriptor 列表；只读/副作用声明、可用状态 | 仅发现声明，不试执行写操作，也不授予执行权限。 |
| DA01.9.2 参数与约束探测 | `inspect_action_constraints` | CapabilityDescriptor、接口规范、已有调用诊断 | 入参约束、返回条件、前置要求及未知项 | 缺失规范标注未知，不能通过危险探测补齐。 |
| DA01.9.3 限流与配额探测 | `inspect_rate_limits` | ConnectionRef、能力标识、文档或响应头、观测窗口 | LimitProfile；速率、配额、重置时间、可信来源 | 发现限制不等于分配预算；不通过压测探测生产限额。 |

### DA01.10 凭据代理与归属 〔FDE〕

边界：不在上下文中出现明文密钥。

实现位置：`src/dataagent_data/ingestion/credentials.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA01.10.1 凭据代理与不落地 | `bind_credential_proxy` | CredentialRef、目标连接、允许的调用范围、有效期 | CredentialBindingRef；代理句柄与绑定回执 | 模型与普通结果中不出现明文密钥；实际调用仍走对应适配器。 |
| DA01.10.2 资源归属登记 | `register_resource_owner` | ResourceRef、所属主体、责任依据、expected_revision | OwnershipRef；主体关联及版本回执 | 资源归属不自动授予主体或 Agent 权限。 |
| DA01.10.3 轮换与失效 | `rotate_or_revoke_credential` | CredentialBindingRef、rotate/revoke、新凭据引用或失效条件 | 绑定新版本或撤销回执；受影响连接、状态 | 需要凭据系统提供相应操作，旧值不写入返回或轨迹。 |
