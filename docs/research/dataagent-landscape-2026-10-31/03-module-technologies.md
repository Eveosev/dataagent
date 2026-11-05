# DataAgent 模块技术：从一般问数到广义数据应用

调研日期：2026-10-31，Asia/Shanghai。范围：接入、准备、召回、规划执行、分析计算、验证交付、状态资产反馈；业务语义只定义接口，具体语义建模另文讨论。这里的 DataAgent 指一类系统，不以任何现有 agent 平台、工作区或产品架构为前提。

本轮复用 [2026-10-30 开源研究](../dataagent-2026-10-30/02-open-source-and-ontology.md) 中已固定的 DB-GPT、Vanna、SQLGlot 等源码阅读，以及 [旧评测研究](../dataagent-2026-10-30/03-benchmarks-and-evaluation.md) 的数据集与 scorer 核验；没有重复扩大项目清单，没有运行第三方代码、安装依赖、执行 benchmark 或连接业务数据。新增证据在 `sources/modules-*`，网页有原始 HTML 和阅读用纯文本；manifest 保存 URL、抓取时间和 SHA256。本文固定 Git SHA 是本次读取的版本，不表示已验证可用的发行版。

证据标记：**[事实·源码]** 已静态阅读固定提交；**[事实·文档]** 官方技术文档规定的接口/行为；**[自报·工程]** 厂商/团队披露的内部实现或效果；**[用户报告]** 公开 issue 正文及当时状态；**[推断]** 对机制边界的分析；**[建议]** 待实现/待验收方案。README 的性能或安全形容词只算自报，文档示例也不算集成成功。未核实的许可证不作开放授权结论。

## 1. 主要判断

1. **可复用的是执行与数据机制，端到端正确性需要组合验收。** DuckDB/Arrow 提供本地关系计算与交换；dlt 提供增量状态/去重/结构契约；Pandera 提供可执行数据断言；SQLGlot 提供 AST 与名称绑定；Ibis 提供可延迟编译的表达式。这些部件都不能独立承诺业务 grain、指标含义、源数据完整性或权限正确。
2. **从问数扩展到表格、统计、预测、仿真与优化，主要新增“任务契约”和“运行治理”。** 需要明确产物、可写范围、时间可知性、统计假设、目标函数/约束、预算、长任务取消和验收者，不能只把 SQL 工具扩成 Python 工具。
3. **join 和 SQL 正确性必须分层。** 列名/值相似是关系候选；解析通过是语法证据；引擎执行通过是运行证据；grain、cardinality、时态和业务反例才接近正确性证据。单数据快照同值、`DISTINCT` 消重和 LLM 自评都不足以认证关系。
4. **工作簿是有计算状态和呈现状态的文档。** 首行类型推断、公式缓存、1900/1904 日期系统、多表范围、隐藏/合并单元格、外链与对象保留必须单独处理。DataFrame 只是其中一种投影。
5. **rolling backtest 也可能泄漏。** StatsForecast 的 CV 可把验证窗内的协变量作为 `X_future` 交给预测器；调用方必须证明它们在 cutoff 时真实可知。Chronos-2 支持协变量是能力范围，不能证明训练污染、业务目标和现场收益已过关。
6. **状态存储要区分运行记录、实验记录、数据血缘与已批准知识。** Temporal、MLflow、OpenLineage 各解决一部分；成功执行和用户点赞不应自动成为可复用的业务事实。

## 2. 八模块矩阵

下表所有“建议升级”为设计建议，代码存在仅表示可以进一步试验，不表示可直接插入生产系统。

| 模块 | 输入 → 输出契约 | 通用可复用机制与依据 | 扩到广义应用需升级/新增 | 当前主要难点与验证边界 |
| --- | --- | --- | --- | --- |
| **M1 数据接入** | 源标识、凭据引用、principal/目的、范围与 as-of → 可寻址数据快照/流、schema、增量游标、来源/页数/行数、失败与漂移记录 | dlt 的 cursor、重叠区去重、主键/复合键和 schema contract；MCP Toolbox 的 source/tool 分离、参数化 SQL、可信身份 claim 参数 [A1–A3] | 文件/数据库/API/MCP 统一数据句柄；保留原文件/原响应；记录断点、迟到数据、删除与幂等；分析任务读取快照，生产写入独立身份/工具 | API 分页并发变动、无快照接口、游标重置、软删除、跨源时点不一致；接通 MCP 不等于完成 ETL、目录或行列授权；默认自由 SQL 工具不可被当生产边界 |
| **M2 数据探查与准备** | 原数据/工作簿、允许采样范围、质量规则 → 表/范围候选、profile、质量报告、转换 DAG、清洁数据及 reject/差异工件 | DuckDB JSON/Parquet/表计算，Arrow 批交换；Pandera schema/row/dataframe checks 与 lazy failure cases；Valentine 列匹配候选 [B1–B4, C1] | 加 workbook 结构视图、公式和值双轨；时间/单位/枚举规范化；转换可逆、训练窗 fit、异常/缺失保留；多表/跨系统关联发现 | 抽样唯一不能证明全量 PK；自动 coerce/drop-invalid 可改变分母；同名/同值不等于同实体；范围推断、类型混杂与公式缓存易静默错数 |
| **M3 业务语义接口** | profile、业务文档、既有模型/查询与 owner 证据 → 版本化语义引用与候选；外部返回指标/维度/grain/join/时间/权限约束 | 消费已发布语义层的稳定 ID、编译/解释/校验接口；已有研究涵盖 MDL/MetricFlow 等，本报告不重复选型 | 必须表达预测目标/频率/未来信息、实验人群/处理、仿真假设、优化约束/目标及其有效期；草稿可试读，发布仍由对应流程控制 | 靠描述 embedding 无法承载可加性/时态等约束；调用方要处理未知/冲突/废弃版本；检索索引、任务计划和工件都绑定相同 release |
| **M4 问题理解及表/字段/值召回** | 用户请求、多轮约束、可见目录和语义 release → 类型化需求、候选资产/值、必要 join 闭包、歧义/缺失项及证据 | DB-GPT table→field 分级召回；Vanna 的相似 SQL/DDL/文档检索边界；标识符/编码精确查找+关键词+embedding/rerank；LinkedIn 分层目录渐进披露 [D1–D3] | 同时检索方法、可调用函数、历史分析/模型卡/工作簿范围；区分“查历史”“预测未来”“比较干预”“分配资源”；召回结果类型与权限感知 | top-k 任一片段相关不等于必要集合齐全；bridge/tenant/time key 被漏召；高基数/敏感值查找、同名编码、中文别名、多轮口径漂移；PR 分支语义不能混进正式结果 |
| **M5 任务规划与执行** | 类型化任务、数据/语义/权限版本、工具能力、预算 → 带依赖/前后置条件的计划、可恢复 job、受限 SQL/Python/引擎执行及事件 | SQLGlot qualify/AST；MCP Toolbox 预定义 prepared tools；Temporal activity/heartbeat/retry/cancellation；PandasAI 的生成→执行可作适配反例 [A2–A3, E1–E4, E6] | SQL/Python/表格/预测/solver 分执行器；资源额度、异步状态、幂等键、checkpoint、取消确认、清理和强制回收；写操作及导出有显式能力范围 | 只读 SQL 仍可外读文件/网络/高成本；Python AST 清理不是隔离；取消 agent turn 不等于停止 DB/GPU/子进程；重试导致重复工件或外部写入 |
| **M6 分析计算** | 数据句柄、方法/参数、时间契约、输出类型 → 查询结果/工作簿/统计估计/预测分布/仿真轨迹/优化解及诊断 | BI 用 DuckDB/Ibis；表格保留工作簿对象/重算；统计用受控函数；StatsForecast baseline/CV/区间；Chronos-2 可换预测器；SimPy 资源事件、OR-Tools CP-SAT [B1, F1–F6] | 方法注册表（适用条件、数据/结果类型、资源）；统计假设与多重比较；预测 as-of 和未来可知性；仿真校准/重复采样；优化可行性、gap、业务约束 | 各 backend 语义未必等价；大表拉入 pandas 内存；观察性相关写成因果；预测目标取错；仿真缺标定；FEASIBLE 被写成 OPTIMAL；复杂任务无唯一标准答案 |
| **M7 结果验证与交付** | 候选结果、可接受答案/约束、数据/方法证据 → 验证结论、可复算表/图/文件/报告、限制说明与审计包 | 确定性数值/集合/公式/约束检验；SQL 多实例 test suite；图表轴/单位/分母检查；OpenLineage 输出/字段依赖 [G1, H1–H2] | 增加统计/预测不确定性与业务损失验收，solver 状态/约束校验、仿真置信区间；工作簿无关区域/对象完整性；报告每项事实指向结果 | 文件存在、代码无错、LLM judge 通过都不等于结论成立；公开 scorer 可忽略重复/行关系或读 stale cache；静默丢任务会抬高成功率 |
| **M8 状态、资产与反馈** | job/查询/产物、来源版本、用户纠正、owner 决策 → 可重放 run、分析/实验资产、lineage、待审知识提案、失效/回归清单 | OpenLineage Dataset/Job/Run/facets；MLflow 数据集/参数/模型/指标关联；Temporal 运行历史；LinkedIn generated 与 curated context 分存后检索合并 [D3, E6, H1–H3] | 资产身份/租户/保留期/用途；已验证案例库、方法/模型发布、漂移与撤权失效；把用户反馈转成带证据提案和回归任务 | lineage 不等于数据快照或可重现环境；MLflow dataset reference 不保证历史数据可取；缓存撤权、语义更新、个人偏好和企业事实混淆；反馈污染与过期答案复用 |

