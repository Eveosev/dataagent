# B · 开源 Data Agent / Text-to-SQL / 语义层 / 目录：代码级调研

> 调研日期 **2026-10-30**。star 数经 GitHub REST API 与 ungh 镜像读取（同一日），License 尽量直接读仓库 `LICENSE` 原文；标 **†** 者为仅依据仓库徽章/包元数据（PyPI `license_expression`）判断、未逐字核对 LICENSE 文件；标「未核实」者不做推断。web_search 本次不可用，检索依赖 GitHub API/raw 文件与官方文档直连。

## 1. 执行摘要

开源栈已能覆盖 DataAgent 约八成工作量，可复用的三段是「语义层（MDL/Cube YAML）、连接器（MCP）、执行与可视化（DuckDB/Polars/Evidence）」。**WrenAI**（18.0k★，core/ 为 Apache-2.0）的 MDL 是当前最适合当 ontology 参考的 schema：模型/关系/视图/cube 与 `knowledge/`（规则、术语、NL-SQL 对）分层，且 MDL 与知识各自独立 `schema_version`。**DB-GPT**（20.2k★，MIT）给出最完整的 agent+AWEL 工作流+沙箱组织方式；**Cube**（21.1k★）、**SuperSonic**（5.1k★）可作语义层与 Headless BI 参照；**MCP Toolbox**（16.8k★）与 **DBHub**（3.8k★）是连接器成熟度基准。真正缺的是：产品级「自动 join/关系推断」、语义层版本化后的 agent 召回、开箱行级权限（RLS）——三者均无开源先例，须自研。许可证是最大暗礁：Chat2DB 5.3+ 已改为禁对外提供服务的修改版 Apache，SuperSonic 附加商业条款，WrenAI 预留 AGPL 模块。

## 2. 项目清单大表

### 2.1 语义层 / 建模

| 项目 | 仓库 | License | ★ | 语言 | 定位 | 复用建议 |
|---|---|---|---|---|---|---|
| WrenAI | Canner/WrenAI | Apache-2.0（core/sdk/skills）+ docs CC-BY-4.0，预留 AGPL-3.0 模块 | 18,011 | Rust/Python/TS | GenBI 引擎：MDL 语义层 + 治理 SQL + MCP | **首选参考**，MDL schema 直接借鉴 |
| wren-engine | Canner/wren-engine | 同源 | 660 | Rust | 已并入 WrenAI `core/`（2026-05-07），仓库归档 | 不要单独依赖 |
| Cube Core | cube-js/cube | Apache-2.0 为主，少量 MIT | 21,129 | TS/Rust | 语义层 + pre-aggregation + SQL/REST/GraphQL API | 复用语义编译与预聚合思路；单机重 |
| MetricFlow | dbt-labs/metricflow | Apache-2.0（PyPI `dbt-metricflow` 0.15.0，2026-09-10） | 1,853 | Python | dbt 语义层指标引擎 | 指标定义/编译参考；依赖 dbt-core 全家桶 |
| Malloy | malloydata/malloy | MIT | 2,608 | TS/Go | 建模语言 + 查询编译器（关系即类型） | 借鉴「关系内建于语言」表达；生态小 |
| Lightdash | lightdash/lightdash | MIT（`packages/backend/src/ee` 除外） | 6,214 | TS | LookML 的 dbt 系开源替代，Agentic BI | 复用「指标即代码 + 维度下钻」UX |
| Apache Ossie（原 OSI） | apache/ossie | Apache-2.0 | 2,582 | Python/JSON Schema | 厂商中立的语义模型交换规范（JSON/YAML） | **做导出/互操作标准**，避免自造协议 |

### 2.2 NL2SQL / 分析 Agent

