# DataAgent 的 MintHub 组合方式与语义互通

调研日期：2026-10-30，Asia/Shanghai。本文区分「源码事实」和「建议设计」。只做静态读取，没有安装、运行或发布 DataAgent。

## 1. 本次核验范围

- 工作区本身不是 Git 仓库；内层 `packages/agent-kernel` 是独立仓库。
- 本次读取的 Kernel/Mint HEAD：`86ae83c452a1d6e55554699c27bb4cbd64628147`，读取时 `git status --short` 为空。
- 读取 manifest、preset 合并、MCP loader/client/transport、ToolContract、StoreContract、HostCall 与相关测试源码。测试只读，未执行。
- 旧资料 `docs/mint/README.md` 是 2026-10-26 的整理，不能直接代表当前源码或实际发布制品。
- 在线 MintHub 文档已读取；没有用源码 HEAD 推断线上包版本、二进制 feature 或干净机器消费结果。

## 2. Mint 当前能承载什么

所有源码路径以下均相对 `packages/agent-kernel/`，行号以本次 HEAD 为准。

| 事项 | 已读源码事实 | 对 DataAgent 的影响 |
| --- | --- | --- |
| 包类型 | `mint/crates/mint-manifest/src/lib.rs:44` 的 `Kind` 包括 bundle、preset、app、iface、mcp 等 | 类型存在只证明清单可表达，仍要查消费者 |
| bundle 的 MCP 装载 | `mint/crates/mint-core/src/mcp_loader.rs:442` 扫 lock，仅选择 `Kind::Bundle` 并读 `.mcp.json` | 本次核验到的能力入口是 bundle + stdio server |
| 项目信任 | `mcp_loader.rs:188` 的 `load_mcp_clients_with` 检查项目 trust；包自报来源或 trust 不构成豁免 | 安装包与允许启动工具是两个步骤 |
| 启动程序与环境 | `mcp_loader.rs:325` 的 `prepare_server` 检查包的 `capabilities.exec/env` | 发布包只声明必要程序和环境变量名；这不是文件或网络隔离的证明 |
| 远程 MCP | `mcp_loader.rs:328` 明确拒绝无 command 的配置；`mint-manifest/src/mcp.rs:29` 虽有 `StreamableHttp` | 当前路径需要本地服务调用远程数据库/API，或另行验收可用的远程适配 |
| 工具注册 | loader 给工具加 `<server>__<tool>` 前缀，注册到扩展 registry | DataAgent 可复用现有工具循环，无需新造 Agent runtime |
| 请求超时 | `mint-core/src/mcp/transport.rs:24` 默认单请求 60 秒 | 数据库扫描、建模与预测应短请求受理，另取任务状态 |
| 取消 | `mint-core/src/iface_adapters/mcp_tool.rs:169` 的 `abort` 返回 `METHOD_NOT_IMPLEMENTED` | 应提供应用级 job cancel，并确认底层数据库也停止查询 |
| 身份上下文 | `mint-core/src/mcp/client.rs:561` 的 `Tool::call` 接收 `_ctx`，调用仅转发工具参数 | 不能假设租户、用户和会话权限已经自动传至服务端 |
| 工具效果判断 | `mcp/client.rs:706` 的 `guess_kind_from_name` 按名字猜分类 | 服务端仍需独立执行权限和副作用检查；不能把命名当授权机制 |
| 结果承载 | `mcp/client.rs:579` 调 `McpContent::join_text`；iface 适配也转为文本 bytes | 大表与文件留在受控数据面，工具返回摘要和可验证 artifact 引用 |
| preset | `mint/bins/mint/src/preset.rs:1` 合并依赖配置和 UI，policy 只能收紧 | 适合表达 DataAgent 的能力组合与默认流程 |
| Host API | `mint/crates/mint-protocol/src/host.rs:370` 仅有 log、store.get/set、notify、net.fetch | 不应假设 JS 插件已具有通用本地文件、Python 或数据库驱动接口 |
| Kernel 存储 | `kernel/iface/src/store.rs:1` 是事件存储契约 | 业务 ontology registry、值索引和结果集存储需要明确的应用层所有者 |