## 3. 接入和准备：保留可重放来源，再做分析投影

### 3.1 dlt、MCP Toolbox 与本地计算承担不同职责

**[事实·源码]** dlt `Incremental` 将 `last_value`、`initial_value`、`end_value`、`row_order`、`lag`、边界开闭和 dedup key 放进同一增量机制；主键可用复合 tuple，重叠 cursor 值可去重；设置 open 起始范围会禁用重叠去重。`Schema.apply_schema_contract` 处理 `evolve/freeze/discard_row/discard_value`；默认表、列、类型为 evolve。[A1]

**[推断]** 这是值得复用的“读取进度+结构策略”，并不是来源一致性的证明。例如源端分页没有 snapshot、更新不推进 cursor、删除无 tombstone、晚到超过 lag，仍会丢/错数据。`discard_row` 和 `discard_value` 更不能被 agent 当作无害清洗：销量/金额分母会改变。建议每次接入保留 request 范围、游标前后值、主键策略、页数/行数/去重数/reject 数、schema diff 和源更新时间，输出覆盖范围与“是否可重放”。若 API 不支持历史快照，明确记录最早/最晚采集时刻，而非伪造统一 as-of。

**[事实·文档+源码]** MCP Toolbox 把 source 凭据/连接与工具声明分开；`postgres-sql` 是预定义 statement 的位置参数 prepared execution，`templateParameters` 在 prepare 前替换标识符等结构，官方明确其更易注入，建议限制 allowedValues。Authenticated parameters 可从验证过的 OIDC claim 注入，防止用户随意传入 principal/tenant 值。[A2–A3]

**[事实·文档]** `postgres-execute-sql` 官方明确写“intended for developer assistant workflows with human-in-the-loop and shouldn't be used for production agents”。**[事实·源码]** 该工具把任意 `sql` 送入 `source.RunSQL(ctx, sql, nil)`，默认 destructive annotations；通用 Postgres source 的 `IsReadOnly()` 返回 false。Cloud SQL PG 是另一条实现，可用 `readOnly` 加 `cloudsql_session_read_only=locked`；不能据此泛化所有 PostgreSQL 或 MCP source 都只读。[A2]

**[建议]** 两类工具并存：日常经营查询优先预定义参数化能力；自由探索才用受限 SQL 执行器。无论哪类都以数据库最小授权身份、行列策略、允许对象/函数、资源上限为最终边界。MCP 是调用协议；Airbyte 类完整 connector 平台的现有 connector/调度投资可以复用，但本轮没有展开其源码/授权，不能由 connector 数量推定语义、快照和质量覆盖。

### 3.2 Arrow、DuckDB、Pandera：交换、计算、断言不可互相代替

**[事实·文档]** Arrow 定义列式内存布局、有效位图、嵌套结构等交换语义；它有利于多个计算器间交换 batch。[B2] **[推断]** 不能把“使用 Arrow”写成端到端零复制、低内存或精确保留所有业务类型：decimal、timezone、dictionary/category、nested/null 的跨库映射及 materialization 点仍需验收。

**[事实·文档]** DuckDB 有 JSON reader 和 XLSX 扩展；当前 2.0 Excel 文档说明 `.xls` 不支持，默认第一张 sheet；未指定范围时按首段连续非空区域及首个空行推断，列类型依据第一条数据行；`ignore_errors` 会把不能转换的单元格变 NULL。[B1] **[建议]** 在已识别的范围和明确 schema 上运行计算，先读取 metadata/原值，再显式转换；不把自动 NULL 当源端缺失。

**[事实·源码]** Pandera pandas backend 先做列/类型等处理，再执行组件和 dataframe checks；`head/tail/sample` 能使数据值校验只作用于子样本，`lazy=True` 收集多项失败，`coerce`、`drop_invalid_rows` 会影响返回数据。[B3] **[建议]** 用它表达经批准的类型、非空、域、唯一、金额/计数守恒断言；将质量检查与修复分开。跨表外键、时态 join、freshness、分区缺失需自定义查询/检查与调度，不能以某个 dataframe schema 校验成功代表全源健康。Soda/Great Expectations 也是质量断言/运行报告方向候选；本轮未同深度读取，暂不排序其可集成性。