| 项目 | 仓库 | License | ★ | 语言 | 定位 | 复用建议 |
|---|---|---|---|---|---|---|
| DB-GPT | eosphoros-ai/DB-GPT | MIT | 20,215 | Python | agentic 数据助手：agents/AWEL/RAG/skills/sandbox | **首选流程参考**，学其 agent+workflow 分层 |
| Vanna | vanna-ai/vanna | MIT | 23,804 | Python | RAG 式 text-to-SQL（DDL/文档/SQL 三元组检索） | 直接复用「示例对 + 向量召回」；2026-02 后低活跃 |
| Dataherald | Dataherald/dataherald | Apache-2.0 | 3,649 | Python | NL2SQL 服务（含 golden SQL、评估） | 已停滞（末次 push 2024-07），只作设计抄本 |
| SQLCoder | defog-ai/sqlcoder | Apache-2.0† | 4,044 | Python | 专用 NL2SQL 模型权重+推理脚本 | 末次 push 2024-05，仅作 baseline |
| Defog analyst | — | — | — | — | 原 OSS analyst 仓库已 404，产品转闭源 | 未核实，勿规划依赖 |
| DBCopilot | tshu-w/DBCopilot | **无 LICENSE 文件**（EDBT 2025 论文代码） | 137 | Python | 大规模库的 schema routing（草图检索+路由） | 只读论文与路由思路，代码不可直接商用 |
| SuperSonic | TencentMusic/SuperSonic | Apache-2.0 **+ 附加条款**（衍生分发需商业授权） | 5,148 | Java | Chat BI + Headless BI 双引擎，中文语义解析 | 借鉴双引擎架构；许可需法务过 |
| Chat2DB | OtterMind/Chat2DB | 修改版 Apache-2.0（`LicenseRef-Chat2DB`，5.3.0 起） | 28,347 | Java/TS | 40+ 库客户端 + AI SQL + MCP | **仅内部使用**；不得对外提供服务 |
| MindsDB | mindsdb/mindshub | MIT | 39,831 | Python | 把 ML/agent 当虚拟表接入库 | 概念可借；架构过重 |
| LangChain | langchain-ai/langchain | MIT | 148,676 | Python | `SQLDatabaseChain`/SQL agent 工具箱 | 复用工具封装与 schema 提示词 |
| LlamaIndex | run-llama/llama_index | MIT | 52,735 | Python | `NLSQLTableQueryEngine`、表检索 | 复用表/列检索器 |
| Datus | Datus-ai/Datus-agent | Apache-2.0 | 1,875 | Python | CLI SQL 客户端 + 上下文工程（新秀，极活跃） | 参考「context engineering」命令面 |
| PandasAI | sinaptik-ai/pandas-ai | MIT Expat（`pandasai/ee/` 除外） | 23,910 | Python | 自然语言问 CSV/数仓 | 复用 dataframe 交互层 |
| Julius | — | 闭源 SaaS | — | — | 无开源仓库 | 仅作产品对标 |
| DataLine | — | 未核实 | — | — | 未找到对应开源项目 | 不纳入 |

### 2.3 元数据 / 血缘 / 剖析

