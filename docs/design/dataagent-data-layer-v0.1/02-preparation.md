# DA02｜数据准备与探查：输入输出与代码划分 v0.1

定位：将原始表格、文档和记录整理为可分析的数据，并保留结构、画像与技术依赖。

**模块输入**：原始文件解析结果、表/文档引用、结构、画像预算、变换规则、已有运行记录。

**模块输出**：结构恢复结果、数据集新版本、画像/关系候选、数据血缘、文档单元、快照和现状基线。

**模块边界**：探查产出候选；正式业务定义交 DA03。表格/文档处理保留原文锚点，变换产生新数据。现状流程、角色与基线属于按需启用的 FDE 扩展。

本文件与 [共享契约](06-shared-contracts.md) 一起使用。下表仅列业务参数；所有调用另携带 `CallContext`，所有输出套用 `CapabilityResult<T>`。表内对象名称是契约类型草案，不代表已存在的类或既有平台接口。

建议源码根：`src/dataagent_data/preparation/`。共 15 个能力组、48 项原子能力。

## 能力组与源码归属

| 能力组 | 作用 | 输入 | 输出 | 源码文件 |
| --- | --- | --- | --- | --- |
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
| --- | --- | --- | --- | --- |
| DA02.1.1 工作簿表块检测 | `detect_workbook_regions` | WorkbookRef、sheet 范围、布局提示 | TableRegion 列表；单元格范围、候选置信度与重叠问题 | 只定位表块，不决定跨块业务关系。 |
| DA02.1.2 文档页面表格检测 | `detect_page_tables` | DocumentRef、页范围、文字/图像布局 | TableRegion 列表；页 bbox、单元格候选及原页锚点 | 模型检测结果是候选，不自动产生认证业务记录。 |

### DA02.2 表格结构恢复

边界：保留原值；不能确认的拼接保留待确认状态。

实现位置：`src/dataagent_data/preparation/structure.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.2.1 多行表头恢复 | `recover_headers` | TableRegion、单元格或文字网格、表头策略 | 表头路径与目标列映射；TableRef、歧义列表 | 保留多层表头原路径，不能为同名列任意合并。 |
| DA02.2.2 合并单元格展开 | `expand_merged_cells` | 表块或 TableRef、合并区域、允许传播的范围 | 新 TableRef；展开映射与变换记录 | 只按结构规则传播合并值，不填补非合并空值。 |
| DA02.2.3 明细/合计行识别 | `classify_table_rows` | TableRef、标签及公式线索、识别配置 | 行角色标注；明细/合计/小计/标题/未知、依据 | 只标注，不删除合计行或改动金额。 |
| DA02.2.4 跨页续表拼接 | `stitch_continued_tables` | TableRef 列表、页序、列对齐与续表提示 | 拼接候选 TableRef；来源映射、冲突与未拼接块 | 不确定的续表关系返回候选，保持原块可追溯。 |

### DA02.3 数据结构转换

边界：不替用户决定跨表业务关系。

实现位置：`src/dataagent_data/preparation/reshape.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.3.1 表格转置 | `transpose_table` | TableRef、目标表头与索引规则 | 新 TableRef；字段/单元格映射、变换记录 | 转置不重新解释业务实体或粒度。 |
| DA02.3.2 宽长表转换 | `reshape_table` | TableRef、宽转长或长转宽、id/value 字段、冲突规则 | 新 TableRef；目标 SchemaRef、映射与冲突 | 长转宽遇多值必须显式给聚合规则，不静默取首值。 |
| DA02.3.3 嵌套字段展开 | `flatten_nested_records` | DataBatchRef、字段路径、展开深度、数组展开策略 | TableRef 或表集合；父子键、路径映射、行膨胀统计 | 保留数组顺序和父记录标识，不默认做笛卡尔积。 |
| DA02.3.4 同结构表追加 | `append_compatible_tables` | TableRef 列表、列对齐、类型兼容与来源列选项 | 新 TableRef；schema 差异、来源映射、行数对账 | 仅追加同构记录，业务 Join 由 DA03/DA06 决定。 |