### 3.3 关联发现：先找候选，再证明允许的连接

**[事实·源码]** Valentine 的 `valentine_match` 返回带相似分的 `MatcherResults`；JaccardDistanceMatcher 组合列对，按值集合/可配置字符串距离匹配，Tversky 参数可偏向 containment；metrics 对 1:1 matching 可使用选择算法。[C1] 这对同实体列候选和 schema matching 有用。

**[推断]** 1:1 column matching 不是关系数据的 1:1 cardinality；值集合 containment 也不能证明 FK 或安全 join。`customer_id=42` 在不同 tenant/不同源系统可能是不同客户；地址/金额/日期也可能高重叠。匹配库不会自动决定收入按订单还是订单行计算，也不会修复 SCD 有效期。

**[建议]** 采用可回归的证据链，而非让相似度直接发布 join：

1. 先取声明 FK、受认可 dbt/BI 模型、业务文档和已验证查询日志，再以列名、类型、值匹配扩候选。
2. 对获准范围检查复合唯一性、空值、左右 referential coverage、每键匹配数分布；按 tenant、时间分区、逻辑删除状态分别验证。
3. 检查 join 前后行数、未匹配率与可加指标守恒；N:N 需显式 bridge/先聚合/业务去重规则，禁止自动加 DISTINCT 隐藏 fanout。
4. 验证事件时点、SCD validity、业务键变更、编码/单位转换和候选路径的含义；保留采样范围与“全量/抽样”证据等级。
5. 形成 join proposal 交 M3 审核/发布；M4 只使用适用 release 的批准边，并为没有文本命中的 bridge、tenant/time key 补闭包。

最小反例应包括：同 ID 跨租户、重复主键、N:N、复合键少一列、失效维度、迟到退款、同业务多有效路径。列匹配 precision/recall、join edge 正确率、fanout/总额正确率分别报告；不能只报一个“关联准确率”。

## 4. 理解、召回与执行：把请求变成受约束任务

### 4.1 召回要为任务必要集合负责

**[继承事实·源码]** 旧报告已读的 DB-GPT `DBSchemaRetriever._similarity_search` 先召回 table chunks，再对 separated 大表按 metadata filter 召回 field；这是压缩上下文的好策略，并未证明值召回、join 闭包和 grain 完整。Vanna legacy 召回问答 SQL、DDL、文档，其 `allow_llm_to_see_data` 也说明“允许执行”与“允许数据进入模型上下文”是不同授权。[D1–D2]

**[建议]** 把一次请求先写成 `TaskSpec`：任务类型、对象/指标、分组、过滤、时间/时区、比较或预测跨度、输出工件、验收标准、权限目的、待澄清槽位。召回各自返回 stable ID、版本、类型、来源、命中分、权限范围和缺失信息；精确 ID/别名/编码检索、文本检索、向量召回可组合，reranker 后补关系闭包。结果集最小化不应删掉计算所必需的桥表/条件。

扩到广义应用要多召回三类资产：方法的适用条件和数据需求、已审分析的假设/代码/已知限制、模型/仿真/优化的任务配置。问“下月够不够库存”可能需要需求预测、在途/库存规则和服务水平模拟；召回相关表后直接生成一条 SUM SQL 无法满足原意。没有足够时间/业务信息时，应输出缺失项或提出针对性澄清，而非自造成本函数。

**[自报·工程]** LinkedIn 2026-10-09 披露把自动 profile（schema/query logs/code/masked samples）与 owner 通过 Git PR 审阅的 curated context 分存，同资产 ID 一起返回；global/team/analysis 三种作用域，树状摘要目录逐层披露，支持已知 URN 直接 fetch 与 PR 分支试读。[D3] **[建议]** 可借鉴“可寻址事实+审阅知识+渐进目录”，避免把所有历史对话拼入 prompt。其内部单业务域 acceptable-answer 变化属于自报，不是开放可复现准确率，本报告不用于选型打分。

### 4.2 SQL 需要四层验证

| 层 | 能证明什么 | 不能证明什么/建议补充 |
| --- | --- | --- |
| AST/名称绑定 | SQLGlot 解析、规范化、qualify、展开星号/别名、按 schema 绑定/验证列；可抽对象/列/函数清单 [E1] | 不保证目标方言完整接受、不证明 RLS/资源/业务；显式指定 dialect/schema，失败不要“尽力转换”后静默执行 |
| 真实引擎计划与策略 | dry-run/EXPLAIN（按引擎能力）、权限身份、禁止结构/外部函数、参数绑定、估计扫描/timeout | EXPLAIN 不证明查询结果正确，EXPLAIN ANALYZE 可能实际执行；云引擎开销估计也不等于实际账单 |
| 数据不变量与多实例 | join cardinality、行数/金额守恒、NULL/重复/边界时间反例、多快照结果比较 | 有限测例不能完全证明 SQL 等价；空结果偶合、set 比较丢重复、错误 DISTINCT 会掩盖缺陷 |
| 业务验收 | 指标口径、grain、时间角色、单位、适用人群/比较基线与答案证据 | 需要可追溯定义/owner；同一个模型生成计划再自评不能作为唯一真值 |

**[事实·源码]** SQLGlot `optimizer/qualify.py` 以 schema 推断/限定表和列，默认运行 column validation；这可以支持对象白名单和出错诊断。[E1] **[事实·文档]** test-suite-sql-eval 针对多组数据库实例比较语义结果，明确比单实例执行更接近语义准确度；但其选项能填 gold values、默认不保留 DISTINCT，实际评测设置仍需固定。[G1] **[建议]** 复用“能打破错误 SQL 的变值数据”思想，对企业 join/时间/空值自己造确定性反例；不直接搬旧评测器的容差和集合语义。

### 4.3 只读身份与 Python 隔离是运行契约

**[事实·文档]** DuckDB 官方 2.0 安全指南把不可信 SQL 视作代码，说明引擎能访问文件、网络、扩展；设置是 defense in depth，不代替 sandbox。可禁自动安装/加载扩展、禁外部访问并设置 allowed paths、锁配置；非 SQL 的文件路径/表达式接口也有外读与资源风险。[E2]

**[事实·文档]** PostgreSQL READ ONLY 禁止一系列持久表写入/DDL，但官方明确这是 high-level notion，不能防止所有磁盘写；还可写部分临时表场景。`statement_timeout`、`lock_timeout` 等控制不同等待范围。[E4] **[建议]** 最小数据库角色+受管 session/事务策略+工具白名单+行列授权共同落地；不能仅靠 SQL 首词 SELECT、MCP readOnlyHint 或可被后续语句改回的 session 默认值。限制可执行函数、外部 reader、扩展和凭据可见性；日志/trace 也不能完整输出敏感参数。

