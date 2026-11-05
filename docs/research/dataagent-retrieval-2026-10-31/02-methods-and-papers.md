# Text2SQL 召回与探索：论文和官方实现证据

调研与访问日期：2026-10-31（Asia/Shanghai）。本文只回答“表、字段、值、业务术语是否必须按固定顺序召回，以及哪些方法真的让模型选择下一步探索动作”。这是方法综述，不是统一条件下的成绩比较，也不代表已在 AgentOS 中实现或运行这些系统。

## 1. 结论

用户的问题可以从值、字段名或业务术语开始；“先选表，才能查字段和值”不是 Text2SQL 的必要约束。CHESS 的全库值索引检索可直接返回值所属的表和列；RAT-SQL 将问题词、列、表及值匹配关系共同编码。两者都为“值反向帮助定位列/表”提供一手证据，但都不能据此被描述为全局自由规划的检索 Agent。

同时，需要区分四件事：多种证据各自召回后合并、正反向召回覆盖遗漏、预设条件触发的迭代探索、模型基于工具观察选择下一动作。它们可以组合，不能统一归为“agentic retrieval”。APEX-SQL 和 Spider-Agent 给出了较强的动态动作选择证据；APEX-SQL 依然保留 schema linking → SQL generation 的宏观两阶段结构。

| 方法 | 起始证据与传播路径 | 谁决定顺序/下一步 | 本文分类 |
| --- | --- | --- | --- |
| RAT-SQL | 问题词↔列/表名称、问题词↔列值匹配，再加 schema 关系 | 预定义关系构造 + 学习的 attention；没有工具策略 | 多关系联合编码；支持值→列链接 |
| CHESS | 关键词→全库相似值→所属列/表；另查 catalog 描述 | 外层 Agent 按配置连成链；局部模型选择工具；索引内部流程固定 | 多类型召回 + 局部受限工具选择，非全局任意遍历 |
| RSL-SQL | question→schema，与完整 schema 上初步 SQL→schema 并集 | 固定四阶段，修复为规则触发循环 | 双向召回/覆盖 + 完整/裁剪 schema 风险对冲 |
| ReFoRCE | 压缩 schema→候选执行/投票→低置信样本列探索 | 预设分支触发；模型生成探索 SQL，执行反馈修复 | 条件触发的固定流程内迭代探索 |
| APEX-SQL | 抽象计划→正负剪枝→表内 SQL 探索→全局补依赖；生成时继续探查 | 宏观两阶段固定；阶段内模型根据历史与结果选择动作 | 有界的动态探索与假设验证 |
| Spider-Agent | 文件/文档、schema、样本及 SQL 执行观察 | ReAct 式模型逐步选择动作；受动作空间、提示词和预算约束 | 通用环境探索 Agent，非专用多类型召回算法 |

“多类型召回”不自动代表并行执行；上表没有把 CHESS 的多路证据声称为运行时并发。双向召回也不自动代表一致性校验：RSL-SQL 取的是并集，以保召回为目的，并未证明两个方向必须相互同意。

## 2. CHESS：值先于表选择，以及局部 Agent 的实际边界