### DA02.4 数据画像

边界：推断是候选，不直接成为业务定义。

实现位置：`src/dataagent_data/preparation/profiles.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.4.1 表结构画像 | `profile_table_structure` | TableRef 或 SchemaRef、统计预算与采样计划 | ProfileRef；字段形态、行列规模、约束与统计覆盖 | 区分 schema 声明、精确统计和采样估计。 |
| DA02.4.2 字段取值画像 | `profile_field_values` | TableRef、字段集合、采样与敏感值输出策略 | ProfileRef；空值、基数、分布、受限样例与覆盖 | 遵守值访问与脱敏要求；样本统计不声明全量结论。 |
| DA02.4.3 字段类型推断 | `infer_field_types` | SchemaRef、ProfileRef、允许的类型词表 | 类型候选；置信度、依据和冲突 | 这是数据/语义类型候选，不修改源 schema 或认证实体定义。 |
| DA02.4.4 时间角色识别 | `infer_time_roles` | 字段结构、取值画像、相关说明 | 时间角色候选；事件/入库/生效等、依据与歧义 | 字段名相近不等于业务时间相同。 |
| DA02.4.5 记录粒度识别 | `infer_record_grain` | TableRef、键与重复画像、来源说明 | 粒度候选；唯一性统计、反例和限定范围 | 样本唯一不代表全量主键，不自动确立业务粒度。 |

### DA02.5 Join 关系发现

边界：业务关系确认归 DA03。

实现位置：`src/dataagent_data/preparation/joins.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.5.1 键关系发现 | `discover_key_candidates` | SchemaRef 列表、ProfileRef、候选字段范围 | 主键/外键候选；对应字段、统计依据与缺口 | 与源端正式约束区分，不直接写入合法业务 Join。 |
| DA02.5.2 取值覆盖匹配 | `compare_value_coverage` | 两组字段引用、标准化规则、采样/精算预算 | 交叠率、覆盖方向、空值比例、未匹配样例引用 | 取值重叠是候选证据，不证明实体相同。 |
| DA02.5.3 Join 基数探查 | `profile_join_cardinality` | 候选 Join、TableRef、过滤条件、统计预算 | 一对一/多对多等基数报告；膨胀率、覆盖与反例 | 限定到实际快照及过滤范围；业务合法性归 DA03。 |

### DA02.6 数据清洗

边界：保留原件和变换记录，不静默补造事实。

实现位置：`src/dataagent_data/preparation/cleaning.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.6.1 重复记录处理 | `deduplicate_records` | TableRef、重复判定键、保留或合并规则 | 新 TableRef；重复分组、保留映射、改动记录 | 模糊匹配须明确阈值；不覆盖原件。 |
| DA02.6.2 类型转换 | `cast_field_types` | TableRef、目标类型、locale、失败处理策略 | 新 TableRef；转换失败、溢出与精度损失清单 | 不能转换的值保留问题，不静默变为 null。 |
| DA02.6.3 取值标准化 | `normalize_field_values` | TableRef、字段、映射字典与标准化规则版本 | 新 TableRef；值映射、未命中项与变换记录 | 应用指定字典，不自行修改正式业务枚举。 |
| DA02.6.4 缺失值处理 | `handle_missing_values` | TableRef、缺失定义、标记/填补策略及依据 | 新 TableRef；缺失掩码、填补值来源与统计 | 填补值与观测事实分开标识，默认不凭模型补造事实。 |

### DA02.7 数据血缘

边界：区分静态推断与实际执行记录；动态 SQL、存储过程或未覆盖的代码需标注缺口，不据此推断业务口径。

实现位置：`src/dataagent_data/preparation/lineage.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.7.1 源端血缘导入：接入数据目录、ETL 或数据库已有血缘 | `import_source_lineage` | 源端目录/ETL 血缘、资产标识映射、版本范围 | 数据血缘候选边；来源、覆盖范围、无法解析项 | 保存源端声明来源，不当成实际执行观测。 |
| DA02.7.2 SQL 血缘提取：解析表、视图和列的读取与派生关系 | `extract_sql_lineage` | SQL 文本或 AssetRef、方言、SchemaRef、作用域 | 数据血缘边；表/列依赖、表达式引用、解析缺口 | 动态 SQL 或未知 UDF 标注覆盖缺口；不推导业务口径。 |
| DA02.7.3 转换血缘采集：记录文件处理、代码和数据转换的来源及去向 | `collect_transformation_lineage` | 实际执行事件、输入/输出 AssetRef、列映射或代码引用 | observed 数据血缘边；run_id、变换版本及缺口 | 只采集实际提供的信息，不用模型补造已观测列级映射。 |
| DA02.7.4 数据血缘维护：保存和更新带版本的表级、列级依赖 | `upsert_data_lineage` | 数据血缘边、依赖版本、expected_revision | LineageRef；新增/替代/失效边及存储回执 | 保存表列处理关系；资产通用版本政策复用 DA12。 |