**[事实·源码]** PandasAI 当前 `Agent` 的 sandbox 参数默认 None，`execute_code` 有 sandbox 才走其 execute，否则调用 CodeExecutor；后者第 29 行是 `exec(code, self._environment)`。`CodeCleaner.clean_code` 会做 AST、表名/图路径重写，但已读逻辑不构成 OS 权限边界。[E3] **[事实·文档]** 官方说明 DockerSandbox 需独立 `pandasai-docker` 包、Docker 和显式传入，宣称离线/资源/文件系统隔离；企业增强另列。[E3] **[推断]** “有 sandbox 选项”不等于当前部署已经隔离，AST 黑名单也不能替代进程/容器/系统隔离。

**[建议]** 广义 Python runner 使用一次性工作目录、固定依赖镜像、非 root/无特权、禁宿主 socket、只读输入挂载、受限输出目录、默认无网/显式出口、CPU/内存/进程/磁盘/墙钟预算；数据读取尽量由 broker 完成，代码不拿生产凭据。需要更强边界时评估 gVisor/VM，并按自身威胁模型实测；gVisor 文档也明确攻击面和侧信道边界。[E5] 文件/单元格/查询日志中的指令应作为不可信数据，不覆盖执行策略。

### 4.4 长任务：请求取消、实际停止、资源清理分别留证

**[事实·文档+源码]** Temporal 区分 Workflow cancel 与 terminate：cancel 让业务处理清理，terminate 停止 workflow 不给清理机会。普通远程 Activity 通过 heartbeat 接收取消，文档要求 heartbeat timeout；worker 源码分别处理 async task、同步线程取消和事件。[E6] **[推断]** workflow 显示 cancelled/terminated 不保证外部 SQL 查询、子进程、GPU job 或 optimizer 已停止；必须把 engine query ID/process group/job ID 交执行适配器收尾。

**[建议]** `JobSpec` 与 `TaskSpec` 分开，前者含 idempotency key、数据/代码/语义版本、执行器镜像、预算、checkpoint/heartbeat、外部 job handle。状态区分 queued/running/cancel_requested/cancelled/failed/succeeded，并记录“输出是否完整”。取消链为：停止派新任务→向引擎/进程请求取消→限时等待→必要时终止执行单元→确认子任务与资源释放→把部分产物标为 incomplete。重试只针对允许重试的失败，产物发布用幂等键或原子提交，避免重复导出/重复业务动作。Temporal 的重试能力不替代这些 adapter 契约。

## 5. 分析计算：统一任务外壳，保留方法差异

### 5.1 BI 与表格：关系投影和工作簿编辑两条产物路径

**[事实·源码+文档]** Ibis `Expr.compile` 与 backend 执行分开，DuckDB backend 提供 Arrow batches/Arrow/pandas 结果接口；基础教程说明表达式延迟执行，interactive mode 会执行预览，并不是纯展示。[F1] **[建议]** 可用 Ibis 建受控表达式/编译层，推过滤聚合到数据所在后端，最终以 Arrow batch 传输；不能预设所有 backend 都支持同一操作/精度/时区，需冻结 backend 能力矩阵、SQL 结果回归和物化预算。preview 也受权限与计费预算限制。

**[事实·文档]** openpyxl 不计算公式；`data_only` 返回上次 Excel 保存的缓存值，`keep_vba` 仅保留而不可编辑 VBA；只读模式不支持完整对象，文档警告已有文件打开保存可能丢 shapes。[F2] 这说明“pandas 读 Excel→算完→写 Excel”只覆盖规范数据导出，不能保证原 workbook 完整。

**[建议]** workbook contract 至少含 sheet/range/table/named range、公式与缓存、merged/hidden、number format、locale/date system、外链/VBA/图表/透视与可修改区域。先识别多表边界和有效行，保留原文件；只有数值分析时生成独立结果工作簿，编辑既有工作簿则做结构 diff、限定目标区域、用受控 Excel/LibreOffice 引擎重算并视觉检查。未支持公式/外部数据连接标为 inconclusive，不能拿 None 当零或当模型答错。

### 5.2 统计：函数注册比任意分析脚本更易验收

**[建议]** 常用统计封装成带输入/输出类型的函数：描述统计、分组估计、置信区间、回归/检验、实验分析；每项附缺失值策略、样本/重复测量单位、权重、假设、最小样本与随机种子。输出同时包含 N、效应量、区间、检验/模型诊断，不只 p 值或“显著”。对探索性大量分组检查要处理多重比较；时间/人群混杂和抽样偏差要能拒绝因果结论。自由 Python 作为可审实验工件，之后若重复使用再提升为受测方法，避免每次从自然语言重新发明算法。

广义应用不等于每题都用 ML。对账/运营很多任务优先使用确定性查询、守恒断言和约束检查；有预测/干预/优化目标才调用相应方法。现有 DataSciBench/DiscoveryBench 可给复杂产物评分设计启发，但无法替业务决定因果识别假设。

### 5.3 预测：优先验证时间信息，再比较模型

**[事实·源码]** StatsForecast 提供时序 expanding/rolling CV，参数有 `h/n_windows/step_size/input_size/refit`，输出 cutoff/实际值/预测；底层把 cutoff 前数据给 `y_train/X_train`，同时从验证窗取 `X_future` 交模型。`forecast` 的 exog 检查要求未来 `X_df`；官方指南明确未来值拿不到时需先预测或移除协变量。[F3] **[推断]** 库能按时间切目标，不会替业务审查天气实测、结算后状态、最终促销效果是否在 cutoff 已知；把这些作为 X_future 会产生现场无法实现的结果。

**[事实·文档/模型卡]** Chronos-2 支持单/多变量、past-only 与 known-future real/categorical covariates；早期 Chronos/Bolt 不原生支持未来协变量，模型卡区分这一点。[F4] 模型卡的 SOTA 表述为自报，未据此推荐上线。GIFT-Eval 明确 `pretrained/zero-shot/fine-tuned` 的区别，zero-shot 同时要求不含 test、也不使用其数据池 train；模型家族名称不是 checkpoint 的无污染证明。[F4, G2]

**[建议]** 预测任务必须冻结：

- `target/entity/grain/frequency/calendar/timezone/as_of/horizon`、目标业务含义（需求/销量、发生/入账、量/金额），库存截断/退货/缺货观察偏差。
- 每个 feature 的 `available_at` 和未来值来源；训练/验证/最终测试按时间隔离；插补、缩放、编码、特征选择只在训练窗 fit；调参用验证集，最终测试不反复反馈给 agent。
- 基线至少 naive/seasonal-naive 与适用的简单统计模型；再把 Chronos/TimesFM 等做可替换模型函数。后两者的训练语料、协变量接口、算力与权重条款按实际 checkpoint 核查；本轮未展开 TimesFM，故不声称与 Chronos 可直接等价替换。
- 同时报告分组 MASE/RMSSE、偏差、业务权重误差、pinball loss/区间覆盖和宽度，保留冷启动、稀疏/零值、结构变化与最差组；不以总体均值掩盖关键 SKU/门店退化。
- 业务验收定义决策频率、提前期、缺货/积压成本、服务水平、人工 override 和 rollout 范围。先 shadow/历史决策回放，再验收新策略；更低 RMSE 不能直接推出库存收益更高。