| 项目 | 仓库 | License | ★ | 语言 | 定位 | 复用建议 |
|---|---|---|---|---|---|---|
| DataHub | datahub-project/datahub | Apache-2.0 | 12,929 | Java/Python | 元数据+血缘+「上下文平台」 | 复用 PDL 实体模型/血缘图；部署重 |
| OpenMetadata | open-metadata/OpenMetadata | Apache-2.0† | 15,629 | Java/TS | 目录 + 术语表 + 数据契约 | 复用 glossary/metric 实体设计 |
| Amundsen | amundsen-io/amundsen | Apache-2.0† | 4,785 | Python | 目录（表/列/owner） | 轻量，适合内嵌 |
| OpenLineage | OpenLineage/OpenLineage | Apache-2.0† | 2,730 | Java/Python | 血缘事件标准 | 事件 schema 直接采用 |
| SQLGlot | tobymao/sqlglot | MIT | 9,736 | Python | SQL 解析/转写/优化（20+ 方言） | **必用**：方言归一、列级血缘、dry-plan |
| sqlparse | andialbrecht/sqlparse | BSD-3† | 4,022 | Python | 非校验式解析（仅格式化/切分） | 只用于展示层 |
| Metanome | HPI-Information-Systems/Metanome | Apache-2.0† | 197 | Java | 剖面 + IND/UCC/FD 发现平台 | 学术级，末次 push 2025-06 |
| IND 算法集 | HPI-Information-Systems/inclusion-dependency-algorithms | Apache-2.0 | 13 | Java | Spider/Binder/Mind 等 IND 算法实现 | **唯一可用 IND 参考**，2019 后停更 |
| DataProfiler | capitalone/DataProfiler | Apache-2.0† | 1,594 | Python | schema/统计/实体识别 | 直接复用探查器 |
| ydata-profiling | Data-Centric-AI-Community/fg-data-profiling（原 ydataai/ydata-profiling） | MIT† | 13,743 | Python | 一行 EDA 报告 | 复用 HTML 报告生成 |
| Great Expectations | fivetran/great_expectations | Apache-2.0† | 11,908 | Python | 数据质量断言套件 | 复用 expectation 语义做「体检」 |
| soda-core | sodadata/soda-core | Apache-2.0† | 2,458 | Python | SodaCL 数据契约扫描 | 复用 YAML 契约 DSL |

### 2.4 文件/表格分析 + MCP 数据连接器生态

| 项目 | 仓库 | License | ★ | 语言 | 定位 | 复用建议 |
|---|---|---|---|---|---|---|
| DuckDB | duckdb/duckdb | MIT | 42,674 | C++ | 嵌入式分析库（可直读 parquet/CSV/HTTP） | **本地执行首选** |
| Polars | pola-rs/polars | MIT | 40,229 | Rust | 列式 DataFrame | 复用大文件处理 |
| Arrow | apache/arrow | Apache-2.0† | 17,250 | 多语言 | 列式内存标准 | 跨进程零拷贝 |
| Evidence | evidence-dev/evidence | MIT | 7,077 | TS/Svelte | BI as code（Markdown+SQL） | 复用报表 DSL |
| Rill | rilldata/rill | Apache-2.0† | 2,971 | Go/TS | 面向 agent 的快速 BI | 复用 metrics view 定义 |
| Marimo | marimo-team/marimo | Apache-2.0 | 23,369 | Python | 响应式 notebook（纯 .py 可 git） | 复用「notebook 即文件」做产物 |
| SheetJS | SheetJS/sheetjs | Apache-2.0† | 36,345 | JS | 表格解析/导出 | GitHub 已于 2024-04 停更，迁 git.sheetjs.com |
| Univer | dream-num/univer | Apache-2.0† | 22,798 | TS | 表格/文档「Office Harness for AI Agents」 | 复用前端表格运行时 |
| Grist | gristlabs/grist-core | Apache-2.0† | 12,021 | TS/Python | 关系型电子表格 | 复用「表格+Python 列」模型 |
| MCP servers | modelcontextprotocol/servers | **MIT→Apache-2.0 迁移中**（新贡献 Apache-2.0） | 91,683 | TS/Python | 官方参考 server（postgres/sqlite 等） | 参考实现，勿当生产网关 |
| MCP Toolbox | googleapis/mcp-toolbox | Apache-2.0 | 16,754 | Go | 数据库 MCP 框架（BigQuery/Spanner/PG/MySQL/Snowflake…） | **连接器层首选**，tools.yaml 即策略 |
| dbt MCP | dbt-labs/dbt-mcp | Apache-2.0† | 614 | Python | 暴露 dbt 模型/指标/ lineage | 语义层检索入口 |
| Snowflake MCP | Snowflake-Labs/mcp | Apache-2.0† | 303 | Python | Snowflake + Cortex + 语义视图 | 云上场景参考 |
| Postgres MCP Pro | crystaldba/postgres-mcp | MIT | 3,444 | Python | 读写分级 + 索引/执行计划调优 | 复用「受限模式 + 性能分析」 |
| DBHub | bytebase/dbhub | MIT | 3,753 | TS | 极简多库 MCP 网关（6 种库，只读/限行/超时） | **token 最省**（默认 2 工具 1.4k tokens） |
| Databricks ai-dev-kit | databricks-solutions/ai-dev-kit | 未核实 | 1,975 | Python | Databricks MCP/工具集（Field Engineering 出品） | 非官方产品，谨慎 |

