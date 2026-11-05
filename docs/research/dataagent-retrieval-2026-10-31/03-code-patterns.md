# 自适应 metadata retrieval：五组可定位的源码机制

日期：2026-10-31。范围：静态阅读固定 Git SHA；复用 10-30、10-31 调研缓存，再补必要函数和调用方。未安装、运行第三方代码，未连接业务数据库，未做召回效果或权限穿透实验。新增缓存均位于 `sources/code-*`；URL、版本、内容 SHA-256 与失败记录见 [code-fetch-manifest.json](sources/code-fetch-manifest.json)。本文的调用示例是静态推演。

**结论：可以复用“带类型的候选对象 + 可独立调用的检索工具 + 程序补齐约束”，不应复用一条全局 table→column→value 必经链。** 但“能从值命中列”“LLM 可选检索工具”“自动补齐合法 join/权限/版本”是三件不同的事。以下项目各覆盖其中一部分，没有一个已读实现证明三者同时完整成立。

## 1. 先看谁决定下一步

| 固定源码 | 可借鉴的实际行为 | LLM 决定什么 | 程序固定什么 | 未证明的能力 |
|---|---|---|---|---|
| WrenAI `8edc086b1f8f9f2974b9faf8ab7c639c85851b46` | `wren_fetch_context(question, item_type, model)` 可直接指定 column/relationship；另有独立 recall 工具 | 接入外部 agent 时，可选择工具与过滤参数 | 小 schema 返回全文，大 schema 向量检索；工具内部不是自由规划器 | 任意值反查、规则类型独立检索、召回后 join 闭包、检索阶段 ACL |
| SuperSonic `ce881947433f07bb8d5469c7c157991046645113` | names/values/aliases 统一匹配；值别名转真实编码；指标、维度、术语等返回类型化对象 | 可配置的 embedding 分支中，筛选已召回的 ID；后续 parser 另有 LLM | mapper 顺序、accept 条件、分词/字典/阈值/配额、工作流状态转移 | LLM 自选 mapper 或任意重新规划检索动作；逐用户值索引隔离 |
| DB-GPT `06a46eea2d248a0f2b3e9096035424df4f2dc2eb` | table chunks→大表 field chunks，用于缩减 schema 上下文 | 本检索器中没有 LLM 动作选择 | 先 table，再对 separated table 检索 field | value-first、指标/规则入口、必要连接表的完整召回 |
| Vanna `365d0617c1a4567ffee1b19b40c27feb4206bfcf` | 可注册独立工具，LLM tool-call loop，执行前再检查工具权限 | 从当轮可见工具中选工具、参数及后续动作 | 工具白名单、group 检查、参数校验、最大迭代数；默认自动检索一部分文本记忆 | 内置完整 metadata 工具集合；每个工具自动具备数据行权限、语义版本或 join 闭包 |
| MCP Toolbox `772847cb6d35e0dc6979f6ba13298adcc71b52d4` | 已有直接 `search-hotels-by-name(name)`、`search-hotels-by-location(location)`，另有 schema 工具 | quickstart 把工具交给 ReAct agent，由模型调用 | 运维者配置工具、SQL 和数据源；工具内部参数化执行 | 自动在未知全库定位任意值；统一企业语义推理 |

“强模型负责调度”只能是可评估的实现选项。工具描述、候选质量、回退动作和停止条件仍须设计；源码没有证明换强模型就会自动解决漏召、同名值或非法 join。

## 2. Wren：直接选择 schema 类型，schema 检索与问答记忆分开

### 真实入口与顺序