MLflow 适合保存 dataset/参数/模型/指标/产物关系，但必须另外保存可重取的数据 snapshot、特征可知性报告与环境。没有这些，run 可看见并不等于历史可复现。[H3]

### 5.4 仿真与优化：新增建模责任和验收者

**[事实·文档]** SimPy 的 Resource/PriorityResource/PreemptiveResource、Container/Store 表达容量、排队、库存、优先级和抢占；是离散事件模型机制。[F5] **[建议]** 对产线/客服/仓储，可复用事件和资源原语，但到达/服务分布、路由、初始库存、暖机期、容量、取消/抢占语义均需真实数据校准。固定随机种子、独立重复、置信区间与历史 replay；业务 owner 验证模型结构，再比较情景。生成能运行的 SimPy 脚本不能证明模型代表现实。

**[事实·文档]** OR-Tools CP-SAT 需要整数约束；返回 OPTIMAL、FEASIBLE、INFEASIBLE、MODEL_INVALID、UNKNOWN。FEASIBLE 未证明最优，UNKNOWN 可能是超时未找到解/未证明无解。[F6] **[建议]** agent 输出变量/单位/域、硬软约束、目标和优先级、数据来源与求解预算；调用 solver 后独立验约束、报告 bound/gap（适用时）与终止原因，给无解诊断和人工可解释的约束放松提案。不要自动松掉合规/容量约束。业务验收既看可行率/目标值/时间，也看实际排班可执行性、稳定性与变更成本。

预测、仿真、优化常串联为“预测需求→模拟风险→优化动作”；上游预测不确定性应通过场景/分布传播，不能只传一列均值再把 solver 最优解当确定建议。该串联是建议工作流，本轮未验证任何库组合的端到端能力。

## 6. 状态与反馈：一次成功如何变成可复用资产

**[事实·源码+文档]** OpenLineage 将 Dataset、Job、Run 区分，RunEvent 有 START/RUNNING/COMPLETE/ABORT/FAIL/OTHER；当前 schema 描述一次 run 发 START 和一个终态。ColumnLineage facet 区分输出字段来源，以及会影响整个数据集的 filtering/grouping/join/window 等依赖；文档另区分 runtime 与 design lineage。[H1–H2] **[推断]** lineage 描述如何产生，不自动保存源数据、验证规则或批准决策。

**[建议]** 可将下列对象按 ID 关联，而不塞进一份自由文本 memory：

| 对象 | 应留信息 | 复用/失效规则 |
| --- | --- | --- |
| Run/job | request/TaskSpec、plan、tools/版本、principal/policy decision、预算、事件、查询 ID、失败分类 | 运行 trace 用于诊断；敏感参数脱敏；取消/partial 状态不冒充成功 |
| Data/transform | 源 snapshot/as-of、schema hash、转换/质量规则版本、reject 与依赖 | 源过期/撤权/结构变化触发失效；原文件与分析投影分别寻址 |
| Analysis/experiment | 问题、假设/范围、SQL/代码、结果/图/工作簿、验证记录、限制、reviewer | 与语义 release/数据绑定；高价值结果可审阅后成为分析案例 |
| Model/scenario/solution | 模型/环境、切分/cutoff、校准、baseline/区间、业务目标/约束/solver 状态 | 运行提升不自动生产发布；漂移与业务规则变化重验 |
| Feedback/proposal | 纠错者身份、原/改答案、原因、证据、适用范围、待审状态 | 用户偏好与企业定义区分；未审例子不能污染 gold/生产知识 |

**[自报·工程]** LinkedIn 的 generated/curated 分存与 Git 合并后同步展示了可参考的知识维护边界；可在 PR 分支试读再发布。[D3] **[建议]** 对 DataAgent，反馈先做分类：数据问题、召回漏项、语义冲突、计划/SQL错、计算错、交付错、个人偏好；保存最小复现案例。修复经验证后更新规则/测试/资产索引，批准知识才进入 M3/M4；按 lineage 找受影响旧结果，并撤销缓存可见性。不要把“多轮里用户没反驳”当成正确标签。

## 7. 公开一手使用问题：把文档能力还原为集成成本

以下已读正文、页面状态和可见评论。**它们是个案和待复核风险，不是当前所有部署的普遍缺陷；没有运行 PoC 或复现文件。** 抓取快照时间见 `modules-issues-manifest.json`。