## 3. 重点五个项目架构拆解

### 3.1 WrenAI：MDL 与「语义层 + 上下文层」的双层结构

```
CLI/SDK (wrenai, wren-langchain, wren-pydantic) ── MCP server ── 外部 agent(Claude Code/Cursor)
        │
        ├─ MDL 源文件  models/ relationships.yml views/ cubes/  wren_project.yml(schema_version:5)
        │      └─ wren context build ─► target/mdl.json (camelCase, 引擎线格式)
        ├─ knowledge/  rules/(业务规则 md) glossary/ metrics/ caveats/ sql/(NL→SQL 对)
        │      └─ wren memory index ─► .wren/memory (LanceDB, 混合检索, gitignore)
        └─ wren-core (Rust + Apache DataFusion, 22+ 连接器) ─► dry-plan 校验 ─► 行数上限 ─► 执行
```

MDL 字段面（可直接映射 ontology）：`models[].table_reference|ref_sql`、`columns[]`（`is_calculated`/`expression`/`is_primary_key`/`relationship`/`is_hidden`）、`relationships[]`（`join_type` 四值 + 仅支持等值 `condition`）、`views[].statement`、`cubes[]{measures,dimensions,time_dimensions,hierarchies}`。两个关键设计值得抄：① **列不暴露即列级权限**——未在模型中声明的列对 agent 物理不可见；② **MDL 与 knowledge 的 `schema_version` 解耦**，知识层可独立演进。坑：relationship handle 不能在 SELECT 中直接穿越（`orders.customer.first_name` 报 `No field named`，issue #2688），只能经 calculated column 走；`TO_MANY` 穿越必须带聚合。

### 3.2 DB-GPT：agent + AWEL 的分层工作流

```
应用层   apps / skills(prompt+工具+流程包) / Web(5670)
编排层   Agent(task planning, ReAct/CodeAct) ⇄ AWEL DAG(operator: input/map/reduce/join/branch/trigger)
能力层   RAG 检索 · 数据源连接器(DB/CSV/Excel/知识库) · 代码解释器
基础层   SMMF 多模型适配(vLLM/OpenAI/DeepSeek/Qwen…) · 向量库 · 沙箱执行 · 存储
```

可借鉴的是「**流程可声明、可复用、可落盘**」：AWEL 把编排写成 DAG（而非埋在 prompt 里），skills 把领域知识打包成可安装单元，沙箱隔离代码执行。对我们意味着：DataAgent 的探查/建模/问答应是三条显式 DAG，而非一个万能 chat loop。

### 3.3 Cube：语义层即编译器

`model/cubes/*.yml`（measures/dimensions/joins/segments）+ `views/` → 编译期生成 SQL → 查询 API（REST/GraphQL/SQL）+ **pre-aggregations**（rollup 物化 + 刷新策略）。其价值在「一份定义、多种消费面」与预聚合路由；代价是需要 Cube Store（Rust）与独立服务，单机嵌入不划算。

### 3.4 SuperSonic：Chat BI 与 Headless BI 双引擎

```
用户问句 ─► 语义解析器(词典/映射/LLM) ─► 语义查询(S2SQL DSL) ─► 物理 SQL ─► 引擎
                    ▲                                          │
              语义层(主题域/指标/维度/标签)  ◄── 映射与干预校正 ◄──┘
```
它的差异化是「中文词典 + 人工干预校正 + 指标平台」闭环，适合中文企业语境；但 Java 单体 + 附加许可条款，不适合直接嵌入。