`mint/crates/mint-core/tests/mcp_tool_contract.rs` 包含工具绑定、结果错误、审批路径及不支持 abort 的断言。这里的结论是源码和测试定义可见，尚不构成实际部署验证。

### 不能从上述事实推出的结论

不能据此承诺远程 OAuth、用户身份透传、数据库 RLS、Python 隔离、图表/表格原生渲染或完整企业多租户已经就绪。需按目标 Core/Host/GUI 制品分别验收。

## 3. 建议的交付组合

以下名称是建议的职责名，不代表 MintHub 已有同名包，不是可直接运行的清单。

| 交付层 | 内容 | 建议形态 |
| --- | --- | --- |
| 契约 | SourceProfile、SemanticRevision、QueryPlan、ResultArtifact、FunctionSpec、EvalCase 的版本化 schema 与 fixtures | 纯契约包；实际 kind 以目标 CLI 消费能力为准 |
| 数据能力 | 文件导入、数据源连接、profile、执行与任务服务 | bundle 中的 stdio MCP 入口，或已验证的宿主适配 |
| 语义能力 | ontology 提案、业务确认、版本、检索与计划编译 | 可独立版本的库/模块，按需经服务暴露 |
| 分析能力 | BI 运算、表格产物、预测函数及依赖锁 | 功能包；不要求每个函数启动一个进程 |
| 行业内容 | 业务术语、指标模板、日历、常见关系、分析方法、评测样例 | 无客户数据的领域 bundle |
| Agent 配方 | 模块依赖、提示词、工作流和权限默认值 | preset |
| 用户产品 | 会话、文件选择、数据源、口径确认、结果表、图、导出和任务界面 | agent 工程构建成 app |

推荐顺序：先通过 bundle/preset 验证真实消费，再决定是否需要携带专用 UI 和 runtime 的 app。客户原始文件、凭据、值索引与私有 ontology 放在客户工作区或企业存储，公开 MintHub 只分发代码、模板和契约。

### 包边界和进程边界分别设计

多个可复用模块可以链接到同一个受控服务，避免共享数据重复序列化和多个 Python 环境。隔离需求不同的预测 worker、第三方函数可单独运行。每一个拆包都应有独立消费者、替换需求或版本生命周期；初版无需把下表每一行都发布成单独包。

### 契约的最小职责

| 契约草案 | 应表达的关键内容 |
| --- | --- |
| SourceProfile | 数据源 ID、方言、结构指纹、表/列/约束、采样策略、完整或估算标记、采集时间、授权范围 |
| SemanticRevision | 稳定概念 ID、grain、指标公式和时间、join/cardinality、证据、审核状态、来源与父版本 |
| QueryPlan | 绑定的概念/字段/值、时间解释、语义版本、参数、join 路径、SQL/DSL、解释与待澄清项 |
| ResultArtifact | 查询/数据快照标识、schema、行数、截断标记、digest、受控引用、权限、统计摘要 |
| FunctionSpec | typed input/output、适用条件、算法/包版本、参数、时间与内存预算、数据外发和副作用声明 |
| EvalCase | fixture、问题、可接受解释、业务结果断言、权限主体、版本、预算与评分器身份 |

这些契约属于研究建议，尚未通过 iface conformance，也未注册为任何已支持的 `implements`。

## 4. 运行期设计建议

### 4.1 长任务

建议 `submit -> job_id -> status/result/cancel`。受理时固定源、用户、授权范围、语义版本和幂等键。状态区分 pending/running/succeeded/failed/cancelled/unknown；请求超时后先查状态，避免重做扫描或训练。