| 一手来源与抓取状态 | 具体环境/证据 | 当前可说与不可说 | 应转为的验收项 |
| --- | --- | --- | --- |
| [PandasAI #1895](https://github.com/sinaptik-ai/pandas-ai/issues/1895)，2026-06-12 创建，**Open** | 报告者称默认无 sandbox 时模型生成代码可执行 OS 调用，正文指向 CodeExecutor/Agent 的执行分支；未提供固定 package 版本。本文固定 SHA 的 `exec` 和 sandbox 默认 None 与相关代码描述一致 | 可说默认执行边界需要部署者负责；“可被任意真实输入稳定利用”的安全结论仍是报告者主张，未经本轮复现；不能把 AST 过滤/限制 builtins 当充分修复 | 必须显式隔离或拒绝执行；默认失败关闭；host 文件/网络/凭据隔离与资源耗尽测试 |
| [PandasAI #1801](https://github.com/sinaptik-ai/pandas-ai/issues/1801)，2025-08-12 创建，2026-01-07 **Closed as not planned** | RHEL 9.6、Python3.10.18、PandasAI3.0.0b19、pandasai-docker0.1.4、Podman socket；报告镜像未找到/拉取403。2025-10-01 贡献者解释无预构建 Hub 镜像，需本地 Dockerfile 构建，并怀疑 Docker/Podman 连接 | 有部署依赖与镜像构建门槛；关闭由 stale bot 触发，不能声称已修复，也不能把旧 beta/Podman 个案外推当前 Docker 环境 | 固定镜像 digest/构建上下文、架构/运行时矩阵、离线启动和依赖供应、sandbox 启动失败不得回退宿主执行 |
| [duckdb-excel #104](https://github.com/duckdb/duckdb-excel/issues/104)，2026-10-06 创建，**Open** | 报告 DuckDB1.5.4、excel扩展 `f4c72b5`，1904日期系统被按1900转换，2024-01-01读成2019-12-31，差1462天；报告 native/WASM 均见；页面无维护者确认/关联PR | 这是带明确复现环境的日期语义风险；未复现、未查当前2.0对应源码，不能断言2.0仍错或已修复 | 输入/输出1900与1904工作簿，Excel显示值对齐；日期边界/闰年/时区与原XML epoch留证 |
| [SpreadsheetBench #31](https://github.com/RUCKBReasoning/SpreadsheetBench/issues/31)，2025-12-19 创建，**Open** | 报告 openpyxl/pandas 写公式无计算缓存，读取值的 evaluator 得 None/stale，Excel打开重算后通过；2026-05-23 评论者提出第三方 recalc，并声明自己为维护者 | 与 openpyxl 官方不计算公式的说明吻合；第三方评论不是 benchmark 官方修复，也不是新引擎等价于 Excel 的证据 | 保存公式文本→固定重算引擎/版本→读缓存值→记录 unsupported/external-link/inconclusive；单列 scorer/环境问题 |

这些样本偏向开源工程用户与 bug 报告者，不能估计产品失败发生率；但比“支持 Excel/sandbox”的功能表更接近具体集成验收条件。

## 8. 模块评测组合与公开 benchmark 边界

本节是模块组合建议，不重复旧报告全表、规模和门槛，也不提供本次自跑成绩。分三条轨道：**从原始源冷启动、已发布语义上的应用、逐步提供 gold 表/字段/join/口径的瓶颈诊断**。gold 辅助轨不能冒充产品成功率。

| 被测模块 | 最小验收工件/指标 | 公开参考与适用边界 | 必须自建的补测 |
| --- | --- | --- | --- |
| M1–M2 接入/质量/关系 | 页/行/键覆盖、schema drift、采样范围、质量漏报/误报、join候选/闭包 P/R、fanout/守恒 | Valentine 可比较 column matching；BEAVER 的 join/key 子任务可定位召回/关联；均不能证明 API快照、全量 cardinality、跨租户/时态含义 | 翻页更新/重试/删除/乱序、cursor 同值、schema类型变、复合键/N:N/SCD/tenant、质量规则与repair分开 |
| M4–M5 召回/SQL/交互 | 必要 table/column/value **集合全召回率**、join闭包覆盖、结构/执行/业务通过率、澄清信息增益、预算 | BIRD侧重值/证据；Spider2侧重大schema/工作流；BEAVER可分解；BIRD-Interact测试交互；test-suite多实例比单库EX更能揭错 | 权限与release过滤、中文别名/编码/敏感值、漏桥表恢复、SQL多快照反例、只读身份/函数与缓存泄漏 |
| M5 运行治理 | 实际终止延迟、剩余query/process/GPU/文件数、重复产物、恢复成功、成本/超时 | 上述SQL/分析benchmark的工具轨迹有参考价值，通常不覆盖真实取消/资源隔离 | 强制终止、失联worker、DB超时、checkpoint重放、at-least-once重试、sandbox启动失败、输出原子发布 |
| M6–M7 BI/表格/统计交付 | 数值/单位/分母、图表证据、公式重算、范围与对象完整性、统计效应/区间/假设 | DABench适合闭式CSV快速回归；SpreadsheetBench适合真实工作簿操作/OJ变值，需重算且核对题/答案版本；DataSciBench TFC适合逐产物评分；DiscoveryBench适合假设facet，均有judge/标准答案边界 | 复杂表头/多表/隐藏合并/日期系统/外链、未修改区域、图表误导、重复观察/权重/多重检验、相关≠因果 |
| M6–M7 预测/仿真/优化 | 数据目标正确+无泄漏，backtest误差/覆盖+业务损失；仿真校准/重复CI；solver可行性/status/gap | GIFT-Eval/Monash只验证预测函数/配置，不能验证agent选目标或库存收益；本轮未识别能覆盖任意业务仿真/优化的通用公开端到端基准 | as-of/available_at、特征fit窗、冷启动/缺货截断、业务回放；仿真历史轨迹/极端情景；优化硬约束/无解/超时/可执行性 |
| M8 资产/反馈/版本 | 固定快照重放、依赖覆盖、撤权/更新失效、纠错转回归、污染率 | OpenLineage/MLflow是记录机制，不能当能力benchmark；公开静态题集通常不测企业知识维护生命周期 | schema/指标/日历/权限v1→v2、缓存撤权、被污染反馈、未审知识隔离、旧案例失效/回滚 |

**[建议]** 端到端任务必须同时过业务结果、权限/隔离、证据和产物完整性；不能平均抵消安全失败。固定全部任务分母，超时/漏答/取消/工具失败分别计；记录精确数据、scorer、model/checkpoint、prompt、工具/预算、缓存、query plan与环境版本。结果采用保留重复行的 bag/必要排序语义，定义 NULL/NaN/decimal/timezone/容差；图/报告用确定性约束为主、judge辅以人工抽检。公开集按实际 artifact/许可取得情况选择，不能把 research/NC 数据打包商业分发；各项旧报告已核实的许可边界继续适用。

## 9. 来源、固定代码与许可证核验

下列为本文实际阅读范围。官方文档可能随服务更新；`modules-*-manifest.json` 与原文缓存才是本次证据快照。许可证仅核到列出的根文件/路径，未做依赖闭包、模型权重与数据授权审计。

### A. 接入与工具

- **[A1] dlt，SHA `13db5716037352ba46fcdfc825251df3a9fdcc9f`**：[Incremental](https://github.com/dlt-hub/dlt/blob/13db5716037352ba46fcdfc825251df3a9fdcc9f/dlt/extract/incremental/__init__.py#L99)、[Schema.apply_schema_contract](https://github.com/dlt-hub/dlt/blob/13db5716037352ba46fcdfc825251df3a9fdcc9f/dlt/common/schema/schema.py#L177)、[Pipeline](https://github.com/dlt-hub/dlt/blob/13db5716037352ba46fcdfc825251df3a9fdcc9f/dlt/pipeline/pipeline.py)；[增量官方说明](https://dlthub.com/docs/general-usage/incremental-loading)、[schema evolution](https://dlthub.com/docs/general-usage/schema-evolution)。根 [LICENSE.txt](https://github.com/dlt-hub/dlt/blob/13db5716037352ba46fcdfc825251df3a9fdcc9f/LICENSE.txt) 已读：Apache-2.0。
- **[A2] MCP Toolbox，SHA `772847cb6d35e0dc6979f6ba13298adcc71b52d4`**：[自由SQL文档](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/docs/en/integrations/postgres/tools/postgres-execute-sql.md)、[执行实现](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/internal/tools/postgres/postgresexecutesql/postgresexecutesql.go#L87)、[通用Postgres source](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/internal/sources/postgres/postgres.go#L100)、[CloudSQL PG只读配置](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/internal/sources/cloudsqlpg/cloud_sql_pg.go#L177)。根 [LICENSE](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/LICENSE) 已读：Apache-2.0。
- **[A3] 同SHA**：[postgres-sql/prepared与template文档](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/docs/en/integrations/postgres/tools/postgres-sql.md)、[实现](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/internal/tools/postgres/postgressql/postgressql.go)、[工具参数/授权](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/docs/en/documentation/configuration/tools/_index.md)、[认证模式](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/docs/en/documentation/configuration/authentication/_index.md)。注意标准MCP客户端是否支持特定扩展须另验。

### B/C. 数据准备与候选关联

- **[B1] DuckDB官方2.0文档**：[Excel](https://duckdb.org/docs/2.0/core_extensions/excel.html)、[JSON](https://duckdb.org/docs/2.0/data/json/overview.html)。旧报告只核过 DuckDB 根许可，本轮不把其根许可推定为所有独立扩展/制品许可。
- **[B2] Arrow官方格式**：[Columnar format](https://arrow.apache.org/docs/format/Columnar.html)，本轮文档阅读，未展开运行时源码/许可。
- **[B3] Pandera，SHA `185059015b816cb3f09ddd8157b77e7433769045`**：[pandas container backend](https://github.com/unionai-oss/pandera/blob/185059015b816cb3f09ddd8157b77e7433769045/pandera/backends/pandas/container.py#L48)、[Lazy Validation](https://pandera.readthedocs.io/en/stable/lazy_validation.html)。根 [LICENSE.txt](https://github.com/unionai-oss/pandera/blob/185059015b816cb3f09ddd8157b77e7433769045/LICENSE.txt) 已读：MIT。
- **[B4] 工作簿边界**见 [F2] 与 issue 表；数据清理应保留 reject/修改工件是本文建议，不是 Pandera 自动交付全部 lineage 的事实。
- **[C1] Valentine，SHA `a725a04ea8dfdcf092821a0bc1b42522e1619c68`**：[README](https://github.com/delftdata/valentine/blob/a725a04ea8dfdcf092821a0bc1b42522e1619c68/README.md)、[valentine_match](https://github.com/delftdata/valentine/blob/a725a04ea8dfdcf092821a0bc1b42522e1619c68/valentine/__init__.py#L73)、[JaccardDistanceMatcher](https://github.com/delftdata/valentine/blob/a725a04ea8dfdcf092821a0bc1b42522e1619c68/valentine/algorithms/jaccard_distance/jaccard_distance.py#L160)、[metrics](https://github.com/delftdata/valentine/blob/a725a04ea8dfdcf092821a0bc1b42522e1619c68/valentine/metrics/metrics.py)。根 [LICENSE](https://github.com/delftdata/valentine/blob/a725a04ea8dfdcf092821a0bc1b42522e1619c68/LICENSE) 已读：Apache-2.0。

### D/E. 召回与执行

- **[D1] DB-GPT**：复用旧报告 SHA `06a46eea2d248a0f2b3e9096035424df4f2dc2eb`，重点 [DBSchemaRetriever](https://github.com/eosphoros-ai/DB-GPT/blob/06a46eea2d248a0f2b3e9096035424df4f2dc2eb/packages/dbgpt-ext/src/dbgpt_ext/rag/retriever/db_schema.py#L190)。本轮不重新声明最新版本、安全或许可证。
- **[D2] Vanna**：复用旧报告 SHA `365d0617c1a4567ffee1b19b40c27feb4206bfcf`，重点 [legacy generate_sql](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/legacy/base/base.py#L93)、[RunSqlTool](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/tools/run_sql.py#L56)。同样不将 legacy 行为等同整个新 agent 的所有配置。
- **[D3] LinkedIn 2026-10-09官方工程博客**：[Inside LinkedIn’s data context layer](https://www.linkedin.com/blog/engineering/infrastructure/inside-linkedins-data-context-layer-curating-trustworthy-context-for-humans-and-agents)。全文已读，内部实现/效果为团队自报，无公开源码或可复现评测工件；不推断为现成开源组件。
- **[E1] SQLGlot，沿用旧报告SHA `f31f109daef0ca99347d36295534a0d59956059c`**，本轮新增读取 [qualify.py](https://github.com/tobymao/sqlglot/blob/f31f109daef0ca99347d36295534a0d59956059c/sqlglot/optimizer/qualify.py#L19)；[README](https://github.com/tobymao/sqlglot/blob/f31f109daef0ca99347d36295534a0d59956059c/README.md) 明确 schema/type 对优化规则的影响。许可沿用旧报告已读根文件，未复核依赖。
- **[E2] DuckDB官方安全指南**：[2.0 Securing DuckDB](https://duckdb.org/docs/2.0/operations_manual/securing_duckdb/overview.html)。stable URL 在本次返回HTML meta redirect，实际抓取2.0正文；没有把跳转页当技术正文。
- **[E3] PandasAI，SHA `bbbb771d31062d81f6fa19bafb40620d5cbe48f4`**：[CodeExecutor](https://github.com/sinaptik-ai/pandas-ai/blob/bbbb771d31062d81f6fa19bafb40620d5cbe48f4/pandasai/core/code_execution/code_executor.py#L27)、[Agent默认sandbox及执行分支](https://github.com/sinaptik-ai/pandas-ai/blob/bbbb771d31062d81f6fa19bafb40620d5cbe48f4/pandasai/agent/base.py#L48)、[CodeCleaner](https://github.com/sinaptik-ai/pandas-ai/blob/bbbb771d31062d81f6fa19bafb40620d5cbe48f4/pandasai/core/code_generation/code_cleaning.py#L138)、[Privacy & Security文档](https://docs.pandas-ai.com/v3/privacy-security)。根 [LICENSE](https://github.com/sinaptik-ai/pandas-ai/blob/bbbb771d31062d81f6fa19bafb40620d5cbe48f4/LICENSE) 已读：`pandasai/ee/` 另许可，其他列述范围为 MIT Expat，第三方各自条款；未核 Docker 扩展与镜像完整授权，不笼统称全部MIT。
- **[E4] PostgreSQL官方**：[18 SET TRANSACTION](https://www.postgresql.org/docs/18/sql-set-transaction.html)、[client timeouts](https://www.postgresql.org/docs/current/runtime-config-client.html)。READ ONLY 不是全面磁盘/网络隔离。
- **[E5] gVisor官方**：[Security Model](https://gvisor.dev/docs/architecture_guide/security/)，本轮只读威胁边界文档，未运行或核制品许可。
- **[E6] Temporal Python SDK，SHA `c1a79fb659ffab144d7949213664a584809089f7`**：[Activity API](https://github.com/temporalio/sdk-python/blob/c1a79fb659ffab144d7949213664a584809089f7/temporalio/activity.py#L327)、[worker取消处理](https://github.com/temporalio/sdk-python/blob/c1a79fb659ffab144d7949213664a584809089f7/temporalio/worker/_activity.py#L219)、[运行活动取消](https://github.com/temporalio/sdk-python/blob/c1a79fb659ffab144d7949213664a584809089f7/temporalio/worker/_activity.py#L744)、[Cancellation官方文档](https://docs.temporal.io/develop/python/cancellation)、[failure/retry官方页](https://docs.temporal.io/develop/python/failure-detection)。后者现跳转 error handling，正文说明 at-least-once 与幂等；并非从URL标题推断。根 [LICENSE](https://github.com/temporalio/sdk-python/blob/c1a79fb659ffab144d7949213664a584809089f7/LICENSE) 已读：MIT，仅此SDK，不代表server/服务。

### F/G/H. 分析、评测与资产

- **[F1] Ibis，SHA `8c3800b03f74345686be63134c30a791599f11cd`**：[Expr.compile](https://github.com/ibis-project/ibis/blob/8c3800b03f74345686be63134c30a791599f11cd/ibis/expr/types/core.py#L479)、[DuckDB backend/to_pyarrow_batches](https://github.com/ibis-project/ibis/blob/8c3800b03f74345686be63134c30a791599f11cd/ibis/backends/duckdb/__init__.py#L1348)、[基础教程执行说明](https://ibis-project.org/tutorials/basics)。根 [LICENSE.txt](https://github.com/ibis-project/ibis/blob/8c3800b03f74345686be63134c30a791599f11cd/LICENSE.txt) 已读：Apache-2.0；未跑backend互换测试。
- **[F2] openpyxl官方**：[Tutorial](https://openpyxl.readthedocs.io/en/stable/tutorial.html)、[Formulae](https://openpyxl.readthedocs.io/en/stable/simple_formulae.html)，本轮未核许可证/编译计算引擎。
- **[F3] StatsForecast，SHA `f9cd2f2c3204df45a4b3af7ea63bfd9492a2a9b7`**：[CV切窗/X_future](https://github.com/Nixtla/statsforecast/blob/f9cd2f2c3204df45a4b3af7ea63bfd9492a2a9b7/python/statsforecast/core.py#L281)、[cross_validation接口](https://github.com/Nixtla/statsforecast/blob/f9cd2f2c3204df45a4b3af7ea63bfd9492a2a9b7/python/statsforecast/core.py#L1126)、[models](https://github.com/Nixtla/statsforecast/blob/f9cd2f2c3204df45a4b3af7ea63bfd9492a2a9b7/python/statsforecast/models.py)、[Cross validation](https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/crossvalidation.html)、[Exogenous regressors](https://nixtlaverse.nixtla.io/statsforecast/docs/how-to-guides/exogenous.html)、[Conformal prediction](https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/conformalprediction.html)。根 [LICENSE](https://github.com/Nixtla/statsforecast/blob/f9cd2f2c3204df45a4b3af7ea63bfd9492a2a9b7/LICENSE) 已读：Apache-2.0；不等同Nixtla所有产品/模型服务条款。
- **[F4] Chronos-2官方模型卡**：[amazon/chronos-2](https://huggingface.co/amazon/chronos-2)。读取卡片，不下载权重、不将卡片Apache标签代替完整权重/语料许可核验；代码家族背景沿用旧报告。
- **[F5] SimPy官方**：[Shared Resources](https://simpy.readthedocs.io/en/latest/topical_guides/resources.html)，抓取页面自标 `4.1.2.dev16+gf43816490`；仅文档层证据，未读实现/许可。
- **[F6] OR-Tools官方**：[CP-SAT solver](https://developers.google.com/optimization/cp/cp_solver)，文档层证据；本轮 git读取失败，未固定源码或核许可，不声称已审代码。
- **[G1] test-suite-sql-eval，SHA `e97acc546ecbee8fa27fa8dbf025ef61493a876c`**：[README](https://github.com/taoyds/test-suite-sql-eval/blob/e97acc546ecbee8fa27fa8dbf025ef61493a876c/README.md)，只读方法/选项；本轮未展开 scorer 源码、下载测试数据库或核数据许可，不与原Spider2评分器混称。
- **[G2] GIFT-Eval官方**：[README](https://github.com/SalesforceAIResearch/gift-eval/blob/main/README.md)，本轮浮动main快照已缓存；不是固定可复现数据/评估release。其余 benchmark 的官方URL/实现细节、许可与版本冲突沿用旧报告 [第9节](../dataagent-2026-10-30/03-benchmarks-and-evaluation.md#9-本次已读一手来源)。
- **[H1/H2] OpenLineage，SHA `bad2d7fc50c57d009ed58bb3643287aa1fe02631`**：[RunEvent schema](https://github.com/OpenLineage/OpenLineage/blob/bad2d7fc50c57d009ed58bb3643287aa1fe02631/spec/OpenLineage.json)、[ColumnLineageDatasetFacet](https://github.com/OpenLineage/OpenLineage/blob/bad2d7fc50c57d009ed58bb3643287aa1fe02631/spec/facets/ColumnLineageDatasetFacet.json)、[Object model](https://openlineage.io/docs/spec/object-model/)，文档抓取版本1.55.0。根 [LICENSE](https://github.com/OpenLineage/OpenLineage/blob/bad2d7fc50c57d009ed58bb3643287aa1fe02631/LICENSE) 已读：Apache-2.0。
- **[H3] MLflow官方**：[Tracking](https://mlflow.org/docs/latest/ml/tracking/)，本轮文档层、未固定源码/读许可证，未验证运行服务/RBAC/数据快照保存。

## 10. 未验证项与优先复核

**所有组合都未运行集成验证**；本轮源码仅选定文件静态阅读，未做依赖/身份/网络/调用入口全链安全审计。GitHub API匿名限流记录在 `modules-code-manifest.json`；改用固定 raw 与只读 blobless git抓取，没有用失败的tree响应支撑结论。网页状态为抓取时点，不保证后续不变。

优先复核三项主张，直接影响设计选择：

1. **只读/隔离能否被执行链强制落实。** 在指定数据库身份、DuckDB版本/扩展和Python镜像上，验证对象/行列、文件/网络、凭据、资源限制、重试与取消，尤其确认无sandbox不会回退宿主，以及cancel后外部query/process真的退出。源码接口与文档形容词无法替代此项。
2. **跨源join与工作簿是否能保持业务数字。** 用授权样本/确定性反例验证复合键/tenant/SCD/N:N fanout、类型/日期系统、公式重算及未修改区域/对象；对duckdb-excel #104固定旧环境与目标新版本分别复测，不能凭Open状态直接定当前缺陷。
3. **预测任务的现场可用性是否成立。** 对每个协变量落实available_at、rolling cutoff与预处理fit窗，保留简单基线和业务决策回放；审实际checkpoint/训练污染和目标定义，再评模型误差/收益。StatsForecast或Chronos可调用不等于可交付预测应用。