### 3.5 MCP Toolbox / DBHub：连接器与工具面收敛

```
agent ──MCP(http/stdio)──► Toolbox: tools.yaml{sources, tools(SQL模板+参数), toolsets, prompts, resources}
                              ├─ 参数化 SQL（不接受自由 SQL）
                              ├─ authorized parameters（认证注入参数→行级过滤）
                              └─ OTel 观测 + 连接池 + IAM
```
对照实验数据（DBHub README 自测）：DBHub 默认 2 工具 **1.4k tokens**，MCP Toolbox 默认 28 工具 **19.0k tokens**。这直接决定 agent 的上下文预算——工具面必须收敛，MCP Toolbox 的价值在「预定义参数化工具 + 按 toolset 分组」，而不是把库的所有能力都暴露。

## 4. 可复用组件清单（按三项能力归类）

**A. 探查与上下文构建（可直接复用为主）**
- schema 抽取：SQLAlchemy inspector / DuckDB `information_schema` / `sqlglot` 解析 DDL 与列级血缘（MIT）。
- 数据剖析：DataProfiler（列统计+实体）、fg-data-profiling（HTML 报告）、GX/soda-core（契约式体检）。
- 采样执行：DuckDB 直读 parquet/CSV/Postgres（`ATTACH`），本地零运维。
- 元数据落库：轻量用 Amundsen 实体，重场景用 DataHub/OpenMetadata；血缘事件用 OpenLineage schema。
- **缺口**：IND/关系发现只有 Metanome + 2019 年的 Java 算法集（Apache-2.0），无 Python 产品级实现。

**B. 语义层（参考 schema + 局部复用）**
- 直接抄结构：MDL 的 `models/relationships/views/cubes + knowledge/` 目录与 `schema_version` 演进策略（v2 目录化→v3 dialect→v4 复合主键→v5 knowledge）。
- 直接复用：`sqlglot` 做 dialect 归一与语义 SQL→物理 SQL；`Ossie`（apache/ossie）做导入导出互操作；`dbt-mcp` 做 dbt 指标召回。
- 不要自造：指标表达（measure/dimension/time_dimension/hierarchy）已被 Cube/MetricFlow/MDL 三重验证，照抄即可。

**C. NL2SQL / 执行 / 可视化**
- 检索式 NL2SQL：Vanna 的「DDL+文档+历史 SQL 对」三库召回是最省算力的路线，配合 MDL 而非裸 schema 做上下文。
- 编排：DB-GPT 的 agent+AWEL 分层、沙箱执行、skills 打包。
- 执行：DuckDB（本地/文件）+ 各库 MCP（远端）；dry-plan/EXPLAIN 前置校验 + 行数上限 + 超时（DBHub/Postgres MCP Pro 已实现）。
- 可视化：Evidence（Markdown+SQL 报表）、Rill（metrics view）、Marimo（可 git 的 notebook 产物）、Univer/SheetJS（表格进出）。

## 5. 自研 gap 与风险