取消验收需要看到数据库 query handle 或 worker 已停止。仅前端停止等待不能证明任务取消。大结果通过分页或 Arrow/Parquet 等数据面传递，模型只读 schema、摘要和必要片段。

### 4.2 身份与权限

本地单用户试点可以使用用户自己的只读连接。企业共享服务需要可信宿主签发的身份/授权上下文，服务端验证；模型填写的 `tenant_id`、`user_id` 或 `approved=true` 都不授予权限。

权限覆盖发现、采样、schema 和值检索、query、cache、artifact 与导出全链路。服务账号能采样某个值，不代表这个值能展示给所有用户。cache/index 按授权作用域隔离，并能随权限变更失效。

数据库/API 侧只读账号、RLS/列策略与成本限制是执行控制的一部分。SQL AST allowlist 和提示词不能替代这些控制。DuckDB 的文件/网络读取和扩展安装也需要受限。

### 4.3 版本和存储

至少分别记录：代码/依赖版本、语义 revision、schema 指纹、policy revision、index 构建版本、数据 snapshot/as-of、function/模型版本和运行配置。`mint.lock` 只解决依赖制品，不会自动锁定客户的实时数据或业务口径。

源不支持 snapshot 时，记录查询执行时间、源版本能力和可重复性限制。用户数据写在包安装目录外；包升级与语义迁移应分别处理。语义字段改名、指标公式改动或 join 基数变化要触发影响分析和回归，保留旧 revision 供历史解释。

## 5. 语义层开放标准：Ossie 的实际状态

本次读取并固定 Apache Ossie HEAD `7a8de20f850dad3934e307a1ac7425b09e9ca89f`。官方 README 确认项目原名 Open Semantic Interchange / OSI；当前 Core spec 明确为 `0.2.0.dev0` 草案，Version History 记录 `0.1.1` 于 2025-12-11 发布。

| 已读内容 | 事实 | 设计含义 |
| --- | --- | --- |
| Core spec | JSON/YAML 的 dataset、field、relationship、metric、ai_context、custom_extensions | 值得作为跨工具交换格式候选 |
| 0.2.0.dev0 迁移说明 | 单模型扁平文档取代 `semantic_model` 数组；字段引用语义变化 | 不能混用版本形状，导入器必须显式标注版本 |
| Ontology spec | EntityType/ValueType、关系、multiplicity、identify_by、requires、IRI 与 mappings | 可参考概念层/物理映射分层；不能等同已有完整可执行 ontology 引擎 |
| ROADMAP | 仍列 grain/aggregation、标准查询语言、reference compiler、治理和版本等建设项 | 交换规范不会自动解决指标编译、权限或跨模型执行 |
| ossie-converters README | 有各厂商转换方向、扩展与 round-trip 建议，当前文档使用 0.2.0.dev0 | 转换器存在不能证明本项目所需字段均可无损互通 |

**建议：内部先固定实际用到的语义契约，建立 Ossie 以及客户已有 dbt/Cube/厂商语义模型的适配。** 每个适配器声明支持的版本、字段、损失报告与测试。客户已治理的指标直接引用已有语义引擎，避免重新生成另一套口径。

选生产交换版本应依据真实消费者，不能因草案表达力更强就全部跟随 `main`，也不能只因 `0.1.1` 稳定就假设它覆盖了本项目的 ontology 和 governance 需求。RDF/OWL 适用于需要外部概念对齐或推理的领域，初版可以不要求图数据库。

## 6. 连接器生态的复用候选

Google MCP Toolbox for Databases 当前仓库已从 `genai-toolbox` 更名 `mcp-toolbox`。本次固定 HEAD `772847cb6d35e0dc6979f6ba13298adcc71b52d4`，已读 README。