### DA02.8 文档加工

边界：复用 DA01 解析，不承担检索或业务结论判断。

实现位置：`src/dataagent_data/preparation/documents.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.8.1 章节/表格切分 | `segment_document` | DocumentRef、章节/条款/表格分块策略、上下文窗口 | DocumentUnitRef 列表；层级、原文锚点、跨块上下文 | 划分检索单元，不执行检索或形成业务判定。 |
| DA02.8.2 原文引用锚点维护 | `maintain_source_anchors` | 文档单元或字段引用、SourceAnchor、源版本、修订映射 | 锚点映射版本；可解析/过期/无法定位状态 | 原文件变化后不能沿用相同坐标并声称仍有效。 |

### DA02.9 结构变化适配

边界：修订建议不自动改变业务定义。

实现位置：`src/dataagent_data/preparation/schema_changes.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.9.1 Schema 差异检测 | `diff_schemas` | 旧/新 SchemaRef、兼容规则 | SchemaDiff；新增/删除/改名候选/类型变更 | 重命名是候选，不能仅凭位置认定同一字段。 |
| DA02.9.2 接口兼容检查 | `check_interface_compatibility` | 旧/新接口描述、已用参数与返回字段、兼容标准 | CompatibilityReport；破坏项、受影响调用点与缺口 | 静态兼容不保证运行成功或业务等价。 |
| DA02.9.3 字段映射修订建议 | `propose_field_remapping` | SchemaDiff、旧 MappingRef、取值画像与说明 | 映射修订候选；依据、冲突及验证需求 | 不直接替换正式语义映射。 |

### DA02.10 修复建议与复核

边界：执行复用 DA02.6，验证复用 DA11，不自动覆盖原数据。

实现位置：`src/dataagent_data/preparation/repairs.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.10.1 修复方案生成 | `propose_data_repairs` | 质量问题、ProfileRef、允许修复策略、原始数据引用 | RepairProposal；步骤、受影响范围、预期变化与风险 | 仅给方案；执行复用 DA02.6，验证复用 DA11。 |
| DA02.10.2 修复前后验证 | `compare_repair_results` | 原/修复后 TableRef、修复计划、验证判据引用 | ValidationReportRef；差异、对账及未解决问题 | 复用 DA11 检查，不自建另一套正确性判据。 |
| DA02.10.3 复核反馈转修复规则 | `derive_repair_rule` | 复核决定、对应问题与改动、适用范围、样本引用 | 修复规则候选；正反例、适用与失效条件 | 人工接受一次不等于可跨企业自动应用。 |

### DA02.11 历史数据保留

边界：仅有时间戳、digest 或最新数据不能保证历史重现。

实现位置：`src/dataagent_data/preparation/snapshots.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.11.1 文件/查询结果快照保存 | `save_data_snapshot` | FileRef 或查询结果引用、保留要求、目标存储 | SnapshotRef；digest、字节/记录范围、实际保存状态 | 必须保有内容或有效历史读取能力，digest 本身不是快照。 |
| DA02.11.2 源端 as-of/快照引用 | `bind_source_snapshot` | 资源引用、as-of/版本 token、源端能力、可选校验请求 | SnapshotRef；解析方式、有效期及可重读能力 | 时间戳不自动等价于可重现；无法保证时明确限制。 |