外部 agent 可见的 LangChain 工具在 [`sdk/wren-langchain/src/wren_langchain/_tools_memory.py:43`](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/sdk/wren-langchain/src/wren_langchain/_tools_memory.py#L43)：

```python
wren_fetch_context(question, limit=5,
    item_type: Literal["model", "column", "relationship", "view"] | None = None,
    model: str | None = None)
wren_recall_queries(question, limit=3)
```

这两个是独立工具，fetch 的参数不要求先拿到 table。`item_type="column"` 可以直接查列，已知模型时再加 `model` 收窄。工具描述要求写 SQL 前先 fetch，是 agent 指引；这段 wrapper 没有运行一个固定 table→column 链，也没有自己运行完整 agent loop。

调用链是 `wren_fetch_context → toolkit.memory.fetch → _MemoryAPI.fetch → load_manifest → MemoryStore.get_context`。[`_memory_api.py:26`](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/sdk/wren-langchain/src/wren_langchain/_memory_api.py#L26) 把 `model` 改为底层的 `model_name`。[`store.py:313`](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/memory/store.py#L313) 固定执行：

1. `describe_schema(manifest)` 生成结构化全文。
2. 文本不超过阈值时直接返回 `{"strategy":"full","schema":...}`；默认阈值是 30,000 **字符**。
3. 超阈值才 `_search_schema(query, limit, item_type, model_name, mdl_hash)`，向量查询并将三个 metadata 条件以 AND 组合。

**细节：小 schema 分支不应用 item_type/model_name 过滤。** CLI 的 `--type`、`--model` 帮助也明确写明 `search strategy only`。因此不能把此工具描述为始终严格返回指定类型的低体积检索 API。

### 索引、版本、规则与 join 的边界

[`schema_indexer.py:309`](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/memory/schema_indexer.py#L309) 把 model、column、relationship、view 以及 cube/measure/cube_dimension/time_dimension 建成不同 `item_type` 的记录。**底层索引比上述 LangChain 工具的 Literal 枚举更丰富**；不能据底层有 measure 就声称该 wrapper 已完整暴露指标专用工具。该索引提取函数没有独立的 value 或 rule record。生成的 agent 指引另要求首轮 `wren context instructions` 加载业务规则（[`context.py:21`](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/context.py#L21)）。

`manifest_hash` 排除 `_` 开头的内部字段，例如 `_instructions`，再计算 16 位十六进制 schema hash（[`schema_indexer.py:14`](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/memory/schema_indexer.py#L14)）。因此它用于隔离 schema 版本，并非覆盖规则、权限、数据 as-of 的语义 release。

`recall_queries` 在 [`store.py:414`](https://github.com/Canner/WrenAI/blob/8edc086b1f8f9f2974b9faf8ab7c639c85851b46/core/wren/src/wren/memory/store.py#L414) 查询另一张 NL→SQL history 表，仅支持 datasource 过滤；SDK 的 recall wrapper 连 datasource 也未传。它没有 schema 检索同样的 `mdl_hash` 限定。`index_schema` 更新 seed queries、保留用户历史；历史命中仍需按当前 schema/规则验证。

大 schema 的 `_search_schema` 返回 top-k 后即结束，**没有从已选列出发补入 bridge 表、复合键、tenant key 或时间谓词**。relationship 是可检索对象，不等于必要关系已构成闭包。Wren 的下游语义引擎有独立关系/访问控制原语（沿用前两轮已读证据），不能用来替代检索阶段完整性与权限验证。此处 MemoryStore 方法没有传入用户主体/租户策略；应在可见 manifest/索引分区和服务层验证授权。

**可复用点：** 将 schema 获取、历史示例、规则指引拆开；让 caller 直接选择 column/relationship；以版本条件约束索引。需要修改的契约是精确过滤、值入口、规则 release，以及确定性的约束扩展。

## 3. SuperSonic：值可以先命中，但 mapper 调度仍是程序规则

### 真实入口与顺序

[`S2ChatLayerService.map:46`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/server/src/main/java/com/tencent/supersonic/headless/server/facade/service/impl/S2ChatLayerService.java#L46) 先按请求 dataset IDs 构建 `SemanticSchema`，然后对 `ComponentFactory.getSchemaMappers()` 逐个调用 `map`。`parse` 入口进入 [`ChatWorkflowEngine.start:38`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/server/src/main/java/com/tencent/supersonic/headless/server/utils/ChatWorkflowEngine.java#L38)，按 MAPPING→PARSING→校正/翻译等状态推进；`performMapping:96` 在没有现成匹配时执行同一 mapper 列表。

以本次读取的 standalone launcher 为准，[`spring.factories:3`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/launchers/standalone/src/main/resources/META-INF/spring.factories#L3) 声明顺序是 `EmbeddingMapper → KeywordMapper → QueryFilterMapper → PartitionTimeMapper → TermDescMapper → AllFieldMapper`。这是该 launcher 的配置顺序，不代表所有部署固定相同配置。`BaseMapper.map` 先判断 `accept`，执行 `doMap` 后 `MapFilter.filter`；异常记录日志后返回（[`BaseMapper.java:30`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/BaseMapper.java#L30)）。

### 关键实现一：值、别名和维度不是表检索的附属阶段

[`KeywordMapper.doMap:34`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/KeywordMapper.java#L34) 固定先 HanLP 字典匹配，再 `DatabaseMatchStrategy`：

- [`HanlpDictMatchStrategy.detectByStep:33`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/HanlpDictMatchStrategy.java#L33) 对 names/values/aliases 做前缀和后缀检索，按相似度与长度排序、去重、阈值过滤；先取有配额的 dimensionValues，再把剩余位置填入其他元素。值能直接进入候选，不要求先根据自然语言召回一张表。
- 字典的 nature 包含模型/元素标识（[`ValueWordBuilder:26`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/knowledge/builder/ValueWordBuilder.java#L26)）。命中后可以回到所属维度/数据集，而非只返回裸字符串。
- `KeywordMapper.doDimValueAliasLogic:97` 对 VALUE 先做字典 alias→word，再用 `SchemaValueMap.bizName/alias` 转 `techName`。例如“华东大区”已配置为编码 `EAST` 的别名时，可直接得到过滤值 `EAST` 及其维度 ID。此例依赖已建字典/映射，是静态推演。
- 名叫 `DatabaseMatchStrategy` 的本版实现实际遍历已经加载的 metrics/dimensions，做字符串包含与编辑距离过滤；**不是对业务数据库各列执行值探查**（[`DatabaseMatchStrategy.java:48`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/DatabaseMatchStrategy.java#L48)）。

`SchemaMapper` 接口注释称覆盖 metrics/dimensions/entities/values；已读具体分支可确认 METRIC/DIMENSION/VALUE/TAG/TERM 等对象，`SchemaElementType` 枚举含 ID 而没有 ENTITY 枚举。**本文不把接口注释扩展成已经验证的通用实体解析器。**

### 关键实现二：LLM 是候选筛选器，术语可触发再次映射

[`EmbeddingMatchStrategy.detect:64`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/EmbeddingMatchStrategy.java#L64) 先执行基础 detection，配置 `EMBEDDING_MAPPER_USE_LLM` 开启后再增加分词检索与 LLM 筛选；`detectByBatch` 把已召回项传给模型，模型输出 ID 列表，程序以 `retrievedIds.contains(id)` 过滤。它能够排除/保留候选，不能生成一个新合法对象，也不能自由选择调用下一个 mapper。

[`TermDescMapper.doMap:26`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/chat/src/main/java/com/tencent/supersonic/headless/chat/mapper/TermDescMapper.java#L26) 将已命中术语的 description 作为新 query 再跑 mapper 列表，并以 `descriptionMapped=true` 避免递归重入。这是“术语→描述→相关指标/维度/值”的程序化扩展，可借鉴为规则/定义入口；它本身不等于规则冲突检测或可执行规则推理。`QueryFilterMapper` 还能把上游已结构化的 filter 直接注入 VALUE 候选；`AllFieldMapper` 仅在 ALL 模式回填全部 metrics/dimensions，是明确的回退策略。

### join、版本、ACL

mapper 返回 `SchemaElementMatch` 和 dataset/type/id，没有在本链路中运行必要 join 集合闭包。下游 [`SemanticSchemaManager.buildOntology:35`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/server/src/main/java/com/tencent/supersonic/headless/server/manager/SemanticSchemaManager.java#L35) 把 metrics/dimensions/models 和已有 `modelRelas` 组装成 ontology；这证明结构化关系可供编译，不证明召回遗漏、fanout、复合键和有效期已被验证。

`SchemaServiceImpl.buildDataSetSchema` 以 ONLINE 状态和 dataset/model IDs 读取元数据，未见类似不可变 semantic release 的统一限定。`map(QueryMapReq)` 有 user-aware dataset 选择；较底层 `map(QueryNLReq)`→`getSemanticSchema(ids)` 没有直接传 User。另有 [`S2DataPermissionAspect:90`](https://github.com/tencentmusic/supersonic/blob/ce881947433f07bb8d5469c7c157991046645113/headless/server/src/main/java/com/tencent/supersonic/headless/server/aspect/S2DataPermissionAspect.java#L90) 在数据查询时做 model/column/row 权限，但 `needAuth=false` 及 model admin 存在提前返回。因此不能据查询执行权限推定检索出来的值和术语已经按用户过滤。入口拦截、缓存分区与敏感值泄露仍需集成验证。

**可复用点：** 类型化匹配结果、值字典反向定位、业务别名到技术编码、术语扩展、显式回退。若 DataAgent 需要自主检索，应把这些能力包装成可独立选择的工具，不能把现有 mapper 状态机直接称为 agent planner。

## 4. DB-GPT：table→field 是一个局部优化器，不能成为全局架构约束

[`DBSchemaRetriever._similarity_search:203`](https://github.com/eosphoros-ai/DB-GPT/blob/06a46eea2d248a0f2b3e9096035424df4f2dc2eb/packages/dbgpt-ext/src/dbgpt_ext/rag/retriever/db_schema.py#L203) 的固定顺序是：

```text
table_vector_store.similar_search(query, top_k, filters)
  ├─ 非 separated：直接反序列化为 DDL 风格上下文
  └─ separated：对每张命中表 _retrieve_field(table_chunk, query)
       → table metadata + part=field 构造 filters
       → field_vector_store.similar_search(query, top_k, filters)
       → 拼回该表字段，反序列化
```

分表 field 任务并发上限为 3。这里 LLM 不决定检索动作；表级候选决定字段搜索空间。某列/编码只存在于未被 table top-k 命中的表中时，此函数没有路径去找它。`db_summary_version` 用于解析/重建摘要，不能自动等价为业务定义 release。外部 filters 可收窄候选，但本方法没有主动绑定身份或补齐 join 约束。

**适用条件：** table 入口已合理、表描述足以召回目标、宽表字段多时可节省上下文。**对 DataAgent 的用法：** 把它作为 `search_schema` 某种后端策略；用户给编码、枚举值、指标名或业务规则时，不应强制经过这一支。

## 5. Vanna：可选工具的 agent loop 与固定 RAG 必须分开

### 新 Agent 的真实工具循环

[`Agent._send_message`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/core/agent/agent.py#L564) 先 `tool_registry.get_schemas(user)`，构建带 tools 的 LLM request；从 `:646` 起，在 `max_tool_iterations` 内处理 `response.tool_calls`，逐个经 `registry.execute` 执行（`:827`），把结果加入 conversation，再构建下一轮 request（`:1009`）。模型选择工具和参数，程序控制校验、执行和循环上限。

[`ToolRegistry.register_local_tool:63`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/core/registry.py#L63) 接收任意符合 Tool 接口的工具，并用 `get_schemas(user)` 按 groups 过滤模型可见工具；执行时再次检查 groups、Pydantic 参数、`transform_args` 后才调用 tool。**默认 transform_args 是 NoOp。** 工具权限与 SQL 行权限、metadata 值可见权限是不同边界。

这允许调用方注册 `search_values`、`search_metrics`、`get_relationships` 等独立工具，并由 LLM 选择入口；这些名称是给 DataAgent 的设计建议，不是声称 Vanna 已内置。**不能把注册式扩展称为默认按需发现工具：** 本版 Agent 每条用户消息开始取一次 `tool_schemas`，工具循环中复用该列表，没有每次行动后自动刷新工具集。

### 检索并非全部交给模型

显式工具 [`SearchSavedCorrectToolUsesTool:120`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/tools/agent_memory.py#L120) 允许 `question/limit/similarity_threshold/tool_name_filter`，通过注入的 `AgentMemory.search_similar_usage` 召回既往工具用法。另有默认 [`DefaultLlmContextEnhancer.enhance_system_prompt:41`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/core/enhancer/default.py#L41)，程序根据用户消息自动 `search_text_memories(limit=5)` 并追加到 prompt，失败则返回原 prompt。这是“自动初始上下文 + 模型可选工具”的混合模式。

legacy [`generate_sql:93`](https://github.com/vanna-ai/vanna/blob/365d0617c1a4567ffee1b19b40c27feb4206bfcf/src/vanna/legacy/base/base.py#L93) 则固定依次 `get_similar_question_sql → get_related_ddl → get_related_documentation → get_sql_prompt → submit_prompt`。模型返回 intermediate_sql 后，只有开启 `allow_llm_to_see_data` 才运行探查、把 DataFrame 送回第二轮 prompt。它可探查值，但不是新 agent 的工具调度，也没有因此变成统一 metadata graph。

在本次已读 Agent/registry/memory 接口里，没有自动 join 闭包、不可变语义发布号、默认数据权限注入。memory backend 是否按 tenant/user/release 隔离取决于实现，不能由 `ToolContext.user` 的存在推出隔离已生效。

**可复用点：** typed tool 参数、按用户展示工具和执行复查、结果反馈给模型、有限迭代；DataAgent 自行提供受控检索工具、结构化缺失证据和闭包检查。

## 6. MCP Toolbox：一个真实 value-first API，但作用域是预配置的数据源

固定 SHA 的官方 [`configure_toolbox.md:85`](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/docs/en/documentation/getting-started/quickstart/shared/configure_toolbox.md#L85) 定义：

```yaml
name: search-hotels-by-name
parameters: [{name: name, type: string, description: The name of the hotel.}]
statement: SELECT * FROM hotels WHERE name ILIKE '%' || $1 || '%';
```

旁边是独立的 `search-hotels-by-location(location)`。输入只有值，调用者不需要先 list tables、读 DDL 再选列。表/列知识由工具作者配置，模型只需选语义明确的工具与值。

[`quickstart/python/langchain/quickstart.py:36`](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/docs/en/documentation/getting-started/quickstart/python/langchain/quickstart.py#L36) 是 `aload_toolset → create_react_agent(model, tools) → agent.invoke`。这证明示例把动作选择交给 agent；没有运行此例，也不声称实际模型必然先选某个工具。

工具内部 [`postgressql.Tool.Invoke:92`](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/internal/tools/postgres/postgressql/postgressql.go#L92) 解析 template 参数及 standard 参数，再 `source.RunSQL(statement, sliceParams)`。此例使用绑定参数 `$1`；模板替换另有边界，不能笼统称所有配置均参数化安全。

独立 [`postgreslisttables.Config.Initialize:145`](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/internal/tools/postgres/postgreslisttables/postgreslisttables.go#L145) 暴露 `table_names` 与 `output_format=simple|detailed`；`Invoke:169` 查询 PostgreSQL catalog，返回列、约束、外键目标、索引等 JSON。可以按需获取 schema；返回外键约束不等于自动补齐完整合法 join 路径。

**范围限制：** 酒店例子是已配置 domain 的直接值查询，不是跨未知表的倒排值索引，也没有统一 semantic release。它说明工具表面可以 value-first，并不说明无需元数据建模。工具调用权限可配置 `authRequired`/scopes，文档还支持把已验证身份 claim 注入 SQL 参数（[`tools/_index.md:399`](https://github.com/googleapis/genai-toolbox/blob/772847cb6d35e0dc6979f6ba13298adcc71b52d4/docs/en/documentation/configuration/tools/_index.md#L399)）；本轮未沿服务器认证实现验证，示例 SQL 也没有租户条件。工具集授权、数据库权限、值结果可见性及预算仍须分别配置。

**可复用点：** 为常见值/实体查找提供窄参数工具；把 schema、值、指标和规则获取分别暴露；由可信配置指定 SQL/数据源/身份参数。不要为了从名字找对象，强迫模型先猜物理表列。

## 7. 对 DataAgent 的最小组合建议

以下是设计推演，不是上述项目已有完整产品能力：

1. **入口不互相强制依赖。** `find_values(text, scope?)`、`find_columns(text, scope?)`、`find_metrics(text, scope?)`、`find_rules(text, scope?)` 都能起步；scope 未知时在当前用户可见空间检索，不能隐式变成先选表。支持同轮多个检索动作。
2. **返回对象与证据。** 值返回候选所属 column/entity/dataset、标准值/编码、匹配方法和歧义；指标返回定义 ID、grain、依赖与 release；规则返回适用对象、优先级/生效区间和来源。裸 top-k 文本不足以驱动后续动作。
3. **模型选动作，程序验证集合。** 类似 Vanna 的工具 loop 负责选下一次查值、查列、查指标、查规则或澄清；确定性 resolver 在要生成查询前补依赖列、复合键、bridge、时间有效期、tenant 条件和策略约束。闭包不是继续扩大 top-k。
4. **索引与历史共同约束版本/权限。** 借鉴 Wren hash，但绑定 schema + semantic release + rule/policy version；缓存 key 和历史示例也必须受相同可见范围约束。授权条件来自身份服务，不能让模型通过参数扩大范围。
5. **停止取决于覆盖证据。** 已获得指标定义、筛选值定位、聚合粒度和合法连接证据才生成查询；冲突/缺失时返回具体缺项。强模型、reranker 和更高预算都应在 value-first/column-first/metric-first/rule-first 的分组评估中比较，不预先承诺自主调度效果。

## 8. 许可与核验边界

| 固定范围 | 已读根许可事实 | 复用边界 |
|---|---|---|
| Wren core/sdk 源码 | 根 LICENSE 按路径给 core/sdk Apache-2.0，docs CC BY 4.0；发布制品的 manifest 优先 | 需保留对应许可/通知；不据此推定商标、商业权限产品或全部制品条款 |
| Vanna、DB-GPT 已读路径 | 根 LICENSE 为 MIT | 模型、存储后端、驱动、远程服务条款另核 |
| SuperSonic | Apache-2.0 外附加商业条款；开发并分发 derivative work 要商业许可 | 本文用于机制研究；复制/派生代码前核目标用法，不列为无条件 Apache fork 候选 |
| MCP Toolbox 已读路径 | 根 LICENSE 为 Apache-2.0，Go 文件有对应头 | 不涵盖托管数据库、模型服务和各客户端依赖条款 |

许可证缓存分别为 `code-wren-LICENSE`、`code-vanna-LICENSE`、`code-dbgpt-LICENSE`、`code-supersonic-LICENSE`、`code-toolbox-LICENSE`，来源均是上表 SHA。未做依赖授权闭包或法律审计。

本轮验证的是源文件存在、固定 SHA、真实符号/调用顺序和缓存完整性。53 次抓取/复用记录中有 52 个成功缓存，SHA-256 全部核对一致；30 个报告固定 SHA 链接均能映射到缓存，行锚点在文件范围内。`src/vanna/core/system_prompt/default.py` 抓取因 SSL EOF 失败，报告不据其内容下结论，失败记录保留在 manifest。未验证：多入口实际召回率与必要集合覆盖率、LLM 动作稳定性、中文别名噪声、高基数值开销、权限/租户索引隔离、完整 join 编译路径、并发 schema 更新、语义版本回放，以及上述工具客户端的实际兼容性。workspace 当前不是 Git checkout，不提供本地产品 commit；本轮没有修改产品代码。