- 既提供 list_tables/execute_sql 等预置工具，也提供结构化参数与 SQL 的 custom tools 框架。
- README 明示连接池、IAM、OpenTelemetry 和多数据库支持；这些是官方文档能力，尚未在 Mint 下运行。
- 可作为连接工具实现候选；需收窄可用 toolset、固定数据库权限，再核验 stdio 与目标协议版本。
- 连接器的存在不意味着已经提供业务 ontology、可靠 join 发现、值索引或跨库联邦查询。

额外互通风险：本地 `mint-core/src/mcp/types.rs:13` 与 `:15` 固定当前及回退版本；`mcp/client.rs:375` 的 `tools/call` metadata 仍使用 `MCP_PROTOCOL_VERSION`。本次未运行旧版本服务，不能断言 discover 回退后任意服务的真实调用都兼容。每个候选连接器都要验收发现、握手/回退、调用、错误与长任务，不能仅因支持 stdio 就标记为即插即用。

ClickHouse 官方 MCP README 也提供只读查询、查询验证/成本估算、超时和取消等实践。`DESCRIBE`/`EXPLAIN` 的语义和成本依赖具体引擎，不能统一称作“零副作用的 dry-run”。本次仅文档级阅读，未运行。

### 建议的接入优先级

先文件与一个企业数据库，再覆盖第二方言；客户已有目录和语义层时优先导入。HTTP API 无 SQL 能力时应保留 API 查询计划和能力限制，不能把所有源都伪装成 SQL 库。多源语义检索可以早做，跨库搬运、实体对齐和联邦执行需要独立评估。

## 7. 核验来源

- 本地源码：上述固定 HEAD 的文件；[MCP loader](/Users/payne/Vibe/AgentOS/packages/agent-kernel/mint/crates/mint-core/src/mcp_loader.rs)、[MCP client](/Users/payne/Vibe/AgentOS/packages/agent-kernel/mint/crates/mint-core/src/mcp/client.rs)、[preset](/Users/payne/Vibe/AgentOS/packages/agent-kernel/mint/bins/mint/src/preset.rs)、[契约测试](/Users/payne/Vibe/AgentOS/packages/agent-kernel/mint/crates/mint-core/tests/mcp_tool_contract.rs)。
- [MintHub 当前能力与边界](https://mint-hub.ea.modelbest.co/docs/availability/)，在线抓取，2026-10-30。
- [Ossie README](https://github.com/apache/ossie/blob/7a8de20f850dad3934e307a1ac7425b09e9ca89f/README.md)。
- [Ossie Core spec](https://github.com/apache/ossie/blob/7a8de20f850dad3934e307a1ac7425b09e9ca89f/core-spec/spec.md)。
- [Ossie Ontology](https://github.com/apache/ossie/blob/7a8de20f850dad3934e307a1ac7425b09e9ca89f/ontology/ontology.md)。
- [Ossie ROADMAP](https://github.com/apache/ossie/blob/7a8de20f850dad3934e307a1ac7425b09e9ca89f/ROADMAP.md)。
- [Ossie Converters](https://github.com/apache/ossie-converters/blob/main/README.md)，读取 main，未固定该仓库 SHA。
- [MCP Toolbox](https://github.com/googleapis/mcp-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/README.md)。
- [ClickHouse MCP](https://github.com/ClickHouse/mcp-clickhouse/blob/main/README.md)，读取 main，未固定该仓库 SHA。
- [SQLGlot](https://github.com/tobymao/sqlglot/blob/main/README.md)：已读 AST、方言转换及 unsupported 行为说明，文档级候选，未执行。
- [StatsForecast](https://github.com/Nixtla/statsforecast/blob/main/README.md)：已读模型、交叉验证、区间与外生变量说明，文档级候选，未执行。

资料方法：本轮无通用搜索工具，直接抓取官方文档/raw GitHub 并读本地源码。`paper-reader` 抓取入口因系统 Python 缺少 `trafilatura` 未运行成功，改用直接抓取；没有调用外部 LLM、完整论文解析器或第三方仓库代码。