1. **自动 join / 关系推断（必须自研）**：开源现状=学术 IND 发现（Metanome 197★、IND 算法集 13★ 且 2019 停更）+ 语义层里**手写** relationships。没有任何项目做「候选生成（命名/类型/值重叠/基数）→ LLM 判定 → 采样 SQL 验证 → 置信度入库」。这正是 MintHub 的差异化点，建议做成 `probe → candidates → verify → propose` 四段流水线，产出物写回语义层并留证据链。
2. **语义层版本化 + agent 召回（半自研）**：WrenAI 是最接近的先例（Git Sync + `knowledge/sql` + LanceDB 混合检索），但 Git Sync 的托管部署属 Cloud；本地只有文件 + 索引，**没有**「MDL diff → 影响面分析（哪些指标/查询失效）→ 召回重排」。需要自研语义层 diff 与影响分析。
3. **行级/列级权限（必须自研）**：WrenAI 的 RLS/CLS 是商业版；MCP 生态只有粗粒度（DBHub 只读模式/限行/超时、Postgres MCP Pro 受限模式、Toolbox authorized parameters）。**没有开源 RLS DSL**。建议在语义层里表达策略，在自有网关强制执行（而非依赖数据库账号）。
4. **许可证雷区**：Chat2DB 5.3+ 禁「对外提供服务/白标/OEM」；SuperSonic 衍生分发需商业授权；WrenAI 预留 AGPL 模块（当前 core 为 Apache-2.0，需持续跟踪路径表）；Lightdash/PandasAI 的 `ee/` 目录另有许可；MCP servers 正处于 MIT→Apache-2.0 过渡（混用文件按原许可）。打包前需按路径做许可证清单。
5. **维护状态**：Dataherald（2024-07 停）、SQLCoder（2024-05 停）、wren-engine（归档）、SheetJS GitHub（2024-04 迁站）、DBCopilot（无 LICENSE）。**未核实**：Databricks/Snowflake/BigQuery 的「官方托管 MCP」现状、Julius 开源部分、DataLine 项目。

## 6. 对 MintHub 打包的启示

- **ontology 直接用 MDL 作骨**：`project.yml(schema_version)` + `models/` + `relationships.yml` + `views/` + `cubes/` + `knowledge/{rules,glossary,metrics,caveats,sql}`，编译产物与源分离（源 YAML 进 git，索引/编译物 gitignore）。这样天然获得「可 review、可 diff、可携带」。
- **三层打包**：`connector pack`（MCP + 只读网关 + 审计）／`semantic pack`（MDL + 指标 + 术语 + 示例对）／`analysis pack`（notebook/报表产物 + 证据）。每层独立版本号。
- **工具面收敛是硬约束**：默认工具 ≤5 个、≤2k tokens（对标 DBHub 1.4k），把「探查/建模/查询」做成三组按需加载的 toolset，而不是全量暴露。
- **执行双轨**：本地/文件走 DuckDB（零依赖、可离线），远端走 MCP；统一在网关做只读校验、行数上限、超时、EXPLAIN 预检。
- **互操作留后门**：语义层提供 Ossie（原 OSI）与 dbt MetricFlow 的 import/export，避免客户已有 dbt 资产时被锁死；对外叙事用「MDL 兼容」而非「私有格式」。
- **不重复造**：SQL 解析/转写用 sqlglot，剖析用 DataProfiler+fg-data-profiling，质量断言用 GX/soda 语义，报表用 Evidence/Rill 思路；把工程预算集中在**关系推断、语义 diff、权限网关**三处。

### 主要链接
- WrenAI https://github.com/Canner/WrenAI · MDL schema https://github.com/Canner/WrenAI/blob/main/docs/core/reference/mdl.md · 架构 https://docs.getwren.ai
- DB-GPT https://github.com/eosphoros-ai/DB-GPT · AWEL https://docs.dbgpt.cn/docs/awel/tutorial
- Cube https://github.com/cube-js/cube · MetricFlow https://github.com/dbt-labs/metricflow · PyPI https://pypi.org/project/dbt-metricflow/
- Apache Ossie https://github.com/apache/ossie · SuperSonic https://github.com/TencentMusic/SuperSonic
- MCP Toolbox https://github.com/googleapis/mcp-toolbox · DBHub https://github.com/bytebase/dbhub · Postgres MCP Pro https://github.com/crystaldba/postgres-mcp
- Metanome https://github.com/HPI-Information-Systems/Metanome · IND 算法 https://github.com/HPI-Information-Systems/inclusion-dependency-algorithms · DBCopilot https://github.com/tshu-w/DBCopilot
- DataHub https://github.com/datahub-project/datahub · OpenMetadata https://github.com/open-metadata/OpenMetadata · OpenLineage https://github.com/OpenLineage/OpenLineage · sqlglot https://github.com/tobymao/sqlglot