论文：[CHESS: Contextual Harnessing for Efficient SQL Synthesis，v3](https://arxiv.org/html/2405.16755v3)，2024-11-25。实际阅读 §3 方法、§4.1–4.3 实验和消融、§5 限制、Appendix A.1–A.3；没有把摘要作为全文证据。

### 2.1 对固定召回链最直接的反例

§3.1 的 Information Retriever 有 `extract_keywords`、`retrieve_entity`、`retrieve_context` 三类工具。`retrieve_entity` 根据关键词寻找相似数据库值，同时返回其所属列。它不以已选定的表为前提；当用户只给出某个产品名、公司名或编码片段时，可以先找到值，再带出表/列。

`retrieve_context` 则搜索 catalog 中的列描述、展开的列名和值说明。预处理分别为唯一值建立 LSH 索引，为 catalog 描述建立向量库。论文 Appendix A.1 描述 LSH 缩小候选集，再用 embedding 相似度和字符串编辑相似度细化结果；这不是“对全库所有值做一次昂贵语义检索”。

固定代码中的 `retrieve_entity.py` 还独立匹配候选列名：`_run()` 同时写入 `similar_columns` 和 `schema_with_examples`。值分支实际顺序为 `_get_similar_entities_via_LSH` → 字符串相似度过滤 → embedding 相似度过滤，最后按列汇总值。LSH 查询 `top_n=10`；字符串过滤使用 Python `difflib.SequenceMatcher`，因此不宜把该具体实现称为严格 Levenshtein 编辑距离。论文的文字概要与固定代码在细节顺序、保留值方式上不完全相同，复用时应以选定版本实现为准。

### 2.2 Agent 标签应分层看

官方实现的 `team_builder.py` 把 YAML 配置中的 Agent 按顺序连接成链，如 IR → SS → CG → evaluation；没有顶层模型按需返回 IR 或在任意类型之间路由。

但 `Agent.workout()` 确实有最多 10 步循环：模型输出 `<tool_call>tool_name</tool_call>` 或 `DONE`，IR 局部可选择上述三个工具。因此它也不是完全没有模型选工具的静态函数链。

关键限制在于该固定 commit：`call_agent(system_state)` 虽然接收参数，却没有把 `system_state` 序列化加入消息；`call_tool()` 对成功调用只返回 `Tool X called successfully.`。实际检索数据写入共享 state 供后续工具/生成使用，但本次读到的局部调度消息没有完整回注检索观察。由此只能确认“局部模型选择工具名称”，不能推断为“根据检索到的值和列自由改变全局策略”。这是静态代码观察，未运行验证。

### 2.3 限制与可复用点

- §3.3 承认 schema selection 有 precision/recall 权衡；schema 小且模型强时，裁剪可能降低正确率，并非每次都该先裁剪。
- 工业规模实验通过合并 BIRD 库构造较大 schema；不能把它等同为在任意企业私有库上完成验证。
- 预建值索引适合“值入口”，但不是业务枚举语义、权限、索引更新、同名值歧义的完整方案。
- Unit Tester 的“unit test”由 LLM 生成和判断自然语言语义差别，不等于独立执行的业务断言。

最值得借鉴的是：**值、列名、catalog 描述应拥有独立入口，并保留 value→column→table 的归属关系**。外层是否由 Agent 路由是另一设计问题。

代码固定于 [`3d6e835f858d26885d21d4bc0215aeecf855efbe`](https://github.com/ShayanTalaei/CHESS/tree/3d6e835f858d26885d21d4bc0215aeecf855efbe)（2024-11-13）。已读 `src/workflow/agents/agent.py`、IR 类与 entity/context 工具、`team_builder.py`、配置和 Agent 模板。

## 3. RSL-SQL：正反向取并集，避免过早裁掉必要 schema

论文：[RSL-SQL: Robust Schema Linking in Text-to-SQL Generation，v2](https://arxiv.org/html/2411.00073v2)，2024-11-26。实际阅读 §III 方法及 Algorithm 1、§V 的消融解释、§VII 结论；没有单列的 Limitations 节，以下将论文承认的现象与本文推论区分。

§III-B 的 forward linking 从完整 schema、值样本和问题直接找相关表列；还可从 BIRD `evidence` 找列名。随后使用完整 schema 生成 preliminary SQL，再从该 SQL 中提取被引用列作为 backward linking。作者最终选择列名字符串匹配，以接受噪声换取更高召回，而非严格依赖 SQL parser。两路结果取并集，生成简化的 schema、值样本和描述。

它随后执行固定步骤：

1. Bidirectional Schema Linking；
2. Contextual Information Augmentation：在简化 schema 上生成可能的 schema elements、conditions、keywords，再生成 SQL2；
3. Binary Selection：比较完整 schema SQL1 与简化 schema SQL2 及其执行结果；
4. Multi-Turn Self-Correction：执行失败或空结果时进入有上限的修复循环。

因此，“双向”是 **问题→schema 与初步 SQL→schema 的互补覆盖**，不是“表召回和值召回双向循环”，也不是任意动作选择。完整 schema 路径保留结构完整性，裁剪 schema 路径降低噪声；二选一用于对冲裁剪错误。

固定代码 `bid_schema_linking.py` 可核验 `extract_from_sql()`、`extract_from_hint()`、`merge()`：合并 LLM、SQL、hint 三路集合，最后过滤到真实 schema。代码的判断是 `if column in sql`/`if column in hint` 的子串检测，比论文“exact matching”一词更宽松；重名或短列名会额外召回。

论文 §V-C 明确观察到：对其中较弱模型，双向带来的噪声可能抵消高召回收益，只有 backward 的后续正确率略高；不能把“多召回总更好”当作普遍结论。该方法还依赖完整 schema 能进入最初调用，无法直接解决数万张表目录中的初始定位。空集只是一种修复启发式，业务问题的正确答案可能确实为空。

最值得借鉴的是：**允许初步计划或 SQL 反向补召回，保留完整路径作为 fallback，并评估必要集合是否全部覆盖**。这与从单一路径不断向下裁剪的固定链不同。

代码固定于 [`fb1dcf02923e5fd89171cc6cfe1ae3e4e5bc3b94`](https://github.com/Laqcce-cao/RSL-SQL/tree/fb1dcf02923e5fd89171cc6cfe1ae3e4e5bc3b94)（2025-09-17）。已读 README 的完整命令流程与 `src/bid_schema_linking.py`。

## 4. ReFoRCE：有条件地付出列探索成本

论文：[ReFoRCE: A Text-to-SQL Agent with Self-Refinement, Consensus Enforcement, and Column Exploration，v5](https://arxiv.org/html/2502.00675v5)，2025-06-03。实际阅读 §3 方法、§4.1 实验设置、§4.3 消融、§5.1 限制、Appendix C 算法与提示。官方仓库标题仍使用早期的 “Format Restriction”，不同版本不能混成一个实验。

§3.2 主动将其设计与更不受限的 ReAct 区分。流程先压缩数据库信息：按相似表名模式分组，极长输入再做表级 schema linking；生成并 self-refine 多个 SQL 候选；按执行结果投票。

§3.2.2 的“高置信”具体定义为有唯一最高票结果，**不要求超过一半**；最高票并列的样本进入低置信集合。§3.2.3 才对该集合做 column exploration，而非每题都先探查值。

探索会生成由简单到复杂的 SQL，检查嵌套列、字符串实际格式等；错误执行反馈用于改正当前查询，并修正后续具有相似错误的查询。Appendix C 提示要求最多 10 条 SELECT、每条 LIMIT 20、围绕给定表、禁止 schema inspection。这里模型决定的是探索 SQL 内容，外层触发时机由预设投票分支控制。剩余未解决问题仍有随机选择 fallback。

§4.3 消融指出：对所有样本都探索可扩大候选多样性、提高 top-k 中包含正确解的机会，但最终选中答案的 EX 略降。不能从“探索更广”直接推导“单次用户任务更准”。§5.1 承认在 BIRD 这类强调细粒度 schema 的设置上泛化有限；正文未整合外部专门 value retrieval 模块。gold schema 的额外实验也说明，能够执行探索并不意味着 schema 信息已无价值。

官方代码比论文 v5 更早：[`fd80efad09589f8074df7f8cb52dd10b9c740d45`](https://github.com/Snowflake-Labs/ReFoRCE/tree/fd80efad09589f8074df7f8cb52dd10b9c740d45)（2025-04-30）。已读 README、`methods/ReFoRCE/agent.py` 的 `exploration()`、`execute_sqls()`、`self_refine()`、`vote_result()` 和相关 prompt。代码的 `exploration()` 对少于 10 条 SQL 会重试，而论文提示说“at most 10”；不能假定该仓库精确复现 v5 的全部配置。没有运行其脚本，也未用早期代码核准 v5 成绩。

最值得借鉴的是：**高成本探索应由具体不确定性触发；执行反馈既用于修 SQL，也可修正对值格式与嵌套结构的理解**。但票数是启发式置信信号，多个候选可能共享同一业务错误。

## 5. APEX-SQL：宏观两阶段内，模型选择探索/归纳/生成动作

论文：[APEX-SQL: Talking to the data via Agentic Exploration for Text-to-SQL，v1](https://arxiv.org/html/2602.16720v1)，2026-02-11。实际阅读 §3 方法、§4.3.4 推理配置、§4.4 分析、§5 结论与 Appendix A/C/D 相关提示和案例；没有单列 Limitations 节。论文 HTML 本身没有给出可确认的代码链接；通过腾讯官方仓库 README 反向链接该论文确认实现身份。

### 5.1 Schema linking 中就能查真实数据

§3.2 先生成不依赖具体 schema 名称的逻辑计划，多个计划合成 master plan；再以双路径剪枝缩小目录：负向删除明显无关列、正向选择必要列，合并方式为 `(batch - delete) ∪ keep`。目标是避免过早丢失词面上不相关的 foreign key/桥接依赖。

随后为候选表安排独立探索者，根据预设的表列角色生成探索 SQL，以真实数据验证语义，最后全局综合、补齐 join key/桥表等依赖。与“先把 schema linking 完全做完，再做值探查”相比，它把值与数据模式探查纳入 linking。

### 5.2 SQL generation 的动作确实依赖观察

§3.3 先用逻辑计划推导可能的 SQL 操作路径，以确定性关键词规则查 SQL best practices/tips；规则召回的是**SQL 探索指导**，不能等同为完整企业业务规则库。

随后式(5)明确使下一状态依赖动作空间、指导、历史和观察。动作包含 Profiling、Consolidation、SQL Synthesis、Confirmation。官方 `BIRD/agent.py` 对应 `[EXPLORE]`、`[REFINE]`、`[SQL]`、`[CONFIRM]`，把探索结果作为 System Feedback 送回模型，压缩时保留累积探索证据及最新计划。这个层面具备真实的观察→下一动作回路。

仍然存在硬边界：整体是 schema linking → SQL generation；在裁剪出的候选范围中探索，不是任意值入口的全局异构图漫游。正文推理配置限制 40 actions 与约 56k tokens；耗尽前提示/迫使进入 SQL 合成。多候选选择也另有成本与误差，不应把 pass@8 当最终一次回答准确率。

### 5.3 固定代码与论文概要的差异

官方代码固定于 [`8611d3cda9e439a8af00da1153eda1017f5e3bae`](https://github.com/Tencent/APEX-SQL-Project/tree/8611d3cda9e439a8af00da1153eda1017f5e3bae)（2026-05-18）。实际读取 README、`BIRD/agent.py`、`BIRD/schema_linking.py`、`BIRD/preprocess_select_tips.py`；没有执行仓库代码。

- `BIRD/schema_linking.py` 默认 `enable_pruning=False`，`process_single_case()` 也显式传 `False`。双路径剪枝有实现，但不能说该默认入口一定运行剪枝。
- 表探索使用线程池接口，`DEFAULT_MAX_WORKERS=1`；“每表独立 Agent”与“默认并发执行”是不同事实。
- 单表探查最多两轮；全局 refinement 也有两轮上限，可请求补充 SQL 探索与恢复依赖。结构连通主要由模型提示和探索判断支持，不能当作独立图算法或基数约束已经证明成立。
- `[CONFIRM]` 是模型的再次语义检查。所读代码确认已生成 SQL 后采纳该标签文本；没有独立语义 oracle，因此它不是业务正确性硬验证。

Appendix D 的一个案例先从 10 行样本推断某时间戳全为空，后文又给出另一 NULL 比例，叙述不一致；本文不把该比例或由少量样本推断总体的说法当可靠方法证据。真正可复用的部分是查询实际数据、验证替代字段及 join 映射的动作机制。

最值得借鉴的是：**先提出可被数据反驳的具体假设，再选择探查动作；同时允许全局补依赖，避免单表相关性筛选破坏 join 路径**。这比把一次向量召回包装成 Agent 更接近动态探索。

## 6. RAT-SQL：值链接不是新出现的 Agent 能力

论文：[RAT-SQL: Relation-Aware Schema Encoding and Linking for Text-to-SQL Parsers，v5](https://arxiv.org/html/1911.04942v5)，2021-08-24；ACL 2020 论文。实际阅读 §4 方法、§5.1 指标、§5.2 消融、§5.3 值解码限制、§5.4 错误分析与 §6 结论。

§4 将问题词、列、表组成联合图，预定义外键/主键、所属表关系，并添加双向 question-schema 关系。名称链接使用问题 n-gram 与表列名的 exact/partial match；value-based linking 检测问题词是否作为某列的值或值中的完整词出现，再添加词↔列关系。

因此数据库值可以帮助链接到列，列和表结构再共同影响表示；不是先硬选一张表再考虑字段。但它并不把每一个数据库值都作为独立节点，也不执行一个可自由选择 tool 的 Agent 策略。联合 attention 学习关系权重，与运行时重新选择检索动作是不同机制。

官方 `spider_match_utils.py` 中 `compute_schema_linking()` 与 `compute_cell_value_linking()` 可直接核验：文本值用 SQLite `LIKE` 查词出现，数字按列类型建立 number/time 标记。它不是通用语义实体归一、别名推断或业务规则解释器。

§5.1 明确其 Spider exact-match 指标不评价 SQL value generation；§5.3 在 WikiSQL 的简化指针值解码中，多 token 常量容易失败。因而不能用 RAT-SQL 的 schema linking 效果推导“已解决值生成”。§5.4 也保留了列歧义和业务短语解释错误。

代码固定于 [`051e7d35f3092d2c75b64dc0c7f1d791942d4f19`](https://github.com/microsoft/rat-sql/tree/051e7d35f3092d2c75b64dc0c7f1d791942d4f19)（2021-06-19）。已读 README、`ratsql/models/spider/spider_match_utils.py`。

## 7. Spider-Agent：实际的环境工具探索对照

论文：[Spider 2.0: Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows，v2](https://arxiv.org/html/2411.07763v2)，2025-03-17。此处方法证据来自 §3.1、Appendix C.1 的框架与动作空间，另读 §4 的失败分析；Spider 2.0 的版本/评估区别参见已有 benchmark 报告，不在本文比较榜单。

Spider-Agent 让模型逐轮接收 observation，生成 thought/action，执行后再观察。论文动作包含 `BASH`、`ExecuteSQL`、`GetTables`、`GetTabInfo`、`SampleRows`、文件编辑及终止；这支持从文档、schema 或 SQL 反馈继续探索，而非固定只调用一次表检索。

官方当前 Lite 实现的 `agents.py` 中 `predict(obs)` 把观察发给模型，解析动作，`run()` 调用 `env.step(action)` 后进入下一轮，证据强于从名称猜测 Agent。与此同时提示词仍要求初始读文档/DDL，并限制云端 schema 从本地文件查，不允许直接查 `INFORMATION_SCHEMA`。它是**受环境和提示约束的动态动作选择**，并非无边界探索，也不是专用 value index/业务 ontology 检索器。

代码固定于 [`cafb867313aab4e674652054198f383cf4018943`](https://github.com/xlang-ai/Spider2/tree/cafb867313aab4e674652054198f383cf4018943)（2026-08-12）。实际阅读 `methods/spider-agent-lite/README.md`、`agent/agents.py`、`agent/prompts.py` 以及动作/环境实现的相关定义。论文动作表和后来 Lite 代码不能假定完全一致，因此本文只据两者共同支持的观察→动作→执行循环作判断。

## 8. 对方案设计的约束：哪些能据论文说，哪些仍需自行验证

可以据这些文献提出：多入口召回、值带归属信息反向定位列/表、计划/SQL 反向补召回、全局补桥表、按不确定性追加探查、执行结果回注的有界 Agent policy。它们分别有方法先例，可以组合成 hybrid 系统。

不能据此声称：某个方法已证明任意业务术语可直接映射所有企业规则；全局异构证据图一定优于固定链；更多探索必然提高最终正确率；模型确认或非空执行已经证明业务正确；多 Agent 名称就代表并行、自治或完整观察回灌。这些需要产品自己的配对实验。

评测至少区分：必要表/列/值集合全召回、桥表/连接键覆盖、业务定义来源、索引遗漏与策略遗漏、探索成本、最终严格结果与口径正确。控制模型、数据/ontology 版本、工具权限、上下文与动作预算，比较固定链、多入口合并、有界动态策略；不使用不同论文的成绩拼接排行。更多评测边界见 [已有 benchmark 报告](../dataagent-2026-10-30/03-benchmarks-and-evaluation.md)。

## 9. 来源、缓存和阅读深度

所有访问日期均为 2026-10-31。arXiv URL 使用明确版本；GitHub 使用固定 commit；缓存为 `sources/papers-*`，保存本次原始 HTML/README/源码/API 元数据及机械提取文本。只运行自行编写的 HTTP 抓取与文本提取代码，未运行论文仓库、未调用其模型 API、未复现 benchmark。

| 来源 | 原文固定版本 | 实际阅读层级 | 主要本地缓存 |
| --- | --- | --- | --- |
| CHESS | [arXiv v3](https://arxiv.org/html/2405.16755v3)、[官方 commit](https://github.com/ShayanTalaei/CHESS/tree/3d6e835f858d26885d21d4bc0215aeecf855efbe) | 方法、实验/消融、限制、实现附录；关键代码静态阅读 | `papers-chess-fulltext.txt`、`papers-chess-{agent,ir,entity,context,team,config,template-agent}.txt` |
| RSL-SQL | [arXiv v2](https://arxiv.org/html/2411.00073v2)、[官方 commit](https://github.com/Laqcce-cao/RSL-SQL/tree/fb1dcf02923e5fd89171cc6cfe1ae3e4e5bc3b94) | 方法/算法、消融讨论、结论；流程与 linking 代码 | `papers-rsl-fulltext.txt`、`papers-rsl-bid.txt`、`papers-rsl-readme.txt` |
| ReFoRCE | [arXiv v5](https://arxiv.org/html/2502.00675v5)、[较早官方 commit](https://github.com/Snowflake-Labs/ReFoRCE/tree/fd80efad09589f8074df7f8cb52dd10b9c740d45) | 方法、实验设置、消融、限制、Appendix C；关键代码 | `papers-reforce-fulltext.txt`、`papers-reforce-agent.txt`、`papers-reforce-prompt.txt` |
| APEX-SQL | [arXiv v1](https://arxiv.org/html/2602.16720v1)、[官方 commit](https://github.com/Tencent/APEX-SQL-Project/tree/8611d3cda9e439a8af00da1153eda1017f5e3bae) | 方法、推理配置、分析；相关附录；BIRD 动作与 linking 代码 | `papers-apex-fulltext.txt`、`papers-apex-{readme,agent,schema,tips}.txt` |
| RAT-SQL | [arXiv v5](https://arxiv.org/html/1911.04942v5)、[官方 commit](https://github.com/microsoft/rat-sql/tree/051e7d35f3092d2c75b64dc0c7f1d791942d4f19) | 方法、指标/消融、值解码限制、错误分析；匹配代码 | `papers-ratsql-fulltext.txt`、`papers-ratsql-match.txt` |
| Spider 2.0 / Spider-Agent | [arXiv v2](https://arxiv.org/html/2411.07763v2)、[官方 commit](https://github.com/xlang-ai/Spider2/tree/cafb867313aab4e674652054198f383cf4018943) | §3.1、§4、App C.1；Lite Agent 循环/提示/动作相关定义 | `papers-spider2-fulltext.txt`、`papers-spider2-lite-{agent-code,prompts,actions,env}.txt` |

这里没有 abstract-only 项；“已读方法和相关章节”不意味着逐字审读全文全部公式、参考文献或所有附录，也没有执行验证代码的正确性。普通 main/master README 抓取随后核对到同一 commit 元数据；引用实现时以上述固定 commit 为准。