### DA02.12 文档信息抽取

边界：复用 DA01 解析与 OCR；每个值关联原文位置和置信度，低置信结果保留待确认，不补造缺失值。

实现位置：`src/dataagent_data/preparation/extraction.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.12.1 按目标结构抽取字段 | `extract_fields_to_schema` | DocumentRef、目标字段定义、上下文与提取策略 | ExtractedRecordRef；字段值、置信度、SourceAnchor、缺失项 | 按目标结构抽取，结构草案由调用方提供，不补造缺失值。 |
| DA02.12.2 表单/单据键值抽取 | `extract_form_key_values` | DocumentRef、表单区域、可选字段字典 | 键值记录；重复键、键值区域、置信度及歧义 | 跨页或一键多值不强制压成单值。 |
| DA02.12.3 抽取结果原文锚定 | `anchor_extracted_values` | ExtractedRecordRef、原 DocumentRef、候选原文位置 | 字段到 SourceAnchor 的映射；可核验匹配与未定位项 | 不能定位的值标注缺口，不编造引用。 |

### DA02.13 流程勘查 〔FDE〕

边界：不直接给 to-be 方案。

实现位置：`src/dataagent_data/preparation/processes.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.13.1 步骤与触发条件提取 | `extract_process_steps` | 访谈/流程文档单元引用、业务范围 | 步骤与触发条件候选；来源锚点及待确认项 | 记录现状，不直接生成未来改造流程。 |
| DA02.13.2 分支与例外路径记录 | `record_process_exceptions` | 流程步骤、访谈/案例引用、分支描述 | 分支与例外路径；触发条件、证据和覆盖缺口 | 文档规定与实际做法不一致时分别记录。 |
| DA02.13.3 人工步骤识别 | `identify_manual_steps` | 流程图或步骤集合、角色与操作材料 | 人工步骤标记；人工原因、交接点与待确认项 | 人工环节不自动等同不可自动化。 |

### DA02.14 角色与审批链还原 〔FDE〕

边界：不替代授权系统。

实现位置：`src/dataagent_data/preparation/roles.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.14.1 角色与权限现状 | `describe_current_roles` | 组织/权限材料引用、业务环境范围、观测记录 | 角色与实际权限现状；时点、声明/观测差异 | 描述现状，不授予或撤销权限。 |
| DA02.14.2 事实上的决定者识别 | `identify_actual_deciders` | 流程轨迹、访谈、角色现状、业务事项 | 决定者候选；事项、依据和分歧 | 实际影响力不等于正式审批权限。 |
| DA02.14.3 审批链还原 | `reconstruct_approval_chain` | 流程步骤、角色信息、审批历史或制度引用 | 审批链候选；条件分支、角色和例外 | 观测审批链与正式授权策略分别标识。 |

### DA02.15 现状基线 〔FDE〕

边界：不承诺改进幅度。

实现位置：`src/dataagent_data/preparation/baselines.py`。

| 编号与能力 | 调用名 | 输入 | 输出 | 边界与副作用 |
| --- | --- | --- | --- | --- |
| DA02.15.1 人工耗时与频次 | `measure_manual_effort` | 业务事件/人工记录、时间窗口、计量规则 | 人工耗时/频次基线；样本量、缺口与统计口径 | 自报耗时与自动测量分开，不做收益承诺。 |
| DA02.15.2 错误率与返工率 | `measure_rework_baseline` | 处理记录、错误/返工定义、样本范围 | 错误率/返工率基线；分母、区间与来源 | 跨期比较必须使用一致判据与分母。 |
| DA02.15.3 成本基线 | `measure_cost_baseline` | 人工与系统成本记录、分摊规则、时间/币种 | 成本基线；成本项、假设、区间和未覆盖项 | 估算与实付分列，收益比较交 DA18.5。 |
